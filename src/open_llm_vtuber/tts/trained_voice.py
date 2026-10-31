"""Lazy trained-voice worker; configuring this adapter never loads a GPU model."""

import atexit
import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


class TrainedVoice:
    sample_rate = 48000

    def __init__(self, settings):
        self.settings = dict(settings)
        for key in ("python_path", "model_path"):
            path = Path(self.settings.get(key, ""))
            if not self.settings.get(key):
                raise ValueError(f"Trained voice {key} is required")
            path = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
            if not path.exists():
                raise FileNotFoundError(f"Trained voice {key} not found: {path}")
            self.settings[key] = str(path)
        if not Path(self.settings["python_path"]).is_file():
            raise ValueError("Trained voice Python must be an executable file")
        model = Path(self.settings["model_path"])
        if self.settings.get("codec_path"):
            codec = Path(self.settings["codec_path"]).expanduser()
            codec = (
                (ROOT / codec).resolve() if not codec.is_absolute() else codec.resolve()
            )
            if not (codec / "config.json").is_file():
                raise FileNotFoundError(f"Trained voice audio codec not found: {codec}")
            self.settings["codec_path"] = str(codec)
        for name in (
            "config.json",
            "voices_v3_turbo.json",
            "mao_emotion_tokens.json",
            "speaker_encoder.onnx",
            "denoiser.onnx",
            "update/config.json",
            "update/model.safetensors",
            "update/tokenizer.json",
        ):
            if not (model / name).is_file():
                raise FileNotFoundError(
                    f"Trained voice checkpoint is incomplete: {name}"
                )
        self.tokens = json.loads(
            (model / "mao_emotion_tokens.json").read_text(encoding="utf-8")
        )
        presets = json.loads(
            (model / "voices_v3_turbo.json").read_text(encoding="utf-8")
        )["presets"]
        if "neutral" not in self.tokens or any(
            "Cold Queen · " + key not in presets for key in self.tokens
        ):
            raise ValueError("Trained voice presets do not match its emotion tokens")
        self._lock = threading.Lock()
        self._responses = queue.Queue()
        self._process = self._log = self._reader = None
        self._closed = False
        atexit.register(self.close)

    def _read(self, process):
        try:
            for line in process.stdout:
                self._responses.put(json.loads(line))
        except Exception:
            self._responses.put({"error": "Invalid trained voice worker protocol"})
        finally:
            self._responses.put({"error": "Trained voice worker exited"})

    def _receive(self, timeout):
        try:
            packet = self._responses.get(timeout=timeout)
        except queue.Empty as error:
            raise TimeoutError(
                "Trained voice worker timed out; see logs/trained-voice-worker.log"
            ) from error
        if not isinstance(packet, dict) or packet.get("error"):
            raise RuntimeError(
                "Trained voice failed; see logs/trained-voice-worker.log"
            )
        return packet

    def _start(self):
        (ROOT / "logs").mkdir(exist_ok=True)
        self._log = (ROOT / "logs/trained-voice-worker.log").open("a", encoding="utf-8")
        self._process = subprocess.Popen(
            [
                self.settings["python_path"],
                "-u",
                str(Path(__file__).with_name("trained_voice_worker.py")),
                json.dumps(self.settings),
            ],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self._reader = threading.Thread(
            target=self._read, args=(self._process,), daemon=True
        )
        self._reader.start()
        ready = self._receive(self.settings.get("startup_timeout", 180))
        if ready.get("type") != "ready" or ready.get("sample_rate") != self.sample_rate:
            raise ValueError(
                "Trained voice worker returned an invalid startup response"
            )

    def infer(self, text, temperature=0.7, emotion="neutral", **kwargs):
        if (
            not isinstance(text, str)
            or not 1 <= len(text.strip()) <= 16000
            or emotion not in self.tokens
        ):
            raise ValueError("Invalid trained voice synthesis request")
        if type(temperature) not in (int, float) or not 0 < temperature <= 2:
            raise ValueError("Invalid trained voice temperature")
        with self._lock:
            if self._closed:
                raise RuntimeError(
                    "Trained voice worker is closed; restart the TTS engine"
                )
            try:
                if self._process is None:
                    self._start()
                if self._process.poll() is not None:
                    raise RuntimeError("Trained voice worker stopped")
                request = {"text": text, "temperature": temperature, "emotion": emotion}
                self._process.stdin.write(json.dumps(request, ensure_ascii=True) + "\n")
                self._process.stdin.flush()
                packet = self._receive(self.settings.get("timeout", 120))
                audio = np.frombuffer(
                    base64.b64decode(packet["audio"], validate=True), dtype="<f4"
                ).copy()
                if (
                    packet.get("sample_rate") != self.sample_rate
                    or not 0 < audio.size <= self.sample_rate * 180
                ):
                    raise ValueError("Invalid trained voice audio length/rate")
                if not np.isfinite(audio).all():
                    raise ValueError("Invalid trained voice PCM")
                return audio
            except Exception:
                # Do not associate a late/timed-out response with the next sentence.
                self.close()
                raise

    def save(self, audio, path):
        import soundfile as sf

        sf.write(path, audio, self.sample_rate, subtype="PCM_16")

    def close(self):
        self._closed = True
        atexit.unregister(self.close)
        process, self._process = self._process, None
        if process is not None:
            if process.poll() is None:
                try:
                    process.stdin.close()
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    if os.name == "nt" and process.poll() is None:
                        # Windows venv Python can own a redirector child; kill the
                        # owned tree so a timeout cannot leave a GPU model behind.
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    elif process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
            if self._reader and self._reader is not threading.current_thread():
                self._reader.join(timeout=1)
            for pipe in (process.stdin, process.stdout):
                if pipe and not pipe.closed:
                    pipe.close()
        if self._log:
            self._log.close()
            self._log = None
