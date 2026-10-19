import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from src.open_llm_vtuber.asr.faster_whisper_asr import (
    RecognitionResult,
    VoiceRecognition,
)
from src.open_llm_vtuber.conversations.conversation_utils import process_user_input
from src.open_llm_vtuber.conversations.single_conversation import (
    process_single_conversation,
)
from src.open_llm_vtuber.websocket_handler import WebSocketHandler


class RecognitionTests(unittest.TestCase):
    def setUp(self):
        with patch("src.open_llm_vtuber.asr.faster_whisper_asr.WhisperModel"):
            self.engine = VoiceRecognition(language="vi", device="cpu")
        self.audio = np.ones(16000, dtype=np.float32) * 0.1

    @staticmethod
    def segment(text, confidence=-0.1, silence=0.01, compression=1.1):
        return SimpleNamespace(
            text=text,
            start=0,
            end=1,
            avg_logprob=confidence,
            no_speech_prob=silence,
            compression_ratio=compression,
        )

    def test_clear_vietnamese_preserves_words_and_separates_segments(self):
        self.engine.model.transcribe.return_value = (
            iter([self.segment(" Mình là người"), self.segment(" tạo ra bạn.")]),
            None,
        )
        result = self.engine.transcribe_with_details(self.audio)
        self.assertEqual(result, RecognitionResult("Mình là người tạo ra bạn."))
        options = self.engine.model.transcribe.call_args.kwargs
        self.assertEqual(options["language"], "vi")
        self.assertEqual(options["task"], "transcribe")
        self.assertFalse(options["condition_on_previous_text"])

    def test_silence_invalid_and_accidental_short_buffers_do_not_hallucinate(self):
        for audio in (
            np.array([]),
            np.zeros(16000),
            np.ones(100),
            np.full(16000, np.nan),
        ):
            with self.subTest(samples=len(audio)):
                self.assertEqual(self.engine.transcribe_with_details(audio).text, "")
        self.engine.model.transcribe.assert_not_called()

    def test_low_confidence_noise_or_repetition_requires_clarification(self):
        for segment in (
            self.segment("nghe nhầm", confidence=-0.95),
            self.segment("nhiễu", confidence=-0.6, silence=0.9),
            self.segment("lặp lặp lặp", compression=3),
        ):
            self.engine.model.transcribe.return_value = (iter([segment]), None)
            self.assertTrue(self.engine.transcribe_with_details(self.audio).uncertain)


class SpeechInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_vad_pcm_reaches_recognizer_at_correct_volume(self):
        pcm = np.tile(np.array([16384, -16384], dtype=np.int16), 512)
        context = SimpleNamespace(vad_engine=Mock())
        context.vad_engine.detect_speech.return_value = iter([pcm.tobytes()])
        handler = SimpleNamespace(
            client_contexts={"mic": context},
            received_data_buffers={"mic": np.array([], dtype=np.float32)},
        )
        await WebSocketHandler._handle_raw_audio_data(
            handler, SimpleNamespace(send_text=AsyncMock()), "mic", {"audio": [1]}
        )
        np.testing.assert_allclose(
            handler.received_data_buffers["mic"], pcm.astype(np.float32) / 32768
        )

    async def test_uncertain_words_are_shown_but_not_treated_as_user_claims(self):
        engine = SimpleNamespace(
            async_transcribe_with_details=AsyncMock(
                return_value=RecognitionResult("người ta ra bắt", True)
            )
        )
        send = AsyncMock()
        text = await process_user_input(np.ones(16000), engine, send)
        self.assertIn("nhắc lại", text)
        self.assertNotIn("người ta ra bắt", text)
        event = json.loads(send.call_args.args[0])
        self.assertEqual(event["text"], "người ta ra bắt")
        self.assertTrue(event["uncertain"])

    async def test_other_asr_providers_and_typed_input_still_work(self):
        engine = SimpleNamespace(async_transcribe_np=AsyncMock(return_value="Chào Mao"))
        send = AsyncMock()
        self.assertEqual(
            await process_user_input(np.ones(16000), engine, send), "Chào Mao"
        )
        self.assertEqual(
            await process_user_input("Mình đang nói", engine, send), "Mình đang nói"
        )
        engine.async_transcribe_np.assert_awaited_once()

    async def test_silent_turn_releases_queue_without_calling_language_model(self):
        context = SimpleNamespace(
            asr_engine=SimpleNamespace(
                async_transcribe_with_details=AsyncMock(
                    return_value=RecognitionResult("")
                )
            ),
            agent_engine=Mock(),
        )
        send = AsyncMock()
        result = await process_single_conversation(
            context, send, "silent-client", np.zeros(16000)
        )
        self.assertEqual(result, "")
        context.agent_engine.chat.assert_not_called()
        self.assertEqual(
            json.loads(send.call_args.args[0])["text"], "conversation-chain-end"
        )


if __name__ == "__main__":
    unittest.main()
