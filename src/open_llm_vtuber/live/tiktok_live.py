import asyncio
import traceback
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from .idle_host import ChatActivity
from .idle_host_storage import write_json

# Import the TikTokLive library (unofficial TikTok LIVE client)
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import (
        CommentEvent,
        ConnectEvent,
        DisconnectEvent,
        JoinEvent,
        GiftEvent,
    )
    from TikTokLive.client.errors import UserOfflineError

    TIKTOKLIVE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"TikTokLive import failed: {e}")
    logger.warning("TikTok live functionality will not be available.")
    TIKTOKLIVE_AVAILABLE = False


from .buffered_chat import BufferedLiveChat


class TikTokLivePlatform(BufferedLiveChat):
    """TikTok transport; queue/deduplication is shared with YouTube."""

    def __init__(
        self, unique_id, *args, classroom_only=False, health_path=None, **kwargs
    ):
        self._health_path = Path(health_path) if health_path else None
        self._reader_health = {
            "connected": False,
            "comments_received": 0,
            "fresh_comments": 0,
            "ignored_comments": 0,
            "last_comment_at": 0,
        }
        self._gifts = None
        self.classroom_only = classroom_only
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

    def _accept_gift(self, event):
        from .gifts import GiftStore

        if getattr(event, "streaking", False):
            return False
        if self.classroom_only and (
            not self._classroom_enabled
            or self._classroom_account.casefold() != self._unique_id.casefold()
        ):
            return False
        new_event = self._is_new_event(event)
        user = getattr(event, "user", None)
        gift = getattr(event, "gift", None)
        common = getattr(event, "common", None)
        if gift is None:
            return False
        player = getattr(user, "id", None) or getattr(user, "unique_id", None)
        msg_id = getattr(common, "msg_id", 0)
        group = getattr(event, "group_id", 0)
        streakable = getattr(gift, "type", 0) == 1
        if not new_event and (
            not streakable
            or (
                self._event_time(event)
                and self._event_time(event) < getattr(self, "_listen_started_at", 0) - 5
            )
        ):
            return False
        identity = (
            f"combo:{group}:{player}:{getattr(gift, 'id', 0)}"
            if streakable and group
            else f"msg:{msg_id}"
        )
        if not player or not (msg_id or (streakable and group)):
            return False
        if self._gifts is None:
            self._gifts = GiftStore(
                self._comment_state.path.with_name("mao-gifts.sqlite3")
            )
        room = getattr(self._client, "room_id", "")
        accepted = self._gifts.record(
            self._unique_id,
            f"{room}:{identity}",
            str(player),
            getattr(user, "nickname", None)
            or getattr(user, "unique_id", None)
            or "Bạn",
            getattr(gift, "name", None) or "quà",
            max(1, int(getattr(event, "repeat_count", 1) or 1)),
            int(getattr(gift, "diamond_count", 0)),
        )
        if accepted:
            self._write_health(
                last_event_at=time.time(),
                last_event_type="gift",
                last_gift_repeat_count=int(getattr(event, "repeat_count", 1) or 1),
                last_gift_combo_count=int(getattr(event, "combo_count", 0) or 0),
            )
        return accepted

    def _write_health(self, **updates):
        self._reader_health.update(updates)
        if self._health_path:
            write_json(
                self._health_path,
                {
                    **self._reader_health,
                    "account": self._unique_id,
                    "pending": len(self._pending),
                    "updated_at": time.time(),
                },
            )

    async def _check_current_room(self):
        if self._client is None:
            return
        fresh = await asyncio.wait_for(
            self._client.web.fetch_room_id_from_api(self._unique_id.lstrip("@")), 10
        )
        current = getattr(self._client, "room_id", None)
        self._write_health(
            room_id=str(current),
            resolved_room_id=str(fresh),
            last_room_check_at=time.time(),
        )
        if fresh and current and str(fresh) != str(current):
            raise RuntimeError(
                "TikTok LIVE room changed; reconnecting to the current broadcast"
            )

    async def _watch_room(self):
        while self._running:
            await asyncio.sleep(30)
            try:
                await self._check_current_room()
            except (asyncio.TimeoutError, ConnectionError):
                continue

    def _accept_comment(self, nickname, comment, **kwargs):
        if self.classroom_only and (
            not self._classroom_enabled
            or self._classroom_account.casefold() != self._unique_id.casefold()
        ):
            return
        return super()._accept_comment(nickname, comment, **kwargs)

    def _accept_join(self, nickname, viewer_id):
        if self.classroom_only or self._classroom_enabled:
            return
        return super()._accept_join(nickname, viewer_id)

    async def disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as error:
                logger.warning("TikTok disconnect failed: {}", error)
            try:
                await self._client.web.close()
            except Exception:
                logger.debug("TikTok HTTP client already closed")
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
            self._write_health(
                connected=True,
                phase="connected",
                last_error="",
                room_id=str(getattr(client, "room_id", "")),
                connected_at=time.time(),
            )
            logger.info(
                "Connected to TikTok LIVE of {} (room {})",
                self._unique_id,
                getattr(client, "room_id", None),
            )

        async def on_disconnect(event: DisconnectEvent) -> None:
            self._write_health(
                connected=False,
                phase="offline"
                if self._reader_health.get("phase") == "offline"
                else "disconnected",
            )
            logger.warning(f"Disconnected from TikTok LIVE of {self._unique_id}")

        async def on_comment(event: CommentEvent) -> None:
            user = getattr(event, "user", None)
            nickname = (
                getattr(user, "nickname", None)
                or getattr(user, "unique_id", None)
                or "viewer"
            )
            comment = getattr(event, "content", None) or getattr(event, "comment", "")
            event_key = self._comment_state.identity(
                self._unique_id,
                getattr(getattr(event, "common", None), "msg_id", 0),
                self._event_time(event),
                getattr(user, "id", None) or nickname.casefold(),
                comment,
            )
            first_seen = self._comment_state.audit(
                event_key, self._unique_id, nickname, comment
            )
            self._reader_health["comments_received"] += 1
            if not self._is_new_event(event):
                if first_seen:
                    self._comment_state.stage(
                        [event_key], "skipped", "historical_or_duplicate_event"
                    )
                self._reader_health["ignored_comments"] += 1
                self._write_health(
                    last_comment_at=time.time(),
                    last_source_timestamp=self._event_time(event),
                )
                return
            self._reader_health["fresh_comments"] += 1
            self._write_health(
                last_comment_at=time.time(),
                last_fresh_comment_at=time.time(),
                last_event_at=time.time(),
                last_event_type="comment",
                last_source_timestamp=self._event_time(event),
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
            self._write_health(last_event_at=time.time(), last_event_type="join")
            user = getattr(event, "user", None)
            nickname = getattr(user, "nickname", "")
            viewer_id = (
                getattr(user, "id", None)
                or getattr(user, "id_str", None)
                or getattr(event, "user_id", "")
            )
            self._accept_join(nickname, viewer_id)

        async def on_gift(event: GiftEvent) -> None:
            self._accept_gift(event)

        client.add_listener(GiftEvent, on_gift)
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
        room_task: Optional[asyncio.Task] = None

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
            room_id = None
            try:
                room_id = await asyncio.wait_for(
                    self._client.web.fetch_room_id_from_api(
                        self._unique_id.lstrip("@")
                    ),
                    10,
                )
                self._write_health(resolved_room_id=str(room_id))
            except Exception as error:
                logger.warning(
                    "Current TikTok room lookup: {}; using client fallback",
                    type(error).__name__,
                )
            live_task = asyncio.create_task(
                self._client.connect(process_connect_events=False, room_id=room_id)
            )
            room_task = asyncio.create_task(self._watch_room())
            done, _ = await asyncio.wait(
                {live_task, receive_task, dispatch_task, room_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                await task

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        except UserOfflineError:
            self._write_health(connected=False, phase="offline", last_error="")
            logger.info("TikTok LIVE is offline; waiting for the next broadcast")
        except Exception as e:
            self._write_health(
                connected=False, phase="reconnecting", last_error=type(e).__name__
            )
            logger.error(f"Error in TikTok Live run loop: {e}")
            logger.debug(traceback.format_exc())
        finally:
            tasks = [
                task
                for task in (dispatch_task, receive_task, live_task, room_task)
                if task
            ]
            for task in tasks:
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.disconnect()
