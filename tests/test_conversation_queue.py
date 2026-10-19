import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import numpy as np

from src.open_llm_vtuber.conversations.conversation_handler import (
    handle_conversation_trigger,
    handle_individual_interrupt,
)
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.proxy_handler import ProxyHandler


class ConversationQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.context = SimpleNamespace(history_uid=None, agent_engine=Mock())
        self.ws = Mock(send_text=AsyncMock())
        self.groups = Mock()
        self.groups.get_client_group.return_value = None
        self.tasks = {}
        self.buffers = {"client": np.array([0.1, 0.2])}

    async def trigger(self, text=None):
        await handle_conversation_trigger(
            "text-input" if text is not None else "mic-audio-end",
            {"text": text} if text is not None else {},
            "client",
            self.context,
            self.ws,
            {},
            {},
            self.groups,
            self.buffers,
            self.tasks,
            AsyncMock(),
        )

    async def test_microphone_and_text_share_one_worker_without_memory_overlap(self):
        started, release = asyncio.Event(), asyncio.Event()
        order, running, peak = [], 0, 0

        async def process(**turn):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            value = turn["user_input"]
            order.append(value if isinstance(value, str) else value.tolist())
            if len(order) == 1:
                started.set()
                await release.wait()
            running -= 1

        with patch(
            "src.open_llm_vtuber.conversations.conversation_handler.process_single_conversation",
            process,
        ):
            await self.trigger("first")
            await started.wait()
            worker = self.tasks["client"]
            await self.trigger()
            await self.trigger("third")
            self.assertIs(self.tasks["client"], worker)
            self.assertEqual(order, ["first"])
            self.assertEqual(len(self.buffers["client"]), 0)
            release.set()
            await asyncio.wait_for(worker, 1)
        self.assertEqual(order, ["first", [0.1, 0.2], "third"])
        self.assertEqual(peak, 1)

    async def test_interrupt_finishes_cancellation_before_accepting_new_turn(self):
        started = asyncio.Event()
        order = []

        async def process(**turn):
            order.append(turn["user_input"])
            if turn["user_input"] == "old":
                started.set()
                await asyncio.Event().wait()

        with patch(
            "src.open_llm_vtuber.conversations.conversation_handler.process_single_conversation",
            process,
        ):
            await self.trigger("old")
            await started.wait()
            await self.trigger("stale queued input")
            old_worker = self.tasks["client"]
            await handle_individual_interrupt(
                "client", self.tasks, self.context, "heard"
            )
            self.assertTrue(old_worker.cancelled())
            await self.trigger("new")
            await asyncio.wait_for(self.tasks["client"], 1)
        self.assertEqual(order, ["old", "new"])

    async def test_failed_turn_releases_proxy_and_next_input_still_runs(self):
        order = []

        async def process(**turn):
            order.append(turn["user_input"])
            if len(order) == 1:
                raise RuntimeError("model unavailable")

        with patch(
            "src.open_llm_vtuber.conversations.conversation_handler.process_single_conversation",
            process,
        ):
            await self.trigger("first")
            await self.trigger("next")
            await asyncio.wait_for(self.tasks["client"], 1)
        self.assertEqual(order, ["first", "next"])
        self.assertEqual(
            json.loads(self.ws.send_text.call_args.args[0])["text"],
            "conversation-chain-end",
        )

    async def test_proxy_marks_direct_voice_start_busy_before_broadcast(self):
        proxy = ProxyHandler()
        proxy.connected = True
        messages = [
            SimpleNamespace(
                type=aiohttp.WSMsgType.TEXT,
                data=json.dumps({"type": "control", "text": text}),
            )
            for text in ("conversation-chain-start", "conversation-chain-end")
        ] + [SimpleNamespace(type=aiohttp.WSMsgType.CLOSED)]
        proxy.server_ws = Mock(closed=False, receive=AsyncMock(side_effect=messages))
        states = []

        async def broadcast(data):
            states.append(proxy.message_queue.conversation_active)

        proxy.broadcast_to_clients = broadcast
        await proxy.forward_server_messages()
        self.assertEqual(states, [True, False])

    async def test_clearing_tts_cancels_unfinished_generation(self):
        task = asyncio.create_task(asyncio.Event().wait())
        manager = TTSTaskManager()
        manager.task_list.append(task)
        manager.clear()
        await asyncio.sleep(0)
        self.assertTrue(task.cancelled())
