import json
import unittest

from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.contracts import CONTRACTS
from src.open_llm_vtuber.agent.hybrid.runtime import TOOL, lean_tool


class LeanToolTests(unittest.TestCase):
    def test_disabled_features_are_not_offered_to_the_model(self):
        tool = lean_tool(HybridConfig(enabled=True))
        operations = tool["input_schema"]["properties"]["operation"]["enum"]
        self.assertEqual(
            operations, ["recall", "remember", "forget", "feedback", "status"]
        )
        schema = json.dumps(tool)
        for name in ("wesnoth", "computer", "explore", "vision_click", "PlanStep"):
            self.assertNotIn(name, schema)
        self.assertLess(len(schema), len(json.dumps(TOOL)) / 2)

    def test_every_offered_operation_still_has_a_validating_contract(self):
        tool = lean_tool(HybridConfig(enabled=True))
        for operation in tool["input_schema"]["properties"]["operation"]["enum"]:
            self.assertIn(operation, CONTRACTS)
        data = tool["input_schema"]["properties"]["data"]["properties"]
        self.assertEqual(
            set(data), {"query", "kind", "source", "content", "subject", "id", "score", "note"}
        )
        self.assertEqual(
            set(data["kind"]["enum"]), {"long_term", "social", "skill"}
        )

    def test_name_is_unchanged_so_the_executor_still_routes_it(self):
        self.assertEqual(lean_tool(HybridConfig(enabled=True))["name"], TOOL["name"])

    def test_enabling_a_feature_restores_the_full_schema(self):
        for options in (
            {"computer": {"enabled": True}},
            {"exploration_enabled": True},
            {"wesnoth_enabled": True},
        ):
            with self.subTest(options=options):
                self.assertIs(lean_tool(HybridConfig(enabled=True, **options)), TOOL)


if __name__ == "__main__":
    unittest.main()
