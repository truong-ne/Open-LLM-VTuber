"""Local, session-bound bridge to the sandboxed Wesnoth Lua add-on."""

import asyncio
import json
from pathlib import Path
import re
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "private/wesnoth"
PREFIX = "MAO_WESNOTH_V1 "
SESSION = re.compile(r"^[a-f0-9]{32}$")
REQUEST = re.compile(r"^[0-9]+:[0-9]+:[0-9]+$")
ACTION = re.compile(r"^a[0-9]{1,3}$")


def write_text(path, value, *, encoding="utf-8"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(value, encoding=encoding)
    try:
        for attempt in range(10):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.02)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False))


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 100_000:
        raise ValueError("Oversized Wesnoth bridge record")
    return json.loads(path.read_text(encoding="utf-8"))


class WesnothBridge:
    def __init__(self, directory=BRIDGE):
        self.directory = Path(directory)

    def observe(self):
        try:
            state = read_json(self.directory / "state.json")
        except FileNotFoundError:
            return {"status": "not_running"}
        if not SESSION.fullmatch(str(state.get("session", ""))):
            raise ValueError("Invalid Wesnoth session")
        if not REQUEST.fullmatch(str(state.get("request_id", ""))):
            raise ValueError("Invalid Wesnoth request")
        if state.get("status") == "finished" and state.get("outcome") in {
            "victory", "defeat", "turn_limit"
        }:
            return state
        if time.time() >= state.get("expires_at", 0):
            return {"status": "expired", "request_id": state["request_id"]}
        return {"status": "awaiting_action", **state}

    def choose(self, session, request_id, action_id):
        if not SESSION.fullmatch(session) or not REQUEST.fullmatch(request_id):
            raise ValueError("Invalid session or request ID")
        if not ACTION.fullmatch(action_id):
            raise ValueError("Invalid action ID")
        state = self.observe()
        if (
            state.get("status") != "awaiting_action"
            or state.get("session") != session
            or state.get("request_id") != request_id
        ):
            raise PermissionError("Wesnoth state expired or changed; observe again")
        if action_id not in {a["id"] for a in state.get("actions", [])}:
            raise ValueError("Action is not in the game's current legal-action list")
        claim = self.directory / "claims" / session / request_id.replace(":", "-")
        claim.parent.mkdir(parents=True, exist_ok=True)
        duplicate = False
        try:
            with claim.open("x", encoding="ascii") as file:
                file.write(action_id)
        except FileExistsError:
            if claim.read_text(encoding="ascii") != action_id:
                raise PermissionError("A different action was already submitted")
            duplicate = True
        write_json(
            self.directory / "command.json",
            {"session": session, "request_id": request_id, "action_id": action_id},
        )
        return {
            "status": "already_submitted" if duplicate else "submitted",
            "request_id": request_id,
            "action_id": action_id,
        }

    async def execute(self, arguments, *, wait_seconds=8):
        if arguments["action"] == "observe":
            return await asyncio.to_thread(self.observe)
        result = await asyncio.to_thread(
            self.choose,
            arguments["session"],
            arguments["request_id"],
            arguments["action_id"],
        )
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            try:
                acknowledgement = await asyncio.to_thread(
                    read_json, self.directory / "result.json"
                )
                if (
                    acknowledgement.get("session") == arguments["session"]
                    and acknowledgement.get("request_id") == arguments["request_id"]
                    and acknowledgement.get("action_id") == arguments["action_id"]
                ):
                    return acknowledgement
            except FileNotFoundError:
                pass
            await asyncio.sleep(0.1)
        return {**result, "confirmed": False, "note": "Await game acknowledgement"}
