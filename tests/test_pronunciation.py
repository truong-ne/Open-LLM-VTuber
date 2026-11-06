import unittest

from src.open_llm_vtuber.utils.pronunciation import normalize_spoken_names


class PronunciationTests(unittest.TestCase):
    def test_requested_name_is_read_as_words_instead_of_acronyms(self):
        for name in ("KAITO KID", "kaito kid", "Kaito Kid", "KAITO   KID"):
            with self.subTest(name=name):
                self.assertEqual(
                    normalize_spoken_names(f"Cảm ơn {name} nhé!"),
                    "Cảm ơn Kaito Kid nhé!",
                )
        self.assertEqual(
            normalize_spoken_names("KAITO KID, đừng chọc Mao! AI, CPU và GPU."),
            "Kaito Kid, đừng chọc Mao! AI, CPU và GPU.",
        )
        self.assertEqual(
            normalize_spoken_names("KAITO KIDDO và XKAITO KID"),
            "KAITO KIDDO và XKAITO KID",
        )

    def test_blue_compact_nickname_is_segmented_without_changing_mentioned_person(self):
        source = "Cửabiếtđinhàbiếtbaysânbiếtbò🪽 nói em yêu Mèo Gian Khổ bro."
        spoken = normalize_spoken_names(source)
        self.assertEqual(
            spoken,
            "Cửa biết đi, nhà biết bay, sân biết bò nói em yêu Mèo Gian Khổ bro.",
        )
        self.assertIn("Cửabiếtđinhàbiếtbaysânbiếtbò🪽", source)
        self.assertEqual(normalize_spoken_names(spoken), spoken)

    def test_real_vieneu_frontend_preserves_english_name_syllables(self):
        try:
            from vieneu_utils.phonemize_text import (
                normalize_to_chunks_v3_with_gaps,
                phonemize_text,
            )
        except ImportError:
            self.skipTest("Optional VieNeu frontend is not installed")
        source = "Mao cảm ơn KAITO KID nhé."
        spoken = normalize_spoken_names(source)
        chunks, _ = normalize_to_chunks_v3_with_gaps(spoken)
        self.assertIn("kaito kid", chunks[0])
        self.assertNotIn("ca a i tê ô", chunks[0])
        phones = phonemize_text(spoken)
        self.assertIn("aɪ", phones)
        self.assertIn("ɪd", phones)
        self.assertIn("KAITO KID", source)
