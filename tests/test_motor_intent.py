import asyncio
import unittest
from unittest.mock import patch
from src.open_llm_vtuber.agent.motor_intent import extract_pose_tag, validate_pose, motor_context, PoseStreamGuard
from src.open_llm_vtuber.agent.transformers import actions_extractor, sentence_divider
from src.open_llm_vtuber.live2d_model import Live2dModel
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags, TagInfo, TagState


class MotorIntentTests(unittest.TestCase):
    def test_only_bounded_finite_numbers(self):
        self.assertEqual(validate_pose({'tilt': 900, 'height': -.9}), {'tilt': 12, 'height': -.1})
        for invalid in ({'bone': 1}, {'tilt': True}, {'tilt': float('nan')}, {'nod': float('inf')}, {'duration': 3}, [], None):
            self.assertIsNone(validate_pose(invalid))

    def test_never_speak_invalid_or_executable_tags(self):
        for tag in ('tilt=nan', 'tilt=1,tilt=2', 'tilt=1,code=3', '__import__("os")', 'tilt=1=2'):
            self.assertEqual(extract_pose_tag(f'[pose:{tag}] Xin chào!'), ('Xin chào!', None))

    def test_pending_pose_crosses_sentence_boundary_and_thought_does_not_execute(self):
        @actions_extractor(Live2dModel('mao_pro'))
        async def stream():
            yield SentenceWithTags('[pose:tilt=5]', [TagInfo('think', TagState.START)])
            yield SentenceWithTags('[pose:right=0.72,tilt=-4,smile=0.4]', [])
            yield SentenceWithTags('Mình giải thích nhé!', [])
            yield SentenceWithTags('Câu tiếp theo.', [])

        async def collect():
            return [item async for item in stream()]
        output = asyncio.run(collect())
        self.assertIsNone(output[0][1].pose)
        self.assertEqual(output[1][1].pose, {'right': .72, 'tilt': -4, 'smile': .4})
        self.assertNotIn('[pose:', output[1][0].text)
        self.assertIsNone(output[2][1].pose)

    def test_inactive_renderer_does_not_advertise_motor_control(self):
        with patch('src.open_llm_vtuber.agent.motor_intent.read_body_state', return_value=None):
            self.assertEqual(motor_context(), '')
        with patch('src.open_llm_vtuber.agent.motor_intent.read_body_state', return_value={'mode': 'window'}):
            self.assertIn('[pose:', motor_context())

    def test_decimal_pose_survives_actual_token_stream(self):
        @actions_extractor(Live2dModel('mao_pro'))
        @sentence_divider(faster_first_response=True)
        async def stream():
            for chunk in ('[po', 'se:right=0.', '72,tilt=-4,smile=0.4]', ' Mình giải thích nhé.', ' Bạn thấy thế nào?'):
                yield chunk
        async def collect():
            return [item async for item in stream()]
        output = asyncio.run(collect())
        poses = [actions.pose for _, actions in output if actions.pose]
        self.assertEqual(poses, [{'right': .72, 'tilt': -4, 'smile': .4}])
        self.assertNotIn('[pose:', ''.join(sentence.text for sentence, _ in output))

    def test_truncated_and_oversized_instructions_are_not_spoken(self):
        guard = PoseStreamGuard()
        self.assertEqual(guard.feed('Chào! [po'), 'Chào! ')
        self.assertEqual(guard.feed('se:tilt=0.'), '')
        self.assertEqual(guard.feed('', final=True), '')
        guard = PoseStreamGuard()
        self.assertEqual(guard.feed('[pose:' + 'x' * 1000), '')
        self.assertEqual(guard.feed('] Vẫn trò chuyện.'), ' Vẫn trò chuyện.')

    def test_motor_parameters_do_not_pollute_conversation_memory(self):
        from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._memory = []
        agent._max_memory_messages = 0
        agent._add_message('[pose:right=0.72,smile=0.4] Chào papa!', 'assistant')
        agent._add_message('[pose:tilt=4]', 'assistant')
        self.assertEqual(agent._memory, [{'role': 'assistant', 'content': 'Chào papa!'}])


if __name__ == '__main__':
    unittest.main()
