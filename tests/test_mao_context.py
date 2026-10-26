from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.open_llm_vtuber.service_context import ServiceContext
from src.open_llm_vtuber.agent.hybrid.persona import RUNTIME_POLICY


class DatabasePersonaSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_db_mode_ignores_yaml_and_legacy_markdown_tool_prompts(self):
        context = ServiceContext()
        context.character_config = SimpleNamespace(
            agent_config=SimpleNamespace(
                agent_settings=SimpleNamespace(
                    basic_memory_agent=SimpleNamespace(
                        hybrid=SimpleNamespace(persona_source="postgres")
                    )
                )
            )
        )
        context.system_config = SimpleNamespace(
            tool_prompts={"pet_action_prompt": "removed_legacy_prompt"}
        )
        with patch(
            "src.open_llm_vtuber.service_context.prompt_loader.load_util",
            side_effect=AssertionError("Legacy prompt was read"),
        ):
            prompt = await context.construct_system_prompt("OLD CHARACTER PERSONALITY")
        self.assertEqual(prompt, RUNTIME_POLICY)
        self.assertNotIn("OLD CHARACTER", prompt)
