"""Local operator controls for the separate Vua Tieng Viet classroom."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import httpx
    from src.open_llm_vtuber.interaction.ingress import control_token

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["on", "off", "status"])
    parser.add_argument("--account", default="@thanhoathirty6")
    parser.add_argument("--port", type=int, default=12393)
    parser.add_argument(
        "--profile",
        default="local_companion",
        choices=["local_companion", "local_dev", "live", "test"],
    )
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    try:
        with httpx.Client(trust_env=False, timeout=10) as client:
            if args.operation == "status":
                response = client.get(base + "/api/vuatiengviet/state")
            else:
                response = client.post(
                    base + "/api/classroom/control",
                    headers={"X-Mao-Control": control_token(args.profile)},
                    json={
                        "enabled": args.operation == "on",
                        "account": args.account,
                    },
                )
            response.raise_for_status()
            state = response.json()
            if "classroom" not in state:
                print("Backend needs restarting to load the classroom feature.")
                return 1
            summary = {
                k: v
                for k, v in state["classroom"].items()
                if k not in {"standings", "seats"}
            }
            print(json.dumps(summary, ensure_ascii=False))
            return 0
    except httpx.HTTPError as error:
        print(
            f"Classroom unavailable: {type(error).__name__}. Start/restart Mao backend; check profile and port."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
