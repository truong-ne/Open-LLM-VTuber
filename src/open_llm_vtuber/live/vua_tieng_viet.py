"""Deterministic 60-second Vietnamese word rounds; no LLM decides the scores."""

import asyncio
from collections import deque
from difflib import SequenceMatcher
import json
from pathlib import Path
import random
import re
import time
import unicodedata
import uuid

from loguru import logger

WORD_PATH = Path(__file__).resolve().parents[3] / "knowledge/vua_tieng_viet.vi.json"
COMMAND = re.compile(r"^!vuatiengviet\s*$", re.IGNORECASE)
RESULT_REACTIONS = {
    "correct": (
        "Hay quá! Chúc mừng {nickname}, đoán đúng sớm nhất với một trăm điểm!",
        "Giỏi quá nè! {nickname} đoán đúng đầu tiên, nhận trọn một trăm điểm!",
        "Chúc mừng {nickname}! Bạn đoán đúng sớm nhất, được một trăm điểm!",
        "Bắt được từ khóa rồi! Chúc mừng {nickname}, đúng nhanh nhất với một trăm điểm!",
    ),
    "missed": (
        "Tiếc quá, vòng này chưa ai đoán đúng!",
        "Ui, tiếc ghê! Cả nhà chưa tìm ra từ này rồi!",
        "Thiếp tiếc ghê! Vòng này chưa có đáp án đúng.",
        "Tiếc quá nè, từ này trốn cả nhà thành công rồi!",
    ),
    "empty": (
        "Tiếc quá, chưa có bạn nào gửi đáp án!",
        "Ui, tiếc ghê! Vòng này cả nhà chưa kịp gửi câu trả lời rồi!",
        "Tiếc quá, chưa có lượt đoán nào!",
        "Tiếc ghê, từ này còn chưa được ai đoán thử!",
    ),
}


