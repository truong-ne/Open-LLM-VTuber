import json
import unittest
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI

from src.open_llm_vtuber.agent.stateless_llm_factory import LLMFactory
from src.open_llm_vtuber.config_manager.stateless_llm import OllamaConfig


class OllamaThinkingTests(unittest.IsolatedAsyncioTestCase):
    async def test_thinking_setting_reaches_serialized_streaming_request(self):
        for think in (False, True, None):
            with self.subTest(think=think):
                bodies = []

                def respond(request):
                    bodies.append(json.loads(request.content))
                    chunk = {
                        "id": "chat-test",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": "mao-companion",
                        "choices": [{"index": 0, "delta": {"content": "Chào bạn!"}}],
                    }
                    return httpx.Response(
                        200,
                        headers={"content-type": "text/event-stream"},
                        content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n",
                    )

                def make_client(**kwargs):
                    return AsyncOpenAI(
                        **kwargs,
                        http_client=httpx.AsyncClient(
                            transport=httpx.MockTransport(respond)
                        ),
                    )

                config = OllamaConfig(
                    base_url="http://ollama.test/v1",
                    model="mao-companion",
                    think=think,
                    unload_at_exit=False,
                )
                with (
                    patch(
                        "src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm.AsyncOpenAI",
                        side_effect=make_client,
                    ),
                    patch(
                        "src.open_llm_vtuber.agent.stateless_llm.ollama_llm.requests.post"
                    ),
                ):
                    llm = LLMFactory.create_llm("ollama_llm", **config.model_dump())
                try:
                    answer = "".join(
                        [
                            part
                            async for part in llm.chat_completion(
                                [{"role": "user", "content": "Hi Mao"}], "Persona"
                            )
                        ]
                    )
                finally:
                    await llm.client.close()
                self.assertEqual(answer, "Chào bạn!")
                self.assertTrue(bodies[0]["stream"])
                self.assertEqual(bodies[0]["messages"][0]["role"], "system")
                if think is None:
                    self.assertNotIn("reasoning_effort", bodies[0])
                else:
                    self.assertEqual(
                        bodies[0]["reasoning_effort"], "medium" if think else "none"
                    )
                self.assertNotIn(
                    "think", bodies[0], "native-only field is ignored on /v1"
                )
