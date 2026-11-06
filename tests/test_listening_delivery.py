import inspect
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from src.open_llm_vtuber.dialogue.listening import (
    limit_listening_reply,
    collect_listening_reply,
)
from src.open_llm_vtuber.dialogue.intent import ResponsePlan
from src.open_llm_vtuber.dialogue.recall import quoted_recall
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
import test_runtime_architecture as architecture


class ListeningDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def test_questions_and_invitations_are_removed_before_speech(self):
        self.assertEqual(
            limit_listening_reply("Ngày hôm nay nhiều việc thật. Kể tiếp đi, papa."),
            "Ngày hôm nay nhiều việc thật.",
        )
        self.assertEqual(limit_listening_reply("Papa muốn kể gì? Hãy kể đi."), "Ừm.")
        self.assertEqual(
            limit_listening_reply("[concern] Nghe mệt thật. [body:spin] Kể tiếp đi."),
            "[concern] Nghe mệt thật.",
        )

    async def test_buffer_closes_stream_and_does_not_swallow_provider_error(self):
        closed = []

        async def stream():
            try:
                yield "Kể tiếp "
                yield "đi."
            finally:
                closed.append(True)

        self.assertEqual(await collect_listening_reply(stream()), "Ừm.")
        self.assertEqual(closed, [True])

        async def error():
            yield {"type": "error", "message": "offline"}

        with self.assertRaises(RuntimeError):
            await collect_listening_reply(error())

    async def test_live_agent_uses_speech_only_guard_and_saves_only_kept_text(self):
        calls = []

        async def completion(messages, system, tools=None):
            calls.append(tools)
            yield "Một ngày khá nặng nề. Kể tiếp đi, papa."

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._hybrid = SimpleNamespace(
            prepare=AsyncMock(),
            persona_changed=False,
            interaction=None,
            direct_reply=None,
            dialogue_plan=ResponsePlan("listen"),
        )
        agent._tts_preprocessor_config = None
        agent._live2d_model = Mock()
        agent._faster_first_response = False
        agent._segment_method = "regex"
        agent.reset_interrupt = Mock()
        agent._to_messages = Mock(return_value=[])
        agent._system_prompt = Mock(return_value="Mao profile")
        agent._llm = SimpleNamespace(chat_completion=completion)
        agent._add_message = Mock()
        chat = inspect.unwrap(agent._chat_function_factory())
        result = [
            part
            async for part in chat(
                BatchInput([TextData(TextSource.INPUT, "Chỉ muốn kể thôi")])
            )
        ]
        self.assertEqual(result, ["Một ngày khá nặng nề."])
        self.assertEqual(calls, [None])
        agent._add_message.assert_called_once_with(result[0], "assistant")


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class QuoteProvenanceTests(unittest.TestCase):
    setUp = architecture.ArchitectureDatabaseTests.setUp
    tearDown = architecture.ArchitectureDatabaseTests.tearDown
    event = architecture.ArchitectureDatabaseTests.event

    def test_operator_revision_is_not_misquoted_as_user_speech(self):
        event, _ = self.event("Biệt danh bí mật papa dùng là BAMBOO_731.")
        item = self.repo.add_item(event.event_id, event.content)
        view = self.repo.context("room", "person-a", "private")
        self.assertTrue(view["items"][0]["exact_user_quote"])
        self.assertIn(
            "BAMBOO_731", quoted_recall("Biệt danh bí mật papa đã nói là gì?", view)
        )
        self.repo.revise_item(item, 1, "Biệt danh bí mật đã được sửa thành LOTUS_42.")
        view = self.repo.context("room", "person-a", "private")
        self.assertFalse(view["items"][0]["exact_user_quote"])
        self.assertIsNone(quoted_recall("Biệt danh bí mật papa đã nói là gì?", view))
