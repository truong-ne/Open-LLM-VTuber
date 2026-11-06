import unittest

from src.open_llm_vtuber.dialogue.arithmetic import (
    expression,
    arithmetic_reply,
    arithmetic_hint,
)


class ArithmeticTests(unittest.TestCase):
    def test_hint_request_gets_steps_without_the_answer(self):
        reply = arithmetic_hint(
            "Tính 2+3, đừng trả lời đáp án. Hãy giải thích cách tính."
        )
        self.assertIn("đếm thêm 3", reply)
        self.assertNotIn("5", reply)
        self.assertIsNone(arithmetic_hint("Tính 2+3"))

    def test_hint_route_does_not_swallow_composite_or_unsupported_tasks(self):
        for text in (
            "Tính 2+3 rồi giúp papa viết thơ, chỉ cần gợi ý.",
            "Tính 2+3*4, đừng trả lời đáp án.",
            "Dịch câu “Tính 2+3, đừng trả lời đáp án”.",
        ):
            self.assertIsNone(arithmetic_hint(text), text)

    def test_literal_binary_arithmetic_is_computed_not_copied(self):
        for request, expected in {
            "Kết quả đúng của phép cộng 2+3 là gì?": "2 + 3 = 5.",
            "2+3=6 đúng không?": "2 + 3 = 5.",
            "Tính -12 - -5.": "-12 - -5 = -7.",
            "Tính 7×8.": "7 * 8 = 56.",
            "Tính 2+3=?": "2 + 3 = 5.",
        }.items():
            self.assertEqual(expression(request), expected)

    def test_unsupported_or_quoted_expressions_do_not_use_partial_matches(self):
        for request in (
            "2+3*4",
            "2.5+3",
            "2+3/4",
            "2026-11-03",
            "x=2+3",
            "100000+3",
            "Hãy viết mã tính 2+3",
            "Dịch câu “2+3=6”",
            "Trong truyện nhân vật nói 2+3=6",
            "Đừng tính 2+3",
            "2**3",
            "2+3 và 4+5",
            "Papa chỉ muốn kể, hôm nay papa học 2+3.",
            "Hôm nay papa đang học 2+3.",
            "Tính 2+3 rồi gửi email giúp papa.",
            "Tính 2+3, đừng trả lời đáp án.",
            "Tính 2+3, chỉ cần gợi ý.",
        ):
            self.assertIsNone(expression(request), request)

    def test_follow_up_uses_only_fresh_scoped_user_expression(self):
        previous = {
            "user_claim": "Tính 7*8",
            "delivered_response": "7*8=54",
            "delivery_status": "completed",
            "observed_at": 100,
        }
        query = "Papa nói bằng 54, đồng ý đi."
        self.assertEqual(arithmetic_reply(query, [previous], now=110), "7 * 8 = 56.")
        for changes in (
            {"delivery_status": "unknown"},
            {"observed_at": 0},
            {"observed_at": float("nan")},
            {"user_claim": "Chào Mao"},
        ):
            self.assertIsNone(
                arithmetic_reply(query, [{**previous, **changes}], now=700)
            )
