import io
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
from pydantic import ValidationError

from src.open_llm_vtuber.config_manager.tts import RVCConfig, VieNeuTTSConfig
from src.open_llm_vtuber.tts.rvc_converter import RVCConverter
from src.open_llm_vtuber.tts.vieneu_tts import TTSEngine


class RVCVoiceTests(unittest.TestCase):
    def test_disabled_stage_does_not_start_cuda_or_change_base_engine(self):
        self.assertFalse(VieNeuTTSConfig().rvc.enabled)
        with (
            patch("src.open_llm_vtuber.tts.vieneu_tts.Vieneu", return_value=Mock()),
            patch("src.open_llm_vtuber.tts.rvc_converter.RVCConverter") as worker,
        ):
            engine = TTSEngine(rvc={"enabled": False})
        self.assertIsNone(engine.rvc)
        worker.assert_not_called()
        for values in (
            {"index_rate": 2},
            {"protect": -1},
            {"pitch": 30},
            {"timeout": 0},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                RVCConfig(**values)

    def test_converted_audio_uses_40k_rate_for_pauses_tempo_and_saved_wav(self):
        engine = TTSEngine.__new__(TTSEngine)
        engine.mode, engine.voice, engine.ref_audio = "v3turbo", "Mỹ Duyên", None
        engine.temperature, engine.speed, engine.expressive, engine.ffmpeg = (
            0.8,
            1.0,
            True,
            None,
        )
        engine.tts = Mock(sample_rate=48000)
        engine.tts.infer.return_value = np.ones(48000, dtype=np.float32) * 0.1
        engine.rvc = Mock()
        engine.rvc.convert.return_value = (
            np.ones(40000, dtype=np.float32) * 0.2,
            40000,
        )
        speech = SimpleNamespace(
            native_cue=None, tempo=1.0, pause_ms=100, mood="neutral"
        )
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / "voice.wav")
            engine.generate_cache_file_name = Mock(return_value=target)
            with patch.object(
                engine, "_adjust_speed", wraps=engine._adjust_speed
            ) as tempo:
                self.assertEqual(
                    engine.generate_audio("Xin chào!", prosody=speech), target
                )
            tempo.assert_called_once()
            self.assertEqual(tempo.call_args.kwargs["sample_rate"], 40000)
            audio, rate = sf.read(target)
            self.assertEqual(rate, 40000)
            self.assertEqual(len(audio), 44000)
            self.assertTrue(np.all(audio[-4000:] == 0))
        engine.tts.save.assert_not_called()

    def test_timeout_stops_worker_so_old_response_cannot_become_next_sentence(self):
        converter = RVCConverter.__new__(RVCConverter)
        converter._lock = threading.Lock()
        converter._responses = queue.Queue()
        converter.timeout = 0.001
        converter._process = Mock(stdin=io.StringIO())
        converter._process.poll.return_value = None
        converter.close = Mock()
        with self.assertRaises(TimeoutError):
            converter.convert(np.ones(1600, dtype=np.float32), 16000)
        converter.close.assert_called_once()

    def test_invalid_audio_is_rejected_before_sending_to_worker(self):
        converter = RVCConverter.__new__(RVCConverter)
        for audio in (
            np.array([]),
            np.array([np.nan]),
            np.array([np.inf]),
            np.ones((2, 10)),
        ):
            with self.subTest(audio=audio), self.assertRaises(ValueError):
                converter.convert(audio, 48000)

    def test_bad_sample_rate_is_rejected_before_using_worker(self):
        converter = RVCConverter.__new__(RVCConverter)
        for rate in (0, -1, 7999, 500000, float("nan")):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                converter.convert(np.ones(1600, dtype=np.float32), rate)

    def test_close_releases_pipes_log_and_exit_hook_and_can_run_twice(self):
        converter = RVCConverter.__new__(RVCConverter)
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO())
        process.poll.return_value = 0
        log = io.StringIO()
        converter._process = process
        converter._log = log
        converter._reader = Mock()
        with patch(
            "src.open_llm_vtuber.tts.rvc_converter.atexit.unregister"
        ) as unregister:
            converter.close()
            converter.close()
        unregister.assert_any_call(converter.close)
        self.assertTrue(process.stdin.closed)
        self.assertTrue(process.stdout.closed)
        self.assertTrue(log.closed)
        self.assertIsNone(converter._process)
        converter._reader.join.assert_called_once()

    def test_broken_pipe_closes_worker_instead_of_leaking_gpu_process(self):
        converter = RVCConverter.__new__(RVCConverter)
        converter._lock = threading.Lock()
        converter._process = Mock()
        converter._process.poll.return_value = None
        converter._process.stdin.write.side_effect = BrokenPipeError("worker exited")
        converter.close = Mock()
        with self.assertRaises(BrokenPipeError):
            converter.convert(np.ones(1600, dtype=np.float32), 16000)
        converter.close.assert_called_once()
