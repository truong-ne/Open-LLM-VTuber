"""Operator surfaces: bounded inspection, source edits/deletion, policy lifecycle."""

import json
import uuid

from .character.development import Development
from .experience.repository import Experiences
from .interaction.repository import Journal
from .experience.activities import Activities


def safe(value):
    return json.loads(json.dumps(value, default=str))


class Operations:
    def __init__(self, store):
        self.store = store
        self.repo = Experiences(store)
        self.development = Development(store)

    def state(self):
        scope = self.store.scope
        with self.store.connect() as db:
            events = db.execute(
                """SELECT id,room_id,actor_id,kind,visibility,deleted,recorded_at,
                left(content,160) AS preview FROM mao_hybrid.interaction_events WHERE scope=%s ORDER BY recorded_at DESC LIMIT 50""",
                (scope,),
            ).fetchall()
            items = db.execute(
                """SELECT k.id,k.claim_type,k.content,k.status,k.revision,k.actor_id,k.visibility,
                array_agg(e.event_id::text) AS evidence FROM mao_hybrid.knowledge_items k
                JOIN mao_hybrid.memory_evidence e ON e.scope=k.scope AND e.item_id=k.id
                WHERE k.scope=%s GROUP BY k.scope,k.id ORDER BY k.created DESC LIMIT 50""",
                (scope,),
            ).fetchall()
            preferences = db.execute(
                """SELECT p.*,coalesce(jsonb_agg(jsonb_build_object('event',e.event_id,'feedback',e.feedback_event_id,'supports',e.supports))
                FILTER(WHERE e.event_id IS NOT NULL),'[]') AS evidence FROM mao_hybrid.character_preferences p
                LEFT JOIN mao_hybrid.preference_evidence e ON e.scope=p.scope AND e.preference_id=p.id
                WHERE p.scope=%s GROUP BY p.scope,p.id ORDER BY p.created DESC LIMIT 40""",
                (scope,),
            ).fetchall()
            policies = db.execute(
                """SELECT v.*,coalesce(jsonb_agg(jsonb_build_object('split',e.split,'samples',e.samples,
                'baseline',e.baseline_score,'candidate',e.candidate_score,'hard_failures',e.hard_failures))
                FILTER(WHERE e.id IS NOT NULL),'[]') AS evaluations FROM mao_hybrid.policy_versions v
                LEFT JOIN mao_hybrid.evaluation_runs e ON e.scope=v.scope AND e.policy_revision=v.revision
                WHERE v.scope=%s GROUP BY v.scope,v.revision ORDER BY v.revision DESC LIMIT 30""",
                (scope,),
            ).fetchall()
            activities = db.execute(
                "SELECT id,room_id,actor_id,status,revision,canon,expires FROM mao_hybrid.activities WHERE scope=%s ORDER BY expires DESC LIMIT 10",
                (scope,),
            ).fetchall()
            focus_rows = db.execute(
                """SELECT topic,question,repair,revision,source_event,actor_id,visibility
                FROM mao_hybrid.dialogue_focus WHERE scope=%s AND expires>now() ORDER BY expires DESC LIMIT 20""",
                (scope,),
            ).fetchall()
            counts = db.execute(
                """SELECT (SELECT count(*) FROM mao_hybrid.interaction_events WHERE scope=%s) AS events,
                (SELECT count(*) FROM mao_hybrid.episodes WHERE scope=%s) AS episodes,
                (SELECT count(*) FROM mao_hybrid.knowledge_items WHERE scope=%s) AS memories,
                pg_database_size(current_database()) AS database_bytes""",
                (scope, scope, scope),
            ).fetchone()
        config = self.store.config
        return safe(
            {
                "schema_version": 1,
                "scope": self.store.scope,
                "flags": {
                    "interaction": config.interaction_enabled,
                    "coordinator": config.coordinator_enabled,
                    "shadow": config.coordinator_shadow,
                    "emotion": config.emotion_enabled,
                    "auto_promotion": config.auto_policy_promotion,
                },
                "health": Journal(self.store).snapshot(),
                "worker": self.store.get("runtime_worker_status", {}),
                "counts": counts,
                "events": events,
                "items": items,
                "preferences": preferences,
                "policies": policies,
                "activities": activities,
                "focus": focus_rows,
            }
        )

    def source(self, identifier):
        identifier = uuid.UUID(str(identifier))
        with self.store.connect() as db:
            source = db.execute(
                "SELECT id,room_id,actor_id,session_id,kind,visibility,content,deleted,raw_expired,recorded_at FROM mao_hybrid.interaction_events WHERE scope=%s AND id=%s",
                (self.store.scope, identifier),
            ).fetchone()
            delivery = db.execute(
                """SELECT t.id,t.status,t.persona_revision,t.policy_revision,t.metrics,
                coalesce(jsonb_agg(jsonb_build_object('id',s.id,'status',s.status,'text',s.content,'ordinal',s.ordinal) ORDER BY s.ordinal) FILTER(WHERE s.id IS NOT NULL),'[]') AS segments
                FROM mao_hybrid.turns t LEFT JOIN mao_hybrid.delivery_segments s ON s.scope=t.scope AND s.turn_id=t.id
                WHERE t.scope=%s AND t.event_id=%s GROUP BY t.scope,t.id""",
                (self.store.scope, identifier),
            ).fetchall()
        if not source:
            raise ValueError("Source unavailable")
        return safe({"source": source, "delivery": delivery})

    def action(self, body):
        if not isinstance(body, dict) or len(json.dumps(body)) > 65536:
            raise ValueError("Invalid operator action")
        operation = body.get("operation")
        if operation == "forget_source":
            self.repo.forget_source(uuid.UUID(body["id"]))
        elif operation == "edit_item":
            return {
                "id": self.repo.revise_item(
                    int(body["id"]), int(body["revision"]), body["content"]
                )
            }
        elif operation in {"lock_preference", "retire_preference"}:
            self.development.lock_preference(
                uuid.UUID(body["id"]), operation == "retire_preference"
            )
        elif operation == "propose":
            return {"revision": self.development.propose(uuid.UUID(body["id"]))}
        elif operation == "trial":
            self.development.trial(int(body["revision"]), int(body.get("budget", 20)))
        elif operation == "promote":
            self.development.real_trial(int(body["revision"]))
            self.development.promote(int(body["revision"]))
        elif operation == "rollback":
            self.development.rollback(int(body["revision"]))
        elif operation == "evaluate":
            from .learning.evaluation import evaluate_candidate

            with self.store.connect() as db:
                row = db.execute(
                    "SELECT settings FROM mao_hybrid.policy_versions WHERE scope=%s AND revision=%s",
                    (self.store.scope, int(body["revision"])),
                ).fetchone()
            if not row:
                raise ValueError("Policy unavailable")
            report = evaluate_candidate(row["settings"])
            for run in report["runs"]:
                self.development.evaluate(
                    int(body["revision"]),
                    run["split"],
                    run["digest"],
                    run["samples"],
                    run["baseline"],
                    run["candidate"],
                    run["hard_failures"],
                )
            return report
        elif operation == "story_action":
            return Activities(self.store).apply(
                uuid.UUID(body["id"]),
                uuid.UUID(body["event_id"]),
                uuid.UUID(body["action_id"]),
                int(body["revision"]),
                body["content"],
                bool(body.get("complete", False)),
            )
        elif operation == "retention":
            return {"raw_sources_redacted": self.repo.retain()}
        else:
            raise ValueError("Unsupported operator action")
        return {"status": "ok"}
