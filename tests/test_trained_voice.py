import base64
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from pydantic import ValidationError

from src.open_llm_vtuber.config_manager.tts import VieNeuTTSConfig
from src.open_llm_vtuber.tts.trained_voice import TrainedVoice
from src.open_llm_vtuber.tts.trained_voice_worker import synthesize
from src.open_llm_vtuber.tts.vieneu_tts import TTSEngine


class TrainedVoiceTests(unittest.TestCase):
    def test_explicit_codec_is_validated_without_loading_gpu(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("subprocess.Popen") as popen,
        ):
            settings = self.settings(directory)
            settings["codec_path"] = str(Path(directory) / "codec")
            with self.assertRaisesRegex(FileNotFoundError, "audio codec"):
                TrainedVoice(settings)
            Path(settings["codec_path"]).mkdir()
            (Path(settings["codec_path"]) / "config.json").touch()
            voice = TrainedVoice(settings)
            self.assertEqual(
                voice.settings["codec_path"],
                str(Path(settings["codec_path"]).resolve()),
            )
            voice.close()
            popen.assert_not_called()

    def settings(self, directory):
        root = Path(directory)
        (root / "python.exe").touch()
        model = root / "model"
        (model / "update").mkdir(parents=True)
        for name in (
            "config.json",
            "speaker_encoder.onnx",
            "denoiser.onnx",
            "update/config.json",
            "update/model.safetensors",
            "update/tokenizer.json",
        ):
            (model / name).touch()
        (model / "mao_emotion_tokens.json").write_text(
            json.dumps({"neutral": "<|emotion_8|>"})
        )
        (model / "voices_v3_turbo.json").write_text(
            json.dumps({"presets": {"Cold Queen · neutral": {}}})
        )
        return {
            "enabled": True,
            "python_path": str(root / "python.exe"),
            "model_path": str(model),
            "device": "cpu",
        }

    def test_configuration_and_close_never_start_a_worker(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("subprocess.Popen") as popen,
        ):
            voice = TrainedVoice(self.settings(directory))
            self.assertIsNone(voice._process)
            voice.close()
            voice.close()
            popen.assert_not_called()

    def test_missing_checkpoint_fails_without_starting_or_falling_back(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("subprocess.Popen") as popen,
        ):
            settings = self.settings(directory)
            (Path(settings["model_path"]) / "update/model.safetensors").unlink()
            with self.assertRaises(FileNotFoundError):
                TrainedVoice(settings)
            popen.assert_not_called()

    def test_schema_rejects_double_conversion_and_incompatible_mode(self):
        trained = {"enabled": True, "python_path": "python", "model_path": "model"}
        for extra in (
            {"rvc": {"enabled": True}},
            {"mode": "v3nano"},
            {"ref_audio": "reference.wav"},
        ):
            with self.assertRaises(ValidationError):
                VieNeuTTSConfig(trained_voice=trained, **extra)
        with self.assertRaises(ValidationError):
            VieNeuTTSConfig(trained_voice={"enabled": True})

    def test_pcm_response_and_request_use_the_same_sample_rate_and_emotion(self):
        with tempfile.TemporaryDirectory() as directory:
            voice = TrainedVoice(self.settings(directory))
            process = Mock(stdin=io.StringIO(), stdout=io.StringIO())
            process.poll.return_value = 0

            def start():
                voice._process = process
                process.poll.return_value = None

            voice._start = Mock(side_effect=start)
            audio = np.array([0.1, -0.2, 0], dtype="<f4")
            packet = {
                "audio": base64.b64encode(audio.tobytes()).decode(),
                "sample_rate": 48000,
            }
            voice._receive = Mock(return_value=packet)
            try:
                result = voice.infer("Xin chào.", temperature=0.7)
                np.testing.assert_array_equal(result, audio)
                request = json.loads(process.stdin.getvalue())
                self.assertEqual(request["emotion"], "neutral")
                self.assertEqual(request["temperature"], 0.7)
                voice._start.assert_called_once()
            finally:
                process.poll.return_value = 0
                voice.close()

    def test_timeout_closes_worker_and_cannot_reuse_a_late_response(self):
        with tempfile.TemporaryDirectory() as directory:
            voice = TrainedVoice(self.settings(directory))
            process = Mock(stdin=io.StringIO(), stdout=io.StringIO())
            process.poll.return_value = None
            voice._process = process
            voice._receive = Mock(side_effect=TimeoutError())
            with self.assertRaises(TimeoutError):
                voice.infer("Xin chào.")
            self.assertTrue(process.stdin.closed)
            self.assertIsNone(voice._process)
            with self.assertRaises(RuntimeError):
                voice.infer("Câu tiếp theo.")

    def test_windows_timeout_terminates_only_the_owned_process_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            voice = TrainedVoice(self.settings(directory))
            process = Mock(stdin=io.StringIO(), stdout=io.StringIO(), pid=123456)
            process.poll.return_value = None
            process.wait.side_effect = [subprocess.TimeoutExpired("worker", 5), 0]
            voice._process = process
            with (
                patch("src.open_llm_vtuber.tts.trained_voice.os.name", "nt"),
                patch("subprocess.run") as kill,
            ):
                voice.close()
            self.assertEqual(
                kill.call_args.args[0], ["taskkill", "/PID", "123456", "/T", "/F"]
            )

    def test_trained_engine_bypasses_base_model_and_keeps_preview_neutral(self):
        with (
            patch("src.open_llm_vtuber.tts.trained_voice.TrainedVoice") as factory,
            patch("src.open_llm_vtuber.tts.vieneu_tts.Vieneu") as base,
            patch("src.open_llm_vtuber.tts.rvc_converter.RVCConverter") as rvc,
        ):
            engine = TTSEngine(speed=1, trained_voice={"enabled": True})
            engine.generate_cache_file_name = Mock(return_value="unused.wav")
            factory.return_value.infer.return_value = np.ones(20, dtype=np.float32)
            factory.return_value.sample_rate = 48000
            from src.open_llm_vtuber.tts.prosody import SpeechProsody

            engine.generate_audio("Xin chào.", prosody=SpeechProsody(mood="warm"))
            self.assertEqual(
                factory.return_value.infer.call_args.kwargs["emotion"], "neutral"
            )
            base.assert_not_called()
            rvc.assert_not_called()
            engine.close()
            factory.return_value.close.assert_called_once()

    def test_every_internal_chunk_keeps_the_learned_token_and_no_reference_codes(self):
        parent = ModuleType("vieneu_utils")
        parent.__path__ = []
        phonemes = SimpleNamespace(
            normalize_to_chunks_v3_with_gaps=lambda *a, **k: (["một", "hai"], [1])
        )
        gaps = SimpleNamespace(
            gaps_to_silence=lambda value: [1], pause_pad_samples=lambda *a: 2
        )
        calls, closed = [], []

        class FakeTTS:
            sample_rate = 48000

            def infer_stream(self, text, **kwargs):
                calls.append((text, kwargs))
                try:
                    yield np.ones(4, dtype=np.float32)
                finally:
                    closed.append(True)

        with patch.dict(
            "sys.modules",
            {
                "vieneu_utils": parent,
                "vieneu_utils.phonemize_text": phonemes,
                "vieneu_utils.core_utils": gaps,
            },
        ):
            audio = synthesize(
                FakeTTS(), "Nội dung.", "neutral", {"neutral": "<|emotion_8|>"}, 0.7
            )
        self.assertEqual(
            [x[0] for x in calls], ["<|emotion_8|> một", "<|emotion_8|> hai"]
        )
        self.assertTrue(all(x[1]["use_ref_codes"] is False for x in calls))
        self.assertEqual(len(audio), 10)
        self.assertEqual(len(closed), 2)
