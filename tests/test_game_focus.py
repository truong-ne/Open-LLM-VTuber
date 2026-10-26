import unittest
from unittest.mock import AsyncMock

from src.open_llm_vtuber.live.vua_tieng_viet import VuaTiengViet, WordGameService
from src.open_llm_vtuber.proxy_handler import ProxyHandler


class GameFocusTests(unittest.IsolatedAsyncioTestCase):
    async def test_starting_game_interrupts_only_automatic_chatter(self):
        for source, interrupts in (("mao-idle-host", 1), ("youtube-live", 0)):
            service = WordGameService(VuaTiengViet())
            proxy = ProxyHandler(word_game=service)
            proxy._active_input_source = source
            proxy.forward_to_server = AsyncMock()
            proxy.broadcast_to_clients = AsyncMock()
            result = await service.submit("Lan", "!vuatiengviet", player_id="test")
            self.assertEqual(result, "started")
            self.assertEqual(proxy.forward_to_server.await_count, interrupts)
            if interrupts:
                proxy.forward_to_server.assert_awaited_once_with({"type": "interrupt-signal"})

    async def test_idle_turn_queued_before_game_does_not_reach_model(self):
        service = WordGameService(VuaTiengViet())
        service.game.submit("Lan", "!vuatiengviet", player_id="test")
        proxy = ProxyHandler(word_game=service)
        proxy.forward_to_server = AsyncMock()
        proxy.broadcast_to_clients = AsyncMock()
        proxy.message_queue.conversation_active = True
        for kind in ("user-input-transcription", "text-input"):
            await proxy.forward_with_broadcast({"type": kind, "source": "mao-idle-host", "text": "Old host topic"})
        proxy.forward_to_server.assert_not_awaited()
        proxy.broadcast_to_clients.assert_not_awaited()
        self.assertFalse(proxy.message_queue.conversation_active)

    def test_first_announcement_remains_the_clue_without_a_rules_intro(self):
        game = VuaTiengViet()
        game.submit("Lan", "!vuatiengviet", player_id="test")
        game.tick()
        announcement = game.announcements.popleft()
        self.assertEqual(announcement["kind"], "start")
        self.assertTrue(announcement["text"].startswith("Gợi ý 1:"))
        self.assertNotIn("luật", announcement["text"].lower())
