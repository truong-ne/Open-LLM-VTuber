import time
from typing import Literal
import uuid
from contextvars import ContextVar

from pydantic import BaseModel, ConfigDict, Field

current_delivery = ContextVar("mao_delivery", default=None)


class InteractionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    schema_version: Literal[1] = 1
    room_id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    provider: Literal["local", "proxy", "host"] = "local"
    kind: Literal["input", "host_proposal"] = "input"
    source_key: str | None = Field(default=None, min_length=1, max_length=150)
    visibility: Literal["private", "public", "test"] = "private"
    synthetic: bool = False
    content: str | None = Field(default=None, max_length=16000)


class DeliveryTracker:
    def __init__(self):
        self.turn_id = str(uuid.uuid4())
        self.epoch = str(uuid.uuid4())
        self.segments = {}
        self.state = "running"
        self.started = time.monotonic()
        self.metrics = {}
        self.modality = "text"
        self.phase = "first_use"

    def segment(self, text):
        identifier = str(uuid.uuid4())
        self.segments[identifier] = {
            "id": identifier,
            "content": text[:4000],
            "status": "sent",
        }
        self.metrics.setdefault(
            "first_audio_ms", (time.monotonic() - self.started) * 1000
        )
        return {
            "turn_id": self.turn_id,
            "generation_epoch": self.epoch,
            "segment_id": identifier,
        }

    def ack(self, payload):
        if (
            payload.get("turn_id") != self.turn_id
            or payload.get("generation_epoch") != self.epoch
            or self.state != "running"
        ):
            return False
        segment = self.segments.get(payload.get("segment_id"))
        status = payload.get("status")
        if not segment or status not in {"started", "completed", "failed"}:
            return False
        if segment["status"] in {"completed", "failed", "interrupted"}:
            return status == segment["status"]
        segment["status"] = status
        return True

    def finish(self, status=None):
        if self.state != "running":
            return self.state
        statuses = [s["status"] for s in self.segments.values()]
        self.state = status or (
            "failed"
            if self.metrics.get("errors", 0)
            else (
                "failed"
                if "failed" in statuses
                else "completed"
                if statuses and all(s == "completed" for s in statuses)
                else "unknown"
            )
        )
        for segment in self.segments.values():
            if segment["status"] not in {"completed", "failed"}:
                segment["status"] = (
                    "interrupted" if self.state == "interrupted" else "unknown"
                )
        self.metrics["duration_ms"] = (time.monotonic() - self.started) * 1000
        return self.state
