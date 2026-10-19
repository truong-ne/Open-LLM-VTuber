"""Bound unsolicited VTuber speech before it reaches subtitles, TTS or memory."""

import json
import re

from .input_types import TextSource

HOST_PREFIX = "[Mao chủ động mở chuyện khi chat yên; đây không phải bình luận khán giả]"
SHORT_STYLES = frozenset(
    ("chat", "activity", "followup", "question", "initiative", "support")
)


def proactive_style(input_data):
    """Only the host's structured turn opts into short speech; real chat is untouched."""
    for item in input_data.texts:
        if item.source != TextSource.INPUT or not item.content.startswith(HOST_PREFIX):
            continue
        try:
            context = json.loads(item.content.rsplit("\n", 1)[-1])["live_context"]
            style = context["style"]
            return style if style in SHORT_STYLES else None
        except (ValueError, KeyError, TypeError):
            return None
    return None


def limit_proactive_reply(text, style):
    # Keep decimal points and punctuation inside pose/body tags intact.
    tags = []

    def protect(match):
        tags.append(match[0])
        return f"\ue000{len(tags) - 1}\ue001"

    protected = re.sub(r"\[[^\]\r\n]*\]", protect, text)
    sentences = re.split(r"(?<=[.!?…。！？])\s+|[\r\n]+", protected.strip())
    accepted = []
    words = 0
    closed = False
    last_kept = False
    for sentence in sentences:
        spoken = re.sub(r"\ue000\d+\ue001", "", sentence).strip()
        if not spoken:
            if accepted and last_kept:
                accepted[-1] += " " + sentence.strip()
            continue
        last_kept = False
        if closed:
            continue
        # A truncated or unfinished tail is never spoken as a dangling clause.
        if spoken[-1:] not in ".!?…。！？\"”'":
            continue
        is_question = "?" in spoken or "？" in spoken
        if is_question and style not in ("question", "initiative"):
            continue
        count = len(spoken.split())
        if words + count > 60:
            closed = True
            continue
        accepted.append(sentence.strip())
        last_kept = True
        words += count
        if len(accepted) >= 3 or is_question:
            closed = True
    result = " ".join(accepted)
    return re.sub(r"\ue000(\d+)\ue001", lambda m: tags[int(m[1])], result)


async def collect_proactive_reply(stream, style):
    """Buffer these short turns so rejected sentences cannot start speaking first."""
    text = ""
    try:
        async for event in stream:
            if isinstance(event, str):
                text += event
            elif isinstance(event, dict) and event.get("type") == "text_delta":
                text += event.get("text", "")
            if len(text) >= 2400:
                # Retain complete earlier sentences, discard the unbounded tail.
                text = text[:2400].rsplit(" ", 1)[0]
                break
    finally:
        if hasattr(stream, "aclose"):
            await stream.aclose()
    return limit_proactive_reply(text, style)
