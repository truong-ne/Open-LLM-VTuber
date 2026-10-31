import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText, SentenceOutput
from src.open_llm_vtuber.dialogue.engine import DialogueEngine
from src.open_llm_vtuber.interaction.events import DeliveryTracker, current_delivery


def sentence(text):
    return SentenceOutput(DisplayText(text), text, Actions())


class Agent:
    _use_mcpp = False

    def __init__(self, attempts):
        self.attempts = attempts
        self.calls = 0
        self.closed = 0

    async def chat(self, data):
        items = self.attempts[self.calls]
        self.calls += 1
        try:
            for item in items:
                yield item
        finally:
            self.closed += 1


class DialogueDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_bundled_desktop_audio_events_complete_the_server_delivery_tracker(
        self,
    ):
        import json
        import os
        import subprocess
        from pathlib import Path

        tracker = DeliveryTracker()
        packet = tracker.segment("Mao nghe rồi.")
        process = await asyncio.to_thread(
            subprocess.run,
            ["node", "tests/test_mao_desktop_runtime.mjs", "--delivery-receipts"],
            cwd=Path(__file__).resolve().parents[1],
            env={
                **os.environ,
                "MAO_TEST_TURN": packet["turn_id"],
                "MAO_TEST_EPOCH": packet["generation_epoch"],
                "MAO_TEST_SEGMENT": packet["segment_id"],
            },
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        for receipt in json.loads(process.stdout.strip().splitlines()[-1]):
            self.assertTrue(tracker.ack(receipt))
        self.assertEqual(tracker.finish(), "completed")

    async def test_silent_or_symbol_only_stream_retries_once_without_double_speech(
        self,
    ):
        for first in ([], [sentence("  ")], [sentence("😊…")]):
            agent = Agent([first, [sentence("Mao nghe rồi.")]])
            trace = DeliveryTracker()
            token = current_delivery.set(trace)
            try:
                result = [item async for item in DialogueEngine(agent, {}).chat(None)]
            finally:
                current_delivery.reset(token)
            self.assertEqual([item.tts_text for item in result], ["Mao nghe rồi."])
            self.assertEqual(agent.calls, 2)
            self.assertEqual(agent.closed, 2)
            self.assertEqual(trace.metrics["empty_reply_retries"], 1)

    async def test_two_silent_attempts_emit_error_and_delivery_is_failed(self):
        agent = Agent([[], []])
        result = [item async for item in DialogueEngine(agent, {}).chat(None)]
        self.assertEqual(result[0]["code"], "empty-agent-reply")
        tracker = DeliveryTracker()
        from src.open_llm_vtuber.interaction.service import TurnSession

        turn = SimpleNamespace(
            delivery=tracker, event=SimpleNamespace(visibility="test")
        )
        import json

        await TurnSession.send(turn, json.dumps(result[0]), AsyncMock())
        self.assertEqual(tracker.finish(), "failed")
        self.assertEqual(agent.closed, 2)

    async def test_tool_enabled_or_tool_event_turn_is_never_replayed(self):
        agent = Agent([[]])
        agent._use_mcpp = True
        result = [item async for item in DialogueEngine(agent, {}).chat(None)]
        self.assertEqual(agent.calls, 1)
        self.assertEqual(result[-1]["code"], "empty-agent-reply")
        agent = Agent([[{"type": "tool_call_status", "status": "completed"}]])
        result = [item async for item in DialogueEngine(agent, {}).chat(None)]
        self.assertEqual(agent.calls, 1)
        self.assertEqual(result[-1]["code"], "empty-agent-reply")

    async def test_partial_spoken_answer_and_provider_error_are_not_replayed(self):
        for items in ([sentence("Một câu.")], [{"type": "error", "code": "provider"}]):
            agent = Agent([items])
            result = [item async for item in DialogueEngine(agent, {}).chat(None)]
            self.assertEqual(result, items)
            self.assertEqual(agent.calls, 1)

    async def test_sentence_cap_closes_stream_without_retry(self):
        agent = Agent([[sentence("Một.") for _ in range(5)]])
        result = [
            item
            async for item in DialogueEngine(
                agent, {"settings": {"verbosity": "brief"}}
            ).chat(None)
        ]
        self.assertEqual(len(result), 3)
        self.assertEqual(agent.closed, 1)
        self.assertEqual(agent.calls, 1)

    async def test_cancellation_closes_stream_without_retry_or_error(self):
        started = asyncio.Event()

        class WaitingAgent(Agent):
            async def chat(self, data):
                self.calls += 1
                try:
                    started.set()
                    await asyncio.Event().wait()
                    yield sentence("late")
                finally:
                    self.closed += 1

        agent = WaitingAgent([])

        async def consume():
            return [item async for item in DialogueEngine(agent, {}).chat(None)]

        task = asyncio.create_task(consume())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(agent.calls, 1)
        self.assertEqual(agent.closed, 1)

    async def test_actual_tag_and_tts_pipeline_recovers_from_expression_only_reply(
        self,
    ):
        from test_proactive_reply import ProactiveReplyTests
        from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig
        from src.open_llm_vtuber.agent.input_types import (
            BatchInput,
            TextData,
            TextSource,
        )

        calls = []

        async def completion(*args, **kwargs):
            calls.append(kwargs)
            yield "[joy] 😊" if len(calls) == 1 else "Mao nghe rồi."

        agent = ProactiveReplyTests().agent(completion)
        from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import (
            AsyncLLM,
        )

        agent._use_mcpp = True
        agent._formatted_tools_openai = [
            {"type": "function", "function": {"name": "mao_hybrid"}}
        ]
        agent._tool_executor = Mock()
        agent._llm = AsyncLLM.__new__(AsyncLLM)
        agent._llm.chat_completion = completion
        agent._live2d_model = SimpleNamespace(
            extract_emotion=lambda text: [],
            context_motions_for_sentence=lambda text: [],
            remove_context_motion_tags=lambda text: text,
        )
        agent._tts_preprocessor_config = TTSPreprocessorConfig(
            remove_special_char=True,
            translator_config={
                "translate_audio": False,
                "translate_provider": "deeplx",
            },
        )
        data = BatchInput([TextData(TextSource.INPUT, "Cảm ơn Mao.")])
        result = [item async for item in DialogueEngine(agent, {}).chat(data)]
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]["tools"])
        self.assertNotIn("tools", calls[1])
        agent._tool_executor.execute_tools.assert_not_called()
        self.assertEqual(len(result), 1)
        self.assertIn("Mao nghe", result[0].tts_text)

    async def test_recovery_does_not_replay_an_agent_that_already_executed_a_tool(self):
        class RecoverableAgent(Agent):
            _use_mcpp = True

            def recover_silent_reply(self, data):
                raise AssertionError("Must not replay a turn with tool events")

        agent = RecoverableAgent(
            [[{"type": "tool_call_status", "status": "completed"}]]
        )
        result = [item async for item in DialogueEngine(agent, {}).chat(None)]
        self.assertEqual(agent.calls, 1)
        self.assertEqual(result[-1]["code"], "empty-agent-reply")
