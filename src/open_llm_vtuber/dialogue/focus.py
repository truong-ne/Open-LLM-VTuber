"""Short-lived conversational focus; silence creates no claims about the person."""

from ..experience.repository import Experiences
from ..character.appraisal import folded
from .attention import continues_topic, quiet_request


class Focus(Experiences):
    @staticmethod
    def attention_available(db):
        return bool(
            db.execute(
                "SELECT 1 FROM mao_hybrid.schema_versions WHERE version=10"
            ).fetchone()
        )

    def legacy_input(self, db, source, event_id, text):
        # Keep existing databases usable until the additive migration is applied.
        if source["visibility"] == "public":
            db.execute(
                "UPDATE mao_hybrid.dialogue_focus SET question='' WHERE scope=%s AND room_id=%s AND visibility='public'",
                (self.scope, source["room_id"]),
            )
        repair = any(
            word in folded(text)
            for word in (
                "hieu nham",
                "y to la",
                "y minh la",
                "misunderstood",
                "i meant",
            )
        )
        db.execute(
            """INSERT INTO mao_hybrid.dialogue_focus(scope,room_id,actor_id,visibility,source_event,topic,repair)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(scope,room_id,actor_id,visibility) DO UPDATE SET
            source_event=excluded.source_event,topic=excluded.topic,question='',repair=excluded.repair,
            revision=mao_hybrid.dialogue_focus.revision+1,expires=now()+interval '10 minutes'""",
            (
                self.scope,
                source["room_id"],
                source["actor_id"],
                source["visibility"],
                event_id,
                text[:180],
                repair,
            ),
        )

    def input(self, event_id, text):
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            if (
                source["synthetic"]
                or source["kind"] != "input"
                or source["raw_expired"]
            ):
                return
            if not self.attention_available(db):
                self.legacy_input(db, source, event_id, text)
                return
            control = quiet_request(text) if source["visibility"] != "public" else None
            previous = db.execute(
                """SELECT f.* FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=COALESCE(f.topic_event,f.source_event)
                WHERE f.scope=%s AND f.room_id=%s AND f.actor_id=%s AND f.visibility=%s
                AND f.expires>now() AND NOT e.deleted AND NOT e.raw_expired""",
                (
                    self.scope,
                    source["room_id"],
                    source["actor_id"],
                    source["visibility"],
                ),
            ).fetchone()
            keep = bool(previous and (continues_topic(text) or control))
            topic = previous["topic"] if keep else ("" if control else text[:180])
            topic_event = (
                (previous["topic_event"] or previous["source_event"])
                if keep
                else event_id
            )
            if source["visibility"] == "public":
                db.execute(
                    "UPDATE mao_hybrid.dialogue_focus SET question='' WHERE scope=%s AND room_id=%s AND visibility='public'",
                    (self.scope, source["room_id"]),
                )
            repair = any(
                word in folded(text)
                for word in (
                    "hieu nham",
                    "y to la",
                    "y minh la",
                    "misunderstood",
                    "i meant",
                )
            )
            db.execute(
                """INSERT INTO mao_hybrid.dialogue_focus(scope,room_id,actor_id,visibility,source_event,topic,repair,topic_event,quiet_event,quiet_until)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='quiet' THEN %s::uuid END,
                CASE WHEN %s='quiet' THEN now()+interval '10 minutes' END)
                ON CONFLICT(scope,room_id,actor_id,visibility) DO UPDATE SET
                source_event=excluded.source_event,topic=excluded.topic,topic_event=excluded.topic_event,question='',repair=excluded.repair,
                quiet_event=CASE WHEN %s='quiet' THEN excluded.quiet_event WHEN %s='resume' THEN NULL ELSE mao_hybrid.dialogue_focus.quiet_event END,
                quiet_until=CASE WHEN %s='quiet' THEN excluded.quiet_until WHEN %s='resume' THEN NULL ELSE mao_hybrid.dialogue_focus.quiet_until END,
                revision=mao_hybrid.dialogue_focus.revision+1,expires=now()+interval '10 minutes' """,
                (
                    self.scope,
                    source["room_id"],
                    source["actor_id"],
                    source["visibility"],
                    event_id,
                    topic,
                    repair,
                    topic_event,
                    control,
                    event_id,
                    control,
                    control,
                    control,
                    control,
                    control,
                ),
            )

    def delivered(self, event_id, text):
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            self.source(db, event_id)
            question = text[-300:].strip() if text.strip().endswith(("?", "？")) else ""
            db.execute(
                """UPDATE mao_hybrid.dialogue_focus SET question=%s,revision=revision+1,
                expires=now()+interval '10 minutes' WHERE scope=%s AND source_event=%s""",
                (question, self.scope, event_id),
            )

    def current(self, room, actor, visibility):
        with self.store.connect() as db:
            if not self.attention_available(db):
                return db.execute(
                    """SELECT f.topic,f.question,f.repair,f.revision,f.source_event FROM mao_hybrid.dialogue_focus f
                    JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.source_event
                    WHERE f.scope=%s AND f.room_id=%s AND f.actor_id=%s AND f.visibility=%s AND f.expires>now()
                    AND NOT e.deleted AND NOT e.raw_expired""",
                    (self.scope, room, actor, visibility),
                ).fetchone()
            return db.execute(
                """SELECT f.topic,f.question,f.repair,f.revision,f.source_event,f.topic_event,
                (f.quiet_until>now()) AS quiet FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.source_event
                JOIN mao_hybrid.interaction_events t ON t.scope=f.scope AND t.id=COALESCE(f.topic_event,f.source_event)
                WHERE f.scope=%s AND f.room_id=%s AND f.actor_id=%s AND f.visibility=%s AND f.expires>now()
                AND NOT e.deleted AND NOT e.raw_expired AND NOT t.deleted AND NOT t.raw_expired""",
                (self.scope, room, actor, visibility),
            ).fetchone()

    def room_quiet(self, room, visibility):
        # A private request controls the shared private audio floor. Public viewers
        # cannot mute a live room, and private requests never affect public output.
        if visibility not in {"private", "test"}:
            return False
        with self.store.connect() as db:
            if not self.attention_available(db):
                return False
            return bool(
                db.execute(
                    """SELECT 1 FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.quiet_event
                WHERE f.scope=%s AND f.room_id=%s AND f.visibility=%s AND f.quiet_until>now()
                AND NOT e.deleted AND NOT e.raw_expired LIMIT 1""",
                    (self.scope, room, visibility),
                ).fetchone()
            )

    def room_waiting(self, room):
        # Public LIVE questions invite a short listening pause. Their topic may
        # remain in focus for ten minutes without silencing the host that long.
        # Private conversations retain the full original waiting period.
        with self.store.connect() as db:
            return bool(
                db.execute(
                    """SELECT 1 FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.source_event
                WHERE f.scope=%s AND f.room_id=%s AND f.question!='' AND f.expires>now() AND NOT e.deleted
                AND (f.visibility!='public' OR f.expires-interval '10 minutes'>now()-interval '35 seconds') LIMIT 1""",
                    (self.scope, room),
                ).fetchone()
            )
