import json
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.open_llm_vtuber.dialogue.story import (
    story_request,
    story_text,
    generate_story,
    collect_story_response,
)
from src.open_llm_vtuber.dialogue.intent import response_plan
from src.open_llm_vtuber.agent.hybrid.runtime import user_evidence
from src.open_llm_vtuber.agent.input_types import TextData, TextSource

STORY = {
    "beginning": "Một tối mưa, Nam trực một mình ở thư viện và nghe tiếng gõ từ chiếc tủ khóa đã lâu.",
    "middle": "Cậu tìm chìa khóa trong ngăn bàn rồi mở tủ. Bên trong chỉ có chiếc máy ghi âm cũ, đang phát tiếng gõ đều đều. Nam tắt máy, thở phào, định quay về bàn thì nghe giọng bà thủ thư gọi từ hành lang: cháu tìm được nó rồi à.",
    "ending": "Bà chỉ vào cuộn băng ghi tên người chồng đã mất. Bà cảm ơn Nam rồi cất máy, khóa cửa thư viện và cùng cậu đi về dưới chiếc ô lớn.",
}


class StoryTests(unittest.IsolatedAsyncioTestCase):
    def test_requests_genres_and_negatives(self):
        for text, expected in [
            ("Mao kể chuyện ma đi", "horror"),
            ("ke chuyen hai cho minh nghe", "comedy"),
            ("Kể một truyện về chú mèo đi", "general"),
            ("Mình muốn nghe chuyện ma", "horror"),
            ("Ma: kể chuyện hài đi", "comedy"),
            ("Đừng kể chuyện ma, kể chuyện hài đi", "comedy"),
            ("Mình kể chuyện ma cho Mao nghe", "none"),
            ("Mao đừng kể chuyện ma", "none"),
            ("Dịch câu “kể chuyện ma đi”.", "none"),
            ("Hướng dẫn cách kể chuyện ma", "none"),
            ("Hôm qua mình nghe chuyện ma", "none"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(
                    story_request(text), None if expected == "none" else expected
                )
        self.assertEqual(response_plan("Kể chuyện ma đi").mode, "story")
        payload = "[Lượt trả lời nhóm bình luận TikTok]\n" + json.dumps(
            {"comment_groups": [{"comment": "kể chuyện hài đi", "nicknames": ["Lan"]}]}
        )
        evidence = user_evidence([TextData(source=TextSource.INPUT, content=payload)])
        self.assertEqual(story_request(evidence), "comedy")

    def test_playful_scare_is_distinct_from_story_requests_and_real_distress(self):
        for text in (
            "có 10 con ma dưới gầm giường của Mao vào tối nay",
            "Có con ma sau lưng Mao kìa",
            "Hù Mao nè",
        ):
            with self.subTest(text=text):
                self.assertEqual(response_plan(text).mode, "playful_scare")
                self.assertIsNone(story_request(text))
        for text in (
            "Mình sợ ma quá, không ngủ được",
            "Không có ma dưới gầm giường Mao đâu",
            "Dịch câu “có ma sau lưng Mao”.",
        ):
            with self.subTest(text=text):
                self.assertNotEqual(response_plan(text).mode, "playful_scare")
        self.assertEqual(
            response_plan("Kể chuyện ma dưới gầm giường Mao đi").mode, "story"
        )
        rule = response_plan("Có con ma sau lưng Mao").prompt()
        self.assertIn("trách yêu", rule)
        self.assertIn("không xác nhận có ma thật", rule)

    def test_finished_story_is_spoken_without_json_labels(self):
        spoken = story_text(json.dumps(STORY, ensure_ascii=False))
        self.assertTrue(spoken.startswith(STORY["beginning"]))
        self.assertTrue(spoken.endswith(STORY["ending"]))
        self.assertNotIn("beginning", spoken)
        self.assertLessEqual(len(spoken.split()), 200)

    def test_missing_ending_cliffhanger_and_overlong_story_are_rejected(self):
        for value in [
            {k: v for k, v in STORY.items() if k != "ending"},
            {
                **STORY,
                "ending": "Chuyện này vẫn còn tiếp, Mao sẽ kể phần sau cho bạn nghe.",
            },
            {**STORY, "middle": ("Nam tiếp tục bước đi. " * 100)},
            {**STORY, "ending": "Nam chưa biết điều gì đang chờ mình phía sau"},
            {**STORY, "ending": "[smile] " + STORY["ending"]},
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    story_text(json.dumps(value, ensure_ascii=False))

    async def test_draft_is_retried_before_any_story_is_returned(self):
        calls = []
        drafts = iter(
            [
                json.dumps({"beginning": "Dở dang."}),
                json.dumps(STORY, ensure_ascii=False),
            ]
        )

        async def completion(messages, system, tools=None):
            calls.append((system, tools))
            for chunk in [next(drafts)]:
                yield chunk

        reply = await generate_story(
            SimpleNamespace(chat_completion=completion), [], "Mao", "horror"
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(reply, story_text(json.dumps(STORY, ensure_ascii=False)))
        self.assertTrue(all(tools is None for _, tools in calls))
        self.assertIn("chuyện ma", calls[0][0])

    async def test_error_event_and_oversize_response_are_never_spoken_or_truncated(
        self,
    ):
        closed = []

        async def stream(event):
            try:
                yield event
            finally:
                closed.append(True)

        with self.assertRaises(RuntimeError):
            await collect_story_response(stream({"type": "error"}))
        with self.assertRaises(ValueError):
            await collect_story_response(stream("x" * 12001))
        self.assertEqual(len(closed), 2)

    async def test_agent_emits_one_finished_story_and_stores_only_spoken_text(self):
        from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
        from src.open_llm_vtuber.agent.input_types import BatchInput

        calls = []

        async def completion(messages, system, tools=None):
            calls.append(tools)
            raw = json.dumps(STORY, ensure_ascii=False)
            for i in range(0, len(raw), 30):
                yield raw[i : i + 30]

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._hybrid = SimpleNamespace(
            prepare=AsyncMock(),
            persona_changed=False,
            interaction=None,
            direct_reply=None,
            dialogue_plan=response_plan("Kể chuyện ma đi"),
        )
        agent._tts_preprocessor_config = None
        agent._live2d_model = Mock()
        agent._faster_first_response = False
        agent._segment_method = "regex"
        agent.reset_interrupt = Mock()
        agent._to_messages = Mock(return_value=[])
        agent._system_prompt = Mock(return_value="Mao profile")
        agent._llm = SimpleNamespace(chat_completion=completion)
        agent._add_message = Mock()
        chat = inspect.unwrap(agent._chat_function_factory())
        result = [
            chunk
            async for chunk in chat(
                BatchInput([TextData(TextSource.INPUT, "Kể chuyện ma đi")])
            )
        ]
        self.assertEqual(result, [story_text(json.dumps(STORY, ensure_ascii=False))])
        agent._add_message.assert_called_once_with(result[0], "assistant")
        self.assertEqual(calls, [None])
