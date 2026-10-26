import json
import unittest
from unittest.mock import patch

import httpx
from loguru import logger
from openai import AsyncOpenAI

from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import AsyncLLM


class ToolLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_tool_argument_reaches_executor_without_leaking_to_logs(self):
        secret = "synthetic-private-form-text-123"

        def respond(request):
            chunk = {
                "id": "test",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "test",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call-test",
                                    "type": "function",
                                    "function": {
                                        "name": "mao_hybrid",
                                        "arguments": json.dumps(
                                            {
                                                "operation": "computer",
                                                "data": {
                                                    "action": "fill",
                                                    "text": secret,
                                                },
                                            }
                                        ),
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n",
            )

        def make_client(**kwargs):
            return AsyncOpenAI(
                **kwargs,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
            )

        logs = []
        sink = logger.add(lambda message: logs.append(str(message)), level="TRACE")
        try:
            with patch(
                "src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm.AsyncOpenAI",
                side_effect=make_client,
            ):
                model = AsyncLLM(model="test", base_url="http://local.test/v1")
            output = [
                part
                async for part in model.chat_completion(
                    [{"role": "user", "content": secret}], "persona"
                )
            ]
            self.assertTrue(
                any(
                    isinstance(part, list) and secret in part[0].function.arguments
                    for part in output
                )
            )
            self.assertNotIn(secret, "".join(logs))
        finally:
            logger.remove(sink)
            await model.client.close()
