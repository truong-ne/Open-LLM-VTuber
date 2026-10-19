import asyncio
import unittest
from types import SimpleNamespace

from src.open_llm_vtuber.agent.transformers import actions_extractor
from src.open_llm_vtuber.live2d_model import Live2dModel
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags, TagInfo, TagState
from src.open_llm_vtuber.conversations.conversation_handler import handle_conversation_trigger


class PetContextTests(unittest.TestCase):
    def setUp(self):
        self.model = Live2dModel("mao_pro")

    def test_supported_motion_only_and_not_random_on_plain_text(self):
        self.assertEqual(self.model.extract_context_motions("Xin chào!"), [])
        self.assertEqual(self.model.extract_context_motions("[idle] [execute]"), [])
        self.assertEqual(self.model.extract_context_motions("[Shy] [nod]"), ["shy"])
        self.assertEqual(self.model.context_motions_for_sentence("Hi Bông!"), ["nod"])
        self.assertEqual(self.model.context_motions_for_sentence("Mình đang nghe."), [])

    def test_motion_is_payload_not_spoken_text(self):
        @actions_extractor(self.model)
        async def stream():
            yield SentenceWithTags("[nod] Hi Bông! [joy]", [])

        async def collect():
            return [item async for item in stream()]

        sentence, actions = asyncio.run(collect())[0]
        self.assertEqual(actions.to_dict(), {"expressions": [3], "motions": ["nod"]})
        self.assertNotIn("[nod]", sentence.text)
        self.assertIn("Hi Bông!", sentence.text)

    def test_thought_tags_cannot_execute_motion(self):
        @actions_extractor(self.model)
        async def stream():
            yield SentenceWithTags("[shake]", [TagInfo("think", TagState.START)])

        async def collect():
            return [item async for item in stream()]

        _, actions = asyncio.run(collect())[0]
        self.assertNotIn("motions", actions.to_dict())

    def test_story_face_tags_are_metadata_and_never_spoken(self):
        for motion in ("refuse", "squint", "flat", "surprised"):
            @actions_extractor(self.model)
            async def stream():
                yield SentenceWithTags(f"[{motion}] [joy] Một tình huống bất ngờ!", [])

            async def collect():
                return [item async for item in stream()]

            sentence, actions = asyncio.run(collect())[0]
            self.assertEqual(actions.motions, [motion])
            self.assertNotIn(f"[{motion}]", sentence.text)
            self.assertEqual(actions.expressions, [3])

    def test_idle_speech_trigger_is_ignored_in_pet_context(self):
        context = SimpleNamespace(system_config=SimpleNamespace(
            tool_prompts={"pet_action_prompt": "mao_pet_actions"}
        ))
        asyncio.run(handle_conversation_trigger(
            "ai-speak-signal", {"idle_time": 20}, "test", context,
            None, {}, {}, None, {}, {}, None,
        ))


if __name__ == "__main__":
    unittest.main()
