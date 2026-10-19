"""Small per-sentence reading plans; no invented TTS emotion API or pitch shift."""

import re
from dataclasses import dataclass, replace


NATIVE_CUES = {"cười", "thở dài", "hắng giọng"}
CUE_PATTERN = re.compile(r"\[(cười|thở dài|hắng giọng)\]", re.IGNORECASE)


@dataclass(frozen=True)
class SpeechProsody:
    mood: str = "neutral"
    tempo: float = 1.0
    pause_ms: int = 0
    native_cue: str | None = None


def plan_speech(text: str) -> SpeechProsody:
    """Prefer the model's explicit intent; use modest text-based fallbacks."""
    tags = re.findall(r"\[([^\[\]]+)\]", text.casefold())
    cue = next((tag for tag in tags if tag in NATIVE_CUES), None)
    # Respectful subjects override an accidental smile/laugh emitted by the LLM.
    if re.search(
        r"\b(tưởng niệm|hy sinh|hi sinh|liệt sĩ|mất mát|chia buồn|qua đời)\b",
        text,
        re.I,
    ):
        return SpeechProsody("solemn", 0.95, 180)
    if re.search(r"\b(tự hào|biết ơn|quê hương|yêu nước)\b", text, re.I):
        return SpeechProsody("proud", 0.98, 140)
    moods = {
        "sadness": ("gentle", 0.92, 180),
        "sad": ("gentle", 0.92, 180),
        "fear": ("gentle", 0.92, 180),
        "shy": ("bashful", 0.94, 170),
        "smirk": ("playful", 0.98, 110),
        "joy": ("bright", 1.06, 80),
        "surprise": ("curious", 0.97, 150),
        "surprised": ("curious", 0.97, 150),
        "tilt": ("curious", 0.97, 150),
        "refuse": ("firm", 1.0, 140),
        "anger": ("firm", 1.0, 100),
        "neutral": ("neutral", 1.0, 0),
    }
    for tag in tags:
        if tag in moods:
            mood, tempo, pause = moods[tag]
            return SpeechProsody(mood, tempo, pause, cue)
    if re.search(
        r"\b(mình nghe|mình hiểu|không sao|buồn|mệt mỏi|chia buồn|tiếc quá|tiếc ghê)\b",
        text,
        re.I,
    ):
        return SpeechProsody("gentle", 0.92, 180, cue)
    if re.search(r"\b(ngại quá|ngượng|mắc cỡ)\b", text, re.I):
        return SpeechProsody("bashful", 0.94, 170, cue)
    if re.search(r"\b(trêu|ngọt thế|ghẹo)\b", text, re.I):
        return SpeechProsody("playful", 0.98, 110, cue)
    if re.search(r"\b(vui quá|hay quá|tuyệt quá|thích quá|chúc mừng)\b", text, re.I):
        return SpeechProsody("bright", 1.06, 80, cue)
    if "?" in text:
        return SpeechProsody("curious", 0.97, 150, cue)
    if re.search(r"\b(cảm ơn|xin chào|hi|chào|mới ghé)\b", text, re.I):
        return SpeechProsody("warm", 0.98, 100, cue)
    return SpeechProsody(native_cue=cue)


def hide_native_cues(text: str) -> str:
    return CUE_PATTERN.sub("", text).strip()


class TurnSpeechPlanner:
    """Carry a modest reading intention across two untagged follow-up sentences.

    Instantiate for each output stream: never carry moods between viewers/turns,
    and never replay a native cue on another sentence.
    """

    def __init__(self):
        self.previous = SpeechProsody()
        self.remaining = 0

    def plan(self, text: str) -> SpeechProsody:
        speech = plan_speech(text)
        if "[neutral]" in text.casefold():
            self.remaining = 0
            return speech
        if speech.mood != "neutral":
            self.previous = replace(speech, native_cue=None)
            self.remaining = 2
            return speech
        if self.remaining:
            strength = self.remaining / 2
            self.remaining -= 1
            return replace(
                self.previous,
                tempo=1 + (self.previous.tempo - 1) * strength,
                pause_ms=round(self.previous.pause_ms * strength),
                native_cue=(
                    None
                    if self.previous.mood in {"solemn", "gentle", "proud"}
                    else speech.native_cue
                ),
            )
        return speech
