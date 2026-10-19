import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.open_llm_vtuber.live.session_content import (
    SessionContent,
    TOPICS,
    ANGLES,
    ENGAGEMENT_TOPICS,
)
from src.open_llm_vtuber.live.idle_host_storage import read_json, write_json
from src.open_llm_vtuber.agent.agents.basic_memory_agent import (
    BasicMemoryAgent,
    MEMORY_SUMMARY_BATCH_CHARS,
)
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource


class LongLiveContentTests(unittest.TestCase):
    def test_engagement_topics_rotate_without_losing_the_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            planner = SessionContent(Path(folder) / "session.json", random.Random(11))
            previous = None
            for _ in range(12):
                topic = planner.topic(exclude=previous, preferred=ENGAGEMENT_TOPICS)
                self.assertIn(topic, ENGAGEMENT_TOPICS)
                self.assertNotEqual(topic, previous)
                planner.commit(topic, planner.angle(topic))
                previous = topic
            self.assertEqual(planner.turns, 12)

    def test_eight_hour_schedule_has_960_distinct_topic_angle_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            planner = SessionContent(Path(folder) / "session.json", random.Random(8))
            pairs = set()
            with patch("src.open_llm_vtuber.live.session_content.write_json"):
                for segment in range(480):
                    recent = planner.recent_topics.copy()
                    topic = planner.topic()
                    self.assertNotIn(topic, recent)
                    for _ in range(2):
                        angle = planner.angle(topic)
                        self.assertNotIn((topic, angle), pairs)
                        pairs.add((topic, angle))
                        planner.commit(topic, angle)
            self.assertEqual(len(pairs), 960)
            self.assertGreaterEqual(len(TOPICS) * len(ANGLES), 960)

    def test_content_rotation_survives_restart_without_reusing_recent_topics(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            planner = SessionContent(path, random.Random(3))
            topic = planner.topic()
            angle = planner.angle(topic)
            planner.commit(topic, angle)
            resumed = SessionContent(path, random.Random(3))
            self.assertEqual(resumed.turns, 1)
            self.assertNotEqual(resumed.topic(), topic)
            self.assertNotEqual(resumed.angle(topic), angle)
            self.assertEqual(read_json(path)["turns"], 1)

    def test_invalid_journal_recovers_with_fresh_rotation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            write_json(path, {"used": None, "recent_topics": 4, "turns": "bad"})
            planner = SessionContent(path)
            self.assertIn(planner.topic(), TOPICS)
            self.assertEqual(planner.turns, 0)


class LiveMemoryTests(unittest.IsolatedAsyncioTestCase):
    def agent(self):
        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._memory = []
        agent._max_memory_messages = 24
        agent._summarize_memory = True
        agent._memory_summary = ""
        agent._pending_summary_messages = []
        agent._summary_task = None
        return agent

    def test_current_instruction_is_full_but_stored_memory_keeps_only_its_context(self):
        agent = self.agent()
        context = {"topic": "ngắm mây", "angle": "đổi góc nhìn", "style": "chat"}
        text = (
            "[Mao chủ động mở chuyện khi chat yên; đây không phải bình luận khán giả]\n"
            + "Hướng dẫn vận hành dài. " * 100
            + "\n"
            + json.dumps({"live_context": context}, ensure_ascii=False)
        )
        messages = agent._to_messages(
            BatchInput(texts=[TextData(TextSource.INPUT, text)])
        )
        self.assertEqual(messages[-1]["content"][0]["text"], text)
        stored = agent._memory[-1]["content"]
        self.assertIn("ngắm mây", stored)
        self.assertLess(len(stored), len(text) / 4)
        self.assertNotIn("Hướng dẫn vận hành", stored)
        agent._add_message("Mình thích đám mây giống một con mèo.", "assistant")
        self.assertEqual(
            agent._memory[-1]["content"], "Mình thích đám mây giống một con mèo."
        )

    def test_real_viewer_text_is_preserved_and_old_tiktok_is_labeled_old(self):
        compact = BasicMemoryAgent._compact_live_prompt
        real = "Mình thích cà phê hơn trà sữa, Mao nhớ nha."
        self.assertEqual(compact(real), real)
        old = compact(
            "[Lượt trả lời nhóm bình luận TikTok thật đã chờ lượt]\n"
            '{"comment_groups":[{"comment":"Mao là ai?"}]}'
        )
        self.assertIn("không tự đáp lại", old)
        self.assertIn("Mao là ai?", old)

    async def test_many_hours_of_memory_are_summarized_in_bounded_batches(self):
        agent = self.agent()
        agent._pending_summary_messages = [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": str(i) + "x" * 1000,
            }
            for i in range(100)
        ]
        calls = []

        async def summarize(batch):
            calls.append(batch)
            self.assertLessEqual(
                sum(len(m["content"]) for m in batch), MEMORY_SUMMARY_BATCH_CHARS
            )
            return "Sở thích đã xác nhận; câu hỏi đã đáp; chuyện đã khép; ý còn chờ."

        agent._request_memory_summary = summarize
        await agent._summarize_pending_memory()
        self.assertEqual(sum(len(batch) for batch in calls), 100)
        self.assertGreater(len(calls), 1)
        self.assertFalse(agent._pending_summary_messages)
        self.assertIn("chuyện đã khép", agent._memory_summary)
