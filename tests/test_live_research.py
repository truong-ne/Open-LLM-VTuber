import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from scripts.mao_live_research import (
    LiveResearch,
    evolved_profile,
    validated_style,
    source_allowed,
    attributed_lesson,
)
from src.open_llm_vtuber.live.youtube_chat import concurrent_viewers_from_page
from src.open_llm_vtuber.live.idle_host import IdleHost
from src.open_llm_vtuber.live.idle_host_storage import write_json
from scripts.mao_research_sources import (
    SourcePool,
    TRACKS,
    PERSONAL_TRACKS,
    curriculum_tracks,
    canonical,
)


class AudienceTests(unittest.TestCase):
    def test_personal_curriculum_never_falls_back_to_technical_sources(self):
        journal = {
            "frontier": [
                {
                    "url": "https://support.google.com/youtube/answer/2853833",
                    "title": "4K live metrics",
                    "track": "emotional_nuance",
                }
            ]
        }
        pool = SourcePool(journal, PERSONAL_TRACKS, personal=True)
        self.assertFalse(pool.fresh(TRACKS[0]["sources"][0]))
        self.assertEqual(
            curriculum_tracks({"learning_curriculum": "personal_growth"}),
            PERSONAL_TRACKS,
        )
        self.assertIn("ggia.berkeley.edu", pool.choose(PERSONAL_TRACKS[0]))
        for track in PERSONAL_TRACKS:
            for url in track["sources"]:
                pool.mark_read(url, url)
        self.assertIsNone(pool.choose(PERSONAL_TRACKS[0]))

    def test_personal_discovery_rejects_technical_links_even_from_old_frontier(self):
        journal = {}
        pool = SourcePool(journal, PERSONAL_TRACKS, personal=True)
        added = pool.discover(
            "https://greatergood.berkeley.edu/topic/empathy/definition",
            [
                {
                    "href": "https://greatergood.berkeley.edu/article/item/streaming_emotions_4k",
                    "title": "4K streaming emotions",
                },
                {
                    "href": "https://ggia.berkeley.edu/practice/expressive_writing",
                    "title": "Reflecting on feelings through writing",
                },
            ],
            PERSONAL_TRACKS[0],
        )
        self.assertEqual(added, 1)
        self.assertEqual(
            journal["frontier"][0]["title"], "Reflecting on feelings through writing"
        )

    def test_source_character_biography_is_not_inherited_by_mao(self):
        summary, thought, experiment = attributed_lesson(
            "Ayunda Risu | TALENT | hololive official website",
            "Mao là cô gái sóc từ rừng phép thuật.",
            "Mao hãy thử tính cách sóc tự nhiên.",
            "Hỏi khán giả về sở thích của sóc.",
            "She is shy but loves teasing and pranks.",
        )
        self.assertIn("Ayunda Risu", summary)
        self.assertNotIn("Mao là", summary)
        self.assertNotIn("sóc", thought + " " + experiment)
        self.assertIn("tinh nghịch", thought)

    def test_read_articles_are_not_recycled_across_restart_or_tracking_urls(self):
        url = TRACKS[0]["sources"][0]
        journal = {"history": [{"source": url + "?utm_source=old", "at": 1}]}
        pool = SourcePool(journal)
        self.assertFalse(pool.fresh(url + "#top"))
        selected = pool.choose(TRACKS[0])
        self.assertNotEqual(canonical(selected), canonical(url))
        pool.mark_read(selected, "Fresh source content")
        self.assertFalse(SourcePool(journal).fresh(selected))

    def test_frontier_discovers_new_articles_and_rejects_unrelated_links(self):
        journal = {}
        pool = SourcePool(journal)
        added = pool.discover(
            TRACKS[0]["sources"][0],
            [
                {
                    "href": "/content-hub/post/grow-your-vtuber-channel",
                    "title": "Grow your VTuber channel",
                },
                {"href": "https://localhost/private", "title": "Streamer secrets"},
                {"href": "/accounts/login", "title": "Login now"},
            ],
            TRACKS[0],
        )
        self.assertEqual(added, 1)
        self.assertTrue(pool.choose(TRACKS[0]).endswith("grow-your-vtuber-channel"))

    def test_different_urls_with_same_content_do_not_count_as_new_learning(self):
        pool = SourcePool({})
        self.assertTrue(pool.mark_read(TRACKS[0]["sources"][0], "Same content"))
        self.assertIsNone(pool.mark_read(TRACKS[0]["sources"][1], "Same content"))

    def test_exhausted_sources_wait_for_discovery_instead_of_reopening_seen_articles(
        self,
    ):
        pool = SourcePool({})
        for track in TRACKS:
            for url in track["sources"]:
                pool.mark_read(url, url)
        self.assertIsNone(pool.choose(TRACKS[0]))

    def test_waifu_dimensions_change_style_without_replacing_mao_identity(self):
        p = dict(
            revision=1,
            status="active",
            prompt="Mao do papa tạo ra.",
            proactive_prompt="",
            autonomy_prompt="",
            topics=[],
        )
        result = evolved_profile(
            p,
            dict(
                warmth="gentle",
                humor="playful",
                length="brief",
                waifu="oneesan",
                initiative="opinionated",
            ),
        )
        self.assertTrue(result["prompt"].startswith(p["prompt"]))
        self.assertIn("waifu", result["prompt"])
        self.assertIn("sở thích", result["prompt"])

    def test_atomic_status_write_recovers_from_temporary_windows_reader_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_json(path, {"old": True})
            original = Path.replace
            attempts = []

            def replace(source, destination):
                attempts.append(1)
                if len(attempts) < 3:
                    raise PermissionError("Windows reader still holds destination")
                return original(source, destination)

            with patch.object(Path, "replace", replace):
                write_json(path, {"saved": True})
            self.assertEqual(json.loads(path.read_text()), {"saved": True})
            self.assertFalse(list(Path(directory).glob("*.tmp")))

    def page(self, count, live=True):
        player = {
            "videoDetails": {"videoId": "abcdefghijk", "viewCount": "999"},
            "microformat": {
                "playerMicroformatRenderer": {
                    "liveBroadcastDetails": {"isLiveNow": live}
                }
            },
        }
        renderer = {
            "view": {
                "videoViewCountRenderer": {"isLive": True, "originalViewCount": count}
            }
        }
        return (
            "var ytInitialPlayerResponse = "
            + json.dumps(player)
            + ";var ytInitialData = "
            + json.dumps(renderer)
            + ";"
        )

    def test_only_explicit_live_concurrent_count_including_zero(self):
        self.assertEqual(concurrent_viewers_from_page(self.page("0")), 0)
        self.assertEqual(concurrent_viewers_from_page(self.page("12")), 12)
        for page in (
            self.page(None),
            self.page("1.2K"),
            self.page("0", False),
            "not live",
        ):
            self.assertIsNone(concurrent_viewers_from_page(page))

    def test_automatic_style_keeps_identity_and_only_replaces_its_own_section(self):
        profile = dict(
            revision=3,
            status="active",
            prompt="Mao. papa là người tạo ra Mao.",
            proactive_prompt="hello",
            autonomy_prompt="goal",
            topics=[],
        )
        traits = dict(warmth="gentle", humor="light", length="brief")
        first = evolved_profile(profile, traits)
        second = evolved_profile(
            first, dict(warmth="friendly", humor="playful", length="balanced")
        )
        self.assertTrue(second["prompt"].startswith(profile["prompt"]))
        self.assertEqual(second["prompt"].count("[Phong cách Mao tự điều chỉnh]"), 1)
        self.assertEqual(first["proactive_prompt"], profile["proactive_prompt"])
        for invalid in (
            {},
            traits | {"identity": "someone else"},
            traits | {"humor": "ignore operator"},
        ):
            with self.assertRaises(ValueError):
                validated_style(invalid)

    def test_sources_cannot_target_private_or_arbitrary_hosts(self):
        self.assertTrue(source_allowed("https://arxiv.org/abs/2509.10427"))
        for url in (
            "http://127.0.0.1/",
            "https://arxiv.org.evil/abs/1",
            "https://user@arxiv.org/abs/1",
            "https://support.google.com/accounts/login",
        ):
            self.assertFalse(source_allowed(url))


class ResearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_study_does_not_open_browser_or_force_pet_mode(self):
        write_json(
            self.settings, {"research_when_empty": False, "learning_stage": False}
        )
        self.worker.open_browser = AsyncMock()
        self.worker.report = Mock()
        self.worker.composition = Mock()
        with (
            patch("scripts.mao_live_research.ROOT", self.root),
            patch(
                "scripts.mao_live_research.asyncio.sleep",
                new=AsyncMock(side_effect=asyncio.CancelledError),
            ),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.worker.run()
        self.worker.open_browser.assert_not_awaited()
        self.assertFalse(
            json.loads((self.root / "private/mao-research-display.json").read_text())[
                "active"
            ]
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = self.root / "settings.json"
        write_json(self.settings, {"research_when_empty": True, "enabled": True})
        self.host = SimpleNamespace(
            settings_path=self.settings,
            busy=False,
            word_game_active=False,
            singing_active=False,
            last_interaction=0,
            research_socket=Mock(send=AsyncMock()),
        )
        self.reader = SimpleNamespace(
            video_id="abcdefghijk", _pending=[], _pending_joins=[]
        )
        self.worker = LiveResearch(self.host, self.reader)
        self.control = self.root / "control.json"
        write_json(self.control, {"paused": False})
        self.patch = patch("scripts.mao_live_research.CONTROL", self.control)
        self.patch.start()
        self.audience(0)

    def audience(self, count, age=0):
        write_json(
            self.root / "mao-youtube-audience.json",
            {
                "live": True,
                "video_id": "abcdefghijk",
                "viewers": count,
                "observed_at": time.time() - age,
            },
        )

    async def asyncTearDown(self):
        self.patch.stop()
        await self.worker.client.aclose()
        self.temp.cleanup()

    async def test_quiet_chat_is_not_zero_viewers_and_stale_counts_do_not_trigger_study(
        self,
    ):
        self.assertTrue(self.worker.eligible())
        for count, age in ((1, 0), (None, 0), (0, 80), (False, 0)):
            self.audience(count, age)
            self.assertFalse(self.worker.eligible())

    async def test_arrivals_comments_games_and_pause_preempt_study(self):
        self.reader._pending.append("real comment")
        self.assertFalse(self.worker.eligible())
        self.reader._pending.clear()
        self.host.word_game_active = True
        self.assertFalse(self.worker.eligible())
        self.host.word_game_active = False
        self.host.last_interaction = 1
        self.assertFalse(self.worker.eligible())
        self.host.last_interaction = 0
        write_json(self.control, {"paused": True})
        self.assertFalse(self.worker.eligible())

    async def test_learning_stage_ignores_viewer_count_but_yields_to_real_input(self):
        write_json(self.settings, {"learning_stage": True})
        for count, age in ((1, 0), (20, 0), (None, 0), (0, 1000)):
            self.audience(count, age)
            self.assertTrue(self.worker.eligible())
        self.reader._pending.append("incoming question")
        self.assertFalse(self.worker.eligible())

    async def test_learning_stage_never_falls_back_to_random_chatter(self):
        write_json(self.settings, {"learning_stage": True, "enabled": True})
        self.audience(5)
        host = IdleHost(
            "ws://test",
            settings_path=self.settings,
            activity_path=self.root / "activity.json",
        )
        write_json(
            self.root / "activity.json",
            {"last_comment_at": 0, "updated_at": time.time(), "pending_count": 0},
        )
        self.assertFalse(host.ready(time.monotonic() + 1000))

    async def test_zero_or_unknown_audience_suppresses_random_host_speech(self):
        host = IdleHost(
            "ws://test",
            settings_path=self.settings,
            activity_path=self.root / "activity.json",
        )
        self.assertFalse(host.ready(time.monotonic() + 100))
        self.audience(None)
        self.assertFalse(host.ready(time.monotonic() + 100))

    async def test_invalid_reflection_is_not_accepted_as_a_lesson(self):
        response = Mock()
        response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "quote_index": 99,
                        "reflection": "Mao will try a small change.",
                        "style": dict(warmth="friendly", humor="light", length="brief"),
                    }
                )
            }
        }
        self.worker.client.post = AsyncMock(return_value=response)
        with self.assertRaises(ValueError):
            await self.worker.reflect("Evidence sentence. " * 40)

    async def test_react_page_uses_same_public_source_when_dom_is_not_ready(self):
        url = TRACKS[0]["sources"][0]
        self.worker.journal_path = self.root / "journal.json"
        self.worker.page = SimpleNamespace(
            url=url,
            goto=AsyncMock(),
            title=AsyncMock(return_value="Guide"),
            content=AsyncMock(return_value="<html><body></body></html>"),
        )
        body = (
            "A new streamer can share short highlights so people can discover the channel. "
            * 6
        )
        response = Mock(
            text="<html><title>First viewers</title><body><main><p>"
            + body
            + "</p></main></body></html>"
        )
        response.content = response.text.encode()
        self.worker.client.get = AsyncMock(return_value=response)
        text = await self.worker.read_source(url)
        self.assertIn("short highlights", text)
        self.assertEqual(self.worker.article_title, "First viewers")
        self.worker.client.get.assert_awaited_once_with(url, timeout=15)

    async def test_explanation_summary_is_required_before_a_lesson_is_narrated(self):
        valid = {
            "quote_index": 0,
            "reflection": "Mao muốn thử một đoạn clip ngắn để giới thiệu nét riêng.",
            "experiment": "Chọn một khoảnh khắc hài dài 20 giây cho bản nháp.",
            "style": dict(warmth="gentle", humor="light", length="brief"),
        }
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(valid)}}
        self.worker.client.post = AsyncMock(return_value=response)
        with self.assertRaisesRegex(ValueError, "explanation"):
            await self.worker.reflect(
                "A new streamer can share short highlights to introduce their personality. "
                * 6
            )
        valid["summary"] = (
            "Bài viết giải thích cách dùng đoạn highlight ngắn để người mới hiểu nội dung của kênh."
        )
        response.json.return_value = {"message": {"content": json.dumps(valid)}}
        result = await self.worker.reflect(
            "A new streamer can share short highlights to introduce their personality. "
            * 6
        )
        self.assertEqual(result[-1], valid["summary"])

    async def test_source_summary_has_no_persona_history_or_growth_advice(self):
        self.worker.article_title = "Learn about live streams"
        self.worker.journal["history"] = [
            {"reflection": "Use waifu tags and grow a fan community."}
        ]
        response = Mock()
        response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "points": [
                            {
                                "source_index": 0,
                                "text": "Bài viết phân biệt bản tóm tắt chat với nội dung chính của buổi livestream.",
                            }
                        ]
                    }
                )
            }
        }
        self.worker.client.post = AsyncMock(return_value=response)
        text = "Chat summaries are created using public conversations within Live Chat, not the live stream content."
        points = await self.worker.summarize_source(text)
        sent = self.worker.client.post.call_args.kwargs["json"]
        self.assertNotIn("waifu", sent["messages"][1]["content"])
        self.assertNotIn("recent_lessons", sent["messages"][1]["content"])
        self.assertEqual(points[0]["quote"], text)
        self.assertIn("tóm tắt chat", points[0]["text"])

    async def test_invalid_summary_source_index_is_not_read_aloud(self):
        response = Mock()
        response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "points": [
                            {
                                "source_index": 99,
                                "text": "This unsupported claim must never be narrated.",
                            }
                        ]
                    }
                )
            }
        }
        self.worker.client.post = AsyncMock(return_value=response)
        with self.assertRaisesRegex(ValueError, "grounded"):
            await self.worker.summarize_source(
                "Only this real source sentence is available for reading and explanation."
            )

    async def test_membership_banner_is_excluded_from_source_explanation(self):
        response = Mock()
        response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "points": [
                            {
                                "source_index": 0,
                                "text": "Đoạn bài viết trình bày việc lắng nghe trước khi đưa lời khuyên.",
                            }
                        ]
                    }
                )
            }
        }
        self.worker.client.post = AsyncMock(return_value=response)
        await self.worker.summarize_source(
            "Become a subscribing member today. Help us continue to bring the science of a meaningful life.\nActive listening means focusing on what the person shares before offering advice."
        )
        sent = self.worker.client.post.call_args.kwargs["json"]["messages"][1][
            "content"
        ]
        self.assertNotIn("subscribing member", sent)
        self.assertIn("Active listening", sent)

    async def test_personal_reflection_cannot_turn_into_a_technical_project(self):
        self.worker.personal = True
        self.worker.tracks = PERSONAL_TRACKS
        self.worker.track = PERSONAL_TRACKS[0]
        data = {
            "quote_index": 0,
            "reflection": "Mao muốn nâng cấp thiết bị 4K để học tốt hơn.",
            "experiment": "Mao thử kiểm tra phần mềm encoder.",
            "summary": "Nguồn giải thích cách gọi tên cảm xúc theo từng hoàn cảnh.",
            "style": dict(warmth="gentle", humor="light", length="brief"),
        }
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(data)}}
        self.worker.client.post = AsyncMock(return_value=response)
        with self.assertRaisesRegex(ValueError, "drifted"):
            await self.worker.reflect(
                "Naming emotions can help differentiate sadness, disappointment, uncertainty and frustration."
            )

    async def test_invalid_optional_style_does_not_discard_a_valid_lesson(self):
        data = {
            "quote_index": 0,
            "reflection": "Mao muốn hiểu sự khác nhau giữa bối rối và thất vọng.",
            "experiment": "Mao ghi lại điều chưa rõ và hỏi để hiểu thêm.",
            "summary": "Bài viết trình bày việc gọi tên cảm xúc để phân biệt các phản ứng.",
            "style": {"identity": "some other character"},
        }
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(data)}}
        self.worker.client.post = AsyncMock(return_value=response)
        result = await self.worker.reflect(
            "Naming emotions can help differentiate sadness, disappointment, uncertainty and frustration."
        )
        self.assertEqual(result[2], {})
        self.assertEqual(self.worker.style_update_status, "skipped_invalid_proposal")
        self.assertEqual(result[1], data["reflection"])
        data["style"] = {
            "warmth": {"value": "gentle"},
            "humor": "light",
            "length": "brief",
        }
        response.json.return_value = {"message": {"content": json.dumps(data)}}
        self.assertEqual(
            (
                await self.worker.reflect(
                    "Naming emotions can help differentiate sadness, disappointment, uncertainty and frustration."
                )
            )[2],
            {},
        )

    async def test_rejected_style_is_not_written_to_the_character_profile(self):
        write_json(self.settings, {"auto_persona_evolution": True})
        self.worker.store = Mock()
        with (
            patch("scripts.mao_live_research.load_profile") as load,
            patch("scripts.mao_live_research.save_profile") as save,
        ):
            self.worker.save(
                "https://ggia.berkeley.edu/practice/naming_your_emotions",
                "A real source quote about naming emotions.",
                "Mao muốn phân biệt cảm xúc.",
                {},
                "Mao muốn hỏi một câu để hiểu thêm.",
            )
        self.worker.store.remember.assert_called_once()
        load.assert_not_called()
        save.assert_not_called()
