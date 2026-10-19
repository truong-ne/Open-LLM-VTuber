import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.conversations.conversation_utils import (
    finalize_conversation_turn,
)
from src.open_llm_vtuber.message_handler import message_handler
from src.open_llm_vtuber.proxy_handler import ProxyHandler


class SpeechRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_immediate_frontend_ack_is_not_lost_and_marker_is_sent_once(self):
        manager = Mock(task_list=[object()], wait_for_completion=AsyncMock())
        sent = []

        async def send(raw):
            data = json.loads(raw)
            sent.append(data)
            if data.get("type") == "backend-synth-complete":
                message_handler.handle_message(
                    "test-speaker", {"type": "frontend-playback-complete"}
                )

        await finalize_conversation_turn(manager, send, "test-speaker")
        manager.wait_for_completion.assert_awaited_once()
        self.assertEqual(
            sum(m.get("type") == "backend-synth-complete" for m in sent), 1
        )
        self.assertEqual(
            sent[-1], {"type": "control", "text": "conversation-chain-end"}
        )

    async def test_missing_ack_still_releases_conversation(self):
        manager = Mock(task_list=[object()], wait_for_completion=AsyncMock())
        send = AsyncMock()
        with patch.object(
            message_handler, "wait_for_response", new=AsyncMock(return_value=None)
        ) as wait:
            await finalize_conversation_turn(manager, send, "no-player")
        self.assertEqual(wait.call_args.kwargs["timeout"], 60)
        self.assertEqual(
            json.loads(send.call_args.args[0])["text"], "conversation-chain-end"
        )

    async def test_silent_audio_payload_is_forwarded_without_len_none_error(self):
        proxy = ProxyHandler()
        client = Mock(send_json=AsyncMock())
        proxy.clients["desktop"] = client
        payload = {"type": "audio", "audio": None, "volumes": None}
        await proxy.broadcast_to_clients(payload)
        client.send_json.assert_awaited_once_with(payload)


if __name__ == "__main__":
    unittest.main()
