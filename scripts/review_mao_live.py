"""Back up live/classroom state and verify the review did not reset user data."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "logs/mao-live-review-baseline.json"
BANKS = [
    "vua_tieng_viet.vi.json",
    "classroom.vi.json",
    "classroom.hard.vi.json",
    "classroom.expanded.vi.json",
    "classroom.proverbs-new.vi.json",
    "classroom-bank-policy.json",
]


def snapshot():
    result = {
        "banks": {
            name: hashlib.sha256((ROOT / "knowledge" / name).read_bytes()).hexdigest()
            for name in BANKS
        }
    }
    with closing(
        sqlite3.connect(
            f"file:{ROOT / 'private/mao-classroom.sqlite3'}?mode=ro", uri=True
        )
    ) as db:
        result["classroom"] = json.loads(
            db.execute("SELECT payload FROM classroom WHERE id=1").fetchone()[0]
        )
        result["honor"] = db.execute(
            "SELECT account,player_id,points,gold,silver,bronze FROM classroom_honor ORDER BY account,player_id"
        ).fetchall()
        result["ledgers"] = {
            table: db.execute("SELECT count(*) FROM " + table).fetchone()[0]
            for table in [
                "classroom_sessions",
                "classroom_round_awards",
                "classroom_session_awards",
            ]
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = snapshot()
    if args.verify:
        previous = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert current["banks"] == previous["banks"], "Question bank changed"
        by_player = {(r[0], r[1]): r[2:] for r in current["honor"]}
        for row in previous["honor"]:
            assert (row[0], row[1]) in by_player, "Honor entry missing"
            assert all(a >= b for a, b in zip(by_player[(row[0], row[1])], row[2:])), (
                "Honor totals decreased"
            )
        for table, count in previous["ledgers"].items():
            assert current["ledgers"][table] >= count, "Award/session records missing"
        if not previous["classroom"]["enabled"]:
            for key in ["session_id", "standings", "round_number", "enabled"]:
                assert current["classroom"][key] == previous["classroom"][key], (
                    f"Classroom {key} changed during offline review"
                )
        (ROOT / "logs/mao-live-review-data-check.json").write_text(
            json.dumps(
                {
                    "preserved": True,
                    "banks": len(current["banks"]),
                    "honor_entries": len(current["honor"]),
                    "ledgers": current["ledgers"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            "Verified: question files, classroom session, honor totals and award ledgers preserved."
        )
        return
    if BASELINE.exists():
        raise RuntimeError("Baseline exists; refusing to overwrite it")
    backup = ROOT / "private/backups/live-review-2026-11-06"
    backup.mkdir(parents=True, exist_ok=True)
    for name in [
        "mao-classroom.sqlite3",
        "mao-comment-state.db",
        "mao-viewer-memory.sqlite3",
    ]:
        source = ROOT / "private" / name
        if source.exists():
            with (
                closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as db,
                closing(sqlite3.connect(backup / name)) as dest,
            ):
                db.backup(dest)
    BASELINE.write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved baseline and consistent SQLite backups.")


if __name__ == "__main__":
    main()
