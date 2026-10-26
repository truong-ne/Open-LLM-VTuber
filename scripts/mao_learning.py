"""Local operator console. Viewer chat and model tools cannot submit these ratings."""

import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path

from mao_hybrid import config, load_admin_env
from src.open_llm_vtuber.agent.hybrid.learning import DailyLearning
from src.open_llm_vtuber.agent.hybrid.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["status", "review", "feedback", "reset", "teach"]
    )
    parser.add_argument("--lesson-file", type=Path)
    parser.add_argument("--day", type=date.fromisoformat)
    parser.add_argument("--turn")
    parser.add_argument(
        "--label", choices=["useful", "too_long", "too_short", "incorrect", "unsafe"]
    )
    args = parser.parse_args()
    settings = config()
    if args.command in {"feedback", "reset", "teach"}:
        load_admin_env()
        os.environ["MAO_OPERATOR_DSN"] = os.environ["MAO_DATABASE_ADMIN_URL"]
        settings = settings.model_copy(update={"database_url_env": "MAO_OPERATOR_DSN"})
    store = Store(settings)
    learning = DailyLearning(store)
    try:
        if args.command == "teach":
            if not args.lesson_file or args.lesson_file.stat().st_size > 10000:
                parser.error("teach requires --lesson-file JSON, at most 10 KB")
            lesson = json.loads(args.lesson_file.read_text(encoding="utf-8-sig"))
            if set(lesson) != {"kind", "content", "evidence"} or lesson["kind"] not in {
                "skill",
                "long_term",
            }:
                parser.error(
                    "lesson requires kind(skill/long_term),content,evidence only"
                )
            if not all(
                isinstance(lesson[k], str) and 0 < len(lesson[k].strip()) <= 1000
                for k in ("content", "evidence")
            ):
                parser.error(
                    "content and evidence must be nonempty text, at most 1000 characters"
                )
            store.remember(
                lesson["kind"],
                "shared",
                lesson["content"],
                "operator",
                evidence=lesson["evidence"],
            )
            store.event("operator_lesson", {"kind": lesson["kind"]})
            result = {
                "stored": True,
                "source": "operator",
                "meaning": "operator-supplied evidence, not independently verified truth",
            }
        elif args.command == "feedback":
            if not args.turn or not args.label:
                parser.error("feedback requires --turn and --label")
            with store.connect() as db:
                db.execute(
                    "INSERT INTO mao_hybrid.learning_feedback(scope,turn_id,label) VALUES(%s,%s,%s) ON CONFLICT(scope,turn_id) DO UPDATE SET label=excluded.label,created=now()",
                    (settings.scope, args.turn, args.label),
                )
            result = {"rated": args.turn, "label": args.label}
        elif args.command == "review":
            result = learning.review(
                args.day or (datetime.now(learning.zone).date() - timedelta(days=1))
            )
        elif args.command == "reset":
            with store.connect() as db:
                db.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("learning:" + settings.scope,),
                )
                db.execute(
                    "INSERT INTO mao_hybrid.learning_profiles(scope,proactive_max_words,reason) VALUES(%s,60,'operator_reset')",
                    (settings.scope,),
                )
            result = {"reset": True, "proactive_max_words": 60}
        else:
            result = learning.status()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        store.close()


if __name__ == "__main__":
    main()
