"""Transactional journal. An outbox entry can never exist without its source."""

from psycopg.types.json import Jsonb


class Journal:
    def acquire_lease(self):
        import psycopg
        from ..agent.hybrid.store import resolve_dsn

        connection = psycopg.connect(resolve_dsn(self.store.config), autocommit=True)
        try:
            acquired = connection.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s,0))",
                ("runtime:" + self.scope,),
            ).fetchone()[0]
            if not acquired:
                raise RuntimeError("Another backend already owns this runtime scope")
            return connection
        except BaseException:
            connection.close()
            raise

    def __init__(self, store):
        self.store, self.scope = store, store.scope

    def accept(self, event, delivery, running=True):
        if event.synthetic and event.visibility != "test":
            raise ValueError("Synthetic events require test visibility")
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO mao_hybrid.rooms(scope,id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (self.scope, event.room_id),
            )
            db.execute(
                "INSERT INTO mao_hybrid.actors(scope,id,provider) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (self.scope, event.actor_id, event.provider),
            )
            row = db.execute(
                """INSERT INTO mao_hybrid.interaction_events
                (scope,id,room_id,actor_id,session_id,kind,visibility,source_key,content,synthetic)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING RETURNING id""",
                (
                    self.scope,
                    event.event_id,
                    event.room_id,
                    event.actor_id,
                    event.session_id,
                    event.kind,
                    event.visibility,
                    event.source_key,
                    event.content,
                    event.synthetic,
                ),
            ).fetchone()
            if not row:
                return False
            db.execute(
                """INSERT INTO mao_hybrid.turns(scope,id,event_id,room_id,actor_id,epoch,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.scope,
                    delivery.turn_id,
                    event.event_id,
                    event.room_id,
                    event.actor_id,
                    delivery.epoch,
                    "running" if running else "accepted",
                ),
            )
            db.execute(
                "INSERT INTO mao_hybrid.interaction_outbox(scope,event_id) VALUES(%s,%s)",
                (self.scope, event.event_id),
            )
        return True

    def start(self, delivery):
        with self.store.connect() as db:
            row = db.execute(
                "UPDATE mao_hybrid.turns SET status='running',updated=now() WHERE scope=%s AND id=%s AND status='accepted' RETURNING id",
                (self.scope, delivery.turn_id),
            ).fetchone()
        return bool(row)

    def touch(self, delivery):
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.turns SET updated=now() WHERE scope=%s AND id=%s AND status='running'",
                (self.scope, delivery.turn_id),
            )

    def transcribed(self, event, content):
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET content=%s WHERE scope=%s AND id=%s AND NOT deleted",
                (content[:16000], self.scope, event.event_id),
            )

    def finish(
        self,
        event,
        delivery,
        persona_revision=None,
        policy_revision=0,
        policy_settings=None,
    ):
        metrics = {
            key: value
            for key, value in delivery.metrics.items()
            if key
            in {
                "duration_ms",
                "first_audio_ms",
                "asr_ms",
                "first_token_ms",
                "errors",
                "cancelled",
            }
        }
        with self.store.connect() as db:
            for ordinal, segment in enumerate(delivery.segments.values()):
                db.execute(
                    """INSERT INTO mao_hybrid.delivery_segments(scope,turn_id,epoch,id,content,status,ordinal)
                    SELECT %s,%s,%s,%s,CASE WHEN e.deleted THEN NULL ELSE %s END,%s,%s
                    FROM mao_hybrid.interaction_events e WHERE e.scope=%s AND e.id=%s
                    ON CONFLICT(scope,turn_id,id) DO UPDATE SET status=excluded.status,content=excluded.content,ordinal=excluded.ordinal""",
                    (
                        self.scope,
                        delivery.turn_id,
                        delivery.epoch,
                        segment["id"],
                        segment["content"],
                        segment["status"],
                        ordinal,
                        self.scope,
                        event.event_id,
                    ),
                )
            db.execute(
                """UPDATE mao_hybrid.turns SET status=%s,metrics=%s,persona_revision=%s,
                policy_revision=%s,policy_settings=%s,modality=%s,phase=%s,updated=now() WHERE scope=%s AND id=%s AND epoch=%s AND status IN ('accepted','running') """,
                (
                    delivery.state,
                    Jsonb(metrics),
                    persona_revision,
                    policy_revision,
                    Jsonb(policy_settings or {}),
                    delivery.modality,
                    delivery.phase,
                    self.scope,
                    delivery.turn_id,
                    delivery.epoch,
                ),
            )

    def recover(self, force=False):
        # Never replay audio or actions from a previous process.
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.turns SET status='unknown',updated=now() WHERE scope=%s AND status IN ('accepted','running') AND (%s OR updated<now()-interval '10 minutes')",
                (self.scope, force),
            )

    def snapshot(self):
        with self.store.connect() as db:
            turns = db.execute(
                """SELECT status,count(*) AS count FROM mao_hybrid.turns
                WHERE scope=%s AND created>now()-interval '1 day' GROUP BY status""",
                (self.scope,),
            ).fetchall()
            latency = db.execute(
                """SELECT count(*) AS samples,
                percentile_cont(.5) WITHIN GROUP(ORDER BY (metrics->>'duration_ms')::float8) AS p50_ms,
                percentile_cont(.95) WITHIN GROUP(ORDER BY (metrics->>'duration_ms')::float8) AS p95_ms
                FROM mao_hybrid.turns WHERE scope=%s AND created>now()-interval '1 day'
                AND metrics ? 'duration_ms' """,
                (self.scope,),
            ).fetchone()
            outbox = db.execute(
                "SELECT count(*) AS pending FROM mao_hybrid.interaction_outbox WHERE scope=%s AND status!='processed'",
                (self.scope,),
            ).fetchone()
            by_modality = db.execute(
                """SELECT modality,phase,count(*) AS samples,
                percentile_cont(.5) WITHIN GROUP(ORDER BY (metrics->>'duration_ms')::float8) AS p50_ms,
                percentile_cont(.95) WITHIN GROUP(ORDER BY (metrics->>'duration_ms')::float8) AS p95_ms
                FROM mao_hybrid.turns WHERE scope=%s AND metrics ? 'duration_ms' AND status!='rejected'
                AND created>now()-interval '1 day' GROUP BY modality,phase""",
                (self.scope,),
            ).fetchall()
        return {
            "turns": turns,
            "latency": latency,
            "latency_by_modality": by_modality,
            "outbox": outbox,
        }
