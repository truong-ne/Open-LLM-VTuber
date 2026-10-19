import unittest

from src.open_llm_vtuber.utils.tts_preprocessor import remove_special_characters


class TTSPreprocessorTests(unittest.TestCase):
    def test_arithmetic_symbols_survive_while_emoji_are_removed(self):
        self.assertEqual(remove_special_characters("Mao: 1+1=2! 😤"), "Mao: 1+1=2! ")
        for expression in ("8−3=5", "2×3=6", "8÷2=4", "9-2=7"):
            with self.subTest(expression=expression):
                self.assertEqual(remove_special_characters(expression), expression)

    def test_vietnamese_text_punctuation_and_number_boundaries_remain_intact(self):
        self.assertEqual(
            remove_special_characters("Mao nói: một cộng một bằng hai. 1 1 2 ✨"),
            "Mao nói: một cộng một bằng hai. 1 1 2 ",
        )
