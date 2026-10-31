import asyncio
import json
import uuid
import math
from typing import Dict, Optional
from fastapi import WebSocket
from loguru import logger
import aiohttp
from starlette.websockets import WebSocketDisconnect

from .proxy_message_queue import ProxyMessageQueue
from .live.comment_feed import CommentFeed


class ProxyHandler:
    """
    A proxy handler that allows multiple clients to connect through a single WebSocket connection to the server.
    This enables scenarios like having a web client and a live platform both connected to the same VTuber server.
    """

    def __init__(
        self,
        server_url: str = "ws://localhost:12393/client-ws",
        word_game=None,
        singing=None,
        activity=None,
    ):
        """
        Initialize the proxy handler.

        Args:
            server_url: The WebSocket URL of the actual server
        """
        self.server_url = server_url
        self.activity = activity
        self.word_game = word_game
        self.singing = singing
        self._last_sing_notice = float("-inf")
        if singing is not None:
            singing.proxy = self
        self.comment_feed = CommentFeed()
        if word_game is not None:
            word_game.proxy = self
        self.server_ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.clients: Dict[str, WebSocket] = {}
        self.actor_tokens = {}
        self.runtime_v2 = False
        self.connected = False
        self.server_task: Optional[asyncio.Task] = None
        self._init_config: Optional[dict] = None
        self._active_input_source = None
        self.lock = asyncio.Lock()

        # Initialize message queue manager
        self.message_queue = ProxyMessageQueue()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = True
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect_to_server(self):
        """Establish a WebSocket connection to the actual server"""
        if self.connected:
            return

        async with self.lock:
            if self.connected:  # Double-check to prevent race conditions
                return

            try:
                self._init_config = None
                # Create session if not exists
                if not self._session:
                    self._session = aiohttp.ClientSession()
                self.server_ws = await self._session.ws_connect(self.server_url)
                self.connected = True
                logger.info(f"Proxy connected to server at {self.server_url}")

                # Initialize message queue with our forward function
                self.message_queue.initialize(self.forward_with_broadcast)

                # Start heartbeat task
                self._heartbeat_task = asyncio.create_task(self._maintain_connection())

                # Start task to receive messages from server
                self.server_task = asyncio.create_task(self.forward_server_messages())
            except Exception as e:
                logger.error(f"Failed to connect to server: {e}")
                if self._session:
                    await self._session.close()
                    self._session = None
                raise

    async def _maintain_connection(self):
        """Maintain connection with heartbeat and automatic reconnection"""
        while self._running:
            try:
                if self.connected and self.server_ws and not self.server_ws.closed:
                    # Send heartbeat
                    await self.server_ws.send_json({"type": "heartbeat"})
                    await asyncio.sleep(30)  # Heartbeat interval
                else:
                    # Try to reconnect
                    logger.info("Connection lost, attempting to reconnect...")
                    try:
                        await self.connect_to_server()
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                        await asyncio.sleep(5)  # Wait before retry
            except Exception as e:
                logger.error(f"Error in connection maintenance: {e}")
                self.connected = False
                await asyncio.sleep(5)

    async def handle_client_connection(self, websocket: WebSocket):
        """
        Handle a new client connection to the proxy.

        Args:
            websocket: The client's WebSocket connection
        """
        await websocket.accept()

        # Generate a unique client ID
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        from .interaction.ingress import issue_actor, verify_actor

        self.actor_tokens[client_id] = issue_actor()
        logger.info(
            f"Client {client_id} connected to proxy. Total clients: {len(self.clients)}"
        )

        # Ensure server connection is established
        if not self.connected:
            await self.connect_to_server()

        await websocket.send_json(
            {
                "type": "conversation-state",
                "active": self.message_queue.conversation_active,
            }
        )
        if self.word_game is not None:
            await websocket.send_json(self.word_game.game.snapshot())
        if self.singing is not None:
            await websocket.send_json(self.singing.snapshot())

        if self.connected:
            try:
                if self._init_config is not None:
                    # A chat reader reconnect must not reload the avatar or set
                    # the already-speaking desktop back to idle.
                    await websocket.send_json(self._init_config)
                else:
                    init_request = {
                        "type": "request-init-config",
                        "client_id": client_id,
                    }
                    await self.forward_to_server(init_request, client_id)
            except Exception as e:
                logger.error(f"Failed to request initialization: {e}")

        await websocket.send_json(
            {"type": "actor-session", "token": self.actor_tokens[client_id]}
        )
        try:
            # Handle messages from this client
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "resume-actor":
                    if verify_actor(message.get("token")):
                        self.actor_tokens[client_id] = message["token"]
                    await websocket.send_json(
                        {
                            "type": "actor-session",
                            "token": self.actor_tokens[client_id],
                            "force": True,
                        }
                    )
                    continue
                message.pop("_host_ingress", None)
                message.pop("recipient_actor_id", None)
                if self.activity:
                    self.activity(message)

                if message.get("type") == "live-comment":
                    self.comment_feed.add(message)
                    continue
                if message.get("type") == "text-input" and message.get(
                    "source"
                ) not in (
                    "mao-idle-host",
                    "tiktok-live",
                    "youtube-live",
                    "vua-tieng-viet",
                ):
                    self.comment_feed.add({**message, "source": "desktop"})

                if self.singing is not None and await self.handle_sing_message(
                    message, client_id
                ):
                    continue
                if self.word_game is not None and await self.handle_game_message(
                    message, client_id
                ):
                    continue
                # Speech scripts are produced only by the local game service.
                if message.get("source") != "mao-idle-host":
                    message.pop("narration_speech", None)
                for field in ("game_speech", "game_round_id", "game_kind"):
                    message.pop(field, None)
                if message.get("source") == "vua-tieng-viet":
                    message.pop("source", None)

                # Process text-input messages through the queue
                if message.get("type") == "text-input":
                    # Queue the message with the sender's ID
                    if self.message_queue.queue_message(message, client_id) is False:
                        await websocket.send_json(
                            {
                                "type": "input-status",
                                "status": "rejected_busy",
                                "event_id": message.get("event_id"),
                            }
                        )
                # Handle interrupt signals
                elif message.get("type") == "interrupt-signal":
                    logger.info("Received interrupt; wait for backend to end the turn")
                    # Forward the interrupt signal directly
                    await self.forward_to_server(message, client_id)
                else:
                    # Forward other message types directly
                    await self.forward_to_server(message, client_id)

        except WebSocketDisconnect:
            await self.handle_client_disconnect(client_id)
        except Exception as e:
            logger.error(f"Error handling client connection: {e}")
            await self.handle_client_disconnect(client_id)

    async def handle_sing_message(self, message, client_id):
        from .live.singing import parse_song_command
        from .live.vua_tieng_viet import COMMAND

        kind, source = message.get("type"), message.get("source")
        if kind not in ("game-comment", "text-input"):
            return False
        text = str(message.get("text", ""))[:300]
        if parse_song_command(text) is not None:
            stamp = message.get("created_at", 0)
            if (
                not isinstance(stamp, (int, float))
                or isinstance(stamp, bool)
                or not math.isfinite(stamp)
            ):
                stamp = 0
            result = await self.singing.submit(
                text,
                message.get("nickname", "bạn"),
                event_id=f"{source}:{message.get('event_id')}"
                if message.get("event_id")
                else "",
                created_at=stamp,
                operator=kind == "text-input"
                and source not in ("youtube-live", "tiktok-live", "mao-idle-host"),
            )
            if (
                result["status"] not in ("duplicate", "stale")
                and kind == "game-comment"
            ):
                self.comment_feed.add(message)
            await self.clients[client_id].send_json(result)
            if (
                result["status"] not in ("duplicate", "stale")
                and self.singing.clock() - self._last_sing_notice >= 3
            ):
                self._last_sing_notice = self.singing.clock()
                # Feedback stays on Mao's own screen; do not post to live chat
                # or produce one spoken reply for every repeated command.
                await self.broadcast_to_clients(result, exclude_client=client_id)
            if kind == "game-comment":
                await self.clients[client_id].send_json(
                    {
                        "type": "game-comment-ack",
                        "event_id": message.get("event_id", ""),
                        "status": result["status"],
                    }
                )
            # Restore the game reader's state if an earlier command paused it.
            if self.word_game:
                await self.clients[client_id].send_json(self.word_game.game.snapshot())
            return True
        if self.singing.active and COMMAND.fullmatch(text.strip()):
            await self.clients[client_id].send_json(
                self.singing.reply(
                    "busy", "Mao đang hát; chờ hết tiết mục rồi chơi nhé!"
                )
            )
            if kind == "game-comment":
                self.comment_feed.add(message)
                await self.clients[client_id].send_json(
                    {
                        "type": "game-comment-ack",
                        "event_id": message.get("event_id", ""),
                        "status": "busy",
                    }
                )
            if self.word_game:
                await self.clients[client_id].send_json(self.word_game.game.snapshot())
            return True
        if self.singing.active and source == "mao-idle-host":
            await self.clients[client_id].send_json(self.singing.snapshot())
            return True
        return False

    async def handle_game_message(self, message, client_id):
        from .live.vua_tieng_viet import COMMAND

        kind, source = message.get("type"), message.get("source")
        game = self.word_game.game
        if kind == "game-comment":
            text = str(message.get("text", ""))[:300]
            author = str(
                message.get("author_id") or message.get("nickname") or client_id
            )[:120]
            stamp = message.get("created_at", 0)
            if (
                not isinstance(stamp, (int, float))
                or isinstance(stamp, bool)
                or not math.isfinite(stamp)
            ):
                stamp = 0
            status = await self.word_game.submit(
                str(message.get("nickname") or "bạn")[:40],
                text,
                player_id=f"{str(source)[:80]}:{author}",
                event_id=str(message.get("event_id", ""))[:160],
                created_at=stamp,
            )
            if status not in ("duplicate", "stale"):
                self.comment_feed.add(message)
            await self.clients[client_id].send_json(
                {
                    "type": "game-comment-ack",
                    "event_id": message.get("event_id", ""),
                    "status": status,
                }
            )
            # A reader optimistically pauses normal chat on the command. Even
            # a rejected cooldown command must restore its authoritative state.
            if COMMAND.fullmatch(text.strip()):
                await self.clients[client_id].send_json(game.snapshot())
            return True
        if kind != "text-input":
            return False
        text = str(message.get("text", ""))[:300]
        if source == "mao-idle-host" and game.active:
            await self.clients[client_id].send_json(game.snapshot())
            return True
        if COMMAND.fullmatch(text.strip()) or (
            game.active
            and source not in ("mao-idle-host", "youtube-live", "tiktok-live")
        ):
            await self.word_game.submit(
                str(message.get("nickname") or "papa")[:40],
                text,
                player_id="desktop:" + client_id,
            )
            return True
        return False

    async def handle_client_disconnect(self, client_id: str):
        """
        Handle a client disconnection.

        Args:
            client_id: The ID of the disconnected client
        """
        self.clients.pop(client_id, None)
        getattr(self, "actor_tokens", {}).pop(client_id, None)
        logger.info(
            f"Client {client_id} removed. Remaining clients: {len(self.clients)}"
        )

        # If no clients are connected, disconnect from the server
        if not self.clients and self.connected:
            await self.disconnect()

    async def disconnect(self):
        """Disconnect from the server"""
        self._running = False

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.server_ws and not self.server_ws.closed:
            await self.server_ws.close()

        if self.server_task:
            self.server_task.cancel()

        # Close session
        if self._session:
            await self._session.close()
            self._session = None

        self.connected = False
        # Stop and clear the message queue
        self.message_queue.stop()
        self.message_queue.clear()
        logger.info("Proxy disconnected from server")

    async def forward_to_server(self, message: dict, sender_id: Optional[str] = None):
        """
        Forward a message from a client to the server.

        Args:
            message: The message to forward
            sender_id: ID of the client sending the message, to exclude from broadcast
        """
        if not self.connected or not self.server_ws:
            await self.connect_to_server()

        if self.server_ws and not self.server_ws.closed:
            if message.get("type") in {"text-input", "mic-audio-end"} and sender_id:
                from .interaction.ingress import (
                    verify_actor,
                    seal,
                    verify_host_proposal,
                )

                actor = verify_actor(getattr(self, "actor_tokens", {}).get(sender_id))
                if actor:
                    source_key = message.get("event_id")
                    if not isinstance(source_key, str) or len(source_key) > 150:
                        source_key = None
                    message = {
                        **message,
                        "_host_ingress": seal(
                            actor,
                            sender_id,
                            source_key,
                            message.get("source") in {"youtube-live", "tiktok-live"}
                            or verify_host_proposal(message),
                            provider="host"
                            if verify_host_proposal(message)
                            else "proxy",
                        ),
                    }
            await self.server_ws.send_json(message)

    async def forward_server_messages(self):
        """Forward messages from server to all connected clients"""
        try:
            while self.connected and self.server_ws and not self.server_ws.closed:
                try:
                    msg = await self.server_ws.receive()

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            # Parse the message
                            if not msg.data:  # Check if data is empty
                                continue

                            data = json.loads(msg.data)
                            if not data:  # Check if parsed data is empty
                                continue
                            if data.get("type") == "actor-session":
                                self.runtime_v2 = True
                                # Upstream proxy transport identity is never a downstream user's identity.
                                continue

                            if data.get("type") == "set-model-and-conf":
                                self._init_config = {
                                    **(self._init_config or {}),
                                    **data,
                                }
                            if data.get("type") == "control":
                                if data.get("text") == "conversation-chain-start":
                                    self.message_queue.conversation_active = True
                                elif data.get("text") == "conversation-chain-end":
                                    logger.info("Received conversation end signal")
                                    self.message_queue.conversation_active = False
                                    self._active_input_source = None
                            if data.get("type") == "input-status" and data.get(
                                "status"
                            ) in {
                                "duplicate",
                                "rejected_busy",
                                "expired",
                                "superseded",
                                "failed",
                                "interrupted",
                                "declined_policy",
                            }:
                                self.message_queue.conversation_active = False

                            # Broadcast the message to all clients
                            await self.broadcast_to_clients(data)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse message data: {e}")
                            continue
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {self.server_ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        break
                except Exception as e:
                    logger.error(f"Error processing server message: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error forwarding server messages: {e}")
        finally:
            self.connected = False
            self.message_queue.conversation_active = False
            logger.info("Server message forwarding ended")

    async def broadcast_to_clients(
        self, message: dict, exclude_client: Optional[str] = None
    ):
        """
        Broadcast a message to all connected clients.

        Args:
            message: The message to broadcast
            exclude_client: Optional client ID to exclude from broadcast
        """
        if not message:  # Add null check
            return

        disconnected_clients = []

        # Log message, but handle audio data specially to avoid huge logs
        log_msg = (
            message.copy()
            if "audio" not in message
            else {
                **{k: v for k, v in message.items() if k != "audio"},
                "audio": f"[Audio data, {len(message.get('audio') or '')} bytes truncated]",
            }
        )

        if "volumes" in log_msg and len(log_msg.get("volumes") or []) > 10:
            log_msg["volumes"] = f"[{len(message.get('volumes', []))} volume values]"

        logger.debug(
            "Broadcasting message type={} (content omitted)", message.get("type")
        )

        for client_id, websocket in self.clients.items():
            recipient = message.get("recipient_actor_id")
            if recipient:
                from .interaction.ingress import verify_actor

                if (
                    verify_actor(getattr(self, "actor_tokens", {}).get(client_id))
                    != recipient
                ):
                    continue
            # Skip the excluded client
            if exclude_client and client_id == exclude_client:
                continue

            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.handle_client_disconnect(client_id)

    async def forward_with_broadcast(
        self, message: dict, sender_id: Optional[str] = None
    ):
        """
        Forward message to server and handle any necessary broadcasting

        Args:
            message: The message to forward
            sender_id: ID of the client sending the message
        """
        if self.word_game is not None and message.get("source") == "vua-tieng-viet":
            if not self.word_game.game.announcement_valid(
                message.get("game_round_id"), message.get("game_kind")
            ):
                if message.get("type") == "text-input":
                    self.message_queue.conversation_active = False
                    await self.broadcast_to_clients(
                        {"type": "conversation-state", "active": False}
                    )
                return
        if (
            self.word_game is not None
            and self.word_game.game.active
            and message.get("source") == "mao-idle-host"
        ):
            # An idle turn may have been queued just before the game command.
            if message.get("type") == "text-input":
                self.message_queue.conversation_active = False
            return
        # Queue-generated transcripts are local display/activity events, not
        # another backend input (which would be interpreted twice).
        if message.get("type") == "user-input-transcription":
            if getattr(self, "runtime_v2", False):
                from .interaction.ingress import verify_actor, verify_host_proposal

                public = message.get("source") in {
                    "youtube-live",
                    "tiktok-live",
                } or verify_host_proposal({**message, "type": "text-input"})
                actor = verify_actor(self.actor_tokens.get(sender_id))
                if actor and not public:
                    message = {**message, "recipient_actor_id": actor}
            await self.broadcast_to_clients(
                message,
                exclude_client=None
                if message.get("source") in ("tiktok-live", "youtube-live")
                else sender_id,
            )
            return
        if message.get("type") == "text-input":
            self._active_input_source = message.get("source")
        await self.forward_to_server(message, sender_id)
