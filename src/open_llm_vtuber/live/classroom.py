"""Optional long-running classroom. Ordinary word rounds remain unchanged when off."""

import json
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import uuid

from .vua_tieng_viet import VuaTiengViet, WORD_PATH, normalize_answer

ROOT = WORD_PATH.parents[1]
BANK = ROOT / "knowledge/classroom.vi.json"
SEAT_COUNT = 40
HONOR_BONUSES = (10, 6, 3)


class ClassroomGame(VuaTiengViet):
    def __init__(self, words=None, *, database=None, **kwargs):
        default_bank = words is None
        if default_bank:
            words = json.loads(WORD_PATH.read_text(encoding="utf-8"))
            words += json.loads(BANK.read_text(encoding="utf-8"))
            words += json.loads(
                (BANK.parent / "classroom.hard.vi.json").read_text(encoding="utf-8")
            )
            words += json.loads(
                (BANK.parent / "classroom.expanded.vi.json").read_text(encoding="utf-8")
            )
        super().__init__(words, **kwargs)
        self.word_keys = [normalize_answer(word["answer"]) for word in self.words]
        self.excluded_answers = set()
        if default_bank:
            policy = json.loads(
                (BANK.parent / "classroom-bank-policy.json").read_text(encoding="utf-8")
            )
            self.excluded_answers = {
                normalize_answer(answer) for answer in policy["excluded_answers"]
            }
        self.eligible_indices = [
            i
            for i, key in enumerate(self.word_keys)
            if key not in self.excluded_answers
        ]
        if not self.eligible_indices:
            raise ValueError("Classroom bank has no playable questions")
        self.used_answers = set()
        self.recent_answers = []
        self.recent_categories = []
        self.database = Path(database or ROOT / "private/mao-classroom.sqlite3")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.enabled = False
        self.session_id = ""
        self.session_end = 0
        self.session_start = 0
        self.round_number = 0
        self.standings = {}
        self.used_words = set()
        self.round_comments = []
        self.comment_sequence = 0
        self._recorded_round_id = ""
        self._round_result = []
        self.account = "@thanhoathirty6"
        self.end_reason = ""
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS classroom_question_history(account TEXT PRIMARY KEY,payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS classroom (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)"
            )
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_honor (
                account TEXT NOT NULL, player_id TEXT NOT NULL, nickname TEXT NOT NULL,
                avatar_seed TEXT NOT NULL, points INTEGER NOT NULL DEFAULT 0,
                gold INTEGER NOT NULL DEFAULT 0, silver INTEGER NOT NULL DEFAULT 0,
                bronze INTEGER NOT NULL DEFAULT 0, first_award REAL NOT NULL,
                last_award REAL NOT NULL, PRIMARY KEY(account,player_id))""")
            db.execute("""CREATE INDEX IF NOT EXISTS classroom_honor_rank
                ON classroom_honor(account,points DESC,gold DESC,first_award)""")
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_round_awards (
                account TEXT NOT NULL, session_id TEXT NOT NULL, round_id TEXT NOT NULL,
                completed_at REAL NOT NULL, result_json TEXT NOT NULL,
                PRIMARY KEY(account,session_id,round_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_sessions (
                account TEXT NOT NULL, session_id TEXT NOT NULL, updated_at REAL NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(account,session_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_session_awards (
                account TEXT NOT NULL, session_id TEXT NOT NULL, awarded_at REAL NOT NULL,
                result_json TEXT NOT NULL, PRIMARY KEY(account,session_id))""")
            row = db.execute("SELECT payload FROM classroom WHERE id=1").fetchone()
        self._init_daily_honor()
        if row:
            saved = json.loads(row[0])
            self.session_id = saved["session_id"]
            self.session_start = saved["session_start"]
            self.session_end = 0
            self.round_number = saved["round_number"]
            self.standings = saved["standings"]
            migrated_avatars = False
            for player in self.standings.values():
                if not player.get("avatar_seed"):
                    player["avatar_seed"] = uuid.uuid4().hex
                    migrated_avatars = True
            self.used_words = set(saved.get("used_words", []))
            # Keep old index data, and migrate to stable answer identities.
            self.used_answers = set(saved.get("used_answers", []))
            if "used_answers" not in saved:
                self.used_answers.update(
                    self.word_keys[i]
                    for i in self.used_words
                    if isinstance(i, int) and 0 <= i < len(self.words)
                )
            self.recent_answers = saved.get("recent_answers", [])[-100:]
            self.recent_categories = saved.get("recent_categories", [])[-3:]
            self.account = saved.get("account", self.account)
            self.enabled = saved["enabled"]
            self.end_reason = saved.get("end_reason", "")
            if self.enabled:
                self._next_round()
            if migrated_avatars:
                self._save()

    @contextmanager
    def _db(self):
        connection = sqlite3.connect(self.database, timeout=3)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _save(self, connection=None):
        payload = {
            name: getattr(self, name)
            for name in (
                "session_id",
                "session_start",
                "session_end",
                "round_number",
                "standings",
                "enabled",
                "account",
                "end_reason",
            )
        }
        payload["used_words"] = sorted(self.used_words)
        payload["used_answers"] = sorted(self.used_answers)
        payload["recent_answers"] = self.recent_answers[-100:]
        payload["recent_categories"] = self.recent_categories[-3:]
        encoded = json.dumps(payload, ensure_ascii=False)

        def write(db):
            db.execute(
                "INSERT INTO classroom_question_history VALUES(?,?) ON CONFLICT(account) DO UPDATE SET payload=excluded.payload",
                (
                    self.account.casefold(),
                    json.dumps(
                        {
                            "used_answers": sorted(self.used_answers),
                            "recent_answers": self.recent_answers[-100:],
                            "recent_categories": self.recent_categories[-3:],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            db.execute(
                "INSERT OR REPLACE INTO classroom(id,payload) VALUES(1,?)", (encoded,)
            )
            if self.session_id:
                db.execute(
                    """INSERT INTO classroom_sessions(account,session_id,updated_at,payload)
                    VALUES(?,?,?,?) ON CONFLICT(account,session_id) DO UPDATE SET
                    updated_at=excluded.updated_at,payload=excluded.payload""",
                    (
                        self.account.casefold(),
                        self.session_id,
                        self.wall_clock(),
                        encoded,
                    ),
                )

        if connection is not None:
            write(connection)
        else:
            with self._db() as db:
                write(db)

    @property
    def active(self):
        return self.enabled or super().active

    def enable(self, account="@thanhoathirty6"):
        if self.enabled:
            return
        if not re.fullmatch(r"@[\w.]{1,24}", account, re.ASCII):
            raise ValueError("Tên TikTok không hợp lệ.")
        if self.session_id:
            self._save()
        if self.account.casefold() != account.casefold():
            with self._db() as db:
                row = db.execute(
                    "SELECT payload FROM classroom_question_history WHERE account=?",
                    (account.casefold(),),
                ).fetchone()
            history = json.loads(row[0]) if row else {}
            self.used_answers = set(history.get("used_answers", []))
            self.recent_answers = history.get("recent_answers", [])[-100:]
            self.recent_categories = history.get("recent_categories", [])[-3:]
            self.used_words = {
                i for i, key in enumerate(self.word_keys) if key in self.used_answers
            }
        self.enabled = True
        self.account = account
        self.session_id = uuid.uuid4().hex
        self.session_start = self.wall_clock()
        self.session_end = 0
        self.end_reason = ""
        self.round_number, self.standings = 0, {}
        self._next_round()
        self._save()

    def disable(self, reason="operator"):
        # Invalidate queued game speech; normal Mao resumes after any current turn.
        self.enabled = False
        self.phase, self.round_id = "idle", uuid.uuid4().hex
        self.announcements.clear()
        self.end_reason = reason
        self.cooldown_deadline = 0
        self.revision += 1
        self._save()

    @property
    def hint_count(self):
        return (
            2
            if self.enabled and self.word and self.word.get("difficulty") != "hard"
            else 3
        )

    def _prepare(self, nickname):
        super()._prepare(nickname)
        self.round_comments = []
        self._round_result = []
        self.duration = (
            (40 if self.word.get("difficulty") == "hard" else 25)
            if self.enabled
            else 60
        )

    def _next_round(self):
        self._prepare("Lớp học Mao")
        self.round_number += 1

    def _choose_word(self):
        if not self.enabled:
            return super()._choose_word()
        # Retired questions stay in the files/database but are never selected.
        available = [
            i
            for i in self.eligible_indices
            if self.word_keys[i] not in self.used_answers
        ]
        if not available:
            self.used_words.clear()
            self.used_answers.clear()
            available = list(self.eligible_indices)
        recent = set(self.recent_answers[-100:])
        fresh = [i for i in available if self.word_keys[i] not in recent]
        if fresh:
            available = fresh
        elif self.word and len(available) > 1:
            available = [
                i for i in available if self.words[i]["answer"] != self.word["answer"]
            ] or available
        # About one challenge after four ordinary questions, while each pool
        # has unseen words. Preserve the full-bank no-repeat cycle.
        hard_turn = (self.round_number + 1) % 5 == 0
        preferred = [
            i
            for i in available
            if (self.words[i].get("difficulty") == "hard") == hard_turn
        ]
        pool = preferred or available
        varied = [
            i
            for i in pool
            if self.words[i].get("category") not in self.recent_categories[-2:]
        ]
        chosen = self.rng.choice(varied or pool)
        self.recent_categories = (
            self.recent_categories + [self.words[chosen].get("category", "")]
        )[-3:]
        self.used_words.add(chosen)
        self.used_answers.add(self.word_keys[chosen])
        self.recent_answers = (self.recent_answers + [self.word_keys[chosen]])[-100:]
        return chosen

    def submit(self, nickname, text, *, player_id, event_id="", created_at=0):
        if self.enabled and str(text).strip().lower() == "!vuatiengviet":
            return "already-playing"
        status = super().submit(
            nickname,
            text,
            player_id=player_id,
            event_id=event_id,
            created_at=created_at,
        )
        if (
            self.enabled
            and status in ("accepted", "rate-limited", "not-playing")
            and self.phase in ("playing", "finished")
            and (not created_at or created_at >= self.started_at)
        ):
            if event_id and any(
                item.get("event_id") == event_id for item in self.round_comments
            ):
                return status
            player = self.players.get(player_id)
            accepted = status == "accepted"
            received = player["last_at"] if accepted else self.clock()
            guess = player["last_guess"] if accepted else str(text)
            correct = accepted and normalize_answer(guess) == normalize_answer(
                self.word["answer"]
            )
            self.comment_sequence += 1
            if correct and player["last_at"] == player["best_at"]:
                player.setdefault("first_correct_order", self.comment_sequence)
            self.round_comments.append(
                {
                    "id": self.comment_sequence,
                    "event_id": event_id,
                    "player_id": player_id,
                    "nickname": str(nickname or "bạn")[:40],
                    "text": str(text)[:180],
                    "player_tag": f"P{player['order'] + 1:03d}" if player else "",
                    "elapsed_ms": max(0, round((received - self.started) * 1000)),
                    "correct": correct,
                    "scored": accepted,
                    "first_correct": correct and player["last_at"] == player["best_at"],
                }
            )
            self.round_comments = self.round_comments[-60:]
            if not accepted:
                self.revision += 1
        return status

    def tick(self, *, ready=True):
        self._settle_days()
        if not self.enabled:
            return super().tick(ready=ready)
        super().tick(ready=ready)
        if self.phase == "finished" and self._recorded_round_id != self.round_id:
            self._record_round()
            self.cooldown_deadline = self.clock() + 20
            self.revision += 1
            self._save()
        elif self.phase == "finished" and not self.cooldown_remaining and ready:
            self._next_round()
            self._save()

    def ranking(self):
        if not self.enabled:
            return super().ranking()
        return sorted(
            self.players.values(),
            key=lambda p: (
                -p["score"],
                p["best_at"],
                p.get("first_correct_order", p["order"]),
            ),
        )

    def _record_round(self):
        # Round results update daily standings; honor is awarded after the day closes.
        winners = [
            (ident, player)
            for ident, player in self.players.items()
            if player["score"] == 100
        ]
        winners.sort(
            key=lambda item: (
                item[1]["best_at"],
                item[1].get("first_correct_order", item[1]["order"]),
            )
        )
        result = [
            {
                "position": rank,
                "received_order": player.get("first_correct_order", player["order"]),
                "player_tag": f"P{player['order'] + 1:03d}",
                "nickname": player["nickname"],
                "answer": player["guess"],
                "elapsed_ms": max(0, round((player["best_at"] - self.started) * 1000)),
                "bonus": 0,
            }
            for rank, (_, player) in enumerate(winners, 1)
        ]
        original = self.standings
        updated = dict(original)
        account = self.account.casefold()
        try:
            with self._db() as db:
                existing = db.execute(
                    "SELECT result_json FROM classroom_round_awards WHERE account=? AND session_id=? AND round_id=?",
                    (account, self.session_id, self.round_id),
                ).fetchone()
                if existing:
                    saved_result = json.loads(existing[0])
                    self._round_result = (
                        saved_result.get("winners", [])
                        if isinstance(saved_result, dict)
                        else saved_result
                    )
                    self._recorded_round_id = self.round_id
                    return
                for rank, (player_id, player) in enumerate(winners, 1):
                    seconds = max(0, player["best_at"] - self.started)
                    record = (
                        dict(updated[player_id])
                        if player_id in updated
                        else {
                            "nickname": player["nickname"],
                            "correct": 0,
                            "points": 0,
                            "first_correct": self.wall_clock(),
                            "order": len(updated),
                            "avatar_seed": uuid.uuid4().hex,
                        }
                    )
                    if player_id in updated or len(updated) < 5000:
                        record["nickname"] = player["nickname"]
                        record["correct"] += 1
                        seconds = max(0, player["best_at"] - self.started)
                        record["points"] += max(10, 100 - int(seconds))
                        updated[player_id] = record
                    db.execute(
                        """INSERT INTO classroom_daily_scores
                        (account,day,player_id,nickname,avatar_seed,correct,points,first_correct)
                        VALUES(?,?,?,?,?,1,?,?) ON CONFLICT(account,day,player_id) DO UPDATE SET
                        nickname=excluded.nickname,correct=correct+1,points=points+excluded.points""",
                        (
                            account,
                            self._day(self.wall_clock()),
                            player_id,
                            record["nickname"],
                            record["avatar_seed"],
                            max(10, 100 - int(seconds)),
                            self.wall_clock(),
                        ),
                    )
                db.execute(
                    "INSERT INTO classroom_round_awards VALUES(?,?,?,?,?)",
                    (
                        account,
                        self.session_id,
                        self.round_id,
                        self.wall_clock(),
                        json.dumps(
                            {
                                "answer": self.word["answer"],
                                "duration": self.duration,
                                "ranking_method": "server_first_correct",
                                "winners": result,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                self.standings = updated
                self._save(connection=db)
            self._round_result = result
            self._recorded_round_id = self.round_id
        except BaseException:
            self.standings = original
            raise

    @staticmethod
    def _day(timestamp):
        return (
            datetime.fromtimestamp(timestamp, timezone(timedelta(hours=7)))
            .date()
            .isoformat()
        )

    def _init_daily_honor(self):
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_daily_scores (
                account TEXT NOT NULL,day TEXT NOT NULL,player_id TEXT NOT NULL,
                nickname TEXT NOT NULL,avatar_seed TEXT NOT NULL,correct INTEGER NOT NULL,
                points INTEGER NOT NULL,first_correct REAL NOT NULL,
                PRIMARY KEY(account,day,player_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS classroom_daily_awards (
                account TEXT NOT NULL,day TEXT NOT NULL,awarded_at REAL NOT NULL,
                result_json TEXT NOT NULL,PRIMARY KEY(account,day))""")
            db.execute(
                "CREATE TABLE IF NOT EXISTS classroom_migrations (name TEXT PRIMARY KEY)"
            )
            if db.execute(
                "SELECT 1 FROM classroom_migrations WHERE name='daily_honor_v1'"
            ).fetchone():
                return
            # Keep the old totals intact for audit before replacing per-question awards.
            db.execute(
                "CREATE TABLE IF NOT EXISTS classroom_honor_before_daily AS SELECT * FROM classroom_honor"
            )
            db.execute("DELETE FROM classroom_honor")
            # Preserve operator-verified podiums, which were already awarded once per LIVE.
            for account, _, awarded_at, payload in db.execute(
                "SELECT * FROM classroom_session_awards"
            ).fetchall():
                for rank, player in enumerate(json.loads(payload)["podium"], 1):
                    self._award_honor(db, account, player, rank, awarded_at)
            # Legacy sessions only stored cumulative standings, so seed their known totals
            # on the session's local start date. New rounds use the actual completion day.
            for account, _, _, payload in db.execute(
                "SELECT * FROM classroom_sessions"
            ).fetchall():
                session = json.loads(payload)
                day = self._day(session["session_start"])
                for ident, player in session["standings"].items():
                    db.execute(
                        """INSERT INTO classroom_daily_scores VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(account,day,player_id) DO UPDATE SET
                        correct=correct+excluded.correct,points=points+excluded.points,
                        first_correct=min(first_correct,excluded.first_correct)""",
                        (
                            account,
                            day,
                            ident,
                            player["nickname"],
                            player.get("avatar_seed") or uuid.uuid4().hex,
                            player["correct"],
                            player["points"],
                            player["first_correct"],
                        ),
                    )
            db.execute("INSERT INTO classroom_migrations VALUES('daily_honor_v1')")
        self._settle_days()

    def _award_honor(self, db, account, player, rank, now):
        db.execute(
            """INSERT INTO classroom_honor VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(account,player_id) DO UPDATE SET
            nickname=excluded.nickname,points=classroom_honor.points+excluded.points,
            gold=classroom_honor.gold+excluded.gold,silver=classroom_honor.silver+excluded.silver,
            bronze=classroom_honor.bronze+excluded.bronze,last_award=excluded.last_award""",
            (
                account,
                player["player_id"],
                player["nickname"],
                player.get("avatar_seed") or uuid.uuid4().hex,
                HONOR_BONUSES[rank - 1],
                int(rank == 1),
                int(rank == 2),
                int(rank == 3),
                now,
                now,
            ),
        )

    def _settle_days(self):
        today = self._day(self.wall_clock())
        with self._db() as db:
            days = db.execute(
                """SELECT DISTINCT account,day FROM classroom_daily_scores s
                WHERE day<? AND NOT EXISTS (SELECT 1 FROM classroom_daily_awards a
                WHERE a.account=s.account AND a.day=s.day)""",
                (today,),
            ).fetchall()
            for account, day in days:
                # Claim the day before adding any bonuses, in the same transaction.
                claimed = db.execute(
                    "INSERT OR IGNORE INTO classroom_daily_awards VALUES(?,?,?,?)",
                    (account, day, self.wall_clock(), "[]"),
                ).rowcount
                if not claimed:
                    continue
                rows = db.execute(
                    """SELECT player_id,nickname,avatar_seed FROM classroom_daily_scores
                    WHERE account=? AND day=? AND correct>0
                    ORDER BY correct DESC,points DESC,first_correct ASC,player_id ASC LIMIT 3""",
                    (account, day),
                ).fetchall()
                podium = [
                    dict(zip(("player_id", "nickname", "avatar_seed"), row))
                    for row in rows
                ]
                for rank, player in enumerate(podium, 1):
                    self._award_honor(db, account, player, rank, self.wall_clock())
                db.execute(
                    "UPDATE classroom_daily_awards SET result_json=? WHERE account=? AND day=?",
                    (json.dumps(podium, ensure_ascii=False), account, day),
                )

    def restore_session_podium(self, session_id, podium, proof):
        """One-time operator repair of a previous LIVE's known final podium."""
        if not session_id or not 1 <= len(podium) <= 3:
            raise ValueError("A verified previous session and podium are required")
        if len({row["player_id"] for row in podium}) != len(podium):
            raise ValueError("Podium participants must be distinct")
        account = self.account.casefold()
        with self._db() as db:
            if db.execute(
                "SELECT 1 FROM classroom_session_awards WHERE account=? AND session_id=?",
                (account, session_id),
            ).fetchone():
                return False
            now = self.wall_clock()
            for rank, row in enumerate(podium, 1):
                db.execute(
                    """INSERT INTO classroom_honor
                    (account,player_id,nickname,avatar_seed,points,gold,silver,bronze,first_award,last_award)
                    VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(account,player_id) DO UPDATE SET
                    nickname=excluded.nickname,points=classroom_honor.points+excluded.points,
                    gold=classroom_honor.gold+excluded.gold,silver=classroom_honor.silver+excluded.silver,
                    bronze=classroom_honor.bronze+excluded.bronze,last_award=excluded.last_award""",
                    (
                        account,
                        row["player_id"],
                        row["nickname"],
                        row.get("avatar_seed") or uuid.uuid4().hex,
                        HONOR_BONUSES[rank - 1],
                        int(rank == 1),
                        int(rank == 2),
                        int(rank == 3),
                        now,
                        now,
                    ),
                )
            db.execute(
                "INSERT INTO classroom_session_awards VALUES(?,?,?,?)",
                (
                    account,
                    session_id,
                    now,
                    json.dumps(
                        {
                            "kind": "previous_live_podium",
                            "podium": podium,
                            "proof": proof,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        return True

    def honor_board(self):
        with self._db() as db:
            rows = db.execute(
                """SELECT nickname,avatar_seed,points,gold,silver,bronze FROM classroom_honor
                WHERE account=? ORDER BY points DESC,gold DESC,silver DESC,bronze DESC,first_award ASC,player_id ASC LIMIT 40""",
                (self.account.casefold(),),
            ).fetchall()
        return [
            dict(
                zip(
                    (
                        "nickname",
                        "avatar_seed",
                        "honor_points",
                        "gold",
                        "silver",
                        "bronze",
                    ),
                    row,
                )
            )
            for row in rows
        ]

    def public_comments(self):
        positions = {}
        if self.phase == "finished":
            winners = [
                (ident, p) for ident, p in self.players.items() if p["score"] == 100
            ]
            winners.sort(
                key=lambda item: (
                    item[1]["best_at"],
                    item[1].get("first_correct_order", item[1]["order"]),
                )
            )
            positions = {ident: i + 1 for i, (ident, _) in enumerate(winners)}
        rows = []
        for item in self.round_comments:
            row = {
                key: item[key]
                for key in ("id", "nickname", "text", "elapsed_ms", "player_tag")
            }
            row["status"] = "received" if item.get("scored", True) else "not_scored"
            if self.phase == "finished":
                row["status"] = (
                    "correct"
                    if item["correct"]
                    else "incorrect"
                    if item.get("scored", True)
                    else "not_scored"
                )
                if item["first_correct"]:
                    row["position"] = positions.get(item["player_id"])
            rows.append(row)
        return rows

    def recent_results(self):
        with self._db() as db:
            rows = db.execute(
                """SELECT round_id,completed_at,result_json FROM classroom_round_awards
                WHERE account=? ORDER BY completed_at DESC,rowid DESC LIMIT 10""",
                (self.account.casefold(),),
            ).fetchall()
        output = []
        for round_id, completed_at, payload in rows:
            data = json.loads(payload)
            if isinstance(data, list):
                data = {"answer": "", "winners": data}
            output.append(
                {
                    "round_id": round_id,
                    "completed_at": completed_at,
                    "answer": data.get("answer", ""),
                    "ranking_method": "server_first_correct",
                    "winners": data.get("winners", [])[:SEAT_COUNT],
                }
            )
        return output

    @property
    def speak_hints(self):
        return True

    def start_speech(self):
        if not self.enabled:
            return super().start_speech()
        invitation = (
            "Chào cả nhà đến lớp Vua Tiếng Việt cùng Mao! Bình luận đáp án để chơi, không dấu cũng được. "
            if self.round_number == 1
            else ""
        )
        return f"{invitation}Câu tiếp theo, chủ đề {self.word['category']}. {self.word['hints'][0]}"

    def announcement_valid(self, round_id, kind):
        if self.enabled and kind == "chat":
            return round_id == self.round_id and (
                self.phase == "playing"
                and self.deadline - self.clock() > 3
                or self.phase == "finished"
                and self.cooldown_remaining > 4
            )
        return super().announcement_valid(round_id, kind)

    @staticmethod
    def _spoken_name(name):
        return re.sub(r"[\[\]<>\r\n]", " ", str(name))[:40].strip() or "bạn"

    def _result_speech(self):
        if not self.enabled:
            return super()._result_speech()
        winners = [p for p in self.ranking() if p["score"] == 100]
        if winners:
            name = self._spoken_name(winners[0]["nickname"])
            reaction = self._result_line(
                "classroom-winner",
                (
                    "Chúc mừng {name}, bạn đoán nhanh nhất câu này! Mao vỗ tay cho bạn nè!",
                    "Nhanh nhất là {name}! Chúc mừng bạn nha, bắt từ nhanh thật đó!",
                    "Một tràng vỗ tay cho {name}, người về đầu câu này nhé!",
                    "{name} về đầu rồi! Chúc mừng bạn, cả nhà mình cùng vỗ tay nào!",
                ),
            ).format(name=name)
            if len(winners) > 1:
                others = ", ".join(
                    self._spoken_name(p["nickname"]) for p in winners[1:3]
                )
                reaction += f" {others} cũng đoán đúng nữa nè!"
            reaction += f" Câu này có {len(winners)} bạn đúng."
        else:
            reaction = self._result_line(
                "classroom-no-winner",
                (
                    "Câu này chưa ai đúng, không sao đâu! Mình chơi vui mà, câu sau thử tiếp với Mao nha.",
                    "Chưa ai đoán trúng nè. Biết thêm một câu hay cũng lời rồi, cả nhà đừng nản nhé!",
                    "Mình cùng bỏ túi đáp án này nha. Câu sau biết đâu bạn lại về đầu đó!",
                ),
            )
        return f"Hết giờ! Đáp án là {self.word['answer']}. {reaction} {self.word['explanation']}"

    def feedback_speech(self, nickname, guess):
        if not self.enabled:
            return super().feedback_speech(nickname, guess)
        name = self._spoken_name(nickname)
        hint = self.word["hints"][self.hint_index]
        choices = (
            f"Mao nhận được lượt đoán của {name} rồi! Mình để ý gợi ý này nha: {hint}",
            f"Cảm ơn {name} đã thử nhé! Cả lớp cùng nghĩ tiếp nè: {hint}",
            f"{name} đang cùng Mao tìm từ rồi nè. Nhớ gợi ý này nhé: {hint}",
        )
        return choices[self.hint_index % len(choices)]

    def snapshot(self):
        state = super().snapshot()
        board = sorted(
            self.standings.values(),
            key=lambda p: (-p["correct"], -p["points"], p["first_correct"], p["order"]),
        )
        # Public rows never contain stable account identifiers.
        rows = [
            {k: p[k] for k in ("nickname", "correct", "points", "avatar_seed")}
            for p in board[:SEAT_COUNT]
        ]
        with self._db() as db:
            daily = [
                dict(zip(("nickname", "avatar_seed", "correct", "points"), row))
                for row in db.execute(
                    """SELECT nickname,avatar_seed,correct,points FROM classroom_daily_scores
                WHERE account=? AND day=? ORDER BY correct DESC,points DESC,first_correct ASC,player_id ASC LIMIT 40""",
                    (self.account.casefold(), self._day(self.wall_clock())),
                )
            ]
        state["classroom"] = {
            "enabled": self.enabled,
            "session_id": self.session_id,
            "starts_at": self.session_start,
            "ends_at": self.session_end,
            "remaining": max(0, self.session_end - self.wall_clock()),
            "unlimited": True,
            "round_number": self.round_number,
            "account": self.account,
            "standings": rows,
            "seats": rows + [None] * (SEAT_COUNT - len(rows)),
            "seat_count": SEAT_COUNT,
            "honor": self.honor_board(),
            "honor_bonuses": list(HONOR_BONUSES),
            "daily_standings": daily,
            "daily_seats": daily + [None] * (SEAT_COUNT - len(daily)),
            "honor_period": "daily",
            "honor_timezone": "Asia/Ho_Chi_Minh",
            "comments": self.public_comments(),
            "round_results": self._round_result[:SEAT_COUNT]
            if self.phase == "finished"
            else [],
            "ranking_method": "server_first_correct",
            "players": len(self.standings),
            "bank_size": len(self.eligible_indices),
            "bank_total": len(self.words),
            "retired_count": len(self.words) - len(self.eligible_indices),
            "reason": self.end_reason,
        }
        if self.phase == "finished" and self.word:
            state["explanation"] = self.word["explanation"]
            state["correct_count"] = sum(
                p["score"] == 100 for p in self.players.values()
            )
        return state


def install_classroom_routes(app, service, profile):
    """Only a host control token can toggle the classroom; comments cannot."""
    import secrets
    from fastapi import HTTPException, Request
    from pydantic import BaseModel, Field
    from ..interaction.ingress import control_token

    class Options(BaseModel):
        enabled: bool
        account: str = Field(
            default="@thanhoathirty6", pattern=r"^@[A-Za-z0-9_.]{1,24}$"
        )

    @app.get("/api/classroom/results")
    async def results():
        return {"rounds": service.game.recent_results()}

    @app.post("/api/classroom/control")
    async def control(options: Options, request: Request):
        if request.client.host not in {
            "127.0.0.1",
            "::1",
        } or not secrets.compare_digest(
            request.headers.get("X-Mao-Control", ""), control_token(profile)
        ):
            raise HTTPException(403, "Local host authorization required")
        if options.enabled:
            if service.proxy and service.proxy.singing and service.proxy.singing.active:
                raise HTTPException(409, "Dừng tiết mục hát trước khi mở lớp.")
            service.game.enable(options.account)
        else:
            service.game.disable()
            if (
                service.proxy
                and getattr(service.proxy, "_active_input_source", None)
                == "vua-tieng-viet"
            ):
                await service.proxy.forward_to_server({"type": "interrupt-signal"})
        await service.publish()
        return service.game.snapshot()
