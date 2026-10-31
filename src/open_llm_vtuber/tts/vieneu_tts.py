import os
import shutil
import subprocess
import asyncio
import re

import numpy as np

from loguru import logger
from .tts_interface import TTSInterface
from .prosody import SpeechProsody, NATIVE_CUES
from ..utils.math_speech import normalize_vietnamese_math

try:
    from vieneu import Vieneu

    VIENEU_AVAILABLE = True
except ImportError:
    VIENEU_AVAILABLE = False
    logger.warning("vieneu not installed. Run: uv pip install vieneu")


# VieNeu-TTS: Vietnamese (and English) TTS with preset voices and voice cloning.
# https://github.com/pnnbao97/VieNeu-TTS (Apache-2.0)
# - mode 'v3turbo': 48 kHz. Runs on CPU via ONNX Runtime without torch, or on an
#   NVIDIA GPU via PyTorch (~1 GB VRAM). Models are downloaded from Hugging Face
#   on first use.
# - mode 'v3nano': 24 kHz, ONNX/CPU only, for weak CPUs.
# Preset voices (v3turbo) include e.g. 'Trúc Ly', 'Đoan Trang', 'Ngọc Huyền'
# (female) and 'Hải Đăng', 'Adam' (male).


class TTSEngine(TTSInterface):
    supports_prosody = True

    def __init__(
        self,
        mode: str = "v3turbo",
        voice: str = "",
        ref_audio: str = "",
        backend: str = "auto",
        device: str = "auto",
        precision: str = "fp32",
        threads: int = 0,
        temperature: float = 0.8,
        speed: float = 1.0,
        expressive: bool = True,
        rvc: dict | None = None,
        trained_voice: dict | None = None,
    ):
        """Initializes the VieNeu-TTS engine using the Python API.

        Args:
            mode: 'v3turbo' (best quality) or 'v3nano' (lighter, CPU only).
            voice: Preset voice name. Empty uses the model's default voice.
            ref_audio: Path to a 3-8 s clip to clone; overrides `voice` when set.
            backend: 'auto' (ONNX on CPU, PyTorch on GPU), 'onnx' or 'pytorch'.
            device: 'auto', 'cpu' or 'cuda'.
            precision: ONNX/CPU precision, 'fp32' or 'int8' (faster, needs a CPU with VNNI).
            threads: ONNX/CPU threads, 0 = automatic.
            temperature: Sampling temperature (v3turbo).
            speed: Speech tempo multiplier, preserving pitch (requires ffmpeg).
        """
        trained = bool(trained_voice and trained_voice.get("enabled"))
        if not VIENEU_AVAILABLE and not trained:
            raise ImportError("vieneu is required. Install with: uv pip install vieneu")

        self.mode = mode
        self.voice = voice or None
        self.ref_audio = ref_audio or None
        self.temperature = temperature
        if not 0.75 <= speed <= 1.5:
            raise ValueError("VieNeu speech speed must be between 0.75 and 1.5")
        self.speed = speed
        self.expressive = expressive
        self.rvc = None
        self.trained_voice = trained
        self.trained_emotions = bool(
            trained_voice and trained_voice.get("emotion_control")
        )
        self.ffmpeg = shutil.which("ffmpeg")
        if speed != 1.0 and not self.ffmpeg:
            raise FileNotFoundError("ffmpeg is required to adjust VieNeu speech speed")

        if self.ref_audio and not os.path.exists(self.ref_audio):
            raise FileNotFoundError(
                f"VieNeu reference audio not found: {self.ref_audio}"
            )

        try:
            if trained:
                if mode != "v3turbo" or self.ref_audio or (rvc and rvc.get("enabled")):
                    raise ValueError(
                        "Trained voice cannot be combined with RVC or reference audio"
                    )
                from .trained_voice import TrainedVoice

                self.tts = TrainedVoice(trained_voice)
                logger.info("Trained Mao voice configured; model loads on first speech")
                return
            logger.info(
                f"Loading VieNeu-TTS ({mode}, backend={backend}, device={device})"
            )
            self.tts = Vieneu(
                mode=mode,
                backend=backend,
                device=device,
                precision=precision,
                threads=threads,
            )
            if rvc and rvc.get("enabled"):
                from .rvc_converter import RVCConverter

                self.rvc = RVCConverter(rvc)
            logger.info(
                "VieNeu-TTS loaded: voice={}, speed={}x", self.voice, self.speed
            )
        except Exception as e:
            logger.critical(f"Failed to load VieNeu-TTS: {e}")
            raise

    def generate_audio(
        self,
        text: str,
        file_name_no_ext: str | None = None,
        prosody: SpeechProsody | None = None,
    ) -> str | None:
        """Generates a speech audio file using VieNeu-TTS.

        Args:
            text: The text to convert to speech.
            file_name_no_ext: The name of the file without the extension. Defaults to None.

        Returns:
            The path to the generated audio file, or None on failure.
        """
        file_name = self.generate_cache_file_name(file_name_no_ext, "wav")

        kwargs = {}
        if self.ref_audio:
            kwargs["ref_audio"] = self.ref_audio
        elif self.voice:
            kwargs["voice"] = self.voice
        if self.mode == "v3turbo":
            kwargs["temperature"] = self.temperature
        if getattr(self, "trained_voice", False):
            # Neutral is the user-approved preview. Learned expressive labels
            # remain opt-in; normal prosody tempo and pauses still apply below.
            kwargs["emotion"] = (
                {
                    "bright": "happy",
                    "warm": "happy",
                    "playful": "happy",
                    "solemn": "sad",
                }.get(prosody.mood, "neutral")
                if self.trained_emotions and self.expressive and prosody
                else "neutral"
            )

        try:
            text = normalize_vietnamese_math(text)
            speed = self.speed
            pause_ms = 0
            if self.expressive and prosody:
                # VieNeu v3's `style` parameter is ignored. Its three native
                # non-verbal cues work through inline text, not arbitrary labels.
                text = re.sub(r"\[[^\[\]]*\]", "", text).strip()
                if self.mode == "v3turbo" and prosody.native_cue in NATIVE_CUES:
                    ending = re.search(r"[.!?…]+$", text)
                    if ending:
                        text = (
                            text[: ending.start()].rstrip()
                            + f" [{prosody.native_cue}]"
                            + ending.group()
                        )
                    else:
                        text += f" [{prosody.native_cue}]."
                if self.ffmpeg:
                    speed = min(1.5, max(0.75, self.speed * prosody.tempo))
                pause_ms = max(0, min(200, prosody.pause_ms))
                logger.debug(
                    "VieNeu prosody: mood={}, tempo={}x, pause={}ms, native_cue={}",
                    prosody.mood,
                    round(speed, 3),
                    pause_ms,
                    prosody.native_cue,
                )
            audio = self.tts.infer(text, **kwargs)
            if audio is None or len(audio) == 0:
                logger.warning(f"VieNeu-TTS produced no audio for: {text!r}")
                return None
            sample_rate = self.tts.sample_rate
            if self.rvc is not None:
                audio, sample_rate = self.rvc.convert(audio, sample_rate)
            audio = self._adjust_speed(audio, speed, sample_rate=sample_rate)
            if pause_ms:
                audio = np.concatenate(
                    (
                        audio,
                        np.zeros(
                            round(sample_rate * pause_ms / 1000),
                            dtype=np.float32,
                        ),
                    )
                )
            if self.rvc is not None:
                import soundfile as sf

                sf.write(file_name, audio, sample_rate, subtype="PCM_16")
            else:
                self.tts.save(audio, file_name)
            logger.info(f"Generated audio file: {file_name}")
            return file_name
        except Exception as e:
            logger.critical(f"Error: VieNeu-TTS unable to generate audio: {e}")
            return None

    async def async_generate_audio(self, text, file_name_no_ext=None, prosody=None):
        return await asyncio.to_thread(
            self.generate_audio, text, file_name_no_ext, prosody
        )

    def close(self):
        if getattr(self, "trained_voice", False):
            self.tts.close()

    def _adjust_speed(
        self, audio: np.ndarray, speed=None, sample_rate=None
    ) -> np.ndarray:
        speed = self.speed if speed is None else speed
        if speed == 1.0:
            return audio
        # Filter in memory at the original sample rate; no extra audio files.
        result = subprocess.run(
            [
                self.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "f32le",
                "-ar",
                str(sample_rate or self.tts.sample_rate),
                "-ac",
                "1",
                "-i",
                "pipe:0",
                "-af",
                f"atempo={speed}",
                "-f",
                "f32le",
                "pipe:1",
            ],
            input=np.asarray(audio, dtype="<f4").tobytes(),
            capture_output=True,
            check=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        adjusted = np.frombuffer(result.stdout, dtype="<f4").copy()
        if not adjusted.size:
            raise RuntimeError("VieNeu tempo adjustment produced no audio")
        return adjusted
