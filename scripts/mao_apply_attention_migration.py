"""Apply additive migration 010; verify digests/counts without copying user data."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def snapshot(db):
    return {
        "persona_digest": db.execute(
            "SELECT md5(coalesce(string_agg(row_to_json(p)::text,'' ORDER BY scope),'')) AS value "
            "FROM mao_hybrid.character_profiles p"
        ).fetchone()["value"],
        **{
            table: db.execute(
                f"SELECT count(*) AS n FROM mao_hybrid.{table}"
            ).fetchone()["n"]
            for table in ("memories", "knowledge_items", "interaction_events")
        },
    }


def apply():
    from scripts.mao_hybrid import config, load_admin_env
    from src.open_llm_vtuber.agent.hybrid.store import Store

    load_admin_env()
    settings = config(use_profile=False)
    store = Store(
        settings.model_copy(update={"database_url_env": "MAO_DATABASE_ADMIN_URL"})
    )
    try:
        with store.connect() as db:
            db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            db.execute("SELECT pg_advisory_xact_lock(742019103)")
            before = snapshot(db)
            migration = (
                ROOT
                / "src/open_llm_vtuber/agent/hybrid/migrations/010_dialogue_attention.sql"
            )
            db.execute(migration.read_text(encoding="utf-8"))
            after = snapshot(db)
            if before != after:
                raise ValueError("Migration changed protected persona or memory data")
    finally:
        store.close()
    runtime = Store(settings)
    try:
        with runtime.connect() as db:
            version = db.execute(
                "SELECT max(version) AS n FROM mao_hybrid.schema_versions"
            ).fetchone()["n"]
            db.execute(
                "SELECT topic_event,quiet_event,quiet_until FROM mao_hybrid.dialogue_focus LIMIT 0"
            )
    finally:
        runtime.close()
    return {
        "status": "applied",
        "schema_version": version,
        "runtime_role_can_read_new_columns": True,
        "protected_data_unchanged": before == after,
        "before": before,
        "after": after,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "logs/mao-attention-migration.json"
    )
    args = parser.parse_args()
    try:
        report = apply()
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
