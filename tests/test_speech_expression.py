import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.agent.transformers import (
    tts_filter,
    actions_extractor,
    display_processor,
)
from src.open_llm_vtuber.live2d_model import Live2dModel
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.tts.prosody import (
    SpeechProsody,
    TurnSpeechPlanner,
    plan_speech,
)
from src.open_llm_vtuber.tts.vieneu_tts import TTSEngine
from src.open_llm_vtuber.utils.sentence_divider import (
    SentenceWithTags,
    TagInfo,
    TagState,
)
from test_vieneu_speed import FFMPEG

FILTER_CONFIG = SimpleNamespace(
    vietnamese_math=True,
    remove_special_char=True,
    ignore_brackets=True,
    ignore_parentheses=True,
    ignore_asterisks=True,
    ignore_angle_brackets=True,
)


class ExpressionPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_math_is_spoken_but_original_formula_stays_on_subtitles(self):
        @tts_filter(FILTER_CONFIG)
        @display_processor()
        @actions_extractor(Live2dModel("mao_pro"))
        async def stream():
            yield SentenceWithTags("Với x^2 và x<3 nhé.", [])

        output = [item async for item in stream()][0]
        self.assertEqual(output.display_text.text, "Với x^2 và x<3 nhé.")
        self.assertEqual(output.tts_text, "Với ích mũ 2 và ích nhỏ hơn 3 nhé.")

    async def test_arithmetic_reaches_vieneu_without_merging_numbers(self):
        from vieneu_utils.phonemize_text import _get_normalizer

        for text in ("1+1=2.", "1 + 1 = 2.", "１＋１＝２."):
            with self.subTest(text=text):

                @tts_filter(FILTER_CONFIG)
                async def stream():
                    yield SentenceWithTags(text, []), DisplayText(text), Actions()

                output = [item async for item in stream()][0]
                self.assertEqual(output.display_text.text, text)
                self.assertEqual(
                    _get_normalizer().normalize(output.tts_text),
                    "một cộng một bằng hai.",
                )

    async def test_shy_gesture_keeps_vocal_intent_after_removal_from_spoken_text(self):
        @tts_filter(FILTER_CONFIG)
        @display_processor()
        @actions_extractor(Live2dModel("mao_pro"))
        async def stream():
            yield SentenceWithTags("[shy] Ơ… khen vậy làm Mao hơi ngại đấy.", [])
            yield SentenceWithTags("[joy] Nhưng mình vui lắm!", [])

        shy, bright = [item async for item in stream()]
        self.assertEqual(shy.actions.motions, ["shy"])
        self.assertEqual(shy.speech.mood, "bashful")
        self.assertNotIn("[shy]", shy.tts_text)
        self.assertNotIn("[shy]", shy.display_text.text)
        self.assertEqual(bright.speech.mood, "bright")
        self.assertGreater(bright.speech.tempo, shy.speech.tempo)

    async def test_paragraph_emotion_flows_but_new_stream_starts_neutral(self):
        @tts_filter(FILTER_CONFIG)
        async def stream(with_mood):
            lines = ["[smirk] Bạn trêu cô đấy à [cười]?"] if with_mood else []
            lines += ["Cô vẫn đang đợi câu tiếp theo đấy."]
            for text in lines:
                yield SentenceWithTags(text, []), DisplayText(text), Actions()

        expressive = [item async for item in stream(True)]
        self.assertEqual(expressive[1].speech.mood, "playful")
        self.assertIsNone(expressive[1].speech.native_cue)
        fresh = [item async for item in stream(False)]
        self.assertEqual(fresh[0].speech.mood, "neutral")

    async def test_native_cue_is_metadata_not_subtitle_or_spoken_label(self):
        @tts_filter(FILTER_CONFIG)
        async def stream():
            text = "[smirk] Bạn trêu cô Mao đấy à [cười]?"
            yield SentenceWithTags(text, []), DisplayText(text), Actions()

        output = [item async for item in stream()][0]
        self.assertEqual(output.speech.mood, "playful")
        self.assertEqual(output.speech.native_cue, "cười")
        self.assertNotIn("cười", output.tts_text)
        self.assertNotIn("[cười]", output.display_text.text)
        self.assertIn("Bạn trêu cô Mao", output.tts_text)

    async def test_thinking_cannot_execute_vocal_cues(self):
        @tts_filter(FILTER_CONFIG)
        async def stream():
            text = "[cười]"
            yield (
                SentenceWithTags(text, [TagInfo("think", TagState.START)]),
                DisplayText(text),
                Actions(),
            )

        output = [item async for item in stream()][0]
        self.assertFalse(output.tts_text)
        self.assertIsNone(output.speech)

    async def test_turn_limits_native_cue_but_keeps_mood_on_later_sentences(self):
        manager = TTSTaskManager()
        manager._process_tts = AsyncMock()
        speech = SpeechProsody("bright", 1.03, 70, "cười")
        try:
            for _ in range(2):
                await manager.speak(
                    "Vui quá!",
                    DisplayText("Vui quá!"),
                    Actions(),
                    Mock(),
                    Mock(),
                    AsyncMock(),
                    speech=speech,
                )
            await asyncio.gather(*manager.task_list)
            first, second = manager._process_tts.call_args_list
            self.assertEqual(first.kwargs["speech"].native_cue, "cười")
            self.assertIsNone(second.kwargs["speech"].native_cue)
            self.assertEqual(second.kwargs["speech"].mood, "bright")
        finally:
            sender = manager._sender_task
            manager.clear()
            if sender:
                await asyncio.gather(sender, return_exceptions=True)

    async def test_other_tts_engines_keep_the_original_call_signature(self):
        manager = TTSTaskManager()
        engine = SimpleNamespace(
            async_generate_audio=AsyncMock(return_value="audio.wav")
        )
        speech = plan_speech("[joy] Vui quá!")
        await manager._generate_audio(engine, "Vui quá!", speech)
        self.assertNotIn("prosody", engine.async_generate_audio.call_args.kwargs)
        engine.supports_prosody = True
        await manager._generate_audio(engine, "Vui quá!", speech)
        self.assertEqual(
            engine.async_generate_audio.call_args.kwargs["prosody"], speech
        )


