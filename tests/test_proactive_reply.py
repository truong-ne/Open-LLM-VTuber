import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.agent.proactive_reply import (
    HOST_PREFIX,
    proactive_style,
    limit_proactive_reply,
    collect_proactive_reply,
)
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.vietnam_knowledge import PERSONA_MARKER


def host_input(style):
    text = HOST_PREFIX + "\n" + json.dumps({"live_context": {"style": style}})
    return BatchInput(texts=[TextData(TextSource.INPUT, text)])


class ProactiveReplyTests(unittest.IsolatedAsyncioTestCase):
    def agent(self, stream, messages=None):
        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._tts_preprocessor_config = None
        agent._live2d_model = Mock()
        agent._faster_first_response = False
        agent._segment_method = "regex"
        agent.reset_interrupt = Mock()
        agent._to_messages = Mock(return_value=messages or [])
        agent._use_mcpp = True
        agent._tool_manager = Mock()
        agent._system = PERSONA_MARKER
        agent._system_prompt = Mock(return_value=PERSONA_MARKER)
        agent._llm = SimpleNamespace(chat_completion=stream)
        agent._add_message = Mock()
        return agent

    async def test_short_turn_uses_speech_guard_even_when_mcp_is_enabled(self):
        async def stream(*args):
            yield "Mao chọn xanh ngọc. Bạn thích màu nào? Mao hỏi thêm nhé?"

        agent = self.agent(stream)
        raw_chat = inspect.unwrap(agent._chat_function_factory())
        result = [part async for part in raw_chat(host_input("initiative"))]
        self.assertEqual(result, ["Mao chọn xanh ngọc. Bạn thích màu nào?"])
        agent._add_message.assert_called_once_with(result[0], "assistant")
        self.assertEqual(proactive_style(host_input("support")), "support")

    async def test_current_database_persona_cannot_bypass_host_speech_limits(self):
        async def stream(*args):
            yield "[thought]Internal planning.</thought> Một. Hai. Ba. Bạn nghĩ sao?"

        agent = self.agent(stream)
        agent._system = "Hồ sơ Mao đang hoạt động từ PostgreSQL."
        raw_chat = inspect.unwrap(agent._chat_function_factory())
        result = [part async for part in raw_chat(host_input("chat"))]
        self.assertEqual(result, ["Một. Hai."])
        agent._add_message.assert_called_once_with("Một. Hai.", "assistant")

    async def test_empty_reply_retries_once_with_recent_context(self):
        calls = []

        async def stream(messages, system):
            calls.append(messages)
            yield (
                "[smirk]"
                if len(calls) == 1
                else "Mao thích xanh ngọc vì nhìn dịu mà nổi bật."
            )

        history = [{"role": "user", "content": f"old {i}"} for i in range(20)]
        agent = self.agent(stream, history)
        raw_chat = inspect.unwrap(agent._chat_function_factory())
        result = [part async for part in raw_chat(host_input("chat"))]
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(calls[1]), 4)
        self.assertEqual(calls[0], history)
        self.assertEqual(result, ["Mao thích xanh ngọc vì nhìn dịu mà nổi bật."])
        agent._add_message.assert_called_once()

    async def test_repeated_empty_reply_reports_error_instead_of_silent_success(self):
        calls = []

        async def stream(*args):
            calls.append(True)
            yield "[smirk]"

        agent = self.agent(stream)
        raw_chat = inspect.unwrap(agent._chat_function_factory())
        result = [part async for part in raw_chat(host_input("chat"))]
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]["code"], "empty-proactive-reply")
        agent._add_message.assert_not_called()

    def test_real_comments_and_requested_stories_are_not_shortened(self):
        for text in (
            "Kể chuyện dài cho mình nghe",
            '{"live_context":{"style":"chat"}}',
        ):
            self.assertIsNone(
                proactive_style(BatchInput(texts=[TextData(TextSource.INPUT, text)]))
            )
        self.assertIsNone(proactive_style(host_input("story")))
        self.assertEqual(proactive_style(host_input("chat")), "chat")

    def test_no_questions_escape_non_question_turns(self):
        text = "[tilt] Bạn chọn gì? Mình thích tông xanh. Bạn thấy sao?"
        for style in ("chat", "activity", "followup"):
            self.assertEqual(
                limit_proactive_reply(text, style), "Mình thích tông xanh."
            )

    def test_question_turn_stops_after_question_and_does_not_answer_for_viewers(self):
        self.assertEqual(
            limit_proactive_reply(
                "Mình thích xanh. Bạn chọn gì? Chắc bạn chọn hồng rồi.", "question"
            ),
            "Mình thích xanh. Bạn chọn gì?",
        )

    def test_bounds_stop_on_complete_sentences_without_cutting_mid_clause(self):
        self.assertEqual(
            limit_proactive_reply("Một. Hai. Ba. Bốn.", "chat"), "Một. Hai."
        )
        self.assertEqual(
            limit_proactive_reply("Một. Phần sau chưa nói hết", "chat"), "Một."
        )
        self.assertEqual(
            limit_proactive_reply("Đủ rồi. " + "dài " * 65 + ".", "chat"), "Đủ rồi."
        )

    def test_pose_decimals_and_trailing_body_command_survive(self):
        text = "[pose:right=0.6,left=0.2] Mình đổi tư thế một chút. [body:spin]"
        self.assertEqual(limit_proactive_reply(text, "activity"), text)
        # A dropped question must not leak its action into a different sentence.
        self.assertEqual(
            limit_proactive_reply("Xong rồi. [tilt] Bạn thấy sao? [body:spin]", "chat"),
            "Xong rồi.",
        )

    async def test_stream_is_closed_and_buffered_before_any_filtered_text_is_used(self):
        closed = []

        async def stream():
            try:
                yield "Mình thích "
                yield {"type": "text_delta", "text": "xanh. Bạn "}
                yield "chọn gì?"
            finally:
                closed.append(True)

        result = await collect_proactive_reply(stream(), "chat")
        self.assertEqual(result, "Mình thích xanh.")
        self.assertEqual(closed, [True])

    async def test_only_spoken_reply_enters_agent_memory(self):
        async def stream(*args):
            yield "[tilt] Bạn chọn gì? Mình thích xanh."

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._tts_preprocessor_config = None
        agent._live2d_model = Mock()
        agent._faster_first_response = False
        agent._segment_method = "regex"
        agent.reset_interrupt = Mock()
        agent._to_messages = Mock(return_value=[])
        agent._use_mcpp = False
        agent._tool_manager = None
        agent._system = PERSONA_MARKER
        agent._system_prompt = Mock(return_value=PERSONA_MARKER)
        agent._llm = SimpleNamespace(chat_completion=stream)
        agent._add_message = Mock()
        raw_chat = inspect.unwrap(agent._chat_function_factory())
        result = [part async for part in raw_chat(host_input("chat"))]
        self.assertEqual(result, ["Mình thích xanh."])
        agent._add_message.assert_called_once_with("Mình thích xanh.", "assistant")

    async def test_unbounded_model_output_cannot_grow_buffer_forever(self):
        count = 0

        async def stream():
            nonlocal count
            yield "Đủ rồi. "
            for _ in range(1000):
                count += 1
                yield "chưa kết thúc "

        self.assertEqual(await collect_proactive_reply(stream(), "chat"), "Đủ rồi.")
        self.assertLess(count, 200)
