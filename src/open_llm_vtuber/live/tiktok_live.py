import asyncio
import traceback
from typing import Optional

from loguru import logger

from .idle_host import ChatActivity

# Import the TikTokLive library (unofficial TikTok LIVE client)
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, JoinEvent

    TIKTOKLIVE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"TikTokLive import failed: {e}")
    logger.warning("TikTok live functionality will not be available.")
    TIKTOKLIVE_AVAILABLE = False


from .buffered_chat import BufferedLiveChat


class TikTokLivePlatform(BufferedLiveChat):
    """TikTok transport; queue/deduplication is shared with YouTube."""

    def __init__(self, unique_id, *args, **kwargs):
        if not TIKTOKLIVE_AVAILABLE:
            raise ImportError(
                "TikTokLive library is required for TikTok live functionality"
            )
        super().__init__(
            unique_id if unique_id.startswith("@") else f"@{unique_id}",
            *args,
            activity=ChatActivity(),
            **kwargs,
        )

    async def disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as error:
                logger.warning("TikTok disconnect failed: {}", error)
            self._client = None
        await super().disconnect()

    def _is_new_event(self, event) -> bool:
        common = getattr(event, "common", None)
        timestamp = self._event_time(event)
        if timestamp and timestamp < self._listen_started_at - 5:
            logger.debug("Ignored historical TikTok event (created {})", timestamp)
            return False
        message_id = getattr(common, "msg_id", 0)
        if message_id:
            if message_id in self._seen_event_ids:
                return False
            self._seen_event_ids.append(message_id)
        return True

    @staticmethod
    def _event_time(event):
        timestamp = getattr(getattr(event, "common", None), "create_time", 0) or 0
        # TikTok may provide seconds, milliseconds or microseconds.
        while timestamp > 100_000_000_000:
            timestamp /= 1000
        return timestamp

    def _create_client(self) -> "TikTokLiveClient":
        """Create the TikTok client and attach event listeners."""
        client = TikTokLiveClient(unique_id=self._unique_id)

        async def on_connect(event: ConnectEvent) -> None:
            logger.info(f"Connected to TikTok LIVE of {self._unique_id}")

        async def on_disconnect(event: DisconnectEvent) -> None:
            logger.warning(f"Disconnected from TikTok LIVE of {self._unique_id}")

        async def on_comment(event: CommentEvent) -> None:
            if not self._is_new_event(event):
                return
            user = getattr(event, "user", None)
            nickname = (
                getattr(user, "nickname", None)
                or getattr(user, "unique_id", None)
                or "viewer"
            )
            # TikTokLive v7 names it 'content'; older versions used 'comment'
            comment = getattr(event, "content", None) or getattr(event, "comment", "")
            event_key = self._comment_state.identity(
                self._unique_id,
                getattr(getattr(event, "common", None), "msg_id", 0),
                self._event_time(event),
                getattr(user, "id", None) or nickname.casefold(),
                comment,
            )
            logger.debug(f"[TikTok] {nickname}: {comment}")
            self._accept_comment(
                nickname,
                comment,
                event_key=event_key,
                created_at=self._event_time(event),
                author_id=getattr(user, "id", None)
                or getattr(user, "unique_id", None)
                or nickname,
            )

        async def on_join(event: JoinEvent) -> None:
            # WebcastMemberMessage also carries subscriptions (action=3).
            if getattr(event, "action", 0) != 1:  # JOINED
                return
            if not self._is_new_event(event):
                return
            user = getattr(event, "user", None)
            nickname = getattr(user, "nickname", "")
            viewer_id = (
                getattr(user, "id", None)
                or getattr(user, "id_str", None)
                or getattr(event, "user_id", "")
            )
            self._accept_join(nickname, viewer_id)

        client.add_listener(ConnectEvent, on_connect)
        client.add_listener(DisconnectEvent, on_disconnect)
        client.add_listener(CommentEvent, on_comment)
        client.add_listener(JoinEvent, on_join)
        return client

    async def run(self) -> None:
        """
        Main entry point for running the TikTok Live platform client.
        Connects to the proxy and the TikTok live room, then forwards comments.
        """
        receive_task: Optional[asyncio.Task] = None
        dispatch_task: Optional[asyncio.Task] = None
        live_task: Optional[asyncio.Task] = None

        try:
            self._running = True

            if not await self.connect(self._proxy_url):
                logger.error("Failed to connect to proxy, exiting")
                return

            receive_task = asyncio.create_task(self.start_receiving())
            dispatch_task = asyncio.create_task(self._dispatch_loop())

            self._client = self._create_client()
            logger.info(f"Connecting to TikTok LIVE of {self._unique_id}")

            # Observe all workers. A dead receiver/dispatcher must not leave a
            # healthy TikTok socket running with a permanently stuck queue.
            live_task = asyncio.create_task(
                self._client.connect(process_connect_events=False)
            )
            done, _ = await asyncio.wait(
                {live_task, receive_task, dispatch_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                await task

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        except Exception as e:
            logger.error(f"Error in TikTok Live run loop: {e}")
            logger.debug(traceback.format_exc())
        finally:
            tasks = [task for task in (dispatch_task, receive_task, live_task) if task]
            for task in tasks:
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.disconnect()
