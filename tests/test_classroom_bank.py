import json
from pathlib import Path
import re
import unittest
from collections import Counter
from src.open_llm_vtuber.live.vua_tieng_viet import normalize_answer

ROOT = Path(__file__).resolve().parents[1]


class ClassroomBankTests(unittest.TestCase):
    def test_expansion_has_unique_bounded_playable_questions_without_leaking_answers(
        self,
    ):
        rows = json.loads(
            (ROOT / "knowledge/classroom.expanded.vi.json").read_text(encoding="utf-8")
        )
        old = []
        for file in [
            "vua_tieng_viet.vi.json",
            "classroom.vi.json",
            "classroom.hard.vi.json",
        ]:
            old += json.loads((ROOT / "knowledge" / file).read_text(encoding="utf-8"))
        policy = json.loads(
            (ROOT / "knowledge/classroom-bank-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(rows), 2500)
        self.assertEqual(len(old), 257)
        old_keys = {normalize_answer(w["answer"]) for w in old}
        self.assertEqual(
            {normalize_answer(a) for a in policy["excluded_answers"]}, old_keys
        )
        keys = {normalize_answer(w["answer"]) for w in rows}
        self.assertEqual(len(keys), 2500)
        self.assertFalse(keys & old_keys)
        self.assertEqual(
            Counter(w["difficulty"] for w in rows), {"normal": 2000, "hard": 500}
        )
        self.assertGreaterEqual(len({w["category"] for w in rows}), 20)
        self.assertEqual(sum(w["category"] == "Ca dao và tục ngữ" for w in rows), 30)
        for word in rows:
            with self.subTest(answer=word["answer"]):
                self.assertTrue(2 <= len(word["answer"]) <= 32)
                self.assertEqual(len(word["hints"]), 3)
                self.assertTrue(all(0 < len(h) <= 200 for h in word["hints"]))
                self.assertTrue(0 < len(word["explanation"]) <= 300)
                answer = normalize_answer(word["answer"])
                for hint in word["hints"][:2]:
                    self.assertIsNone(
                        re.search(
                            r"(?<!\w)" + re.escape(answer) + r"(?!\w)",
                            normalize_answer(hint),
                        )
                    )
