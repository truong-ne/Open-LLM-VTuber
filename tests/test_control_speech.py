import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from src.open_llm_vtuber.dialogue.control_speech import (
    limit_control_reply,
    collect_control_reply,
)
from src.open_llm_vtuber.dialogue.intent import ResponsePlan
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from scripts.mao_dialogue_eval import response_flags


class ControlSpeechTests(unittest.IsolatedAsyncioTestCase):
    def test_resume_keeps_one_ack_and_drops_autobiography(self):
        raw = "Được, tiếp tục nhé. Mao là một AI VTuber và chưa có ký ức cá nhân. Bạn muốn gì?"
        self.assertEqual(limit_control_reply(raw, "resume"), "Được, tiếp tục nhé.")
        self.assertEqual(
            limit_control_reply("Mao là một AI. Bạn muốn gì?", "quiet"), "Được rồi."
        )
        self.assertEqual(
            limit_control_reply(
                "[calm] Được rồi. [body:spin] Mao là AI VTuber.", "quiet"
            ),
            "[calm] Được rồi.",
        )
        with self.assertRaises(ValueError):
            limit_control_reply(raw, "answer")

    def test_vietnamese_ai_is_not_confused_with_the_AI_acronym(self):
        self.assertNotIn(
            "unrequested_system_explanation",
            response_flags("Anh không cần phải là ai đó hoàn hảo.", {}),
        )
        self.assertIn(
            "unrequested_system_explanation", response_flags("Mao là một AI.", {})
        )

    async def test_error_does_not_become_successful_acknowledgement(self):
        closed = []

        async def stream():
            try:
                yield {"type": "error"}
            finally:
                closed.append(True)

        with self.assertRaises(RuntimeError):
            await collect_control_reply(stream(), "resume")
        self.assertEqual(closed, [True])

    async def test_agent_control_modes_do_not_send_raw_introduction_to_tts_or_memory(
        self,
    ):
        for mode in ("quiet", "resume"):
            calls = []

            async def completion(messages, system, tools=None):
                calls.append(tools)
                yield "Được, tiếp tục nhé. Mao là AI VTuber, không có cơ thể sinh học."

            agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
            agent._hybrid = SimpleNamespace(
                prepare=AsyncMock(),
                persona_changed=False,
                interaction=None,
                direct_reply=None,
                dialogue_plan=ResponsePlan(mode),
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
                    BatchInput([TextData(TextSource.INPUT, "Mao nói tiếp đi")])
                )
            ]
            self.assertEqual(result, ["Được, tiếp tục nhé."])
            self.assertEqual(calls, [None])
            agent._add_message.assert_called_once_with(result[0], "assistant")
