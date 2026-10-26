import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from src.open_llm_vtuber.agent.hybrid.autonomy import (
    AutonomyService,
    AutonomyLedger,
    PublicReader,
    LocalCuriosityModel,
    valid_title,
    knowledge_content,
    valid_spark,
)
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig


class CuriosityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.seed_patch = patch(
            "src.open_llm_vtuber.agent.hybrid.autonomy.SEEDS", ["Aurora", "Cat"]
        )
        self.seed_patch.start()
        self.addCleanup(self.seed_patch.stop)
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.config = HybridConfig(autonomy={"enabled": True})
        self.store = Mock()
        self.store.get.return_value = {}
        self.reader, self.model = (
            SimpleNamespace(read=AsyncMock(), close=AsyncMock()),
            SimpleNamespace(
                choose=AsyncMock(return_value=("Aurora", "qwen_choice")),
                reflect=AsyncMock(),
                close=AsyncMock(),
            ),
        )
        text = "An aurora is a natural light display in Earth's sky. It is predominantly seen in high-latitude regions."
        self.article = {
            "title": "Aurora",
            "requested_title": "Aurora",
            "text": text,
            "source": "https://en.wikipedia.org/wiki/Aurora",
            "revision": "123",
            "related": ["Earth"],
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        self.reader.read.return_value = self.article
        self.model.reflect.return_value = (
            text[:51],
            "Thiếp muốn tìm hiểu thêm về ánh sáng.",
            "qwen_grounded_quote",
        )
        self.service = AutonomyService(
            self.config,
            store=self.store,
            reader=self.reader,
            model=self.model,
            control=root / "control.json",
            status=root / "status.json",
        )
        self.service.ledger = Mock()
        self.service.ledger.claim.return_value = {
            "token": "lease",
            "state": {},
            "now": time.time(),
        }

    async def asyncTearDown(self):
        await self.service.close()
        self.directory.cleanup()

    async def test_real_evidence_is_saved_as_unverified_external_claim(self):
        self.assertTrue(await self.service.cycle())
        self.store.remember.assert_called_once()
        args = self.store.remember.call_args
        self.assertEqual(args.args[:2], ("long_term", "shared"))
        self.assertEqual(args.args[3], "unverified_claim")
        self.assertFalse(json.loads(args.kwargs["evidence"])["verified_truth"])
        record = self.service.ledger.finish.call_args.args[1]
        self.assertEqual(record["status"], "completed")
        self.assertFalse(record["reflection_verified"])

    async def test_page_or_model_cannot_invent_a_topic_or_save_ungrounded_text(self):
        self.model.choose.return_value = (
            "https://attacker.example/private",
            "injected",
        )
        self.assertFalse(await self.service.cycle())
        self.reader.read.assert_not_awaited()
        self.store.remember.assert_not_called()
        self.model.choose.return_value = ("Aurora", "qwen_choice")
        self.model.reflect.return_value = (
            "This sentence does not occur in the observed source article at all.",
            "",
            "injected",
        )
        self.assertFalse(await self.service.cycle())
        self.store.remember.assert_not_called()

    async def test_incoming_human_cancels_network_work_and_does_not_claim_learning(
        self,
    ):
        started = asyncio.Event()

        async def reading(title):
            started.set()
            await asyncio.Event().wait()

        self.reader.read.side_effect = reading
        task = self.service.cycle_task = asyncio.create_task(self.service.cycle())
        await started.wait()
        self.service.observe_input({"type": "live-comment", "text": "hello"})
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.store.remember.assert_not_called()
        self.assertEqual(
            self.service.ledger.finish.call_args.args[1]["status"], "interrupted"
        )

    async def test_pause_and_speech_prevent_source_work(self):
        self.service.control.write_text('{"paused":true}')
        with self.assertRaises(asyncio.CancelledError):
            await self.service.cycle()
        self.reader.read.assert_not_awaited()
        self.service.control.write_text("malformed")
        self.assertTrue(self.service.paused())
        self.service.control.write_text('{"paused":false}')
        self.service.busy = lambda: True
        with self.assertRaises(asyncio.CancelledError):
            await self.service.cycle()

    async def test_exhausted_daily_budget_does_not_call_model_or_source(self):
        self.service.ledger.claim.return_value = None
        self.assertFalse(await self.service.cycle())
        self.model.choose.assert_not_awaited()
        self.reader.read.assert_not_awaited()

    async def test_successful_topics_are_not_read_again_within_a_day(self):
        self.service.ledger.claim.return_value["state"] = {
            "learned": {"Aurora": time.time()}
        }
        self.model.choose.return_value = ("Cat", "qwen_choice")
        await self.service.cycle()
        self.assertNotIn("Aurora", self.model.choose.call_args.args[0])

    async def test_model_outage_falls_back_without_fabricating_reflection(self):
        model = LocalCuriosityModel("test")
        try:
            with patch.object(
                model, "ask", new=AsyncMock(side_effect=httpx.ConnectError("offline"))
            ):
                title, status = await model.choose(["Aurora", "Cat"])
                self.assertEqual(title, "Aurora")
                self.assertIn("fallback", status)
                excerpt, thought, status = await model.reflect(self.article)
                self.assertIn(excerpt, self.article["text"])
                self.assertEqual(thought, "")
        finally:
            await model.close()

    async def test_idle_loop_waits_and_closes_cleanly_without_viewer_count(self):
        self.service.last_human = time.monotonic()
        task = asyncio.create_task(self.service.run())
        await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.service.ledger.claim.assert_not_called()
        self.assertEqual(self.service.phase, "stopped")

    async def test_model_selects_evidence_id_and_cannot_replace_the_quote(self):
        model = LocalCuriosityModel("test")
        try:
            with patch.object(
                model,
                "ask",
                new=AsyncMock(
                    return_value={
                        "quote_index": 0,
                        "quote": "invented",
                        "reflection": "Thiếp muốn tìm hiểu thêm.",
                    }
                ),
            ):
                quote, thought, status = await model.reflect(self.article)
                self.assertIn(quote, self.article["text"])
                self.assertNotEqual(quote, "invented")
                self.assertEqual(status, "qwen_grounded_quote")
            for index in (-1, 99, True, "0"):
                with patch.object(
                    model,
                    "ask",
                    new=AsyncMock(
                        return_value={"quote_index": index, "reflection": "invented"}
                    ),
                ):
                    _, thought, status = await model.reflect(self.article)
                    self.assertEqual(thought, "")
                    self.assertIn("source_excerpt_only", status)
        finally:
            await model.close()


class PublicSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_fixed_get_endpoints_and_numeric_revision_are_accepted(self):
        calls = []

        def respond(request):
            calls.append(request)
            if request.url.path.startswith("/api/rest_v1/"):
                return httpx.Response(
                    200,
                    json={
                        "title": "Aurora",
                        "type": "standard",
                        "revision": "12",
                        "extract": "A source observation. " * 10,
                    },
                )
            return httpx.Response(
                200,
                json={
                    "query": {
                        "pages": [
                            {
                                "links": [
                                    {"title": "Earth"},
                                    {"title": "https://attacker.example"},
                                ]
                            }
                        ]
                    }
                },
            )

        reader = PublicReader(httpx.MockTransport(respond))
        try:
            result = await reader.read("Aurora")
            self.assertEqual(result["related"], ["Earth"])
            self.assertEqual(len(calls), 2)
            self.assertTrue(
                all(
                    r.method == "GET" and r.url.host == "en.wikipedia.org"
                    for r in calls
                )
            )
            for title in ("https://localhost/", "User:Private", "a@b.com", "../secret"):
                self.assertFalse(valid_title(title))
        finally:
            await reader.close()

    async def test_redirect_and_oversized_source_are_rejected(self):
        for response in (
            httpx.Response(302, headers={"location": "http://127.0.0.1/secret"}),
            httpx.Response(
                200, headers={"content-type": "application/json"}, content=b"x" * 65537
            ),
        ):
            reader = PublicReader(httpx.MockTransport(lambda _: response))
            try:
                with self.assertRaises((httpx.HTTPError, ValueError)):
                    await reader.read("Aurora")
            finally:
                await reader.close()


class InputIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def test_thought_validation_has_no_fixed_pronouns_or_personality(self):
        self.assertTrue(valid_spark("I prefer a quiet topic."))
        self.assertTrue(valid_spark("Chúng tôi muốn khám phá âm nhạc."))
        self.assertFalse(valid_spark(""))
        self.assertFalse(valid_spark("x" * 351))
        self.assertFalse(valid_spark(None))

    def test_knowledge_content_does_not_seed_old_character_preferences(self):
        self.assertIn("Ocean:", knowledge_content("Ocean", "source excerpt"))
        self.assertNotIn("thiếp", knowledge_content("Ocean", "source excerpt"))

    async def test_direct_websocket_notifies_autonomy_before_routing_input(self):
        from starlette.websockets import WebSocketDisconnect
        from src.open_llm_vtuber.websocket_handler import WebSocketHandler

        events = []
        autonomy = SimpleNamespace(
            observe_input=lambda message: events.append("preempt")
        )
        handler = WebSocketHandler(SimpleNamespace(autonomy=autonomy))
        handler._route_message = AsyncMock(
            side_effect=lambda *args: events.append("route")
        )
        socket = SimpleNamespace(
            receive_json=AsyncMock(
                side_effect=[
                    {"type": "text-input", "text": "hello"},
                    WebSocketDisconnect(),
                ]
            )
        )
        with self.assertRaises(WebSocketDisconnect):
            await handler.handle_websocket_communication(socket, "test")
        self.assertEqual(events, ["preempt", "route"])


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class LedgerIntegrationTests(unittest.TestCase):
    def test_lease_cooldown_restart_and_stale_worker(self):
        import uuid
        from scripts.mao_hybrid import config
        from src.open_llm_vtuber.agent.hybrid.store import Store

        settings = config().model_copy(
            update={"scope": "test-autonomy-" + uuid.uuid4().hex}
        )
        store = Store(settings)
        try:
            ledger = AutonomyLedger(
                store, settings.autonomy, settings.learning_timezone
            )
            first = ledger.claim()
            self.assertIsNotNone(first)
            self.assertIsNone(
                AutonomyLedger(
                    store, settings.autonomy, settings.learning_timezone
                ).claim()
            )
            self.assertFalse(ledger.finish("stale-token", {"status": "completed"}))
            self.assertTrue(
                ledger.finish(
                    first["token"], {"status": "interrupted", "title": "Aurora"}
                )
            )
            self.assertIsNone(ledger.claim())
            self.assertEqual(store.get("autonomy")["attempts"], 1)
            state = store.get("autonomy")
            state.update(attempts=settings.autonomy.daily_cycles, last_attempt=0)
            store.put("autonomy", state)
            self.assertIsNone(ledger.claim())
            state.update(day="2000-01-01", learned={"Cat": 123}, last_attempt=0)
            store.put("autonomy", state)
            next_day = ledger.claim()
            self.assertIsNotNone(next_day)
            self.assertEqual(next_day["state"]["attempts"], 1)
            self.assertEqual(next_day["state"]["learned"], {"Cat": 123})
        finally:
            with store.connect() as db:
                db.execute(
                    "DELETE FROM mao_hybrid.state WHERE scope=%s", (store.scope,)
                )
                db.execute(
                    "DELETE FROM mao_hybrid.events WHERE scope=%s", (store.scope,)
                )
            store.close()
