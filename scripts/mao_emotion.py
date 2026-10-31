"""Operator diagnostics/reset and deterministic synthetic replay for Mao affect."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.open_llm_vtuber.character.appraisal import appraise_text, outcome_appraisal  # noqa: E402
from src.open_llm_vtuber.character.emotion import (  # noqa: E402
    affect_summary,
    normalize_state,
    response_policy,
    transition,
)


def replay(stateless=False):
    corpus = json.loads(
        (ROOT / "tests/fixtures/mao_emotion_v2.json").read_text(encoding="utf-8")
    )
    cases = []
    for case in corpus["cases"]:
        state = {}
        checks = []
        for index, step in enumerate(case["steps"]):
            if stateless:
                state = {}
            if "text" in step:
                state = transition(
                    state,
                    "audience_input",
                    appraisal=appraise_text(step["text"]),
                    event_id=f"replay:{index}",
                    now=step["at"],
                )
            elif "outcome" in step:
                state = transition(
                    state,
                    "task_result",
                    appraisal=outcome_appraisal(step["outcome"]),
                    event_id=f"replay:{index}",
                    now=step["at"],
                )
            else:
                state = normalize_state(state, now=step["at"])
            policy = response_policy(state, now=step["at"])
            expected = {
                key: actual
                for key, actual in (
                    ("strategy", policy["strategy"]),
                    ("humor", policy["allow_humor"]),
                    ("step_limit", policy["exploration_step_limit"]),
                    ("mode", state["mode"]),
                )
                if key in step
            }
            checks.append(
                {
                    "step": index,
                    "passed": all(
                        step[key] == actual for key, actual in expected.items()
                    ),
                    "policy": policy,
                    "state": affect_summary(state, now=step["at"]),
                }
            )
        cases.append(
            {
                "id": case["id"],
                "passed": all(check["passed"] for check in checks),
                "checks": checks,
            }
        )
    return {
        "schema_version": 1,
        "corpus_version": corpus["version"],
        "synthetic": True,
        "mode": "stateless_ablation" if stateless else "stateful",
        "passed": all(case["passed"] for case in cases),
        "cases": cases,
        "limitations": "Tests controller dynamics only, not human emotion accuracy or conversation quality.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "reset", "replay"))
    parser.add_argument("--test-database", action="store_true")
    parser.add_argument("--room", help="Verified conversation room ID")
    parser.add_argument("--actor", help="Verified actor ID; never a nickname")
    parser.add_argument("--visibility", choices=("private", "public", "test"))
    parser.add_argument(
        "--stateless",
        action="store_true",
        help="Replay ablation: reset state before every event",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from src.open_llm_vtuber.character.affect_scope import affect_key

    identity = {"room": args.room, "actor": args.actor, "visibility": args.visibility}
    try:
        key = affect_key(**identity)
    except ValueError as error:
        parser.error(str(error))
    if args.command == "replay" and key != "affect":
        parser.error("Replay is synthetic and does not read conversation state")
    if args.command == "replay":
        result = replay(args.stateless)
    else:
        from scripts.mao_hybrid import config
        from src.open_llm_vtuber.agent.hybrid.store import Store

        settings = config()
        if args.test_database:
            from scripts.mao_test import prepare_database

            prepare_database()
            settings = settings.model_copy(
                update={
                    "scope": "mao-synthetic-test",
                    "database_url_env": "MAO_TEST_DATABASE_URL",
                    "database_env_file": "private/mao-test.env",
                }
            )
        store = Store(settings)
        try:
            if args.command == "reset":
                store.clear_affect(**identity)
            state = store.read_affect(**identity)
            result = {
                "schema_version": 1,
                "enabled": settings.emotion_enabled,
                "state": affect_summary(state),
                "policy": response_policy(state),
                "reset": args.command == "reset",
                "context": "conversation" if key != "affect" else "shared_host",
                "reset_all_conversations": args.command == "reset" and key == "affect",
            }
        finally:
            store.close()
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
    print(content)
    return 0 if result.get("passed", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "unavailable", "error_type": type(error).__name__}))
        raise SystemExit(2) from None
