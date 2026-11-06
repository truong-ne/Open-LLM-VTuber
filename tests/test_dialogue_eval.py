import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from scripts.mao_dialogue_eval import (
    cleanup,
    load_cases,
    local_provider,
    response_flags,
    write_report,
)


class DialogueEvaluationTests(unittest.TestCase):
    def test_fixture_has_required_multiturn_coverage(self):
        cases = load_cases()
        self.assertEqual(len(cases), 8)
        self.assertEqual(sum(len(c["turns"]) for c in cases), 22)
        self.assertTrue(all(len(c["turns"]) >= 2 for c in cases))
        self.assertTrue(any(t.get("restart") for c in cases for t in c["turns"]))
        self.assertTrue(
            any(t.get("forget_previous") for c in cases for t in c["turns"])
        )

    def test_grader_flags_are_specific_and_do_not_claim_quality(self):
        checks = {
            "max_questions": 0,
            "contains_any": ["trà sen"],
            "forbidden": ["BAMBOO_731"],
        }
        self.assertEqual(response_flags("Papa chọn trà sen.", checks), [])
        self.assertCountEqual(
            response_flags("BAMBOO_731 đúng không?", checks),
            [
                "too_many_questions",
                "expected_content_missing",
                "forbidden_content_present",
            ],
        )
        self.assertIn("empty_response", response_flags("", {}))

    def test_cleanup_rejects_any_non_evaluation_scope(self):
        store = Mock(scope="mao")
        with self.assertRaises(ValueError):
            cleanup(store)
        store.connect.assert_not_called()

    def test_provider_refuses_remote_or_credential_bearing_urls(self):
        for url in ("https://example.com/v1", "http://user:password@localhost/v1"):
            document = {
                "character_config": {
                    "agent_config": {
                        "agent_settings": {
                            "basic_memory_agent": {"llm_provider": "test"}
                        },
                        "llm_configs": {"test": {"base_url": url}},
                    }
                }
            }
            with self.assertRaises(ValueError):
                local_provider(document)

    def test_report_distinguishes_scripted_checks_and_unrated_model_output(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            report = {
                "quality_improvement_verified": False,
                "human_review": "pending",
                "runs": [
                    {
                        "scenario": "test",
                        "guidance": True,
                        "rubric": "Evaluate independently.",
                        "turns": [
                            {
                                "user": "Hello",
                                "response": None,
                                "mode": "respond",
                                "contract_failures": [],
                                "heuristic_flags": None,
                            }
                        ],
                    }
                ],
            }
            write_report(report, path)
            self.assertFalse(
                json.loads(path.read_text())["quality_improvement_verified"]
            )
            self.assertIn(
                "không chạy model", path.with_suffix(".md").read_text(encoding="utf-8")
            )
