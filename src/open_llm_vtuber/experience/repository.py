import re
import uuid


class Experiences:
    def __init__(self, store):
        self.store, self.scope = store, store.scope

    def lock(self, db, room):
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("experience:" + self.scope + ":" + room,),
        )

    def source(self, db, event_id, include_deleted=False):
        row = db.execute(
            "SELECT * FROM mao_hybrid.interaction_events WHERE scope=%s AND id=%s",
            (self.scope, event_id),
        ).fetchone()
        if not row or (row["deleted"] and not include_deleted):
            raise ValueError("Source was deleted or is unavailable")
        return row

    def add_item(
        self, event_id, content, claim_type="user_claim", item_key=None, temporary=False
    ):
        if (
            claim_type
            not in {
                "user_claim",
                "user_preference",
                "fiction",
                "shared_memory",
                "lesson_candidate",
            }
            or not isinstance(content, str)
            or not 0 < len(content) <= 4000
        ):
            raise ValueError("Invalid knowledge item")
        if item_key is not None and (
            not isinstance(item_key, str) or len(item_key) > 100
        ):
            raise ValueError("Invalid knowledge key")
        vector = self.store._vector(content)
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            if claim_type in {"user_claim", "user_preference"} and source[
                "kind"
            ] not in {"input", "operator_correction"}:
                raise ValueError("Host proposals are not user claims")
            if claim_type in {"user_claim", "user_preference"} and content not in (
                source["content"] or ""
            ):
                raise ValueError("User claims require an exact source excerpt")
            if source["synthetic"] and source["visibility"] != "test":
                raise ValueError("Synthetic source outside test scope")
            duplicate = db.execute(
                """SELECT k.id FROM mao_hybrid.knowledge_items k JOIN mao_hybrid.memory_evidence e
                ON e.scope=k.scope AND e.item_id=k.id WHERE k.scope=%s AND e.event_id=%s AND k.content=%s AND k.claim_type=%s""",
                (self.scope, event_id, content, claim_type),
            ).fetchone()
            if duplicate:
                return duplicate["id"]
            if item_key:
                db.execute(
                    """UPDATE mao_hybrid.knowledge_items SET status='superseded',revision=revision+1
                    WHERE scope=%s AND room_id=%s AND actor_id=%s AND visibility=%s AND item_key=%s AND status='active' """,
                    (
                        self.scope,
                        source["room_id"],
                        source["actor_id"],
                        source["visibility"],
                        item_key,
                    ),
                )
            row = db.execute(
                """INSERT INTO mao_hybrid.knowledge_items
                (scope,room_id,actor_id,visibility,claim_type,item_key,content,embedding,embedding_model,valid_until)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,now()+(%s * interval '1 day')) RETURNING id""",
                (
                    self.scope,
                    source["room_id"],
                    source["actor_id"],
                    source["visibility"],
                    claim_type,
                    item_key,
                    content,
                    vector,
                    self.store.embedding_profile,
                    1 if temporary else self.store.config.retention_days,
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO mao_hybrid.memory_evidence(scope,item_id,event_id) VALUES(%s,%s,%s)",
                (self.scope, row["id"], event_id),
            )
            db.execute(
                "UPDATE mao_hybrid.rooms SET revision=revision+1 WHERE scope=%s AND id=%s",
                (self.scope, source["room_id"]),
            )
            return row["id"]

    def context(self, room, actor, visibility, query="", limit=8):
        with self.store.connect() as db:
            has_items = db.execute(
                """SELECT 1 FROM mao_hybrid.knowledge_items WHERE scope=%s AND room_id=%s AND status='active'
                AND (valid_until IS NULL OR valid_until>now()) AND (actor_id=%s AND visibility=%s OR visibility='public' AND %s!='test') LIMIT 1""",
                (self.scope, room, actor, visibility, visibility),
            ).fetchone()
        vector = (
            self.store._vector(query[:2000], query=True)
            if query.strip() and has_items
            else None
        )
        with self.store.connect() as db:
            revision = db.execute(
                "SELECT revision FROM mao_hybrid.rooms WHERE scope=%s AND id=%s",
                (self.scope, room),
            ).fetchone()
            items = db.execute(
                """SELECT k.id,k.content,k.claim_type,k.item_key,k.revision,k.valid_from,k.valid_until,k.actor_id,k.room_id,k.visibility,
                array_agg(e.event_id::text) AS evidence FROM mao_hybrid.knowledge_items k
                JOIN mao_hybrid.memory_evidence e ON e.scope=k.scope AND e.item_id=k.id
                JOIN mao_hybrid.interaction_events s ON s.scope=e.scope AND s.id=e.event_id
                WHERE k.scope=%s AND k.room_id=%s AND k.status='active' AND k.claim_type!='fiction' AND NOT s.deleted
                AND (k.valid_until IS NULL OR k.valid_until>now())
                AND ((k.visibility='public' AND %s!='test') OR (k.visibility=%s AND k.actor_id=%s))
                AND (k.claim_type!='user_preference' OR k.actor_id=%s)
                GROUP BY k.scope,k.id ORDER BY
                CASE WHEN k.item_key='preference:address' AND k.actor_id=%s THEN -1
                WHEN %s::vector IS NULL THEN 0 ELSE COALESCE(k.embedding <=> %s::vector,1.0) END,
                k.created DESC LIMIT 64""",
                (
                    self.scope,
                    room,
                    visibility,
                    visibility,
                    actor,
                    actor,
                    actor,
                    vector,
                    vector,
                ),
            ).fetchall()
            threads = (
                db.execute(
                    """SELECT id,topic,revision FROM mao_hybrid.open_threads
                WHERE scope=%s AND room_id=%s AND actor_id=%s AND status='open' AND expires>now()
                ORDER BY expires LIMIT 4""",
                    (self.scope, room, actor),
                ).fetchall()
                if visibility != "public"
                else []
            )
            recent = db.execute(
                """SELECT e.id::text AS event_id,e.content AS user_claim,t.status AS delivery_status,
                extract(epoch from e.recorded_at)::float8 AS observed_at,
                string_agg(d.content,' ' ORDER BY d.ordinal,d.id) AS delivered_response
                FROM mao_hybrid.turns t JOIN mao_hybrid.interaction_events e ON e.scope=t.scope AND e.id=t.event_id
                JOIN mao_hybrid.delivery_segments d ON d.scope=t.scope AND d.turn_id=t.id
                WHERE t.scope=%s AND e.room_id=%s AND e.actor_id=%s AND e.visibility=%s
                AND t.status IN ('completed','interrupted','unknown','failed') AND NOT e.deleted AND d.status='completed'
                AND NOT e.synthetic AND NOT e.raw_expired
                GROUP BY t.scope,t.id,e.id,e.content,e.recorded_at ORDER BY t.created DESC LIMIT 4""",
                (self.scope, room, actor, visibility),
            ).fetchall()
        terms = set(re.findall(r"\w+", query.casefold()))
        if terms:
            items.sort(
                key=lambda item: (
                    item["item_key"] == "preference:address"
                    and item["actor_id"] == actor,
                    len(terms & set(re.findall(r"\w+", item["content"].casefold()))),
                ),
                reverse=True,
            )
        safe = [
            {
                **item,
                "valid_from": str(item["valid_from"]),
                "valid_until": str(item["valid_until"]),
                "verified": False,
            }
            for item in items[: max(1, min(16, limit))]
        ]
        return {
            "speaker": {"actor_id": actor, "room_id": room, "visibility": visibility},
            "revision": revision["revision"] if revision else 0,
            "items": safe,
            "open_threads": [{**row, "id": str(row["id"])} for row in threads],
            "delivered_turns": recent,
        }

    def forget_item(self, item_id, room, actor, visibility):
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT e.event_id FROM mao_hybrid.memory_evidence e
                JOIN mao_hybrid.knowledge_items k ON k.scope=e.scope AND k.id=e.item_id
                WHERE k.scope=%s AND k.id=%s AND k.room_id=%s AND k.actor_id=%s AND k.visibility=%s""",
                (self.scope, item_id, room, actor, visibility),
            ).fetchall()
        if not rows:
            raise PermissionError("Memory is not owned by the current actor and scope")
        for row in rows:
            self.forget_source(row["event_id"])

    def boundaries(self, room, actor, visibility):
        from .claims import lasting_boundary

        with self.store.connect() as db:
            rows = db.execute(
                """SELECT k.content FROM mao_hybrid.knowledge_items k
                JOIN mao_hybrid.memory_evidence p ON p.scope=k.scope AND p.item_id=k.id
                JOIN mao_hybrid.interaction_events e ON e.scope=p.scope AND e.id=p.event_id
                WHERE k.scope=%s AND k.room_id=%s AND k.actor_id=%s AND k.visibility=%s
                AND k.item_key='boundary:humor' AND k.status='active' AND NOT e.deleted
                AND (k.valid_until IS NULL OR k.valid_until>now()) ORDER BY k.created DESC LIMIT 1""",
                (self.scope, room, actor, visibility),
            ).fetchall()
        value = lasting_boundary(rows[0]["content"]) if rows else None
        return {"humor": value} if value else {}

    def revise_item(self, item_id, revision, content):
        if not isinstance(content, str) or not 0 < len(content) <= 4000:
            raise ValueError("Invalid content")
        vector = self.store._vector(content)
        with self.store.connect() as db:
            old = db.execute(
                "SELECT * FROM mao_hybrid.knowledge_items WHERE scope=%s AND id=%s",
                (self.scope, item_id),
            ).fetchone()
            if not old:
                raise ValueError("Knowledge item unavailable")
            self.lock(db, old["room_id"])
            old = db.execute(
                "SELECT * FROM mao_hybrid.knowledge_items WHERE scope=%s AND id=%s AND revision=%s AND status='active' FOR UPDATE",
                (self.scope, item_id, revision),
            ).fetchone()
            if not old:
                raise ValueError("Knowledge changed; reload before editing")
            event = uuid.uuid4()
            db.execute(
                """INSERT INTO mao_hybrid.interaction_events(scope,id,room_id,actor_id,session_id,kind,visibility,content)
                VALUES(%s,%s,%s,%s,'operator','operator_correction',%s,%s)""",
                (
                    self.scope,
                    event,
                    old["room_id"],
                    old["actor_id"],
                    old["visibility"],
                    content,
                ),
            )
            new = db.execute(
                """INSERT INTO mao_hybrid.knowledge_items(scope,room_id,actor_id,claim_type,visibility,item_key,content,embedding,embedding_model,valid_until)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::vector,%s,now()+interval '180 days') RETURNING id""",
                (
                    self.scope,
                    old["room_id"],
                    old["actor_id"],
                    old["claim_type"],
                    old["visibility"],
                    old["item_key"],
                    content,
                    vector,
                    self.store.embedding_profile,
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO mao_hybrid.memory_evidence(scope,item_id,event_id) VALUES(%s,%s,%s)",
                (self.scope, new["id"], event),
            )
            db.execute(
                """INSERT INTO mao_hybrid.memory_evidence(scope,item_id,event_id)
                SELECT scope,%s,event_id FROM mao_hybrid.memory_evidence WHERE scope=%s AND item_id=%s
                ON CONFLICT DO NOTHING""",
                (new["id"], self.scope, item_id),
            )
            db.execute(
                "UPDATE mao_hybrid.knowledge_items SET status='superseded',revision=revision+1 WHERE scope=%s AND id=%s",
                (self.scope, item_id),
            )
            db.execute(
                "UPDATE mao_hybrid.rooms SET revision=revision+1 WHERE scope=%s AND id=%s",
                (self.scope, old["room_id"]),
            )
            return new["id"]

    def open_thread(self, event_id, topic):
        if not isinstance(topic, str) or not 0 < len(topic) <= 500:
            raise ValueError("Invalid open thread")
        with self.store.connect() as db:
            source = self.source(db, event_id)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            db.execute(
                """INSERT INTO mao_hybrid.open_threads(scope,id,room_id,actor_id,event_id,topic)
                VALUES(%s,%s,%s,%s,%s,%s)""",
                (
                    self.scope,
                    uuid.uuid4(),
                    source["room_id"],
                    source["actor_id"],
                    event_id,
                    topic,
                ),
            )

    def acknowledge_threads(self, room, actor):
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.open_threads SET status='closed',revision=revision+1 WHERE scope=%s AND room_id=%s AND actor_id=%s",
                (self.scope, room, actor),
            )

    def process_outbox(self, limit=50):
        processed = 0
        for _ in range(min(100, limit)):
            with self.store.connect() as db:
                candidate = db.execute(
                    """SELECT e.room_id,o.event_id FROM mao_hybrid.interaction_outbox o
                    JOIN mao_hybrid.interaction_events e ON e.scope=o.scope AND e.id=o.event_id
                    JOIN mao_hybrid.turns t ON t.scope=e.scope AND t.event_id=e.id
                    WHERE o.scope=%s AND o.status='pending' AND t.status NOT IN ('accepted','running') ORDER BY o.updated LIMIT 1""",
                    (self.scope,),
                ).fetchone()
                if not candidate:
                    break
                self.lock(db, candidate["room_id"])
                row = db.execute(
                    """SELECT o.event_id,e.room_id,e.actor_id,e.session_id,e.visibility,e.content,e.deleted,e.synthetic,t.status
                    FROM mao_hybrid.interaction_outbox o JOIN mao_hybrid.interaction_events e ON e.scope=o.scope AND e.id=o.event_id
                    JOIN mao_hybrid.turns t ON t.scope=e.scope AND t.event_id=e.id
                    WHERE o.scope=%s AND o.event_id=%s AND o.status='pending' AND t.status NOT IN ('accepted','running')
                    ORDER BY o.updated FOR UPDATE OF o SKIP LOCKED LIMIT 1""",
                    (self.scope, candidate["event_id"]),
                ).fetchone()
                if not row:
                    break
                if not row["deleted"] and row["content"]:
                    self.lock(db, row["room_id"])
                    # Lock the source too: deletion and consolidation cannot race.
                    source = self.source(db, row["event_id"])
                    existing = db.execute(
                        """SELECT id FROM mao_hybrid.episodes WHERE scope=%s AND room_id=%s AND actor_id=%s
                        AND visibility=%s AND session_id=%s AND updated>now()-interval '10 minutes' ORDER BY updated DESC LIMIT 1""",
                        (
                            self.scope,
                            row["room_id"],
                            row["actor_id"],
                            row["visibility"],
                            row["session_id"],
                        ),
                    ).fetchone()
                    identifier = existing["id"] if existing else uuid.uuid4()
                    topic = source["content"][:120]
                    db.execute(
                        """INSERT INTO mao_hybrid.episodes(scope,id,room_id,actor_id,visibility,session_id,topic,outcome)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(scope,id) DO UPDATE SET updated=now(),outcome=excluded.outcome""",
                        (
                            self.scope,
                            identifier,
                            row["room_id"],
                            row["actor_id"],
                            row["visibility"],
                            row["session_id"],
                            topic,
                            "unknown",
                        ),
                    )
                    db.execute(
                        "INSERT INTO mao_hybrid.episode_events(scope,episode_id,event_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                        (self.scope, identifier, row["event_id"]),
                    )
                db.execute(
                    "UPDATE mao_hybrid.interaction_outbox SET status='processed',attempts=attempts+1,updated=now() WHERE scope=%s AND event_id=%s",
                    (self.scope, row["event_id"]),
                )
                processed += 1
        return processed

    def forget_source(self, event_id):
        with self.store.connect() as db:
            source = self.source(db, event_id, include_deleted=True)
            self.lock(db, source["room_id"])
            source = self.source(db, event_id, include_deleted=True)
            if source["deleted"]:
                return
            from ..character.affect_scope import affect_key

            # Conservative invalidation: no transcript is retained in affect, but
            # its numbers may have been derived from the forgotten source.
            db.execute(
                "DELETE FROM mao_hybrid.state WHERE scope=%s AND key=%s",
                (
                    self.scope,
                    affect_key(
                        room=source["room_id"],
                        actor=source["actor_id"],
                        visibility=source["visibility"],
                    ),
                ),
            )
            db.execute(
                "DELETE FROM mao_hybrid.dialogue_focus WHERE scope=%s AND source_event=%s",
                (self.scope, event_id),
            )
            # Conservative invalidation removes any derivation that used this source.
            db.execute(
                "UPDATE mao_hybrid.policy_versions SET status='retired' WHERE scope=%s AND status IN ('active','trial') AND preference_id IN (SELECT id FROM mao_hybrid.character_preferences WHERE scope=%s AND room_id=%s AND actor_id=%s)",
                (self.scope, self.scope, source["room_id"], source["actor_id"]),
            )
            db.execute(
                """DELETE FROM mao_hybrid.character_preferences p WHERE p.scope=%s AND EXISTS
                (SELECT 1 FROM mao_hybrid.preference_evidence e WHERE e.scope=p.scope AND e.preference_id=p.id AND (e.event_id=%s OR e.feedback_event_id=%s))""",
                (self.scope, event_id, event_id),
            )
            db.execute(
                """DELETE FROM mao_hybrid.evaluation_runs e USING mao_hybrid.policy_versions v,mao_hybrid.character_preferences p
                WHERE e.scope=v.scope AND e.policy_revision=v.revision AND p.scope=v.scope AND p.id=v.preference_id
                AND e.scope=%s AND p.room_id=%s AND p.actor_id=%s AND e.split='real_trial'""",
                (self.scope, source["room_id"], source["actor_id"]),
            )
            db.execute(
                "DELETE FROM mao_hybrid.real_feedback WHERE scope=%s AND (event_id=%s OR target_event=%s)",
                (self.scope, event_id, event_id),
            )
            db.execute(
                "DELETE FROM mao_hybrid.lessons WHERE scope=%s AND event_id=%s",
                (self.scope, event_id),
            )
            db.execute(
                """DELETE FROM mao_hybrid.knowledge_items k WHERE k.scope=%s AND EXISTS
                (SELECT 1 FROM mao_hybrid.memory_evidence e WHERE e.scope=k.scope AND e.item_id=k.id AND e.event_id=%s)""",
                (self.scope, event_id),
            )
            db.execute(
                """DELETE FROM mao_hybrid.episodes p WHERE p.scope=%s AND EXISTS
                (SELECT 1 FROM mao_hybrid.episode_events e WHERE e.scope=p.scope AND e.episode_id=p.id AND e.event_id=%s)""",
                (self.scope, event_id),
            )
            db.execute(
                "DELETE FROM mao_hybrid.open_threads WHERE scope=%s AND event_id=%s",
                (self.scope, event_id),
            )
            db.execute(
                """DELETE FROM mao_hybrid.activities a WHERE a.scope=%s AND (a.source_event=%s OR EXISTS
                (SELECT 1 FROM mao_hybrid.activity_evidence e WHERE e.scope=a.scope AND e.activity_id=a.id AND e.event_id=%s))""",
                (self.scope, event_id, event_id),
            )
            db.execute(
                """UPDATE mao_hybrid.delivery_segments d SET content=NULL FROM mao_hybrid.turns t
                WHERE d.scope=t.scope AND d.turn_id=t.id AND t.scope=%s AND t.event_id=%s""",
                (self.scope, event_id),
            )
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET content=NULL,deleted=true WHERE scope=%s AND id=%s",
                (self.scope, event_id),
            )
            db.execute(
                "UPDATE mao_hybrid.interaction_outbox SET status='processed' WHERE scope=%s AND event_id=%s",
                (self.scope, event_id),
            )
            db.execute(
                "UPDATE mao_hybrid.rooms SET revision=revision+1 WHERE scope=%s AND id=%s",
                (self.scope, source["room_id"]),
            )

    def retain(self, raw_days=30, diagnostics_days=7):
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT id FROM mao_hybrid.interaction_events WHERE scope=%s AND NOT deleted AND NOT raw_expired
                AND recorded_at<now()-(%s * interval '1 day') LIMIT 100""",
                (self.scope, max(1, raw_days)),
            ).fetchall()
        for row in rows:
            with self.store.connect() as db:
                source = self.source(db, row["id"])
                self.lock(db, source["room_id"])
                db.execute(
                    "UPDATE mao_hybrid.interaction_events SET content=NULL,raw_expired=true WHERE scope=%s AND id=%s",
                    (self.scope, row["id"]),
                )
                db.execute(
                    """UPDATE mao_hybrid.delivery_segments d SET content=NULL FROM mao_hybrid.turns t
                    WHERE d.scope=t.scope AND d.turn_id=t.id AND t.scope=%s AND t.event_id=%s""",
                    (self.scope, row["id"]),
                )
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.turns SET metrics='{}' WHERE scope=%s AND created<now()-(%s * interval '1 day')",
                (self.scope, max(1, diagnostics_days)),
            )
            db.execute(
                "DELETE FROM mao_hybrid.open_threads WHERE scope=%s AND expires<now()",
                (self.scope,),
            )
            db.execute(
                "DELETE FROM mao_hybrid.dialogue_focus WHERE scope=%s AND expires<now()",
                (self.scope,),
            )
            db.execute(
                "UPDATE mao_hybrid.activities SET status='unknown' WHERE scope=%s AND expires<now() AND status IN ('accepted','running')",
                (self.scope,),
            )
            db.execute(
                "DELETE FROM mao_hybrid.knowledge_items WHERE scope=%s AND valid_until<now()",
                (self.scope,),
            )
            # Invalidate cached context whenever retention may remove a source record.
            db.execute(
                "UPDATE mao_hybrid.rooms SET revision=revision+1 WHERE scope=%s",
                (self.scope,),
            )
            db.execute(
                "DELETE FROM mao_hybrid.activities WHERE scope=%s AND expires<now()-interval '23 days'",
                (self.scope,),
            )
            db.execute(
                "DELETE FROM mao_hybrid.episodes WHERE scope=%s AND updated<now()-interval '90 days'",
                (self.scope,),
            )
            db.execute(
                """UPDATE mao_hybrid.policy_versions v SET status='retired' WHERE v.scope=%s AND v.status IN ('active','trial') AND
                (SELECT count(*) FROM mao_hybrid.preference_evidence e WHERE e.scope=v.scope AND e.preference_id=v.preference_id)<3""",
                (self.scope,),
            )
        return len(rows)
