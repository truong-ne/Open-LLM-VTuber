import random
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber.live.comment_state import CommentState
from src.open_llm_vtuber.live.diagnostics import install_live_diagnostics, live_snapshot
from src.open_llm_vtuber.live.food_choice import pick_food
from src.open_llm_vtuber.live.idle_host_storage import write_json
from src.open_llm_vtuber.live.viewer_memory import ViewerMemory, preference
from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform
from src.open_llm_vtuber.live.idle_host import ChatActivity


class LiveOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "comments.sqlite3"

    def test_audit_migration_preserves_dedup_data_and_tracks_confirmed_delivery(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE comments(event_key TEXT PRIMARY KEY,created_at REAL NOT NULL,received_at REAL NOT NULL,state TEXT NOT NULL,updated_at REAL NOT NULL)"
            )
            db.execute("INSERT INTO comments VALUES('old',1,1,'answered',1)")
        state = CommentState(self.path)
        self.assertEqual(state.get_state("old"), "answered")
        self.assertFalse(state.reserve("old"))
        state.audit("new", "@channel", "Mèo Gian Khổ", "123 + 123")
        self.assertTrue(state.reserve("new"))
        state.set_state(["new"], "queued", batch_id="batch")
        for stage in [
            "accepted",
            "answering",
            "audio_generated",
            "playing",
            "delivered",
        ]:
            state.stage(["new"], stage)
        row = state.snapshot()[0]
        self.assertEqual(row["state"], "delivered")
        self.assertEqual(row["batch_id"], "batch")
        self.assertEqual(
            [s["state"] for s in row["transitions"]],
            [
                "received",
                "queued",
                "accepted",
                "answering",
                "audio_generated",
                "playing",
                "delivered",
            ],
        )
        self.assertEqual(state.snapshot(account="@other"), [])

    def test_offline_is_separate_from_stale_socket_and_endpoint_is_local(self):
        write_json(
            self.root / "private/tiktok-reader-health.json",
            {"phase": "offline", "connected": False, "updated_at": 0},
        )
        self.assertEqual(live_snapshot(self.root, self.path)["connection"], "offline")
        write_json(
            self.root / "private/tiktok-reader-health.json",
            {"connected": True, "updated_at": 0},
        )
        self.assertEqual(live_snapshot(self.root, self.path)["connection"], "stale")
        app = FastAPI()
        install_live_diagnostics(app, root=self.root, state_path=self.path)
        client = TestClient(app)
        self.assertEqual(client.get("/api/live/diagnostics").status_code, 200)
        self.assertEqual(
            client.get(
                "/api/live/diagnostics", headers={"Origin": "https://foreign.example"}
            ).status_code,
            403,
        )

    def test_viewer_preferences_survive_restart_and_do_not_cross_identity(self):
        path = self.root / "memory.sqlite3"
        memory = ViewerMemory(path)
        memory.observe("@a", "stable-a", "Mình thích ăn phở", "source-1")
        self.assertEqual(memory.recall("@a", "stable-b"), [])
        self.assertEqual(memory.recall("@b", "stable-a"), [])
        item = ViewerMemory(path).recall("@a", "stable-a")[0]
        self.assertEqual(item["source_event"], "source-1")
        self.assertFalse(item["verified"])
        memory.observe("@a", "stable-a", "Mình không thích phở", "source-2")
        self.assertEqual(len(memory.recall("@a", "stable-a")), 1)
        self.assertIn("không thích", memory.recall("@a", "stable-a")[0]["content"])
        memory.observe("@a", "stable-a", "Quên sở thích của tôi", "forget")
        self.assertEqual(memory.recall("@a", "stable-a"), [])

    def test_temporary_quoted_jokes_and_third_party_claims_are_not_preferences(self):
        for text in [
            "Hôm nay mình thích phở",
            "Mình thích phở haha",
            "Bạn Lan thích phở",
            "Mình thích phở, mật khẩu là abc",
            '"Mình thích phở"',
            "Giả sử mình thích phở",
        ]:
            self.assertIsNone(preference(text), text)
        self.assertEqual(preference("Từ nay gọi mình là Bông")[0], "address")

    def test_explicit_story_continuation_is_scoped_and_can_be_finished(self):
        memory = ViewerMemory(self.root / "thread.sqlite3")
        memory.observe(
            "@a",
            "viewer",
            "Mình đang kể chuyện đi học, để lần sau kể tiếp",
            "thread-source",
        )
        self.assertEqual(len(memory.recall("@a", "viewer")), 1)
        self.assertEqual(memory.recall("@a", "other"), [])
        memory.observe("@a", "viewer", "Chuyện đó xong rồi", "finished")
        self.assertEqual(memory.recall("@a", "viewer"), [])

    def test_reply_groups_recall_only_their_stable_author_even_with_same_name(self):
        with patch(
            "src.open_llm_vtuber.live.tiktok_live.ChatActivity",
            return_value=ChatActivity(self.root / "activity.json"),
        ):
            client = TikTokLivePlatform("channel", comment_state_path=self.path)
        client._accept_comment(
            "Lan", "Mình thích ăn phở", event_key="pref", author_id="id-a"
        )
        client._accept_comment(
            "Lan", "Mao nhớ món mình thích không?", event_key="ask-a", author_id="id-a"
        )
        client._accept_comment(
            "Lan", "Mao gợi món cho mình?", event_key="ask-b", author_id="id-b"
        )
        text = client._build_turn_text(
            [("Lan", "Mao nhớ món mình thích không?"), ("Lan", "Mao gợi món cho mình?")]
        )
        import json

        groups = json.loads(text.splitlines()[-1])["comment_groups"]
        self.assertEqual(groups[0]["viewer_memories"][0]["source_event"], "pref")
        self.assertNotIn("viewer_memories", groups[1])

    def test_food_choice_uses_supplied_options_and_respects_constraints(self):
        rng = random.Random(7)
        picks = {pick_food("xôi hay phở?", rng) for _ in range(30)}
        self.assertEqual(picks, {"xôi", "phở"})
        self.assertIsNone(pick_food("Tôi dị ứng gà, gà rán hay phở?"))
        self.assertIsNone(pick_food("Đi ngủ hay đi làm?"))

    def test_old_audit_rows_are_pruned_without_removing_active_dedup_records(self):
        state = CommentState(self.path)
        with patch("time.time", return_value=1):
            state.audit("old", "@a", "A", "hello")
            state.reserve("old")
        reopened = CommentState(self.path)
        self.assertEqual(reopened.snapshot(), [])
        self.assertEqual(reopened.get_state("old"), "queued")


if __name__ == "__main__":
    unittest.main()
