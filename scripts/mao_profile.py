"""Operator-only PostgreSQL persona commands. No Markdown/YAML personality fallback."""

import argparse
import json
from pathlib import Path
import sys

from mao_hybrid import config, Store
from src.open_llm_vtuber.agent.hybrid.persona import read_profile, write_profile


def profile_store(operator=False):
    settings = config()
    if operator:
        settings = settings.model_copy(
            update={"database_url_env": "MAO_DATABASE_ADMIN_URL"}
        )
    return Store(settings)


def load_profile():
    store = profile_store()
    try:
        return read_profile(store)
    finally:
        store.close()


def save_profile(document):
    store = profile_store(operator=True)
    try:
        return write_profile(store, document)
    finally:
        store.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["show", "save"])
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    if args.command == "save":
        if not args.file:
            parser.error("save requires --file with a profile document")
        result = save_profile(json.loads(args.file.read_text(encoding="utf-8")))
    else:
        result = load_profile()
    print(json.dumps(result, ensure_ascii=False, indent=2))
