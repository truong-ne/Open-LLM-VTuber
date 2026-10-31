"""Short-lived conversational focus; silence creates no claims about the person."""

from ..experience.repository import Experiences
from ..character.appraisal import folded


class Focus(Experiences):
    def input(self, event_id, text):
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
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
                revision=mao_hybrid.dialogue_focus.revision+1,expires=now()+interval '10 minutes' """,
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
            return db.execute(
                """SELECT f.topic,f.question,f.repair,f.revision,f.source_event FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.source_event
                WHERE f.scope=%s AND f.room_id=%s AND f.actor_id=%s AND f.visibility=%s AND f.expires>now() AND NOT e.deleted""",
                (self.scope, room, actor, visibility),
            ).fetchone()

    def room_waiting(self, room):
        with self.store.connect() as db:
            return bool(
                db.execute(
                    """SELECT 1 FROM mao_hybrid.dialogue_focus f
                JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.source_event
                WHERE f.scope=%s AND f.room_id=%s AND f.question!='' AND f.expires>now() AND NOT e.deleted LIMIT 1""",
                    (self.scope, room),
                ).fetchone()
            )
