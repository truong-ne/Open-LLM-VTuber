"""Refuse integration writes unless both roles use a dedicated test database."""

import os


def database_identity(dsn):
    from psycopg.conninfo import conninfo_to_dict

    info = conninfo_to_dict(dsn)
    # Do not let implicit libpq defaults or service aliases evade comparison.
    if not all(info.get(key) for key in ("host", "port", "dbname")):
        raise ValueError("Test DSNs require explicit host, port and dbname")
    if info.get("service") or info.get("hostaddr") or "," in info["host"]:
        raise ValueError("Test DSNs must identify a single explicit endpoint")
    host = info["host"].lower()
    if host in {"localhost", "::1", "127.0.0.1"}:
        host = "loopback"
    return host, int(info["port"]), info["dbname"]


def assert_test_database(dsn, production_dsns=()):
    try:
        identity = database_identity(dsn)
        if not identity[2].endswith("_test"):
            raise ValueError("Dedicated test database name must end with _test")
        for production in production_dsns:
            if production and identity == database_identity(production):
                raise ValueError("Test database matches production")
    except Exception:
        # libpq error messages can contain the credential-bearing input.
        raise ValueError(
            "Unsafe test database configuration; refusing database access"
        ) from None


def production_dsns(config):
    from pathlib import Path
    from .agent.hybrid.store import ROOT

    production = []
    # Always include the production file even when the test config uses another file.
    for path in {
        ROOT / "private/mao-hybrid.env",
        ROOT / Path(config.database_env_file),
    }:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() in {"MAO_DATABASE_URL", "MAO_DATABASE_ADMIN_URL"}:
                    production.append(value.strip().strip("\"'"))
    if not os.environ.get("MAO_TEST_POSTGRES"):
        production.extend(
            os.environ.get(name, "")
            for name in ("MAO_DATABASE_URL", "MAO_DATABASE_ADMIN_URL")
        )
    return production


def guard_integration_dsn(dsn, config):
    if not (
        os.environ.get("MAO_TEST_POSTGRES")
        or os.environ.get("MAO_TEST_BROWSER")
        or os.environ.get("MAO_RUNTIME_PROFILE") == "test"
    ):
        return
    assert_test_database(dsn, production_dsns(config))
