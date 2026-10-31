"""Real local LLM/TTS smoke test on an isolated, temporary synthetic DB scope."""

import argparse
import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(output):
    from loguru import logger

    logger.remove()
    from scripts.mao_test import prepare_database
    from src.open_llm_vtuber.character.emotion import affect_summary, response_policy
    from src.open_llm_vtuber.config_manager import read_yaml, validate_config
    from src.open_llm_vtuber.conversations.single_conversation import (
        process_single_conversation,
    )
    from src.open_llm_vtuber.message_handler import message_handler
    from src.open_llm_vtuber.service_context import ServiceContext

    prepare_database()
    os.environ["MAO_RUNTIME_PROFILE"] = "test"
    config = validate_config(read_yaml(str(ROOT / "conf.yaml")))
    settings = (
        config.character_config.agent_config.agent_settings.basic_memory_agent.hybrid
    )
    settings.scope = "emotion-smoke-" + uuid.uuid4().hex
    report = {
        "schema_version": 1,
        "synthetic": True,
        "status": "initializing",
        "turns": [],
        "limits": "Local LLM and TTS/RVC, in-process transport; ACK is synthetic, no speaker/browser verification.",
    }
    context = ServiceContext()
    store = None
    try:
        started = time.monotonic()
        await context.load_from_config(config)
        report["startup_ms"] = (time.monotonic() - started) * 1000
        context.history_uid = None
        store = context.agent_engine._hybrid.store
        engine = context.tts_engine
        plans = []

        class RecordingTTS:
            def __getattr__(self, key):
                return getattr(engine, key)

            async def async_generate_audio(self, *args, **kwargs):
                plans.append(
                    asdict(kwargs["prosody"]) if kwargs.get("prosody") else None
                )
                return await engine.async_generate_audio(*args, **kwargs)

        context.tts_engine = RecordingTTS()
        for request, expected in (
            (
                "Đây là hội thoại giả lập. Mình buồn, chỉ muốn kể thôi, đừng đùa. Hãy đáp đúng một câu ngắn.",
                "support",
            ),
            (
                "Đây là hội thoại giả lập. Mình làm được rồi, vui quá! Hãy chúc mừng bằng đúng một câu ngắn.",
                "share",
            ),
        ):
            plans.clear()
            row = {"expected_strategy": expected, "audio_chunks": 0, "errors": 0}

            async def send(message):
                data = json.loads(message)
                if data.get("type") == "audio" and data.get("audio"):
                    row["audio_chunks"] += 1
                if data.get("type") == "error":
                    row["errors"] += 1
                if data.get("type") == "backend-synth-complete":
                    message_handler.handle_message(
                        "emotion-smoke", {"type": "frontend-playback-complete"}
                    )

            response = await asyncio.wait_for(
                process_single_conversation(
                    context,
                    send,
                    "emotion-smoke",
                    request,
                    metadata={"skip_history": True},
                ),
                180,
            )
            affect = context.agent_engine._hybrid.affect
            row.update(
                policy=response_policy(affect),
                state=affect_summary(affect),
                speech=list(plans),
                response_nonempty=bool(response.strip()),
            )
            row["passed"] = bool(
                row["policy"]["strategy"] == expected
                and row["audio_chunks"]
                and not row["errors"]
                and row["response_nonempty"]
                and plans
            )
            if expected == "support":
                row["passed"] = row["passed"] and all(
                    plan
                    and plan["native_cue"] is None
                    and plan["mood"] in {"gentle", "solemn", "proud"}
                    for plan in plans
                )
            report["turns"].append(row)
        report["status"] = (
            "ok" if all(row["passed"] for row in report["turns"]) else "incomplete"
        )
    except Exception as error:
        report.update(status="unavailable", error_type=type(error).__name__)
    finally:
        message_handler.cleanup_client("emotion-smoke")
        try:
            if store is not None:
                with store.connect() as db:
                    for table in ("state", "memories", "events", "approvals"):
                        db.execute(
                            f"DELETE FROM mao_hybrid.{table} WHERE scope=%s",
                            (settings.scope,),
                        )
        except Exception as error:
            report.update(status="cleanup_failed", error_type=type(error).__name__)
        await context.close()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({"status": report["status"], "report": str(output)}))
    return 0 if report["status"] == "ok" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "logs/mao-emotion-smoke.json"
    )
    args = parser.parse_args()
    return asyncio.run(run(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
