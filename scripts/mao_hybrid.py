"""Operator-only setup/diagnostics/approvals. Never registered as a model tool."""

import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.open_llm_vtuber.agent.hybrid.config import HybridConfig  # noqa: E402
from src.open_llm_vtuber.agent.hybrid.store import Store  # noqa: E402


def config():
    import yaml

    file = yaml.safe_load((ROOT / "conf.yaml").read_text(encoding="utf-8"))
    return HybridConfig(
        **file["character_config"]["agent_config"]["agent_settings"][
            "basic_memory_agent"
        ].get("hybrid", {})
    )


def load_admin_env():
    path = ROOT / "private/mao-hybrid.env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key in {"MAO_DATABASE_ADMIN_URL", "MAO_APP_PASSWORD"}:
                os.environ.setdefault(key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "init-env",
            "migrate",
            "enable",
            "status",
            "pending",
            "approve",
            "deny-all",
            "reembed",
            "cancel",
        ],
    )
    parser.add_argument("request_id", nargs="?")
    args = parser.parse_args()
    if args.command == "init-env":
        path = ROOT / "private/mao-hybrid.env"
        path.parent.mkdir(exist_ok=True)
        owner, app = secrets.token_hex(24), secrets.token_hex(24)
        # Exclusive creation: never replace credentials for an existing volume.
        with path.open("x", encoding="utf-8") as file:
            file.write(
                f"POSTGRES_PASSWORD={owner}\nMAO_APP_PASSWORD={app}\n"
                f"MAO_DATABASE_URL=postgresql://mao_app:{app}@127.0.0.1:55432/mao\n"
                f"MAO_DATABASE_ADMIN_URL=postgresql://mao_owner:{owner}@127.0.0.1:55432/mao\n"
            )
        print("Created private credentials; no credentials printed.")
        return
    if args.command == "enable":
        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.preserve_quotes = True
        template = yaml.load(ROOT / "config_templates/mao.hybrid.yaml")
        for name in ("conf.yaml", "characters/mao_live.yaml"):
            path = ROOT / name
            document = yaml.load(path)
            character = document["character_config"]
            settings = (
                character.setdefault("agent_config", {})
                .setdefault("agent_settings", {})
                .setdefault("basic_memory_agent", {})
            )
            settings.setdefault("hybrid", template["hybrid"])
            with path.open("w", encoding="utf-8") as file:
                yaml.dump(document, file)
        print(
            "Hybrid enabled; computer/exploration remain operator-configured. Restart backend to load."
        )
        return
    settings = config()
    load_admin_env()
    if args.command in {"migrate", "approve", "deny-all"}:
        if not os.environ.get("MAO_DATABASE_ADMIN_URL"):
            raise RuntimeError("Operator DSN MAO_DATABASE_ADMIN_URL is required")
        os.environ["MAO_OPERATOR_DSN"] = os.environ["MAO_DATABASE_ADMIN_URL"]
        settings = settings.model_copy(update={"database_url_env": "MAO_OPERATOR_DSN"})
    store = Store(settings)
    try:
        if args.command == "migrate":
            from psycopg import sql

            store.migrate()
            password = os.environ.get("MAO_APP_PASSWORD")
            if password:
                with store.connect() as db:
                    exists = db.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname='mao_app'"
                    ).fetchone()
                    if not exists:
                        db.execute(
                            sql.SQL("CREATE ROLE mao_app LOGIN PASSWORD {}").format(
                                sql.Literal(password)
                            )
                        )
                    db.execute("GRANT USAGE ON SCHEMA mao_hybrid TO mao_app")
                    db.execute(
                        "GRANT SELECT,INSERT,UPDATE,DELETE ON mao_hybrid.memories,mao_hybrid.state,mao_hybrid.events,mao_hybrid.learning_turns,mao_hybrid.learning_days,mao_hybrid.learning_profiles TO mao_app"
                    )
                    db.execute(
                        "GRANT SELECT ON mao_hybrid.schema_versions,mao_hybrid.character_profiles TO mao_app"
                    )
                    db.execute(
                        "GRANT SELECT ON mao_hybrid.learning_feedback TO mao_app"
                    )
                    db.execute(
                        "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA mao_hybrid TO mao_app"
                    )
                    db.execute("GRANT SELECT,DELETE ON mao_hybrid.approvals TO mao_app")
                    db.execute(
                        "GRANT INSERT(id,scope,payload,expires) ON mao_hybrid.approvals TO mao_app"
                    )
            print(
                "Migrations applied; runtime role cannot approve browser actions or alter schema."
            )
        elif args.command == "approve":
            with store.connect() as db:
                row = db.execute(
                    "SELECT payload,expires FROM mao_hybrid.approvals WHERE id=%s AND scope=%s AND expires>now()",
                    (args.request_id, settings.scope),
                ).fetchone()
            if not row:
                raise ValueError("Request is missing or expired")
            print(json.dumps(row["payload"], ensure_ascii=False, indent=2))
            if input("Type APPROVE to authorize this exact action once: ") != "APPROVE":
                raise ValueError("Not approved")
            with store.connect() as db:
                from psycopg.types.json import Jsonb

                approved = db.execute(
                    "UPDATE mao_hybrid.approvals SET approved=true WHERE id=%s AND scope=%s AND expires=%s AND payload=%s AND expires>now() RETURNING id",
                    (
                        args.request_id,
                        settings.scope,
                        row["expires"],
                        Jsonb(row["payload"]),
                    ),
                ).fetchone()
                if not approved:
                    raise ValueError(
                        "Request expired or changed while being reviewed; inspect the current request again"
                    )
            store.event("operator_approval", {"request_id": args.request_id})
            print("Approved once. Mao must retry before expiry.")
        elif args.command == "deny-all":
            with store.connect() as db:
                db.execute(
                    "DELETE FROM mao_hybrid.approvals WHERE scope=%s", (settings.scope,)
                )
            print("All pending approvals revoked.")
        elif args.command == "pending":
            with store.connect() as db:
                rows = db.execute(
                    "SELECT id,payload,expires,approved FROM mao_hybrid.approvals WHERE scope=%s AND expires>now()",
                    (settings.scope,),
                ).fetchall()
            print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
        elif args.command == "reembed":
            print(
                json.dumps(
                    {
                        "reembedded": store.reembed(),
                        "embedding_status": store.embedding_status,
                    }
                )
            )
        elif args.command == "cancel":
            print(json.dumps({"goal": store.cancel_goal()}, ensure_ascii=False))
        elif args.command == "status":
            with store.connect() as db:
                row = db.execute(
                    "SELECT count(*) AS memories,count(embedding) AS vectors FROM mao_hybrid.memories WHERE scope=%s",
                    (settings.scope,),
                ).fetchone()
                version = db.execute(
                    "SELECT extversion FROM pg_extension WHERE extname='vector'"
                ).fetchone()
            print(
                json.dumps(
                    {
                        **row,
                        "pgvector": version["extversion"],
                        "search_mode": settings.search_mode,
                        "goal": store.get("goal"),
                    },
                    default=str,
                )
            )
    finally:
        store.close()


if __name__ == "__main__":
    main()
