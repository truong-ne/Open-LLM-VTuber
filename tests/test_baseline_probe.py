import time
import unittest

from scripts.mao_baseline import TokenProbe
from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import AsyncLLM


class BaselineProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_instrumentation_preserves_native_tool_routing_and_timing(self):
        provider = AsyncLLM.__new__(AsyncLLM)
        calls = []

        async def completion(*args, **kwargs):
            calls.append(kwargs)
            yield ""
            yield {"type": "text_delta", "text": "Xin chào."}

        provider.chat_completion = completion
        probe = TokenProbe(provider)
        probe.marks, probe.started = {}, time.monotonic()
        self.assertIsInstance(probe, AsyncLLM)
        result = [
            item
            async for item in probe.chat_completion(
                [], "system", tools=[{"name": "test"}]
            )
        ]
        self.assertEqual(calls[0]["tools"], [{"name": "test"}])
        self.assertEqual(result[-1]["text"], "Xin chào.")
        self.assertGreaterEqual(probe.marks["first_token_ms"], 0)
