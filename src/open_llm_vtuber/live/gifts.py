"""Durable TikTok gift leaderboard and a host-owned spoken thank-you outbox."""

import asyncio
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import time

from loguru import logger

ROOT = Path(__file__).resolve().parents[3]
GIFT_PATH = ROOT / "private/mao-gifts.sqlite3"


class GiftStore:
    def __init__(self, path=GIFT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS gifts (
                account TEXT NOT NULL,event_key TEXT NOT NULL,player_id TEXT NOT NULL,
                nickname TEXT NOT NULL,gift_name TEXT NOT NULL,count INTEGER NOT NULL,
                coins INTEGER NOT NULL,received_at REAL NOT NULL,announced INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(account,event_key))""")
            db.execute(
                "CREATE INDEX IF NOT EXISTS gifts_account_time ON gifts(account,received_at)"
            )

            db.execute("""CREATE TABLE IF NOT EXISTS gift_reconciliations (
                account TEXT NOT NULL,room_id TEXT NOT NULL,player_id TEXT NOT NULL,
                nickname TEXT NOT NULL,target_coins INTEGER NOT NULL,cutoff REAL NOT NULL,
                source TEXT NOT NULL,PRIMARY KEY(account,room_id,player_id))""")
            db.execute("""CREATE VIEW IF NOT EXISTS gift_contributions AS
                SELECT account,player_id,nickname,coins,count,received_at FROM gifts
                UNION ALL
                SELECT r.account,r.player_id,r.nickname,
                    max(0,r.target_coins-coalesce((SELECT sum(g.coins) FROM gifts g
                        WHERE g.account=r.account AND g.player_id=r.player_id
                        AND instr(g.event_key,r.room_id||':')=1 AND g.received_at<=r.cutoff),0)),
                    0,r.cutoff FROM gift_reconciliations r""")

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def record(
        self,
        account,
        event_key,
        player_id,
        nickname,
        gift_name,
        count,
        unit_coins,
        *,
        now=None,
    ):
        if (
            not event_key
            or not player_id
            or not 1 <= count <= 1000000
            or not 0 <= unit_coins <= 10000000
        ):
            return False
        with closing(self.connect()) as db, db:
            return bool(
                db.execute(
                    """INSERT INTO gifts VALUES(?,?,?,?,?,?,?,?,0)
                    ON CONFLICT(account,event_key) DO UPDATE SET
                        count=excluded.count,coins=excluded.coins,nickname=excluded.nickname,announced=0
                    WHERE instr(gifts.event_key,':combo:')>0 AND excluded.count>gifts.count
                        AND excluded.player_id=gifts.player_id AND excluded.gift_name=gifts.gift_name""",
                    (
                        account.casefold(),
                        str(event_key),
                        str(player_id),
                        str(nickname)[:80],
                        str(gift_name)[:80],
                        count,
                        count * unit_coins,
                        time.time() if now is None else now,
                    ),
                ).rowcount
            )

    def snapshot(self, account):
        with closing(self.connect()) as db:
            rows = db.execute(
                """SELECT player_id,sum(coins),sum(count),min(received_at),max(received_at)
                FROM gift_contributions WHERE account=? GROUP BY player_id
                ORDER BY sum(coins) DESC,sum(count) DESC,min(received_at),player_id LIMIT 10""",
                (account.casefold(),),
            ).fetchall()
            board = []
            for ident, coins, count, _, _ in rows:
                name = db.execute(
                    "SELECT nickname FROM gift_contributions WHERE account=? AND player_id=? ORDER BY received_at DESC LIMIT 1",
                    (account.casefold(), ident),
                ).fetchone()[0]
                board.append({"nickname": name, "coins": coins, "gifts": count})
            coins, count = db.execute(
                "SELECT coalesce(sum(coins),0),coalesce(sum(count),0) FROM gift_contributions WHERE account=?",
                (account.casefold(),),
            ).fetchone()
        return {
            "account": account,
            "total_coins": coins,
            "total_gifts": count,
            "leaderboard": board,
            "unit": "coin",
        }

    def reconcile_room_total(
        self,
        account,
        room_id,
        player_id,
        nickname,
        target_coins,
        source,
        *,
        cutoff=None,
    ):
        """Operator-provided total at a cutoff; late combo corrections consume the gap."""
        if (
            not source
            or not room_id
            or not player_id
            or type(target_coins) is not int
            or target_coins < 0
        ):
            raise ValueError("Verified room, player, coin total and source required")
        with closing(self.connect()) as db, db:
            previous = db.execute(
                "SELECT source FROM gift_reconciliations WHERE account=? AND room_id=? AND player_id=?",
                (account.casefold(), str(room_id), str(player_id)),
            ).fetchone()
            if previous and previous[0] == source:
                return False
            db.execute(
                """INSERT INTO gift_reconciliations VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(account,room_id,player_id) DO UPDATE SET
                    nickname=excluded.nickname,target_coins=excluded.target_coins,
                    cutoff=excluded.cutoff,source=excluded.source""",
                (
                    account.casefold(),
                    str(room_id),
                    str(player_id),
                    nickname,
                    target_coins,
                    time.time() if cutoff is None else cutoff,
                    source,
                ),
            )
        return True

    def pending(self, account, *, now=None):
        now = time.time() if now is None else now
        with closing(self.connect()) as db:
            return db.execute(
                """SELECT event_key,nickname,gift_name,count,coins FROM gifts
                WHERE account=? AND announced=0 AND received_at>=? ORDER BY received_at,rowid LIMIT 1""",
                (account.casefold(), now - 600),
            ).fetchone()

    def announced(self, account, event_key):
        with closing(self.connect()) as db, db:
            db.execute(
                "UPDATE gifts SET announced=1 WHERE account=? AND event_key=?",
                (account.casefold(), event_key),
            )


def gift_speech(nickname, gift_name, count, coins):
    # Names are literal speech, never instructions sent to a model.
    name = re.sub(r"[^\w\sÀ-ỹ.-]", "", nickname, flags=re.UNICODE).strip()[:40] or "bạn"
    gift = (
        re.sub(r"[^\w\sÀ-ỹ.-]", "", gift_name, flags=re.UNICODE).strip()[:40]
        or "món quà"
    )
    return f"Mao cảm ơn {name} đã tặng {count} {gift}, góp {coins} coin vào quỹ lớp nha! Cảm ơn bạn đã ủng hộ Mao và cả lớp nhé!"


class GiftService:
    def __init__(self, proxy, account, store=None):
        self.proxy = proxy
        self.account = account
        self.store = store or GiftStore()

    def dispatch_once(self):
        proxy = self.proxy()
        if not proxy or not proxy.connected or not proxy.clients:
            return False
        queue = proxy.message_queue
        if (
            queue.external_busy
            or any(
                item["message"].get("source") == "mao-gift"
                for item in queue.message_queue
            )
            or (
                queue.conversation_active
                and getattr(proxy, "_active_input_source", None) == "mao-gift"
            )
        ):
            return False
        # Thank gifts between activities, without cutting off a clue or a song.
        if (proxy.word_game and proxy.word_game.game.active) or (
            proxy.singing and proxy.singing.active
        ):
            return False
        row = self.store.pending(self.account())
        if not row:
            return False
        event_key, nickname, gift_name, count, coins = row
        from ..interaction.ingress import sign_host_proposal

        speech = gift_speech(nickname, gift_name, count, coins)
        accepted = queue.queue_message(
            sign_host_proposal(
                {
                    "type": "text-input",
                    "source": "mao-gift",
                    "event_id": "gift:" + event_key,
                    "text": speech,
                    "narration_speech": speech,
                }
            ),
            priority=True,
        )
        if accepted is False:
            return False
        self.store.announced(self.account(), event_key)
        return True

    async def run(self):
        while True:
            try:
                self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gift thank-you dispatch failed")
            await asyncio.sleep(1)
