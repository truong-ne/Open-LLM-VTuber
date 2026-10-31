"""Measure the real local pipeline on synthetic data in the dedicated test DB.

The audio sink simulates player time. It does not measure microphone/browser/device
latency and never claims that a person heard the output.
"""

import argparse
import asyncio
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TokenProbe:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.marks = None
        self.started = 0

    def __getattr__(self, key):
        return getattr(self.wrapped, key)

    @property
    def __class__(self):
        # Preserve native-provider routing while measuring token timings.
        return self.wrapped.__class__

    async def chat_completion(self, *args, **kwargs):
        async for event in self.wrapped.chat_completion(*args, **kwargs):
            text = (
                event
                if isinstance(event, str)
                else event.get("text", "")
                if isinstance(event, dict)
                else ""
            )
            if text and self.marks is not None:
                self.marks.setdefault(
                    "first_token_ms", (time.monotonic() - self.started) * 1000
                )
            yield event


async def measure(context, probe, value, modality, phase, interrupt=False):
    from src.open_llm_vtuber.conversations.single_conversation import (
        process_single_conversation,
    )
    from src.open_llm_vtuber.message_handler import message_handler

    started = time.monotonic()
    marks = {"input_received_ms": 0}
    probe.marks, probe.started = marks, started
    row = {
        "modality": modality,
        "phase": phase,
        "marks": marks,
        "audio_chunks": 0,
        "errors": 0,
        "cancelled": False,
        "playback_evidence": "simulated_sink",
        "playback_complete_ms": None,
    }
    player_end = started
    task = None
    segments = []
    playback_tracker = None

    async def send(message):
        nonlocal player_end, playback_tracker
        data = json.loads(message)
        now = time.monotonic()
        elapsed = (now - started) * 1000
        if data.get("type") == "user-input-transcription":
            marks.setdefault("asr_complete_ms", elapsed)
            row["asr_uncertain"] = bool(data.get("uncertain"))
        if data.get("type") == "audio" and data.get("audio"):
            playback_tracker = getattr(context, "mao_delivery", None)
            if data.get("segment_id"):
                segments.append(
                    {
                        key: data[key]
                        for key in ("turn_id", "generation_epoch", "segment_id")
                    }
                )
            marks.setdefault("first_audio_ms", elapsed)
            row["audio_chunks"] += 1
            with wave.open(io.BytesIO(base64.b64decode(data["audio"])), "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
            player_end = max(now, player_end) + duration
            if interrupt and task:
                asyncio.get_running_loop().call_soon(task.cancel)
        if data.get("type") == "error":
            row["errors"] += 1
        if data.get("type") == "backend-synth-complete":
            marks["synthesis_complete_ms"] = elapsed
            await asyncio.sleep(max(0, player_end - time.monotonic()))
            row["playback_complete_ms"] = (time.monotonic() - started) * 1000
            if playback_tracker:
                for segment in segments:
                    playback_tracker.ack({**segment, "status": "completed"})
            message_handler.handle_message(
                "synthetic-baseline",
                {
                    "type": "frontend-playback-complete",
                    "request_id": data.get("turn_id"),
                },
            )

    try:
        task = asyncio.create_task(
            process_single_conversation(
                context,
                send,
                "synthetic-baseline",
                value,
                metadata={"rehearsal": True, "skip_history": True, "skip_memory": True},
            )
        )
        response = await asyncio.wait_for(task, timeout=180)
        row["response_nonempty"] = bool(response.strip())
    except asyncio.CancelledError:
        row["cancelled"] = True
    except Exception as error:
        row["errors"] += 1
        row["error_type"] = type(error).__name__
    finally:
        probe.marks = None
        message_handler.cleanup_client("synthetic-baseline")
        row["duration_ms"] = (time.monotonic() - started) * 1000
        row["delivery_state"] = playback_tracker.state if playback_tracker else None
    return row


async def run(output, samples):
    from loguru import logger

    logger.remove()  # Baseline reports never include transcripts or raw provider errors.
    from scripts.mao_test import prepare_database

    prepare_database()
    os.environ["MAO_RUNTIME_PROFILE"] = "test"
    from scripts.mao_doctor import collect
    from src.open_llm_vtuber.config_manager import read_yaml, validate_config
    from src.open_llm_vtuber.service_context import ServiceContext

    corpus_path = ROOT / "tests/fixtures/mao_baseline_v1.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "synthetic": True,
        "corpus_version": corpus["version"],
        "corpus_digest": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "sample_size_per_modality": samples,
        "turns": [],
        "status": "initializing",
        "limits": [
            "In-process transport; simulated playback, no physical audio device.",
            "First turn per modality means first use, not a fresh model process.",
            "Single fixed fixture per modality; empirical p95 is not proof of a production SLO.",
        ],
    }
    context = ServiceContext()

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(output)

    save()
    try:
        report["environment"] = collect("test")
        if report["environment"]["database"]["status"] != "ok":
            raise RuntimeError("Test database unavailable")
        config = validate_config(read_yaml(str(ROOT / "conf.yaml")))
        startup = time.monotonic()
        await context.load_from_config(config)
        report["context_startup_ms"] = (time.monotonic() - startup) * 1000
        context.history_uid = None
        probe = TokenProbe(context.agent_engine._llm)
        context.agent_engine._llm = probe
        report["status"] = "running"
        for index in range(samples):
            context.agent_engine._memory.clear()
            report["turns"].append(
                await measure(
                    context,
                    probe,
                    corpus["text"],
                    "text",
                    "first_use" if index == 0 else "warm",
                )
            )
            save()
        # Synthesize the fixed fixture, then feed 16kHz mono float samples to real ASR.
        import numpy as np
        from scipy.signal import resample_poly
        import soundfile as sf
        from math import gcd

        fixture = await context.tts_engine.async_generate_audio(
            corpus["voice"], "mao_baseline_v1_input"
        )
        try:
            audio, rate = sf.read(fixture, dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            divisor = gcd(rate, 16000)
            audio = np.asarray(
                resample_poly(audio, 16000 // divisor, rate // divisor),
                dtype=np.float32,
            )
        finally:
            context.tts_engine.remove_file(fixture, verbose=False)
        for index in range(samples):
            context.agent_engine._memory.clear()
            report["turns"].append(
                await measure(
                    context,
                    probe,
                    audio,
                    "voice",
                    "first_use" if index == 0 else "warm",
                )
            )
            save()
        context.agent_engine._memory.clear()
        report["interrupt"] = await measure(
            context, probe, corpus["interrupt"], "text", "warm", True
        )
        report["status"] = (
            "ok"
            if all(
                not row["errors"]
                and not row.get("asr_uncertain", False)
                and row.get("response_nonempty")
                and row["audio_chunks"]
                and "first_token_ms" in row["marks"]
                and row["playback_complete_ms"] is not None
                for row in report["turns"]
            )
            and report["interrupt"]["cancelled"]
            else "incomplete"
        )
    except Exception as error:
        report.update(status="unavailable", error_type=type(error).__name__)
    finally:
        await context.close()
        save()
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": str(output),
                "turns": len(report["turns"]),
            }
        )
    )
    return 0 if report["status"] == "ok" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "logs/mao-baseline.json")
    parser.add_argument("--samples", type=int, choices=range(1, 202), default=2)
    args = parser.parse_args()
    return asyncio.run(run(args.output, args.samples))


if __name__ == "__main__":
    raise SystemExit(main())
