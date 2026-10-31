import os
import time
import unittest
from unittest.mock import patch

from src.open_llm_vtuber.character.affect_scope import affect_key
from src.open_llm_vtuber.character.appraisal import appraise_text
from src.open_llm_vtuber.character.contextual_appraisal import appraise_conversation
from src.open_llm_vtuber.character.emotion import response_policy
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.store import Store
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
import test_runtime_architecture as architecture


def exchange(user="Mình đang buồn.", assistant="Mao nghe đây.", **overrides):
    return {
        "user_claim": user,
        "delivered_response": assistant,
        "delivery_status": "completed",
        "observed_at": 100,
        **overrides,
    }


class ContextualAppraisalTests(unittest.TestCase):
    def test_short_follow_up_uses_only_latest_confirmed_exchange(self):
        prior = exchange()
        self.assertEqual(appraise_text("Vẫn vậy.").kind, "conversation")
        self.assertEqual(
            appraise_conversation("Vẫn vậy.", [prior], now=110).kind, "support"
        )
        self.assertEqual(
            appraise_conversation(
                "Vẫn vậy.", [exchange("Chào Mao!"), prior], now=110
            ).kind,
            "conversation",
        )

    def test_no_carry_over_without_fresh_confirmed_history(self):
        for history in (
            [],
            [exchange(observed_at=0)],
            [exchange(observed_at=120)],
            [exchange(delivery_status="unknown")],
            [exchange(observed_at=float("nan"))],
            [exchange(observed_at="100")],
            [None],
        ):
            with self.subTest(history=history):
                self.assertEqual(
                    appraise_conversation("Vẫn vậy.", history, now=1000).kind,
                    "conversation",
                )

    def test_topic_change_recovery_and_current_requests_win(self):
        for text, kind in {
            "Mình ổn rồi, cứ đùa đi.": "conversation",
            "Đổi chủ đề, tính 2+3.": "conversation",
            "Mao hiểu sai rồi.": "correction",
            "Đừng đùa nhé.": "boundary",
            "Vui quá!": "celebration",
            "Định lý này là gì?": "question",
        }.items():
            with self.subTest(text=text):
                self.assertEqual(
                    appraise_conversation(text, [exchange()], now=110).kind, kind
                )

    def test_sarcasm_with_explicit_bad_outcome_does_not_trigger_celebration(self):
        for text in ("Tuyệt vời, mất hết dữ liệu rồi.", "Vui quá, lại sai hết rồi."):
            self.assertEqual(appraise_conversation(text).kind, "support")
        self.assertEqual(
            appraise_conversation("Tuyệt vời, đừng đùa nhé.").kind, "boundary"
        )

    def test_quotes_fiction_and_code_cannot_become_current_mood(self):
        for text in (
            "Dịch câu “tuyệt vời, mất hết dữ liệu”.",
            "Trong truyện nhân vật nói vui quá, lại sai hết.",
            "```Vẫn vậy```",
            "“Vẫn vậy”",
        ):
            self.assertNotIn(
                appraise_conversation(text, [exchange()], now=110).kind,
                {"support", "boundary", "celebration"},
            )

    def test_yes_no_can_resolve_single_option_question_but_not_multiple_choice(self):
        cases = (
            ("Có.", "Bạn muốn Mao chỉ lắng nghe thôi không?", "boundary"),
            ("Không.", "Bạn muốn Mao đùa một chút không?", "boundary"),
            ("Đúng.", "Bạn muốn Mao đùa một chút không?", "conversation"),
            ("Có.", "Bạn muốn Mao lắng nghe hay đưa giải pháp?", "conversation"),
            ("Không.", "Bạn không muốn Mao đùa phải không?", "conversation"),
            (
                "Có.",
                "Trong truyện nhân vật hỏi “Bạn muốn tôi chỉ lắng nghe không?”",
                "conversation",
            ),
        )
        for text, assistant, expected in cases:
            with self.subTest(text=text, assistant=assistant):
                self.assertEqual(
                    appraise_conversation(
                        text, [exchange("Chuyện dài lắm.", assistant)], now=110
                    ).kind,
                    expected,
                )

    def test_assistant_claim_is_not_a_user_self_report(self):
        prior = exchange("Chào Mao", "Bạn đang buồn, vẫn buồn lắm.")
        self.assertEqual(
            appraise_conversation("Vẫn vậy", [prior], now=110).kind, "conversation"
        )

    def test_key_separates_actor_room_visibility_and_rejects_partial_identity(self):
        keys = {
            affect_key(room=r, actor=a, visibility=v)
            for r in ("r1", "r2")
            for a in ("a", "b")
            for v in ("private", "public", "test")
        }
        self.assertEqual(len(keys), 12)
        self.assertNotIn("affect", keys)
        self.assertEqual(affect_key(), "affect")
        for kwargs in (
            {"room": "r"},
            {"room": "r", "actor": "a", "visibility": "operator"},
        ):
            with self.assertRaises(ValueError):
                affect_key(**kwargs)


class ContextualAffectRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_identity_history_and_event_id_reach_storage(self):
        from test_emotion_v2 import EmotionRuntimeTests

        store = EmotionRuntimeTests().store()
        store.observe_affect.side_effect = None
        store.observe_affect.return_value = {}
        config = HybridConfig(enabled=True)
        runtime = HybridRuntime(config, store=store)
        identity = {
            "event_id": "current",
            "room_id": "room",
            "actor_id": "a",
            "visibility": "private",
            "source_text": "Vẫn vậy.",
            "policy": {},
        }
        view = {
            "revision": 0,
            "items": [],
            "delivered_turns": [exchange(observed_at=time.time(), event_id="prior")],
        }
        with (
            patch(
                "src.open_llm_vtuber.experience.repository.Experiences.context",
                return_value=view,
            ),
            patch(
                "src.open_llm_vtuber.experience.activities.Activities.context",
                return_value=[],
            ),
            patch("src.open_llm_vtuber.dialogue.focus.Focus.current", return_value={}),
            patch(
                "src.open_llm_vtuber.dialogue.context.context_block", return_value=""
            ),
        ):
            await runtime.prepare(
                BatchInput(
                    [TextData(TextSource.INPUT, "ignored")],
                    metadata={"_interaction": identity},
                )
            )
        kwargs = store.observe_affect.call_args.kwargs
        self.assertEqual(kwargs["room"], "room")
        self.assertEqual(kwargs["actor"], "a")
        self.assertEqual(kwargs["visibility"], "private")
        self.assertEqual(kwargs["event_id"], "current")
        self.assertEqual(kwargs["context_event"], "prior")
        self.assertEqual(kwargs["appraisal"]["kind"], "support")


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class ScopedAffectDatabaseTests(unittest.TestCase):
    setUp = architecture.ArchitectureDatabaseTests.setUp
    tearDown = architecture.ArchitectureDatabaseTests.tearDown

    def event(self, *args, **kwargs):
        return architecture.ArchitectureDatabaseTests.event(self, *args, **kwargs)[0]

    def observe(self, event):
        return self.store.observe_affect(
            "audience_input",
            appraisal=appraise_text(event.content).model_dump(),
            event_id=str(event.event_id),
            room=event.room_id,
            actor=event.actor_id,
            visibility=event.visibility,
        )

    def test_private_mood_isolated_but_global_attention_is_shared(self):
        event = self.event("Mình buồn, đừng đùa.")
        self.observe(event)
        local = self.store.read_affect(
            room="room", actor="person-a", visibility="private"
        )
        self.assertEqual(response_policy(local)["strategy"], "support")
        for r, a, v in (
            ("room", "person-b", "private"),
            ("other", "person-a", "private"),
            ("room", "person-a", "public"),
        ):
            self.assertEqual(
                self.store.read_affect(room=r, actor=a, visibility=v)["revision"], 0
            )
        shared = self.store.read_affect()
        self.assertEqual(shared["channels"]["concern"], 0)
        self.assertEqual(shared["last_cue"], "conversation")
        self.assertFalse(response_policy(shared)["allow_background"])

    def test_replay_dedup_and_restart_preserve_only_same_identity(self):
        event = self.event("Mình vui quá!")
        first = self.observe(event)
        self.assertEqual(self.observe(event)["revision"], first["revision"])
        restarted = Store(self.config)
        try:
            self.assertEqual(
                restarted.read_affect(
                    room="room", actor="person-a", visibility="private"
                )["revision"],
                first["revision"],
            )
            self.assertEqual(
                restarted.read_affect(
                    room="room", actor="person-b", visibility="private"
                )["revision"],
                0,
            )
        finally:
            restarted.close()

    def test_forget_clears_derived_state_and_rejects_late_write(self):
        event = self.event("Mình buồn.")
        other = self.event("Vui quá!", actor="person-b")
        self.observe(event)
        self.observe(other)
        self.repo.forget_source(event.event_id)
        self.assertEqual(
            self.store.read_affect(room="room", actor="person-a", visibility="private")[
                "revision"
            ],
            0,
        )
        self.assertGreater(
            self.store.read_affect(room="room", actor="person-b", visibility="private")[
                "revision"
            ],
            0,
        )
        with self.assertRaises(ValueError):
            self.observe(event)

    def test_deleted_context_cannot_restore_a_forgotten_mood(self):
        previous = self.event("Mình buồn.")
        current = self.event("Vẫn vậy.")
        self.repo.forget_source(previous.event_id)
        with self.assertRaises(ValueError):
            self.store.observe_affect(
                "audience_input",
                appraisal=appraise_text("Mình buồn.").model_dump(),
                event_id=str(current.event_id),
                context_event=str(previous.event_id),
                room="room",
                actor="person-a",
                visibility="private",
            )

    def test_context_has_host_timestamp_and_excludes_other_actor_and_synthetic(self):
        event = self.event("Mình buồn.")
        self.event("Vui quá!", actor="person-b")
        synthetic = self.event("Đừng đùa.")
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET synthetic=true WHERE scope=%s AND id=%s",
                (self.store.scope, synthetic.event_id),
            )
        history = self.repo.context("room", "person-a", "private")["delivered_turns"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["event_id"], str(event.event_id))
        self.assertLess(abs(time.time() - history[0]["observed_at"]), 30)

    def test_sources_from_other_identity_or_rehearsal_cannot_update_state(self):
        other = self.event("Mình buồn.", actor="person-b")
        synthetic = self.event("Mình buồn.")
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET synthetic=true WHERE scope=%s AND id=%s",
                (self.store.scope, synthetic.event_id),
            )
        for source in (other, synthetic):
            with self.assertRaises(ValueError):
                self.store.observe_affect(
                    "audience_input",
                    appraisal=appraise_text("Mình buồn.").model_dump(),
                    event_id=str(source.event_id),
                    room="room",
                    actor="person-a",
                    visibility="private",
                )
        self.assertEqual(
            self.store.read_affect(room="room", actor="person-a", visibility="private")[
                "revision"
            ],
            0,
        )

    def test_new_conversation_does_not_inherit_legacy_global_mood(self):
        self.store.observe_affect(
            "audience_input", appraisal=appraise_text("Mình buồn.").model_dump()
        )
        self.assertGreater(self.store.read_affect()["channels"]["concern"], 0)
        self.assertEqual(
            self.store.read_affect(room="room", actor="person-a", visibility="private")[
                "channels"
            ]["concern"],
            0,
        )

    def test_scoped_reset_and_operator_reset_keep_unrelated_state(self):
        self.observe(self.event("Mình buồn."))
        self.observe(self.event("Vui quá!", actor="person-b"))
        self.store.put("unrelated", {"kept": True})
        self.store.clear_affect(room="room", actor="person-a", visibility="private")
        self.assertGreater(
            self.store.read_affect(room="room", actor="person-b", visibility="private")[
                "revision"
            ],
            0,
        )
        self.store.clear_affect()
        self.assertEqual(
            self.store.read_affect(room="room", actor="person-b", visibility="private")[
                "revision"
            ],
            0,
        )
        self.assertEqual(self.store.get("unrelated"), {"kept": True})
