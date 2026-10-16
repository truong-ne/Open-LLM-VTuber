import os

from loguru import logger
from .tts_interface import TTSInterface

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
        """
        if not VIENEU_AVAILABLE:
            raise ImportError("vieneu is required. Install with: uv pip install vieneu")

        self.mode = mode
        self.voice = voice or None
        self.ref_audio = ref_audio or None
        self.temperature = temperature

        if self.ref_audio and not os.path.exists(self.ref_audio):
            raise FileNotFoundError(
                f"VieNeu reference audio not found: {self.ref_audio}"
            )

        try:
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
            logger.info("VieNeu-TTS loaded successfully")
        except Exception as e:
            logger.critical(f"Failed to load VieNeu-TTS: {e}")
            raise

    def generate_audio(
        self, text: str, file_name_no_ext: str | None = None
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

        try:
            audio = self.tts.infer(text, **kwargs)
            if audio is None or len(audio) == 0:
                logger.warning(f"VieNeu-TTS produced no audio for: {text!r}")
                return None
            self.tts.save(audio, file_name)
            logger.info(f"Generated audio file: {file_name}")
            return file_name
        except Exception as e:
            logger.critical(f"Error: VieNeu-TTS unable to generate audio: {e}")
            return None
