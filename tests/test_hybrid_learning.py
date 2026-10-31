import os
import unittest
import uuid
from datetime import datetime, timedelta

from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.learning import DailyLearning, decide
from src.open_llm_vtuber.agent.hybrid.store import Store
from src.open_llm_vtuber.agent.proactive_reply import limit_proactive_reply


class DecisionTests(unittest.TestCase):
    def test_feedback_gate_conflict_and_bounds(self):
        self.assertEqual(decide(60, ["too_long"] * 2)[0], 60)
        self.assertEqual(decide(60, ["too_long"] * 3)[0], 55)
        self.assertEqual(decide(60, ["too_long"] * 3 + ["too_short"])[0], 60)
        self.assertEqual(decide(40, ["too_long"] * 10)[0], 40)
        self.assertEqual(decide(60, ["too_short"] * 10)[0], 60)
        self.assertEqual(decide(45, ["unsafe"])[0], 60)

    def test_replay_complete_sentences_tags_and_budget(self):
        text = "[joy] " + "xin " * 24 + "chào. " + "Mao " * 24 + "đây."
        self.assertNotIn("đây.", limit_proactive_reply(text, "chat", 60))
        shorter = limit_proactive_reply(text, "chat", 45)
        self.assertNotIn("đây.", shorter)
        self.assertTrue(shorter.endswith("chào."))
        self.assertIn("[joy]", shorter)
        self.assertEqual(limit_proactive_reply("Bạn khỏe không?", "chat", 45), "")


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES"), "PostgreSQL integration opt-in"
)
class PostgresLearningTests(unittest.TestCase):
    def setUp(self):
        self.scope = "learning-test-" + uuid.uuid4().hex
        self.config = HybridConfig(
            enabled=True, learning_enabled=True, scope=self.scope, learning_min_turns=3
        )
        self.store = Store(self.config)
        self.learning = DailyLearning(self.store)
        from scripts.mao_hybrid import load_admin_env

        load_admin_env()
        os.environ["MAO_LEARNING_TEST_ADMIN"] = os.environ["MAO_DATABASE_ADMIN_URL"]
        self.admin = Store(
            self.config.model_copy(
                update={"database_url_env": "MAO_LEARNING_TEST_ADMIN"}
            )
        )
        self.day = datetime.now(self.learning.zone).date() - timedelta(days=1)

    def tearDown(self):
        with self.admin.connect() as db:
            for name in (
                "learning_feedback",
                "learning_turns",
                "learning_profiles",
                "learning_days",
            ):
                db.execute(
                    f"DELETE FROM mao_hybrid.{name} WHERE scope=%s", (self.scope,)
                )
        self.store.close()
        self.admin.close()

    def fixtures(self, count=3, kind="proactive", label="too_long"):
        from datetime import time

        stamp = datetime.combine(self.day, time(12), self.learning.zone)
        identifiers = []
        for _ in range(count):
            identifier = self.learning.record(
                "SYNTHETIC_PRIVATE_CONTENT",
                {"audio_chunks": 1, "secret": "do not store"},
                kind,
            )
            identifiers.append(identifier)
            with self.admin.connect() as db:
                db.execute(
                    "UPDATE mao_hybrid.learning_turns SET created=%s WHERE scope=%s AND id=%s",
                    (stamp, self.scope, identifier),
                )
                db.execute(
                    "INSERT INTO mao_hybrid.learning_feedback(scope,turn_id,label,created) VALUES(%s,%s,%s,%s)",
                    (self.scope, identifier, label, stamp),
                )
        return identifiers

    def test_atomic_daily_preference_and_restart_idempotency(self):
        self.fixtures()
        report = self.learning.review(self.day)
        self.assertTrue(report["changed"])
        self.assertEqual(report["proactive_max_words"], 55)
        self.assertFalse(report["quality_improvement_verified"])
        self.assertEqual(self.learning.review(self.day), report)
        self.assertEqual(DailyLearning(self.store).profile()["proactive_max_words"], 55)
        with self.store.connect() as db:
            row = db.execute(
                "SELECT * FROM mao_hybrid.learning_turns WHERE scope=%s LIMIT 1",
                (self.scope,),
            ).fetchone()
        self.assertNotIn("SYNTHETIC_PRIVATE_CONTENT", str(row))
        self.assertNotIn("secret", row["metrics"])

    def test_no_learning_from_rehearsals_or_general_chat(self):
        self.fixtures(kind="rehearsal")
        self.assertEqual(self.learning.review(self.day)["turns"], 0)
        self.assertEqual(self.learning.profile()["proactive_max_words"], 60)

    def test_runtime_cannot_rate_and_cross_scope_fk(self):
        import psycopg

        identifier = self.learning.record("test", {})
        with (
            self.assertRaises(psycopg.errors.InsufficientPrivilege),
            self.store.connect() as db,
        ):
            db.execute(
                "INSERT INTO mao_hybrid.learning_feedback(scope,turn_id,label) VALUES(%s,%s,'useful')",
                (self.scope, identifier),
            )
        with (
            self.assertRaises(psycopg.errors.ForeignKeyViolation),
            self.admin.connect() as db,
        ):
            db.execute(
                "INSERT INTO mao_hybrid.learning_feedback(scope,turn_id,label) VALUES(%s,%s,'useful')",
                (self.scope + "-other", identifier),
            )

    def test_insufficient_turns_and_current_day_rejected(self):
        self.fixtures(count=2)
        self.assertFalse(self.learning.review(self.day)["changed"])
        with self.assertRaises(ValueError):
            self.learning.review(datetime.now(self.learning.zone).date())
