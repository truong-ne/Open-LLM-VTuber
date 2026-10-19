"""Local, prepared song performances. Chat never supplies a file path or URL."""

import asyncio
from collections import OrderedDict
import json
import math
from pathlib import Path
import re
import time
import uuid

from loguru import logger
import soundfile as sf

from .vua_tieng_viet import normalize_answer

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "knowledge/mao_songs.vi.json"
SONG_ROOT = ROOT / "assets/mao_songs"
SING_COMMAND = re.compile(r"^!(sing|songs|baihat|stopsing)(?:\s+(.*))?$", re.I)
ACTIVE_PHASES = ("waiting", "loading", "playing")


def parse_song_command(text):
    match = SING_COMMAND.fullmatch(str(text).strip())
    if not match:
        return None
    command, query = match.group(1).lower(), (match.group(2) or "").strip()
    if command == "stopsing":
        return "stop", ""
    if command in ("songs", "baihat") or not query:
        return "list", ""
    return "sing", normalize_answer(query.lstrip("+").strip())


class SongCatalog:
    def __init__(self, path=CATALOG_PATH, root=SONG_ROOT):
        self.path, self.root = Path(path), Path(root).resolve()
        self.songs, self.names = {}, {}
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))["songs"]
            if not isinstance(rows, list) or len(rows) > 200:
                raise ValueError("Expected at most 200 songs")
            for row in rows:
                self._add(row)
        except (OSError, ValueError, KeyError, TypeError):
            logger.exception("Could not load the prepared Mao song catalog")
            self.songs, self.names = {}, {}

    def _add(self, row):
        ident, title = row["id"], row["title"]
        aliases = row.get("aliases", [])
        bpm = row.get("bpm", 120)
        if (
            not isinstance(ident, str)
            or not re.fullmatch(r"[a-z0-9-]{1,64}", ident)
            or ident in self.songs
            or not isinstance(title, str)
            or not title.strip()
            or len(title) > 100
            or not isinstance(aliases, list)
            or len(aliases) > 20
            or any(
                not isinstance(a, str) or not a.strip() or len(a) > 100 for a in aliases
            )
            or isinstance(bpm, bool)
            or not isinstance(bpm, (int, float))
            or not 40 <= bpm <= 220
        ):
            raise ValueError("Invalid song metadata")
        names = {normalize_answer(value) for value in [ident, title, *aliases]}
        if "" in names or any(name in self.names for name in names):
            raise ValueError("Ambiguous song name")
        file = row.get("file", "")
        if not isinstance(file, str) or ":" in file or Path(file).is_absolute():
            raise ValueError("Song file must be a local relative path")
        path = (self.root / file).resolve() if isinstance(file, str) else self.root
        if not path.is_relative_to(self.root) or path.suffix.lower() not in (
            ".wav",
            ".mp3",
            ".ogg",
            ".flac",
        ):
            raise ValueError("Song files must stay inside the local song directory")
        duration = 0
        try:
            duration = sf.info(str(path)).duration
        except (RuntimeError, OSError):
            pass
        available = math.isfinite(duration) and 0 < duration <= 900
        self.songs[ident] = {
            "id": ident,
            "title": title.strip(),
            "aliases": aliases,
            "bpm": bpm,
            "duration": duration if available else 0,
            "available": available,
            "path": path,
        }
        self.names.update({name: ident for name in names})

    def find(self, query):
        return self.songs.get(self.names.get(query))

    def public(self):
        return [self.public_song(song) for song in self.songs.values()]

    @staticmethod
    def public_song(song):
        return {key: value for key, value in song.items() if key != "path"}


