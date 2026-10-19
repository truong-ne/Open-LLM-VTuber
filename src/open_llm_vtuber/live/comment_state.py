"""Durable TikTok event states; stores hashes and timing, never chat text."""

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

    def set_state(self, event_keys, state):
        if not event_keys:
            return
        with self._database() as db:
            db.executemany(
                "UPDATE comments SET state=?, updated_at=? WHERE event_key=?",
                [(state, time.time(), key) for key in event_keys],
            )

    def get_state(self, event_key):
        with self._database() as db:
            row = db.execute(
                "SELECT state FROM comments WHERE event_key=?", (event_key,)
            ).fetchone()
        return row[0] if row else None

    def _prune(self, db):
        # Keep outstanding work even if a very busy room fills the history.
        db.execute(
            "DELETE FROM comments WHERE event_key IN ("
            "SELECT event_key FROM comments WHERE state IN ('answered', 'skipped', 'completed') "
            "ORDER BY received_at DESC, rowid DESC LIMIT -1 OFFSET ?)",
            (self.MAX_RECORDS,),
        )
