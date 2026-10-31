import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from src.open_llm_vtuber.live.idle_host import (
    ChatActivity,
    IdleHost,
    JokeSource,
    read_json,
    write_json,
)
from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform


class IdleHostTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.activity = root / "activity.json"
        self.settings = root / "settings.json"
        self.jokes = AsyncMock()
        self.jokes.get.return_value = {
            "setup": "Why dark mode?",
            "punchline": "Light attracts bugs.",
            "source": "https://official-joke-api.appspot.com/jokes/1",
        }
        # Constructor timestamps must use the same clock as the assertions.
        self.clock = patch("time.monotonic", return_value=1000)
        self.clock_mock = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.wall = patch("time.time", return_value=1000)
        self.wall.start()
        self.addCleanup(self.wall.stop)
        self.host = IdleHost(
            "ws://test",
            activity_path=self.activity,
            settings_path=self.settings,
            jokes=self.jokes,
            rng=random.Random(3),
        )
        self.host.started_at = 900

    def activity_at(self, last, pending=0, updated=1000):
        write_json(
            self.activity,
            {"last_comment_at": last, "pending_count": pending, "updated_at": updated},
        )

    def test_fresh_curiosity_suppresses_automatic_chatter_but_stale_status_does_not(
        self,
    ):
        self.activity_at(900)
        status = self.settings.with_name("mao-autonomy-status.json")
        write_json(status, {"phase": "reading", "updated_at": 1000})
        self.assertFalse(self.host.ready(1000))
        write_json(status, {"phase": "reading", "updated_at": 980})
        self.assertTrue(self.host.ready(1000))

    def test_ten_second_threshold_resets_on_new_comment(self):
        self.activity_at(990.01)
        self.assertFalse(self.host.ready(1000))
        self.activity_at(990)
        self.assertTrue(self.host.ready(1000))
        self.activity_at(999)
        self.assertFalse(self.host.ready(1000))

    def test_wait_for_queue_and_actual_playback_end(self):
        self.activity_at(980, pending=2)
        self.assertFalse(self.host.ready(1000))
        self.activity_at(980)
        self.host.receive({"type": "control", "text": "conversation-chain-start"})
        self.assertFalse(self.host.ready(1000))
        self.host.receive({"type": "control", "text": "conversation-chain-end"})
        self.assertFalse(self.host.ready(1009.9))
        self.assertTrue(self.host.ready(1010))

    def test_waits_on_initial_connect_and_in_progress_playback(self):
        self.host.started_at = 995
        self.assertFalse(self.host.ready(1000))
        self.host.started_at = 980
        self.assertTrue(self.host.ready(1000))
        self.host.receive({"type": "audio", "audio": "payload"})
        self.assertFalse(self.host.ready(1000))

    async def test_no_speech_before_threshold_and_only_one_turn_until_end(self):
        ws = AsyncMock()
        self.activity_at(999)
        self.assertFalse(await self.host.dispatch_once(ws))
        ws.send.assert_not_called()
        self.activity_at(980)
        self.assertTrue(await self.host.dispatch_once(ws))
        self.assertFalse(await self.host.dispatch_once(ws))
        ws.send.assert_awaited_once()
        self.assertEqual(self.host.sent, 1)

    async def test_declined_proposal_releases_host_and_preserves_cooldown(self):
        self.activity_at(900)
        await self.host.dispatch_once(AsyncMock())
        identifier = self.host._submitted_event_id
        self.host.receive(
            {"type": "input-status", "status": "accepted", "event_id": identifier}
        )
        self.assertTrue(self.host.busy)
        self.host.receive(
            {
                "type": "input-status",
                "status": "declined_policy",
                "event_id": "another-turn",
            }
        )
        self.assertTrue(self.host.busy)
        self.host.receive(
            {
                "type": "input-status",
                "status": "declined_policy",
                "event_id": identifier,
            }
        )
        self.assertFalse(self.host.busy)
        self.assertEqual(self.host.silent, 1)
        self.assertFalse(self.host.ready(1001))
        self.assertTrue(self.host.ready(1030))

    async def test_legacy_uncorrelated_decline_releases_only_an_unplayed_proposal(self):
        self.activity_at(900)
        await self.host.dispatch_once(AsyncMock())
        self.host.receive({"type": "input-status", "status": "declined_policy"})
        self.assertFalse(self.host.busy)
        self.clock_mock.return_value = 1030
        await self.host.dispatch_once(AsyncMock())
        self.host.receive({"type": "audio", "audio": "fixture"})
        self.host.receive({"type": "input-status", "status": "declined_policy"})
        self.assertTrue(self.host.busy)

    async def test_new_comment_during_joke_download_cancels_proactive_turn(self):
        self.host.styles = ["story"]

        async def download():
            self.activity_at(1000, pending=1)
            return {"setup": "question", "punchline": "answer", "source": "url"}

        self.jokes.get.side_effect = download
        ws = AsyncMock()
        self.assertFalse(await self.host.dispatch_once(ws))
        ws.send.assert_not_called()
        self.assertEqual(self.host.sent, 0)

    async def test_story_uses_real_source_as_data_and_vietnamese_instructions(self):
        self.host.styles = ["story"]
        text, label = await self.host.make_turn()
        self.assertIn("web_joke_data", text)
        self.assertIn("tiếng Việt", text)
        self.assertIn("source=", label)
        self.assertNotIn("Quan sát:", text)

    async def test_offline_fallback_does_not_claim_web_origin(self):
        self.host.styles = ["story"]
        self.jokes.get.return_value = None
        text, label = await self.host.make_turn()
        self.assertNotIn("web_joke_data", text)
        self.assertNotIn("source=", label)

    async def test_recent_audience_topic_takes_priority_over_random_story(self):
        self.activity_at(980)
        self.host.styles = ["story"]
        _, label = await self.host.make_turn()
        self.assertTrue(label.startswith("idle:followup"))
        self.jokes.get.assert_not_awaited()
        self.assertEqual(self.host.last_comment_seen, 980)

    async def test_topic_can_continue_across_three_brief_turns(self):
        await self.host.make_turn()
        first = self.host.current_topic
        await self.host.make_turn()
        self.assertEqual(self.host.current_topic, first)
        await self.host.make_turn()
        self.assertEqual(self.host.current_topic, first)
        await self.host.make_turn()
        self.assertNotEqual(self.host.current_topic, first)

    async def test_default_host_never_downloads_or_schedules_unsolicited_stories(self):
        labels = []
        for _ in range(24):
            text, label = await self.host.make_turn()
            self.assertNotIn("Quan sát:", text)
            labels.append(label)
        self.assertTrue(any(label.startswith("idle:activity") for label in labels))
        self.assertTrue(any(label.startswith("idle:question") for label in labels))
        self.assertGreater(sum(label.startswith("idle:chat") for label in labels), 6)
        self.assertTrue(any(label.startswith("idle:initiative") for label in labels))
        self.assertFalse(any(label.startswith("idle:story") for label in labels))
        self.jokes.get.assert_not_awaited()

    async def test_legacy_story_segments_require_explicit_opt_in(self):
        write_json(self.settings, {"proactive_stories": True})
        labels = [(await self.host.make_turn())[1] for _ in range(7)]
        self.assertTrue(any(label.startswith("idle:story") for label in labels))
        self.jokes.get.assert_awaited_once()

    async def test_question_listening_pause_starts_after_actual_playback_end(self):
        self.host.styles = ["question"]
        self.assertTrue(await self.host.dispatch_once(AsyncMock()))
        self.assertFalse(self.host.awaiting_reply)
        self.host.receive({"type": "audio", "audio": "payload"})
        self.assertTrue(self.host.awaiting_reply)
        # Generation/playback can take arbitrarily long. It is still busy.
        self.clock_mock.return_value = 1100
        self.assertFalse(self.host.ready(1100))
        self.host.receive({"type": "control", "text": "conversation-chain-end"})
        self.assertFalse(self.host.ready(1119.9))
        self.assertTrue(self.host.ready(1120))
        # Quiet chat is not an answer, even after the listening pause expires.
        self.assertTrue(self.host.awaiting_reply)

    async def test_new_audience_reply_releases_question_pause_without_double_answer(
        self,
    ):
        self.host.styles = ["question"]
        await self.host.dispatch_once(AsyncMock())
        self.host.receive({"type": "control", "text": "conversation-chain-end"})
        self.clock_mock.return_value = 1030
        self.host.receive(
            {
                "type": "user-input-transcription",
                "source": "youtube-live",
                "text": "Mình chọn màu xanh",
            }
        )
        self.assertFalse(self.host.awaiting_reply)
        self.assertFalse(self.host.followup_pending)
        self.assertFalse(self.host.ready(1039.9))
        self.assertTrue(self.host.ready(1040))

    async def test_unanswered_question_is_not_asked_again_or_answered_for_viewers(self):
        self.host.awaiting_reply = True
        self.host.receive(
            {
                "type": "user-input-transcription",
                "source": "mao-idle-host",
                "text": "own prompt",
            }
        )
        self.assertTrue(self.host.awaiting_reply)
        self.host.styles = ["question"]
        text, label = await self.host.make_turn()
        self.assertTrue(label.startswith("idle:chat"))
        self.assertIn("Không tự trả lời thay khán giả", text)

    async def test_failed_question_submission_does_not_start_listening_pause(self):
        self.host.styles = ["question"]
        ws = AsyncMock()
        ws.send.side_effect = ConnectionError("offline")
        with self.assertRaises(ConnectionError):
            await self.host.dispatch_once(ws)
        self.assertFalse(self.host.awaiting_reply)
        self.assertEqual(self.host.sent, 0)

    async def test_first_turn_opens_an_interaction_and_waits_for_a_real_reply(self):
        ws = AsyncMock()
        self.assertTrue(await self.host.dispatch_once(ws))
        self.assertTrue(self.host.last_topic.startswith("idle:initiative"))
        self.assertFalse(self.host.awaiting_reply)
        self.host.receive({"type": "audio", "audio": "payload"})
        self.assertTrue(self.host.awaiting_reply)
        self.assertEqual(self.host.last_invitation_at, 1000)
        text = json.loads(ws.send.call_args.args[0])["text"]
        self.assertIn("Nêu lựa chọn riêng trước", text)
        self.assertIn("không tự khởi động game", text)
        self.assertFalse(await self.host.dispatch_once(ws))

    async def test_unanswered_invitation_moves_on_without_getting_stuck(self):
        self.host.awaiting_reply = True
        self.host.current_topic = "trà sữa và cà phê"
        self.host.last_sent = self.host.last_invitation_at = 980
        self.host.last_end = 1000
        self.clock_mock.return_value = 1020
        self.assertTrue(self.host.ready(1020))
        self.host.styles = ["question"]
        text, label = await self.host.make_turn()
        self.assertFalse(self.host.awaiting_reply)
        self.assertNotEqual(self.host.current_topic, "trà sữa và cà phê")
        self.assertTrue(label.startswith("idle:chat"))
        self.assertIn("chuyển sang một ý hoặc chủ đề mới", text)
        self.assertIn("Không tự trả lời thay khán giả", text)
        # After the invitation cooldown, a genuinely new interaction is allowed.
        self.clock_mock.return_value = 1040
        self.host.styles = ["initiative"]
        self.assertTrue(await self.host.dispatch_once(AsyncMock()))
        self.host.receive({"type": "audio", "audio": "payload"})
        self.assertTrue(self.host.awaiting_reply)
        self.assertEqual(self.host.last_invitation_at, 1040)

    async def test_silent_turn_is_not_counted_as_speech_or_a_question(self):
        self.host.styles = ["question"]
        await self.host.dispatch_once(AsyncMock())
        self.host.receive({"type": "control", "text": "conversation-chain-end"})
        self.assertFalse(self.host.awaiting_reply)
        self.assertEqual(self.host.last_invitation_at, float("-inf"))
        self.assertEqual(self.host.spoken, 0)
        self.assertEqual(self.host.silent, 1)
        self.host.report()
        status = read_json(self.host.status_path)
        self.assertEqual(status["submitted_turns"], 1)
        self.assertEqual(status["proactive_turns"], 0)

    def test_listening_and_invitation_settings_validate_numbers(self):
        for value in (True, float("nan"), 1, "20"):
            write_json(
                self.settings,
                {"question_wait_seconds": value, "invitation_interval_seconds": value},
            )
            self.assertEqual(self.host.question_wait(), 20)
            self.assertEqual(self.host.invitation_interval(), 60)
        write_json(
            self.settings,
            {"question_wait_seconds": 30, "invitation_interval_seconds": 90},
        )
        self.assertEqual(self.host.question_wait(), 30)
        self.assertEqual(self.host.invitation_interval(), 90)

    async def test_followup_does_not_force_a_random_topic_or_consume_topic_budget(self):
        self.host.followup_pending = True
        with patch.object(self.host, "_topic") as pick:
            text, label = await self.host.make_turn()
        pick.assert_not_called()
        self.assertEqual(self.host.topic_turns, 0)
        self.assertTrue(label.startswith("idle:followup"))
        self.assertNotIn("Gợi ý dự phòng", text)
        self.assertIsNone(self.host._planned_content)

    async def test_repeated_monologues_wait_30_seconds_but_first_turn_waits_ten(self):
        self.host.started_at = 990
        self.assertTrue(self.host.ready(1000))
        self.assertTrue(await self.host.dispatch_once(AsyncMock()))
        self.host.receive({"type": "control", "text": "conversation-chain-end"})
        self.assertFalse(self.host.ready(1010))
        self.assertFalse(self.host.ready(1029.9))
        self.assertTrue(self.host.ready(1030))
        write_json(self.settings, {"min_interval_seconds": 60})
        self.assertFalse(self.host.ready(1045))
        self.assertTrue(self.host.ready(1060))

    def test_quieter_settings_wait_for_both_submission_and_actual_playback(self):
        write_json(
            self.settings,
            {
                "silence_seconds": 30,
                "min_interval_seconds": 75,
                "speech_pause_seconds": 20,
                "question_wait_seconds": 35,
                "invitation_interval_seconds": 180,
            },
        )
        self.activity_at(900)
        self.host.last_sent = 950
        self.host.last_end = 990
        self.assertFalse(self.host.ready(1024.9))
        self.assertTrue(self.host.ready(1025))
        self.host.last_end = 1020
        self.assertFalse(self.host.ready(1039.9))
        self.assertTrue(self.host.ready(1040))
        self.assertEqual(self.host.question_wait(), 35)
        self.assertEqual(self.host.invitation_interval(), 180)

    def test_settings_can_disable_without_restart(self):
        write_json(self.settings, {"enabled": False})
        self.assertFalse(self.host.ready(1000))
        write_json(self.settings, {"enabled": True, "silence_seconds": 10})
        self.assertTrue(self.host.ready(1000))

    async def test_support_reminder_has_ten_minute_cooldown_and_counts_successful_sends(
        self,
    ):
        self.host.last_support_at = 400.01
        self.assertFalse(self.host.support_due(1000))
        self.host.last_support_at = 400
        self.assertTrue(self.host.support_due(1000))
        ws = AsyncMock()
        self.assertTrue(await self.host.dispatch_once(ws))
        text = json.loads(ws.send.call_args.args[0])["text"]
        self.assertEqual(
            json.loads(text.splitlines()[-1])["live_context"]["style"], "support"
        )
        self.assertNotIn("donate để nâng cấp Mao", text)
        self.assertNotIn("Lượt này không tự chen", text)
        self.assertEqual(self.host.last_support_at, 1000)
        self.assertIsNone(self.host._planned_content)
        self.assertEqual(self.host.topic_turns, 0)
        self.assertFalse(self.host.support_due(1599.99))
        self.assertTrue(self.host.support_due(1600))

    async def test_failed_support_send_does_not_start_cooldown(self):
        self.host.last_support_at = 400
        ws = AsyncMock()
        ws.send.side_effect = ConnectionError("offline")
        with self.assertRaises(ConnectionError):
            await self.host.dispatch_once(ws)
        self.assertEqual(self.host.last_support_at, 400)
        self.assertTrue(self.host.support_due(1000))
        self.assertEqual(self.host.sent, 0)

    async def test_real_conversation_and_listening_pause_take_priority_over_support(
        self,
    ):
        self.host.last_support_at = 0
        self.host.followup_pending = True
        _, label = await self.host.make_turn()
        self.assertTrue(label.startswith("idle:followup"))
        self.host.awaiting_reply = True
        self.host.styles = ["chat"]
        text, label = await self.host.make_turn()
        self.assertTrue(label.startswith("idle:chat"))
        self.assertIn("Không tự trả lời thay khán giả", text)
        self.assertEqual(self.host.last_support_at, 0)

    async def test_support_does_not_interrupt_game_or_song(self):
        self.host.last_support_at = 0
        ws = AsyncMock()
        for flag in ("word_game_active", "singing_active"):
            setattr(self.host, flag, True)
            self.assertFalse(await self.host.dispatch_once(ws))
            setattr(self.host, flag, False)
        ws.send.assert_not_called()
        self.assertEqual(self.host.last_support_at, 0)

    def test_support_settings_disable_and_validate_interval(self):
        self.host.last_support_at = 0
        write_json(self.settings, {"support_reminders_enabled": False})
        self.assertFalse(self.host.support_due(1000))
        for value in (True, 1, float("nan"), "600"):
            write_json(self.settings, {"support_interval_seconds": value})
            self.assertFalse(self.host.support_due(599))
            self.assertTrue(self.host.support_due(600))
        write_json(self.settings, {"support_interval_seconds": 900})
        self.assertFalse(self.host.support_due(899))
        self.assertTrue(self.host.support_due(900))

    def test_shorter_speech_pause_preserves_chat_silence_and_start_interval(self):
        write_json(
            self.settings,
            {
                "silence_seconds": 10,
                "min_interval_seconds": 20,
                "speech_pause_seconds": 5,
            },
        )
        self.activity_at(980)
        self.host.last_sent = 980
        self.host.last_end = 995
        self.assertTrue(self.host.ready(1000))
        self.assertFalse(self.host.ready(999.9))
        self.host.last_sent = 990
        self.assertFalse(self.host.ready(1000))
        self.host.last_sent = 980
        self.activity_at(995)
        self.assertFalse(self.host.ready(1000))
        self.activity_at(980, pending=1)
        self.assertFalse(self.host.ready(1000))

    def test_desktop_voice_and_text_reset_silence_but_own_prompt_does_not(self):
        self.host.receive(
            {"type": "user-input-transcription", "text": "Mình vừa về nhà"}
        )
        self.assertFalse(self.host.ready(1009))
        self.assertTrue(self.host.ready(1010))
        self.assertTrue(self.host.followup_pending)
        self.host.followup_pending = False
        self.host.receive(
            {
                "type": "user-input-transcription",
                "text": "chủ động nói",
                "source": "mao-idle-host",
            }
        )
        self.assertFalse(self.host.followup_pending)

    async def test_desktop_conversation_is_followed_up_without_new_tiktok_comment(self):
        self.host.followup_pending = True
        self.host.styles = ["story"]
        _, label = await self.host.make_turn()
        self.assertTrue(label.startswith("idle:followup"))
        self.jokes.get.assert_not_awaited()
        self.assertFalse(self.host.followup_pending)

    async def test_activity_counts_all_nonempty_comments_and_tiktok_yields_to_host(
        self,
    ):
        with patch("src.open_llm_vtuber.live.tiktok_live.ChatActivity") as tracker:
            tracker.return_value = ChatActivity(self.activity)
            client = TikTokLivePlatform(
                "test",
                blocked_words=["blocked"],
                comment_state_path=Path(self.temp.name) / "comments.db",
            )
        client._accept_comment("someone", "hi")
        state = read_json(self.activity)
        self.assertEqual(state["pending_count"], 1)
        self.assertEqual(state["last_comment_at"], 1000)
        self.assertNotIn("someone", json.dumps(state))
        client._accept_comment("someone", "blocked")
        self.assertEqual(len(client._pending), 1)
        await client.handle_incoming_messages(
            {"type": "control", "text": "conversation-chain-start"}
        )
        self.assertTrue(client._conversation_active)
        await client.handle_incoming_messages(
            {"type": "control", "text": "conversation-chain-end"}
        )
        self.assertFalse(client._conversation_active)


class JokeSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_cache_deduplicate_and_record_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "jokes.json"
            source = JokeSource(path, random.Random(3))
            jokes = [
                {"id": i, "type": "general", "setup": "Question", "punchline": "Answer"}
                for i in (1, 2)
            ]
            response = httpx.Response(
                200, json=jokes, request=httpx.Request("GET", "https://test")
            )
            with patch(
                "httpx.AsyncClient.get", new=AsyncMock(return_value=response)
            ) as fetch:
                first, second = await source.get(), await source.get()
                fetch.assert_awaited_once()
            self.assertNotEqual(first["source"], second["source"])
            self.assertEqual(len(read_json(path)["recent"]), 2)
            self.assertEqual(len(JokeSource(path).recent), 2)

    async def test_http_failure_and_invalid_payload_fail_to_original_small_talk(self):
        with tempfile.TemporaryDirectory() as folder:
            source = JokeSource(Path(folder) / "jokes.json")
            with patch(
                "httpx.AsyncClient.get", side_effect=httpx.ConnectError("offline")
            ):
                self.assertIsNone(await source.get())
            response = httpx.Response(
                200,
                json={"invalid": "shape"},
                request=httpx.Request("GET", "https://test"),
            )
            with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
                self.assertIsNone(await source.get())
