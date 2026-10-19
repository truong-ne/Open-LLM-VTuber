"""JSON-lines PCM bridge; launched only by RVCConverter in its CUDA environment."""

import base64
import contextlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


def main():
    protocol = sys.stdout

    def send(value):
        protocol.write(json.dumps(value) + "\n")
        protocol.flush()

    # All upstream diagnostic output belongs in the worker log, not the PCM pipe.
    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import librosa
        import torch

        settings = json.loads(sys.argv[1])
        sys.path.insert(0, str(Path(settings["applio_path"]).resolve()))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from rvc.infer.infer import VoiceConverter

        torch.set_num_threads(settings.get("threads", 4))
        device = settings.get("device", "cuda:0")
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "RVC requires CUDA, but its Python runtime cannot use the GPU"
            )
        converter = VoiceConverter()
        converter.config.device = device
        converter.get_vc(settings["model_path"], 0, inference_engine="torch")
        converter.load_hubert("contentvec")
        converter.last_embedder_model = "contentvec"

        def convert(audio, sample_rate):
            if sample_rate != 16000:
                audio = librosa.resample(
                    audio, orig_sr=sample_rate, target_sr=16000, res_type="soxr_hq"
                )
            peak = np.max(np.abs(audio))
            if peak > 0.95:
                audio = audio * (0.95 / peak)
            with torch.inference_mode():
                result = converter.vc.pipeline(
                    model=converter.hubert_model,
                    net_g=converter.net_g,
                    sid=0,
                    audio=audio,
                    pitch=settings.get("pitch", 0),
                    f0_method="rmvpe",
                    file_index=settings["index_path"],
                    index_rate=settings.get("index_rate", 0.6),
                    pitch_guidance=converter.use_f0,
                    volume_envelope=1.0,
                    version=converter.version,
                    protect=settings.get("protect", 0.33),
                    f0_autotune=False,
                    f0_autotune_strength=0.0,
                    proposed_pitch=False,
                    proposed_pitch_threshold=155.0,
                )
            result = np.asarray(result, dtype="<f4")
            if not result.size or not np.isfinite(result).all():
                raise ValueError("RVC produced invalid audio")
            return result

        # Warm pitch prediction, the 48 kHz resampler and speech-length kernels.
        warmup = (0.03 * np.sin(2 * np.pi * 220 * np.arange(48000 * 4) / 48000)).astype(
            np.float32
        )
        convert(warmup, 48000)
        send({"type": "ready", "device": device, "sample_rate": converter.tgt_sr})
        for line in sys.stdin:
            try:
                request = json.loads(line)
                audio = np.frombuffer(
                    base64.b64decode(request["audio"], validate=True), dtype="<f4"
                ).copy()
                if not audio.size or not np.isfinite(audio).all():
                    raise ValueError("Invalid input audio")
                started = time.perf_counter()
                result = convert(audio, int(request["sample_rate"]))
                send(
                    {
                        "audio": base64.b64encode(result.tobytes()).decode("ascii"),
                        "sample_rate": converter.tgt_sr,
                        "seconds": time.perf_counter() - started,
                    }
                )
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                send({"error": str(exc)})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        sys.stdout.flush()
        sys.exit(1)
