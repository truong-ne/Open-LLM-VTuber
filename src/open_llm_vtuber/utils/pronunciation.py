"""Operator-requested spoken names; keep display text and real acronyms intact."""

import re

KAITO_KID = re.compile(r"(?<!\w)kaito\s+kid(?!\w)", re.IGNORECASE)

CUA_BIET_DI = re.compile(
    r"(?<!\w)cửa\s*biết\s*đi\s*nhà\s*biết\s*bay\s*sân\s*biết\s*bò(?!\w)(?:🪽)?",
    re.IGNORECASE,
)


def normalize_spoken_names(text: str) -> str:
    # VieNeu treats ALL CAPS as an acronym before its English G2P runs.
    # Title case keeps the words intact so it produces /kaɪɾoʊ kɪd/.
    text = KAITO_KID.sub("Kaito Kid", text)
    return CUA_BIET_DI.sub("Cửa biết đi, nhà biết bay, sân biết bò", text)
