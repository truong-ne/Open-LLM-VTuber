"""Restartable consumers: observations are idempotent, reflection is not reward."""

import asyncio
import re
import time
from types import SimpleNamespace

from ..agent.hybrid.runtime import user_evidence
from ..character.appraisal import folded
from ..character.development import Development, CHOICES
from ..interaction.repository import Journal
from .repository import Experiences


class ExperienceWorker:
    def __init__(self, store):
        self.store = store
        self.repo = Experiences(store)
        self.development = Development(store)
        self.last_retention = 0
        self.processed = 0
        self.errors = 0
        self.last_success = 0
        self.next_evaluation = 0

    def tick(self):
        Journal(self.store).recover()
        self.processed += self.repo.process_outbox()
        with self.store.connect() as db:
            inputs = db.execute(
                """SELECT e.* FROM mao_hybrid.interaction_events e
                JOIN mao_hybrid.episode_events p ON p.scope=e.scope AND p.event_id=e.id
                LEFT JOIN mao_hybrid.observation_receipts r ON r.scope=e.scope AND r.event_id=e.id
                WHERE e.scope=%s AND e.kind='input' AND NOT e.deleted AND NOT e.synthetic AND e.visibility='private'
                AND r.event_id IS NULL ORDER BY e.recorded_at LIMIT 50""",
                (self.store.scope,),
            ).fetchall()
        for source in inputs:
            value = folded(
                user_evidence([SimpleNamespace(content=source["content"] or "")])
            )
            value = re.sub(r'["“][^"”]*["”]|`[^`]*`', " ", value)
            positive = bool(
                re.search(
                    r"dung y|vua du|the nay tot|thich cach|that helped|good answer",
                    value,
                )
            )
            negative = bool(
                re.search(
                    r"dai qua|qua dai|khong dung y|chua dung y|not helpful|dua qua",
                    value,
                )
            )
            if re.search(
                r"(?:khong|chua|not|never).{0,12}(?:dung y|vua du|thich cach|that helped|good answer)",
                value,
            ):
                positive = False
            if positive or negative:
                with self.store.connect() as db:
                    prior = db.execute(
                        """SELECT t.event_id,t.policy_revision,t.policy_settings,t.status,e.deleted,p.episode_id,
                        EXISTS(SELECT 1 FROM mao_hybrid.delivery_segments s WHERE s.scope=t.scope AND s.turn_id=t.id AND s.status='completed') AS delivered
                        FROM mao_hybrid.turns t JOIN mao_hybrid.interaction_events e ON e.scope=t.scope AND e.id=t.event_id
                        LEFT JOIN mao_hybrid.episode_events p ON p.scope=e.scope AND p.event_id=e.id
                        WHERE t.scope=%s AND e.room_id=%s AND e.actor_id=%s AND e.visibility=%s
                        AND NOT e.synthetic AND e.kind='input' AND e.recorded_at<%s
                        ORDER BY e.recorded_at DESC LIMIT 1""",
                        (
                            self.store.scope,
                            source["room_id"],
                            source["actor_id"],
                            source["visibility"],
                            source["recorded_at"],
                        ),
                    ).fetchone()
                if (
                    prior
                    and not prior["deleted"]
                    and prior["status"] == "completed"
                    and prior["delivered"]
                    and prior["episode_id"]
                ):
                    dimensions = {"verbosity"}
                    if negative:
                        dimensions = set()
                        if re.search(r"dai qua|qua dai", value):
                            dimensions.add("verbosity")
                        if "dua qua" in value:
                            dimensions.add("humor")
                    elif prior["policy_revision"]:
                        with self.store.connect() as db:
                            selected = db.execute(
                                """SELECT p.dimension FROM mao_hybrid.policy_versions v
                                JOIN mao_hybrid.character_preferences p ON p.scope=v.scope AND p.id=v.preference_id
                                WHERE v.scope=%s AND v.revision=%s""",
                                (self.store.scope, prior["policy_revision"]),
                            ).fetchone()
                        dimensions = {selected["dimension"]} if selected else set()
                    for dimension, choice in prior["policy_settings"].items():
                        if (
                            dimension in dimensions
                            and dimension in CHOICES
                            and choice in CHOICES[dimension]
                        ):
                            try:
                                self.development.choice(
                                    prior["event_id"],
                                    dimension,
                                    choice,
                                    sorted(CHOICES[dimension]),
                                    supports=positive and not negative,
                                    feedback_event_id=source["id"],
                                )
                            except ValueError:
                                pass
                    with self.store.connect() as db:
                        self.repo.lock(db, source["room_id"])
                        self.repo.source(db, source["id"])
                        self.repo.source(db, prior["event_id"])
                        db.execute(
                            """INSERT INTO mao_hybrid.real_feedback(scope,event_id,target_event,episode_id,policy_revision,positive)
                            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                            (
                                self.store.scope,
                                source["id"],
                                prior["event_id"],
                                prior["episode_id"],
                                prior["policy_revision"],
                                positive and not negative,
                            ),
                        )
            with self.store.connect() as db:
                db.execute(
                    "INSERT INTO mao_hybrid.observation_receipts(scope,event_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (self.store.scope, source["id"]),
                )
        if time.monotonic() - self.last_retention >= 3600:
            self.repo.retain()
            self.last_retention = time.monotonic()
        self.last_success = time.time()
        self.store.put("runtime_worker_status", self.snapshot())
        self.advance_candidates()
        return self.snapshot()

    def advance_candidates(self):
        with self.store.connect() as db:
            eligible = db.execute(
                "SELECT id FROM mao_hybrid.character_preferences WHERE scope=%s AND status='eligible' LIMIT 10",
                (self.store.scope,),
            ).fetchall()
        for row in eligible:
            self.development.propose(row["id"])
        if time.monotonic() >= self.next_evaluation:
            with self.store.connect() as db:
                candidate = db.execute(
                    """SELECT v.revision,v.settings FROM mao_hybrid.policy_versions v WHERE v.scope=%s AND v.status='candidate'
                    AND NOT EXISTS(SELECT 1 FROM mao_hybrid.evaluation_runs e WHERE e.scope=v.scope AND e.policy_revision=v.revision AND e.split='held_out')
                    ORDER BY revision LIMIT 1""",
                    (self.store.scope,),
                ).fetchone()
            if candidate:
                self.next_evaluation = time.monotonic() + 60
                from ..learning.evaluation import evaluate_candidate

                report = evaluate_candidate(candidate["settings"])
                for run in report["runs"]:
                    self.development.evaluate(
                        candidate["revision"],
                        run["split"],
                        run["digest"],
                        run["samples"],
                        run["baseline"],
                        run["candidate"],
                        run["hard_failures"],
                    )
                if self.store.config.auto_policy_promotion and all(
                    run["candidate"] > run["baseline"] and not run["hard_failures"]
                    for run in report["runs"]
                ):
                    self.development.trial(candidate["revision"])
        if self.store.config.auto_policy_promotion:
            with self.store.connect() as db:
                trials = db.execute(
                    "SELECT revision FROM mao_hybrid.policy_versions WHERE scope=%s AND status='trial'",
                    (self.store.scope,),
                ).fetchall()
            for row in trials:
                try:
                    self.development.real_trial(row["revision"])
                    self.development.promote(row["revision"])
                except ValueError:
                    pass

    def snapshot(self):
        return {
            "processed": self.processed,
            "errors": self.errors,
            "last_success": self.last_success,
        }

    async def run(self):
        while True:
            try:
                await asyncio.to_thread(self.tick)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.errors += 1
            await asyncio.sleep(1)
