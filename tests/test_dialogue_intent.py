from copy import deepcopy
import json
import time
import unittest
from unittest.mock import Mock, patch

from src.open_llm_vtuber.dialogue.context import context_block
from src.open_llm_vtuber.dialogue.intent import response_plan
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource


def exchange(user="Papa chỉ muốn kể thôi.", **changes):
    return {
        "event_id": "prior",
        "user_claim": user,
        "delivered_response": "Papa cứ kể, thiếp nghe đây.",
        "delivery_status": "completed",
        "observed_at": 100,
        **changes,
    }


class IntentTests(unittest.TestCase):
    def test_later_request_in_same_input_replaces_earlier_listening_request(self):
        for text, expected in (
            ("Papa chỉ muốn kể thôi. Bây giờ cho papa ba cách giải quyết.", "answer"),
            ("Đừng chỉ muốn kể thôi, hãy giải thích đoạn này.", "answer"),
            ("Giúp papa tìm giải pháp. Bây giờ papa chỉ muốn kể thôi.", "listen"),
            ("Đổi chủ đề nhé, hãy kể một điều về mèo.", "change_topic"),
            ("Papa muốn yên tĩnh. Bây giờ Mao nói tiếp đi.", "resume"),
        ):
            with self.subTest(text=text):
                self.assertEqual(response_plan(text).mode, expected)

    def test_current_explicit_requests(self):
        for text, mode in {
            "Hôm nay mệt quá, papa chỉ muốn kể thôi.": "listen",
            "Chỉ muốn Mao nghe thôi.": "listen",
            "Đừng vội khuyên nhé.": "listen",
            "Mình không muốn lời khuyên.": "listen",
            "Mao hiểu sai ý papa rồi.": "repair",
            "Ý papa là đổi giờ hẹn, không phải hủy.": "repair",
            "Ổn rồi, đổi chủ đề nhé.": "change_topic",
            "Cho papa ba cách giải quyết.": "answer",
            "Giải thích đoạn này.": "answer",
        }.items():
            with self.subTest(text=text):
                self.assertEqual(response_plan(text).mode, mode)

    def test_quotes_reports_negation_and_clipboard_like_data_are_not_requests(self):
        for text in (
            "Dịch câu “Mao hiểu sai rồi”.",
            "Trong truyện nhân vật chỉ muốn kể thôi.",
            "```Đừng vội khuyên nhé```",
            "Bạn tôi chỉ muốn tâm sự.",
            "Mao không hiểu sai đâu.",
            "Papa không chỉ muốn kể thôi.",
            "Đừng đổi chủ đề nhé.",
            "Papa chưa muốn nói chuyện khác.",
            "Mao đừng hiểu sai nhé.",
        ):
            with self.subTest(text=text):
                self.assertEqual(response_plan(text).mode, "respond")

    def test_listening_continues_only_from_fresh_confirmed_user_request(self):
        plan = response_plan("Vẫn vậy.", [exchange()], now=110)
        self.assertEqual(plan.mode, "listen")
        self.assertEqual(plan.context_event, "prior")
        self.assertEqual(
            response_plan("Ừ.", [exchange("Vẫn vậy."), exchange()], now=110).mode,
            "listen",
        )
        for history in (
            [],
            [None],
            [exchange(observed_at=0)],
            [exchange(observed_at=701)],
            [exchange(observed_at=float("nan"))],
            [exchange(observed_at="100")],
            [exchange(delivery_status="unknown")],
            [exchange(delivery_status="interrupted")],
            [exchange("Xin chào", delivered_response="Bạn chỉ muốn kể thôi?")],
            [exchange("Đổi chủ đề nhé"), exchange()],
            [exchange("Cho papa một giải pháp"), exchange()],
        ):
            with self.subTest(history=history):
                self.assertEqual(
                    response_plan("Vẫn vậy", history, now=700).mode, "respond"
                )

    def test_new_request_or_unrelated_topic_does_not_inherit_listening(self):
        history = [exchange()]
        self.assertEqual(
            response_plan("Cho papa ba cách xử lý", history, now=110).mode, "answer"
        )
        self.assertEqual(
            response_plan("Đổi chủ đề nhé", history, now=110).mode, "change_topic"
        )
        self.assertEqual(
            response_plan("Hôm nay trời đẹp", history, now=110).mode, "respond"
        )
        self.assertEqual(response_plan("", history, now=110).mode, "respond")

    def test_guidance_is_fixed_and_has_no_user_text_or_persistent_claim(self):
        plan = response_plan("Mao hiểu sai rồi. PRIVATE_MARKER")
        self.assertNotIn("PRIVATE_MARKER", plan.prompt())
        self.assertIn("tối đa một câu", plan.prompt())
        self.assertIn("this turn only", plan.prompt())