def normalize_answer(text):
    text = unicodedata.normalize("NFD", str(text).casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def answer_score(guess, answer):
    guess, answer = normalize_answer(guess), normalize_answer(answer)
    if not guess:
        return 0
    if guess == answer:
        return 100
    return min(
        99, round(SequenceMatcher(None, guess, answer, autojunk=False).ratio() * 100)
    )


class VuaTiengViet:
    duration = 60
    cooldown_seconds = 60

    def __init__(
        self, words=None, *, clock=time.monotonic, wall_clock=time.time, rng=None
    ):
        self.words = (
            words
            if words is not None
            else json.loads(WORD_PATH.read_text(encoding="utf-8"))
        )
        if not self.words or any(
            not isinstance(w.get("answer"), str)
            or not 2 <= len(w["answer"]) <= 32
            or not isinstance(w.get("category"), str)
            or not isinstance(w.get("hints"), list)
            or len(w["hints"]) != 3
            or any(not isinstance(h, str) or not h or len(h) > 200 for h in w["hints"])
            or not isinstance(w.get("explanation"), str)
            or not w["explanation"].strip()
            or len(w["explanation"]) > 300
            for w in self.words
        ):
            raise ValueError("Invalid Vua tieng Viet word bank")
        self.clock, self.wall_clock, self.rng = (
            clock,
            wall_clock,
            rng or random.Random(),
        )
        self.phase, self.round_id = "idle", ""
        self.word = None
        self.players = {}
        self.seen = set()
        self.recent = deque(maxlen=max(1, len(self.words) - 1))
        self.hint_index = 0
        self.started = self.deadline = self.started_at = self.ends_at = (
            self.finished
        ) = 0
        self.revision = 0
        self.starter = ""
        self.letters = []
        self.announcements = deque()
        self.feedback_windows = set()
        self.feedback_read = set()
        self._last_result_lines = {}
        self.cooldown_deadline = self.finished_at = 0

    @property
    def active(self):
        return self.phase in ("waiting", "playing")

    @property
    def cooldown_remaining(self):
        return (
            max(0, self.cooldown_deadline - self.clock())
            if self.phase == "finished"
            else 0
        )

    def submit(self, nickname, text, *, player_id, event_id="", created_at=0):
        self.tick(ready=False)
        text = str(text).strip()[:300]
        nickname = str(nickname or "bạn").strip()[:40]
        player_id = str(player_id)[:160]
        if event_id and event_id in self.seen:
            return "duplicate"
        if COMMAND.fullmatch(text):
            if self.active:
                return "already-playing"
            if self.cooldown_remaining:
                return "cooldown"
            # Do not turn commands queued during the break into a new round
            # when a reader reconnects or finishes draining a burst of spam.
            if (
                created_at
                and self.finished_at
                and created_at < self.finished_at + self.cooldown_seconds
            ):
                return "stale"
            self._prepare(nickname)
            if event_id:
                self.seen.add(event_id)
            return "started"
        if self.phase != "playing":
            return "not-playing"
        if created_at and created_at < self.started_at:
            return "stale"
        if event_id:
            if len(self.seen) >= 10000:
                return "round-full"
            self.seen.add(event_id)
        guess = re.sub(r"^!doan\s+", "", text, flags=re.IGNORECASE)
        if not normalize_answer(guess):
            return "empty"
        player = self.players.get(player_id)
        now = self.clock()
        if player is not None and (
            player["attempts"] >= 12 or now - player["last_at"] < 1
        ):
            return "rate-limited"
        if player is None:
            if len(self.players) >= 1000:
                return "round-full"
            player = self.players[player_id] = {
                "nickname": nickname,
                "score": -1,
                "attempts": 0,
                "best_at": now,
                "last_at": float("-inf"),
                "guess": "",
                "order": len(self.players),
            }
        player["attempts"] += 1
        player["last_at"] = now
        player["last_guess"] = guess
        score = answer_score(guess, self.word["answer"])
        if score > player["score"]:
            player.update(score=score, best_at=now, guess=guess)
        self.revision += 1
        return "accepted"

    def _prepare(self, nickname):
        candidates = [i for i in range(len(self.words)) if i not in self.recent]
        chosen = self.rng.choice(candidates or list(range(len(self.words))))
        self.recent.append(chosen)
        self.word = self.words[chosen]
        self.phase, self.round_id, self.starter = "waiting", uuid.uuid4().hex, nickname
        self.players, self.seen, self.announcements = {}, set(), deque()
        self.hint_index = 0
        self.feedback_windows = set()
        self.feedback_read = set()
        self.letters = [
            c
            for c in unicodedata.normalize("NFC", self.word["answer"].upper())
            if c != " "
        ]
        self.rng.shuffle(self.letters)
        ordered = [
            c
            for c in unicodedata.normalize("NFC", self.word["answer"].upper())
            if c != " "
        ]
        if self.letters == ordered:
            self.letters = self.letters[1:] + self.letters[:1]
        self.revision += 1

    def tick(self, *, ready=True):
        if self.phase == "waiting" and ready:
            self.started, self.started_at = self.clock(), self.wall_clock()
            self.deadline, self.ends_at = (
                self.started + self.duration,
                self.started_at + self.duration,
            )
            self.phase = "playing"
            self._announce(
                "start",
                self.start_speech(),
            )
            self.revision += 1
        if self.phase != "playing":
            return
        now = self.clock()
        if now >= self.deadline:
            self.phase, self.finished = "finished", now
            self.finished_at = self.wall_clock()
            self.cooldown_deadline = now + self.cooldown_seconds
            self._announce("result", self._result_speech())
            self.revision += 1
            return
        index = min(2, int((now - self.started) // 20))
        if index > self.hint_index:
            self.hint_index = index
            self._announce(
                f"hint-{index}",
                f"Gợi ý {index + 1}: {self.word['hints'][index]}",
            )
            self.revision += 1
        if (
            (now - self.started) % 20 >= 10
            and index not in self.feedback_windows
            and self.players
        ):
            unread = [
                (ident, player)
                for ident, player in self.players.items()
                if (ident, player["last_at"]) not in self.feedback_read
            ]
            if not unread:
                return
            self.feedback_windows.add(index)
            ident, recent = min(unread, key=lambda item: item[1]["last_at"])
            self.feedback_read.add((ident, recent["last_at"]))
            name = re.sub(r"[\[\]<>\n]", " ", recent["nickname"])
            guess = re.sub(r"[\[\]<>\n]", " ", recent["last_guess"])[:60]
            self._announce(
                f"feedback-{index}",
                f"{name} đoán là {guess}. Cả nhà đoán tiếp nhé!",
            )

    def start_speech(self):
        return f"Gợi ý 1: {self.word['hints'][0]}"

    def _result_line(self, kind, choices):
        previous = self._last_result_lines.get(kind)
        line = self.rng.choice([line for line in choices if line != previous])
        self._last_result_lines[kind] = line
        return line

    def _result_speech(self):
        ranking = self.ranking()
        outcome = (
            "correct"
            if ranking and ranking[0]["score"] == 100
            else "missed"
            if ranking
            else "empty"
        )
        reaction = self._result_line(outcome, RESULT_REACTIONS[outcome])
        if ranking:
            # A viewer name is spoken as plain text, never as an expression tag.
            name = re.sub(r"[\[\]<>\r\n]", " ", ranking[0]["nickname"])
            reaction = reaction.format(nickname=name)
        sentences = [
            "Hết giờ!",
            f"Đáp án là {self.word['answer']}.",
            reaction,
            re.split(r"(?<=[.!?…])\s+", self.word["explanation"].strip())[0],
        ]
        if outcome == "missed":
            sentences.append(
                f"Chưa ai đúng hoàn toàn; {name} gần nhất với {ranking[0]['score']} điểm."
            )
        return " ".join(sentences)

    def _announce(self, kind, text):
        self.announcements.append(
            {"round_id": self.round_id, "kind": kind, "text": text}
        )

    def announcement_valid(self, round_id, kind):
        if round_id != self.round_id:
            return False
        if kind == "result":
            return self.phase == "finished" and self.clock() - self.finished < 30
        if isinstance(kind, str) and kind.startswith("feedback-"):
            return self.phase == "playing" and kind == f"feedback-{self.hint_index}"
        return self.phase == "playing" and kind == (
            "start" if self.hint_index == 0 else f"hint-{self.hint_index}"
        )

    def ranking(self):
        return sorted(
            self.players.values(), key=lambda p: (-p["score"], p["best_at"], p["order"])
        )

    def snapshot(self):
        remaining = (
            max(0, self.deadline - self.clock()) if self.phase == "playing" else 0
        )
        result = {
            "type": "vua-tieng-viet-state",
            "phase": self.phase,
            "round_id": self.round_id,
            "revision": self.revision,
            "server_now": self.wall_clock(),
            "duration": self.duration,
            "ends_at": self.wall_clock() + remaining,
            "remaining": remaining,
            "cooldown_seconds": self.cooldown_seconds,
            "cooldown_remaining": self.cooldown_remaining,
            "cooldown_ends_at": self.wall_clock() + self.cooldown_remaining
            if self.cooldown_remaining
            else 0,
            "starter": self.starter,
            "participants": len(self.players),
            "category": self.word["category"] if self.word else "",
            "slots": [
                len(w)
                for w in unicodedata.normalize("NFC", self.word["answer"]).split()
            ]
            if self.word
            else [],
            "letters": self.letters,
            "hint_index": self.hint_index,
            "hints": self.word["hints"][: self.hint_index + 1]
            if self.word and self.phase != "waiting"
            else [],
            "leaderboard": [],
        }
        if self.phase == "finished":
            result["answer"] = self.word["answer"]
            result["show_until"] = self.wall_clock() + max(
                0, 15 - (self.clock() - self.finished)
            )
            result["leaderboard"] = [
                {
                    "nickname": p["nickname"],
                    "score": p["score"],
                    "seconds": round(p["best_at"] - self.started, 2),
                    "guess": p["guess"],
                }
                for p in self.ranking()[:5]
            ]
        return result


class WordGameService:
    def __init__(self, game=None, *, require_presentation=False):
        self.game = game or VuaTiengViet()
        self.proxy = None
        self.task = None
        self._last_revision = -1
        self.require_presentation = require_presentation
        self.presented_round = ""
        self.speech_cache = None
        self.prefetch_task = None
        self.prefetch_round = ""
        self.prepared = set()

    def configure_speech(self, engine):
        from .game_speech import PreparedGameSpeech

        if engine is not None:
            self.speech_cache = PreparedGameSpeech(engine)
            engine._mao_word_game_speech = self.speech_cache

    def prepare_speech_if_idle(self):
        if not self.speech_cache or not self.proxy or not self.game.active:
            return
        queue = self.proxy.message_queue
        if self.prefetch_task and not self.prefetch_task.done():
            return
        if (
            queue.conversation_active
            or queue.has_pending_messages()
            or queue.external_busy
        ):
            return
        if self.prefetch_round != self.game.round_id:
            self.prefetch_round = self.game.round_id
            self.prepared.clear()
        if self.game.phase == "waiting":
            kind, script = "start", self.game.start_speech() + " Hết giờ!"
        else:
            # Leave an eight-second margin before a timed hint/result. Jobs
            # run only between spoken turns, never competing with live TTS.
            elapsed = self.game.clock() - self.game.started
            if elapsed >= self.game.duration:
                return
            next_event = min(moment for moment in (20, 40, 60) if moment > elapsed)
            if next_event - elapsed < 8:
                return
            index = next(
                (
                    i
                    for i in (1, 2)
                    if i > self.game.hint_index and f"hint-{i}" not in self.prepared
                ),
                None,
            )
            if index is None:
                return
            kind, script = (
                f"hint-{index}",
                f"Gợi ý {index + 1}: {self.game.word['hints'][index]}",
            )
        if kind in self.prepared:
            return
        queue.external_busy = True

        async def prepare():
            try:
                await self.speech_cache.prepare(script)
            except Exception:
                logger.exception("Game speech preparation failed; using normal TTS")
            finally:
                self.prepared.add(kind)
                queue.external_busy = False

        self.prefetch_task = asyncio.create_task(prepare())

    def mark_presented(self, round_id):
        if self.game.phase == "waiting" and round_id == self.game.round_id:
            self.presented_round = round_id
            return True
        return False

    @property
    def presentation_ready(self):
        return (
            not self.require_presentation or self.presented_round == self.game.round_id
        )

    async def start(self):
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.prefetch_task:
            await asyncio.gather(self.prefetch_task, return_exceptions=True)

    async def submit(self, nickname, text, *, player_id, event_id="", created_at=0):
        # All state transitions happen on the backend event loop.
        status = self.game.submit(
            nickname,
            text,
            player_id=player_id,
            event_id=event_id,
            created_at=created_at,
        )
        if (
            status == "started"
            and self.proxy
            and getattr(self.proxy, "_active_input_source", None) == "mao-idle-host"
        ):
            # The operator/viewer chose a game: finish automatic chatter now,
            # then let the first clue wait for the actual conversation end signal.
            await self.proxy.forward_to_server({"type": "interrupt-signal"})
        await self.publish()
        return status

    async def publish(self):
        if self.proxy and self._last_revision != self.game.revision:
            self._last_revision = self.game.revision
            await self.proxy.broadcast_to_clients(self.game.snapshot())

    async def _run(self):
        while True:
            try:
                if self.game.phase == "waiting":
                    self.prepare_speech_if_idle()
                ready = bool(
                    self.proxy
                    and self.proxy.clients
                    and self.proxy.connected
                    and not self.proxy.message_queue.conversation_active
                    and not self.proxy.message_queue.has_pending_messages()
                    and not self.proxy.message_queue.external_busy
                    and self.presentation_ready
                )
                self.game.tick(ready=ready)
                await self.publish()
                if self.proxy:
                    while self.game.announcements:
                        announcement = self.game.announcements.popleft()
                        self.proxy.message_queue.queue_message(
                            {
                                "type": "text-input",
                                "text": announcement["text"],
                                "source": "vua-tieng-viet",
                                "game_speech": announcement["text"],
                                "game_round_id": announcement["round_id"],
                                "game_kind": announcement["kind"],
                            },
                            priority=True,
                        )
                    # Publish and queue due speech BEFORE reserving TTS for a
                    # future clue. Otherwise a new job at exactly second 20
                    # can block the already prepared second clue.
                    if self.game.phase == "playing":
                        self.prepare_speech_if_idle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Vua tieng Viet tick failed")
            await asyncio.sleep(0.2)
