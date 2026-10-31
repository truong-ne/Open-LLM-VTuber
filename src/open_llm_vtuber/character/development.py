"""Evidence-backed style candidates; no learner can edit the core profile here."""

import math
import uuid
from psycopg.types.json import Jsonb

from ..experience.repository import Experiences

CHOICES = {
    "verbosity": {"brief", "detailed"},
    "initiative": {"wait", "offer"},
    "humor": {"gentle", "playful"},
    "examples": {"concrete", "abstract"},
}


class Development(Experiences):
    def choice(
        self,
        event_id,
        dimension,
        choice,
        alternatives,
        supports=True,
        feedback_event_id=None,
    ):
        if (
            dimension not in CHOICES
            or choice not in CHOICES[dimension]
            or set(alternatives) != CHOICES[dimension]
            or type(supports) is not bool
        ):
            raise ValueError(
                "A real choice between the supported alternatives is required"
            )
        with self.store.connect() as db:
            source = self.source(db, event_id)
            if (
                source["visibility"] != "private"
                or source["synthetic"]
                or source["kind"] != "input"
            ):
                raise ValueError(
                    "Lasting individual style requires non-synthetic private experiences"
                )
            self.lock(db, source["room_id"])
            source = self.source(db, event_id)
            if feedback_event_id:
                feedback = self.source(db, feedback_event_id)
                if feedback["kind"] != "input" or feedback["synthetic"]:
                    raise ValueError("Feedback requires a user input source")
                if (
                    feedback["room_id"],
                    feedback["actor_id"],
                    feedback["visibility"],
                ) != (source["room_id"], source["actor_id"], source["visibility"]):
                    raise ValueError(
                        "Feedback belongs to another actor or visibility scope"
                    )
            episode = db.execute(
                """SELECT p.episode_id AS id FROM mao_hybrid.episode_events p JOIN mao_hybrid.turns t
                ON t.scope=p.scope AND t.event_id=p.event_id WHERE p.scope=%s AND p.event_id=%s AND t.status='completed' """,
                (self.scope, event_id),
            ).fetchone()
            if not episode:
                raise ValueError(
                    "Only a completed, consolidated experience can support a lasting choice"
                )
            identifier = uuid.uuid4()
            row = db.execute(
                """INSERT INTO mao_hybrid.character_preferences(scope,id,room_id,actor_id,dimension,choice)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(scope,room_id,actor_id,dimension,choice)
                DO UPDATE SET revision=mao_hybrid.character_preferences.revision+1 RETURNING *""",
                (
                    self.scope,
                    identifier,
                    source["room_id"],
                    source["actor_id"],
                    dimension,
                    choice,
                ),
            ).fetchone()
            identifier = row["id"]
            db.execute(
                """INSERT INTO mao_hybrid.preference_evidence(scope,preference_id,event_id,episode_id,supports,feedback_event_id)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(scope,preference_id,episode_id)
                DO UPDATE SET supports=mao_hybrid.preference_evidence.supports AND excluded.supports,
                feedback_event_id=CASE WHEN NOT excluded.supports THEN excluded.feedback_event_id ELSE mao_hybrid.preference_evidence.feedback_event_id END""",
                (
                    self.scope,
                    identifier,
                    event_id,
                    episode["id"],
                    supports,
                    feedback_event_id,
                ),
            )
            counts = db.execute(
                """SELECT count(*) FILTER(WHERE p.supports) AS positives,
                count(*) FILTER(WHERE NOT p.supports) AS negatives,count(DISTINCT e.session_id) FILTER(WHERE p.supports) AS sessions
                FROM mao_hybrid.preference_evidence p JOIN mao_hybrid.interaction_events e ON e.scope=p.scope AND e.id=p.event_id
                WHERE p.scope=%s AND p.preference_id=%s AND NOT e.deleted""",
                (self.scope, identifier),
            ).fetchone()
            status = (
                "eligible"
                if counts["positives"] >= 3
                and counts["sessions"] >= 2
                and counts["negatives"] == 0
                else "provisional"
            )
            if row["status"] not in {"locked", "retired"}:
                db.execute(
                    "UPDATE mao_hybrid.character_preferences SET status=%s WHERE scope=%s AND id=%s",
                    (status, self.scope, identifier),
                )
                if status == "provisional":
                    db.execute(
                        "UPDATE mao_hybrid.policy_versions SET status='retired' WHERE scope=%s AND preference_id=%s AND status IN ('candidate','active','trial')",
                        (self.scope, identifier),
                    )
            db.execute(
                """INSERT INTO mao_hybrid.lessons(scope,id,episode_id,event_id,dimension,choice)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (self.scope, uuid.uuid4(), episode["id"], event_id, dimension, choice),
            )
            return {
                "id": str(identifier),
                "status": row["status"]
                if row["status"] in {"locked", "retired"}
                else status,
                **counts,
            }

    def propose(self, preference_id):
        with self.store.connect() as db:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("policy:" + self.scope,),
            )
            row = db.execute(
                "SELECT * FROM mao_hybrid.character_preferences WHERE scope=%s AND id=%s AND status='eligible'",
                (self.scope, preference_id),
            ).fetchone()
            if not row:
                raise ValueError("Preference has insufficient independent evidence")
            existing = db.execute(
                "SELECT revision FROM mao_hybrid.policy_versions WHERE scope=%s AND preference_id=%s AND status IN ('candidate','trial','active') ORDER BY revision DESC LIMIT 1",
                (self.scope, preference_id),
            ).fetchone()
            if existing:
                return existing["revision"]
            revision = db.execute(
                "SELECT coalesce(max(revision),0)+1 AS n FROM mao_hybrid.policy_versions WHERE scope=%s",
                (self.scope,),
            ).fetchone()["n"]
            db.execute(
                "INSERT INTO mao_hybrid.policy_versions(scope,revision,preference_id,settings) VALUES(%s,%s,%s,%s)",
                (
                    self.scope,
                    revision,
                    preference_id,
                    Jsonb({row["dimension"]: row["choice"]}),
                ),
            )
            return revision

    def evaluate(
        self,
        revision,
        split,
        digest,
        samples,
        baseline,
        candidate,
        hard_failures,
    ):
        if split == "real_trial":
            raise ValueError(
                "Real trials require sourced feedback; scalar scores are not accepted"
            )
        if (
            split not in {"development", "held_out", "real_trial"}
            or type(samples) is not int
            or samples <= 0
            or type(hard_failures) is not int
            or hard_failures < 0
        ):
            raise ValueError("Invalid evaluation evidence")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError("Evaluation suite must have a SHA256 digest")
        if not all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1
            for v in (baseline, candidate)
        ):
            raise ValueError("Invalid evaluation scores")
        with self.store.connect() as db:
            db.execute(
                """INSERT INTO mao_hybrid.evaluation_runs(scope,id,policy_revision,suite_digest,split,samples,baseline_score,candidate_score,hard_failures)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.scope,
                    uuid.uuid4(),
                    revision,
                    digest,
                    split,
                    samples,
                    baseline,
                    candidate,
                    hard_failures,
                ),
            )

    def trial(self, revision, budget=20):
        if type(budget) is not int or not 1 <= budget <= 20:
            raise ValueError("Trial budget must be between 1 and 20")
        with self.store.connect() as db:
            row = db.execute(
                """UPDATE mao_hybrid.policy_versions v SET status='trial',budget=%s FROM mao_hybrid.character_preferences p
                WHERE v.scope=%s AND v.revision=%s AND v.status='candidate' AND p.scope=v.scope AND p.id=v.preference_id AND p.status='eligible' RETURNING v.revision""",
                (budget, self.scope, revision),
            ).fetchone()
            if not row:
                raise ValueError("Candidate unavailable")

    def promote(self, revision):
        with self.store.connect() as db:
            owner = db.execute(
                "SELECT p.room_id,p.actor_id FROM mao_hybrid.policy_versions v JOIN mao_hybrid.character_preferences p ON p.scope=v.scope AND p.id=v.preference_id WHERE v.scope=%s AND v.revision=%s",
                (self.scope, revision),
            ).fetchone()
            if not owner:
                raise ValueError("Policy unavailable")
            self.lock(db, owner["room_id"])
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("policy:" + self.scope,),
            )
            preference = db.execute(
                """SELECT p.status FROM mao_hybrid.policy_versions v JOIN mao_hybrid.character_preferences p
                ON p.scope=v.scope AND p.id=v.preference_id WHERE v.scope=%s AND v.revision=%s AND v.status IN ('candidate','trial') FOR UPDATE OF v""",
                (self.scope, revision),
            ).fetchone()
            runs = db.execute(
                "SELECT * FROM mao_hybrid.evaluation_runs WHERE scope=%s AND policy_revision=%s",
                (self.scope, revision),
            ).fetchall()
            required = {"development": 40, "held_out": 20, "real_trial": 3}
            good = all(
                any(
                    r["split"] == split
                    and r["samples"] >= count
                    and r["hard_failures"] == 0
                    and r["candidate_score"] > r["baseline_score"]
                    for r in runs
                )
                for split, count in required.items()
            )
            if (
                not preference
                or preference["status"] != "eligible"
                or not good
                or any(r["hard_failures"] for r in runs)
            ):
                raise ValueError(
                    "Promotion requires independent evidence, hard gates, held-out improvement and real trials"
                )
            db.execute(
                """UPDATE mao_hybrid.policy_versions SET status='retired' WHERE scope=%s AND status='active'
                AND preference_id IN (SELECT id FROM mao_hybrid.character_preferences WHERE scope=%s AND room_id=%s AND actor_id=%s)""",
                (self.scope, self.scope, owner["room_id"], owner["actor_id"]),
            )
            db.execute(
                "UPDATE mao_hybrid.policy_versions SET status='active' WHERE scope=%s AND revision=%s",
                (self.scope, revision),
            )
            db.execute(
                "UPDATE mao_hybrid.character_preferences SET status='stable' WHERE scope=%s AND id=(SELECT preference_id FROM mao_hybrid.policy_versions WHERE scope=%s AND revision=%s)",
                (self.scope, self.scope, revision),
            )

    def rollback(self, revision):
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.policy_versions SET status='retired' WHERE scope=%s AND revision=%s",
                (self.scope, revision),
            )

    def effective(self, room, actor, visibility="private"):
        if visibility != "private":
            return {"revision": 0, "settings": {}}
        with self.store.connect() as db:
            row = db.execute(
                """SELECT v.* FROM mao_hybrid.policy_versions v JOIN mao_hybrid.character_preferences p
                ON p.scope=v.scope AND p.id=v.preference_id WHERE v.scope=%s AND p.room_id=%s AND p.actor_id=%s
                AND (p.status IN ('eligible','stable') OR (p.status='locked' AND v.status='active')) AND (v.status='active' OR (v.status='trial' AND v.budget>0))
                ORDER BY CASE WHEN v.status='trial' THEN 0 ELSE 1 END,v.revision DESC LIMIT 1 FOR UPDATE OF v""",
                (self.scope, room, actor),
            ).fetchone()
            if not row:
                return {"revision": 0, "settings": {}}
            if row["status"] == "trial":
                db.execute(
                    "UPDATE mao_hybrid.policy_versions SET budget=budget-1 WHERE scope=%s AND revision=%s",
                    (self.scope, row["revision"]),
                )
            return {
                "revision": row["revision"],
                "settings": row["settings"],
                "trial": row["status"] == "trial",
            }

    def real_trial(self, revision):
        with self.store.connect() as db:
            target = db.execute(
                """SELECT p.room_id,p.actor_id FROM mao_hybrid.policy_versions v
                JOIN mao_hybrid.character_preferences p ON p.scope=v.scope AND p.id=v.preference_id
                WHERE v.scope=%s AND v.revision=%s""",
                (self.scope, revision),
            ).fetchone()
            if not target:
                raise ValueError("Policy unavailable")
            self.lock(db, target["room_id"])
            rows = db.execute(
                """SELECT f.policy_revision,f.positive,e.id,e.session_id,p.id AS episode
                FROM mao_hybrid.real_feedback f JOIN mao_hybrid.interaction_events e ON e.scope=f.scope AND e.id=f.event_id
                JOIN mao_hybrid.episodes p ON p.scope=f.scope AND p.id=f.episode_id
                WHERE f.scope=%s AND e.room_id=%s AND e.actor_id=%s AND NOT e.deleted AND NOT e.synthetic AND e.visibility='private'
                AND f.policy_revision IN (0,%s)""",
                (self.scope, target["room_id"], target["actor_id"], revision),
            ).fetchall()
            return self._finish_trial(db, rows, revision)

    def _finish_trial(self, db, rows, revision):
        import hashlib

        baseline = [r for r in rows if r["policy_revision"] == 0]
        candidate = [r for r in rows if r["policy_revision"] == revision]
        if any(
            len({r["episode"] for r in group}) < 3
            or len({r["session_id"] for r in group}) < 2
            for group in (baseline, candidate)
        ):
            raise ValueError(
                "Real trial needs three independent episodes across two sessions for both policies"
            )
        digest = hashlib.sha256(
            "|".join(sorted(str(r["id"]) for r in rows)).encode()
        ).hexdigest()
        db.execute(
            """INSERT INTO mao_hybrid.evaluation_runs(scope,id,policy_revision,suite_digest,split,samples,baseline_score,candidate_score,hard_failures)
            VALUES(%s,%s,%s,%s,'real_trial',%s,%s,%s,0)""",
            (
                self.scope,
                uuid.uuid4(),
                revision,
                digest,
                len(candidate),
                sum(r["positive"] for r in baseline) / len(baseline),
                sum(r["positive"] for r in candidate) / len(candidate),
            ),
        )

    def lock_preference(self, identifier, retire=False):
        with self.store.connect() as db:
            owner = db.execute(
                "SELECT room_id FROM mao_hybrid.character_preferences WHERE scope=%s AND id=%s",
                (self.scope, identifier),
            ).fetchone()
            if not owner:
                raise ValueError("Preference unavailable")
            self.lock(db, owner["room_id"])
            db.execute(
                "UPDATE mao_hybrid.character_preferences SET status=%s,revision=revision+1 WHERE scope=%s AND id=%s",
                ("retired" if retire else "locked", self.scope, identifier),
            )
            db.execute(
                "UPDATE mao_hybrid.policy_versions SET status='retired' WHERE scope=%s AND preference_id=%s AND (status IN ('candidate','trial') OR (%s AND status='active'))",
                (self.scope, identifier, retire),
            )
