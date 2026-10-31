"""Host-issued pseudonymous identity; nicknames and client claims grant no rights."""

import base64
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import uuid

ROOT = Path(__file__).resolve().parents[3]


def key():
    path = ROOT / "private/mao-ingress.key"
    path.parent.mkdir(exist_ok=True)
    try:
        with path.open("xb") as file:
            file.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    value = path.read_bytes()
    if len(value) != 32:
        raise ValueError("Invalid host ingress key")
    return value


def issue_actor():
    actor = "guest:" + uuid.uuid4().hex
    body = base64.urlsafe_b64encode(
        json.dumps({"actor": actor, "version": 1}).encode()
    ).decode()
    return body + "." + hmac.new(key(), body.encode(), hashlib.sha256).hexdigest()


def verify_actor(token):
    if not isinstance(token, str) or len(token) > 512:
        return None
    try:
        body, signature = token.split(".")
        if not hmac.compare_digest(
            signature, hmac.new(key(), body.encode(), hashlib.sha256).hexdigest()
        ):
            return None
        value = json.loads(base64.urlsafe_b64decode(body))
        actor = value["actor"]
        return (
            actor
            if value["version"] == 1
            and isinstance(actor, str)
            and actor.startswith("guest:")
            and len(actor) == 38
            else None
        )
    except (ValueError, KeyError, TypeError):
        return None


def seal(actor, session, source_key=None, public=False, room="local", provider="local"):
    value = {
        "actor": actor,
        "session": session,
        "source_key": source_key,
        "public": bool(public),
        "room": room,
        "provider": provider,
    }
    body = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return {
        "value": value,
        "signature": hmac.new(key(), body.encode(), hashlib.sha256).hexdigest(),
    }


def control_token(profile):
    return hmac.new(
        key(), ("local-control:v1:" + profile).encode(), hashlib.sha256
    ).hexdigest()


def _proposal_body(message):
    if message.get("type") != "text-input" or message.get("source") not in {
        "mao-idle-host",
        "vua-tieng-viet",
    }:
        raise ValueError("Unsupported host proposal")
    value = {
        name: message[name]
        for name in (
            "type",
            "source",
            "event_id",
            "text",
            "narration_speech",
            "game_speech",
            "game_round_id",
            "game_kind",
        )
        if name in message
    }
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(body) > 20000:
        raise ValueError("Host proposal exceeds size limit")
    return b"host-proposal:v1:" + body


def sign_host_proposal(message):
    value = {**message, "event_id": message.get("event_id") or uuid.uuid4().hex}
    value["host_proof"] = hmac.new(
        key(), _proposal_body(value), hashlib.sha256
    ).hexdigest()
    return value


def verify_host_proposal(message):
    try:
        proof = message.get("host_proof")
        return (
            isinstance(proof, str)
            and len(proof) == 64
            and hmac.compare_digest(
                proof,
                hmac.new(key(), _proposal_body(message), hashlib.sha256).hexdigest(),
            )
        )
    except (ValueError, TypeError):
        return False


def unseal(value):
    try:
        body = json.dumps(value["value"], sort_keys=True, separators=(",", ":"))
        if hmac.compare_digest(
            value["signature"],
            hmac.new(key(), body.encode(), hashlib.sha256).hexdigest(),
        ):
            return value["value"]
    except (TypeError, KeyError, ValueError):
        pass
    return None
