"""Durable fictional canon. Revision/expiry/idempotency precede every action."""

import uuid
from psycopg.types.json import Jsonb

from .repository import Experiences


class Activities(Experiences):
    def append_delivered(self, *args):
        # Delivery stays recorded even if the owner edited/forgot the story meanwhile.
        try:
            return self.apply(*args)
        except ValueError:
            return {"status": "not_committed"}

    def start(self, event_id):
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            existing = db.execute(
                """SELECT a.id,a.revision,a.status,a.canon FROM mao_hybrid.activities a
                JOIN mao_hybrid.interaction_events e ON e.scope=a.scope AND e.id=a.source_event
                WHERE a.scope=%s AND a.room_id=%s AND (a.actor_id=%s OR e.visibility='public') AND e.visibility=%s
                AND NOT e.deleted AND a.status IN ('accepted','running') AND a.expires>now() LIMIT 1""",
                (
                    self.scope,
                    source["room_id"],
                    source["actor_id"],
                    source["visibility"],
                ),
            ).fetchone()
            if existing:
                return {**existing, "id": str(existing["id"])}
            identifier = uuid.uuid4()
            db.execute(
                """INSERT INTO mao_hybrid.activities(scope,id,room_id,actor_id,source_event,kind)
                VALUES(%s,%s,%s,%s,%s,'shared_story')""",
                (
                    self.scope,
                    identifier,
                    source["room_id"],
                    source["actor_id"],
                    event_id,
                ),
            )
            db.execute(
                "INSERT INTO mao_hybrid.activity_evidence(scope,activity_id,event_id) VALUES(%s,%s,%s)",
                (self.scope, identifier, event_id),
            )
            return {
                "id": str(identifier),
                "revision": 1,
                "status": "accepted",
                "canon": [],
            }

    def apply(
        self, activity_id, event_id, action_id, expected_revision, text, complete=False
    ):
        if (
            not isinstance(text, str)
            or not 0 < len(text) <= 2000
            or type(complete) is not bool
        ):
            raise ValueError("Invalid story action")
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            row = db.execute(
                """SELECT a.*,a.expires>now() AS live FROM mao_hybrid.activities a
                JOIN mao_hybrid.interaction_events e ON e.scope=a.scope AND e.id=a.source_event
                WHERE a.scope=%s AND a.id=%s AND (a.actor_id=%s OR e.visibility='public') AND a.room_id=%s
                AND e.visibility=%s AND NOT e.deleted FOR UPDATE OF a""",
                (
                    self.scope,
                    activity_id,
                    source["actor_id"],
                    source["room_id"],
                    source["visibility"],
                ),
            ).fetchone()
            if not row:
                raise ValueError("Activity unavailable in this room/actor scope")
            duplicate = db.execute(
                "SELECT result FROM mao_hybrid.activity_actions WHERE scope=%s AND activity_id=%s AND action_id=%s",
                (self.scope, activity_id, action_id),
            ).fetchone()
            if duplicate:
                return duplicate["result"]
            if (
                not row["live"]
                or row["status"] not in {"accepted", "running"}
                or row["revision"] != expected_revision
            ):
                raise ValueError(
                    "Activity expired, finished or changed; reload before acting"
                )
            if len(row["canon"]) >= 64:
                raise ValueError("Story limit reached; finish this activity")
            canon = row["canon"] + [
                {"kind": "fiction", "text": text, "event_id": str(event_id)}
            ]
            result = {
                "id": str(activity_id),
                "revision": row["revision"] + 1,
                "status": "completed" if complete else "running",
                "canon": canon,
            }
            db.execute(
                "UPDATE mao_hybrid.activities SET revision=%s,status=%s,canon=%s WHERE scope=%s AND id=%s",
                (
                    result["revision"],
                    result["status"],
                    Jsonb(canon),
                    self.scope,
                    activity_id,
                ),
            )
            db.execute(
                "INSERT INTO mao_hybrid.activity_actions(scope,activity_id,action_id,result) VALUES(%s,%s,%s,%s)",
                (self.scope, activity_id, action_id, Jsonb(result)),
            )
            db.execute(
                "INSERT INTO mao_hybrid.activity_evidence(scope,activity_id,event_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (self.scope, activity_id, event_id),
            )
            return result

    def context(self, room, actor, visibility="private"):
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT a.id,a.revision,a.status,a.canon FROM mao_hybrid.activities a
                JOIN mao_hybrid.interaction_events e ON e.scope=a.scope AND e.id=a.source_event
                WHERE a.scope=%s AND a.room_id=%s AND (a.actor_id=%s OR e.visibility='public') AND e.visibility=%s
                AND NOT e.deleted AND a.expires>now() ORDER BY a.expires DESC LIMIT 1""",
                (self.scope, room, actor, visibility),
            ).fetchall()
        return [
            {
                **row,
                "id": str(row["id"]),
                "canon": [
                    dict(item, text=item["text"][:600]) for item in row["canon"][-6:]
                ],
                "fiction": True,
            }
            for row in rows
        ]
