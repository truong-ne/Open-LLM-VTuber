"""Run unittest with optional, explicitly isolated PostgreSQL integration tests."""

import argparse
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare_database():
    from src.open_llm_vtuber.testing import (
        assert_test_database,
        database_identity,
        production_dsns,
    )
    from scripts.mao_hybrid import config

    production = production_dsns(config(use_profile=False))
    path = ROOT / "private/mao-test.env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key in {
                "MAO_TEST_DATABASE_URL",
                "MAO_TEST_DATABASE_ADMIN_URL",
                "MAO_TEST_APP_PASSWORD",
            }:
                os.environ.setdefault(key, value.strip().strip("\"'"))
    runtime = os.environ.get("MAO_TEST_DATABASE_URL", "")
    admin = os.environ.get("MAO_TEST_DATABASE_ADMIN_URL", "")
    for dsn in (runtime, admin):
        assert_test_database(dsn, production)
    if database_identity(runtime) != database_identity(admin):
        raise ValueError("Test runtime and admin must use the same test database")
    # Old integration tests read these names; never load production secrets over them.
    os.environ.update(
        MAO_DATABASE_URL=runtime, MAO_DATABASE_ADMIN_URL=admin, MAO_TEST_POSTGRES="1"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true")
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args()
    if args.postgres:
        prepare_database()
    else:
        os.environ.pop("MAO_TEST_POSTGRES", None)
        os.environ.pop("MAO_TEST_BROWSER", None)
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), pattern=args.pattern
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(
        f"Executed: {result.testsRun}; skipped: {len(result.skipped)}; "
        f"failures: {len(result.failures)}; errors: {len(result.errors)}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError:
        print(
            "Unsafe test database configuration; tests were not started.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
