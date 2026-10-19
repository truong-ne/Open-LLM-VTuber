import shutil
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from pydantic import ValidationError

from src.open_llm_vtuber.config_manager.tts import VieNeuTTSConfig
from src.open_llm_vtuber.tts.vieneu_tts import TTSEngine


FFMPEG = shutil.which("ffmpeg") or str(
    Path(__file__).resolve().parents[1]
    / "private/tools/ffmpeg/ffmpeg-master-latest-win64-lgpl-shared/bin/ffmpeg.exe"
)


class VieNeuSpeedTests(unittest.TestCase):
    def engine(self, speed):
        engine = TTSEngine.__new__(TTSEngine)
        engine.speed = speed
        engine.ffmpeg = FFMPEG
        engine.tts = SimpleNamespace(sample_rate=48000)
        return engine

    def test_normal_speed_keeps_the_original_audio(self):
        audio = np.zeros(48000, dtype=np.float32)
        with patch("subprocess.run") as run:
            self.assertIs(self.engine(1)._adjust_speed(audio), audio)
        run.assert_not_called()

    @unittest.skipUnless(Path(FFMPEG).is_file(), "ffmpeg not installed")
    def test_eight_percent_faster_shortens_audio_without_raising_pitch(self):
        samples = np.arange(48000 * 3)
        audio = (0.2 * np.sin(2 * np.pi * 440 * samples / 48000)).astype(np.float32)
        adjusted = self.engine(1.08)._adjust_speed(audio)
        self.assertAlmostEqual(len(audio) / len(adjusted), 1.08, delta=0.015)
        frequencies = np.fft.rfftfreq(len(adjusted), 1 / 48000)
        peak = frequencies[np.argmax(np.abs(np.fft.rfft(adjusted)))]
        self.assertAlmostEqual(peak, 440, delta=2)

    def test_failed_or_empty_filter_does_not_silently_report_success(self):
        for result in (subprocess.CompletedProcess([], 0, stdout=b""),):
            with patch("subprocess.run", return_value=result):
                with self.assertRaises(RuntimeError):
                    self.engine(1.08)._adjust_speed(np.ones(48000))
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 30)
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.engine(1.08)._adjust_speed(np.ones(48000))

    def test_config_rejects_unreasonable_speeds_and_needs_ffmpeg_only_when_used(self):
        for speed in (0, 2, float("nan")):
            with self.subTest(speed=speed), self.assertRaises(ValidationError):
                VieNeuTTSConfig(speed=speed)
        with patch(
            "src.open_llm_vtuber.tts.vieneu_tts.shutil.which", return_value=None
        ):
            with self.assertRaises(FileNotFoundError):
                TTSEngine(speed=1.08)
            with patch(
                "src.open_llm_vtuber.tts.vieneu_tts.Vieneu", return_value=Mock()
            ):
                self.assertEqual(TTSEngine(speed=1).speed, 1)


if __name__ == "__main__":
    unittest.main()
