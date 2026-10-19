"""Run one real 60s local round with clearly named test players (--play)."""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
import unicodedata

import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.open_llm_vtuber.live.vua_tieng_viet import WORD_PATH, normalize_answer  # noqa: E402


async def check():
    words = json.loads(WORD_PATH.read_text(encoding="utf-8"))
    report = {
        "test_players": True,
        "events": [],
        "audio_texts": [],
        "speech_latency_seconds": {},
    }
    due = {}
    started = time.monotonic()
    playing = None
    answer = None
    sent = set()
    finished = False
    result_audio = False
    async with websockets.connect(
        "ws://127.0.0.1:12393/proxy-ws", max_size=10_000_000
    ) as ws:

        async def comment(ident, name, text):
            await ws.send(
                json.dumps(
                    {
                        "type": "game-comment",
                        "source": "test-vtv",
                        "author_id": name,
                        "nickname": name,
                        "event_id": ident,
                        "text": text,
                        "created_at": time.time(),
                    },
                    ensure_ascii=False,
                )
            )

        await comment("qa-start-" + str(time.time()), "Kiểm thử", "!vuatiengviet")
        while time.monotonic() - started < 130:
            try:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
            except asyncio.TimeoutError:
                event = {}
            kind = event.get("type")
            if kind == "vua-tieng-viet-state":
                report["events"].append(
                    {
                        "at": round(time.monotonic() - started, 2),
                        **{
                            k: event[k]
                            for k in (
                                "phase",
                                "hint_index",
                                "participants",
                                "remaining",
                            )
                        },
                    }
                )
                if event["phase"] == "playing":
                    due.setdefault(f"Gợi ý {event['hint_index'] + 1}", time.monotonic())
                    assert "answer" not in event and not event["leaderboard"]
                    if playing is None:
                        assert event["remaining"] > 59
                        playing = time.monotonic()
                        answer = next(
                            w["answer"]
                            for w in words
                            if sorted(
                                unicodedata.normalize(
                                    "NFC", w["answer"].upper()
                                ).replace(" ", "")
                            )
                            == sorted(event["letters"])
                        )
                        print("Round started: full 60 seconds", flush=True)
                if event["phase"] == "finished":
                    if playing is None:
                        # Connecting first sends the previous round snapshot.
                        # Wait for the fresh command's playing state instead.
                        continue
                    board = event["leaderboard"]
                    assert [p["nickname"] for p in board[:2]] == [
                        "Kiểm thử A",
                        "Kiểm thử B",
                    ], board
                    assert board[0]["score"] == board[1]["score"] == 100
                    assert board[2]["score"] < 100
                    assert time.monotonic() - playing >= 59.8
                    report["result"] = event
                    due.setdefault("Hết giờ", time.monotonic())
                    finished = True
                    print("60s elapsed; exact + earliest ranking passed", flush=True)
            elif kind == "game-comment-ack":
                report["events"].append(
                    {"ack": event.get("status"), "id": event.get("event_id")}
                )
            elif kind == "audio" and event.get("audio"):
                display = event.get("display_text") or {}
                text = (
                    display.get("text", "")
                    if isinstance(display, dict)
                    else str(display)
                )
                report["audio_texts"].append(text)
                for label, scheduled in due.items():
                    if label in text and label not in report["speech_latency_seconds"]:
                        report["speech_latency_seconds"][label] = round(
                            time.monotonic() - scheduled, 3
                        )
                print("Audio:", text, flush=True)
                if finished and "Hết giờ" in text:
                    result_audio = True
            elif kind == "error":
                raise RuntimeError(event)
            if playing is not None and not finished:
                elapsed = time.monotonic() - playing
                for second, name, guess in [
                    (2, "Kiểm thử C", "zzzz"),
                    (4, "Kiểm thử A", normalize_answer(answer)),
                    (6, "Kiểm thử B", answer),
                ]:
                    if elapsed >= second and second not in sent:
                        ident = f"qa-{playing}-{second}"
                        await comment(ident, name, guess)
                        if second == 4:
                            await comment(ident, name, guess)
                        sent.add(second)
            if (
                result_audio
                and kind == "control"
                and event.get("text") == "conversation-chain-end"
            ):
                break
    assert finished and result_audio, report
    for phrase in (
        "Gợi ý 1",
        "Gợi ý 2",
        "Gợi ý 3",
        "đoán là",
    ):
        assert any(phrase in text for text in report["audio_texts"]), phrase
    assert any(e.get("ack") == "duplicate" for e in report["events"])
    report["passed"] = True
    (ROOT / "logs/vua-tieng-viet-live-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        "PASS: full round, clues, spoken guesses, result audio, ranking, replay dedup",
        flush=True,
    )


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--play", action="store_true", help="Start a visible local test round"
    )
    if parser.parse_args().play:
        asyncio.run(check())
    else:
        parser.print_help()
