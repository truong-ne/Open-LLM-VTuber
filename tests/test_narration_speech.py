import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.open_llm_vtuber.live.narration_speech import (
    narration_chunks, narration_text, NarrationPlanner,
)


class NarrationSpeechTests(unittest.TestCase):
    def test_complete_thought_is_not_cut_at_eighteen_words(self):
        sentence = ('Mao đang đọc về cách gọi tên cảm xúc của bản thân để hiểu rõ '
                    'điều gì làm mình vui và điều gì khiến mình bối rối.')
        self.assertGreater(len(sentence.split()), 18)
        self.assertEqual(narration_chunks(sentence), [sentence])
        self.assertEqual(narration_chunks(sentence+' Mao muốn thử!'), [sentence, 'Mao muốn thử!'])

    def test_study_keeps_gentle_intent_and_native_cue_out_of_subtitles(self):
        planner = NarrationPlanner()
        speech = planner.plan('[sadness] Mao đang nghe mọi người.')
        self.assertEqual(speech.mood, 'gentle')
        self.assertLess(speech.tempo, 1)
        self.assertEqual(planner.plan('Cứ nói tiếp nhé.').mood, 'gentle')
        speech = NarrationPlanner().plan('[joy] Vui quá [cười]!')
        self.assertEqual(speech.native_cue, 'cười')
        self.assertEqual(narration_text('[joy] Vui quá [cười]!'), 'Vui quá!')
        self.assertEqual(narration_chunks('Ơ… Mao hơi ngại đấy.'), ['Ơ… Mao hơi ngại đấy.'])
        self.assertIsNone(NarrationPlanner().plan('[joy] Chia buồn [cười].').native_cue)
        self.assertEqual(NarrationPlanner().plan('Mao đang tìm hiểu.').mood, 'thoughtful')


class NarrationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_research_uses_sentence_and_emotion_without_game_speed_or_cache(self):
        from src.open_llm_vtuber.conversations.single_conversation import process_single_conversation
        script = '[sadness] Mao đang nghe mọi người kể về điều khiến mọi người buồn và muốn cùng tìm cách hiểu rõ hơn.'
        context = Mock()
        context.character_config.character_name = 'Mao'
        context.character_config.avatar = 'mao.png'
        manager = Mock(speak=AsyncMock(), wait_for_completion=AsyncMock())
        module = 'src.open_llm_vtuber.conversations.single_conversation'
        with (patch(module+'.TTSTaskManager', return_value=manager),
              patch(module+'.finalize_conversation_turn', new_callable=AsyncMock),
              patch(module+'.cleanup_conversation')):
            await process_single_conversation(context, AsyncMock(), 'test', '', metadata={'narration_speech':script})
        manager.speak.assert_awaited_once()
        call = manager.speak.call_args.kwargs
        self.assertIs(call['tts_engine'], context.tts_engine)
        self.assertEqual(call['speech'].mood, 'gentle')
        self.assertLess(call['speech'].tempo, 1)
        self.assertNotIn('[sadness]', call['tts_text'])
        context.agent_engine.chat.assert_not_called()
