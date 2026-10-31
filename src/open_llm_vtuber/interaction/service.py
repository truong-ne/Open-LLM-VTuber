"""The bridge used by live dialogue, not a second agent or an offline-only demo."""

import asyncio
import json
import re
import uuid

from ..agent.hybrid.config import HybridConfig
from ..character.development import Development
from ..experience.activities import Activities
from ..experience.repository import Experiences
from .coordinator import coordinator
from .events import DeliveryTracker, InteractionEvent, current_delivery
from .ingress import issue_actor, verify_actor, unseal
from .repository import Journal


def enabled(context):
    hybrid = getattr(getattr(context, "agent_engine", None), "_hybrid", None)
    return bool(
        hybrid
        and isinstance(hybrid.config, HybridConfig)
        and hybrid.config.enabled
        and hybrid.config.interaction_enabled
    )


class TurnSession:
    def __init__(self, context, client_uid, metadata=None):
        self.context = context
        self.hybrid = context.agent_engine._hybrid
        self.store = self.hybrid.store
        self.journal = Journal(self.store)
        self.experiences = Experiences(self.store)
        self.activities = Activities(self.store)
        self.development = Development(self.store)
        self.delivery = DeliveryTracker()
        self.delivery.modality = (
            "voice" if (metadata or {}).get("_modality") == "voice" else "text"
        )
        self.client_uid = client_uid
        self.metadata = metadata or {}
        identity = unseal(self.metadata.get("_host_ingress"))
        if not identity:
            token = getattr(context, "mao_actor_token", None)
            if not verify_actor(token):
                token = context.mao_actor_token = issue_actor()
            identity = {
                "actor": verify_actor(token),
                "session": client_uid,
                "source_key": None,
                "public": False,
            }
        self.room = identity.get("room", "local")
        self.actor = identity["actor"]
        if self.metadata.get("_group_member") and identity.get("source_key"):
            import hashlib

            identity = {
                **identity,
                "source_key": hashlib.sha256(
                    (
                        identity["source_key"] + ":" + self.metadata["_group_member"]
                    ).encode()
                ).hexdigest(),
            }
        host_proposal = any(
            self.metadata.get(key)
            for key in (
                "rehearsal",
                "skip_memory",
                "game_speech",
                "narration_speech",
                "proactive_speak",
            )
        )
        synthetic = bool(self.metadata.get("rehearsal"))
        test = self.store.scope.startswith(
            ("test-", "emotion-", "live-check-", "mao-synthetic")
        )
        self.persist = not synthetic or test
        self.event = InteractionEvent(
            provider=identity.get("provider", "local"),
            room_id=self.room,
            actor_id=self.actor,
            session_id=identity["session"],
            source_key=identity.get("source_key"),
            visibility="test"
            if test
            else "public"
            if identity.get("public")
            else "private",
            synthetic=synthetic,
            kind="host_proposal" if host_proposal and not synthetic else "input",
        )
        self.policy = {"revision": 0, "settings": {}}
        self.accepted = False
        self.activity = None
        from ..dialogue.focus import Focus

        self.focus = Focus(self.hybrid.store)
        self.used_profile = False
        self.rejection = "duplicate"
        self.admitted = False
        self._finalization_task = None

    async def admit(self, text=None):
        if text is not None:
            self.event = self.event.model_copy(update={"content": str(text)[:16000]})
        self.accepted = not self.persist or await asyncio.to_thread(
            self.journal.accept, self.event, self.delivery, False
        )
        self.admitted = True
        return self.accepted

    async def begin(self, text=None):
        if not self.admitted:
            await self.admit(text)
        if not self.accepted:
            return False
        if self.persist:
            if not await asyncio.to_thread(self.journal.start, self.delivery):
                return False
        self.policy = (
            await asyncio.to_thread(
                self.development.effective, self.room, self.actor, self.event.visibility
            )
            if self.persist
            else {"revision": 0, "settings": {}}
        )
        proactive = bool(
            self.metadata.get("proactive_speak")
            or self.metadata.get("narration_speech")
        )
        waiting = (
            self.persist
            and proactive
            and await asyncio.to_thread(self.focus.room_waiting, self.room)
        )
        if proactive and (
            waiting or self.policy["settings"].get("initiative") == "wait"
        ):
            self.rejection = "declined_policy"
            await self.finish("rejected")
            return False
        self.context.mao_delivery = self.delivery
        self.context.mao_turn_session = self
        seen = getattr(self.context, "mao_seen_modalities", set())
        self.delivery.phase = "warm" if self.delivery.modality in seen else "first_use"
        self.context.mao_seen_modalities = seen | {self.delivery.modality}
        return True

    async def input(self, text):
        self.used_profile = True
        self.event = self.event.model_copy(update={"content": text[:16000]})
        if self.persist:
            await asyncio.to_thread(self.journal.transcribed, self.event, text)
        original_settings = self.policy["settings"]
        boundaries = {}
        if self.persist and self.event.kind == "input":
            await asyncio.to_thread(self.focus.input, self.event.event_id, text)
            from ..experience.claims import lasting_boundary, explicit_address_request

            if self.event.visibility != "public" and explicit_address_request(
                text[:4000]
            ):
                await asyncio.to_thread(
                    self.experiences.add_item,
                    self.event.event_id,
                    text[:4000],
                    "user_preference",
                    item_key="preference:address",
                )

            if lasting_boundary(text):
                await asyncio.to_thread(
                    self.experiences.add_item,
                    self.event.event_id,
                    text[:4000],
                    "user_preference",
                    item_key="boundary:humor",
                )
            boundaries = await asyncio.to_thread(
                self.experiences.boundaries,
                self.room,
                self.actor,
                self.event.visibility,
            )
        from ..dialogue.policy import requested_settings

        requested = requested_settings({**original_settings, **boundaries}, text)
        self.policy = {**self.policy, "settings": requested}
        if self.policy.get("revision") and any(
            requested.get(key) != value for key, value in original_settings.items()
        ):
            self.policy["revision"] = 0
        if self.persist and self.event.kind == "input":
            if re.search(
                r"/story\s+start|cùng.{0,20}(?:kể|viết).{0,20}(?:truyện|chuyện)",
                text,
                re.I,
            ):
                self.activity = await asyncio.to_thread(
                    self.activities.start, self.event.event_id
                )
            else:
                active = await asyncio.to_thread(
                    self.activities.context,
                    self.room,
                    self.actor,
                    self.event.visibility,
                )
                self.activity = (
                    active[0]
                    if active and active[0]["status"] in {"accepted", "running"}
                    else None
                )
            if re.search(
                r"để lần sau|kể tiếp sau|chưa xong|continue later", text, re.I
            ):
                await asyncio.to_thread(
                    self.experiences.open_thread, self.event.event_id, text[:500]
                )
            if re.search(r"đã hiểu|xong rồi|resolved|all done", text, re.I):
                await asyncio.to_thread(
                    self.experiences.acknowledge_threads, self.room, self.actor
                )
        return {
            "event_id": str(self.event.event_id),
            "room_id": self.room,
            "actor_id": self.actor,
            "visibility": self.event.visibility,
            "session_id": self.event.session_id,
            "synthetic": self.event.synthetic,
            "policy": self.policy,
            "source_text": text[:16000] if self.event.kind == "input" else "",
        }

    async def send(self, message, original):
        data = json.loads(message)
        if self.delivery.state != "running":
            return
        data["visibility"] = self.event.visibility
        if self.event.visibility == "private":
            data["recipient_actor_id"] = self.actor
        kind = data.get("type")
        if kind == "audio" and data.get("audio"):
            if self.persist and self.accepted:
                await asyncio.to_thread(self.journal.touch, self.delivery)
            data.update(
                self.delivery.segment(
                    str((data.get("display_text") or {}).get("text", ""))
                )
            )
        elif kind == "backend-synth-complete":
            data.update(
                turn_id=self.delivery.turn_id,
                generation_epoch=self.delivery.epoch,
                segment_ids=list(self.delivery.segments),
            )
        elif kind == "error":
            self.delivery.metrics["errors"] = self.delivery.metrics.get("errors", 0) + 1
        elif kind == "audio" and data.get("synthesis_error"):
            self.delivery.metrics["errors"] = self.delivery.metrics.get("errors", 0) + 1
        data.setdefault("turn_id", self.delivery.turn_id)
        data.setdefault("generation_epoch", self.delivery.epoch)
        if kind == "control" and data.get("text") == "conversation-chain-end":
            try:
                await self.finish(
                    "interrupted" if asyncio.current_task().cancelling() else None
                )
            except Exception:
                data["durability"] = "unknown"
                await original(json.dumps(data))
                raise
        await original(json.dumps(data))

    async def finish(self, status=None):
        if self._finalization_task is None:
            self._finalization_task = asyncio.create_task(self._finish(status))
        try:
            return await asyncio.shield(self._finalization_task)
        except asyncio.CancelledError:
            # Disconnect must not tear the delivery/fiction commit in half.
            while not self._finalization_task.done():
                try:
                    await asyncio.shield(self._finalization_task)
                except asyncio.CancelledError:
                    continue
            self._finalization_task.result()
            raise

    async def _finish(self, status=None):
        self.delivery.finish(status)
        if self.persist and self.accepted:
            await asyncio.to_thread(
                self.journal.finish,
                self.event,
                self.delivery,
                (self.hybrid.profile or {}).get("revision")
                if self.used_profile
                else None,
                self.policy.get("revision", 0),
                self.policy["settings"],
            )
            delivered = " ".join(
                s["content"]
                for s in self.delivery.segments.values()
                if s["status"] == "completed"
            )
            if delivered and self.event.kind == "input":
                try:
                    await asyncio.to_thread(
                        self.focus.delivered, self.event.event_id, delivered
                    )
                except ValueError:
                    pass
            if self.activity and self.delivery.state == "completed":
                delivered = " ".join(
                    s["content"]
                    for s in self.delivery.segments.values()
                    if s["status"] == "completed"
                )
                if delivered:
                    await asyncio.to_thread(
                        self.activities.append_delivered,
                        self.activity["id"],
                        self.event.event_id,
                        uuid.uuid5(uuid.UUID(self.delivery.turn_id), "story"),
                        self.activity["revision"],
                        delivered[:2000],
                        bool(
                            re.search(
                                r"/story\s+finish|kết thúc (?:câu chuyện|truyện)",
                                self.event.content or "",
                                re.I,
                            )
                        ),
                    )
        if getattr(self.context, "mao_delivery", None) is self.delivery:
            self.context.mao_delivery = None


async def run_single(context, send, client_uid, user_input, invoke, metadata=None):
    metadata = {
        **(metadata or {}),
        "_modality": "text" if isinstance(user_input, str) else "voice",
    }
    turn = (metadata or {}).get("_admitted_turn") or TurnSession(
        context, client_uid, metadata
    )
    async with coordinator(turn.store.scope).floor(client_uid):
        original = send
        token = current_delivery.set(turn.delivery)
        try:
            if not await turn.begin(
                user_input if isinstance(user_input, str) else None
            ):
                identity = unseal(turn.metadata.get("_host_ingress")) or {}
                await send(
                    json.dumps(
                        {
                            "type": "input-status",
                            "status": turn.rejection,
                            "event_id": identity.get("source_key")
                            or str(turn.event.event_id),
                        }
                    )
                )
                return ""

            async def wrapped(message):
                await turn.send(message, original)

            return await invoke(wrapped, turn)
        except asyncio.CancelledError:
            await asyncio.shield(turn.finish("interrupted"))
            raise
        except Exception:
            await turn.finish("failed")
            raise
        finally:
            try:
                if turn.delivery.state == "running":
                    await turn.finish()
            finally:
                current_delivery.reset(token)
