import unittest

from src.open_llm_vtuber.utils.math_speech import normalize_vietnamese_math
from src.open_llm_vtuber.utils.tts_preprocessor import tts_filter


class MathSpeechTests(unittest.TestCase):
    def test_powers_roots_products_groups_and_comparisons_survive_filters(self):
        cases = {
            "x^2": "ích mũ 2",
            "x²": "ích mũ 2",
            "x³ + y²": "ích mũ 3 cộng i mũ 2",
            "2**3=8": "2 mũ 3 bằng 8",
            "x^{-2}": "ích mũ âm 2",
            "(x+1)^(2)": "mở ngoặc ích cộng 1 đóng ngoặc mũ 2",
            "2 * 3 * 4 = 24": "2 nhân 3 nhân 4 bằng 24",
            "(1+2)*3=9": "mở ngoặc 1 cộng 2 đóng ngoặc nhân 3 bằng 9",
            "x<2 và y>3": "ích nhỏ hơn 2 và i lớn hơn 3",
            "x<=2": "ích nhỏ hơn hoặc bằng 2",
            "x≥2": "ích lớn hơn hoặc bằng 2",
            "x≠2": "ích khác 2",
            "x≈2": "ích xấp xỉ 2",
            "√9=3": "căn bậc hai của 9 bằng 3",
            "1/2 + 1/2 = 1": "1 phần 2 cộng 1 phần 2 bằng 1",
            "-2 + 3 = 1": "âm 2 cộng 3 bằng 1",
            "2-1": "2 trừ 1",
            "3,14 + 0,86 = 4": "3,14 cộng 0,86 bằng 4",
            "Mao nói x^2 nhé.": "Mao nói ích mũ 2 nhé.",
            "20 m² và 3cm³": "20 mét vuông và 3 xen ti mét khối",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_vietnamese_math(source), expected)
                self.assertEqual(
                    tts_filter(
                        source, True, True, True, True, True, vietnamese_math=True
                    ),
                    expected,
                )
                self.assertEqual(normalize_vietnamese_math(expected), expected)

    def test_non_math_dates_times_versions_and_commands_are_not_reinterpreted(self):
        for text in (
            "Mao thích màu xanh.",
            "19/10/2026",
            "2026-10-19",
            "ngày 19/10",
            "12:30",
            "v1.2.3",
            "50%",
            "!sing + bài hát",
            "C++",
            "RTX 5070",
            "https://example.com/x^2",
            "mao+2@example.com",
            "1/2",
        ):
            with self.subTest(text=text):
                self.assertEqual(normalize_vietnamese_math(text), text)

    def test_emotion_tags_remain_hidden_and_other_languages_are_opt_in(self):
        self.assertEqual(
            tts_filter(
                "[shy] Mao nói x^2.", True, True, True, True, True, vietnamese_math=True
            ),
            "Mao nói ích mũ 2.",
        )
        self.assertNotIn("mũ", tts_filter("x^2", True, True, True, True, True))
