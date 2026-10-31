"""One output owner, bounded proposals, explicit overflow, deadlines and aging."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import time
from weakref import WeakKeyDictionary

PRIORITY = {"direct": 0, "activity": 1, "proactive": 2, "research": 3}


@dataclass
class Proposal:
    kind: str
    run: object
    notify: object
    created: float = field(default_factory=time.monotonic)
    deadline: float = 0
    owner: str = ""


class RoomCoordinator:
    def __init__(self, limit=20):
        self.limit = limit
        self.pending = []
        self.worker = None
        self.active = None
        self.floor_lock = asyncio.Lock()
        self.owner = None
        self.accepted = self.rejected = self.completed = 0
        self.shadow_inputs = 0

    @asynccontextmanager
    async def floor(self, owner):
        async with self.floor_lock:
            self.owner = owner
            try:
                yield
            finally:
                self.owner = None

    async def _notify(self, proposal, status):
        try:
            await proposal.notify(status)
            return True
        except Exception:
            return False

    async def submit(self, proposal):
        if proposal.kind not in PRIORITY:
            raise ValueError("Unknown proposal kind")
        if proposal.kind == "direct":
            for old in self.pending[:]:
                if old.kind in {"research", "proactive"}:
                    self.pending.remove(old)
                    await self._notify(old, "superseded")
        if len(self.pending) >= self.limit:
            self.rejected += 1
            await self._notify(proposal, "rejected_busy")
            return False
        self.pending.append(proposal)
        self.accepted += 1
        if not await self._notify(proposal, "accepted"):
            self.pending.remove(proposal)
            await self._notify(proposal, "failed")
            return False
        if not self.worker or self.worker.done():
            self.worker = asyncio.create_task(self.drain())
        return True

    async def drain(self):
        while self.pending:
            now = time.monotonic()
            proposal = min(
                self.pending,
                key=lambda p: (
                    max(-0.5, PRIORITY[p.kind] - (now - p.created) / 60),
                    p.created,
                ),
            )
            self.pending.remove(proposal)
            if proposal.deadline and proposal.deadline < now:
                await self._notify(proposal, "expired")
                continue
            self.active = asyncio.create_task(proposal.run())
            self.active_owner = proposal.owner
            try:
                await self.active
                self.completed += 1
            except asyncio.CancelledError:
                await self._notify(proposal, "interrupted")
            except Exception:
                await self._notify(proposal, "failed")
            finally:
                self.active = None

    async def interrupt(self, owner):
        for proposal in self.pending[:]:
            if proposal.owner == owner:
                self.pending.remove(proposal)
                await self._notify(proposal, "interrupted")
        if self.active and self.active_owner == owner:
            self.active.cancel()
            await asyncio.gather(self.active, return_exceptions=True)

    def snapshot(self):
        return {
            "queued": len(self.pending),
            "owner": self.owner,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "completed": self.completed,
            "shadow_inputs": self.shadow_inputs,
        }


_ROOMS = WeakKeyDictionary()


def coordinator(scope):
    # All rooms using the physical speaker share a floor in the current process.
    key = asyncio.get_running_loop()
    if key not in _ROOMS:
        _ROOMS[key] = RoomCoordinator()
    return _ROOMS[key]
