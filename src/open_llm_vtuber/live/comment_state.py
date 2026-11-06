"""Durable deduplication plus a bounded, seven-day local operator comment audit."""

import hashlib
import json
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path


COMMENT_STATE_PATH = (
    Path(__file__).resolve().parents[3] / "private/mao-comment-state.db"
)


class CommentState:
    MAX_RECORDS = 20_000

    def __init__(self, path=COMMENT_STATE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._new_records = 0
        with self._database() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS comments ("
                "event_key TEXT PRIMARY KEY, created_at REAL NOT NULL, "
                "received_at REAL NOT NULL, state TEXT NOT NULL, updated_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS comment_audit (event_key TEXT PRIMARY KEY, "
                "account TEXT NOT NULL, nickname TEXT NOT NULL, text TEXT NOT NULL, "
                "state TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', batch_id TEXT NOT NULL DEFAULT '', "
                "received_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS comment_transitions (id INTEGER PRIMARY KEY, "
                "event_key TEXT NOT NULL, state TEXT NOT NULL, reason TEXT NOT NULL, at REAL NOT NULL)"
            )
            self._prune(db)

    @contextmanager
    def _database(self):
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                yield db

    @staticmethod
    def identity(channel, message_id, created_at, viewer, text):
        if message_id:
            identity = [channel.casefold(), "id", str(message_id)]
        else:
            # A retransmitted event keeps its original creation time. Without
            # either field, suppress the same viewer/text rather than inventing
            # a fresh identity from the time we happened to receive it.
            identity = [
                channel.casefold(),
                "fallback",
                created_at or 0,
                str(viewer),
                text,
            ]
        return hashlib.sha256(
            json.dumps(identity, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def reserve(self, event_key, created_at=0):
        now = time.time()
        with self._database() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO comments VALUES (?, ?, ?, 'queued', ?)",
                (event_key, created_at or 0, now, now),
            ).rowcount
            if inserted:
                self._new_records += 1
                if self._new_records % 100 == 0:
                    self._prune(db)
        return bool(inserted)

    def audit(self, event_key, account, nickname, text, state="received", reason=""):
        now = time.time()
        with self._database() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO comment_audit VALUES(?,?,?,?,?,?,?, ?,?)",
                (
                    event_key,
                    account,
                    nickname[:40],
                    text[:300],
                    state,
                    reason,
                    "",
                    now,
                    now,
                ),
            ).rowcount
            if inserted:
                db.execute(
                    "INSERT INTO comment_transitions(event_key,state,reason,at) VALUES(?,?,?,?)",
                    (event_key, state, reason, now),
                )
        return bool(inserted)

    def set_state(self, event_keys, state, reason="", batch_id=None):
        if not event_keys:
            return
        with self._database() as db:
            db.executemany(
                "UPDATE comments SET state=?, updated_at=? WHERE event_key=?",
                [(state, time.time(), key) for key in event_keys],
            )
            for key in event_keys:
                previous = db.execute(
                    "SELECT state,reason FROM comment_audit WHERE event_key=?", (key,)
                ).fetchone()
                if previous:
                    db.execute(
                        "UPDATE comment_audit SET state=?,reason=?,batch_id=COALESCE(?,batch_id),updated_at=? WHERE event_key=?",
                        (state, reason, batch_id, time.time(), key),
                    )
                    if previous != (state,reason):
                        db.execute(
                            "INSERT INTO comment_transitions(event_key,state,reason,at) VALUES(?,?,?,?)",
                            (key, state, reason, time.time()),
                        )

    def snapshot(self, limit=40, account=None):
        with self._database() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM comment_audit WHERE (? IS NULL OR account=?) ORDER BY received_at DESC,rowid DESC LIMIT ?",
                (account, account, max(1, min(limit, 100))),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["transitions"] = [
                    dict(value)
                    for value in db.execute(
                        "SELECT state,reason,at FROM comment_transitions WHERE event_key=? ORDER BY id DESC LIMIT 12",
                        (row["event_key"],),
                    ).fetchall()
                ][::-1]
                result.append(item)
            return result

    def stage(self, event_keys, state, reason=""):
        """Detailed delivery stages without changing legacy deduplication states."""
        with self._database() as db:
            for key in event_keys:
                row = db.execute(
                    "SELECT state FROM comment_audit WHERE event_key=?", (key,)
                ).fetchone()
                if row and row[0] != state:
                    now = time.time()
                    db.execute(
                        "UPDATE comment_audit SET state=?,reason=?,updated_at=? WHERE event_key=?",
                        (state, reason, now, key),
                    )
                    db.execute(
                        "INSERT INTO comment_transitions(event_key,state,reason,at) VALUES(?,?,?,?)",
                        (key, state, reason, now),
                    )

    def get_state(self, event_key):
        with self._database() as db:
            row = db.execute(
                "SELECT state FROM comments WHERE event_key=?", (event_key,)
            ).fetchone()
        return row[0] if row else None

    def _prune(self, db):
        db.execute(
            "DELETE FROM comment_audit WHERE received_at<?", (time.time() - 7 * 86400,)
        )
        db.execute(
            "DELETE FROM comment_audit WHERE event_key IN (SELECT event_key FROM comment_audit ORDER BY received_at DESC LIMIT -1 OFFSET ?)",
            (self.MAX_RECORDS,),
        )
        db.execute(
            "DELETE FROM comment_transitions WHERE event_key NOT IN (SELECT event_key FROM comment_audit)"
        )
        # Keep outstanding work even if a very busy room fills the history.
        db.execute(
            "DELETE FROM comments WHERE event_key IN ("
            "SELECT event_key FROM comments WHERE state IN ('answered', 'skipped', 'completed') "
            "ORDER BY received_at DESC, rowid DESC LIMIT -1 OFFSET ?)",
            (self.MAX_RECORDS,),
        )