class SingingService:
    cooldown_seconds = 60

    def __init__(self, catalog=None, *, clock=time.monotonic, wall_clock=time.time):
        self.catalog = catalog if catalog is not None else SongCatalog()
        self.clock, self.wall_clock = clock, wall_clock
        self.proxy = self.task = None
        self.phase, self.run_id, self.owner, self.reason = "idle", "", "", ""
        self.song, self.requester = None, ""
        self.deadline = self.cooldown_deadline = self.last_heartbeat = 0
        self.finished_at = self.position = 0
        self.seen = OrderedDict()
        self.revision = 0
        self._published = -1

    @property
    def active(self):
        return self.phase in ACTIVE_PHASES

    def snapshot(self):
        remaining = max(0, self.cooldown_deadline - self.clock())
        return {
            "type": "mao-sing-state",
            "phase": self.phase,
            "run_id": self.run_id,
            "revision": self.revision,
            "song": self.catalog.public_song(self.song) if self.song else None,
            "requester": self.requester,
            "position": self.position,
            "reason": self.reason,
            "server_now": self.wall_clock(),
            "cooldown_remaining": remaining,
            "cooldown_ends_at": self.wall_clock() + remaining if remaining else 0,
        }

    async def submit(
        self, text, nickname="bạn", *, event_id="", created_at=0, operator=False
    ):
        command = parse_song_command(text)
        if command is None:
            return None
        if event_id:
            if event_id in self.seen:
                return self.reply("duplicate", "Lệnh này đã được xử lý.")
            self.seen[event_id] = True
            if len(self.seen) > 2000:
                self.seen.popitem(last=False)
        kind, query = command
        if kind == "list":
            return self.reply(
                "songs",
                "Dùng !sing tên bài để mời Mao hát.",
                songs=self.catalog.public(),
            )
        if kind == "stop":
            if not operator:
                return self.reply(
                    "operator-only", "Chủ phòng mới có thể dừng tiết mục."
                )
            if self.active:
                self.finish("stopped")
                await self.publish()
            return self.reply("stopped", "Đã dừng tiết mục.")
        if self.active:
            return self.reply("busy", "Mao đang có tiết mục, chờ hát xong nhé!")
        if self.clock() < self.cooldown_deadline:
            return self.reply("cooldown", "Mao đang nghỉ giữa hai bài.")
        if (
            created_at
            and self.finished_at
            and created_at < self.finished_at + self.cooldown_seconds
        ):
            return self.reply("stale", "Lệnh cũ trong thời gian nghỉ đã được bỏ qua.")
        game = (
            self.proxy.word_game.game if self.proxy and self.proxy.word_game else None
        )
        if game and (
            game.active or game.snapshot().get("show_until", 0) > self.wall_clock()
        ):
            return self.reply(
                "game-busy", "Đợi hết vòng Vua Tiếng Việt rồi mời Mao hát nhé!"
            )
        song = self.catalog.find(query)
        if not song:
            return self.reply(
                "not-found", "Mao chưa có bài này. Gõ !songs để xem danh sách."
            )
        if not song["available"] or not song["path"].is_file():
            return self.reply("unavailable", "Bài này chưa có file hát sẵn.")
        self.phase, self.run_id = "waiting", uuid.uuid4().hex
        self.song, self.requester = song, str(nickname or "bạn")[:40]
        self.owner = self.reason = ""
        self.position = 0
        self.deadline = self.clock() + 120
        self.revision += 1
        await self.publish()
        return self.reply(
            "accepted", f"Đã nhận bài {song['title']}; chờ Mao nói xong nhé!"
        )

    def reply(self, status, message, **extra):
        return {
            "type": "mao-sing-command-result",
            "status": status,
            "message": message,
            "state": self.snapshot(),
            **extra,
        }

    def finish(self, reason):
        self.phase, self.reason = "finished", reason
        self.finished_at = self.wall_clock()
        self.cooldown_deadline = self.clock() + self.cooldown_seconds
        self.revision += 1
        if self.proxy:
            self.proxy.message_queue.external_busy = False

    async def playback(self, event):
        owner, run = event.get("client_id"), event.get("run_id")
        kind = event.get("event")
        if (
            not isinstance(owner, str)
            or not 1 <= len(owner) <= 80
            or run != self.run_id
        ):
            return {"accepted": False}
        if kind == "claim":
            if self.phase != "loading" or (self.owner and self.owner != owner):
                return {"accepted": False}
            self.owner = owner
            self.last_heartbeat = self.clock()
            return {"accepted": True}
        if (
            not self.owner
            or owner != self.owner
            or self.phase not in ("loading", "playing")
        ):
            return {"accepted": False}
        self.last_heartbeat = self.clock()
        if kind == "playing" and self.phase == "loading":
            self.phase = "playing"
            self.deadline = self.clock() + self.song["duration"] + 15
            self.revision += 1
        elif kind in ("ended", "error", "closed"):
            self.finish(
                {"ended": "ended", "error": "audio-error", "closed": "player-closed"}[
                    kind
                ]
            )
        elif kind == "heartbeat":
            position = event.get("position", 0)
            if (
                isinstance(position, (int, float))
                and not isinstance(position, bool)
                and math.isfinite(position)
            ):
                self.position = max(0, min(self.song["duration"], position))
        else:
            return {"accepted": False}
        await self.publish()
        return {"accepted": True}

    async def tick(self):
        if not self.active:
            return
        now = self.clock()
        if now >= self.deadline:
            self.finish("timeout")
        elif self.owner and now - self.last_heartbeat > 12:
            self.finish("player-disconnected")
        elif self.phase == "waiting" and self.proxy:
            queue = self.proxy.message_queue
            if (
                self.proxy.connected
                and not queue.conversation_active
                and not queue.has_pending_messages()
            ):
                # Reserve the speech queue before the desktop starts the audio.
                queue.external_busy = True
                self.phase, self.deadline = "loading", now + 20
                self.revision += 1
        await self.publish()

    async def publish(self):
        if self.proxy and self._published != self.revision:
            self._published = self.revision
            await self.proxy.broadcast_to_clients(self.snapshot())

    async def start(self):
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.proxy:
            self.proxy.message_queue.external_busy = False

    async def _run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Mao singing tick failed")
            await asyncio.sleep(0.2)
