"""Opaque storage keys for affect; identity must come from verified ingress."""

import hashlib
import json


def affect_key(*, room=None, actor=None, visibility=None):
    if room is None and actor is None and visibility is None:
        return "affect"
    if (
        not isinstance(room, str)
        or not room
        or len(room) > 256
        or not isinstance(actor, str)
        or not actor
        or len(actor) > 256
        or visibility not in {"private", "public", "test"}
    ):
        raise ValueError("Affect requires a complete verified conversation identity")
    identity = json.dumps([room, actor, visibility], ensure_ascii=False).encode("utf-8")
    return "affect:context:" + hashlib.sha256(identity).hexdigest()
