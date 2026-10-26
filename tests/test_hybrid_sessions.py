import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.service_context import ServiceContext
from src.open_llm_vtuber.websocket_handler import WebSocketHandler


class HybridSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_forks_mutable_agent_but_keeps_stateless_model_shared(self):
        model = Mock()
        base = BasicMemoryAgent(model, "core persona", Mock(), segment_method="regex")
        settings = SimpleNamespace(use_mcpp=False, mcp_enabled_servers=[])
        character = SimpleNamespace(
            agent_config=SimpleNamespace(
                agent_settings=SimpleNamespace(basic_memory_agent=settings)
            )
        )
        a, b = ServiceContext(), ServiceContext()
        for context in (a, b):
            await context.load_cache(
                config=Mock(),
                system_config=Mock(),
                character_config=character,
                live2d_model=Mock(),
                asr_engine=Mock(),
                tts_engine=Mock(),
                vad_engine=Mock(),
                agent_engine=base,
                translate_engine=None,
            )
        self.assertIsNot(a.agent_engine, b.agent_engine)
        self.assertIs(a.agent_engine._llm, model)
        a.agent_engine._add_message("private working turn", "user")
        self.assertEqual(b.agent_engine._memory, [])
        self.assertEqual(base._memory, [])
        self.assertEqual(a.agent_engine._system.count("If you received"), 1)
        with patch.object(a.agent_engine, "close", new_callable=AsyncMock) as close:
            await a.close()
            close.assert_awaited_once()
        await b.close()
        await base.close()

    async def test_disconnect_closes_context_after_cancelling_current_work(self):
        handler = WebSocketHandler.__new__(WebSocketHandler)
        context = SimpleNamespace(close=AsyncMock())
        handler.client_contexts = {"client": context}
        handler.client_connections = {"client": Mock()}
        handler.received_data_buffers = {"client": []}
        handler.chat_group_manager = SimpleNamespace(
            get_client_group=Mock(return_value=None), client_group_map={}
        )
        task = asyncio.create_task(asyncio.Event().wait())
        handler.current_conversation_tasks = {"client": task}
        await asyncio.sleep(0)
        with (
            patch(
                "src.open_llm_vtuber.websocket_handler.handle_client_disconnect",
                new_callable=AsyncMock,
            ),
            patch(
                "src.open_llm_vtuber.websocket_handler.message_handler.cleanup_client"
            ),
        ):
            await handler.handle_disconnect("client")
        self.assertTrue(task.cancelled())
        context.close.assert_awaited_once()
        self.assertNotIn("client", handler.client_contexts)

    async def test_failed_connection_releases_its_context(self):
        handler = WebSocketHandler.__new__(WebSocketHandler)
        context = SimpleNamespace(close=AsyncMock())
        handler.client_contexts = {"client": context}
        handler.client_connections = {}
        handler.received_data_buffers = {}
        handler.current_conversation_tasks = {}
        handler.chat_group_manager = SimpleNamespace(client_group_map={})
        with patch(
            "src.open_llm_vtuber.websocket_handler.message_handler.cleanup_client"
        ):
            await handler._cleanup_failed_connection("client")
        context.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
