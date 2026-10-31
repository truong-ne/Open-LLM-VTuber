"""Local VieNeu checkpoint worker. GPU/model imports occur only in main()."""

import base64
import contextlib
import json
import os
from pathlib import Path
import sys


def synthesize(tts, text, emotion, tokens, temperature):
    """Match Mao-TTS's trained preview: condition EVERY normalized chunk."""
    import numpy as np
    from vieneu_utils.phonemize_text import normalize_to_chunks_v3_with_gaps
    from vieneu_utils.core_utils import gaps_to_silence, pause_pad_samples

    chunks, gaps = normalize_to_chunks_v3_with_gaps(text, max_chars=256)
    pauses = gaps_to_silence(gaps)
    parts, last = [], None
    for index, chunk in enumerate(chunks):
        first = True
        stream = tts.infer_stream(
            tokens[emotion] + " " + chunk,
            voice="Cold Queen · " + emotion,
            use_ref_codes=False,
            temperature=temperature,
            max_chars=1_000_000,
            apply_watermark=False,
        )
        try:
            for audio in stream:
                if audio is None or not len(audio):
                    continue
                if first and last is not None:
                    pad = pause_pad_samples(
                        last, audio, tts.sample_rate, pauses[index - 1]
                    )
                    if pad:
                        parts.append(np.zeros(pad, dtype=np.float32))
                parts.append(np.asarray(audio, dtype=np.float32))
                last, first = audio, False
        finally:
            stream.close()
    if not parts:
        raise ValueError("Trained voice produced no audio")
    audio = np.concatenate(parts)
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError("Trained voice returned invalid PCM")
    return audio


def main():
    protocol = sys.stdout

    def send(packet):
        protocol.write(json.dumps(packet) + "\n")
        protocol.flush()

    with contextlib.redirect_stdout(sys.stderr):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        settings = json.loads(sys.argv[1])
        from vieneu import Vieneu

        model = Path(settings["model_path"])
        tokens = json.loads(
            (model / "mao_emotion_tokens.json").read_text(encoding="utf-8")
        )
        tts = Vieneu(
            mode="v3turbo",
            backbone_repo=str(model),
            moss_tokenizer=settings.get("codec_path")
            or "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano",
            backend="pytorch",
            device=settings["device"],
        )
        send({"type": "ready", "sample_rate": tts.sample_rate})
        for line in sys.stdin:
            try:
                request = json.loads(line)
                text = request["text"]
                emotion = request.get("emotion", "neutral")
                temperature = request.get("temperature", 0.7)
                if (
                    not isinstance(text, str)
                    or not 1 <= len(text.strip()) <= 16000
                    or emotion not in tokens
                ):
                    raise ValueError("Invalid synthesis request")
                if type(temperature) not in (float, int) or not 0 < temperature <= 2:
                    raise ValueError("Invalid sampling temperature")
                audio = synthesize(tts, text, emotion, tokens, temperature)
                send(
                    {
                        "audio": base64.b64encode(audio.astype("<f4").tobytes()).decode(
                            "ascii"
                        ),
                        "sample_rate": tts.sample_rate,
                    }
                )
            except Exception as error:
                send({"error": type(error).__name__})


if __name__ == "__main__":
    main()
