import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.live.youtube_live import (
    YouTubeLivePlatform,
    youtube_url,
    live_video_from_page,
)
from src.open_llm_vtuber.live.idle_host import ChatActivity, IdleHost
from src.open_llm_vtuber.live.comment_state import CommentState
from src.open_llm_vtuber.proxy_handler import ProxyHandler
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent


class YouTubeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reader = self.new_reader()
        self.reader._connected = True
        self.reader._state_known = True
        self.reader._websocket = Mock(closed=False, send=AsyncMock())
        self.reader._batch_window = 0
        self.reader._listen_started_at = time.time() - 1

    def new_reader(self):
        return YouTubeLivePlatform(
            "@sejuly-02",
            status_path=self.root / "status.json",
            comment_state_path=self.root / "comments.db",
            activity=ChatActivity(self.root / "activity.json"),
        )

    def event(self, ident="one", **updates):
        return dict(
            message_id=ident,
            timestamp=int(time.time() * 1_000_000),
            message="Hi Mao!",
            message_type="text_message",
            action_type="add_chat_item",
            author={"name": "Bắp", "id": "UCviewer"},
            **updates,
        )

    def test_strict_target_urls(self):
        self.assertEqual(
            youtube_url("@sejuly-02"), "https://www.youtube.com/@sejuly-02/live"
        )
        self.assertEqual(
            youtube_url("https://youtu.be/abcdefghijk?t=3"),
            "https://www.youtube.com/watch?v=abcdefghijk",
        )
        for bad in (
            "file:///tmp/a",
            "https://youtube.com.evil/watch?v=abcdefghijk",
            "https://user@youtube.com/@sejuly-02",
            "https://youtube.com:443/@sejuly-02",
            "https://youtube.com/playlist?list=anything",
        ):
            with self.assertRaises(ValueError):
                youtube_url(bad)

    def test_only_live_player_not_replay_or_scheduled(self):
        player = {
            "videoDetails": {"videoId": "abcdefghijk"},
            "microformat": {
                "playerMicroformatRenderer": {
                    "liveBroadcastDetails": {"isLiveNow": True}
                }
            },
        }

        def page():
            return "var ytInitialPlayerResponse = " + json.dumps(player) + ";"

        self.assertEqual(live_video_from_page(page()), "abcdefghijk")
        details = player["microformat"]["playerMicroformatRenderer"][
            "liveBroadcastDetails"
        ]
        details["endTimestamp"] = "2026-10-18"
        self.assertIsNone(live_video_from_page(page()))
        details.clear()
        self.assertIsNone(live_video_from_page(page()))
        self.assertIsNone(live_video_from_page("<title>Channel</title>"))
        self.assertIsNone(live_video_from_page("ytInitialPlayerResponse = broken;"))

    async def test_metadata_source_nickname_and_spoken_lifecycle(self):
        event = self.event()
        await self.reader.ingest(event, "abcdefghijk")
        self.assertTrue(await self.reader._dispatch_once())
        sent = json.loads(self.reader._websocket.send.call_args.args[0])
        self.assertEqual(sent["source"], "youtube-live")
        self.assertIn("bình luận YouTube thật", sent["text"])
        self.assertIn("Bắp", sent["text"])
        key = CommentState.identity(
            "youtube:abcdefghijk",
            event["message_id"],
            event["timestamp"] / 1e6,
            "UCviewer",
            event["message"],
        )
        self.assertEqual(self.reader._comment_state.get_state(key), "queued")
        await self.reader.handle_incoming_messages(
            {
                "type": "user-input-transcription",
                "source": "youtube-live",
                "batch_id": sent["batch_id"],
            }
        )
        self.assertEqual(self.reader._comment_state.get_state(key), "answering")
        await self.reader.handle_incoming_messages(
            {"type": "audio", "audio": "fixture"}
        )
        self.assertFalse(
            await self.reader._dispatch_once(), "interrupted a spoken story"
        )
        await self.reader.handle_incoming_messages(
            {"type": "control", "text": "conversation-chain-end"}
        )
        self.assertEqual(self.reader._comment_state.get_state(key), "answered")
        resumed = self.new_reader()
        await resumed.ingest(event, "abcdefghijk")
        self.assertEqual(
            len(resumed._pending), 0, "replied to the same event after restart"
        )

    async def test_backlog_drops_oldest_and_groups_without_altering_viewer_text(self):
        self.reader._pending = __import__("collections").deque(maxlen=3)
        for i in range(10):
            event = self.event(str(i))
            event["message"] = f"Ý số {i}, mình từng xem TikTok."
            await self.reader.ingest(event, "abcdefghijk")
        self.assertEqual(len(self.reader._pending), 3)
        self.assertTrue(await self.reader._dispatch_once())
        text = json.loads(self.reader._websocket.send.call_args.args[0])["text"]
        self.assertIn("mình từng xem TikTok", text)
        self.assertIn("YouTube thật", text)
        self.assertEqual(json.loads(text.splitlines()[-1])["omitted_older"], 7)

    async def test_history_deleted_messages_and_unknown_timestamp_do_not_execute(self):
        for change in (
            {"timestamp": int((time.time() - 100) * 1e6)},
            {"timestamp": 0},
            {"timestamp": float("nan")},
            {"timestamp": int((time.time() + 100) * 1e6)},
            {"action_type": "remove_chat_item"},
            {"message_type": "membership_item"},
        ):
            event = self.event()
            event.update(change)
            await self.reader.ingest(event, "abcdefghijk")
        self.assertEqual(len(self.reader._pending), 0)
        self.assertEqual(len(self.reader._pending_joins), 0)

    async def test_youtube_receives_its_own_ack_and_host_does_not_answer_twice(self):
        proxy = ProxyHandler()
        proxy.broadcast_to_clients = AsyncMock()
        proxy.forward_to_server = AsyncMock()
        event = {
            "type": "user-input-transcription",
            "source": "youtube-live",
            "text": "fixture",
            "batch_id": "batch",
        }
        await proxy.forward_with_broadcast(event, "youtube-reader")
        proxy.broadcast_to_clients.assert_awaited_once_with(event, exclude_client=None)
        proxy.forward_to_server.assert_not_awaited()
        host = IdleHost(
            "ws://fixture",
            settings_path=self.root / "settings.json",
            activity_path=self.root / "activity.json",
        )
        host.followup_pending = True
        host.receive(event)
        self.assertFalse(host.followup_pending)
        text = self.reader._build_turn_text([("Bắp", "Hi Mao!")])
        compact = BasicMemoryAgent._compact_live_prompt(text)
        self.assertIn("YouTube cũ", compact)
        self.assertNotIn("Các bình luận bên dưới", compact)

    async def test_live_transport_ingests_received_messages(self):
        event = self.event()

        async def fixture(video_id, on_ready=None):
            if on_ready:
                on_ready()
            yield event

        with patch("src.open_llm_vtuber.live.youtube_live.iter_live_chat", fixture):
            await self.reader.stream_chat("abcdefghijk")
        self.assertEqual(len(self.reader._pending), 1)

    async def test_public_protocol_decodes_chat_and_never_requests_replay(self):
        from src.open_llm_vtuber.live.youtube_chat import iter_live_chat, decode_chat

        player = {
            "videoDetails": {"videoId": "abcdefghijk"},
            "microformat": {
                "playerMicroformatRenderer": {
                    "liveBroadcastDetails": {"isLiveNow": True}
                }
            },
        }
        data = {
            "contents": {
                "liveChatRenderer": {
                    "continuations": [
                        {"reloadContinuationData": {"continuation": "first"}}
                    ]
                }
            }
        }
        cfg = {
            "INNERTUBE_API_KEY": "public-web-key",
            "INNERTUBE_CONTEXT": {"client": {"clientName": "WEB"}},
        }

        def page():
            return (
                "var ytInitialPlayerResponse = "
                + json.dumps(player)
                + "; var ytInitialData = "
                + json.dumps(data)
                + "; ytcfg.set("
                + json.dumps(cfg)
                + ");"
            )

        body = {
            "continuationContents": {
                "liveChatContinuation": {
                    "actions": [
                        {
                            "addChatItemAction": {
                                "item": {
                                    "liveChatTextMessageRenderer": {
                                        "id": "event",
                                        "timestampUsec": "1792350000000000",
                                        "message": {"runs": [{"text": "Hi Mao!"}]},
                                        "authorName": {"simpleText": "Bắp"},
                                        "authorExternalChannelId": "UCviewer",
                                    }
                                }
                            }
                        },
                        {"removeChatItemAction": {"targetItemId": "removed"}},
                        {
                            "replayChatItemAction": {
                                "actions": [{"addChatItemAction": {"item": {}}}]
                            }
                        },
                    ]
                }
            }
        }
        messages, token, _ = decode_chat(body)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["author"]["name"], "Bắp")
        self.assertEqual(messages[0]["message"], "Hi Mao!")
        self.assertIsNone(token)
        client = SimpleNamespace(
            get=AsyncMock(return_value=Mock(text=page())),
            post=AsyncMock(return_value=Mock(status_code=200, json=lambda: body)),
        )
        with patch(
            "src.open_llm_vtuber.live.youtube_chat.httpx.AsyncClient"
        ) as factory:
            factory.return_value.__aenter__.return_value = client
            result = [m async for m in iter_live_chat("abcdefghijk")]
            self.assertEqual(result, messages)
            self.assertEqual(
                client.post.call_args.args[0],
                "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat",
            )
            player["microformat"]["playerMicroformatRenderer"]["liveBroadcastDetails"][
                "isLiveNow"
            ] = False
            client.get.return_value.text = page()
            client.post.reset_mock()
            result = [m async for m in iter_live_chat("abcdefghijk")]
            self.assertEqual(result, [])
            client.post.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
