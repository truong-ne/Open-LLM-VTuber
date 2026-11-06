"""Source-backed preferences scoped to platform account and stable viewer ID."""

import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from ..character.appraisal import folded


def preference(text):
    value = folded(text.strip())
    if len(text) > 240 or re.search(
        r'["“”`]|gia su|gia vo|noi dua|haha|password|mat khau|dia chi|so dien thoai|cccd|can cuoc|ngan hang|ung thu|tram cam|tinh duc|ton giao|chinh tri',
        value,
    ):
        return None
    if re.search(
        r"^(?:mao oi[,! ]*)?(?:toi|minh|to|em|anh) .{0,180}(?:de lan sau ke tiep|ke tiep lan sau|ke tiep sau|chuyen nay chua xong)",
        value,
    ):
        return ("thread", text.strip())
    if re.search(r"hom nay|luc nay", value):
        return None
    if re.search(
        r"^(?:mao oi[,! ]*)?(?:hay |tu nay |nho |nho rang )*goi (?:toi|minh|to|em|anh) la [\w ]{1,35}[.!]?$",
        value,
    ):
        return ("address", text.strip())
    if not re.search(
        r"^(?:(?:mao oi|nho|nho rang)[,! ]+)*(?:toi|minh|to|em|anh) (?:rat |khong )?(?:thich|me|ua)\b",
        value,
    ):
        return None
    for slot, pattern in (
        ("drink", r"ca phe|tra sua|tra dao|cacao|nuoc ep"),
        ("color", r"mau (?:xanh|do|vang|tim|hong|trang|den|cam)"),
        ("food", r"pho|xoi|bun|banh mi|pizza|com tam|mon an"),
        ("music", r"nhac|bai hat|piano|guitar"),
    ):
        if re.search(r"\b(?:" + pattern + r")\b", value):
            return (slot, text.strip())
    return None


class ViewerMemory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS viewer_preferences(account TEXT,author_id TEXT,slot TEXT,content TEXT,event_key TEXT,updated REAL,PRIMARY KEY(account,author_id,slot))"
            )

    def observe(self, account, author_id, text, event_key):
        if not author_id or not event_key:
            return
        value = folded(text)
        with closing(sqlite3.connect(self.path)) as db, db:
            if re.fullmatch(
                r"(?:mao oi[,! ]*)?chuyen (?:do|nay) (?:da )?(?:ke )?xong roi[.!]?",
                value,
            ):
                db.execute(
                    "DELETE FROM viewer_preferences WHERE account=? AND author_id=? AND slot=?",
                    (account, str(author_id), "thread"),
                )
                return
            if re.fullmatch(
                r"(?:mao oi[,! ]*)?(?:hay )?(?:quen|xoa) (?:het )?(?:so thich|ky uc|thong tin) cua (?:toi|minh|to)[.!]?",
                value,
            ):
                db.execute(
                    "DELETE FROM viewer_preferences WHERE account=? AND author_id=?",
                    (account, str(author_id)),
                )
                return
            item = preference(text)
            if not item:
                return
            slot, content = item
            db.execute(
                "INSERT INTO viewer_preferences VALUES(?,?,?,?,?,?) ON CONFLICT(account,author_id,slot) DO UPDATE SET content=excluded.content,event_key=excluded.event_key,updated=excluded.updated",
                (account, str(author_id), slot, content, event_key, time.time()),
            )
            db.execute(
                "DELETE FROM viewer_preferences WHERE updated<?",
                (time.time() - 90 * 86400,),
            )
            db.execute(
                "DELETE FROM viewer_preferences WHERE rowid IN (SELECT rowid FROM viewer_preferences ORDER BY updated DESC LIMIT -1 OFFSET 2000)"
            )

    def recall(self, account, author_id):
        if not author_id:
            return []
        with closing(sqlite3.connect(self.path)) as db:
            return [
                {
                    "content": r[0],
                    "source_event": r[1],
                    "observed_at": r[2],
                    "verified": False,
                }
                for r in db.execute(
                    "SELECT content,event_key,updated FROM viewer_preferences WHERE account=? AND author_id=? AND updated>? ORDER BY CASE WHEN slot='address' THEN 0 ELSE 1 END,updated DESC LIMIT 6",
                    (account, str(author_id), time.time() - 90 * 86400),
                )
            ]

    def summary(self, account=None):
        with closing(sqlite3.connect(self.path)) as db:
            count, viewers = db.execute(
                "SELECT count(*),count(DISTINCT author_id) FROM viewer_preferences WHERE updated>? AND (? IS NULL OR account=?)",
                (time.time() - 90 * 86400, account, account),
            ).fetchone()
        return {"preferences": count, "viewers": viewers, "retention_days": 90}
