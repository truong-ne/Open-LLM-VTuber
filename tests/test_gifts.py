import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase
from unittest.mock import Mock

from src.open_llm_vtuber.live.gifts import GiftStore, GiftService
from src.open_llm_vtuber.live.tiktok_live import TikTokLivePlatform
from src.open_llm_vtuber.interaction.ingress import verify_host_proposal


class GiftTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "gifts.db"
        self.store = GiftStore(self.path)

    def test_coin_value_ranking_dedup_restart_and_accounts(self):
        self.assertTrue(self.store.record("@mao", "one", "a", "Lan", "Rose", 10, 1))
        self.assertFalse(self.store.record("@mao", "one", "a", "Lan", "Rose", 10, 1))
        self.store.record("@mao", "two", "b", "Minh", "Gift", 1, 100)
        self.store.record("@mao", "three", "a", "Lan mới", "Rose", 5, 1)
        self.store.record("@other", "one", "c", "An", "Gift", 100, 100)
        board = GiftStore(self.path).snapshot("@MAO")
        self.assertEqual(board["total_coins"], 115)
        self.assertEqual(board["total_gifts"], 16)
        self.assertEqual(
            [(r["nickname"], r["coins"]) for r in board["leaderboard"]],
            [("Minh", 100), ("Lan mới", 15)],
        )
        self.assertNotIn("player_id", str(board))
        self.assertFalse(self.store.record("@mao", "bad", "a", "Lan", "Rose", -1, 5))
        self.assertFalse(self.store.record("@mao", "bad", "a", "Lan", "Rose", 1, -5))

    def test_combo_is_counted_once_at_completion_even_with_new_message_ids(self):
        client = TikTokLivePlatform.__new__(TikTokLivePlatform)
        client.classroom_only = False
        client._gifts = self.store
        client._unique_id = "@mao"
        client._client = NS(room_id="room")
        client._is_new_event = Mock(return_value=True)
        client._write_health = Mock()
        event = NS(
            streaking=True,
            user=NS(id=3, nickname="Lan"),
            gift=NS(id=1, type=1, name="Rose", diamond_count=2),
            common=NS(msg_id=100),
            group_id=99,
            repeat_count=10,
        )
        self.assertFalse(client._accept_gift(event))
        event.streaking = False
        self.assertTrue(client._accept_gift(event))
        event.common.msg_id = 101
        self.assertFalse(client._accept_gift(event))
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 20)
        event.gift.type = 2
        event.group_id = 0
        event.common.msg_id = 102
        event.repeat_count = 1
        self.assertTrue(client._accept_gift(event))
        client._is_new_event.return_value = False
        event.common.msg_id = 103
        self.assertFalse(client._accept_gift(event))
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 22)

    def test_later_combo_total_replaces_previous_count_without_double_counting(self):
        key = "room:combo:123:a:rose"
        self.store.record("@mao", key, "a", "Lan", "Rose", 1, 1)
        self.store.announced("@mao", key)
        self.assertTrue(self.store.record("@mao", key, "a", "Lan", "Rose", 3, 1))
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 3)
        self.assertFalse(self.store.record("@mao", key, "a", "Lan", "Rose", 3, 1))
        self.assertFalse(self.store.record("@mao", key, "a", "Lan", "Rose", 2, 1))
        self.assertIsNotNone(self.store.pending("@mao"))

    def test_screenshot_reconciliation_is_idempotent_and_late_events_consume_gap(self):
        key = "room:combo:123:a:rose"
        self.store.record("@mao", key, "a", "Lan", "Rose", 1, 1, now=10)
        self.assertTrue(
            self.store.reconcile_room_total(
                "@mao", "room", "a", "Lan", 3, "screenshot", cutoff=20
            )
        )
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 3)
        self.assertFalse(
            self.store.reconcile_room_total(
                "@mao", "room", "a", "Lan", 3, "screenshot", cutoff=25
            )
        )
        self.store.record("@mao", key, "a", "Lan", "Rose", 3, 1, now=30)
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 3)
        self.store.record("@mao", "room:msg:new", "a", "Lan", "Rose", 1, 1, now=30)
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 4)
        self.assertEqual(self.store.snapshot("@other")["total_coins"], 0)
        self.assertEqual(GiftStore(self.path).snapshot("@mao")["total_coins"], 4)

    def test_thank_you_is_signed_prioritized_once_and_queue_failure_retries(self):
        self.store.record("@mao", "one", "a", "Lan", "Hoa hồng", 3, 5)
        queue = NS(
            external_busy=False,
            conversation_active=True,
            message_queue=[],
            queue_message=Mock(return_value=False),
        )
        proxy = NS(
            connected=True,
            clients={"desktop": True},
            message_queue=queue,
            word_game=None,
            singing=None,
        )
        service = GiftService(lambda: proxy, lambda: "@mao", self.store)
        self.assertFalse(service.dispatch_once())
        self.assertIsNotNone(self.store.pending("@mao"))
        queue.queue_message.return_value = True
        self.assertTrue(service.dispatch_once())
        message = queue.queue_message.call_args.args[0]
        self.assertTrue(verify_host_proposal(message))
        self.assertIn("Lan", message["narration_speech"])
        self.assertIn("15 coin", message["narration_speech"])
        self.assertTrue(queue.queue_message.call_args.kwargs["priority"])
        self.assertFalse(service.dispatch_once())
        message["narration_speech"] = "forged"
        self.assertFalse(verify_host_proposal(message))

    def test_disconnected_and_game_wait_without_losing_totals(self):
        self.store.record("@mao", "one", "a", "Lan", "Rose", 1, 1)
        proxy = NS(connected=False, clients={"desktop": True})
        service = GiftService(lambda: proxy, lambda: "@mao", self.store)
        self.assertFalse(service.dispatch_once())
        proxy.connected = True
        proxy.message_queue = NS(
            external_busy=False, conversation_active=False, message_queue=[]
        )
        proxy.word_game = NS(game=NS(active=True))
        proxy.singing = None
        self.assertFalse(service.dispatch_once())
        self.assertIsNotNone(self.store.pending("@mao"))
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 1)

    def test_old_gifts_stay_ranked_without_spoken_replay(self):
        self.store.record("@mao", "one", "a", "Lan", "Rose", 1, 1, now=1)
        self.assertIsNone(self.store.pending("@mao", now=1000))
        self.assertEqual(self.store.snapshot("@mao")["total_coins"], 1)
