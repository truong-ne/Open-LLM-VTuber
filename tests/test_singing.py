import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock
import wave

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber.live.singing import (
    SongCatalog,
    SingingService,
    parse_song_command,
)
from src.open_llm_vtuber.live.vua_tieng_viet import WordGameService
from src.open_llm_vtuber.live.buffered_chat import BufferedLiveChat
from src.open_llm_vtuber.live.idle_host import ChatActivity, IdleHost
from src.open_llm_vtuber.proxy_handler import ProxyHandler
from src.open_llm_vtuber.routes import init_proxy_route


class Clock:
    value = 0

    def now(self):
        return self.value

    def wall(self):
        return 1000 + self.value


class SongFixture:
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        with wave.open(str(self.root / "demo.wav"), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\0\0" * 8000)
        self.manifest = self.root / "songs.json"
        self.row = {
            "id": "bai-thu",
            "title": "Bài thử",
            "file": "demo.wav",
            "aliases": ["demo"],
            "bpm": 100,
        }
        self.write([self.row])
        self.catalog = SongCatalog(self.manifest, self.root)
        self.clock = Clock()
        self.service = SingingService(
            self.catalog, clock=self.clock.now, wall_clock=self.clock.wall
        )
        self.proxy = ProxyHandler(word_game=WordGameService(), singing=self.service)
        self.proxy.connected = True
        self.proxy.broadcast_to_clients = AsyncMock()
        self.proxy.clients["desktop"] = Mock(send_json=AsyncMock())

    def write(self, rows):
        self.manifest.write_text(
            json.dumps({"songs": rows}, ensure_ascii=False), encoding="utf-8"
        )


class CatalogTests(SongFixture, unittest.TestCase):
    def test_exact_accent_insensitive_aliases_and_audio_metadata(self):
        for value in (
            "!sing BÀI THỬ",
            "!SING + bai thu",
            "!sing demo",
            "!sing bai-thu",
        ):
            kind, query = parse_song_command(value)
            self.assertEqual(kind, "sing")
            self.assertEqual(self.catalog.find(query)["id"], "bai-thu")
        self.assertEqual(parse_song_command("!songs"), ("list", ""))
        self.assertEqual(parse_song_command("!sing"), ("list", ""))
        self.assertIsNone(parse_song_command("mình muốn !sing demo"))
        self.assertIsNone(parse_song_command("!singular demo"))
        self.assertEqual(self.catalog.public()[0]["duration"], 1)
        self.assertNotIn("path", self.catalog.public()[0])

    def test_missing_file_is_unavailable_and_path_escape_or_ambiguity_fails_closed(
        self,
    ):
        self.write([{**self.row, "file": "missing.mp3"}])
        self.assertFalse(SongCatalog(self.manifest, self.root).public()[0]["available"])
        for extra in (
            {"file": "../outside.wav"},
            {"file": "https://example.com/song.wav"},
            {"bpm": float("nan")},
        ):
            self.write([{**self.row, **extra}])
            self.assertEqual(SongCatalog(self.manifest, self.root).public(), [])
        self.write([self.row, {**self.row, "id": "another", "title": "Bai thu"}])
        self.assertEqual(SongCatalog(self.manifest, self.root).public(), [])


class SingingTests(SongFixture, unittest.IsolatedAsyncioTestCase):
    async def start(self):
        result = await self.service.submit("!sing bài thử", "Lan", event_id="cmd")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.service.phase, "waiting")
        await self.service.tick()
        self.assertEqual(self.service.phase, "loading")
        self.event = {"run_id": self.service.run_id, "client_id": "screen-1"}

    async def test_waits_for_speech_then_reserves_queue_and_only_one_desktop_can_play(
        self,
    ):
        self.proxy.message_queue.conversation_active = True
        await self.service.submit("!sing demo")
        await self.service.tick()
        self.assertEqual(self.service.phase, "waiting")
        self.proxy.message_queue.conversation_active = False
        await self.service.tick()
        self.assertTrue(self.proxy.message_queue.external_busy)
        first = {"run_id": self.service.run_id, "client_id": "a"}
        self.assertTrue(
            (await self.service.playback({**first, "event": "claim"}))["accepted"]
        )
        self.assertFalse(
            (
                await self.service.playback(
                    {**first, "client_id": "b", "event": "claim"}
                )
            )["accepted"]
        )
        self.assertFalse(
            (
                await self.service.playback(
                    {**first, "client_id": "b", "event": "ended"}
                )
            )["accepted"]
        )
        await self.service.playback({**first, "event": "playing"})
        self.assertEqual(self.service.phase, "playing")
        await self.service.playback({**first, "event": "ended"})
        self.assertEqual(self.service.phase, "finished")
        self.assertFalse(self.proxy.message_queue.external_busy)

    async def test_spam_dedup_global_cooldown_and_old_reconnect_commands(self):
        await self.start()
        run = self.service.run_id
        self.assertEqual(
            (await self.service.submit("!sing demo", event_id="cmd"))["status"],
            "duplicate",
        )
        for i in range(30):
            self.assertEqual(
                (
                    await self.service.submit(
                        "!sing demo", f"Viewer {i}", event_id=str(i)
                    )
                )["status"],
                "busy",
            )
        self.assertEqual(run, self.service.run_id)
        await self.service.playback({**self.event, "event": "claim"})
        # Time spent preparing/playing must not consume the post-song break.
        self.clock.value = 100
        await self.service.playback({**self.event, "event": "ended"})
        deadline = self.service.cooldown_deadline
        self.assertEqual(deadline, 160)
        self.assertEqual(self.service.snapshot()["cooldown_remaining"], 60)
        self.clock.value = 159.999
        self.assertEqual(
            (await self.service.submit("!sing demo"))["status"], "cooldown"
        )
        self.assertEqual(self.service.cooldown_deadline, deadline)
        self.clock.value = 160
        self.assertEqual(
            (await self.service.submit("!sing demo", created_at=1150))["status"],
            "stale",
        )
        self.assertEqual(
            (await self.service.submit("!sing demo", created_at=1160))["status"],
            "accepted",
        )

    async def test_errors_disconnects_and_load_timeouts_release_the_speech_queue(self):
        for event in ("error", "closed", "timeout", "disconnect"):
            with self.subTest(event=event):
                self.clock.value = 0
                self.service.cooldown_deadline = 0
                self.service.finished_at = 0
                self.service.seen.clear()
                await self.start()
                await self.service.playback({**self.event, "event": "claim"})
                if event in ("error", "closed"):
                    await self.service.playback({**self.event, "event": event})
                else:
                    self.clock.value = 21 if event == "timeout" else 13
                    await self.service.tick()
                self.assertEqual(self.service.phase, "finished")
                self.assertFalse(self.proxy.message_queue.external_busy)

    async def test_unknown_song_and_live_stop_do_not_change_state_or_queue_llm(self):
        result = await self.service.submit("!sing https://example.com/file.mp3")
        self.assertEqual(result["status"], "not-found")
        await self.start()
        self.assertEqual(
            (await self.service.submit("!stopsing"))["status"], "operator-only"
        )
        self.assertTrue(self.service.active)
        self.assertEqual(
            (await self.service.submit("!stopsing", operator=True))["status"], "stopped"
        )
        self.assertFalse(self.proxy.message_queue.has_pending_messages())

    async def test_game_and_song_commands_cannot_interrupt_each_other(self):
        await self.start()
        await self.proxy.handle_sing_message(
            {"type": "game-comment", "text": "!vuatiengviet", "event_id": "game"},
            "desktop",
        )
        self.assertFalse(self.proxy.word_game.game.active)
        self.service.finish("ended")
        self.clock.value = 60
        await self.proxy.word_game.submit("Lan", "!vuatiengviet", player_id="a")
        self.assertEqual(
            (await self.service.submit("!sing demo"))["status"], "game-busy"
        )

    async def test_song_command_consumed_without_llm_and_reader_acknowledged(self):
        result = await self.proxy.handle_sing_message(
            {
                "type": "game-comment",
                "text": "!sing demo",
                "event_id": "song",
                "source": "youtube:test",
            },
            "desktop",
        )
        self.assertTrue(result)
        events = [
            call.args[0]
            for call in self.proxy.clients["desktop"].send_json.call_args_list
        ]
        self.assertEqual(events[0]["status"], "accepted")
        self.assertEqual(events[1]["type"], "game-comment-ack")
        self.assertEqual(len(self.proxy.comment_feed.snapshot()["comments"]), 1)
        self.assertFalse(self.proxy.message_queue.has_pending_messages())

    async def test_live_reader_routes_song_commands_while_busy_and_pauses_spoken_digest(
        self,
    ):
        class Reader(BufferedLiveChat):
            async def run(self):
                pass

        reader = Reader(
            "youtube:test",
            comment_state_path=self.root / "comments.db",
            activity=ChatActivity(self.root / "activity.json"),
        )
        reader._connected = reader._state_known = reader._conversation_active = True
        reader._websocket = Mock(closed=False, send=AsyncMock())
        reader._accept_comment("Lan", "!sing demo", event_key="song")
        await reader._dispatch_once()
        message = json.loads(reader._websocket.send.call_args.args[0])
        self.assertEqual(message["type"], "game-comment")
        self.assertEqual(message["text"], "!sing demo")
        await reader.handle_incoming_messages(
            self.service.snapshot() | {"phase": "playing"}
        )
        await reader.handle_incoming_messages(
            {"type": "game-comment-ack", "event_id": "song"}
        )
        reader._conversation_active = False
        reader._accept_comment("Mai", "Mao hát hay quá", event_key="normal")
        await reader._dispatch_once()
        messages = [
            json.loads(call.args[0]) for call in reader._websocket.send.call_args_list
        ]
        self.assertFalse(any(row["type"] == "text-input" for row in messages))
        host = IdleHost(
            "ws://test",
            settings_path=self.root / "host.json",
            activity_path=self.root / "activity.json",
        )
        host.receive({"type": "mao-sing-state", "phase": "playing"})
        self.assertFalse(await host.dispatch_once(Mock()))

    async def test_queue_does_not_forward_during_song_and_resumes_afterward(self):
        queue = self.proxy.message_queue
        forward = AsyncMock()
        queue.initialize(forward)
        queue.external_busy = True
        queue.queue_message({"type": "text-input", "text": "Chào Mao"})
        try:
            await asyncio.sleep(0.15)
            forward.assert_not_awaited()
            queue.external_busy = False
            await asyncio.sleep(0.15)
            self.assertEqual(forward.await_count, 2)
        finally:
            queue.stop()


