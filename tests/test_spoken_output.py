import unittest

from src.open_llm_vtuber.agent.spoken_output import SpokenOutputGuard, spoken_text


class SpokenOutputTests(unittest.TestCase):
    def test_internal_blocks_are_hidden_at_every_chunk_boundary(self):
        for hidden in (
            "<think>private analysis.</think>",
            "[thought]private analysis.</thought>",
            "[ analysis ]private analysis.[/analysis]",
            "<analysis>outer <think>inner</think> hidden</analysis>",
            '{"core":{"arousal":0.2},"channels":{"joy":0.4}}',
            '[{"core":{"arousal":0.2},"channels":{"joy":0.4}}]',
        ):
            text = hidden + "Mao nghe rồi."
            for split in range(len(text) + 1):
                with self.subTest(hidden=hidden, split=split):
                    guard = SpokenOutputGuard()
                    result = guard.feed(text[:split]) + guard.feed(
                        text[split:], final=True
                    )
                    self.assertEqual(result, "Mao nghe rồi.")
            guard = SpokenOutputGuard()
            result = "".join(guard.feed(char) for char in text) + guard.feed(
                "", final=True
            )
            self.assertEqual(result, "Mao nghe rồi.")

    def test_unclosed_reasoning_and_diagnostics_do_not_become_speech(self):
        for text in (
            "[thought]unfinished secret",
            "<think>unfinished",
            "[thought",
            "<thi",
            '{"core":{"arousal":0.2}',
        ):
            self.assertEqual(spoken_text(text), "")

    def test_actions_and_ordinary_json_are_preserved(self):
        for text in (
            "[joy] Mao nghe rồi.",
            "[pose:right=0.6,left=0.2] Đổi tư thế. [body:spin]",
            '{"color":"blue","quote":"a } brace"}',
            "Mao chọn [x] và số 0.2.",
        ):
            guard = SpokenOutputGuard()
            actual = "".join(guard.feed(char) for char in text) + guard.feed(
                "", final=True
            )
            self.assertEqual(actual, text)

    def test_structured_buffer_is_bounded_and_does_not_leak_on_overflow(self):
        guard = SpokenOutputGuard()
        self.assertEqual(guard.feed('{"core":"' + "secret" * 10000), "")
        self.assertLessEqual(len(guard.structured), 16384)
        self.assertEqual(guard.feed('"}Mao nghe rồi.', final=True), "Mao nghe rồi.")

    def test_unmarked_text_remains_streaming(self):
        guard = SpokenOutputGuard()
        self.assertEqual(guard.feed("Mao nghe "), "Mao nghe ")
        self.assertEqual(guard.feed("rồi."), "rồi.")


class SpokenPipelineTests(unittest.IsolatedAsyncioTestCase):
    def test_assistant_memory_keeps_spoken_text_but_user_content_is_not_filtered(self):
        from unittest.mock import Mock
        from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._memory = []
        agent._enforce_memory_limit = Mock()
        agent._add_message("[thought]Private plan.</thought>Mao nghe rồi.", "assistant")
        self.assertEqual(agent._memory[-1]["content"], "Mao nghe rồi.")
        user_text = 'Giải thích nhãn [thought] và JSON {"arousal":0.2}.'
        agent._add_message(user_text, "user")
        self.assertEqual(agent._memory[-1]["content"], user_text)

    async def test_stream_filter_runs_before_subtitles_and_tts_and_preserves_tool_events(
        self,
    ):
        from types import SimpleNamespace
        from src.open_llm_vtuber.agent.transformers import (
            sentence_divider,
            actions_extractor,
            display_processor,
            tts_filter,
        )
        from src.open_llm_vtuber.agent.output_types import SentenceOutput
        from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig

        model = SimpleNamespace(
            extract_emotion=lambda text: [],
            context_motions_for_sentence=lambda text: [],
            remove_context_motion_tags=lambda text: text,
        )
        tool_event = {"type": "tool_call_status", "status": "completed"}

        @tts_filter(
            TTSPreprocessorConfig(
                remove_special_char=True,
                translator_config={
                    "translate_audio": False,
                    "translate_provider": "deeplx",
                },
            )
        )
        @display_processor()
        @actions_extractor(model)
        @sentence_divider(faster_first_response=False, segment_method="regex")
        async def stream():
            yield "[tho"
            yield tool_event
            yield {"type": "text_delta", "text": "ught]Secret analysis.</thought>"}
            for char in '{"core":{"arousal":0.2},"channels":{"joy":0.4}}Mao nghe rồi.':
                yield char

        results = [item async for item in stream()]
        self.assertIn(tool_event, results)
        speech = [item for item in results if isinstance(item, SentenceOutput)]
        self.assertEqual(" ".join(item.tts_text for item in speech), "Mao nghe rồi.")
        self.assertEqual(
            " ".join(item.display_text.text for item in speech), "Mao nghe rồi."
        )
