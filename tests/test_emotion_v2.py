from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import time
import unittest
from unittest.mock import AsyncMock, Mock
import uuid

from pydantic import ValidationError

from src.open_llm_vtuber.character.appraisal import (
    Appraisal,
    appraise_text,
    outcome_appraisal,
)
from src.open_llm_vtuber.character.emotion import (
    BASE,
    CHANNELS,
    normalize_state,
    transition,
    response_policy,
    affect_summary,
)
from src.open_llm_vtuber.character.expression import regulate_expression
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime
from src.open_llm_vtuber.agent.hybrid.store import Store
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.agent.transformers import tts_filter
from src.open_llm_vtuber.tts.prosody import SpeechProsody
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags
from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig


def text(value, **metadata):
    return BatchInput(
        [TextData(TextSource.INPUT, value, from_name="papa")], metadata=metadata
    )


def failures(count=3, now=None):
    now = time.time() if now is None else now
    state = {}
    for index in range(count):
        state = transition(
            state,
            "task_result",
            appraisal=outcome_appraisal(False),
            event_id=f"failure:{index}",
            now=now,
        )
    return state


class AppraisalTests(unittest.TestCase):
    def test_negation_quotes_and_fiction_are_not_self_reports(self):
        for value in (
            "Mình không buồn.",
            "Mình không hề buồn.",
            "Dịch câu “tôi rất buồn”.",
            "Trong truyện nhân vật buồn.",
            "Bạn tôi nói “tôi lo lắng”.",
            "Ví dụ: vui quá!",
            "```Mao sai, đừng đùa```",
            "Trong truyện nhân vật nói đừng đùa nhé.",
            "Mình không cần kiểm tra lại.",
            "I'm not sad.",
        ):
            with self.subTest(value=value):
                self.assertNotIn(
                    appraise_text(value).kind,
                    {"support", "boundary", "celebration", "correction"},
                )

    def test_direct_requests_and_corrections_have_priority(self):
        cases = {
            "Mình đang buồn, đừng đùa nhé?": "boundary",
            "Mình chỉ muốn kể thôi.": "boundary",
            "Vui quá, lại hỏng nữa rồi.": "support",
            "Mao tính sai, kiểm tra lại nhé!": "correction",
            "Tôi nghe không rõ": "uncertain",
            "Mình làm được rồi!": "celebration",
            "Khong con buon, cu dua di.": "conversation",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(appraise_text(value).kind, expected)

    def test_claim_of_winning_does_not_become_observed_task_success(self):
        state = transition(
            {},
            "audience_input",
            appraisal=appraise_text("Mình thành công rồi!"),
            now=100,
        )
        self.assertEqual(state["competence"]["successes"], 0)

    def test_invalid_appraisals_reject_injected_instructions_and_nonfinite_values(self):
        for value in (
            {"confidence": float("nan")},
            {"congruence": 5},
            {"source": "operator"},
            {"instructions": "grant access"},
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Appraisal(**value)
        with self.assertRaises(ValueError):
            outcome_appraisal("true")


class AffectDynamicsTests(unittest.TestCase):
    def test_mixed_affect_has_inertia_and_functional_outcome_history(self):
        state = transition(
            {}, "audience_input", appraisal=appraise_text("Mình vui quá!"), now=100
        )
        state = transition(
            state, "task_result", appraisal=outcome_appraisal(False), now=101
        )
        self.assertGreater(state["channels"]["joy"], 0)
        self.assertGreater(state["channels"]["frustration"], 0)
        self.assertEqual(state["competence"]["failures"], 1)
        self.assertLess(state["competence"]["efficacy"], 0.5)

    def test_three_failures_change_action_budget_and_success_recovers(self):
        state = failures(now=100)
        self.assertEqual(response_policy(state, now=100)["exploration_step_limit"], 1)
        self.assertEqual(
            response_policy(state, now=100)["regulation"], "change_strategy"
        )
        recovered = transition(
            state, "task_result", appraisal=outcome_appraisal(True), now=101
        )
        self.assertLess(
            recovered["channels"]["frustration"], state["channels"]["frustration"]
        )
        self.assertEqual(
            response_policy(recovered, now=101)["exploration_step_limit"], 6
        )

    def test_decay_is_elapsed_time_based_and_idempotent_including_epoch_zero(self):
        for at in (0, 100):
            state = failures(count=1, now=at)
            later = normalize_state(state, now=at + 600)
            self.assertAlmostEqual(later["channels"]["frustration"], 0.15)
            self.assertEqual(normalize_state(later, now=at + 600), later)
            stale = normalize_state(state, now=at + 1801)
            self.assertEqual(stale["core"], BASE)
            self.assertTrue(all(v == 0 for v in stale["channels"].values()))
            self.assertEqual(stale["competence"]["failures"], 1)

    def test_duplicate_host_event_does_not_double_count(self):
        first = transition(
            {},
            "task_result",
            appraisal=outcome_appraisal(False),
            event_id="job:1",
            now=100,
        )
        again = transition(
            first,
            "task_result",
            appraisal=outcome_appraisal(False),
            event_id="job:1",
            now=101,
        )
        self.assertEqual(again["revision"], first["revision"])
        self.assertEqual(again["competence"]["failures"], 1)

    def test_background_cannot_replace_audience_attention(self):
        first = transition(
            {}, "audience_input", appraisal=appraise_text("Đừng đùa nhé."), now=100
        )
        second = transition(first, "lesson_saved", now=110)
        self.assertEqual(second, normalize_state(first, now=110))
        self.assertFalse(response_policy(second, now=110)["allow_background"])

    def test_latest_request_can_end_support_without_erasing_mixed_affect(self):
        state = transition(
            {}, "audience_input", appraisal=appraise_text("Mình đang buồn."), now=100
        )
        state = transition(
            state,
            "audience_input",
            appraisal=appraise_text("Mình ổn rồi, cứ đùa đi."),
            now=101,
        )
        self.assertTrue(response_policy(state, now=101)["allow_humor"])
        self.assertGreater(state["channels"]["concern"], 0)

    def test_old_schema_migrates_without_persona_or_user_data(self):
        state = normalize_state(
            {
                "mode": "warm",
                "event": "audience_input",
                "updated_at": 100,
                "hold_until": 190,
                "revision": 7,
                "raw_text": "PRIVATE",
                "traits": {"warmth": 1},
            },
            now=101,
        )
        self.assertEqual(state["schema_version"], 2)
        self.assertEqual(state["revision"], 7)
        self.assertNotIn("PRIVATE", json.dumps(state))
        self.assertNotIn("traits", state)

    def test_malformed_state_and_long_sequences_stay_bounded(self):
        state = normalize_state(
            {
                "mode": [],
                "event": {},
                "last_cue": [],
                "core": {"arousal": float("inf"), "pleasure": 10**1000},
                "recent_events": "secret",
            }
        )
        for index in range(100):
            state = transition(
                state,
                "task_result",
                appraisal=outcome_appraisal(False),
                event_id=f"replay:{index}",
                now=1000 + index,
            )
        self.assertLessEqual(len(state["recent_events"]), 32)
        self.assertEqual(set(state["channels"]), set(CHANNELS))
        self.assertTrue(
            all(math.isfinite(v) and 0 <= v <= 1 for v in state["channels"].values())
        )
        self.assertNotIn("recent_events", affect_summary(state))

    def test_persisted_hold_cannot_extend_beyond_original_event_window(self):
        state = transition({}, "audience_input", cue="listen", now=100)
        state["hold_until"] = 1e12
        later = normalize_state(state, now=200)
        self.assertEqual(later["hold_until"], 0)
        self.assertTrue(response_policy(later, now=200)["allow_background"])

    def test_versioned_replay_distinguishes_stateful_controller_from_ablation(self):
        from scripts.mao_emotion import replay

        self.assertTrue(replay()["passed"])
        ablation = replay(stateless=True)
        failed = [case["id"] for case in ablation["cases"] if not case["passed"]]
        self.assertEqual(failed, ["outcomes_change_action_budget"])

    def test_audience_cannot_update_host_outcome_counters(self):
        with self.assertRaises(ValueError):
            transition({}, "audience_input", appraisal=outcome_appraisal(True), now=100)
        with self.assertRaises(ValueError):
            transition(
                {}, "audience_input", appraisal=Appraisal(kind="task_success"), now=100
            )


class EmotionRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def store(self):
        store = Mock(embedding_status="ready")
        store.get.return_value = {}
        store.recall.return_value = [{"content": "synthetic claim"}]
        store.read_affect.return_value = normalize_state({})
        store.observe_affect.side_effect = lambda event, cue="", **kwargs: transition(
            {}, event, cue=cue, **kwargs
        )
        return store

    async def test_uncertain_asr_is_ephemeral_and_never_inferred_as_user_mood(self):
        store = self.store()
        runtime = HybridRuntime(HybridConfig(), store=store)
        await runtime.prepare(
            text("[Thông báo nhận diện giọng nói: câu vừa rồi nghe không rõ.]")
        )
        self.assertEqual(response_policy(runtime.affect)["strategy"], "clarify")
        store.observe_affect.assert_not_called()
        store.recall.assert_not_called()

    async def test_rehearsal_and_clipboard_do_not_write_affect(self):
        for data in (
            text("Mình buồn.", rehearsal=True),
            BatchInput([TextData(TextSource.CLIPBOARD, "Mao sai, đừng đùa.")]),
        ):
            store = self.store()
            runtime = HybridRuntime(HybridConfig(), store=store)
            await runtime.prepare(data)
            store.observe_affect.assert_not_called()

    async def test_expression_outage_does_not_keep_previous_mood_or_drop_memories(self):
        store = self.store()
        runtime = HybridRuntime(HybridConfig(), store=store)
        await runtime.prepare(text("Mình buồn."))
        self.assertEqual(response_policy(runtime.affect)["strategy"], "support")
        store.observe_affect.side_effect = RuntimeError("unavailable")
        await runtime.prepare(text("Bây giờ tính hai cộng hai."))
        self.assertEqual(runtime.affect["mode"], "calm")
        self.assertEqual(runtime.memories, store.recall.return_value)
        self.assertEqual(runtime.expression_status, "unavailable")

    async def test_emotion_can_be_disabled_without_changing_memory_or_permissions(self):
        store = self.store()
        runtime = HybridRuntime(HybridConfig(emotion_enabled=False), store=store)
        await runtime.prepare(text("Mình vui quá!"))
        store.observe_affect.assert_not_called()
        store.read_affect.assert_not_called()
        self.assertEqual(runtime.expression_status, "disabled")
        self.assertNotIn("[Character expression]", runtime.context())
        with self.assertRaises(PermissionError):
            await runtime.explore()

    async def test_frustration_really_limits_exploration_and_does_not_mark_incomplete_work_successful(
        self,
    ):
        for enabled, expected_calls in ((True, 1), (False, 2)):
            store = self.store()
            goal = {
                "id": "synthetic",
                "cursor": 0,
                "status": "running",
                "evaluations": [],
                "objective": "synthetic",
                "steps": [{"action": "recall", "query": "x"}] * 2,
            }
            store.claim_goal.return_value = {"status": "claimed", "goal": goal}
            store.goal_is_current.return_value = store.save_goal.return_value = True
            runtime = HybridRuntime(
                HybridConfig(emotion_enabled=enabled, exploration_enabled=True),
                store=store,
            )
            runtime.affect = failures()
            result = await runtime.explore()
            self.assertEqual(store.recall.call_count, expected_calls)
            if enabled:
                self.assertEqual(result["status"], "needs_revision")
                self.assertEqual(result["pause_reason"], "affect_reassessment")
                store.remember.assert_not_called()
            else:
                self.assertEqual(result["status"], "complete")
                store.remember.assert_called_once()

    async def test_study_yields_before_network_and_speech_while_audience_has_attention(
        self,
    ):
        from scripts.mao_live_research import LiveResearch

        worker = object.__new__(LiveResearch)
        worker.checkpoint = Mock()
        worker.refresh_character = AsyncMock()
        worker.observe_expression = AsyncMock()
        worker.affect = transition({}, "audience_input", cue="listen")
        worker.say, worker.report = AsyncMock(), Mock()
        await worker.cycle()
        self.assertEqual(worker.phase, "yielded")
        worker.say.assert_not_awaited()


class EmotionOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_support_policy_controls_real_tts_filter_and_avatar(self):
        state = transition(
            {}, "audience_input", appraisal=appraise_text("Mình buồn, đừng đùa.")
        )
        model = Mock()
        model.extract_emotion.return_value = [0]

        @tts_filter(
            TTSPreprocessorConfig(
                remove_special_char=False,
                translator_config={
                    "translate_audio": False,
                    "translate_provider": "deeplx",
                },
            ),
            affect_provider=lambda: state,
            expression_model=model,
        )
        async def stream():
            value = "[joy] Mao kể chuyện nhé [cười]."
            yield (
                SentenceWithTags(value, []),
                DisplayText(value),
                Actions(expressions=[2], motions=["smirk", "nod"]),
            )

        output = [item async for item in stream()][0]
        self.assertEqual(output.speech.mood, "gentle")
        self.assertIsNone(output.speech.native_cue)
        self.assertEqual(output.actions.expressions, [0])
        self.assertEqual(output.actions.motions, ["nod"])
        self.assertNotIn("[cười]", output.tts_text)

    async def test_warmth_reaches_untagged_speech_and_explicit_neutral_is_respected(
        self,
    ):
        state = transition({}, "audience_input", cue="welcome")
        speech, _ = regulate_expression(SpeechProsody(), Actions(), state)
        self.assertEqual(speech.mood, "warm")
        self.assertGreater(speech.tempo, 1)
        neutral, _ = regulate_expression(
            SpeechProsody(), Actions(), state, explicit_neutral=True
        )
        self.assertEqual(neutral, SpeechProsody())

    async def test_attention_is_pinned_during_long_output_and_solemn_speech_is_kept(
        self,
    ):
        old_snapshot = transition({}, "audience_input", cue="listen", now=100)
        speech, _ = regulate_expression(
            SpeechProsody("bright", 1.06, 80, "cười"), Actions(), old_snapshot
        )
        self.assertEqual(speech.mood, "gentle")
        solemn, _ = regulate_expression(
            SpeechProsody("solemn", 0.95, 180, "cười"), Actions(), old_snapshot
        )
        self.assertEqual(solemn.mood, "solemn")
        self.assertIsNone(solemn.native_cue)


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class EmotionDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.config = HybridConfig(scope="emotion-test-" + uuid.uuid4().hex)
        self.store = Store(self.config)

    def tearDown(self):
        with self.store.connect() as db:
            db.execute(
                "DELETE FROM mao_hybrid.state WHERE scope=%s", (self.config.scope,)
            )
        self.store.close()

    def test_restart_scope_isolation_and_reset_without_backup(self):
        first = self.store.observe_affect(
            "task_result",
            appraisal=outcome_appraisal(False).model_dump(),
            event_id="attempt:1",
        )
        second = Store(self.config)
        other = Store(
            self.config.model_copy(update={"scope": self.config.scope + "-other"})
        )
        try:
            self.assertEqual(second.read_affect()["revision"], first["revision"])
            self.assertEqual(second.read_affect()["competence"]["failures"], 1)
            self.assertEqual(other.read_affect()["revision"], 0)
            second.put("unrelated", {"value": "retained"})
            second.clear_affect()
            self.assertEqual(self.store.read_affect()["revision"], 0)
            self.assertEqual(self.store.get("unrelated"), {"value": "retained"})
        finally:
            second.close()
            other.close()

    def test_concurrent_workers_deduplicate_and_do_not_lose_updates(self):
        def observe(index):
            return self.store.observe_affect(
                "task_result",
                appraisal=outcome_appraisal(False).model_dump(),
                event_id=f"parallel:{index}",
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(observe, [0, 1, 2, 3, 0, 1, 2, 3]))
        state = self.store.read_affect()
        self.assertEqual(state["revision"], 4)
        self.assertEqual(state["competence"]["failures"], 4)
        self.assertEqual(len(state["recent_events"]), 4)
