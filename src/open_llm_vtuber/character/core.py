"""Operator-owned core. Development has no write API for this layer."""

import hashlib
from .identity import identity_prompt


def core_revision(profile):
    return {
        "revision": profile.get("revision"),
        "digest": hashlib.sha256(identity_prompt(profile).encode()).hexdigest(),
    }