class ContextBudgetTests(unittest.TestCase):
    def decode(self, block):
        encoded = block.splitlines()[2]
        return encoded, json.loads(encoded)

    def test_latest_exchange_survives_retrieval_pressure(self):
        experience = {
            "items": [{"content": "ký ức " * 300}],
            "delivered_turns": [exchange(), exchange("lượt cũ " * 300)],
            "focus": {"topic": "chủ đề " * 300},
        }
        original = deepcopy(experience)
        encoded, value = self.decode(context_block(experience, [], {}, budget=650))
        self.assertLessEqual(len(encoded), 650)
        self.assertEqual(value["delivered_turns"], [exchange()])
        self.assertEqual(experience, original)

    def test_activity_input_is_not_mutated_and_tiny_budgets_remain_valid_json(self):
        activities = [{"story": "fiction " * 300}]
        original = deepcopy(activities)
        for budget in (2, 30, 300, 6000):
            encoded, _ = self.decode(context_block({}, activities, {}, budget=budget))
            self.assertLessEqual(len(encoded), budget)
            self.assertEqual(activities, original)
        with self.assertRaises(ValueError):
            context_block({}, [], {}, budget=1)


class IntentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self):
        store = Mock(embedding_status="ready")
        store.get.return_value = {}
        store.recall.return_value = []
        return HybridRuntime(
            HybridConfig(enabled=True, emotion_enabled=False), store=store
        )

    async def test_plan_resets_each_turn_and_synthetic_inputs_cannot_select_it(self):
        runtime = self.runtime()
        await runtime.prepare(
            BatchInput([TextData(TextSource.INPUT, "Chỉ muốn kể thôi.")])
        )
        self.assertEqual(runtime.dialogue_plan.mode, "listen")
        self.assertIn("[Current response guidance", runtime.context())
        for key in ("rehearsal", "wesnoth_turn", "skip_memory", "_host_proposal"):
            await runtime.prepare(
                BatchInput(
                    [TextData(TextSource.INPUT, "Chỉ muốn kể thôi.")],
                    metadata={key: True},
                )
            )
            self.assertIsNone(runtime.dialogue_plan)
            self.assertNotIn("[Current response guidance", runtime.context())
        await runtime.prepare(
            BatchInput([TextData(TextSource.CLIPBOARD, "Mao hiểu sai rồi.")])
        )
        self.assertEqual(runtime.dialogue_plan.mode, "respond")
        await runtime.prepare(
            BatchInput([TextData(TextSource.INPUT, "Giải thích đoạn này.")])
        )
        self.assertEqual(runtime.dialogue_plan.mode, "answer")

    async def test_follow_up_uses_host_scoped_history_even_without_emotion_feature(
        self,
    ):
        runtime = self.runtime()
        identity = {
            "event_id": "current",
            "room_id": "room",
            "actor_id": "person",
            "visibility": "private",
            "source_text": "Vẫn vậy.",
            "policy": {"settings": {}},
        }
        with (
            patch(
                "src.open_llm_vtuber.experience.repository.Experiences.context",
                return_value={
                    "items": [{"content": "UNIQUE_MEMORY_MARKER " * 500}],
                    "revision": 0,
                    "delivered_turns": [exchange(observed_at=time.time())],
                },
            ) as context,
            patch(
                "src.open_llm_vtuber.experience.activities.Activities.context",
                return_value=[],
            ),
            patch(
                "src.open_llm_vtuber.dialogue.focus.Focus.current", return_value=None
            ),
        ):
            await runtime.prepare(
                BatchInput(
                    [TextData(TextSource.INPUT, "ignored")],
                    metadata={"_interaction": identity},
                )
            )
        self.assertEqual(runtime.dialogue_plan.mode, "listen")
        self.assertEqual(context.call_args.args[:3], ("room", "person", "private"))
        self.assertNotIn("UNIQUE_MEMORY_MARKER", runtime.context())
        self.assertIn("Papa chỉ muốn kể thôi", runtime.context())
