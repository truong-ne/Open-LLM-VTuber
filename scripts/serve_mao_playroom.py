"""Loopback-only static UI with authenticated, narrowly scoped OBS preview APIs."""

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time
from urllib.parse import urlsplit

from mao_hybrid import ROOT
from mao_obs_rehearsal import Obs
from mao_playroom_obs import REGISTRY, frame, visibility
from src.open_llm_vtuber.agent.hybrid.autonomy import CONTROL, STATUS
from src.open_llm_vtuber.live.idle_host_storage import read_json, write_json


class PreviewBackend:
    def __init__(self):
        self.lock = threading.Lock()
        self.cached = None
        self.at = 0

    def profile(self):
        from mao_profile import load_profile

        return load_profile()

    def save_profile(self, document):
        from mao_profile import save_profile

        with self.lock:
            return save_profile(document)

    def status(self):
        try:
            record = json.loads(REGISTRY.read_text(encoding="utf-8"))
            return {
                "configured": record["collection"] == "Mao Playroom",
                "visible": record["visible"],
                "window": "Chrome · 2048",
            }
        except (OSError, ValueError, KeyError):
            return {"configured": False, "visible": False}

    def autonomy_status(self):
        status = read_json(STATUS)
        if not 0 <= time.time() - status.get("updated_at", 0) < 10:
            status = {"phase": "offline", "last_result": status.get("last_result")}
        return {
            **status,
            "paused": CONTROL.exists()
            and read_json(CONTROL).get("paused") is not False,
        }

    def autonomy_control(self, paused):
        with self.lock:
            write_json(CONTROL, {"paused": paused})
        return {"paused": paused}

    def image(self):
        with self.lock:
            if not self.status().get("visible"):
                raise PermissionError("Covered")
            if self.cached and time.monotonic() - self.at < 0.5:
                return self.cached
            obs = Obs()
            try:
                try:
                    self.cached = frame(obs)
                except PermissionError:
                    self.cached = None
                    visibility(obs, False)
                    raise
                self.at = time.monotonic()
                return self.cached
            finally:
                obs.ws.close()

    def set_visible(self, show):
        with self.lock:
            obs = Obs()
            try:
                self.cached = None
                return visibility(obs, show)
            finally:
                obs.ws.close()


def handler(token, port, backend):
    class Handler(SimpleHTTPRequestHandler):
        timeout = 5

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web_tool"), **kwargs)

        def valid_host(self):
            return self.headers.get("Host") in {
                f"127.0.0.1:{port}",
                f"localhost:{port}",
            }

        def response(self, status, data, mime="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.response(403, {"error": "Invalid host"})
            path = urlsplit(self.path).path
            if path == "/api/persona":
                if not secrets.compare_digest(
                    self.headers.get("X-Mao-Token", ""), token
                ):
                    return self.response(403, {"error": "Operator token required"})
                try:
                    return self.response(200, backend.profile())
                except Exception:
                    return self.response(503, {"error": "Persona database unavailable"})
            if path == "/api/playroom/session":
                return self.response(200, {"token": token, **backend.status()})
            if path == "/api/playroom/frame":
                if not secrets.compare_digest(
                    self.headers.get("X-Mao-Token", ""), token
                ):
                    return self.response(403, {"error": "Operator token required"})
                try:
                    return self.response(200, backend.image(), "image/png")
                except Exception:
                    return self.response(
                        503, {"error": "Selected game frame unavailable"}
                    )
            if path == "/api/autonomy/status":
                return self.response(200, backend.autonomy_status())
            if path.startswith("/api/"):
                return self.response(404, {"error": "Unknown API"})
            return super().do_GET()

        def do_POST(self):
            if (
                not self.valid_host()
                or self.headers.get("Origin")
                not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
                or not secrets.compare_digest(
                    self.headers.get("X-Mao-Token", ""), token
                )
            ):
                # Drain a small rejected request before closing the HTTP/1.0
                # connection; unread bodies otherwise cause TCP resets on Windows.
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if 0 < size <= 65536:
                        self.rfile.read(size)
                except (ValueError, OSError):
                    pass
                return self.response(403, {"error": "Local operator required"})
            path = urlsplit(self.path).path
            if path == "/api/persona/save":
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 65536:
                        return self.response(
                            413, {"error": "Profile exceeds size limit"}
                        )
                    document = json.loads(self.rfile.read(size))
                    return self.response(200, backend.save_profile(document))
                except (ValueError, TypeError):
                    return self.response(
                        409,
                        {
                            "error": "Profile invalid or changed elsewhere. Reload before saving."
                        },
                    )
                except Exception:
                    return self.response(503, {"error": "Persona database unavailable"})
            if path in {"/api/autonomy/pause", "/api/autonomy/resume"}:
                return self.response(
                    200, backend.autonomy_control(path.endswith("/pause"))
                )
            if path not in {"/api/playroom/hide", "/api/playroom/show"}:
                return self.response(404, {"error": "Unknown action"})
            try:
                return self.response(200, backend.set_visible(path.endswith("/show")))
            except Exception:
                return self.response(503, {"error": "OBS control unavailable"})

        def log_message(self, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=12395)
    args = parser.parse_args()
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        handler(secrets.token_urlsafe(32), args.port, PreviewBackend()),
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
