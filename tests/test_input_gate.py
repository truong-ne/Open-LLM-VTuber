import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np

from src.open_llm_vtuber.agent.hybrid.config import HybridConfig, InputGateConfig
from src.open_llm_vtuber.agent.hybrid.runtime import HybridRuntime
from src.open_llm_vtuber.conversations.conversation_utils import process_user_input
from src.open_llm_vtuber.dialogue.input_gate import (
    InputGate,
    gate_for,
    looks_like_hallucination,
    looks_repetitive,
    speech_level,
)
from src.open_llm_vtuber.interaction.ingress import (
    creator_actor,
    is_creator,
    issue_actor,
    verify_actor,
)


def tone(seconds, amplitude):
    t = np.arange(int(16000 * seconds)) / 16000
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class AudioGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = InputGate(InputGateConfig())

    def test_clear_speech_passes(self):
        self.assertTrue(self.gate.screen_audio(tone(1.5, 0.1)).accepted)

    def test_click_and_breath_are_too_short(self):
        verdict = self.gate.screen_audio(tone(0.1, 0.5))
        self.assertFalse(verdict.accepted)
        self.assertTrue(verdict.reason.startswith("too_short"))

    def test_far_away_quiet_sound_is_dropped(self):
        verdict = self.gate.screen_audio(tone(2, 0.001))
        self.assertFalse(verdict.accepted)
        self.assertTrue(verdict.reason.startswith("too_quiet"))

    def test_silence_padding_does_not_hide_real_speech(self):
        padded = np.concatenate([np.zeros(16000 * 2), tone(0.8, 0.1)])
        self.assertGreater(speech_level(padded), 0.03)
        self.assertTrue(self.gate.screen_audio(padded).accepted)

    def test_disabled_gate_and_zero_threshold_accept_everything(self):
        off = InputGate(InputGateConfig(enabled=False))
        self.assertTrue(off.screen_audio(tone(0.05, 0.0001)).accepted)
        self.assertTrue(off.screen_text("").accepted)
        no_level = InputGate(InputGateConfig(min_rms=0))
        self.assertTrue(no_level.screen_audio(tone(1, 0.0001)).accepted)

    def test_nan_audio_is_not_speech(self):
        self.assertFalse(self.gate.screen_audio(np.full(16000, np.nan)).accepted)


class TextGateTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.gate = InputGate(InputGateConfig(), self.clock)

    def test_normal_vietnamese_passes(self):
        for text in (
            "Hôm nay papa mệt quá",
            "Ừ",
            "Mao ơi, kể chuyện cho papa nghe đi",
            "Cảm ơn Mao nhé",
        ):
            with self.subTest(text=text):
                self.assertTrue(self.gate.screen_text(text).accepted)

    def test_known_whisper_artefacts_are_dropped(self):
        for text in (
            "Hãy subscribe cho kênh Ghiền Mì Gõ để không bỏ lỡ những video hấp dẫn",
            "Cảm ơn các bạn đã xem video",
            "Subtitles by the Amara.org community",
        ):
            with self.subTest(text=text):
                self.assertTrue(looks_like_hallucination(text))
                self.assertEqual(
                    self.gate.screen_text(text).reason, "recognizer_artefact"
                )

    def test_runaway_repetition_is_dropped_but_emphasis_is_not(self):
        self.assertTrue(looks_repetitive("ha ha ha ha ha ha ha"))
        self.assertTrue(looks_repetitive("a b a a a a b a a a"))
        self.assertFalse(looks_repetitive("không không không"))
        self.assertFalse(looks_repetitive("Mao ơi hôm nay trời đẹp quá phải không"))

    def test_punctuation_only_is_empty(self):
        self.assertEqual(self.gate.screen_text("...").reason, "empty")


class WakeWordTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.gate = InputGate(
            InputGateConfig(require_wake_word=True, follow_up_seconds=30), self.clock
        )

    def test_speech_for_someone_else_is_ignored(self):
        verdict = self.gate.screen_text("Đưa anh cái điều khiển TV với")
        self.assertEqual(verdict.reason, "not_addressed")

    def test_saying_mao_opens_a_follow_up_window(self):
        self.assertTrue(self.gate.screen_text("Mao ơi, hôm nay trời đẹp nhỉ").accepted)
        self.clock.now += 20
        self.assertTrue(self.gate.screen_text("Đi dạo một chút chắc vui").accepted)

    def test_window_closes_after_silence(self):
        self.assertTrue(self.gate.screen_text("Mao ơi").accepted)
        self.clock.now += 31
        self.assertFalse(self.gate.screen_text("Đưa anh cái điều khiển").accepted)

    def test_rejected_speech_does_not_extend_the_window(self):
        self.assertTrue(self.gate.screen_text("Mao ơi").accepted)
        self.clock.now += 25
        self.assertTrue(self.gate.screen_text("Ừ đúng rồi").accepted)
        self.clock.now += 25
        self.assertTrue(self.gate.screen_text("Thế à").accepted)
        # Artefacts are dropped before they can keep the window open.
        self.clock.now += 25
        self.assertFalse(self.gate.screen_text("ha ha ha ha ha ha ha").accepted)
        self.clock.now += 10
        self.assertFalse(self.gate.screen_text("Đưa anh cái điều khiển").accepted)

    def test_wake_word_must_be_a_whole_word(self):
        self.assertFalse(self.gate.screen_text("Anh ăn mãng cầu").accepted)