class SongApiTests(SongFixture, unittest.TestCase):
    def test_catalog_audio_and_state_endpoints_expose_only_catalogued_files(self):
        app = FastAPI()
        app.include_router(init_proxy_route("ws://test", singing=self.service))
        with TestClient(app) as client:
            result = client.get("/api/sing/songs").json()
            self.assertTrue(result["songs"][0]["available"])
            self.assertNotIn("path", result["songs"][0])
            self.assertEqual(client.get("/api/sing/audio/bai-thu").content[:4], b"RIFF")
            self.assertEqual(client.get("/api/sing/audio/unknown").status_code, 404)
            self.assertEqual(client.get("/api/sing/state").json()["phase"], "idle")
            self.assertFalse(
                client.post("/api/sing/playback", json={"event": "ended"}).json()[
                    "accepted"
                ]
            )

    def test_full_game_clock_waits_for_the_matching_scene_presentation(self):
        game = WordGameService(require_presentation=True)
        game.game.submit("Lan", "!vuatiengviet", player_id="a")
        self.assertFalse(game.presentation_ready)
        app = FastAPI()
        app.include_router(init_proxy_route("ws://test", word_game=game))
        with TestClient(app) as client:
            self.assertFalse(
                client.post(
                    "/api/vuatiengviet/presentation", json={"round_id": "stale"}
                ).json()["accepted"]
            )
            self.assertFalse(game.presentation_ready)
            self.assertTrue(
                client.post(
                    "/api/vuatiengviet/presentation",
                    json={"round_id": game.game.round_id},
                ).json()["accepted"]
            )
            self.assertTrue(game.presentation_ready)
            game.game.tick(ready=game.presentation_ready)
            self.assertAlmostEqual(game.game.snapshot()["remaining"], 60, delta=0.1)
