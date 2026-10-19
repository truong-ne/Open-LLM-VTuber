import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from src.open_llm_vtuber.live.youtube_creators import (
    YouTubeCreatorLookup,
    channel_profile,
    subscriber_count,
    MIXIGAMING_CHANNEL,
)
from src.open_llm_vtuber.live.youtube_live import YouTubeLivePlatform
from src.open_llm_vtuber.live.idle_host import ChatActivity
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent

CHANNEL = "UC" + "a" * 22
OTHER = "UC" + "b" * 22


def page(count="12.3K subscribers", ident=CHANNEL, *, modern=True):
    header = (
        {
            "pageHeaderRenderer": {
                "content": {
                    "pageHeaderViewModel": {
                        "metadata": {
                            "contentMetadataViewModel": {
                                "metadataRows": [
                                    {
                                        "metadataParts": [
                                            {"text": {"content": count}},
                                            {"text": {"content": "50K videos"}},
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
        if modern
        else {"c4TabbedHeaderRenderer": {"subscriberCountText": {"simpleText": count}}}
    )
    data = {
        "metadata": {
            "channelMetadataRenderer": {
                "externalId": ident,
                "title": "MixiGaming",
                "description": "999M subscribers",
            }
        },
        "header": header,
    }
    return "var ytInitialData = " + json.dumps(data) + ";"


class CreatorParsingTests(unittest.TestCase):
    def test_only_subscriber_labels_and_strict_threshold(self):
        for label, expected in (
            ("12.3K subscribers", 12300),
            ("8.38M subscribers", 8380000),
            ("10,001 subscribers", 10001),
            ("10K subscribers", 10000),
            ("9.99K subscribers", 9990),
            ("1 subscriber", 1),
        ):
            self.assertEqual(subscriber_count(label), expected)
        for label in (
            "1M views",
            "20K videos",
            "hidden",
            "1e6 subscribers",
            "-30K subscribers",
            "100K",
            None,
        ):
            self.assertIsNone(subscriber_count(label))

    def test_header_identity_hidden_counts_and_display_name_impersonation(self):
        profile = channel_profile(page(), CHANNEL)
        self.assertEqual(profile["subscriber_count_lower_bound"], 12300)
        self.assertFalse(
            profile["is_mixi"], "display name must not identify MixiGaming"
        )
        self.assertEqual(
            channel_profile(page(modern=False), CHANNEL)[
                "subscriber_count_lower_bound"
            ],
            12300,
        )
        self.assertIsNone(channel_profile(page(ident=OTHER), CHANNEL))
        self.assertIsNone(channel_profile(page("subscribers hidden"), CHANNEL))
        self.assertIsNone(channel_profile(page(), "@MixiGaming"))
        self.assertTrue(
            channel_profile(page(ident=MIXIGAMING_CHANNEL), MIXIGAMING_CHANNEL)[
                "is_mixi"
            ]
        )


class CreatorLookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_channel_url_and_cached_counts_avoid_per_comment_requests(self):
        clock = Mock(return_value=0)
        lookup = YouTubeCreatorLookup(clock=clock)
        response = httpx.Response(
            200, text=page(), request=httpx.Request("GET", "https://www.youtube.com")
        )
        with patch(
            "httpx.AsyncClient.get", new=AsyncMock(return_value=response)
        ) as get:
            for _ in range(5):
                self.assertIsNotNone(await lookup.lookup(CHANNEL))
            get.assert_awaited_once()
            self.assertEqual(
                get.call_args.args[0], f"https://www.youtube.com/channel/{CHANNEL}"
            )
            clock.return_value = 3601
            await lookup.lookup(CHANNEL)
            self.assertEqual(get.await_count, 2)
            self.assertIsNone(await lookup.lookup("https://evil.example/file"))
            self.assertEqual(get.await_count, 2)

    async def test_failures_are_unknown_and_negative_cached(self):
        lookup = YouTubeCreatorLookup()
        with patch(
            "httpx.AsyncClient.get",
            new=AsyncMock(side_effect=httpx.ConnectError("offline")),
        ) as get:
            self.assertIsNone(await lookup.lookup(CHANNEL))
            self.assertIsNone(await lookup.lookup(CHANNEL))
            get.assert_awaited_once()


class CreatorWelcomeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.lookup = Mock(
            lookup=AsyncMock(return_value=channel_profile(page(), CHANNEL))
        )
        self.reader = YouTubeLivePlatform(
            "@sejuly-02",
            creator_lookup=self.lookup,
            status_path=root / "status.json",
            comment_state_path=root / "comments.db",
            activity=ChatActivity(root / "activity.json"),
            batch_window=0,
        )
        self.reader._listen_started_at = time.time() - 1
        self.reader._connected = self.reader._state_known = True
        self.reader._websocket = Mock(closed=False, send=AsyncMock())

    def event(self, ident="one", channel=CHANNEL, **extra):
        return {
            "message_id": ident,
            "message_type": "text_message",
            "timestamp": time.time(),
            "message": "Hi Mao, mình có một triệu sub!",
            "author": {"id": channel, "name": "Khách"},
            **extra,
        }

    async def test_check_is_off_the_ingest_path_wow_is_verified_and_once_per_channel(
        self,
    ):
        event = self.event()
        await self.reader.ingest(event, "abcdefghijk")
        self.lookup.lookup.assert_not_awaited()
        self.assertEqual(len(self.reader._pending), 1)
        await self.reader.check_creator_once()
        self.assertEqual(len(self.reader._pending_joins), 1)
        self.reader._conversation_active = True
        self.assertFalse(await self.reader._dispatch_once())
        self.reader._conversation_active = False
        self.assertTrue(await self.reader._dispatch_once())
        text = json.loads(self.reader._websocket.send.call_args.args[0])["text"]
        data = json.loads(text.splitlines()[-1])
        self.assertIn("Wow!", text)
        self.assertEqual(data["verified_creator_visits"][0]["channel_id"], CHANNEL)
        self.assertNotIn(
            "joined_viewers",
            data,
            "YouTube comments must not become silent-viewer join events",
        )
        await self.reader.ingest(self.event("two"), "abcdefghijk")
        await self.reader.check_creator_once()
        self.lookup.lookup.assert_awaited_once()
        self.assertFalse(self.reader._pending_joins)

    async def test_hidden_small_equal_threshold_and_self_claims_never_produce_special_greeting(
        self,
    ):
        for profile in (
            None,
            {"channel_id": CHANNEL, "subscriber_count_lower_bound": 9999},
            {"channel_id": CHANNEL, "subscriber_count_lower_bound": 10000},
            {"channel_id": OTHER, "subscriber_count_lower_bound": 20000},
        ):
            self.lookup.lookup.return_value = profile
            self.reader._queue_creator_check("MixiGaming", CHANNEL)
            await self.reader.check_creator_once()
            self.assertFalse(self.reader._pending_joins)

    async def test_old_duplicate_invalid_and_owner_messages_do_not_trigger_lookup(self):
        await self.reader.ingest(self.event(timestamp=time.time() - 100), "abcdefghijk")
        await self.reader.ingest(self.event(channel="fake-name"), "abcdefghijk")
        await self.reader.ingest(
            self.event("owner", stream_channel_id=CHANNEL), "abcdefghijk"
        )
        self.assertFalse(self.reader._creator_candidates)
        event = self.event("fresh")
        await self.reader.ingest(event, "abcdefghijk")
        self.reader._creator_candidates.clear()
        await self.reader.ingest(event, "abcdefghijk")
        self.assertFalse(self.reader._creator_candidates)

    async def test_failed_send_retains_greeting_and_new_arrivals_do_not_get_lost(self):
        for channel in (CHANNEL, OTHER):
            self.lookup.lookup.return_value = channel_profile(
                page(ident=channel), channel
            )
            self.reader._queue_creator_check(channel, channel)
            await self.reader.check_creator_once()
        self.reader._send_to_proxy = AsyncMock(return_value=False)
        self.assertFalse(await self.reader._dispatch_once())
        self.assertEqual(len(self.reader._pending_joins), 2)
        third = "UC" + "c" * 22

        async def sent(*_):
            self.lookup.lookup.return_value = channel_profile(page(ident=third), third)
            self.reader._queue_creator_check(third, third)
            await self.reader.check_creator_once()
            return True

        self.reader._send_to_proxy.side_effect = sent
        self.assertTrue(await self.reader._dispatch_once())
        self.assertEqual(list(self.reader._pending_joins), [(third, third)])

    async def test_three_verified_visitors_are_greeted_in_bounded_batches(self):
        for letter in "abc":
            channel = "UC" + letter * 22
            self.lookup.lookup.return_value = channel_profile(
                page(ident=channel), channel
            )
            self.reader._queue_creator_check(letter, channel)
            await self.reader.check_creator_once()
        self.reader._send_to_proxy = AsyncMock(return_value=True)
        self.assertTrue(await self.reader._dispatch_once())
        data = json.loads(self.reader._send_to_proxy.call_args.args[0].splitlines()[-1])
        self.assertEqual(len(data["verified_creator_visits"]), 2)
        self.assertEqual(len(self.reader._pending_joins), 1)

    def test_previous_greeting_is_not_kept_as_a_new_identity_verification(self):
        text = self.reader._build_turn_text(
            [],
            arrival_details=[{**channel_profile(page(), CHANNEL), "nickname": "Khách"}],
        )
        compact = BasicMemoryAgent._compact_live_prompt(text)
        self.assertNotIn("verified_creator_visits", compact)
        self.assertNotIn(CHANNEL, compact)
        self.assertIn("creator_welcomes_already_handled", compact)
