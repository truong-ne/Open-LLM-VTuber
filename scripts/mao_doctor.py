"""Read-only local runtime diagnostics. Never prints DSNs, prompts or credentials."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def local_models(url):
    import httpx

    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username:
        return {"status": "skipped_nonlocal"}
    base = url.rsplit("/v1", 1)[0].rstrip("/")
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(base + "/api/tags")
            response.raise_for_status()
            return {
                "status": "ok",
                "models": [
                    {"name": item.get("name"), "digest": item.get("digest")}
                    for item in response.json()["models"]
                ],
            }
    except Exception as error:
        return {"status": "unavailable", "error_type": type(error).__name__}


def database_status(settings):
    import psycopg
    from src.open_llm_vtuber.agent.hybrid.store import resolve_dsn

    try:
        with psycopg.connect(
            resolve_dsn(settings),
            connect_timeout=3,
            options="-c default_transaction_read_only=on -c statement_timeout=3000",
        ) as db:
            versions = [
                row[0]
                for row in db.execute(
                    "SELECT version FROM mao_hybrid.schema_versions ORDER BY version"
                )
            ]
        expected = sorted(
            int(p.name.split("_", 1)[0])
            for p in (ROOT / "src/open_llm_vtuber/agent/hybrid/migrations").glob(
                "*.sql"
            )
        )
        return {
            "status": "ok" if set(expected) <= set(versions) else "migration_required",
            "applied": versions,
            "expected": expected,
        }
    except Exception as error:
        return {"status": "unavailable", "error_type": type(error).__name__}


def collect(profile):
    from src.open_llm_vtuber.config_manager import read_yaml, validate_config
    from src.open_llm_vtuber.runtime_profile import effective_summary

    os.environ["MAO_RUNTIME_PROFILE"] = profile
    config = validate_config(read_yaml(str(ROOT / "conf.yaml")))
    summary = effective_summary(config)
    basic = config.character_config.agent_config.agent_settings.basic_memory_agent
    provider = getattr(
        config.character_config.agent_config.llm_configs, basic.llm_provider
    )
    report = {
        "schema_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "effective": summary,
        "config_digest": hashlib.sha256(
            json.dumps(summary, sort_keys=True).encode()
        ).hexdigest(),
        "hardware": {
            "os": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "ports": {
            str(port): port_open("127.0.0.1", port)
            for port in {config.system_config.port, 11434, 55432, 55433}
        },
        "database": database_status(basic.hybrid)
        if basic.hybrid.enabled
        else {"status": "disabled"},
        "providers": {
            "llm": local_models(getattr(provider, "base_url", "")),
            "embedding": local_models(basic.hybrid.embedding_url.rsplit("/api/", 1)[0]),
        },
        "process_scope": "local backend only; external idle/live workers are separate processes",
    }
    for kind, expected in (
        ("llm", summary["model"]),
        ("embedding", basic.hybrid.embedding_model),
    ):
        provider_report = report["providers"][kind]
        expected = expected if expected and ":" in expected else f"{expected}:latest"
        provider_report["configured_model"] = expected
        if provider_report["status"] == "ok":
            provider_report["configured_model_available"] = any(
                model["name"] == expected for model in provider_report["models"]
            )
    report["processes"] = {"status": "unavailable"}
    if platform.system() == "Windows":
        try:
            output = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=4,
                check=True,
            )
            report["processes"] = {
                "status": "ok",
                "items": [
                    {"name": row[0], "pid": int(row[1])}
                    for row in csv.reader(output.stdout.splitlines())
                    if len(row) > 1
                    and row[0].lower()
                    in {
                        "python.exe",
                        "ollama.exe",
                        "docker desktop.exe",
                        "com.docker.backend.exe",
                    }
                ],
            }
        except Exception as error:
            report["processes"]["error_type"] = type(error).__name__
    gpu = shutil.which("nvidia-smi")
    report["hardware"]["gpu"] = {"status": "unavailable"}
    if gpu:
        try:
            output = subprocess.run(
                [
                    gpu,
                    "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=4,
                check=True,
            )
            report["hardware"]["gpu"] = {
                "status": "ok",
                "csv_columns": ["name", "total_mib", "used_mib", "utilization_percent"],
                "devices": list(csv.reader(output.stdout.splitlines())),
            }
        except Exception as error:
            report["hardware"]["gpu"] = {
                "status": "unavailable",
                "error_type": type(error).__name__,
            }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("local_dev", "test", "local_companion", "live"),
        default="local_companion",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = collect(args.profile)
    except Exception as error:
        print(
            json.dumps(
                {"status": "configuration_error", "error_type": type(error).__name__}
            )
        )
        return 1
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    ready = report["database"]["status"] in {"ok", "disabled"} and all(
        value.get("configured_model_available")
        for value in report["providers"].values()
    )
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
