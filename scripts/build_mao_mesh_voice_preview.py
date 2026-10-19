"""Generate one local VieNeu sample for the Draco preview page, never the live queue."""
from pathlib import Path
import os
import sys
import yaml

root = Path(__file__).resolve().parent.parent
os.environ["HF_HOME"] = str(root / "models")
os.environ["HF_HUB_OFFLINE"] = "1"
import imageio_ffmpeg  # noqa: E402
sys.path.insert(0, str(root / "src"))
from open_llm_vtuber.tts.vieneu_tts import TTSEngine  # noqa: E402
from open_llm_vtuber.tts.prosody import SpeechProsody  # noqa: E402

settings = yaml.safe_load((root / "conf.yaml").read_text(encoding="utf-8"))
voice = settings["character_config"]["tts_config"]["vieneu_tts"]
engine = TTSEngine(**{**voice, "speed": 1.0})
engine.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
engine.speed = voice["speed"]
target = root / "web_tool/mao-5070/voice-preview"
result = engine.generate_audio(
    "Hi bạn! Mao đang thử bộ chuyển động mới đây. Mình có thể chớp mắt, mỉm cười và vẫy tay chào bạn rồi nè.",
    str(target),
    SpeechProsody(mood="joy", tempo=1.02),
)
if not result:
    raise SystemExit("VieNeu did not generate the preview")
print(result)
