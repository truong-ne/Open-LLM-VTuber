"""Initialize credentials or migrate the separate synthetic test database."""

import argparse
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init-env", "migrate"))
    args = parser.parse_args()
    if args.command == "init-env":
        owner, app = secrets.token_hex(24), secrets.token_hex(24)
        path = ROOT / "private/mao-test.env"
        path.parent.mkdir(exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(
                f"POSTGRES_PASSWORD={owner}\nMAO_TEST_APP_PASSWORD={app}\n"
                f"MAO_TEST_DATABASE_URL=postgresql://mao_app:{app}@127.0.0.1:55433/mao_test\n"
                f"MAO_TEST_DATABASE_ADMIN_URL=postgresql://mao_owner:{owner}@127.0.0.1:55433/mao_test\n"
            )
        print("Created private/mao-test.env; no credentials printed.")
        return
    from scripts.mao_test import prepare_database
    from scripts import mao_hybrid

    prepare_database()
    password = os.environ.get("MAO_TEST_APP_PASSWORD")
    if not password:
        raise ValueError("Test application password required")
    os.environ["MAO_APP_PASSWORD"] = password
    # Reuse the operator migration/grants against the already validated test DSN.
    sys.argv = ["mao_hybrid.py", "migrate"]
    mao_hybrid.main()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"Test database setup failed ({type(error).__name__}); no credentials printed.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
