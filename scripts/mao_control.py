"""Stop a local Mao profile using a host-signed request and graceful Uvicorn exit."""

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
    parser.add_argument("operation", choices=["stop"])
    parser.add_argument(
        "--profile",
        choices=["local_dev", "local_companion", "test"],
        default="local_companion",
    )
    parser.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()
    port = 12394 if args.profile == "test" else 12393
    failed = False
    with httpx.Client(trust_env=False, timeout=15) as client:
        try:
            response = client.post(
                f"http://127.0.0.1:{port}/api/runtime/shutdown",
                headers={"X-Mao-Control": control_token(args.profile)},
            )
            response.raise_for_status()
            print(json.dumps({"server": "stopping", "profile": args.profile}))
        except httpx.ConnectError:
            print(json.dumps({"server": "already_stopped", "profile": args.profile}))
        except httpx.HTTPError as error:
            print(
                json.dumps(
                    {"server": "unavailable", "error_type": type(error).__name__}
                )
            )
            failed = True
        if args.dashboard:
            dashboard = 12396 if args.profile == "test" else 12395
            try:
                url = f"http://127.0.0.1:{dashboard}"
                client.headers["Origin"] = url
                token = client.get(url + "/api/playroom/session").json()["token"]
                response = client.post(
                    url + "/api/runtime/stop-dashboard", headers={"X-Mao-Token": token}
                )
                response.raise_for_status()
                print(json.dumps({"dashboard": "stopping"}))
            except httpx.ConnectError:
                pass
            except (httpx.HTTPError, ValueError, KeyError) as error:
                print(
                    json.dumps(
                        {"dashboard": "unavailable", "error_type": type(error).__name__}
                    )
                )
                failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