class VieNeuExpressionTests(unittest.TestCase):
    def engine(self):
        engine = TTSEngine.__new__(TTSEngine)
        engine.mode = "v3turbo"
        engine.voice = "Mỹ Duyên"
        engine.ref_audio = None
        engine.rvc = None
        engine.temperature = 0.8
        engine.speed = 1.08
        engine.expressive = True
        engine.ffmpeg = FFMPEG
        engine.generate_cache_file_name = Mock(return_value="unused-test.wav")
        engine.tts = Mock(sample_rate=48000)
        engine.tts.infer.return_value = np.ones(4800, dtype=np.float32) * 0.1
        return engine

    def test_direct_vieneu_calls_also_normalize_powers_before_inference(self):
        engine = self.engine()
        with patch.object(engine, "_adjust_speed", side_effect=lambda a, *_, **kw: a):
            self.assertEqual(engine.generate_audio("x²."), "unused-test.wav")
        self.assertEqual(engine.tts.infer.call_args.args[0], "ích mũ 2.")

    def test_reference_voice_stays_selected_and_native_cue_reaches_infer(self):
        engine = self.engine()
        with patch.object(
            engine, "_adjust_speed", side_effect=lambda audio, _, **kwargs: audio
        ):
            self.assertEqual(
                engine.generate_audio(
                    "[smirk] Bạn trêu mình à?",
                    prosody=plan_speech("[smirk] Câu vui [cười]?"),
                ),
                "unused-test.wav",
            )
        text = engine.tts.infer.call_args.args[0]
        self.assertEqual(text, "Bạn trêu mình à [cười]?")
        self.assertEqual(engine.tts.infer.call_args.kwargs["voice"], "Mỹ Duyên")
        self.assertNotIn("style", engine.tts.infer.call_args.kwargs)
        self.assertEqual(engine.speed, 1.08)  # no mutation shared by parallel tasks
        saved = engine.tts.save.call_args.args[0]
        self.assertEqual(len(saved), 4800 + round(48000 * 0.11))

    def test_unknown_cues_are_never_forwarded_as_emotion_commands(self):
        engine = self.engine()
        with patch.object(
            engine, "_adjust_speed", side_effect=lambda audio, _, **kwargs: audio
        ):
            engine.generate_audio(
                "[happy] Xin chào!", prosody=SpeechProsody(native_cue="happy")
            )
        self.assertEqual(engine.tts.infer.call_args.args[0], "Xin chào!")

    def test_installed_sdk_maps_whitelisted_cue_to_token_not_spoken_words(self):
        from vieneu_utils.phonemize_text import phonemize_text_with_emotions

        with patch(
            "vieneu_utils.phonemize_text._phonemize_cached",
            side_effect=lambda text, **_: text.strip(),
        ):
            phones = phonemize_text_with_emotions("Nghe vui quá [cười].")
        self.assertIn("<|emotion_1|>", phones)
        self.assertNotIn("cười", phones)

    @unittest.skipUnless(Path(FFMPEG).is_file(), "ffmpeg not installed")
    def test_gentle_tempo_preserves_pitch_and_original_base_speed(self):
        engine = self.engine()
        samples = np.arange(48000 * 2)
        audio = (0.2 * np.sin(2 * np.pi * 440 * samples / 48000)).astype(np.float32)
        speed = engine.speed * plan_speech("[sad] Mình đang nghe bạn.").tempo
        adjusted = engine._adjust_speed(audio, speed)
        frequencies = np.fft.rfftfreq(len(adjusted), 1 / 48000)
        peak = frequencies[np.argmax(np.abs(np.fft.rfft(adjusted)))]
        self.assertAlmostEqual(peak, 440, delta=2)
        self.assertAlmostEqual(len(audio) / len(adjusted), speed, delta=0.02)
        self.assertEqual(engine.speed, 1.08)


