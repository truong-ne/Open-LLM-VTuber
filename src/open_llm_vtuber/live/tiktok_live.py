import asyncio
import json
import time
import traceback
from collections import deque
from typing import Callable, Dict, Any, List, Optional, Deque, Tuple

import websockets
from loguru import logger

from .live_interface import LivePlatformInterface

# Import the TikTokLive library (unofficial TikTok LIVE client)
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent

    TIKTOKLIVE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"TikTokLive import failed: {e}")
    logger.warning("TikTok live functionality will not be available.")
    TIKTOKLIVE_AVAILABLE = False


class TikTokLivePlatform(LivePlatformInterface):
    """
    Implementation of LivePlatformInterface for TikTok LIVE.
    Reads comments from a TikTok live room and forwards them to the VTuber.

    TikTok chats can be much faster than the VTuber can answer, so comments are
    kept in a bounded buffer (oldest dropped first) and only sent to the VTuber
    when it has finished the previous answer. Several recent comments are
    merged into a single turn.
    """

    def __init__(
        self,
        unique_id: str,
        batch_size: int = 3,
        max_pending_comments: int = 20,
        min_interval: float = 2.0,
        response_timeout: float = 90.0,
        include_nickname: bool = True,
        blocked_words: Optional[List[str]] = None,
        proxy_url: str = "ws://localhost:12393/proxy-ws",
    ):
        """
        Initialize the TikTok Live platform client.

        Args:
            unique_id: TikTok username of the streamer (with or without '@')
            batch_size: Max number of comments merged into one VTuber turn
            max_pending_comments: Max comments kept while the VTuber is busy
            min_interval: Minimum seconds between two VTuber turns
            response_timeout: Seconds to wait for the VTuber to finish before
                assuming the answer was lost and sending the next comments
            include_nickname: Prefix each comment with the viewer's nickname
            blocked_words: Comments containing any of these words are ignored
            proxy_url: WebSocket URL of the VTuber proxy endpoint
        """
        if not TIKTOKLIVE_AVAILABLE:
            raise ImportError(
                "TikTokLive library is required for TikTok live functionality"
            )

        self._unique_id = unique_id if unique_id.startswith("@") else f"@{unique_id}"
        self._batch_size = max(1, batch_size)
        self._min_interval = min_interval
        self._response_timeout = response_timeout
        self._include_nickname = include_nickname
        self._blocked_words = [w.lower() for w in (blocked_words or []) if w]
        self._proxy_url = proxy_url

        self._client: Optional[TikTokLiveClient] = None
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._running = False
        self._message_handlers: List[Callable[[Dict[str, Any]], None]] = []

        # (nickname, comment) pairs waiting to be answered
        self._pending: Deque[Tuple[str, str]] = deque(
            maxlen=max(1, max_pending_comments)
        )
        self._conversation_active = False
        self._last_sent_at = 0.0

    @property
    def is_connected(self) -> bool:
        """Check if connected to the proxy server."""
        try:
            if hasattr(self._websocket, "closed"):
                return (
                    self._connected and self._websocket and not self._websocket.closed
                )
            elif hasattr(self._websocket, "open"):
                return self._connected and self._websocket and self._websocket.open
            else:
                return self._connected and self._websocket is not None
        except Exception:
            return False

    async def connect(self, proxy_url: str) -> bool:
        """
        Connect to the proxy WebSocket server.

        Args:
            proxy_url: The WebSocket URL of the proxy

        Returns:
            bool: True if connection successful
        """
        try:
            self._websocket = await websockets.connect(
                proxy_url, ping_interval=20, ping_timeout=10, close_timeout=5
            )
            self._connected = True
            logger.info(f"Connected to proxy at {proxy_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to proxy: {e}")
            return False

    async def disconnect(self) -> None:
        """
        Disconnect from the proxy server and stop the TikTok client.
        """
        self._running = False

        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error while stopping TikTok client: {e}")
            self._client = None

        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.warning(f"Error while closing WebSocket: {e}")

        self._connected = False
        logger.info("Disconnected from TikTok Live and proxy server")

    async def send_message(self, text: str) -> bool:
        """
        Send a text message back to the live room.
        Not supported: TikTok Live platform only reads comments.
        """
        logger.warning(
            "TikTok Live platform doesn't support sending messages back to the live room"
        )
        return False

    async def register_message_handler(
        self, handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Register a callback for handling incoming messages.

        Args:
            handler: Function to call when a message is received
        """
        self._message_handlers.append(handler)
        logger.debug("Registered new message handler")

    def _accept_comment(self, nickname: str, comment: str) -> None:
        """
        Filter a TikTok comment and add it to the pending buffer.

        Args:
            nickname: Display name of the viewer
            comment: The comment text
        """
        comment = (comment or "").strip()
        if not comment:
            return
        lowered = comment.lower()
        if any(word in lowered for word in self._blocked_words):
            logger.debug(f"Ignored blocked comment from {nickname}: {comment}")
            return

        if len(self._pending) == self._pending.maxlen:
            logger.debug("Comment buffer full, dropping oldest comment")
        self._pending.append((nickname, comment))

    def _build_turn_text(self, comments: List[Tuple[str, str]]) -> str:
        """
        Merge several comments into the text sent to the VTuber.

        Args:
            comments: (nickname, comment) pairs, oldest first

        Returns:
            str: Text for a single VTuber turn
        """
        if not self._include_nickname:
            return "\n".join(comment for _, comment in comments)
        return "\n".join(f"{nickname}: {comment}" for nickname, comment in comments)

    async def _dispatch_loop(self) -> None:
        """
        Send buffered comments to the VTuber whenever it is free to answer.
        """
        while self._running:
            await asyncio.sleep(0.2)

            now = time.monotonic()
            if self._conversation_active:
                if now - self._last_sent_at < self._response_timeout:
                    continue
                logger.warning(
                    "No conversation end signal received in time, sending next comments"
                )
                self._conversation_active = False

            if not self._pending or now - self._last_sent_at < self._min_interval:
                continue

            # Answer the most recent comments; older ones are stale on a live chat
            comments = list(self._pending)[-self._batch_size :]
            self._pending.clear()

            if await self._send_to_proxy(self._build_turn_text(comments)):
                self._conversation_active = True
                self._last_sent_at = now

    async def _send_to_proxy(self, text: str) -> bool:
        """
        Send comment text to the proxy.

        Args:
            text: The comment text to send

        Returns:
            bool: True if sent successfully
        """
        if not self.is_connected:
            logger.error("Cannot send message: Not connected to proxy")
            return False

        try:
            message = {"type": "text-input", "text": text}
            await self._websocket.send(json.dumps(message))
            logger.info(f"Sent comments to VTuber: {text}")
            return True
        except Exception as e:
            logger.error(f"Error sending message to proxy: {e}")
            self._connected = False
            return False

    async def start_receiving(self) -> None:
        """
        Start receiving messages from the proxy WebSocket.
        This runs in the background to receive messages from the VTuber.
        """
        if not self.is_connected:
            logger.error("Cannot start receiving: Not connected to proxy")
            return

        try:
            logger.info("Started receiving messages from proxy")
            while self._running and self.is_connected:
                try:
                    message = await self._websocket.recv()
                    data = json.loads(message)

                    if "audio" in data:
                        log_data = data.copy()
                        log_data["audio"] = (
                            f"[Audio data, length: {len(data['audio'])}]"
                        )
                        logger.debug(f"Received message from VTuber: {log_data}")
                    else:
                        logger.debug(f"Received message from VTuber: {data}")

                    await self.handle_incoming_messages(data)

                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed by server")
                    self._connected = False
                    break
                except Exception as e:
                    logger.error(f"Error receiving message from proxy: {e}")
                    await asyncio.sleep(1)

            logger.info("Stopped receiving messages from proxy")
        except Exception as e:
            logger.error(f"Error in message receiving loop: {e}")

    async def handle_incoming_messages(self, message: Dict[str, Any]) -> None:
        """
        Process messages received from the VTuber.

        Args:
            message: The message received from the VTuber
        """
        if (
            message.get("type") == "control"
            and message.get("text") == "conversation-chain-end"
        ):
            self._conversation_active = False

        for handler in self._message_handlers:
            try:
                await asyncio.to_thread(handler, message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")

    def _create_client(self) -> "TikTokLiveClient":
        """Create the TikTok client and attach event listeners."""
        client = TikTokLiveClient(unique_id=self._unique_id)

        async def on_connect(event: ConnectEvent) -> None:
            logger.info(f"Connected to TikTok LIVE of {self._unique_id}")

        async def on_disconnect(event: DisconnectEvent) -> None:
            logger.warning(f"Disconnected from TikTok LIVE of {self._unique_id}")

        async def on_comment(event: CommentEvent) -> None:
            user = getattr(event, "user", None)
            nickname = (
                getattr(user, "nickname", None)
                or getattr(user, "unique_id", None)
                or "viewer"
            )
            # TikTokLive v7 names it 'content'; older versions used 'comment'
            comment = getattr(event, "content", None) or getattr(event, "comment", "")
            logger.debug(f"[TikTok] {nickname}: {comment}")
            self._accept_comment(nickname, comment)

        client.add_listener(ConnectEvent, on_connect)
        client.add_listener(DisconnectEvent, on_disconnect)
        client.add_listener(CommentEvent, on_comment)
        return client

    async def run(self) -> None:
        """
        Main entry point for running the TikTok Live platform client.
        Connects to the proxy and the TikTok live room, then forwards comments.
        """
        receive_task: Optional[asyncio.Task] = None
        dispatch_task: Optional[asyncio.Task] = None

        try:
            self._running = True

            if not await self.connect(self._proxy_url):
                logger.error("Failed to connect to proxy, exiting")
                return

            receive_task = asyncio.create_task(self.start_receiving())
            dispatch_task = asyncio.create_task(self._dispatch_loop())

            self._client = self._create_client()
            logger.info(f"Connecting to TikTok LIVE of {self._unique_id}")

            # Blocks until the live ends or the connection drops
            await self._client.connect()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        except Exception as e:
            logger.error(f"Error in TikTok Live run loop: {e}")
            logger.debug(traceback.format_exc())
        finally:
            for task in (dispatch_task, receive_task):
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            await self.disconnect()
