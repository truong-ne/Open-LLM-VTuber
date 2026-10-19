"""Persistent RVC subprocess with an isolated CUDA Python environment."""

import atexit
import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

import numpy as np
from loguru import logger


class RVCConverter:
    def __init__(self, settings: dict):
        self._lock = threading.Lock()
        self._responses = queue.Queue()
        self._process = None
        self._log = None
        self._reader = None
        self.timeout = settings.get("timeout", 30)
        config = dict(settings)
        for name in ("python_path", "applio_path", "model_path", "index_path"):
            if not config.get(name):
                raise ValueError(f"RVC {name} is required")
            path = Path(config[name]).resolve()
            if not path.exists():
                raise FileNotFoundError(f"RVC {name} not found: {path}")
            config[name] = str(path)
        Path("logs").mkdir(exist_ok=True)
        self._log = open("logs/rvc-worker.log", "a", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                [
                    config["python_path"],
                    "-u",
                    str(Path(__file__).with_name("rvc_worker.py")),
                    json.dumps(config),
                ],
                cwd=config["applio_path"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._log,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self._reader = threading.Thread(
                target=self._read_responses, args=(self._process,), daemon=True
            )
            self._reader.start()
            ready = self._receive(settings.get("startup_timeout", 180))
            if ready.get("type") != "ready":
                raise RuntimeError(f"Invalid RVC startup response: {ready}")
            logger.info(
                "RVC ready: model={}, device={}, sample_rate={}",
                config["model_path"],
                ready["device"],
                ready["sample_rate"],
            )
        except Exception:
            self.close()
            raise
        atexit.register(self.close)

    def _read_responses(self, process):
        try:
            for line in process.stdout:
                self._responses.put(json.loads(line))
        except Exception as exc:
            self._responses.put({"error": f"Invalid RVC response: {exc}"})
        finally:
            self._responses.put({"error": "RVC worker exited; see logs/rvc-worker.log"})

    def _receive(self, timeout):
        try:
            response = self._responses.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError(
                f"RVC exceeded {timeout}s; see logs/rvc-worker.log"
            ) from exc
        if response.get("error"):
            raise RuntimeError(response["error"])
        return response

    def convert(self, audio: np.ndarray, sample_rate: int):
        audio = np.asarray(audio, dtype="<f4")
        if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
            raise ValueError("RVC input must be nonempty finite mono audio")
        if not isinstance(sample_rate, int) or not 8000 <= sample_rate <= 192000:
            raise ValueError(
                "RVC sample rate must be an integer between 8000 and 192000"
            )
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError("RVC worker is not running")
            request = {
                "sample_rate": sample_rate,
                "audio": base64.b64encode(audio.tobytes()).decode("ascii"),
            }
            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
                response = self._receive(self.timeout)
                result = np.frombuffer(
                    base64.b64decode(response["audio"], validate=True), dtype="<f4"
                ).copy()
                output_rate = int(response["sample_rate"])
                if (
                    not result.size
                    or not np.isfinite(result).all()
                    or not 8000 <= output_rate <= 192000
                ):
                    raise ValueError("RVC returned invalid audio")
            except (TimeoutError, RuntimeError, OSError, ValueError, KeyError):
                # A timed-out response must never be mistaken for the next sentence.
                self.close()
                raise
            logger.info(
                "RVC conversion: {:.3f}s for {:.2f}s audio",
                response["seconds"],
                len(audio) / sample_rate,
            )
            return result, output_rate

    def close(self):
        atexit.unregister(self.close)
        process = self._process
        self._process = None
        if process is not None:
            if process.poll() is None:
                try:
                    process.stdin.close()
                    process.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    process.kill()
                    process.wait(timeout=3)
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if self._reader and self._reader is not threading.current_thread():
                self._reader.join(timeout=1)
            if process.stdout:
                process.stdout.close()
        if self._log is not None:
            self._log.close()
            self._log = None
