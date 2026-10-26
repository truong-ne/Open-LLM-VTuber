"""Read study narration in sentences, rather than timed game fragments."""

import re
from dataclasses import replace

from ..tts.prosody import TAG_MOODS, TurnSpeechPlanner, hide_native_cues


def narration_chunks(text: str) -> list[str]:
    # Keep a complete thought together. VieNeu handles long sentences itself,
    # including punctuation-aware joins; do not impose the game's 18-word cut.
    return [part.strip() for part in re.split(r'(?<=[.!?])\s+|\n+', text.strip()) if part.strip()]


def narration_text(text: str) -> str:
    text = hide_native_cues(text)
    text = re.sub(
        r'\[([^\[\]]+)\]',
        lambda match: '' if match[1].casefold() in TAG_MOODS else match[0],
        text,
    ).strip()
    return re.sub(r'\s+([,.!?;:…])', r'\1', text)


class NarrationPlanner(TurnSpeechPlanner):
    def plan(self, text):
        speech = super().plan(text)
        if speech.mood == 'neutral':
            return replace(speech, mood='thoughtful', tempo=.98, pause_ms=60)
        return speech
