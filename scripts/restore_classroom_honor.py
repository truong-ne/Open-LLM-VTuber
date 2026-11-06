"""Restore an operator-verified previous LIVE podium exactly once."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from src.open_llm_vtuber.live.classroom import ClassroomGame

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    records = json.loads(args.records.read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    rows = sorted(
        records.items(),
        key=lambda item: (
            -item[1]["correct"],
            -item[1]["points"],
            item[1]["first_correct"],
            item[1]["order"],
        ),
    )
    if len(rows) < 3:
        raise ValueError("Not enough verified podium records")
    missing_players = audit["players"] - len(rows)
    missing_correct = audit["total_correct"] - sum(row["correct"] for _, row in rows)
    missing_points = audit["total_points"] - sum(row["points"] for _, row in rows)
    if min(missing_players, missing_correct, missing_points) < 0:
        raise ValueError("Recovered totals exceed the audited source")
    if missing_players and rows[2][1]["correct"] <= missing_correct:
        raise ValueError(
            "Unrecovered records could change the podium; refusing to infer winners"
        )
    if not missing_players:
        digest = hashlib.sha256(
            json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        if digest != audit["scores_hash"]:
            raise ValueError("Complete recovery does not match the prior audit")
    podium = [{"player_id": key, **row} for key, row in rows[:3]]
    proof = {
        "source": "operator_recovery_of_previous_live",
        "source_session": audit["session"],
        "source_records_sha256": hashlib.sha256(args.records.read_bytes()).hexdigest(),
        "audit_sha256": hashlib.sha256(args.audit.read_bytes()).hexdigest(),
        "known_players": audit["players"],
        "recovered_players": len(rows),
        "missing_correct_total": missing_correct,
        "podium_safe_from_missing_records": True,
    }
    summary = {
        "session": audit["session"],
        "podium": [
            {
                "nickname": r["nickname"],
                "correct": r["correct"],
                "class_points": r["points"],
                "honor_bonus": (10, 6, 3)[i],
            }
            for i, r in enumerate(podium)
        ],
        "applied": False,
    }
    if args.apply:
        game = ClassroomGame()
        if any(
            not r["player_id"].casefold().startswith(game.account.casefold() + ":")
            for r in podium
        ):
            raise ValueError("Recovered podium belongs to another TikTok account")
        summary["applied"] = game.restore_session_podium(
            audit["session"], podium, proof
        )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
