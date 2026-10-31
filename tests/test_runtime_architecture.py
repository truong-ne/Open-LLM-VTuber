import asyncio
import os
import unittest
from unittest.mock import AsyncMock
import uuid

from pydantic import ValidationError

from src.open_llm_vtuber.interaction.events import InteractionEvent, DeliveryTracker
from src.open_llm_vtuber.interaction.ingress import (
    issue_actor,
    verify_actor,
    seal,
    unseal,
)
from src.open_llm_vtuber.interaction.coordinator import RoomCoordinator, Proposal
from src.open_llm_vtuber.interaction.repository import Journal
from src.open_llm_vtuber.experience.repository import Experiences
from src.open_llm_vtuber.experience.activities import Activities
from src.open_llm_vtuber.character.development import Development
from src.open_llm_vtuber.agent.hybrid.config import HybridConfig
from src.open_llm_vtuber.agent.hybrid.store import Store
from test_hybrid_memory import FixedEmbedder


class ContractsTests(unittest.TestCase):
    def test_host_speech_requires_a_host_signature_and_is_bound_to_its_content(self):
        from src.open_llm_vtuber.interaction.ingress import (
            sign_host_proposal,
            verify_host_proposal,
        )

        forged = {
            "type": "text-input",
            "source": "mao-idle-host",
            "text": "script",
            "narration_speech": "script",
        }
        self.assertFalse(verify_host_proposal(forged))
        signed = sign_host_proposal(forged)
        self.assertTrue(verify_host_proposal(signed))
        self.assertIn("event_id", signed)
        signed["narration_speech"] = "replaced"
        self.assertFalse(verify_host_proposal(signed))

    def test_nickname_never_authenticates_and_tokens_cannot_be_modified(self):
        first, second = issue_actor(), issue_actor()
        self.assertNotEqual(verify_actor(first), verify_actor(second))
        self.assertIsNone(verify_actor("papa"))
        self.assertIsNone(verify_actor(first[:-1] + ("0" if first[-1] != "0" else "1")))
        value = seal(verify_actor(first), "session")
        self.assertEqual(unseal(value)["actor"], verify_actor(first))
        value["value"]["actor"] = "operator"
        self.assertIsNone(unseal(value))
        with self.assertRaises(ValidationError):
            InteractionEvent(
                room_id="x", actor_id="papa", session_id="s", role="operator"
            )

    def test_old_ack_never_completes_new_turn_and_interrupt_is_final(self):
        first, second = DeliveryTracker(), DeliveryTracker()
        one = first.segment("generated only")
        two = second.segment("new response")
        self.assertFalse(second.ack({**one, "status": "completed"}))
        self.assertFalse(second.ack({"status": "completed"}))
        self.assertTrue(second.ack({**two, "status": "started"}))
        self.assertEqual(second.finish("interrupted"), "interrupted")
        self.assertFalse(second.ack({**two, "status": "completed"}))
        self.assertEqual(first.finish(), "unknown")

    def test_all_segments_must_finish_and_failure_is_not_success(self):
        tracker = DeliveryTracker()
        a, b = tracker.segment("a"), tracker.segment("b")
        tracker.ack({**a, "status": "completed"})
        tracker.ack({**b, "status": "failed"})
        self.assertEqual(tracker.finish(), "failed")


class SchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_output_cannot_play_after_a_turn_was_interrupted(self):
        from src.open_llm_vtuber.interaction.service import TurnSession

        turn = TurnSession.__new__(TurnSession)
        turn.delivery = DeliveryTracker()
        turn.delivery.finish("interrupted")
        sender = AsyncMock()
        await turn.send('{"type":"audio","audio":"late fixture"}', sender)
        sender.assert_not_called()

    async def test_disconnect_cannot_cancel_a_finalization_already_in_progress(self):
        from src.open_llm_vtuber.interaction.service import TurnSession

        turn = TurnSession.__new__(TurnSession)
        turn._finalization_task = None
        entered = asyncio.Event()
        release = asyncio.Event()
        committed = []

        async def commit(status):
            entered.set()
            await release.wait()
            committed.append(True)

        turn._finish = commit
        task = asyncio.create_task(turn.finish())
        await entered.wait()
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(committed, [True])
        await turn.finish()
        self.assertEqual(committed, [True])

    async def test_proxy_does_not_broadcast_a_private_answer_to_another_actor(self):
        from src.open_llm_vtuber.proxy_handler import ProxyHandler
        from types import SimpleNamespace

        proxy = ProxyHandler.__new__(ProxyHandler)
        first, second = issue_actor(), issue_actor()
        proxy.actor_tokens = {"a": first, "b": second}
        a, b = (
            SimpleNamespace(send_json=AsyncMock()),
            SimpleNamespace(send_json=AsyncMock()),
        )
        proxy.clients = {"a": a, "b": b}
        await proxy.broadcast_to_clients(
            {
                "type": "audio",
                "audio": "fixture",
                "recipient_actor_id": verify_actor(first),
            }
        )
        a.send_json.assert_awaited_once()
        b.send_json.assert_not_called()
        await proxy.broadcast_to_clients({"type": "audio", "audio": "public fixture"})
        self.assertEqual(a.send_json.await_count, 2)
        b.send_json.assert_awaited_once()

    async def test_disconnected_notify_does_not_orphan_an_accepted_proposal(self):
        room = RoomCoordinator()
        run = AsyncMock()
        notify = AsyncMock(side_effect=ConnectionError())
        self.assertFalse(await room.submit(Proposal("direct", run, notify)))
        self.assertEqual(room.pending, [])
        run.assert_not_called()

    async def test_shutdown_requires_the_host_secret_and_an_actor_proof_is_insufficient(
        self,
    ):
        import httpx
        from fastapi import FastAPI
        from types import SimpleNamespace
        from src.open_llm_vtuber.interaction.control import install_local_control
        from src.open_llm_vtuber.interaction.ingress import control_token

        app = FastAPI()
        app.state.runtime_runner = SimpleNamespace(should_exit=False)
        install_local_control(app, "test")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app, client=("127.0.0.1", 1234)),
            base_url="http://localhost",
        ) as client:
            self.assertEqual(
                (
                    await client.post(
                        "/api/runtime/shutdown",
                        headers={"X-Mao-Control": issue_actor()},
                    )
                ).status_code,
                403,
            )
            self.assertFalse(app.state.runtime_runner.should_exit)
            self.assertEqual(
                (
                    await client.post(
                        "/api/runtime/shutdown",
                        headers={"X-Mao-Control": control_token("test")},
                    )
                ).status_code,
                200,
            )
            self.assertTrue(app.state.runtime_runner.should_exit)

    async def test_old_summary_cannot_reappear_after_a_memory_generation_is_reset(self):
        from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent

        agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
        agent._pending_summary_messages = [
            {"role": "user", "content": "discarded evidence"}
        ]
        agent._memory_summary = ""
        agent._summary_task = None
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_summary(batch):
            started.set()
            await release.wait()
            return "discarded evidence"

        agent._request_memory_summary = slow_summary
        task = asyncio.create_task(agent._summarize_pending_memory())
        await started.wait()
        agent._reset_memory_summary()
        release.set()
        await task
        self.assertEqual(agent._memory_summary, "")

    async def test_priority_overflow_and_interrupt_release_floor(self):
        room = RoomCoordinator(limit=2)
        release = asyncio.Event()
        calls = []

        async def active():
            async with room.floor("active"):
                await release.wait()

        async def direct():
            async with room.floor("direct"):
                calls.append("direct")

        notices = AsyncMock()
        await room.submit(Proposal("direct", active, notices, owner="active"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await room.submit(Proposal("research", direct, notices, owner="background"))
        await room.submit(Proposal("direct", direct, notices, owner="direct"))
        self.assertEqual(len(room.pending), 1)
        await room.interrupt("active")
        await room.worker
        self.assertEqual(calls, ["direct"])
        self.assertIsNone(room.owner)
        self.assertIn(unittest.mock.call("superseded"), notices.call_args_list)

    async def test_queue_full_is_rejected_and_never_silently_dropped(self):
        room = RoomCoordinator(limit=1)
        room.worker = asyncio.create_task(asyncio.Event().wait())
        notice = AsyncMock()
        self.assertTrue(
            await room.submit(Proposal("direct", AsyncMock(), notice, owner="a"))
        )
        self.assertFalse(
            await room.submit(Proposal("direct", AsyncMock(), notice, owner="b"))
        )
        self.assertEqual(notice.call_args.args, ("rejected_busy",))
        room.worker.cancel()
        await asyncio.gather(room.worker, return_exceptions=True)


@unittest.skipUnless(
    os.environ.get("MAO_TEST_POSTGRES") == "1", "PostgreSQL integration opt-in"
)
class ArchitectureDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.config = HybridConfig(scope="test-architecture-" + uuid.uuid4().hex)
        self.store = Store(self.config, FixedEmbedder())
        self.journal = Journal(self.store)
        self.repo = Experiences(self.store)
        self.activity = Activities(self.store)
        self.development = Development(self.store)

    def tearDown(self):
        with self.store.connect() as db:
            for table in (
                "evaluation_runs",
                "real_feedback",
                "lessons",
                "policy_versions",
                "preference_evidence",
                "character_preferences",
                "activity_actions",
                "activity_evidence",
                "activities",
                "open_threads",
                "episode_events",
                "episodes",
                "memory_evidence",
                "knowledge_items",
                "observation_receipts",
                "interaction_outbox",
                "delivery_segments",
                "turns",
                "interaction_events",
                "rooms",
                "actors",
                "state",
            ):
                db.execute(
                    f"DELETE FROM mao_hybrid.{table} WHERE scope=%s",
                    (self.store.scope,),
                )
        self.store.close()

    def event(
        self,
        content="synthetic claim",
        actor="person-a",
        room="room",
        session=None,
        visibility="private",
        key=None,
        complete=True,
        policy=0,
        settings=None,
    ):
        event = InteractionEvent(
            room_id=room,
            actor_id=actor,
            session_id=session or uuid.uuid4().hex,
            visibility=visibility,
            content=content,
            source_key=key,
        )
        tracker = DeliveryTracker()
        self.assertTrue(self.journal.accept(event, tracker))
        segment = tracker.segment("synthetic delivered sentence")
        if complete:
            tracker.ack({**segment, "status": "completed"})
        tracker.finish()
        self.journal.finish(
            event,
            tracker,
            policy_revision=policy,
            policy_settings=settings or {"verbosity": "brief"},
        )
        self.repo.process_outbox()
        return event, tracker

    def test_dedup_is_actor_scoped_and_outbox_is_atomic(self):
        first, tracker = self.event(key="source:1")
        self.assertFalse(
            self.journal.accept(
                first.model_copy(update={"event_id": uuid.uuid4()}), DeliveryTracker()
            )
        )
        other, _ = self.event(actor="person-b", key="source:1")
        self.assertNotEqual(first.event_id, other.event_id)
        broken = InteractionEvent(
            room_id="room",
            actor_id="person-a",
            session_id="s",
            content="should roll back",
        )
        with self.assertRaises(Exception):
            self.journal.accept(broken, tracker)
        with self.store.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM mao_hybrid.interaction_events WHERE scope=%s AND id=%s",
                    (self.store.scope, broken.event_id),
                ).fetchone()["n"],
                0,
            )

    def test_private_public_room_and_fiction_filters_precede_retrieval(self):
        private, _ = self.event("PRIVATE SECRET")
        public, _ = self.event("PUBLIC FACT CLAIM", visibility="public")
        fiction, _ = self.event("FICTIONAL CHILDHOOD")
        for event, kind in (
            (private, "user_claim"),
            (public, "user_claim"),
            (fiction, "fiction"),
        ):
            self.repo.add_item(event.event_id, event.content, kind)
        own = self.repo.context("room", "person-a", "private")["items"]
        stranger = self.repo.context("room", "person-b", "private")["items"]
        published = self.repo.context("room", "person-a", "public")["items"]
        self.assertEqual(
            {x["content"] for x in own}, {"PRIVATE SECRET", "PUBLIC FACT CLAIM"}
        )
        self.assertEqual({x["content"] for x in stranger}, {"PUBLIC FACT CLAIM"})
        self.assertEqual({x["content"] for x in published}, {"PUBLIC FACT CLAIM"})
        self.assertEqual(
            self.repo.context("another-room", "person-a", "private")["items"], []
        )

    def test_superseded_preference_does_not_win_after_restart(self):
        first, _ = self.event("I prefer tea")
        self.repo.add_item(first.event_id, first.content, "user_preference", "drink")
        second, _ = self.event("I now prefer coffee")
        self.repo.add_item(second.event_id, second.content, "user_preference", "drink")
        reader = Experiences(self.store)
        self.assertEqual(
            [
                x["content"]
                for x in reader.context("room", "person-a", "private")["items"]
            ],
            ["I now prefer coffee"],
        )

    def test_deletion_invalidates_derivations_and_pending_replay_cannot_resurrect(self):
        event, tracker = self.event("Erase this source", key="durable-source")
        self.repo.add_item(event.event_id, event.content)
        self.repo.open_thread(event.event_id, "unfinished topic")
        activity = self.activity.start(event.event_id)
        self.activity.apply(
            activity["id"], event.event_id, uuid.uuid4(), 1, "fictional canon"
        )
        revision = self.repo.context("room", "person-a", "private")["revision"]
        self.repo.forget_source(event.event_id)
        self.assertEqual(self.repo.context("room", "person-a", "private")["items"], [])
        self.assertGreater(
            self.repo.context("room", "person-a", "private")["revision"], revision
        )
        self.assertEqual(self.activity.context("room", "person-a"), [])
        self.assertEqual(self.repo.process_outbox(), 0)
        with self.assertRaises(ValueError):
            self.repo.add_item(event.event_id, "Erase this source")
        self.assertFalse(
            self.journal.accept(
                event.model_copy(update={"event_id": uuid.uuid4()}), DeliveryTracker()
            )
        )
        with self.store.connect() as db:
            row = db.execute(
                "SELECT content,deleted FROM mao_hybrid.interaction_events WHERE scope=%s AND id=%s",
                (self.store.scope, event.event_id),
            ).fetchone()
            self.assertIsNone(row["content"])
            self.assertTrue(row["deleted"])

    def test_revisioned_edit_rejects_stale_writes(self):
        source, _ = self.event("Old value")
        item = self.repo.add_item(source.event_id, source.content)
        new = self.repo.revise_item(item, 1, "New operator correction")
        with self.assertRaises(ValueError):
            self.repo.revise_item(item, 1, "Stale write")
        self.assertEqual(
            self.repo.context("room", "person-a", "private")["items"][0]["id"], new
        )

    def test_activity_idempotency_expiry_scope_and_secondary_source_deletion(self):
        source, _ = self.event("Start a fictional story")
        started = self.activity.start(source.event_id)
        action = uuid.uuid4()
        result = self.activity.apply(
            started["id"], source.event_id, action, 1, "A fictional forest"
        )
        self.assertEqual(
            self.activity.apply(
                started["id"], source.event_id, action, 1, "A fictional forest"
            ),
            result,
        )
        with self.assertRaises(ValueError):
            self.activity.apply(
                started["id"], source.event_id, uuid.uuid4(), 1, "Stale choice"
            )
        stranger, _ = self.event(actor="person-b")
        with self.assertRaises(ValueError):
            self.activity.apply(
                started["id"], stranger.event_id, uuid.uuid4(), 2, "Other person"
            )
        next_event, _ = self.event("Next choice")
        self.activity.apply(
            started["id"],
            next_event.event_id,
            uuid.uuid4(),
            2,
            "Another fictional scene",
        )
        self.repo.forget_source(next_event.event_id)
        self.assertEqual(self.activity.context("room", "person-a"), [])
        another = self.activity.start(source.event_id)
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.activities SET expires=now()-interval '1 second' WHERE scope=%s AND id=%s",
                (self.store.scope, another["id"]),
            )
        with self.assertRaises(ValueError):
            self.activity.apply(
                another["id"], source.event_id, uuid.uuid4(), 1, "Expired action"
            )

    def eligible(self, actor="person-a"):
        result = None
        sources = []
        for index in range(3):
            event, _ = self.event(session="session-" + str(index), actor=actor)
            sources.append(event)
            result = self.development.choice(
                event.event_id, "verbosity", "brief", ["brief", "detailed"]
            )
        self.assertEqual(result["status"], "eligible")
        return result, sources

    def test_same_episode_never_counts_as_independent_growth(self):
        source, _ = self.event(session="same-session")
        for _ in range(4):
            result = self.development.choice(
                source.event_id, "verbosity", "brief", ["brief", "detailed"]
            )
        self.assertEqual(result["positives"], 1)
        self.assertEqual(result["status"], "provisional")
        with self.assertRaises(ValueError):
            self.development.propose(result["id"])

    def test_counterexample_retires_trial_and_deleted_sources_remove_policy(self):
        preference, sources = self.eligible()
        revision = self.development.propose(preference["id"])
        self.development.trial(revision, 2)
        self.assertEqual(
            self.development.effective("room", "person-a")["revision"], revision
        )
        self.assertEqual(self.development.effective("room", "person-b")["revision"], 0)
        counter, _ = self.event()
        result = self.development.choice(
            counter.event_id, "verbosity", "brief", ["brief", "detailed"], False
        )
        self.assertEqual(result["status"], "provisional")
        self.assertEqual(self.development.effective("room", "person-a")["revision"], 0)
        self.repo.forget_source(sources[0].event_id)
        with self.store.connect() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM mao_hybrid.policy_versions WHERE scope=%s",
                    (self.store.scope,),
                ).fetchone()["n"],
                0,
            )

    def test_promotion_cannot_use_missing_or_scalar_real_trial_results(self):
        preference, _ = self.eligible()
        revision = self.development.propose(preference["id"])
        with self.assertRaises(ValueError):
            self.development.promote(revision)
        self.development.evaluate(revision, "development", "a" * 64, 40, 0.5, 0.8, 0)
        self.development.evaluate(revision, "held_out", "b" * 64, 20, 0.5, 0.8, 0)
        with self.assertRaises(ValueError):
            self.development.evaluate(revision, "real_trial", "c" * 64, 3, 0.5, 0.8, 0)
        with self.assertRaises(ValueError):
            self.development.real_trial(revision)
        with self.assertRaises(ValueError):
            self.development.promote(revision)
        self.development.trial(revision, 1)
        self.assertEqual(
            self.development.effective("room", "person-a")["revision"], revision
        )
        self.assertEqual(self.development.effective("room", "person-a")["revision"], 0)
        self.development.rollback(revision)
        self.assertEqual(self.development.effective("room", "person-a")["revision"], 0)

    def test_counterexample_is_not_erased_by_repetitions_in_the_same_episode(self):
        preference, sources = self.eligible()
        self.development.choice(
            sources[0].event_id,
            "verbosity",
            "brief",
            ["brief", "detailed"],
            supports=False,
        )
        result = self.development.choice(
            sources[0].event_id, "verbosity", "brief", ["brief", "detailed"]
        )
        self.assertEqual(result["status"], "provisional")
        self.assertEqual(result["negatives"], 1)

    def test_operator_retired_trait_is_not_resurrected_by_observation(self):
        preference, sources = self.eligible()
        self.development.lock_preference(preference["id"], retire=True)
        result = self.development.choice(
            sources[0].event_id, "verbosity", "brief", ["brief", "detailed"]
        )
        self.assertEqual(result["status"], "retired")

    def test_raw_retention_preserves_current_sourced_memory_but_explicit_forget_removes_it(
        self,
    ):
        event, _ = self.event(content="Từ nay đừng đùa nhé")
        item = self.repo.add_item(
            event.event_id, event.content, "user_preference", item_key="boundary:humor"
        )
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.interaction_events SET recorded_at=now()-interval '31 days' WHERE scope=%s AND id=%s",
                (self.store.scope, event.event_id),
            )
        self.assertEqual(self.repo.retain(), 1)
        self.assertEqual(
            self.repo.boundaries("room", "person-a", "private"), {"humor": "gentle"}
        )
        self.assertEqual(self.repo.boundaries("room", "person-b", "private"), {})
        with self.store.connect() as db:
            raw = db.execute(
                "SELECT content,raw_expired,deleted FROM mao_hybrid.interaction_events WHERE scope=%s AND id=%s",
                (self.store.scope, event.event_id),
            ).fetchone()
        self.assertIsNone(raw["content"])
        self.assertTrue(raw["raw_expired"])
        self.assertFalse(raw["deleted"])
        self.repo.forget_item(item, "room", "person-a", "private")
        self.assertEqual(self.repo.boundaries("room", "person-a", "private"), {})

    def test_semantic_retrieval_finds_old_evidence_beyond_the_recent_window(self):
        source, _ = self.event(content="I enjoy books")
        wanted = self.repo.add_item(source.event_id, source.content)
        for index in range(66):
            filler, _ = self.event(content=f"Unrelated filler {index}")
            self.repo.add_item(filler.event_id, filler.content)
        results = self.repo.context("room", "person-a", "private", "book", limit=1)
        self.assertEqual(results["items"][0]["id"], wanted)

    def test_promotion_uses_sourced_real_feedback_and_locked_active_style_stays_fixed(
        self,
    ):
        preference, _ = self.eligible()
        revision = self.development.propose(preference["id"])
        self.development.evaluate(revision, "development", "a" * 64, 40, 0.5, 0.8, 0)
        self.development.evaluate(revision, "held_out", "b" * 64, 20, 0.5, 0.8, 0)
        self.development.trial(revision)
        for policy in (0, revision):
            for index in range(3):
                target, _ = self.event(
                    session=f"trial-{policy}-{index}",
                    policy=policy,
                    settings={"verbosity": "brief" if policy else "detailed"},
                )
                feedback, _ = self.event(
                    content="good answer" if policy else "not helpful",
                    session=f"feedback-{policy}-{index}",
                )
                with self.store.connect() as db:
                    episode = db.execute(
                        "SELECT episode_id FROM mao_hybrid.episode_events WHERE scope=%s AND event_id=%s",
                        (self.store.scope, target.event_id),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO mao_hybrid.real_feedback(scope,event_id,target_event,episode_id,policy_revision,positive) VALUES(%s,%s,%s,%s,%s,%s)",
                        (
                            self.store.scope,
                            feedback.event_id,
                            target.event_id,
                            episode["episode_id"],
                            policy,
                            bool(policy),
                        ),
                    )
        self.development.real_trial(revision)
        self.development.promote(revision)
        self.assertEqual(
            self.development.effective("room", "person-a")["revision"], revision
        )
        self.assertEqual(
            self.development.effective("room", "person-a", "public")["revision"], 0
        )
        self.development.lock_preference(preference["id"])
        self.assertEqual(
            self.development.effective("room", "person-a")["revision"], revision
        )
        self.development.rollback(revision)
        self.assertEqual(self.development.effective("room", "person-a")["revision"], 0)

    def test_crash_recovery_never_replays_pending_audio_and_keeps_outbox_receipt(self):
        event = InteractionEvent(
            room_id="room",
            actor_id="person-a",
            session_id="recovery",
            content="crash fixture",
        )
        delivery = DeliveryTracker()
        self.journal.accept(event, delivery, running=False)
        self.journal.recover(force=True)
        with self.store.connect() as db:
            row = db.execute(
                "SELECT status FROM mao_hybrid.turns WHERE scope=%s AND id=%s",
                (self.store.scope, delivery.turn_id),
            ).fetchone()
        self.assertEqual(row["status"], "unknown")
        self.assertEqual(self.repo.process_outbox(), 1)
        self.assertFalse(self.journal.accept(event, DeliveryTracker()))

    def test_delivered_partial_turn_keeps_original_segment_order(self):
        event = InteractionEvent(
            room_id="room", actor_id="person-a", session_id="partial", content="test"
        )
        delivery = DeliveryTracker()
        self.journal.accept(event, delivery)
        for text in ["first", "second"]:
            segment = delivery.segment(text)
            delivery.ack({**segment, "status": "completed"})
        delivery.segment("unheard")
        delivery.finish("interrupted")
        self.journal.finish(event, delivery)
        rows = self.repo.context("room", "person-a", "private")["delivered_turns"]
        self.assertEqual(rows[0]["delivered_response"], "first second")
        self.assertEqual(rows[0]["delivery_status"], "interrupted")

    def test_sql_scope_constraints_and_core_permissions(self):
        from psycopg.errors import InsufficientPrivilege

        a, _ = self.event("A", room="room-a")
        b, _ = self.event("B", room="room-b")
        item = self.repo.add_item(a.event_id, "A")
        with self.assertRaises(Exception):
            with self.store.connect() as db:
                db.execute(
                    "INSERT INTO mao_hybrid.memory_evidence(scope,item_id,event_id) VALUES(%s,%s,%s)",
                    (self.store.scope, item, b.event_id),
                )
        with self.assertRaises(InsufficientPrivilege):
            with self.store.connect() as db:
                db.execute(
                    "UPDATE mao_hybrid.character_profiles SET prompt='learner mutation' WHERE scope=%s",
                    (self.store.scope,),
                )

    def test_single_writer_lease_blocks_duplicate_backend_recovery(self):
        first = self.journal.acquire_lease()
        try:
            with self.assertRaises(RuntimeError):
                self.journal.acquire_lease()
        finally:
            first.close()
        self.journal.acquire_lease().close()

    def test_public_story_is_shared_only_inside_its_room_and_private_story_is_separate(
        self,
    ):
        owner, _ = self.event(content="story", visibility="public")
        activity = self.activity.start(owner.event_id)
        peer, _ = self.event(content="continue", actor="person-b", visibility="public")
        result = self.activity.apply(
            activity["id"], peer.event_id, uuid.uuid4(), 1, "A fictional lamp sings."
        )
        self.assertEqual(result["revision"], 2)
        self.assertEqual(len(self.activity.context("room", "person-b", "public")), 1)
        self.assertEqual(self.activity.context("other-room", "person-b", "public"), [])
        private, _ = self.event(content="private story")
        private_story = self.activity.start(private.event_id)
        self.assertNotEqual(private_story["id"], activity["id"])
        self.assertEqual(self.activity.context("room", "person-b", "private"), [])
        self.repo.forget_source(peer.event_id)
        self.assertEqual(self.activity.context("room", "person-a", "public"), [])

    def test_focus_waits_for_input_expires_and_forgets_without_guessing_a_mood(self):
        from src.open_llm_vtuber.dialogue.focus import Focus

        focus = Focus(self.store)
        source, _ = self.event(content="Ý tớ là một câu chuyện khác")
        focus.input(source.event_id, source.content)
        focus.delivered(source.event_id, "Bạn muốn chọn cánh cửa nào?")
        self.assertTrue(focus.room_waiting("room"))
        self.assertTrue(focus.current("room", "person-a", "private")["repair"])
        self.assertIsNone(focus.current("room", "person-b", "private"))
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.dialogue_focus SET expires=now()-interval '1 second' WHERE scope=%s",
                (self.store.scope,),
            )
        self.assertFalse(focus.room_waiting("room"))
        focus.input(source.event_id, "Chuyển chủ đề")
        self.repo.forget_source(source.event_id)
        self.assertIsNone(focus.current("room", "person-a", "private"))

    def test_edit_keeps_original_provenance_and_forgetting_is_idempotent(self):
        source, _ = self.event(content="I enjoy tea")
        item = self.repo.add_item(source.event_id, source.content)
        self.repo.revise_item(item, 1, "I enjoy milk")
        self.repo.forget_source(source.event_id)
        self.repo.forget_source(source.event_id)
        self.assertEqual(self.repo.context("room", "person-a", "private")["items"], [])

    def test_story_and_delivery_commit_before_the_client_receives_conversation_end(
        self,
    ):
        from types import SimpleNamespace
        from src.open_llm_vtuber.interaction.service import TurnSession

        context = SimpleNamespace(
            agent_engine=SimpleNamespace(
                _hybrid=SimpleNamespace(
                    config=self.config, store=self.store, profile=None
                )
            )
        )

        async def scenario():
            turn = TurnSession(context, "commit-fixture")
            await turn.begin("/story start")
            await turn.input("/story start A fictional lamp")
            segment = turn.delivery.segment("A fictional lamp sings.")
            turn.delivery.ack({**segment, "status": "completed"})

            async def sender(message):
                with self.store.connect() as db:
                    state = db.execute(
                        "SELECT status,jsonb_array_length(canon) AS entries FROM mao_hybrid.activities WHERE scope=%s AND id=%s",
                        (self.store.scope, turn.activity["id"]),
                    ).fetchone()
                    delivered = db.execute(
                        "SELECT status FROM mao_hybrid.turns WHERE scope=%s AND id=%s",
                        (self.store.scope, turn.delivery.turn_id),
                    ).fetchone()
                self.assertEqual(state["entries"], 1)
                self.assertEqual(delivered["status"], "completed")

            await turn.send(
                '{"type":"control","text":"conversation-chain-end"}', sender
            )
            await turn.finish()

        asyncio.run(scenario())

    def test_explicit_address_is_retained_ahead_of_unrelated_retrieval_without_authenticating_a_nickname(
        self,
    ):
        from src.open_llm_vtuber.experience.claims import explicit_address_request

        self.assertTrue(explicit_address_request("Mao ơi, từ nay gọi tớ là Trường"))
        self.assertFalse(explicit_address_request("Người đó đã gọi tớ là Trường"))
        self.assertFalse(explicit_address_request("Hôm nay gọi tớ là Trường"))
        source, _ = self.event(content="Từ nay gọi tớ là Trường")
        identifier = self.repo.add_item(
            source.event_id,
            source.content,
            "user_preference",
            item_key="preference:address",
        )
        for index in range(9):
            note, _ = self.event(content=f"book {index}")
            self.repo.add_item(note.event_id, note.content)
        self.assertEqual(
            self.repo.context("room", "person-a", "private", "book")["items"][0]["id"],
            identifier,
        )
        self.assertIsNone(verify_actor("Trường"))

    def test_feedback_does_not_change_an_unrelated_trait_or_retarget_a_forgotten_answer(
        self,
    ):
        import time
        from src.open_llm_vtuber.experience.worker import ExperienceWorker

        preference, _ = self.eligible()
        feedback, _ = self.event(content="Mao đùa quá")
        worker = ExperienceWorker(self.store)
        worker.last_retention = time.monotonic()
        worker.next_evaluation = float("inf")
        worker.tick()
        with self.store.connect() as db:
            row = db.execute(
                "SELECT status FROM mao_hybrid.character_preferences WHERE scope=%s AND id=%s",
                (self.store.scope, preference["id"]),
            ).fetchone()
        self.assertEqual(row["status"], "eligible")
        self.repo.forget_source(feedback.event_id)
        response, _ = self.event(content="good answer")
        worker.tick()
        with self.store.connect() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM mao_hybrid.real_feedback WHERE scope=%s AND event_id=%s",
                    (self.store.scope, response.event_id),
                ).fetchone()
            )

    def test_promoting_one_actor_does_not_retire_another_actors_style(self):
        first, _ = self.eligible()
        first_revision = self.development.propose(first["id"])
        with self.store.connect() as db:
            db.execute(
                "UPDATE mao_hybrid.policy_versions SET status='active' WHERE scope=%s AND revision=%s",
                (self.store.scope, first_revision),
            )
            db.execute(
                "UPDATE mao_hybrid.character_preferences SET status='stable' WHERE scope=%s AND id=%s",
                (self.store.scope, first["id"]),
            )
        second, _ = self.eligible("person-b")
        revision = self.development.propose(second["id"])
        self.development.evaluate(revision, "development", "a" * 64, 40, 0.5, 0.8, 0)
        self.development.evaluate(revision, "held_out", "b" * 64, 20, 0.5, 0.8, 0)
        for policy in (0, revision):
            for index in range(3):
                target, _ = self.event(
                    actor="person-b", session=f"own-{policy}-{index}", policy=policy
                )
                feedback, _ = self.event(
                    actor="person-b", session=f"feedback-{policy}-{index}"
                )
                with self.store.connect() as db:
                    episode = db.execute(
                        "SELECT episode_id FROM mao_hybrid.episode_events WHERE scope=%s AND event_id=%s",
                        (self.store.scope, target.event_id),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO mao_hybrid.real_feedback(scope,event_id,target_event,episode_id,policy_revision,positive) VALUES(%s,%s,%s,%s,%s,%s)",
                        (
                            self.store.scope,
                            feedback.event_id,
                            target.event_id,
                            episode["episode_id"],
                            policy,
                            bool(policy),
                        ),
                    )
        self.development.real_trial(revision)
        self.development.promote(revision)
        self.assertEqual(
            self.development.effective("room", "person-a")["revision"], first_revision
        )
        self.assertEqual(
            self.development.effective("room", "person-b")["revision"], revision
        )
