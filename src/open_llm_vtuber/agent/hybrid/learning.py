"""Daily measurements and bounded preferences; no self-grading or weight updates.

Only the local operator CLI can write ratings. The model has no learning tools.
An adaptation means a measured preference change, not a claim of greater ability.
"""

import asyncio
from collections import Counter
from datetime import datetime, time, timedelta
import hashlib
import math
import re
import uuid
from zoneinfo import ZoneInfo

from loguru import logger
from psycopg.types.json import Jsonb


def decide(current, labels, minimum=3):
    """Unanimous length feedback only; factual/safety feedback freezes adaptation."""
    counts = Counter(labels)
    if counts["incorrect"] or counts["unsafe"]:
        return 60, "reset_after_operator_quality_flag"
    if counts["too_long"] >= minimum and not counts["too_short"]:
        return max(40, current - 5), "operator_requested_shorter_proactive_speech"
    if counts["too_short"] >= minimum and not counts["too_long"]:
        return min(60, current + 5), "operator_requested_longer_proactive_speech"
    return current, "keep_current_insufficient_or_conflicting_feedback"


class DailyLearning:
    def __init__(self, store):
        self.store = store
        self.config = store.config
        self.scope = store.scope
        self.zone = ZoneInfo(self.config.learning_timezone)

    def profile(self, db=None):
        if db is None:
            with self.store.connect() as connection:
                return self.profile(connection)
        return db.execute(
            "SELECT version,proactive_max_words FROM mao_hybrid.learning_profiles WHERE scope=%s ORDER BY version DESC LIMIT 1",
            (self.scope,),
        ).fetchone() or {"version": None, "proactive_max_words": 60}

    def record(self, response, metrics, kind="conversation", profile_version=None):
        if not self.config.learning_enabled:
            return None
        # A fixed metric schema prevents page/chat text or secrets entering JSON.
        clean = {}
        for key in (
            "duration_ms",
            "first_audio_ms",
            "audio_chunks",
            "errors",
            "cancelled",
        ):
            value = metrics.get(key)
            if isinstance(value, (int, float)) and math.isfinite(value):
                clean[key] = max(0, min(float(value), 86400000))
        words = re.sub(r"\[[^\]]*\]", "", response).split()
        clean.update(words=len(words), empty=not bool(words))
        identifier = uuid.uuid4().hex
        digest = hashlib.sha256(response.encode()).hexdigest()
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO mao_hybrid.learning_turns(scope,id,kind,profile_version,response_hash,metrics) VALUES(%s,%s,%s,%s,%s,%s)",
                (self.scope, identifier, kind, profile_version, digest, Jsonb(clean)),
            )
        return identifier

    def review(self, day):
        if day >= datetime.now(self.zone).date():
            raise ValueError("Review only a completed local day")
        start = datetime.combine(day, time(), self.zone)
        end = datetime.combine(day + timedelta(days=1), time(), self.zone)
        with self.store.connect() as db:
            # One transaction and one scope lock: multiple server sessions cannot
            # promote twice; a failed review leaves neither report nor profile.
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                ("learning:" + self.scope,),
            )
            old = db.execute(
                "SELECT report FROM mao_hybrid.learning_days WHERE scope=%s AND day=%s",
                (self.scope, day),
            ).fetchone()
            if old:
                return old["report"]
            turns = db.execute(
                "SELECT kind,metrics,response_hash FROM mao_hybrid.learning_turns WHERE scope=%s AND created>=%s AND created<%s AND kind<>'rehearsal'",
                (self.scope, start, end),
            ).fetchall()
            profile = self.profile(db)
            labels = db.execute(
                """SELECT f.label FROM mao_hybrid.learning_feedback f
                JOIN mao_hybrid.learning_turns t ON (t.scope,t.id)=(f.scope,f.turn_id)
                WHERE f.scope=%s AND f.created>=%s AND f.created<%s
                AND t.kind='proactive' AND t.profile_version IS NOT DISTINCT FROM %s""",
                (self.scope, start, end, profile["version"]),
            ).fetchall()
            feedback = [r["label"] for r in labels]
            budget, reason = profile["proactive_max_words"], "insufficient_data"
            if len(turns) >= self.config.learning_min_turns:
                budget, reason = decide(
                    budget, feedback, self.config.learning_min_feedback
                )
            changed = budget != profile["proactive_max_words"]
            version = profile["version"]
            if changed:
                version = db.execute(
                    "INSERT INTO mao_hybrid.learning_profiles(scope,proactive_max_words,reason) VALUES(%s,%s,%s) RETURNING version",
                    (self.scope, budget, reason),
                ).fetchone()["version"]
            audio_times = sorted(
                t["metrics"]["first_audio_ms"]
                for t in turns
                if "first_audio_ms" in t["metrics"]
            )
            report = {
                "day": str(day),
                "timezone": self.config.learning_timezone,
                "turns": len(turns),
                "empty_turns": sum(bool(t["metrics"].get("empty")) for t in turns),
                "error_turns": sum(bool(t["metrics"].get("errors")) for t in turns),
                "cancelled_turns": sum(
                    bool(t["metrics"].get("cancelled")) for t in turns
                ),
                "repeated_responses": len(turns)
                - len({t["response_hash"] for t in turns}),
                "first_audio_median_ms": audio_times[len(audio_times) // 2]
                if audio_times
                else None,
                "operator_feedback": dict(Counter(feedback)),
                "decision": reason,
                "changed": changed,
                "profile_version": version,
                "proactive_max_words": budget,
                "quality_improvement_verified": False,
            }
            db.execute(
                "INSERT INTO mao_hybrid.learning_days(scope,day,report) VALUES(%s,%s,%s)",
                (self.scope, day, Jsonb(report)),
            )
            db.execute(
                "DELETE FROM mao_hybrid.learning_turns WHERE scope=%s AND created<now()-%s*interval '1 day'",
                (self.scope, self.config.learning_retention_days),
            )
            db.execute(
                "DELETE FROM mao_hybrid.learning_days WHERE scope=%s AND day<%s",
                (self.scope, day - timedelta(days=self.config.learning_retention_days)),
            )
            return report

    async def run(self):
        """Catch up completed days after restart, bounded to the retention window."""
        while True:
            try:
                for day in await asyncio.to_thread(self.pending_days):
                    await asyncio.to_thread(self.review, day)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Daily learning unavailable: {}", type(error).__name__)
            await asyncio.sleep(300)

    def pending_days(self):
        today = datetime.now(self.zone).date()
        with self.store.connect() as db:
            row = db.execute(
                "SELECT min(created) AS first FROM mao_hybrid.learning_turns WHERE scope=%s",
                (self.scope,),
            ).fetchone()
            completed = {
                r["day"]
                for r in db.execute(
                    "SELECT day FROM mao_hybrid.learning_days WHERE scope=%s",
                    (self.scope,),
                ).fetchall()
            }
        first = (
            row["first"].astimezone(self.zone).date()
            if row["first"]
            else today - timedelta(days=1)
        )
        first = max(first, today - timedelta(days=self.config.learning_retention_days))
        return [
            first + timedelta(days=offset)
            for offset in range((today - first).days)
            if first + timedelta(days=offset) not in completed
        ]

    def status(self):
        with self.store.connect() as db:
            days = db.execute(
                "SELECT report FROM mao_hybrid.learning_days WHERE scope=%s ORDER BY day DESC LIMIT 7",
                (self.scope,),
            ).fetchall()
            turns = db.execute(
                "SELECT id,created,kind,metrics,profile_version FROM mao_hybrid.learning_turns WHERE scope=%s ORDER BY created DESC LIMIT 20",
                (self.scope,),
            ).fetchall()
            return {
                "enabled": self.config.learning_enabled,
                "profile": self.profile(db),
                "days": [d["report"] for d in days],
                "recent_turns": turns,
            }
