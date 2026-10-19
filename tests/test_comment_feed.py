import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock
from starlette.websockets import WebSocketDisconnect

from src.open_llm_vtuber.live.buffered_chat import BufferedLiveChat
from src.open_llm_vtuber.live.comment_feed import CommentFeed
from src.open_llm_vtuber.live.idle_host import ChatActivity
from src.open_llm_vtuber.proxy_handler import ProxyHandler
from src.open_llm_vtuber.live.vua_tieng_viet import WordGameService


class CommentFeedTests(unittest.TestCase):
    def test_bounded_deduplication_is_scoped_to_source_and_survives_eviction(self):
        feed = CommentFeed(limit=2, clock=lambda: 1000)
        first = {
            "text": "!vuatiengviet",
            "nickname": "Lan",
            "source": "youtube:test",
            "event_id": "one",
        }
        self.assertTrue(feed.add(first))
        self.assertFalse(feed.add(first))
        feed.add({**first, "source": "@tiktok"})
        feed.add({**first, "event_id": "three", "text": "đáp án của mình"})
        self.assertFalse(feed.add(first))
        public = feed.snapshot()
        self.assertEqual([row["id"] for row in public["comments"]], [2, 3])
        self.assertEqual(public["comments"][0]["platform"], "tiktok")
        self.assertEqual(public["comments"][1]["received_at"], 1000)
        self.assertNotIn("event_id", public["comments"][0])

    def test_incremental_feed_and_new_session_reset(self):
        feed = CommentFeed()
        for i in range(3):
            feed.add({"text": f"Comment {i}"})
        self.assertEqual(
            len(feed.snapshot(after=2, session=feed.session)["comments"]), 1
        )
        self.assertEqual(
            len(feed.snapshot(after=3, session="previous-boot")["comments"]), 3
        )
        self.assertEqual(
            len(feed.snapshot(after=100, session=feed.session)["comments"]), 3
        )

    def test_public_rows_keep_literal_text_and_limit_size(self):
        feed = CommentFeed()
        self.assertFalse(feed.add({"text": []}))
        self.assertFalse(feed.add({"text": "  "}))
        feed.add(
            {
                "text": "<img onerror=bad>" + "x" * 500,
                "nickname": "<script>" + "n" * 100,
            }
        )
        row = feed.snapshot()["comments"][0]
        self.assertTrue(row["text"].startswith("<img onerror=bad>"))
        self.assertEqual(len(row["text"]), 300)
        self.assertEqual(len(row["nickname"]), 40)


class CommentFeedReaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_comment_display_does_not_wait_for_speech_or_duplicate_spoken_turns(
        self,
    ):
        with tempfile.TemporaryDirectory() as folder:

            class Reader(BufferedLiveChat):
                async def run(self):
                    pass

            reader = Reader(
                "youtube:test",
                comment_state_path=Path(folder) / "state.db",
                activity=ChatActivity(Path(folder) / "activity.json"),
                batch_window=0,
            )
            reader._connected = reader._state_known = True
            reader._conversation_active = True
            reader._websocket = Mock(closed=False, send=AsyncMock())
            reader._accept_comment("Lan", "Mao dễ thương quá", event_key="display-1")
            await reader._dispatch_once()
            payloads = [
                json.loads(call.args[0])
                for call in reader._websocket.send.call_args_list
            ]
            self.assertEqual([row["type"] for row in payloads], ["live-comment"])
            self.assertEqual(payloads[0]["text"], "Mao dễ thương quá")
            self.assertEqual(len(reader._pending), 1)
            reader._conversation_active = False
            await reader._dispatch_once()
            payloads = [
                json.loads(call.args[0])
                for call in reader._websocket.send.call_args_list
            ]
            self.assertEqual(
                [row["type"] for row in payloads], ["live-comment", "text-input"]
            )


class CommentFeedProxyTests(unittest.IsolatedAsyncioTestCase):
    async def test_display_event_is_not_a_game_guess_or_agent_input(self):
        proxy = ProxyHandler(word_game=WordGameService())
        proxy.connected = True
        proxy._init_config = {"type": "set-model-and-conf"}
        proxy.clients["existing-desktop"] = Mock()
        proxy.forward_to_server = AsyncMock()
        proxy.message_queue.queue_message = Mock()
        websocket = Mock(
            send_json=AsyncMock(),
            accept=AsyncMock(),
            receive_json=AsyncMock(
                side_effect=[
                    {
                        "type": "live-comment",
                        "source": "youtube:test",
                        "nickname": "Lan",
                        "text": "!vuatiengviet",
                        "event_id": "display-only",
                    },
                    WebSocketDisconnect(),
                ]
            ),
        )
        await proxy.handle_client_connection(websocket)
        self.assertEqual(proxy.word_game.game.phase, "idle")
        self.assertEqual(
            proxy.comment_feed.snapshot()["comments"][0]["text"], "!vuatiengviet"
        )
        proxy.message_queue.queue_message.assert_not_called()
        proxy.forward_to_server.assert_not_awaited()

    async def test_desktop_comment_is_shown_but_host_instruction_is_not(self):
        proxy = ProxyHandler()
        proxy.connected = True
        proxy._init_config = {"type": "set-model-and-conf"}
        proxy.clients["existing-desktop"] = Mock()
        proxy.message_queue.queue_message = Mock()
        websocket = Mock(
            send_json=AsyncMock(),
            accept=AsyncMock(),
            receive_json=AsyncMock(
                side_effect=[
                    {"type": "text-input", "text": "Chào Mao"},
                    {
                        "type": "text-input",
                        "text": "Internal host instruction",
                        "source": "mao-idle-host",
                    },
                    WebSocketDisconnect(),
                ]
            ),
        )
        await proxy.handle_client_connection(websocket)
        self.assertEqual(
            [row["text"] for row in proxy.comment_feed.snapshot()["comments"]],
            ["Chào Mao"],
        )
        self.assertEqual(proxy.message_queue.queue_message.call_count, 2)

    async def test_game_command_is_shown_once_and_still_starts_a_round(self):
        proxy = ProxyHandler(word_game=WordGameService())
        proxy.clients["reader"] = Mock(send_json=AsyncMock())
        command = {
            "type": "game-comment",
            "text": "!vuatiengviet",
            "nickname": "Lan",
            "source": "youtube:test",
            "event_id": "start-1",
        }
        await proxy.handle_game_message(command, "reader")
        await proxy.handle_game_message(command, "reader")
        self.assertEqual(proxy.word_game.game.phase, "waiting")
        self.assertEqual(len(proxy.comment_feed.snapshot()["comments"]), 1)

    async def test_failed_display_send_can_retry_without_losing_comment(self):
        with tempfile.TemporaryDirectory() as folder:

            class Reader(BufferedLiveChat):
                async def run(self):
                    pass

            reader = Reader(
                "youtube:test",
                comment_state_path=Path(folder) / "state.db",
                activity=ChatActivity(Path(folder) / "activity.json"),
            )
            reader._connected = reader._state_known = True
            reader._conversation_active = True
            reader._websocket = Mock(
                closed=False,
                send=AsyncMock(side_effect=[RuntimeError("disconnect"), None]),
            )
            reader._accept_comment("Lan", "Chào Mao", event_key="retry-1")
            await reader._dispatch_once()
            self.assertEqual(len(reader._display_comments), 1)
            reader._connected = True
            await reader._dispatch_once()
            self.assertFalse(reader._display_comments)
            self.assertEqual(len(reader._pending), 1)
