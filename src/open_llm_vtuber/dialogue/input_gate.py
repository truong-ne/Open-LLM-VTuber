"""Screen microphone speech before it becomes a conversational turn.

The recognizer transcribes every voice in the room. Without speaker
identification this cannot tell who is talking, but it can cheaply drop what is
clearly not an utterance addressed to Mao: clicks, quiet far-away sound, known
Whisper artefacts on noise, runaway repetition and (optionally) speech that
does not name Mao outside an active conversation.

Pure functions plus one small stateful class; no model, network or database.
"""

import re
import time
from dataclasses import dataclass

import numpy as np

from ..agent.hybrid.config import HybridConfig
from ..character.appraisal import folded

SAMPLE_RATE = 16000
FRAME = 320  # 20 ms

# Phrases Whisper invents on silence/noise (accent-folded). A person addressing
# Mao does not say these, so matching one is treated as an artefact.
HALLUCINATIONS = (
    "hay subscribe cho kenh",
    "hay dang ky kenh",
    "dang ky kenh de",
    "de khong bo lo nhung video",
    "ghien mi go",
    "cam on cac ban da xem",
    "cam on da xem video",
    "cam on cac ban da theo doi",
    "hen gap lai cac ban trong nhung video",
    "like va share",
    "amara.org",
    "subtitles by",
    "thanks for watching",
    "thank you for watching",
    "vietsub",
)


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str = ""


ACCEPTED = Verdict(True)


def speech_level(audio):
    """RMS of the loudest half of 20 ms frames, so padding silence is ignored."""
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    frames = audio.size // FRAME
    if frames < 1 or not np.all(np.isfinite(audio)):
        return 0.0
    energy = np.sqrt(
        np.mean(audio[: frames * FRAME].reshape(frames, FRAME) ** 2, axis=1)
    )
    loud = np.sort(energy)[frames // 2 :]
    return float(np.sqrt(np.mean(loud**2)))


def looks_like_hallucination(text):
    value = folded(text)
    return any(phrase in value for phrase in HALLUCINATIONS)


def looks_repetitive(text):
    """A recognizer stuck in a loop: one word repeated many times in a row."""
    words = re.findall(r"\w+", folded(text))
    if len(words) < 6:
        return False
    run = best = 1
    for before, after in zip(words, words[1:]):
        run = run + 1 if before == after else 1
        best = max(best, run)
    return best >= 5 or max(map(words.count, set(words))) / len(words) >= 0.7


def gate_for(context):
    """One gate per connection (it remembers when Mao was last addressed)."""
    hybrid = getattr(getattr(context, "agent_engine", None), "_hybrid", None)
    config = getattr(hybrid, "config", None)
    if not (
        isinstance(config, HybridConfig) and config.enabled and config.input_gate.enabled
    ):
        return None
    gate = getattr(context, "mao_input_gate", None)
    if gate is None or gate.config != config.input_gate:
        gate = context.mao_input_gate = InputGate(config.input_gate)
    return gate


class InputGate:
    def __init__(self, config, clock=time.monotonic):
        self.config = config
        self.clock = clock
        self.last_accepted = None

    def screen_audio(self, audio):
        """Cheap checks on the waveform; run before the recognizer."""
        if not self.config.enabled:
            return ACCEPTED
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        seconds = audio.size / SAMPLE_RATE
        if seconds < self.config.min_seconds:
            return Verdict(False, f"too_short:{seconds:.2f}s")
        level = speech_level(audio)
        if self.config.min_rms and level < self.config.min_rms:
            return Verdict(False, f"too_quiet:{level:.4f}")
        return ACCEPTED

    def addressed(self, text):
        words = set(re.findall(r"\w+", folded(text)))
        return any(folded(word) in words for word in self.config.wake_words)

    def screen_text(self, text):
        """Checks on the transcript; a pass counts as an accepted utterance."""
        if not self.config.enabled:
            return ACCEPTED
        if not re.search(r"\w", text or ""):
            return Verdict(False, "empty")
        if self.config.drop_hallucinations and (
            looks_like_hallucination(text) or looks_repetitive(text)
        ):
            return Verdict(False, "recognizer_artefact")
        now = self.clock()
        if self.config.require_wake_word and not self.addressed(text):
            recent = (
                self.last_accepted is not None
                and now - self.last_accepted <= self.config.follow_up_seconds
            )
            if not recent:
                return Verdict(False, "not_addressed")
        self.last_accepted = now
        return ACCEPTED
