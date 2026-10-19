import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.live.vua_tieng_viet import (
    VuaTiengViet,
    WordGameService,
    answer_score,
    WORD_PATH,
)
from src.open_llm_vtuber.live.buffered_chat import BufferedLiveChat
from src.open_llm_vtuber.live.idle_host import ChatActivity, IdleHost
from src.open_llm_vtuber.proxy_handler import ProxyHandler

WORDS = [
    {
        "answer": "áo dài",
        "category": "Văn hóa",
        "hints": ["Trang phục hai tà.", "Mặc cùng quần.", "Hai tiếng, năm chữ cái."],
        "explanation": "Áo dài là trang phục có hai tà trước sau, thường mặc cùng quần dài. Ví dụ, nhiều nữ sinh mặc áo dài trắng đến trường.",
    }
]


class Clock:
    value = 0.0

    def now(self):
        return self.value

    def wall(self):
        return 1000 + self.value


class WordGameTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.game = VuaTiengViet(
            WORDS,
            clock=self.clock.now,
            wall_clock=self.clock.wall,
            rng=random.Random(1),
        )

    def start(self):
        self.assertEqual(
            self.game.submit("Lan", "!vuatiengviet", player_id="a", event_id="cmd"),
            "started",
        )
        self.game.tick()

    def test_waits_for_mao_then_gives_exactly_sixty_seconds(self):
        self.game.submit("Lan", "!vuatiengviet", player_id="a")
        self.clock.value = 25
        self.game.submit("Lan", "áo dài", player_id="a")
        self.assertEqual(self.game.phase, "waiting")
        self.game.tick(ready=False)
        self.assertEqual(self.game.phase, "waiting")
        self.game.tick(ready=True)
        self.assertEqual(self.game.snapshot()["remaining"], 60)
        self.clock.value = 84.99
        self.game.tick()
        self.assertEqual(self.game.phase, "playing")
        self.clock.value = 85
        self.assertEqual(
            self.game.submit("Lan", "áo dài", player_id="a"), "not-playing"
        )
        self.assertEqual(self.game.snapshot()["cooldown_remaining"], 60)
        self.assertEqual(self.game.cooldown_deadline, 145)
        self.assertEqual(self.game.phase, "finished")

    def test_accents_case_punctuation_and_combining_marks(self):
        for guess in ("ÁO DÀI", "ao dai", "  áo  dài! ", "a\u0301o da\u0300i"):
            self.assertEqual(answer_score(guess, "áo dài"), 100)
        self.assertLess(answer_score("áo đỏ", "áo dài"), 100)
        self.assertLess(answer_score("Mình nghĩ là áo dài", "áo dài"), 100)
        self.assertEqual(answer_score("...", "áo dài"), 0)

    def test_hints_and_public_state_never_leak_answer_before_end(self):
        self.start()
        for now, index in ((0, 0), (19.99, 0), (20, 1), (39.99, 1), (40, 2)):
            self.clock.value = now
            self.game.tick()
            public = self.game.snapshot()
            self.assertEqual(public["hint_index"], index)
            self.assertEqual(len(public["hints"]), index + 1)
            self.assertNotIn("answer", public)
            self.assertNotIn("explanation", public)
            self.assertEqual(public["leaderboard"], [])
        self.assertEqual(self.game.snapshot()["slots"], [2, 3])
        self.clock.value = 60
        self.game.tick()
        self.assertEqual(self.game.snapshot()["answer"], "áo dài")

    def test_exact_beats_nearest_and_earliest_best_breaks_ties(self):
        self.start()
        self.clock.value = 2
        self.game.submit("Gần đúng", "áo đỏ", player_id="wrong")
        self.clock.value = 5
        self.game.submit("Lan", "ao dai", player_id="first")
        self.clock.value = 7
        self.game.submit("Mai", "áo dài", player_id="later")
        self.clock.value = 9
        self.game.submit("Lan", "áo dài", player_id="first")
        self.assertEqual(self.game.phase, "playing")
        self.clock.value = 60
        self.game.tick()
        board = self.game.snapshot()["leaderboard"]
        self.assertEqual([p["nickname"] for p in board], ["Lan", "Mai", "Gần đúng"])
        self.assertEqual(board[0]["seconds"], 5)
        self.assertEqual(board[0]["score"], 100)

    def test_repeated_command_dedup_and_stale_guesses(self):
        self.start()
        ident = self.game.round_id
        self.assertEqual(
            self.game.submit("Lan", "!vuatiengviet", player_id="a", event_id="cmd"),
            "duplicate",
        )
        self.assertEqual(
            self.game.submit("Mai", "!vuatiengviet", player_id="b"), "already-playing"
        )
        self.assertEqual(self.game.round_id, ident)
        self.assertEqual(
            self.game.submit("Mai", "ao dai", player_id="b", created_at=999), "stale"
        )
        self.assertFalse(self.game.players)
        self.game.submit("Mai", "ao dai", player_id="b", event_id="guess")
        self.clock.value = 3
        self.assertEqual(
            self.game.submit("Mai", "ao dai", player_id="b", event_id="guess"),
            "duplicate",
        )

    def test_spam_is_bounded_and_feedback_does_not_decide_scores(self):
        self.start()
        for i in range(13):
            self.clock.value = i + 1
            status = self.game.submit("Lan", "áo đỏ", player_id="a")
        self.assertEqual(status, "rate-limited")
        self.assertEqual(self.game.players["a"]["attempts"], 12)
        self.game.tick()
        feedback = [
            a for a in self.game.announcements if a["kind"].startswith("feedback")
        ]
        self.assertEqual(len(feedback), 1)
        self.assertIn("Lan", feedback[0]["text"])
        self.assertLess(self.game.players["a"]["score"], 100)

    def test_expired_clues_are_not_spoken_and_result_says_nearest(self):
        self.start()
        self.assertTrue(self.game.announcement_valid(self.game.round_id, "start"))
        self.clock.value = 40
        self.game.tick()
        self.assertFalse(self.game.announcement_valid(self.game.round_id, "start"))
        self.game.submit("Lan", "áo đỏ", player_id="a")
        self.clock.value = 60
        self.game.tick()
        self.assertIn("Chưa ai đúng hoàn toàn", self.game.announcements[-1]["text"])
        self.assertTrue(self.game.announcement_valid(self.game.round_id, "result"))
        self.assertFalse(self.game.announcement_valid("old-round", "result"))

    def test_feedback_reads_different_comments_without_repeating(self):
        self.start()
        self.game.submit("Lan", "ao dai", player_id="a")
        self.clock.value = 2
        self.game.submit("Mai", "ao do", player_id="b")
        for moment in (10, 30, 50):
            self.clock.value = moment
            self.game.tick()
        feedback = [
            a for a in self.game.announcements if a["kind"].startswith("feedback")
        ]
        self.assertEqual(len(feedback), 2)
        self.assertIn("Lan", feedback[0]["text"])
        self.assertIn("Mai", feedback[1]["text"])

    def test_word_bank_is_valid_and_rounds_do_not_immediately_repeat(self):
        words = json.loads(WORD_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(words), 30)
        self.assertEqual(len(words), len({w["answer"] for w in words}))
        game = VuaTiengViet(words, clock=self.clock.now, wall_clock=self.clock.wall)
        answers = []
        for _ in range(3):
            game.submit("Lan", "!vuatiengviet", player_id="a")
            game.tick()
            answers.append(game.word["answer"])
            self.clock.value += 60
            game.tick()
            self.clock.value += game.cooldown_seconds
        self.assertEqual(len(set(answers)), 3)

    def test_result_explains_the_word_for_correct_wrong_and_empty_rounds(self):
        for guess in ("ao dai", "áo đỏ", None):
            with self.subTest(guess=guess):
                self.setUp()
                self.start()
                if guess is not None:
                    self.clock.value = 3
                    self.game.submit("Lan", guess, player_id="a")
                self.clock.value = 60
                self.game.tick()
                text = self.game.announcements[-1]["text"]
                self.assertIn("Đáp án là áo dài.", text)
                self.assertIn(WORDS[0]["explanation"].split(". ")[0] + ".", text)
                self.assertNotIn("Ví dụ", text)
                self.assertTrue(text.startswith("Hết giờ! Đáp án là áo dài."))
                if guess == "ao dai":
                    self.assertIn("Lan", text)
                    self.assertIn("một trăm điểm", text)
                    self.assertNotIn("tiếc", text.casefold())
                else:
                    self.assertIn("tiếc", text.casefold())
                    self.assertNotIn("một trăm điểm", text)
                    if guess is not None:
                        self.assertIn("Lan gần nhất", text)
                    else:
                        self.assertNotIn("gần nhất", text)

    def test_result_variants_do_not_repeat_or_announce_twice(self):
        texts = []
        for _ in range(5):
            self.game.submit("Lan", "!vuatiengviet", player_id="a")
            self.game.tick()
            self.clock.value += 60
            self.game.tick()
            text = self.game.announcements[-1]["text"]
            self.assertEqual(text.count(WORDS[0]["explanation"].split(". ")[0]), 1)
            texts.append(text)
            count = len(self.game.announcements)
            self.game.tick()
            self.assertEqual(len(self.game.announcements), count)
            self.clock.value += self.game.cooldown_seconds
        for previous, current in zip(texts, texts[1:]):
            self.assertNotEqual(previous, current)

    def test_word_bank_requires_a_short_nonempty_explanation(self):
        for explanation in (None, "", "   ", "x" * 301):
            with self.subTest(explanation=explanation), self.assertRaises(ValueError):
                VuaTiengViet([{**WORDS[0], "explanation": explanation}])

    def test_result_speaks_viewer_names_without_expression_tags(self):
        self.start()
        self.game.submit("[anger]Lan<test>", "ao dai", player_id="a")
        self.clock.value = 60
        self.game.tick()
        text = self.game.announcements[-1]["text"]
        self.assertNotIn("[anger]", text)
        self.assertNotIn("<test>", text)
        self.assertIn("Lan", text)

    def test_global_cooldown_cannot_be_bypassed_or_extended_by_spam(self):
        self.start()
        self.clock.value = 60
        self.game.tick()
        result = self.game.snapshot()
        self.assertEqual(result["cooldown_remaining"], 60)
        self.assertEqual(result["cooldown_ends_at"], 1120)
        round_id, revision = self.game.round_id, self.game.revision
        announcements = list(self.game.announcements)
        for moment in (60, 65, 90, 119.999):
            self.clock.value = moment
            for i in range(20):
                self.assertEqual(
                    self.game.submit(
                        f"User {i}",
                        "!vuatiengviet",
                        player_id=f"reconnected-{i}",
                        event_id=f"spam-{moment}-{i}",
                    ),
                    "cooldown",
                )
            self.assertEqual(self.game.round_id, round_id)
            self.assertEqual(self.game.revision, revision)
            self.assertEqual(self.game.snapshot()["cooldown_ends_at"], 1120)
            self.assertEqual(list(self.game.announcements), announcements)
        self.clock.value = 120
        self.assertEqual(self.game.snapshot()["cooldown_remaining"], 0)
        self.assertEqual(
            self.game.submit(
                "New viewer", "!vuatiengviet", player_id="new", created_at=1120
            ),
            "started",
        )
        self.assertNotEqual(self.game.round_id, round_id)
        self.assertEqual(self.game.snapshot()["cooldown_remaining"], 0)

    def test_command_created_during_break_cannot_start_round_when_replayed_later(self):
        self.start()
        self.clock.value = 60
        self.game.tick()
        self.clock.value = 121
        self.assertEqual(
            self.game.submit("Lan", "!vuatiengviet", player_id="a", created_at=1085),
            "stale",
        )
        self.assertEqual(self.game.phase, "finished")
        self.assertEqual(
            self.game.submit("Lan", "!vuatiengviet", player_id="a", created_at=1121),
            "started",
        )

    def test_cooldown_uses_monotonic_time_even_if_wall_clock_changes(self):
        self.start()
        self.clock.value = 60
        self.game.tick()
        self.game.wall_clock = lambda: 5000
        self.clock.value = 70
        self.assertEqual(self.game.snapshot()["cooldown_remaining"], 50)
        self.assertEqual(self.game.snapshot()["cooldown_ends_at"], 5050)
        self.assertEqual(
            self.game.submit("Mai", "!vuatiengviet", player_id="another"), "cooldown"
        )


class WordGameIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cooldown_command_restores_reader_state_even_without_revision_change(
        self,
    ):
        clock = Clock()
        game = VuaTiengViet(WORDS, clock=clock.now, wall_clock=clock.wall)
        game.submit("Lan", "!vuatiengviet", player_id="a")
        game.tick()
        clock.value = 60
        game.tick()
        service = WordGameService(game)
        service._last_revision = game.revision
        proxy = ProxyHandler(word_game=service)
        client = Mock(send_json=AsyncMock())
        proxy.clients["reader"] = client
        await proxy.handle_game_message(
            {
                "type": "game-comment",
                "text": "!vuatiengviet",
                "event_id": "new-command",
            },
            "reader",
        )
        events = [c.args[0] for c in client.send_json.call_args_list]
        self.assertEqual(events[0]["status"], "cooldown")
        self.assertEqual(events[1]["phase"], "finished")
        self.assertEqual(events[1]["cooldown_remaining"], 60)
        self.assertFalse(proxy.message_queue.has_pending_messages())

    async def test_expired_announcement_releases_the_speech_queue(self):
        service = WordGameService(VuaTiengViet(WORDS))
        proxy = ProxyHandler(word_game=service)
        proxy.broadcast_to_clients = AsyncMock()
        proxy.forward_to_server = AsyncMock()
        proxy.message_queue.conversation_active = True
        await proxy.forward_with_broadcast(
            {
                "type": "text-input",
                "source": "vua-tieng-viet",
                "game_round_id": "expired",
                "game_kind": "start",
            }
        )
        self.assertFalse(proxy.message_queue.conversation_active)
        proxy.forward_to_server.assert_not_called()

    async def test_game_speech_bypasses_llm_and_waits_for_tts_playback(self):
        from src.open_llm_vtuber.conversations.single_conversation import (
            process_single_conversation,
        )

        context = Mock()
        context.character_config.character_name = "Mao"
        context.character_config.avatar = "mao.png"
        send = AsyncMock()
        manager = Mock(speak=AsyncMock(), wait_for_completion=AsyncMock())
        module = "src.open_llm_vtuber.conversations.single_conversation"
        with (
            patch(module + ".TTSTaskManager", return_value=manager),
            patch(
                module + ".finalize_conversation_turn", new_callable=AsyncMock
            ) as finalize,
            patch(module + ".cleanup_conversation"),
        ):
            result = await process_single_conversation(
                context,
                send,
                "test",
                "input",
                metadata={"game_speech": "Gợi ý 1: Trang phục hai tà."},
            )
        context.agent_engine.chat.assert_not_called()
        manager.speak.assert_awaited_once()
        finalize.assert_awaited_once_with(manager, send, "test")
        self.assertEqual(result, "Gợi ý 1: Trang phục hai tà.")

    async def test_reader_forwards_every_guess_while_mao_is_speaking(self):
        with tempfile.TemporaryDirectory() as folder:

            class Reader(BufferedLiveChat):
                async def run(self):
                    pass

            reader = Reader(
                "youtube:test",
                comment_state_path=Path(folder) / "state.db",
                activity=ChatActivity(Path(folder) / "activity.json"),
            )
            reader._connected = reader._state_known = reader._conversation_active = True
            reader._websocket = Mock(closed=False, send=AsyncMock())
            reader._accept_comment(
                "Lan", "!vuatiengviet", event_key="cmd", author_id="UC1"
            )
            reader._accept_comment("Lan", "áo dài", event_key="guess", author_id="UC1")
            await reader._dispatch_once()
            messages = [
                json.loads(call.args[0])
                for call in reader._websocket.send.call_args_list
            ]
            self.assertEqual(
                [m["type"] for m in messages], ["game-comment", "game-comment"]
            )
            self.assertEqual(messages[-1]["author_id"], "UC1")
            self.assertFalse(reader._pending)
            await reader.handle_incoming_messages(
                {"type": "game-comment-ack", "event_id": "guess", "status": "accepted"}
            )
            self.assertNotIn("guess", reader._game_unacked)

    async def test_proxy_command_is_consumed_and_idle_host_pauses(self):
        service = WordGameService(VuaTiengViet(WORDS))
        proxy = ProxyHandler(word_game=service)
        proxy.clients["desktop"] = Mock(send_json=AsyncMock())
        self.assertTrue(
            await proxy.handle_game_message(
                {"type": "text-input", "text": "!vuatiengviet"}, "desktop"
            )
        )
        self.assertEqual(service.game.phase, "waiting")
        self.assertFalse(proxy.message_queue.has_pending_messages())
        with tempfile.TemporaryDirectory() as folder:
            host = IdleHost(
                "ws://test",
                settings_path=Path(folder) / "host.json",
                activity_path=Path(folder) / "activity.json",
            )
            host.receive(service.game.snapshot())
            self.assertFalse(await host.dispatch_once(Mock()))
