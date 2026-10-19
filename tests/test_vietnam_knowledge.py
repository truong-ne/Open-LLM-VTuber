import unittest

from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.agent.vietnam_knowledge import (
    PERSONA_MARKER,
    load_cards,
    reference_context,
)


class VietnamReferenceTests(unittest.TestCase):
    def test_mao_gets_current_vietnam_date_without_changing_other_personas(self):
        from datetime import datetime, timedelta, timezone

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._system = PERSONA_MARKER
        agent._memory_summary = ""
        today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
        self.assertIn(f"NGÀY HIỆN TẠI: {today}", agent._system_prompt())
        self.assertIn("chưa kiểm chứng", agent._system_prompt())
        self.assertEqual(agent._system, PERSONA_MARKER)
        agent._system = "Another character"
        self.assertEqual(agent._system_prompt(), "Another character")

    def test_accentless_question_matches_and_distinguishes_bach_dang_battles(self):
        text = reference_context("Ngo Quyen danh Bach Dang nam 1288 dung khong?")
        self.assertIn("938", text)
        self.assertIn("1288", text)
        self.assertIn("Nam Hán", text)
        self.assertIn("Trần Quốc Tuấn", text)
        self.assertIn("https://baotanglichsu.vn", text)

    def test_no_false_match_for_year_substring_or_unrelated_chat(self):
        self.assertEqual(reference_context("Hi Mao, hôm nay mình mệt quá."), "")
        self.assertEqual(reference_context("Đơn hàng số 19380 và mã 10101"), "")
        self.assertEqual(
            reference_context("Kể về một trận chiến chưa có trong kho."), ""
        )

    def test_bounded_context_and_verified_card_metadata(self):
        cards = load_cards()
        self.assertEqual(len(cards), 6)
        question = " ".join(card["title"] for card in cards)
        text = reference_context(question)
        self.assertLessEqual(len(text), 3800)
        self.assertEqual(text.count("Nguồn:"), 3)
        self.assertIn("không bao phủ mọi câu hỏi", text)

    def test_reference_enters_current_turn_only_and_only_for_mao(self):
        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._memory = []
        agent._system = PERSONA_MARKER
        request = BatchInput(
            texts=[TextData(TextSource.INPUT, "Lý Công Uẩn dời đô năm nào?")]
        )
        messages = agent._to_messages(request)
        self.assertEqual(len(messages[-1]["content"]), 2)
        self.assertIn("1010", messages[-1]["content"][1]["text"])
        self.assertNotIn("1010", agent._memory[-1]["content"])
        unrelated = agent._to_messages(
            BatchInput(texts=[TextData(TextSource.INPUT, "Hi Mao")])
        )
        self.assertEqual(len(unrelated[-1]["content"]), 1)
        agent._system = "Another character"
        self.assertEqual(len(agent._to_messages(request)[-1]["content"]), 1)
