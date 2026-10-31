"""Exercise scoped affect through the real test server, with simulated playback.

Requires profile=test on port 12394. Inputs are test fixtures, not human feedback.
"""

import asyncio
import base64
import io
import json
from pathlib import Path
import sys
import uuid
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def exercise(closure_rounds=0):
    import websockets
    from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
    from src.open_llm_vtuber.agent.hybrid.store import Store, resolve_dsn
    from src.open_llm_vtuber.interaction.ingress import verify_actor
    from src.open_llm_vtuber.character.emotion import response_policy
    from src.open_llm_vtuber.runtime_profile import TEST_SCOPE
    from src.open_llm_vtuber.testing import assert_test_database

    config = HybridConfig(
        scope=TEST_SCOPE,
        database_url_env="MAO_TEST_DATABASE_URL",
        database_env_file="private/mao-test.env",
    )
    assert_test_database(resolve_dsn(config))
    store = Store(config)
    sockets = []
    report = {
        "profile": "test",
        "sink": "simulated_player",
        "human_feedback": False,
        "turns": [],
        "passed": False,
    }

    async def connect():
        ws = await websockets.connect(
            "ws://127.0.0.1:12394/client-ws", max_size=32 * 1024 * 1024
        )
        sockets.append(ws)
        while True:
            packet = json.loads(await asyncio.wait_for(ws.recv(), 180))
            if packet.get("type") == "actor-session":
                if (
                    packet.get("runtime_profile") != "test"
                    or packet.get("scope") != TEST_SCOPE
                ):
                    raise ValueError(
                        "Refusing to send fixtures outside the test profile"
                    )
                actor = verify_actor(packet["token"])
                if not actor:
                    raise ValueError("Invalid actor proof")
                return ws, actor

    async def turn(ws, actor, text):
        await ws.send(
            json.dumps(
                {
                    "type": "text-input",
                    "source": "mao-affect-test",
                    "event_id": uuid.uuid4().hex,
                    "text": text,
                }
            )
        )
        chunks = 0
        while True:
            packet = json.loads(await asyncio.wait_for(ws.recv(), 180))
            if packet.get("type") == "error":
                raise RuntimeError("Test backend reported an error")
            if packet.get("type") == "audio" and packet.get("audio"):
                chunks += 1
                ids = {
                    key: packet[key]
                    for key in ("turn_id", "generation_epoch", "segment_id")
                }
                await ws.send(
                    json.dumps({"type": "playback-segment", **ids, "status": "started"})
                )
                with wave.open(
                    io.BytesIO(base64.b64decode(packet["audio"])), "rb"
                ) as audio:
                    duration = audio.getnframes() / audio.getframerate()
                await asyncio.sleep(duration)
                await ws.send(
                    json.dumps(
                        {"type": "playback-segment", **ids, "status": "completed"}
                    )
                )
            if packet.get("type") == "backend-synth-complete":
                await ws.send(
                    json.dumps(
                        {
                            "type": "frontend-playback-complete",
                            "turn_id": packet.get("turn_id"),
                            "generation_epoch": packet.get("generation_epoch"),
                        }
                    )
                )
            if (
                packet.get("type") == "control"
                and packet.get("text") == "conversation-chain-end"
            ):
                if not chunks:
                    raise RuntimeError("No audio was generated")
                state = await asyncio.to_thread(
                    store.read_affect, room="local", actor=actor, visibility="test"
                )
                row = {
                    "audio_chunks": chunks,
                    "strategy": response_policy(state)["strategy"],
                    "concern": state["channels"]["concern"],
                    "revision": state["revision"],
                }
                with store.connect() as db:
                    delivered = db.execute(
                        "SELECT status,metrics FROM mao_hybrid.turns WHERE scope=%s AND actor_id=%s "
                        "ORDER BY created DESC LIMIT 1",
                        (store.scope, actor),
                    ).fetchone()
                row["delivery_state"] = delivered["status"] if delivered else None
                row["empty_reply_retries"] = (
                    delivered["metrics"].get("empty_reply_retries", 0)
                    if delivered
                    else 0
                )
                if row["delivery_state"] != "completed":
                    raise AssertionError("Audio delivery was not durably completed")
                report["turns"].append(row)
                return row

    try:
        a, actor_a = await connect()
        first = await turn(
            a, actor_a, "Mình đang buồn. Đừng đùa, chỉ nghe thôi. Trả lời một câu ngắn."
        )
        follow_up = await turn(a, actor_a, "Vẫn vậy.")
        b, actor_b = await connect()
        other = await turn(b, actor_b, "Chào Mao, trả lời chào bằng một câu ngắn.")
        if (
            actor_a == actor_b
            or first["strategy"] != "support"
            or follow_up["strategy"] != "support"
        ):
            raise AssertionError(
                "Scoped support/context did not reach the real pipeline"
            )
        if other["concern"] != 0 or other["strategy"] == "support":
            raise AssertionError("Affect leaked to another actor")
        for index in range(closure_rounds):
            await turn(
                b,
                actor_b,
                (
                    "Để lần sau, tớ chưa xong. Trả lời ngắn thôi nhé."
                    if index % 2 == 0
                    else "Đã hiểu, xong rồi. Cảm ơn Mao. Trả lời ngắn nhé."
                ),
            )
        report["passed"] = True
        return report
    finally:
        for ws in sockets:
            await ws.close()
        store.close()
        (ROOT / "logs/mao-contextual-smoke.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure-rounds", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.closure_rounds <= 20:
        parser.error("Closure rounds must be between 0 and 20")
    result = asyncio.run(exercise(args.closure_rounds))
    print(json.dumps(result, indent=2))
