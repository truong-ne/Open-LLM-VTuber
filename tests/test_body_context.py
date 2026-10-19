import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.open_llm_vtuber.agent.body_context import (
    body_context,
    read_body_state,
    extract_body_tag,
)
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.vietnam_knowledge import PERSONA_MARKER
from src.open_llm_vtuber.agent.transformers import actions_extractor, sentence_divider
from src.open_llm_vtuber.live2d_model import Live2dModel
from src.open_llm_vtuber.utils.sentence_divider import (
    SentenceWithTags,
    TagInfo,
    TagState,
)


class BodyContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "body.json"
        self.state = dict(
            model="draco",
            ready=True,
            visible=True,
            socket="open",
            updatedAt=100000,
            mode="window",
            spaceX=0,
            spaceZ=-3.3,
            spaceYaw=0,
            bodyPhase="idle",
            bodyStopped=False,
        )
        self.model = Live2dModel("mao_pro")

    def tearDown(self):
        self.directory.cleanup()

    def write(self, **overrides):
        data = self.state | overrides
        self.path.write_text(json.dumps(data), encoding="utf-8")
        return data

    def test_grounded_position_heading_and_mode(self):
        self.write()
        text = body_context(self.path, now=101)
        self.assertIn("gần bàn DJ", text)
        self.assertIn("Nam (S), 180°", text)
        self.assertIn("cơ thể avatar 3D", text)
        self.assertIn("[body:dj]", text)
        self.assertIn("phòng riêng đã được trang trí sẵn", text)
        self.assertIn("chờ hết toàn bộ lượt nói mới đi", text)
        self.write(mode="pet")
        text = body_context(self.path, now=101)
        self.assertIn("Pet Mode", text)
        self.assertNotIn("[body:dj]", text)

    def test_stale_hidden_and_malformed_telemetry_not_used(self):
        for values in [
            dict(updatedAt=90000),
            dict(updatedAt=102000),
            dict(visible=False),
            dict(ready=False),
            dict(model="other"),
            dict(spaceX=float("nan")),
            dict(spaceYaw="injected"),
            dict(spaceZ=100),
        ]:
            self.write(**values)
            self.assertIsNone(read_body_state(self.path, now=101))
            self.assertEqual(body_context(self.path, now=101), "")
        self.path.write_text("{", encoding="utf-8")
        self.assertEqual(body_context(self.path, now=101), "")

    def test_tv_studio_context_replaces_old_furniture_and_brand(self):
        self.write(roomTheme="mao-tv-studio", spaceX=2.8, spaceZ=-1.4, bodyStopped=True)
        text = body_context(self.path, now=101)
        self.assertIn("Mao VTuber", text)
        self.assertIn("phòng anime", text)
        self.assertIn("bảng chữ phẳng", text)
        self.assertNotIn("bục dẫn chương trình", text)
        self.assertNotIn("màn hình TV lớn", text)
        self.assertIn("Gợi ý 1/2/3", text)
        self.assertNotIn("lounge", text)
        self.assertNotIn("DJ", text)
        self.assertIn("không tự phát lệnh body", text)

    def test_busy_stop_and_rejected_command_are_not_faked_as_success(self):
        self.write(
            bodyPhase="walk",
            bodyTargetX=0,
            bodyTargetZ=-1.65,
            lastBodyCommand="dj",
            lastBodyAccepted=False,
        )
        text = body_context(self.path, now=101)
        self.assertIn("chưa đồng nghĩa đã tới nơi", text)
        self.assertIn("không được nhận", text)
        self.write(bodyStopped=True)
        self.assertIn("dừng tự đi", body_context(self.path, now=101))

    def test_speaking_does_not_override_stop_or_reintroduce_walk_commands(self):
        self.write(bodyStopped=True, speechFocused=True)
        text = body_context(self.path, now=101)
        self.assertIn("dừng tự đi", text)
        self.assertIn("hướng về camera", text)
        self.assertNotIn("[body:", text)
        self.assertNotIn("La bàn góc trên phải", text)
        self.assertLess(len(text), 1400)

    def test_ephemeral_system_state_does_not_accumulate_in_memory(self):
        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._system = PERSONA_MARKER
        agent._memory_summary = ""
        agent._memory = [{"role": "assistant", "content": "Câu cũ."}]
        with patch(
            "src.open_llm_vtuber.agent.agents.basic_memory_agent.body_context",
            side_effect=["\nBODY_A", "\nBODY_B"],
        ):
            self.assertIn("BODY_A", agent._system_prompt())
            fresh = agent._system_prompt()
            self.assertIn("BODY_B", fresh)
            self.assertNotIn("BODY_A", fresh)
        self.assertEqual(len(agent._memory), 1)
        self.assertEqual(agent._system, PERSONA_MARKER)
        agent._max_memory_messages = 0
        agent._add_message("[body:dj] Mình sẽ bước lại đó.", "assistant")
        self.assertEqual(agent._memory[-1]["content"], "Mình sẽ bước lại đó.")

    def test_tags_stripped_and_only_first_action_in_spoken_turn(self):
        @actions_extractor(self.model)
        async def stream():
            yield SentenceWithTags("[body:dj]", [])
            yield SentenceWithTags("Mình bước về phía bàn DJ nhé.", [])
            yield SentenceWithTags("[body:spin] Mình vẫn đang trò chuyện.", [])

        with patch(
            "src.open_llm_vtuber.agent.transformers.read_body_state",
            return_value=self.state,
        ):
            result = asyncio.run(self.collect(stream()))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1].body["command"], "dj")
        self.assertIsNone(result[1][1].body)
        self.assertNotIn("[body:", "".join(s.text for s, _ in result))
        self.assertEqual(extract_body_tag("[body:execute] Hi!"), ("Hi!", None))

    def test_thoughts_and_stopped_room_cannot_move_avatar(self):
        @actions_extractor(self.model)
        async def stream():
            yield SentenceWithTags("[body:dj]", [TagInfo("think", TagState.START)])
            yield SentenceWithTags("[body:spin] Mình đứng đây nhé.", [])

        with patch(
            "src.open_llm_vtuber.agent.transformers.read_body_state",
            return_value=self.state | {"bodyStopped": True},
        ):
            result = asyncio.run(self.collect(stream()))
        self.assertTrue(all(a.body is None for _, a in result))

    def test_streamed_tag_survives_token_and_sentence_boundaries(self):
        @actions_extractor(self.model)
        @sentence_divider(faster_first_response=False)
        async def stream():
            for text in [
                "[bo",
                "dy:",
                "north] Mình bước ",
                "về phía Bắc nhé.",
                " Mình vẫn nghe bạn nè.",
            ]:
                yield text

        with patch(
            "src.open_llm_vtuber.agent.transformers.read_body_state",
            return_value=self.state,
        ):
            result = asyncio.run(self.collect(stream()))
        actions = [a.body for _, a in result if a.body]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["command"], "north")
        self.assertNotIn("[body:", "".join(s.text for s, _ in result))

    @staticmethod
    async def collect(stream):
        return [item async for item in stream]


if __name__ == "__main__":
    unittest.main()
