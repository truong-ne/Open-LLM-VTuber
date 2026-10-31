"""Exercise the real test-profile WebSocket/LLM/TTS pipeline with a simulated player.

Run the server with --profile test first. A duration below 7200 seconds is a smoke
check, never a two-hour qualification. No production transcript is read or copied.
"""

import argparse
import asyncio
import base64
import io
import json
from pathlib import Path
import statistics
import sys
import time
import uuid
import wave
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def code_digest():
    value = hashlib.sha256()
    paths = [
        ROOT / "scripts/mao_soak.py",
        ROOT / "run_server.py",
        Path(__file__).resolve(),
        ROOT / "web_tool/mao-5070/delivery.mjs",
        ROOT / "web_tool/mao-5070/delivery-bridge.mjs",
    ]
    paths.extend(sorted((ROOT / "src/open_llm_vtuber").rglob("*.py")))
    for path in paths:
        value.update(str(path.relative_to(ROOT)).encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def resources(actor=None, stage=None):
    from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
    from src.open_llm_vtuber.agent.hybrid.store import resolve_dsn
    from src.open_llm_vtuber.testing import assert_test_database
    import psycopg

    config = HybridConfig(
        database_url_env="MAO_TEST_DATABASE_URL",
        database_env_file="private/mao-test.env",
        scope="mao-synthetic-test",
    )
    dsn = resolve_dsn(config)
    assert_test_database(dsn)
    with psycopg.connect(dsn) as db:
        size = db.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    command = """$taskRoot=(Get-NetTCPConnection -LocalPort 12394 -State Listen -ErrorAction Stop | Select-Object -First 1).OwningProcess
    $taskIds=[System.Collections.Generic.HashSet[int]]::new()
    $taskIds.Add([int]$taskRoot) | Out-Null
    $taskProcesses=Get-CimInstance Win32_Process
    do { $taskChanged=$false; foreach($taskProcess in $taskProcesses) {
      if($taskIds.Contains([int]$taskProcess.ParentProcessId) -and $taskIds.Add([int]$taskProcess.ProcessId)) {$taskChanged=$true}
    }} while($taskChanged)
    $taskRss=(Get-Process -Id @($taskIds) -ErrorAction Stop | Measure-Object -Property WorkingSet64 -Sum).Sum
    @{rss=[long]$taskRss} | ConvertTo-Json -Compress"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=True,
    )
    rss = json.loads(result.stdout)["rss"]
    story = None
    if actor:
        # Playback end precedes the durable activity transaction. Observe its
        # result instead of mistaking that short window for a failed action.
        deadline = time.monotonic() + 5
        with psycopg.connect(dsn) as db:
            while True:
                story = db.execute(
                    """SELECT status,jsonb_array_length(canon),revision FROM mao_hybrid.activities
                    WHERE scope=%s AND actor_id=%s AND room_id='local' ORDER BY expires DESC LIMIT 1""",
                    (config.scope, actor),
                ).fetchone()
                expected = "completed" if stage == 3 else "running"
                if (
                    stage not in {1, 2, 3}
                    or (story and story[0] == expected and story[1] >= stage)
                    or time.monotonic() >= deadline
                ):
                    break
                time.sleep(0.05)
    return {
        "server_tree_rss_bytes": rss,
        "database_bytes": size,
        "story": {"status": story[0], "entries": story[1], "revision": story[2]}
        if story
        else None,
    }


async def exercise(seconds, interval, stop_server=False, output=None):
    import websockets
    from src.open_llm_vtuber.runtime_profile import TEST_SCOPE

    started = time.monotonic()
    report = {
        "schema_version": 1,
        "requested_seconds": seconds,
        "elapsed_seconds": 0,
        "sink": "simulated_player",
        "turns": [],
        "errors": [],
        "qualified_two_hour": False,
        "complete": False,
        "code_digest": code_digest(),
        "release_qualified": False,
        "limits": [
            "Simulated playback; not a physical microphone/player or human-feedback qualification."
        ],
    }
    output = (
        Path(output) if output is not None else ROOT / "logs" / "mao-soak-runtime.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    token = None
    verified = False

    def save():
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)

    async def connect():
        nonlocal token, verified
        ws = await websockets.connect(
            "ws://127.0.0.1:12394/client-ws",
            max_size=32 * 1024 * 1024,
            open_timeout=180,
        )
        while True:
            packet = json.loads(await asyncio.wait_for(ws.recv(), 180))
            if packet.get("type") == "actor-session":
                if (
                    packet.get("runtime_profile") != "test"
                    or packet.get("scope") != TEST_SCOPE
                ):
                    await ws.close()
                    raise ValueError("The endpoint is not the isolated test profile")
                verified = True
                if token:
                    await ws.send(json.dumps({"type": "resume-actor", "token": token}))
                    while True:
                        resumed = json.loads(await asyncio.wait_for(ws.recv(), 30))
                        if resumed.get("type") == "actor-session" and resumed.get(
                            "force"
                        ):
                            if resumed["token"] != token:
                                raise ValueError("Stable actor resume failed")
                            break
                else:
                    token = packet["token"]
                return ws

    save()
    ws = None
    try:
        ws = await connect()
        index = 0
        while time.monotonic() - started < seconds:
            cycle = time.monotonic()
            event_id = uuid.uuid4().hex
            row = {
                "index": index,
                "event_id": event_id,
                "audio_chunks": 0,
                "reconnected": False,
            }
            fixtures = [
                "Trả lời ngắn gọn trong một câu: hai cộng ba bằng mấy?",
                "/story start Cùng kể một câu chuyện rất ngắn về ngọn đèn biết hát.",
                "Kể tiếp câu chuyện trong một câu ngắn.",
                "/story finish Kết thúc câu chuyện bằng một câu ngắn.",
                "Để lần sau, tớ chưa xong. Trả lời ngắn thôi nhé.",
                "Đã hiểu, xong rồi. Cảm ơn Mao. Trả lời ngắn nhé.",
            ]
            await ws.send(
                json.dumps(
                    {
                        "type": "text-input",
                        "event_id": event_id,
                        "source": "mao-rehearsal",
                        "text": fixtures[index % len(fixtures)],
                    }
                )
            )
            while True:
                data = json.loads(await asyncio.wait_for(ws.recv(), 180))
                if data.get("type") == "error":
                    code = str(data.get("code", "unspecified"))
                    report["runtime_error_code"] = (
                        code
                        if code.replace("-", "").replace("_", "").isalnum()
                        and len(code) <= 80
                        else "unspecified"
                    )
                    report["failed_turn"] = row
                    raise RuntimeError("Runtime reported an error")
                if data.get("type") == "audio" and data.get("audio"):
                    row.setdefault(
                        "first_audio_ms", round((time.monotonic() - cycle) * 1000, 2)
                    )
                    row["audio_chunks"] += 1
                    ids = {
                        key: data[key]
                        for key in ("turn_id", "generation_epoch", "segment_id")
                    }
                    await ws.send(
                        json.dumps(
                            {"type": "playback-segment", **ids, "status": "started"}
                        )
                    )
                    with wave.open(
                        io.BytesIO(base64.b64decode(data["audio"])), "rb"
                    ) as audio:
                        duration = audio.getnframes() / audio.getframerate()
                    await asyncio.sleep(duration)
                    await ws.send(
                        json.dumps(
                            {"type": "playback-segment", **ids, "status": "completed"}
                        )
                    )
                if data.get("type") == "backend-synth-complete":
                    await ws.send(
                        json.dumps(
                            {
                                "type": "frontend-playback-complete",
                                "turn_id": data.get("turn_id"),
                                "generation_epoch": data.get("generation_epoch"),
                            }
                        )
                    )
                if (
                    data.get("type") == "control"
                    and data.get("text") == "conversation-chain-end"
                ):
                    if not row["audio_chunks"]:
                        raise RuntimeError("Turn completed without audio")
                    break
            row["duration_ms"] = round((time.monotonic() - cycle) * 1000, 2)
            if index % 5 == 2:
                await ws.close()
                ws = await connect()
                row["reconnected"] = True
                await ws.send(
                    json.dumps(
                        {
                            "type": "text-input",
                            "event_id": event_id,
                            "text": "duplicate should not play",
                        }
                    )
                )
                while True:
                    data = json.loads(await asyncio.wait_for(ws.recv(), 30))
                    if data.get("type") == "audio":
                        raise RuntimeError(
                            "Reconnect replay generated duplicate speech"
                        )
                    if (
                        data.get("type") == "input-status"
                        and data.get("status") == "duplicate"
                    ):
                        break
            report["turns"].append(row)
            from src.open_llm_vtuber.interaction.ingress import verify_actor

            stage = index % len(fixtures)
            row.update(await asyncio.to_thread(resources, verify_actor(token), stage))
            if stage in {1, 2, 3}:
                expected = "completed" if stage == 3 else "running"
                if (
                    not row["story"]
                    or row["story"]["status"] != expected
                    or row["story"]["entries"] < stage
                ):
                    raise RuntimeError(
                        "Story canon did not survive the delivered turn/reconnect"
                    )
            save()
            print(
                json.dumps(
                    {
                        "turn": index,
                        "elapsed_seconds": report["elapsed_seconds"],
                        "audio_chunks": row["audio_chunks"],
                    }
                ),
                flush=True,
            )
            index += 1
            until = min(started + seconds, cycle + interval)
            while time.monotonic() < until:
                await asyncio.sleep(min(30, until - time.monotonic()))
        report["complete"] = True
        report["qualified_two_hour"] = (
            seconds >= 7200
            and time.monotonic() - started >= 7200
            and len(report["turns"]) >= 40
            and report["code_digest"] == code_digest()
        )
        report["code_unchanged"] = report["code_digest"] == code_digest()
        if len(report["turns"]) > 5:
            report["resource_growth"] = {
                key: report["turns"][-1][key] - report["turns"][5][key]
                for key in ("server_tree_rss_bytes", "database_bytes")
            }
        values = sorted(row["first_audio_ms"] for row in report["turns"])
        report["latency_ms"] = {
            "first_audio_p50": statistics.median(values),
            "first_audio_p95": values[min(len(values) - 1, int(len(values) * 0.95))],
        }
    except Exception as error:
        report["errors"].append(type(error).__name__)
        if "row" in locals():
            report.setdefault("failed_turn", row)
        raise
    finally:
        if ws:
            await ws.close()
        save()
        if stop_server and verified:
            import httpx
            from src.open_llm_vtuber.interaction.ingress import control_token

            async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
                response = await client.post(
                    "http://127.0.0.1:12394/api/runtime/shutdown",
                    headers={"X-Mao-Control": control_token("test")},
                )
                response.raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=7200)
    parser.add_argument("--interval", type=int, default=90)
    parser.add_argument(
        "--output",
        type=Path,
        help="Report path; defaults to logs/mao-soak-runtime.json",
    )
    parser.add_argument(
        "--stop-server",
        action="store_true",
        help="Gracefully stop the test backend owned by this run when finished",
    )
    args = parser.parse_args()
    if args.seconds < 1 or args.interval < 1:
        parser.error("Duration and interval must be positive")
    asyncio.run(exercise(args.seconds, args.interval, args.stop_server, args.output))
