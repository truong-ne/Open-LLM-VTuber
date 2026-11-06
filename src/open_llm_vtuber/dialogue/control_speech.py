"""Keep quiet/resume acknowledgements short without rewriting quoted pronouns."""

import re

from ..agent.proactive_reply import limit_proactive_reply
from ..character.appraisal import folded
from .listening import collect_speech_text


def limit_control_reply(text, mode):
    if mode not in {"quiet", "resume"}:
        raise ValueError("Unsupported conversation control")
    short = limit_proactive_reply(text, "support", max_words=35)
    for sentence in re.split(r"(?<=[.!…。！])\s+|[\r\n]+", short):
        if not sentence.strip():
            continue
        if re.search(
            r"\b(?:ai vtuber|tri tue nhan tao|moi truong ao|co the sinh hoc|ky uc|so thich|du lieu|he thong)\b",
            folded(sentence),
        ) or re.search(r"\blà (?:một )?AI\b", sentence):
            continue
        return sentence.strip()
    return "Được rồi."


async def collect_control_reply(stream, mode):
    return limit_control_reply(await collect_speech_text(stream), mode)
