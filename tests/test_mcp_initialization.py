import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.mcpp.tool_adapter import ToolAdapter
from src.open_llm_vtuber.mcpp.server_registry import ServerRegistry
from src.open_llm_vtuber.mcpp.types import FormattedTool
from src.open_llm_vtuber.service_context import ServiceContext


class MCPInitializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_discovery_supplies_prompt_native_schemas_and_executor(self):
        raw = {
            "search": FormattedTool(
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                related_server="ddg-search",
                description="Search current web information",
            )
        }
        info = {
            "ddg-search": {
                "search": {
                    "description": "Search current web information",
                    "parameters": {"query": {"type": "string"}},
                    "required": ["query"],
                }
            }
        }
        adapter = ToolAdapter(server_registery=Mock())
        adapter.get_server_and_tool_info = AsyncMock(return_value=(info, raw))
        context = ServiceContext()
        context.tool_adapter = adapter
        with patch(
            "src.open_llm_vtuber.service_context.ServerRegistry",
            return_value=Mock(spec=ServerRegistry),
        ):
            await context._init_mcp_components(True, ["ddg-search"])
        adapter.get_server_and_tool_info.assert_awaited_once_with(["ddg-search"])
        self.assertIn("search", context.mcp_prompt)
        self.assertIs(context.tool_manager.get_tool("search"), raw["search"])
        tool = context.tool_manager.get_formatted_tools("OpenAI")[0]["function"]
        self.assertEqual(tool["name"], "search")
        self.assertEqual(tool["parameters"]["required"], ["query"])
        self.assertIsNotNone(context.tool_executor)
        await context.close()

    async def test_discovery_failure_does_not_leave_a_partial_executor(self):
        context = ServiceContext()
        context.tool_adapter = Mock()
        context.tool_adapter.get_server_and_tool_info = AsyncMock(
            side_effect=RuntimeError("offline")
        )
        with patch(
            "src.open_llm_vtuber.service_context.ServerRegistry",
            return_value=Mock(spec=ServerRegistry),
        ):
            await context._init_mcp_components(True, ["ddg-search"])
        self.assertIsNone(context.tool_manager)
        self.assertIsNone(context.tool_executor)
        await context.close()
