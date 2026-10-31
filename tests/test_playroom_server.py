import sys
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from serve_mao_playroom import handler


class Backend:
    visible = True

    def status(self):
        return {"configured": True, "visible": self.visible}

    def image(self):
        return b"PNG-test-frame"

    def set_visible(self, value):
        self.visible = value
        return {"visible": value}

    paused = False

    def autonomy_status(self):
        return {"paused": self.paused, "phase": "waiting_for_idle"}

    def autonomy_control(self, paused):
        self.paused = paused
        return {"paused": paused}

    def profile(self):
        return {
            "revision": 1,
            "status": "draft",
            "prompt": "",
            "proactive_prompt": "",
            "autonomy_prompt": "",
            "topics": [],
        }

    def save_profile(self, document):
        return {**document, "revision": document["revision"] + 1}

    def memories(self, **options):
        self.memory_options = options
        return {
            "items": [],
            "total": 0,
            "page": 1,
            "pages": 1,
            "summary": {"total": 0, "active": 0, "expired": 0},
        }

    def memory(self, memory_id):
        return (
            {"id": "42", "content": "literal <script>"} if memory_id == "42" else None
        )

    def runtime(self, operation="state", value=None):
        if operation == "action" and value.get("operation") != "retention":
            raise ValueError("Unsupported action")
        return {"operation": operation, "value": value}


class PlayroomServerTests(unittest.TestCase):
    def test_runtime_reads_and_mutations_require_local_operator_authorization(self):
        headers = {
            "X-Mao-Token": "test-token",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        self.assertEqual(self.client.get("/api/runtime/state").status_code, 403)
        allowed = self.client.get("/api/runtime/state", headers=headers)
        self.assertEqual(allowed.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", allowed.headers)
        self.assertEqual(
            self.client.get(
                "/api/runtime/state",
                headers={**headers, "Origin": "https://other.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/runtime/action", json={"operation": "retention"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/runtime/action", headers=headers, json={"operation": "retention"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/runtime/action",
                headers=headers,
                json={"operation": "arbitrary_sql"},
            ).status_code,
            409,
        )

    def setUp(self):
        self.backend = Backend()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler("test-token", 0, self.backend)
        )
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = handler("test-token", self.port, self.backend)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.client = httpx.Client(
            base_url=f"http://127.0.0.1:{self.port}", trust_env=False
        )

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def test_frame_is_private_and_no_cors_is_granted(self):
        self.assertEqual(self.client.get("/api/playroom/frame").status_code, 403)
        response = self.client.get(
            "/api/playroom/frame", headers={"X-Mao-Token": "test-token"}
        )
        self.assertEqual(response.content, b"PNG-test-frame")
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_persona_read_and_write_require_operator_token_and_same_origin(self):
        self.assertEqual(self.client.get("/api/persona").status_code, 403)
        token = {"X-Mao-Token": "test-token"}
        self.assertEqual(
            self.client.get("/api/persona", headers=token).json()["prompt"], ""
        )
        body = {"revision": 1, "status": "draft", "prompt": "new draft"}
        self.assertEqual(
            self.client.post("/api/persona/save", headers=token, json=body).status_code,
            403,
        )
        response = self.client.post(
            "/api/persona/save",
            headers={**token, "Origin": f"http://127.0.0.1:{self.port}"},
            json=body,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 2)

    def test_memories_require_operator_token_and_local_origin(self):
        token = {"X-Mao-Token": "test-token"}
        for path in ("/api/memories", "/api/memories/42"):
            self.assertEqual(self.client.get(path).status_code, 403)
            self.assertEqual(
                self.client.get(
                    path, headers={**token, "Origin": "https://attacker.example"}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.get(
                    path, headers={**token, "Host": "attacker.example"}
                ).status_code,
                403,
            )
            self.assertEqual(self.client.get(path, headers=token).status_code, 200)
        self.assertNotIn(
            "Access-Control-Allow-Origin",
            self.client.get("/api/memories", headers=token).headers,
        )

    def test_memory_filters_are_bounded_and_detail_not_found_is_explicit(self):
        token = {"X-Mao-Token": "test-token"}
        result = self.client.get(
            "/api/memories",
            params={"q": "trà", "kind": "social", "state": "all", "page": 2},
            headers=token,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            self.backend.memory_options,
            {"query": "trà", "kind": "social", "state": "all", "page": 2},
        )
        for query in ("scope=other", "page=0", "kind=invalid", "q=one&q=two"):
            self.assertEqual(
                self.client.get("/api/memories?" + query, headers=token).status_code,
                400,
            )
        self.assertEqual(
            self.client.get("/api/memories/43", headers=token).status_code, 404
        )
        self.assertEqual(
            self.client.get("/api/memories/42?scope=other", headers=token).status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/api/memories/42", headers=token).json()["content"],
            "literal <script>",
        )

    def test_memory_database_failure_is_not_reported_as_empty_data(self):
        from unittest.mock import patch

        with patch.object(
            self.backend, "memories", side_effect=RuntimeError("offline")
        ):
            self.assertEqual(
                self.client.get(
                    "/api/memories", headers={"X-Mao-Token": "test-token"}
                ).status_code,
                503,
            )

    def test_foreign_origin_and_dns_rebinding_host_cannot_control_capture(self):
        response = self.client.post(
            "/api/playroom/hide",
            headers={"X-Mao-Token": "test-token", "Origin": "https://attacker.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.backend.visible)
        self.assertEqual(
            self.client.get(
                "/api/playroom/session", headers={"Host": "attacker.example"}
            ).status_code,
            403,
        )

    def test_only_explicit_hide_show_actions_are_available(self):
        headers = {
            "X-Mao-Token": "test-token",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        self.assertEqual(
            self.client.post("/api/playroom/hide", headers=headers).status_code, 200
        )
        self.assertFalse(self.backend.visible)
        self.assertEqual(
            self.client.post("/api/playroom/start-stream", headers=headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.post("/api/playroom/show", headers=headers).status_code, 200
        )
        self.assertTrue(self.backend.visible)

    def test_autonomy_pause_resume_requires_local_operator_and_cannot_expand_permissions(
        self,
    ):
        headers = {
            "X-Mao-Token": "test-token",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        self.assertEqual(self.client.post("/api/autonomy/pause").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/autonomy/pause",
                headers={**headers, "Origin": "https://attacker.example"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/autonomy/pause", headers=headers).status_code, 200
        )
        self.assertTrue(self.client.get("/api/autonomy/status").json()["paused"])
        self.assertEqual(
            self.client.post("/api/autonomy/resume", headers=headers).status_code, 200
        )
        self.assertFalse(self.backend.paused)
        self.assertEqual(
            self.client.post(
                "/api/autonomy/enable-all-tools", headers=headers
            ).status_code,
            404,
        )