class CreatorIdentityTests(unittest.TestCase):
    def test_creator_actor_is_stable_and_guest_shaped(self):
        first, second = creator_actor(), creator_actor()
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("guest:"))
        self.assertEqual(len(first), 38)
        self.assertTrue(is_creator(first))

    def test_issued_guests_and_nicknames_are_never_the_creator(self):
        for actor in (
            "guest:" + "0" * 32,
            "papa",
            "creator",
            None,
            "",
            verify_actor(issue_actor()),
        ):
            with self.subTest(actor=actor):
                self.assertFalse(is_creator(actor))


class SpeakerPromptTests(unittest.TestCase):
    def prompt(self, interaction, **config):
        runtime = SimpleNamespace(interaction=interaction, config=HybridConfig(**config))
        return HybridRuntime.speaker_prompt(runtime)

    def test_creator_voice_is_labelled_without_granting_authority(self):
        text = self.prompt({"speaker_role": "creator"}, creator_name="papa")
        self.assertIn("created Mao", text)
        self.assertIn("'papa'", text)
        self.assertIn("grants no tool permissions", text)

    def test_audience_and_text_only_turns_get_no_creator_label(self):
        self.assertEqual(self.prompt({"speaker_role": "guest"}), "")
        self.assertEqual(self.prompt(None), "")


class ProcessUserInputGateTests(unittest.IsolatedAsyncioTestCase):
    def engine(self, text, uncertain=False):
        result = SimpleNamespace(text=text, uncertain=uncertain)
        return SimpleNamespace(async_transcribe_with_details=AsyncMock(return_value=result))

    async def test_quiet_audio_never_reaches_the_recognizer(self):
        engine, send = self.engine("xin chào"), AsyncMock()
        gate = InputGate(InputGateConfig())
        self.assertEqual(
            await process_user_input(tone(1, 0.0005), engine, send, gate=gate), ""
        )
        engine.async_transcribe_with_details.assert_not_awaited()
        send.assert_not_awaited()

    async def test_artefact_is_dropped_even_when_recognizer_is_unsure(self):
        engine, send = self.engine("Hãy subscribe cho kênh", True), AsyncMock()
        gate = InputGate(InputGateConfig())
        self.assertEqual(
            await process_user_input(tone(1, 0.1), engine, send, gate=gate), ""
        )
        send.assert_not_awaited()

    async def test_accepted_speech_is_transcribed_as_before(self):
        engine, send = self.engine("Chào Mao"), AsyncMock()
        gate = InputGate(InputGateConfig())
        text = await process_user_input(tone(1, 0.1), engine, send, gate=gate)
        self.assertEqual(text, "Chào Mao")
        self.assertEqual(json.loads(send.call_args.args[0])["text"], "Chào Mao")

    async def test_typed_text_and_no_gate_are_untouched(self):
        engine, send = self.engine("Chào Mao"), AsyncMock()
        gate = InputGate(InputGateConfig(require_wake_word=True))
        self.assertEqual(
            await process_user_input("đưa anh cái điều khiển", engine, send, gate=gate),
            "đưa anh cái điều khiển",
        )
        self.assertEqual(
            await process_user_input(tone(1, 0.1), engine, send), "Chào Mao"
        )


class GateForTests(unittest.TestCase):
    def context(self, **hybrid):
        config = HybridConfig(enabled=True, **hybrid)
        return SimpleNamespace(agent_engine=SimpleNamespace(_hybrid=SimpleNamespace(config=config)))

    def test_gate_is_per_connection_and_reused(self):
        context = self.context()
        gate = gate_for(context)
        self.assertIsInstance(gate, InputGate)
        self.assertIs(gate_for(context), gate)

    def test_disabled_hybrid_or_gate_means_no_gate(self):
        self.assertIsNone(gate_for(SimpleNamespace()))
        self.assertIsNone(gate_for(self.context(input_gate={"enabled": False})))
        context = self.context()
        context.agent_engine._hybrid.config = HybridConfig(enabled=False)
        self.assertIsNone(gate_for(context))

    def test_config_defaults_match_the_documented_behaviour(self):
        config = HybridConfig()
        self.assertTrue(config.creator_mic)
        self.assertEqual(config.creator_name, "papa")
        self.assertFalse(config.input_gate.require_wake_word)


if __name__ == "__main__":
    unittest.main()