class ParagraphProsodyTests(unittest.TestCase):
    def test_distinct_reading_plans_match_emotion_and_never_invent_native_cues(self):
        bright = plan_speech("[joy] Hay quá!")
        shy = plan_speech("[shy] Mình hơi ngại đấy.")
        gentle = plan_speech("[sadness] Mình nghe bạn mà.")
        curious = plan_speech("[surprised] Ơ, chuyện gì vậy?")
        self.assertGreater(bright.tempo, 1)
        self.assertLess(gentle.tempo, shy.tempo)
        self.assertLess(shy.tempo, curious.tempo)
        self.assertGreater(shy.pause_ms, bright.pause_ms)
        for speech in (bright, shy, gentle, curious):
            self.assertIsNone(speech.native_cue)
            self.assertTrue(0.9 <= speech.tempo <= 1.1)
        self.assertEqual(plan_speech("Mao mắc cỡ rồi.").mood, "bashful")
        self.assertEqual(plan_speech("Tiếc quá, vòng này chưa ai đúng!").mood, "gentle")
        self.assertEqual(plan_speech("Chúc mừng Bắp nhé!").mood, "bright")
        self.assertEqual(plan_speech("Chào Bắp, ngồi chơi với Mao nha.").mood, "warm")

    def test_actual_mao_sadness_expression_selects_gentle_voice(self):
        self.assertEqual(plan_speech("[sadness] Bạn cứ nói tiếp nhé.").mood, "gentle")

    def test_mood_fades_after_two_followups_and_explicit_change_wins(self):
        planner = TurnSpeechPlanner()
        first = planner.plan("[sad] Mình đang nghe bạn.")
        second = planner.plan("Bạn cứ nói tiếp nhé.")
        third = planner.plan("Mình ở đây.")
        fourth = planner.plan("Đó là điều mình muốn nói.")
        self.assertEqual(first.tempo, second.tempo)
        self.assertGreater(third.tempo, second.tempo)
        self.assertEqual(fourth.mood, "neutral")
        planner.plan("[sad] Mình đang nghe bạn.")
        self.assertEqual(planner.plan("[joy] Hay quá!").mood, "bright")
        self.assertEqual(
            planner.plan("[neutral] Bây giờ sang phần khác.").mood, "neutral"
        )
        self.assertEqual(planner.plan("Một thông tin tiếp theo.").mood, "neutral")

    def test_solemn_subject_suppresses_accidental_laugh_and_followup_cue(self):
        planner = TurnSpeechPlanner()
        solemn = planner.plan("[joy] Mình tưởng niệm những người đã hy sinh [cười].")
        self.assertEqual(solemn.mood, "solemn")
        self.assertIsNone(solemn.native_cue)
        followup = planner.plan("Đó là điều mình luôn ghi nhớ [cười].")
        self.assertIsNone(followup.native_cue)
        self.assertEqual(followup.mood, "solemn")

    def test_pride_is_measured_and_does_not_force_laughter(self):
        speech = plan_speech("Mình tự hào về quê hương Việt Nam [cười].")
        self.assertEqual(speech.mood, "proud")
        self.assertIsNone(speech.native_cue)
        self.assertGreaterEqual(speech.tempo, 0.95)
