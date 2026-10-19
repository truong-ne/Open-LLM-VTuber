"""Small spoken phrases so timed game announcements do not wait for a monologue."""

import re
import uuid
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

from ..tts.prosody import plan_speech


def game_speech_chunks(text: str, max_words: int = 18) -> list[str]:
    # Keep the clue number with its clue, but release 'Hết giờ!' immediately.
    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        while len(words) > max_words:
            # Prefer a natural clause boundary near the size limit.
            cut = next(
                (
                    i
                    for i in range(max_words, max_words // 2, -1)
                    if words[i - 1].endswith((",", ";", ":"))
                ),
                max_words,
            )
            chunks.append(" ".join(words[:cut]))
            words = words[cut:]
        if words:
            chunks.append(" ".join(words))
    return chunks


def game_speech_prosody(text):
    # A gentle reaction should not slow down the entire result explanation.
    speech = plan_speech(text)
    return replace(
        speech, tempo=max(1.06, speech.tempo), pause_ms=min(60, speech.pause_ms)
    )


class PreparedGameSpeech:
    """Small per-engine WAV cache; prepared files are removed after reading."""

    def __init__(self, engine):
        self.engine = engine
        self.audio = OrderedDict()
        self.supports_prosody = getattr(engine, "supports_prosody", False) is True

    async def prepare(self, script):
        for phrase in game_speech_chunks(script):
            if phrase in self.audio:
                self.audio.move_to_end(phrase)
                continue
            path = None
            try:
                kwargs = (
                    {"prosody": game_speech_prosody(phrase)}
                    if self.supports_prosody
                    else {}
                )
                path = await self.engine.async_generate_audio(
                    phrase,
                    file_name_no_ext=f"game_prepare_{uuid.uuid4().hex}",
                    **kwargs,
                )
                if path and 0 < Path(path).stat().st_size <= 4_000_000:
                    self.audio[phrase] = Path(path).read_bytes()
                    while len(self.audio) > 16:
                        self.audio.popitem(last=False)
            finally:
                if path:
                    self.engine.remove_file(path)

    async def async_generate_audio(self, text, file_name_no_ext=None, **kwargs):
        if text in self.audio:
            self.audio.move_to_end(text)
            path = self.engine.generate_cache_file_name(file_name_no_ext)
            Path(path).write_bytes(self.audio[text])
            return path
        return await self.engine.async_generate_audio(text, file_name_no_ext, **kwargs)

    def remove_file(self, path):
        self.engine.remove_file(path)


def prepared_game_engine(engine):
    cache = getattr(engine, "_mao_word_game_speech", None)
    return cache if isinstance(cache, PreparedGameSpeech) else engine
