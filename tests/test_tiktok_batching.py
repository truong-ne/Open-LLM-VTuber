import asyncio
import json
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import websockets

from starlette.websockets import WebSocketDisconnect
from TikTokLive.events import JoinEvent
from TikTokLive.events import CommentEvent

from src.open_llm_vtuber.live.idle_host import ChatActivity, IdleHost, read_json
from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform
from src.open_llm_vtuber.live.comment_state import CommentState
from src.open_llm_vtuber.proxy_handler import ProxyHandler
from src.open_llm_vtuber.proxy_message_queue import ProxyMessageQueue


class TikTokBatchingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.activity = Path(self.temp.name) / "activity.json"
        with patch("src.open_llm_vtuber.live.tiktok_live.ChatActivity") as tracker:
            tracker.return_value = ChatActivity(self.activity)
            self.client = TikTokLivePlatform(
                "test",
                max_pending_comments=20,
                comment_state_path=Path(self.temp.name) / "comments.db",
            )
        self.client._send_to_proxy = AsyncMock(return_value=True)
        self.client._connected = True
        self.client._state_known = True
        self.client._websocket = Mock(closed=False, send=AsyncMock())
        clock = patch("time.monotonic", return_value=1000)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        wall = patch("time.time", return_value=1000)
        self.wall = wall.start()
        self.addCleanup(wall.stop)

    async def batch(self, count=1):
        for i in range(count):
            self.client._accept_comment(f"viewer{i}", f"Câu hỏi {i}?")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())

    def test_reconnect_history_and_duplicate_event_ids_are_not_answered_again(self):
        self.client._listen_started_at = 1000

        def event(stamp, ident):
            return SimpleNamespace(
                common=SimpleNamespace(create_time=stamp, msg_id=ident)
            )

        self.assertFalse(self.client._is_new_event(event(900, 1)))
        self.assertTrue(self.client._is_new_event(event(998, 2)))
        self.assertTrue(self.client._is_new_event(event(1001, 4)))
        self.assertFalse(self.client._is_new_event(event(1001, 4)))
        self.assertTrue(self.client._is_new_event(SimpleNamespace(common=None)))

    def test_millisecond_history_timestamp_is_normalized(self):
        self.client._listen_started_at = 1_792_156_000
        event = SimpleNamespace(
            common=SimpleNamespace(create_time=1_792_155_583_000, msg_id=1)
        )
        self.assertFalse(self.client._is_new_event(event))

    async def own_start(self):
        await self.client.handle_incoming_messages(
            {
                "type": "user-input-transcription",
                "source": "tiktok-live",
                "batch_id": self.client._inflight_id,
            }
        )
        await self.client.handle_incoming_messages(
            {
                "type": "control",
                "text": "conversation-chain-start",
            }
        )

    async def end(self):
        await self.client.handle_incoming_messages(
            {
                "type": "control",
                "text": "conversation-chain-end",
            }
        )

    async def receive_comment(self, message_id=42, created_at=1001):
        self.client._listen_started_at = 1000
        if not hasattr(self, "comment_listener"):
            with patch(
                "src.open_llm_vtuber.live.tiktok_live.TikTokLiveClient"
            ) as factory:
                self.client._create_client()
            listeners = dict(
                call.args for call in factory.return_value.add_listener.call_args_list
            )
            self.comment_listener = listeners[CommentEvent]
        await self.comment_listener(
            SimpleNamespace(
                common=SimpleNamespace(msg_id=message_id, create_time=created_at),
                user=SimpleNamespace(nickname="Bông", id=123),
                content="Mao thích gì?",
            )
        )

    async def test_answered_event_stays_answered_after_timeout_cache_eviction_and_reopen(
        self,
    ):
        await self.receive_comment()
        ids = next(iter(self.client._pending_comment_ids.values()))
        event_key = next(iter(ids))
        self.assertEqual(self.client._comment_state.get_state(event_key), "queued")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        self.assertEqual(self.client._comment_state.get_state(event_key), "queued")
        await self.end()  # Unrelated turn ending cannot mark our batch answered.
        self.assertEqual(self.client._comment_state.get_state(event_key), "queued")
        await self.own_start()
        self.assertEqual(self.client._comment_state.get_state(event_key), "answering")
        await self.client.handle_incoming_messages({"type": "audio", "audio": "spoken"})
        self.assertEqual(self.client._comment_state.get_state(event_key), "answering")
        await self.end()
        self.assertEqual(self.client._comment_state.get_state(event_key), "answered")

        self.clock.return_value = 2000
        self.wall.return_value = 2000
        self.client._seen_event_ids.clear()  # e.g. many join events or a reconnect.
        await self.receive_comment()
        self.assertFalse(self.client._pending)
        self.assertEqual(read_json(self.activity)["last_comment_at"], 1000)
        reopened = CommentState(self.client._comment_state.path)
        self.assertEqual(reopened.get_state(event_key), "answered")
        self.assertFalse(reopened.reserve(event_key, 1001))

    async def test_timestamp_fallback_ignores_old_event_but_accepts_a_new_message(self):
        await self.receive_comment(message_id=0)
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        await self.client.handle_incoming_messages({"type": "audio", "audio": "spoken"})
        await self.end()
        self.clock.return_value = 1100
        await self.receive_comment(message_id=0, created_at=1001)
        self.assertFalse(self.client._pending)
        await self.receive_comment(message_id=0, created_at=1100)
        self.assertEqual(len(self.client._pending), 1)

    async def test_failed_send_keeps_comment_ids_queued_for_retry(self):
        self.client._accept_comment("Bông", "hi", event_key="first")

        async def fail(*_):
            self.client._accept_comment("Bông", "hi", event_key="same-question")
            self.client._accept_comment("Mây", "hello", event_key="new")
            return False

        self.client._send_to_proxy.side_effect = fail
        self.clock.return_value = 1002
        self.assertFalse(await self.client._dispatch_once())
        for key in ("first", "same-question", "new"):
            self.assertEqual(self.client._comment_state.get_state(key), "queued")
        self.client._send_to_proxy.side_effect = None
        self.clock.return_value = 1004
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        await self.client.handle_incoming_messages({"type": "audio", "audio": "spoken"})
        await self.end()
        for key in ("first", "same-question", "new"):
            self.assertEqual(self.client._comment_state.get_state(key), "answered")

    async def test_grouped_duplicates_share_reply_and_late_repeat_is_skipped(self):
        self.client._accept_comment("Bông", "hi", event_key="a")
        self.client._accept_comment("Bông", "hi!", event_key="b")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        self.client._accept_comment("Bông", "hi", event_key="c")
        self.assertEqual(self.client._comment_state.get_state("c"), "answering")
        await self.client.handle_incoming_messages({"type": "audio", "audio": "spoken"})
        await self.end()
        for key in ("a", "b", "c"):
            self.assertEqual(self.client._comment_state.get_state(key), "answered")
        self.client._accept_comment("Bông", "hi", event_key="d")
        self.assertEqual(self.client._comment_state.get_state("d"), "skipped")

    async def test_overflow_marks_dropped_comments_skipped_not_answered(self):
        for i in range(25):
            self.client._accept_comment(str(i), "hi", event_key=str(i))
        for i in range(5):
            self.assertEqual(self.client._comment_state.get_state(str(i)), "skipped")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        await self.client.handle_incoming_messages({"type": "audio", "audio": "spoken"})
        await self.end()
        self.assertEqual(self.client._comment_state.get_state("24"), "answered")
        self.assertEqual(self.client._comment_state.get_state("0"), "skipped")

    def test_identity_uses_channel_id_or_original_creation_time_and_not_receipt_time(
        self,
    ):
        identity = CommentState.identity
        self.assertEqual(
            identity("@test", 42, 1, "Bông", "hi"),
            identity("@test", "42", 9, "Tên mới", "text changed"),
        )
        self.assertNotEqual(
            identity("@test", 42, 1, "Bông", "hi"),
            identity("@other", 42, 1, "Bông", "hi"),
        )
        self.assertNotEqual(
            identity("@test", 0, 1, 123, "hi"), identity("@test", 0, 2, 123, "hi")
        )
        self.assertEqual(
            identity("@test", 0, 0, 123, "hi"), identity("@test", 0, 0, 123, "hi")
        )

    async def test_collects_burst_and_retains_all_bounded_groups_not_just_last_three(
        self,
    ):
        for i in range(12):
            self.client._accept_comment(f"viewer{i}", f"Câu hỏi {i}?")
        self.assertFalse(await self.client._dispatch_once())
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        text, batch_id = self.client._send_to_proxy.call_args.args
        data = json.loads(text.splitlines()[-1])
        self.assertEqual(len(data["comment_groups"]), 12)
        self.assertEqual(data["comment_groups"][0]["comment"], "Câu hỏi 0?")
        self.assertTrue(batch_id)
        self.assertEqual(read_json(self.activity)["pending_count"], 12)

    async def test_duplicate_comments_count_once_per_viewer_and_collapse_across_viewers(
        self,
    ):
        for _ in range(20):
            self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.client._accept_comment("Mây", "Mao thích mèo không!!!")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        payload = json.loads(
            self.client._send_to_proxy.call_args.args[0].splitlines()[-1]
        )
        self.assertEqual(len(payload["comment_groups"]), 1)
        self.assertEqual(payload["comment_groups"][0]["count"], 2)
        self.assertEqual(payload["comment_groups"][0]["nicknames"], ["Bông", "Mây"])
        self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.assertEqual(len(self.client._pending), 0)

    def test_only_two_names_in_digest_and_greetings_take_precedence(self):
        comments = [(f"viewer{i}", f"Câu hỏi {i}") for i in range(10)]
        comments += [("Bông", "hi"), ("Mây", "hello")]
        text = self.client._build_turn_text(comments)
        groups = json.loads(text.splitlines()[-1])["comment_groups"]
        names = [name for group in groups for name in group.get("nicknames", [])]
        self.assertEqual(names, ["Bông", "Mây"])

    async def test_long_story_is_never_released_by_timeout_or_by_audio_packets(self):
        await self.client.handle_incoming_messages(
            {"type": "conversation-state", "active": True}
        )
        self.client._accept_comment("Bông", "hi")
        self.clock.return_value = 1400
        self.assertFalse(await self.client._dispatch_once())
        self.client._send_to_proxy.assert_not_awaited()
        await self.client.handle_incoming_messages({"type": "audio", "audio": "packet"})
        self.assertFalse(await self.client._dispatch_once())
        await self.end()
        self.assertFalse(await self.client._dispatch_once())
        self.clock.return_value = 1401
        self.assertTrue(await self.client._dispatch_once())

    async def test_repeated_comment_stays_suppressed_through_a_long_reply_and_after_end(
        self,
    ):
        self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        self.clock.return_value = 1200
        self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.assertFalse(self.client._pending)
        await self.end()
        self.clock.return_value = 1259
        self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.assertFalse(self.client._pending)
        self.clock.return_value = 1260
        self.client._accept_comment("Bông", "Mao thích mèo không?")
        self.assertEqual(len(self.client._pending), 1)

    async def test_host_restarting_does_not_reply_again_to_old_chat(self):
        self.client._accept_comment("Bông", "hi")
        host = IdleHost(
            "ws://test",
            settings_path=Path(self.temp.name) / "settings.json",
            activity_path=self.activity,
        )
        self.assertEqual(host.last_comment_seen, 1000)

    async def test_other_turn_ending_does_not_allow_a_second_batch_before_our_reply(
        self,
    ):
        await self.batch()
        self.client._accept_comment("new viewer", "Mao kể tiếp đi")
        await self.end()  # A turn ahead of our queued batch completed.
        self.clock.return_value = 1500
        self.assertFalse(await self.client._dispatch_once())
        await self.own_start()
        await self.end()
        self.clock.return_value = 1501
        self.assertTrue(await self.client._dispatch_once())
        self.assertEqual(self.client._send_to_proxy.await_count, 2)

    async def test_comments_arriving_during_send_stay_in_next_batch(self):
        async def send(*_):
            self.client._accept_comment("late", "Bình luận mới")
            return True

        self.client._send_to_proxy.side_effect = send
        await self.batch()
        self.assertEqual(list(self.client._pending), [("late", "Bình luận mới")])

    async def test_failed_send_retries_the_same_comments_without_marking_answered(self):
        self.client._send_to_proxy.return_value = False
        self.client._accept_comment("Bông", "hi")
        self.clock.return_value = 1002
        self.assertFalse(await self.client._dispatch_once())
        self.assertEqual(list(self.client._pending), [("Bông", "hi")])
        self.assertFalse(self.client._waiting_for_reply)
        self.assertEqual(len(self.client._recent_answers), 0)
        self.client._send_to_proxy.return_value = True
        self.clock.return_value = 1004
        self.assertTrue(await self.client._dispatch_once())

    async def test_waits_for_connection_and_state_resync_before_sending(self):
        self.client._accept_comment("Bông", "hi")
        self.clock.return_value = 1002
        self.client._connected = False
        self.assertFalse(await self.client._dispatch_once())
        self.client._connected = True
        self.client._state_known = False
        self.assertFalse(await self.client._dispatch_once())
        self.client._send_to_proxy.assert_not_awaited()
        await self.client.handle_incoming_messages(
            {"type": "conversation-state", "active": False}
        )
        self.assertTrue(await self.client._dispatch_once())

    async def test_resync_recovers_if_playback_ended_while_reader_was_disconnected(
        self,
    ):
        await self.batch()
        await self.own_start()
        self.client._state_known = False
        await self.client.handle_incoming_messages(
            {"type": "conversation-state", "active": False}
        )
        self.assertFalse(self.client._waiting_for_reply)
        self.assertFalse(self.client._conversation_active)
        self.assertEqual(read_json(self.activity)["pending_count"], 0)

    async def test_overflow_is_bounded_and_reported_without_inventing_missing_comments(
        self,
    ):
        for i in range(100):
            self.client._accept_comment(str(i), "x" * 500 + str(i))
        self.assertEqual(len(self.client._pending), 20)
        self.assertTrue(all(len(text) <= 300 for _, text in self.client._pending))
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        payload = json.loads(
            self.client._send_to_proxy.call_args.args[0].splitlines()[-1]
        )
        self.assertEqual(payload["omitted_older"], 80)

    async def test_answered_tiktok_batch_does_not_trigger_another_idle_answer(self):
        host = IdleHost(
            "ws://test",
            settings_path=Path(self.temp.name) / "settings.json",
            activity_path=self.activity,
            rng=random.Random(3),
        )
        host.started_at = 900
        self.client._accept_comment("Bông", "Mao thích gì?")
        host.followup_pending = True
        host.receive(
            {
                "type": "user-input-transcription",
                "source": "tiktok-live",
                "text": "batch",
            }
        )
        self.assertFalse(host.followup_pending)
        self.assertEqual(host.last_comment_seen, 1000)
        host.receive({"type": "conversation-state", "active": True})
        self.assertTrue(host.busy)
        host.receive({"type": "control", "text": "conversation-chain-end"})
        self.clock.return_value = 1011
        self.wall.return_value = 1011
        self.client._pending.clear()
        self.client._report_activity()
        host.styles = ["chat"]
        _, label = await host.make_turn()
        self.assertTrue(label.startswith("idle:chat"))

    async def test_welcome_waits_for_story_playback_and_finishes_as_one_batch(self):
        self.client._conversation_active = True
        self.client._accept_join("Em Bắp Yêu", "123")
        self.clock.return_value = 1400
        self.assertFalse(await self.client._dispatch_once())
        self.client._send_to_proxy.assert_not_awaited()
        activity = read_json(self.activity)
        self.assertEqual(activity["pending_count"], 1)
        self.assertEqual(activity["last_comment_at"], 0)
        await self.end()
        self.assertFalse(await self.client._dispatch_once())
        self.clock.return_value = 1401
        self.assertTrue(await self.client._dispatch_once())
        text = self.client._send_to_proxy.call_args.args[0]
        self.assertEqual(
            json.loads(text.splitlines()[-1]), {"joined_viewers": ["Em Bắp Yêu"]}
        )
        self.assertIn("Chỉ nói câu chào và cảm ơn đó rồi dừng", text)
        await self.own_start()
        await self.end()
        self.assertEqual(read_json(self.activity)["pending_count"], 0)

    async def test_join_burst_is_bounded_and_attached_after_comment_answer(self):
        for i in range(100):
            self.client._accept_join(f"Khách {i}", str(i))
        self.assertEqual(len(self.client._pending_joins), 20)
        self.client._accept_comment("Bông", "hi")
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        text = self.client._send_to_proxy.call_args.args[0]
        payload = json.loads(text.splitlines()[-1])
        self.assertEqual(payload["joined_viewers"], ["Khách 98", "Khách 99"])
        self.assertEqual(payload["comment_groups"][0]["nicknames"], ["Bông"])
        self.assertIn("THÊM Ở CUỐI", text)
        self.assertFalse(self.client._pending_joins)

    async def test_welcome_cooldown_and_reentry_dedup_do_not_delay_comments(self):
        self.client._accept_join("Bông", "123")
        self.client._accept_join("Tên khác cùng người", "123")
        self.assertEqual(len(self.client._pending_joins), 1)
        self.assertFalse(await self.client._dispatch_once())
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        await self.own_start()
        await self.end()
        self.clock.return_value = 1005
        self.client._accept_join("Khách mới", "456")
        self.assertFalse(self.client._pending_joins)
        self.client._accept_comment("Mây", "Mao thích gì?")
        self.clock.return_value = 1007
        self.assertTrue(await self.client._dispatch_once())
        payload = json.loads(
            self.client._send_to_proxy.call_args.args[0].splitlines()[-1]
        )
        self.assertNotIn("joined_viewers", payload)
        self.clock.return_value = 1032
        self.client._accept_join("Bông", "123")
        self.assertFalse(self.client._pending_joins)
        self.client._accept_join("Khách mới", "456")
        self.assertEqual(len(self.client._pending_joins), 1)
        self.clock.return_value = 1600
        self.client._accept_join("Bông", "123")
        self.assertEqual(len(self.client._pending_joins), 2)

    async def test_failed_welcome_send_preserves_joins_and_new_comments(self):
        async def fail(*_):
            self.client._accept_comment("Mây", "hello")
            self.client._accept_join("Bông", "2")
            return False

        self.client._accept_join("Em Bắp Yêu", "1")
        self.client._send_to_proxy.side_effect = fail
        self.clock.return_value = 1002
        self.assertFalse(await self.client._dispatch_once())
        self.assertEqual(len(self.client._pending_joins), 2)
        self.assertEqual(len(self.client._pending), 1)
        self.assertEqual(read_json(self.activity)["pending_count"], 3)
        self.client._send_to_proxy.side_effect = None
        self.clock.return_value = 1004
        self.assertTrue(await self.client._dispatch_once())
        payload = json.loads(
            self.client._send_to_proxy.call_args.args[0].splitlines()[-1]
        )
        self.assertEqual(payload["joined_viewers"], ["Em Bắp Yêu", "Bông"])
        self.assertEqual(payload["comment_groups"][0]["comment"], "hello")

    async def test_joins_during_send_do_not_create_an_extra_welcome(self):
        async def send(*_):
            self.client._accept_join("Bông", "2")
            self.client._accept_comment("Mây", "hello")
            return True

        self.client._accept_join("Em Bắp Yêu", "1")
        self.client._send_to_proxy.side_effect = send
        self.clock.return_value = 1002
        self.assertTrue(await self.client._dispatch_once())
        self.assertFalse(self.client._pending_joins)
        self.assertEqual(list(self.client._pending), [("Mây", "hello")])

    async def test_join_listener_ignores_history_and_requires_a_real_name(self):
        self.client._listen_started_at = 1000
        with patch(
            "src.open_llm_vtuber.live.tiktok_live.TikTokLiveClient"
        ) as constructor:
            self.client._create_client()
        listeners = dict(
            call.args for call in constructor.return_value.add_listener.call_args_list
        )
        on_join = listeners[JoinEvent]
        event = SimpleNamespace(
            action=1,
            common=SimpleNamespace(create_time=900, msg_id=12),
            user=SimpleNamespace(nickname="Em Bắp Yêu", id=123),
        )
        await on_join(event)
        self.assertFalse(self.client._pending_joins)
        event.common.create_time = 1001
        event.action = 3  # Subscription is not a room arrival.
        await on_join(event)
        self.assertFalse(self.client._pending_joins)
        event.action = 1
        await on_join(event)
        await on_join(event)
        self.assertEqual(list(self.client._pending_joins), [("123", "Em Bắp Yêu")])
        await on_join(SimpleNamespace(action=1, common=None, user=None))
        self.assertEqual(len(self.client._pending_joins), 1)


class ProxyChatPriorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_burst_cannot_preempt_a_story_and_only_one_batch_starts_after_end(
        self,
    ):
        queue = ProxyMessageQueue()
        queue.conversation_active = True
        forwarded = []
        started = asyncio.Event()

        async def forward(message, sender_id):
            if message.get("type") == "text-input":
                forwarded.append(message["text"])
                started.set()

        queue.initialize(forward)
        queue.queue_message(
            {"type": "text-input", "source": "tiktok-live", "text": "summarized batch"}
        )
        await asyncio.sleep(0.15)
        self.assertEqual(forwarded, [])
        queue.conversation_active = False
        await asyncio.wait_for(started.wait(), 1)
        self.assertEqual(forwarded, ["summarized batch"])
        self.assertTrue(queue.conversation_active)
        queue.stop()
        await asyncio.gather(queue._consumer_task, return_exceptions=True)

    async def test_real_chat_replaces_queued_idle_story_but_never_active_speech(self):
        queue = ProxyMessageQueue()
        queue.conversation_active = True
        queue.queue_message(
            {"type": "text-input", "source": "mao-idle-host", "text": "stale story"}
        )
        queue.queue_message(
            {"type": "text-input", "source": "tiktok-live", "text": "new comments"}
        )
        queue.queue_message(
            {"type": "text-input", "source": "mao-idle-host", "text": "another story"}
        )
        self.assertTrue(queue.conversation_active)
        self.assertEqual(
            [item["message"]["text"] for item in queue.message_queue], ["new comments"]
        )

    async def test_batch_ack_is_visible_to_sender_without_forwarding_an_extra_backend_input(
        self,
    ):
        proxy = ProxyHandler()
        proxy.forward_to_server = AsyncMock()
        proxy.broadcast_to_clients = AsyncMock()
        message = {
            "type": "user-input-transcription",
            "source": "tiktok-live",
            "batch_id": "batch1",
        }
        await proxy.forward_with_broadcast(message, "reader")
        proxy.broadcast_to_clients.assert_awaited_once_with(
            message, exclude_client=None
        )
        proxy.forward_to_server.assert_not_awaited()

    async def test_connecting_mid_story_receives_current_busy_state(self):
        proxy = ProxyHandler()
        proxy.connected = True
        proxy.message_queue.conversation_active = True
        proxy.forward_to_server = AsyncMock()
        proxy.handle_client_disconnect = AsyncMock()
        ws = AsyncMock()
        ws.receive_json.side_effect = WebSocketDisconnect()
        await proxy.handle_client_connection(ws)
        self.assertEqual(
            ws.send_json.call_args_list[0].args[0],
            {"type": "conversation-state", "active": True},
        )

    async def test_reader_reconnect_does_not_reload_the_speaking_desktop(self):
        proxy = ProxyHandler()
        proxy.connected = True
        proxy.message_queue.conversation_active = True
        proxy._init_config = {"type": "set-model-and-conf", "conf_name": "Mao"}
        proxy.forward_to_server = AsyncMock()
        proxy.broadcast_to_clients = AsyncMock()
        proxy.handle_client_disconnect = AsyncMock()
        ws = AsyncMock()
        ws.receive_json.side_effect = WebSocketDisconnect()
        await proxy.handle_client_connection(ws)
        self.assertEqual(ws.send_json.call_args_list[1].args[0], proxy._init_config)
        proxy.forward_to_server.assert_not_awaited()
        proxy.broadcast_to_clients.assert_not_awaited()


class TikTokReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_large_audio_and_proxy_drop_preserve_pending_comments_and_reconnect(
        self,
    ):
        connections = 0
        ready = asyncio.Event()
        audio_lengths = []
        with tempfile.TemporaryDirectory() as directory:
            with patch("src.open_llm_vtuber.live.tiktok_live.ChatActivity") as tracker:
                tracker.return_value = ChatActivity(Path(directory) / "activity.json")
                client = TikTokLivePlatform(
                    "test", comment_state_path=Path(directory) / "comments.db"
                )

            async def server_handler(ws):
                nonlocal connections
                connections += 1
                await ws.send(
                    json.dumps(
                        {"type": "conversation-state", "active": connections == 1}
                    )
                )
                if connections == 1:
                    await ws.send(
                        json.dumps({"type": "audio", "audio": "x" * 1_200_000})
                    )
                    await ws.close(code=1012, reason="test proxy restart")
                else:
                    await ws.wait_closed()

            async def observe(data):
                await original_handle(data)
                if data.get("type") == "audio":
                    audio_lengths.append(len(data["audio"]))
                if data.get("type") == "conversation-state" and not data.get("active"):
                    ready.set()

            original_handle = client.handle_incoming_messages
            client.handle_incoming_messages = observe
            client._accept_comment("Bông", "hi")
            client._accept_comment("Mây", "Mao là ai?")
            client._running = True
            async with websockets.serve(server_handler, "127.0.0.1", 0) as server:
                url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
                client._proxy_url = url
                self.assertTrue(await client.connect(url))
                receiver = asyncio.create_task(client.start_receiving())
                try:
                    await asyncio.wait_for(ready.wait(), 5)
                    self.assertEqual(audio_lengths, [1_200_000])
                    self.assertEqual(connections, 2)
                    self.assertEqual(len(client._pending), 2)
                    self.assertTrue(client._state_known)
                    self.assertTrue(client.is_connected)
                    self.assertFalse(client._conversation_active)
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
                    await client.disconnect()

    async def test_worker_failure_cannot_leave_tiktok_running_and_silently_stuck(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("src.open_llm_vtuber.live.tiktok_live.ChatActivity") as tracker:
                tracker.return_value = ChatActivity(Path(directory) / "activity.json")
                client = TikTokLivePlatform(
                    "test", comment_state_path=Path(directory) / "comments.db"
                )
            client.connect = AsyncMock(return_value=True)
            client.disconnect = AsyncMock()
            client.start_receiving = AsyncMock(
                side_effect=RuntimeError("receiver failed")
            )

            async def wait_forever(**kwargs):
                await asyncio.Event().wait()

            client._dispatch_loop = wait_forever
            live = Mock(connect=AsyncMock(side_effect=wait_forever))
            client._create_client = Mock(return_value=live)
            await asyncio.wait_for(client.run(), 1)
            client.disconnect.assert_awaited_once()
            live.connect.assert_awaited_once_with(process_connect_events=False)


if __name__ == "__main__":
    unittest.main()
