"""Apply affect to real speech/avatar output, using existing provider capabilities."""

from dataclasses import replace

from .emotion import normalize_state, response_policy


def regulate_communication(speech, actions, settings, model=None):
    if settings.get("humor") != "gentle":
        return speech, actions
    speech = replace(
        speech,
        mood="gentle" if speech.mood not in {"solemn", "proud"} else speech.mood,
        native_cue=None,
    )
    if model and actions:
        actions = replace(
            actions,
            expressions=model.extract_emotion("[neutral]"),
            motions=[
                m
                for m in (actions.motions or [])
                if m not in {"smirk", "laugh", "joy", "shy", "surprise"}
            ]
            or None,
        )
    return speech, actions


def regulate_expression(speech, actions, state, model=None, *, explicit_neutral=False):
    from ..tts.prosody import SpeechProsody

    # Pin the prepared snapshot so attention does not expire halfway through output.
    snapshot_at = state.get("decayed_at") if isinstance(state, dict) else None
    state = normalize_state(state, now=snapshot_at)
    policy = response_policy(state, now=snapshot_at)
    if not policy["allow_humor"]:
        # Respectful sentence-level plans remain authoritative for solemn subjects.
        if speech.mood not in {"solemn", "proud"}:
            speech = SpeechProsody(
                "gentle" if policy["strategy"] == "support" else "neutral",
                0.96 if policy["strategy"] == "support" else 1.0,
                140,
            )
        else:
            speech = replace(speech, native_cue=None)
        if model:
            actions = replace(
                actions,
                expressions=model.extract_emotion("[neutral]"),
                motions=[
                    m
                    for m in (actions.motions or [])
                    if m not in {"smirk", "laugh", "joy", "shy", "surprise"}
                ]
                or None,
            )
        return speech, actions
    if explicit_neutral:
        return speech, actions
    profiles = {
        "warm": ("warm", 1.02, 80, "joy"),
        "curious": ("curious", 0.98, 100, "surprise"),
        "thoughtful": ("neutral", 0.98, 120, "neutral"),
        "attentive": ("neutral", 0.98, 100, "neutral"),
    }
    profile = profiles.get(state["mode"])
    if profile and speech.mood == "neutral":
        mood, tempo, pause, tag = profile
        speech = replace(speech, mood=mood, tempo=tempo, pause_ms=pause)
        if model and not actions.expressions:
            actions = replace(
                actions, expressions=model.extract_emotion("[" + tag + "]")
            )
    return speech, actions
