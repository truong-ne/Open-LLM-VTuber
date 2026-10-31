"""Synthetic 40/20 policy comparison plus real PostgreSQL hard gates in test DB."""

import argparse
import asyncio
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from loguru import logger

    logger.remove()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default='{"verbosity":"brief"}')
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from scripts.mao_test import prepare_database

    prepare_database()
    settings = json.loads(args.candidate)
    from src.open_llm_vtuber.character.development import CHOICES

    if not isinstance(settings, dict) or any(
        key not in CHOICES or value not in CHOICES[key]
        for key, value in settings.items()
    ):
        raise ValueError("Unsupported candidate setting")
    suite = unittest.defaultTestLoader.loadTestsFromName("test_runtime_architecture")
    hard = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    from src.open_llm_vtuber.learning.evaluation import compare

    report = {
        "schema_version": 1,
        "synthetic": True,
        "hard_gates": {
            "tests": hard.testsRun,
            "failures": len(hard.failures) + len(hard.errors),
            "skipped": len(hard.skipped),
        },
        "runs": [
            asyncio.run(compare(settings, split))
            for split in ("development", "held_out")
        ],
    }
    report["passed"] = (
        hard.wasSuccessful()
        and not hard.skipped
        and not any(run["hard_failures"] for run in report["runs"])
    )
    report["limitations"] = (
        "Mechanical controller evaluation; promotion also requires independently sourced real-session feedback."
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "unavailable", "error_type": type(error).__name__}))
        raise SystemExit(2) from None
