import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI

from src.open_llm_vtuber.live.classroom import ClassroomGame, install_classroom_routes
from src.open_llm_vtuber.live.vua_tieng_viet import normalize_answer

WORDS = [
    {
        "answer": "áo dài",
        "category": "Trang phục",
        "hints": ["Có hai tà.", "Mặc với quần.", "Trang phục truyền thống."],
        "explanation": "Áo dài có hai tà, thường mặc trong dịp lễ.",
    },
    {
        "answer": "cái bàn",
        "category": "Đồ vật",
        "hints": ["Có mặt phẳng.", "Để sách vở.", "Thường đi cùng ghế."],
        "explanation": "Bàn giúp mình có chỗ học và làm việc.",
    },
]


class ClassroomTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "class.db"
        self.now = 0
        self.game = self.load()

    def load(self, words=WORDS):
        return ClassroomGame(
            words,
            database=self.path,
            clock=lambda: self.now,
            wall_clock=lambda: 1000 + self.now,
            rng=random.Random(7),
        )

    def start(self):
        self.game.enable()
        self.game.tick()

    def finish(self):
        self.now = self.game.deadline
        self.game.tick()

    def next_round(self):
        self.now = self.game.cooldown_deadline
        self.game.tick()
        self.assertEqual(self.game.phase, "waiting")
        self.game.tick()

    def test_round_scores_once_and_only_for_exact_answers(self):
        self.start()
        answer = self.game.word["answer"]
        self.now = 2
        self.game.submit(
            "Lan", normalize_answer(answer), player_id="tiktok:a", event_id="one"
        )
        self.now = 4
        self.assertEqual(
            self.game.submit("Lan", answer, player_id="tiktok:a", event_id="one"),
            "duplicate",
        )
        self.game.submit("Lan", answer, player_id="tiktok:a", event_id="two")
        self.game.submit(
            "Tên trùng", "đoán sai", player_id="tiktok:b", event_id="three"
        )
        self.now = 5
        self.game.submit("Tên trùng", answer, player_id="tiktok:c", event_id="four")
        public = self.game.snapshot()
        self.assertNotIn("answer", public)
        self.assertNotIn("explanation", public)
        self.assertEqual(public["classroom"]["standings"], [])
        self.finish()
        self.game.tick()
        rows = self.game.snapshot()["classroom"]["standings"]
        self.assertEqual([p["correct"] for p in rows], [1, 1])
        self.assertEqual(rows[0]["points"], 98)
        self.assertNotIn("tiktok:a", json.dumps(public))
        self.assertEqual(self.game.snapshot()["correct_count"], 2)

    def test_auto_round_waits_for_speech_and_presentation(self):
        self.start()
        first = self.game.word["answer"]
        self.finish()
        self.now += 25
        self.game.tick(ready=False)
        self.assertEqual(self.game.phase, "finished")
        self.assertTrue(self.game.active)
        self.game.tick(ready=True)
        self.assertEqual(self.game.phase, "waiting")
        self.game.tick(ready=False)
        self.assertEqual(self.game.phase, "waiting")
        self.game.tick(ready=True)
        self.assertNotEqual(self.game.word["answer"], first)

    def test_session_total_and_forty_seats_persist_across_restart(self):
        self.start()
        self.now = 3
        self.game.submit("Lan", self.game.word["answer"], player_id="a")
        self.finish()
        self.next_round()
        self.now += 2
        self.game.submit("Lan", self.game.word["answer"], player_id="a")
        self.finish()
        restored = self.load()
        state = restored.snapshot()["classroom"]
        self.assertTrue(state["enabled"])
        self.assertEqual(state["standings"][0]["correct"], 2)
        self.assertEqual(len(state["seats"]), 40)
        self.assertEqual(state["ends_at"], 0)
        self.assertTrue(state["unlimited"])
        original_seed = self.game.snapshot()["classroom"]["standings"][0]["avatar_seed"]
        self.assertEqual(state["standings"][0]["avatar_seed"], original_seed)
        self.assertEqual(len(original_seed), 32)
        self.assertNotIn("Lan", original_seed)

    def test_unlimited_session_and_toggle_restore_normal_rounds(self):
        self.start()
        old_round = self.game.round_id
        self.game.disable()
        self.assertFalse(self.game.active)
        self.assertFalse(self.game.announcement_valid(old_round, "start"))
        self.assertEqual(
            self.game.submit("Lan", "!vuatiengviet", player_id="a"), "started"
        )
        self.game.tick()
        self.assertEqual(self.game.phase, "playing")
        self.game.enable()
        self.now = 7 * 86400
        self.game.tick()
        self.assertTrue(self.game.enabled)
        self.assertTrue(self.load().enabled)
        self.game.disable()
        self.assertFalse(self.load().enabled)

    def test_bank_is_broad_unique_and_no_repeat_until_exhausted(self):
        game = self.load(None)
        self.assertGreaterEqual(len(game.words), 200)
        self.assertGreaterEqual(len({w["category"] for w in game.words}), 15)
        self.assertEqual(
            len({normalize_answer(w["answer"]) for w in game.words}), len(game.words)
        )
        game.enable()
        answers = [game.word["answer"]]
        for _ in range(len(game.eligible_indices) - 1):
            game._next_round()
            answers.append(game.word["answer"])
        self.assertEqual(len(set(answers)), len(game.eligible_indices))
        self.assertFalse(
            {normalize_answer(answer) for answer in answers} & game.excluded_answers
        )
        last_hundred = set(game.recent_answers)
        game._next_round()
        self.assertNotIn(normalize_answer(game.word["answer"]), last_hundred)

    def test_question_history_survives_new_sessions_and_account_switches(self):
        words = [
            dict(WORDS[0], answer=f"từ {i}", category=f"Chủ đề {i % 4}")
            for i in range(30)
        ]
        game = self.load(words)
        game.enable("@first")
        for _ in range(8):
            game._next_round()
        seen = set(game.used_answers)
        game.disable()
        restored = self.load(words)
        restored.enable("@first")
        self.assertTrue(seen < restored.used_answers)
        self.assertNotIn(normalize_answer(restored.word["answer"]), seen)
        restored.disable()
        restored.enable("@second")
        self.assertEqual(len(restored.used_answers), 1)
        restored.disable()
        restored.enable("@first")
        self.assertTrue(seen < restored.used_answers)
        self.assertEqual(restored.standings, {})

    def test_challenges_are_spaced_and_speech_does_not_number_questions(self):
        ordinary = [dict(WORDS[0], answer=f"thường {i}") for i in range(12)]
        hard = [dict(WORDS[1], answer=f"khó {i}", difficulty="hard") for i in range(3)]
        game = self.load(ordinary + hard)
        game.enable()
        selected = []
        for index in range(15):
            if index:
                game._next_round()
            selected.append(game.word["answer"])
            self.assertEqual(
                game.word.get("difficulty") == "hard", (index + 1) % 5 == 0
            )
            self.assertIn("Câu tiếp theo", game.start_speech())
            self.assertNotRegex(game.start_speech(), r"Câu \d+")
        self.assertEqual(len(set(selected)), 15)

    def test_guess_time_and_hint_timing_follow_question_difficulty(self):
        hard = dict(WORDS[1], difficulty="hard")
        for word, seconds in [(WORDS[0], 25), (hard, 40)]:
            with self.subTest(seconds=seconds), tempfile.TemporaryDirectory() as folder:
                now = [0.0]
                game = ClassroomGame(
                    [word], database=Path(folder) / "db", clock=lambda: now[0]
                )
                game.enable()
                game.tick()
                self.assertEqual(game.duration, seconds)
                self.assertEqual(game.deadline, seconds)
                count = 3 if word.get("difficulty") == "hard" else 2
                self.assertEqual(game.snapshot()["hint_count"], count)
                for index in range(1, count):
                    now[0] = seconds * index / count + 0.001
                    game.tick()
                    self.assertEqual(game.hint_index, index)
                now[0] = seconds - 0.001
                game.tick()
                self.assertEqual(game.hint_index, count - 1)
                self.assertEqual(len(game.snapshot()["hints"]), count)
                self.assertNotIn(
                    f"hint-{count}", [a["kind"] for a in game.announcements]
                )
                now[0] = seconds
                game.tick()
                self.assertEqual(game.phase, "finished")

    def test_board_and_voice_both_advance_hints(self):
        self.start()
        opening = self.game.start_speech()
        self.assertIn(self.game.word["hints"][0], opening)
        self.now = self.game.duration / 2 + 0.1
        self.game.tick()
        self.assertEqual(self.game.hint_index, 1)
        self.assertTrue(
            any(
                a["kind"] == "hint-1" and self.game.word["hints"][1] in a["text"]
                for a in self.game.announcements
            )
        )
        self.assertEqual(len(self.game.snapshot()["hints"]), 2)

    def test_chat_reacts_to_comments_and_congratulates_only_actual_fastest(self):
        self.start()
        self.now = 2
        self.game.submit("Lan", self.game.word["answer"], player_id="a")
        self.now = 3
        self.game.submit("Minh", self.game.word["answer"], player_id="b")
        self.finish()
        result = self.game._result_speech()
        self.assertIn("Lan", result)
        self.assertIn("Minh", result)
        self.assertIn("2 bạn đúng", result)
        self.assertIn(self.game.word["answer"], result)
        self.assertIn(self.game.word["explanation"], result)

    def test_expanded_bank_skips_legacy_and_resumes_without_clearing_scores(self):
        game = self.load(None)
        self.assertEqual(len(game.words), 2757)
        self.assertEqual(len(game.eligible_indices), 2500)
        self.assertEqual(len(game.excluded_answers), 257)
        game.enable()
        game.standings["player"] = {
            "nickname": "Lan",
            "correct": 7,
            "points": 650,
            "first_correct": 1,
            "order": 0,
            "avatar_seed": "opaque",
        }
        for _ in range(30):
            game._next_round()
        game._save()
        seen = set(game.used_answers)
        session_id = game.session_id
        restored = self.load(None)
        self.assertEqual(restored.session_id, session_id)
        self.assertEqual(restored.standings["player"]["correct"], 7)
        self.assertEqual(restored.standings["player"]["points"], 650)
        self.assertNotIn(normalize_answer(restored.word["answer"]), seen)
        self.assertTrue(seen <= restored.used_answers)
        self.assertNotIn(
            normalize_answer(restored.word["answer"]), restored.excluded_answers
        )

    def test_honor_bonuses_are_persistent_and_never_double_awarded(self):
        self.start()
        answer = self.game.word["answer"]
        for i, name in enumerate(("Lan", "Minh", "An", "Bình")):
            self.now = i + 1
            self.game.submit(name, answer, player_id=f"p{i}", event_id=f"e{i}")
        live = self.game.snapshot()["classroom"]
        self.assertEqual(len(live["seats"]), 40)
        self.assertTrue(
            all(
                p["status"] == "received" and "position" not in p
                for p in live["comments"]
            )
        )
        self.finish()
        state = self.game.snapshot()["classroom"]
        self.assertEqual(state["honor"], [])
        self.assertEqual([p["position"] for p in state["round_results"]], [1, 2, 3, 4])
        self.assertEqual(
            [p["elapsed_ms"] for p in state["round_results"]], [1000, 2000, 3000, 4000]
        )
        self.assertEqual([p["bonus"] for p in state["round_results"]], [0, 0, 0, 0])
        self.assertEqual([p["position"] for p in state["comments"]], [1, 2, 3, 4])
        totals = dict(self.game.standings["p0"])
        self.game._record_round()
        self.assertEqual(self.game.standings["p0"], totals)
        self.assertEqual(self.game.honor_board(), [])
        self.now += 86400
        self.game._settle_days()
        self.game._settle_days()
        self.assertEqual(self.game.honor_board()[0]["honor_points"], 10)
        self.game.disable()
        self.game.enable()
        self.assertEqual(self.game.standings, {})
        self.assertEqual(self.game.honor_board()[0]["honor_points"], 10)
        restored = self.load()
        self.assertEqual(restored.honor_board()[0]["honor_points"], 10)
        self.assertEqual(restored.honor_board()[0]["gold"], 1)

    def test_daily_top_aggregates_rounds_and_sessions_and_survives_restart(self):
        self.start()
        self.now += 1
        self.game.submit("Lan", self.game.word["answer"], player_id="a", event_id="a1")
        self.now += 2
        self.game.submit("Minh", self.game.word["answer"], player_id="b", event_id="b1")
        self.finish()
        self.game.disable()
        self.game.enable()
        self.game.tick()
        self.now += 1
        self.game.submit("Minh", self.game.word["answer"], player_id="b", event_id="b2")
        self.finish()
        self.assertEqual(self.game.honor_board(), [])
        self.game = self.load()
        self.assertEqual(self.game.honor_board(), [])
        self.now += 86400
        self.game.tick(ready=False)
        board = self.game.honor_board()
        self.assertEqual(
            [(p["nickname"], p["honor_points"]) for p in board],
            [("Minh", 10), ("Lan", 6)],
        )
        self.game = self.load()
        self.game.tick(ready=False)
        self.assertEqual(self.game.honor_board(), board)
        with self.game._db() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM classroom_daily_awards").fetchone()[0],
                1,
            )

    def test_local_midnight_and_award_failure_are_atomic(self):
        self.now = 17 * 3600 - 1000 - 10  # 23:59:50 in Vietnam
        self.start()
        self.now += 1
        self.game.submit("Lan", self.game.word["answer"], player_id="a", event_id="one")
        self.game._record_round()
        self.now = 17 * 3600 - 1000 - 1
        self.game._settle_days()
        self.assertEqual(self.game.honor_board(), [])
        self.now += 1
        with patch.object(
            self.game, "_award_honor", side_effect=RuntimeError("write failed")
        ):
            with self.assertRaises(RuntimeError):
                self.game._settle_days()
        self.assertEqual(self.game.honor_board(), [])
        self.game._settle_days()
        self.assertEqual(self.game.honor_board()[0]["honor_points"], 10)

    def test_only_first_correct_attempt_sets_podium_time(self):
        self.start()
        self.now = 1
        self.game.submit("Lan", "sai", player_id="a", event_id="a1")
        self.now = 2
        self.game.submit("Minh", self.game.word["answer"], player_id="b", event_id="b1")
        self.now = 3
        self.game.submit("Lan", self.game.word["answer"], player_id="a", event_id="a2")
        self.now = 5
        self.game.submit("Minh", self.game.word["answer"], player_id="b", event_id="b2")
        self.finish()
        state = self.game.snapshot()["classroom"]
        self.assertEqual(state["round_results"][0]["nickname"], "Minh")
        self.assertEqual(state["round_results"][0]["elapsed_ms"], 2000)
        comments = state["comments"]
        self.assertEqual(comments[0]["status"], "incorrect")
        self.assertEqual(comments[1]["position"], 1)
        self.assertNotIn("position", comments[-1])
        self.assertNotIn('"player_id"', json.dumps(state))
        with self.game._db() as db:
            self.assertEqual(
                db.execute("SELECT count(*) FROM classroom_round_awards").fetchone()[0],
                1,
            )

    def test_result_archive_and_lifetime_scores_are_scoped_to_tiktok_account(self):
        self.start()
        self.now = 1
        self.game.submit("Lan", self.game.word["answer"], player_id="a", event_id="one")
        self.assertEqual(self.game.recent_results(), [])
        self.finish()
        archive = self.game.recent_results()
        self.assertEqual(archive[0]["answer"], self.game.word["answer"])
        self.assertEqual(archive[0]["winners"][0]["nickname"], "Lan")
        self.assertEqual(archive[0]["winners"][0]["bonus"], 0)
        self.game.disable()
        self.game.enable("@another_account")
        self.assertEqual(self.game.honor_board(), [])
        self.assertEqual(self.game.recent_results(), [])

    def test_live_comment_marks_rejected_attempts_and_bounds_feed(self):
        self.start()
        self.now = 1
        self.game.submit("Lan", "sai", player_id="a", event_id="one")
        self.now = 1.1
        self.assertEqual(
            self.game.submit(
                "Lan", self.game.word["answer"], player_id="a", event_id="two"
            ),
            "rate-limited",
        )
        self.assertEqual(
            self.game.snapshot()["classroom"]["comments"][-1]["status"], "not_scored"
        )
        for i in range(100):
            self.game.submit("Lan", "chat", player_id="a", event_id=f"spam-{i}")
        self.assertEqual(len(self.game.public_comments()), 60)
        self.finish()
        self.assertEqual(self.game.honor_board(), [])
        self.assertEqual(self.game.snapshot()["classroom"]["round_results"], [])

    def test_equal_clock_times_use_first_correct_receipt_not_join_order(self):
        self.start()
        self.now = 1
        self.game.submit("Lan", "sai", player_id="a", event_id="first")
        self.now = 2
        self.game.submit(
            "Minh", self.game.word["answer"], player_id="b", event_id="second"
        )
        self.game.submit(
            "Lan", self.game.word["answer"], player_id="a", event_id="third"
        )
        self.assertEqual(self.game.ranking()[0]["nickname"], "Minh")
        self.finish()
        results = self.game.snapshot()["classroom"]["round_results"]
        self.assertEqual(results[0]["nickname"], "Minh")
        self.assertLess(results[0]["received_order"], results[1]["received_order"])

    def test_failed_round_commit_rolls_back_bonuses_and_can_retry(self):
        self.start()
        self.now = 1
        self.game.submit("Lan", self.game.word["answer"], player_id="a", event_id="one")
        with patch.object(self.game, "_save", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.finish()
        self.assertEqual(self.game.standings, {})
        self.assertEqual(self.game.honor_board(), [])
        self.assertEqual(self.game.recent_results(), [])
        self.game.tick()
        self.assertEqual(self.game.standings["a"]["correct"], 1)
        self.assertEqual(self.game.honor_board(), [])
        self.now += 86400
        self.game._settle_days()
        self.assertEqual(self.game.honor_board()[0]["honor_points"], 10)
        self.game.tick()
        self.assertEqual(self.game.honor_board()[0]["honor_points"], 10)

    def test_previous_session_podium_restore_is_idempotent_and_keeps_class_points(self):
        self.start()
        before = dict(self.game.standings)
        podium = [
            {"player_id": f"old-{i}", "nickname": name, "avatar_seed": f"seed-{i}"}
            for i, name in enumerate(("Lan", "Minh", "An"))
        ]
        self.assertTrue(
            self.game.restore_session_podium(
                "previous-live", podium, {"verified": True}
            )
        )
        self.assertEqual(
            [r["honor_points"] for r in self.game.honor_board()], [10, 6, 3]
        )
        self.assertFalse(
            self.game.restore_session_podium(
                "previous-live", podium, {"verified": True}
            )
        )
        self.assertEqual(
            [r["honor_points"] for r in self.game.honor_board()], [10, 6, 3]
        )
        self.assertEqual(self.game.standings, before)
        old_session = self.game.session_id
        self.game.disable()
        self.game.enable()
        with self.game._db() as db:
            archived = json.loads(
                db.execute(
                    "SELECT payload FROM classroom_sessions WHERE session_id=?",
                    (old_session,),
                ).fetchone()[0]
            )
        self.assertEqual(archived["session_id"], old_session)
        self.assertFalse(archived["enabled"])

    def test_bad_account_rejected(self):
        for value in ("", "not a handle", "@" + "a" * 25, "@name\n"):
            with self.assertRaises(ValueError):
                self.game.enable(account=value)

    def test_feedback_encourages_player_and_repeats_clue_without_answer(self):
        self.start()
        answer = self.game.word["answer"]
        self.now = 2
        self.game.submit("Lan", answer, player_id="a")
        self.now = self.game.duration / (2 * self.game.hint_count) + 0.1
        self.game.tick()
        feedback = [
            a["text"]
            for a in self.game.announcements
            if a["kind"].startswith("feedback-")
        ]
        self.assertEqual(len(feedback), 1)
        self.assertIn("Lan", feedback[0])
        self.assertIn(self.game.word["hints"][0], feedback[0])
        self.assertNotIn(answer, feedback[0])


class ClassroomRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_classroom_blocks_queued_chatter_but_allows_the_current_clue(self):
        from src.open_llm_vtuber.proxy_handler import ProxyHandler

        with tempfile.TemporaryDirectory() as directory:
            game = ClassroomGame(WORDS, database=Path(directory) / "db")
            game.enable()
            game.tick()
            proxy = ProxyHandler(word_game=Mock(game=game))
            proxy.forward_to_server = AsyncMock()
            for source in ("mao-idle-host", "youtube-live", "tiktok-live"):
                await proxy.forward_with_broadcast(
                    {
                        "type": "text-input",
                        "source": source,
                        "text": "Chuyện ngoài trò chơi",
                    }
                )
            proxy.forward_to_server.assert_not_called()
            await proxy.forward_with_broadcast(
                {
                    "type": "text-input",
                    "source": "vua-tieng-viet",
                    "game_round_id": game.round_id,
                    "game_kind": "start",
                    "text": game.start_speech(),
                }
            )
            proxy.forward_to_server.assert_awaited_once()

    async def test_tiktok_reader_only_routes_selected_class_and_stays_silent_when_off(
        self,
    ):
        from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform

        with (
            tempfile.TemporaryDirectory() as directory,
            patch("src.open_llm_vtuber.live.tiktok_live.TIKTOKLIVE_AVAILABLE", True),
        ):
            reader = TikTokLivePlatform(
                "@thanhoathirty6",
                classroom_only=True,
                comment_state_path=Path(directory) / "comments.db",
            )
            reader._accept_comment("Lan", "áo dài", author_id="a")
            self.assertFalse(reader._game_comments)
            await reader.handle_incoming_messages(
                {
                    "type": "vua-tieng-viet-state",
                    "phase": "finished",
                    "classroom": {"enabled": True, "account": "@thanhoathirty6"},
                }
            )
            self.assertTrue(reader._word_game_active)
            reader._accept_comment("Lan", "áo dài", author_id="a")
            self.assertEqual(reader._game_comments[0]["platform"], "tiktok-live")
            reader._accept_join("Lan", "a")
            self.assertFalse(reader._pending_joins)
            await reader.handle_incoming_messages(
                {
                    "type": "vua-tieng-viet-state",
                    "phase": "idle",
                    "classroom": {"enabled": False},
                }
            )
            reader._accept_comment("Mai", "bình luận thường", author_id="b")
            self.assertEqual(len(reader._game_comments), 1)

    async def test_other_rooms_and_desktop_cannot_score_in_tiktok_class(self):
        from src.open_llm_vtuber.proxy_handler import ProxyHandler

        with tempfile.TemporaryDirectory() as directory:
            game = ClassroomGame(WORDS, database=Path(directory) / "db")
            game.enable()
            service = Mock(game=game, submit=AsyncMock(return_value="accepted"))
            proxy = ProxyHandler(word_game=service)
            proxy.clients["reader"] = Mock(send_json=AsyncMock())
            event = {
                "type": "game-comment",
                "source": "@thanhoathirty6",
                "platform": "tiktok-live",
                "nickname": "Lan",
                "text": "áo dài",
                "author_id": "a",
                "event_id": "id",
            }
            await proxy.handle_game_message(
                {**event, "platform": "youtube-live"}, "reader"
            )
            await proxy.handle_game_message({**event, "source": "@other"}, "reader")
            await proxy.handle_game_message(
                {"type": "text-input", "text": "áo dài"}, "reader"
            )
            service.submit.assert_not_called()
            await proxy.handle_game_message(event, "reader")
            service.submit.assert_awaited_once()

    async def test_host_token_required_and_control_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            game = ClassroomGame(WORDS, database=Path(directory) / "db")
            service = Mock(game=game, proxy=None, publish=AsyncMock())
            app = FastAPI()
            with patch(
                "src.open_llm_vtuber.interaction.ingress.control_token",
                return_value="test-control",
            ):
                install_classroom_routes(app, service, "test")
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1000))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://127.0.0.1"
            ) as client:
                path = "/api/classroom/control"
                self.assertEqual(
                    (await client.post(path, json={"enabled": True})).status_code, 403
                )
                headers = {"X-Mao-Control": "test-control"}
                self.assertEqual(
                    (
                        await client.post(
                            path,
                            headers=headers,
                            json={"enabled": True, "account": "bad handle"},
                        )
                    ).status_code,
                    422,
                )
                enabled = await client.post(
                    path, headers=headers, json={"enabled": True}
                )
                self.assertEqual(enabled.status_code, 200)
                self.assertTrue(enabled.json()["classroom"]["enabled"])
                disabled = await client.post(
                    path, headers=headers, json={"enabled": False}
                )
                self.assertFalse(disabled.json()["classroom"]["enabled"])
            remote = httpx.ASGITransport(app=app, client=("192.0.2.1", 1000))
            async with httpx.AsyncClient(
                transport=remote, base_url="http://localhost"
            ) as client:
                self.assertEqual(
                    (
                        await client.post(path, headers=headers, json={"enabled": True})
                    ).status_code,
                    403,
                )


if __name__ == "__main__":
    unittest.main()
