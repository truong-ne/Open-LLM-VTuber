"""Bound short listening speech before any sentence reaches TTS."""

import re

from ..agent.proactive_reply import limit_proactive_reply
from ..character.appraisal import folded


def requests_more_disclosure(text):
    return bool(
        re.search(
            r"\b(?:hay ke|ke tiep di|ke di|cu ke|ke (?:them|cho).{0,20}(?:nghe|nhe|di)|noi tiep di|(?:cu|hay) (?:thoai mai )?chia se|im lang di)\b",
            folded(text),
        )
    )


def limit_listening_reply(text):
    short = limit_proactive_reply(text, "support", max_words=40)
    parts = re.split(r"(?<=[.!…。！])\s+|[\r\n]+", short)
    accepted = [
        part for part in parts if part.strip() and not requests_more_disclosure(part)
    ]
    return " ".join(accepted).strip() or "Ừm."


async def collect_speech_text(stream):
    text = ""
    try:
        async for event in stream:
            if isinstance(event, str):
                text += event
            elif isinstance(event, dict) and event.get("type") == "text_delta":
                text += event.get("text", "")
            else:
                raise RuntimeError("Unexpected non-speech event in listening response")
            if len(text) >= 2400:
                text = text[:2400].rsplit(" ", 1)[0]
                break
    finally:
        close = getattr(stream, "aclose", None)
        if close:
            await close()
    return text


async def collect_listening_reply(stream):
    return limit_listening_reply(await collect_speech_text(stream))
