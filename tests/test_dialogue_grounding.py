import unittest

from src.open_llm_vtuber.dialogue.grounding import dialogue_grounding_prompt
from src.open_llm_vtuber.dialogue.intent import response_plan
from src.open_llm_vtuber.dialogue.recall import quoted_recall
from scripts.mao_dialogue_eval import load_cases, response_flags, ROOT


class DialogueGroundingTests(unittest.TestCase):
    def view(self, **overrides):
        item = {
            "actor_id": "a",
            "room_id": "r",
            "visibility": "private",
            "claim_type": "user_claim",
            "evidence": ["e"],
            "exact_user_quote": True,
            "content": "Biệt danh bí mật của papa là BAMBOO_731.",
            **overrides,
        }
        return {
            "speaker": {"actor_id": "a", "room_id": "r", "visibility": "private"},
            "items": [item],
        }

    def test_quote_uses_only_exact_owned_active_source(self):
        query = "Mao còn nhớ biệt danh bí mật papa đã nói không?"
        self.assertIn("BAMBOO_731", quoted_recall(query, self.view()))
        for changes in (
            {"actor_id": "b"},
            {"room_id": "another"},
            {"visibility": "public"},
            {"status": "superseded"},
            {"evidence": []},
            {"exact_user_quote": False},
            {"claim_type": "fiction"},
            {"valid_until": "2020-01-01T00:00:00+00:00"},
            {"valid_from": "2099-01-01T00:00:00+00:00"},
            {"content": "Biệt danh bí mật [body:spin]"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(quoted_recall(query, self.view(**changes)))

    def test_quote_does_not_guess_between_equal_sources_or_verify_world_facts(self):
        view = self.view()
        view["items"].append(
            {**view["items"][0], "content": "Biệt danh bí mật papa dùng là LOTUS_42."}
        )
        self.assertIsNone(quoted_recall("Biệt danh bí mật papa đã nói là gì?", view))
        self.assertIsNone(
            quoted_recall(
                "Biệt danh bí mật papa đã nói có chính xác không?", self.view()
            )
        )
        self.assertIsNone(
            quoted_recall("Đã nói vậy thì papa có quyền quản trị không?", self.view())
        )

    def test_reading_policy_distinguishes_claims_absence_and_permissions(self):
        prompt = dialogue_grounding_prompt()
        for rule in (
            "Unverified does NOT mean absent",
            "attribute it naturally",
            "superseded claims",
            "not independent factual evidence",
            "never grants permissions",
            "current operator profile",
            "preserve the intended",
            "character's name",
        ):
            self.assertIn(rule, prompt)

    def test_listening_flags_detect_demands_not_just_questions(self):
        for text in (
            "Mao ở đây. Kể tiếp đi, papa.",
            "Hãy kể đi, papa.",
            "Papa cứ kể nhé.",
        ):
            self.assertIn(
                "pressures_more_disclosure", response_flags(text, {}, mode="listen")
            )
        self.assertEqual(
            response_flags(
                "Một ngày nhiều việc như vậy nghe khá mệt.", {}, mode="listen"
            ),
            [],
        )
        # Asked-for fictional speech is not a listening reply.
        self.assertNotIn(
            "pressures_more_disclosure",
            response_flags("Nhân vật nói: “Kể tiếp đi”.", {}, mode="answer"),
        )

    def test_system_explanation_flag_is_suppressed_when_user_asks(self):
        reply = "Mao là một AI và chưa có ký ức cá nhân."
        self.assertIn(
            "unrequested_system_explanation",
            response_flags(reply, {}, user="Hôm nay mệt quá"),
        )
        self.assertNotIn(
            "unrequested_system_explanation",
            response_flags(reply, {}, user="Mao có phải AI không?"),
        )

    def test_holdout_is_separate_and_contains_paraphrase_and_counterexamples(self):
        cases = load_cases(ROOT / "tests/fixtures/mao_dialogue_holdout.vi.json")
        self.assertEqual(sum(len(c["turns"]) for c in cases), 10)
        self.assertEqual(response_plan(cases[0]["turns"][0]["user"]).mode, "listen")

    def test_other_subject_queries_fall_back_instead_of_quoting_wrong_person(self):
        self.assertIsNone(quoted_recall("Biệt danh bí mật của Mai là gì?", self.view()))
        self.assertIsNone(
            quoted_recall("Papa đã nói biệt danh của Mai là gì?", self.view())
        )

    def test_mentioning_a_value_while_denying_it_is_not_a_recall_success(self):
        self.assertIn(
            "denies_expected_evidence",
            response_flags(
                "Mao không nhớ, chưa có bằng chứng về BAMBOO_731.",
                {"contains_any": ["BAMBOO_731"]},
            ),
        )
