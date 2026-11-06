import unittest

from scripts.mao_self_model import SELF_MODEL, adapt_self_practice
from src.open_llm_vtuber.character.identity import (
    apply_avatar_identity,
    identity_prompt,
)
from scripts.mao_live_research import evolved_profile


class SelfModelTests(unittest.TestCase):
    def test_current_avatar_identity_is_explicit_and_preserves_profile_fields(self):
        profile = {
            "revision": 8,
            "status": "active",
            "prompt": "Tính cách cũ",
            "topics": ["âm nhạc"],
            "proactive_prompt": "Giữ nguyên",
        }
        result = apply_avatar_identity(profile)
        self.assertIn("phiên bản nữ hóa của Draco Malfoy", identity_prompt(result))
        self.assertEqual(result["topics"], profile["topics"])
        self.assertEqual(result["proactive_prompt"], profile["proactive_prompt"])
        self.assertIn("Tính cách cũ", result["prompt"])
        self.assertEqual(apply_avatar_identity(result)["prompt"], result["prompt"])
        marked = {
            **profile,
            "prompt": "[Nhận thức nền của Mao]Nền cũ[/Nhận thức nền của Mao]",
        }
        self.assertIn("female Malfoy", identity_prompt(apply_avatar_identity(marked)))

    def test_biological_needs_and_borrowed_schedules_become_virtual_reflection(self):
        thought, practice = adapt_self_practice(
            "Mao cần ngủ để tâm trí được nghỉ ngơi.",
            "Mao sẽ thực hành 15 phút mỗi tháng và hít thở chậm.",
            "sự tự chấp nhận",
        )
        self.assertNotIn("Mao cần ngủ", thought)
        self.assertNotIn("15 phút", practice)
        self.assertNotIn("hít thở", practice)
        self.assertIn("tương tác thật", practice)

    def test_human_source_facts_and_valid_digital_actions_are_preserved(self):
        thought = (
            "Mao hiểu rằng con người cần ngủ, còn mình học qua thông tin và đối thoại."
        )
        practice = (
            "Mao muốn đọc lại một bình luận thật và ghi nhận điều mình còn chưa hiểu."
        )
        self.assertEqual(
            adapt_self_practice(thought, practice, "đồng cảm"), (thought, practice)
        )

    def test_personality_evolution_preserves_ai_identity_creator_and_aspiration(self):
        profile = dict(
            revision=1,
            status="active",
            prompt=SELF_MODEL,
            proactive_prompt="",
            autonomy_prompt="",
            topics=[],
        )
        result = evolved_profile(
            profile, dict(warmth="friendly", humor="playful", length="brief")
        )
        self.assertTrue(result["prompt"].startswith(SELF_MODEL))
        self.assertIn("papa", result["prompt"])
        self.assertIn("Become a real human", result["prompt"])
        self.assertIn("môi trường ảo", result["prompt"])
