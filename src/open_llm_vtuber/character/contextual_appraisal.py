"""Conservative, bounded interpretation of confirmed conversation context.

History is supplied by the host after actor/room/visibility filtering. Neither
stored mood, retrieved claims nor model-generated text is a user self-report.
"""

import re
import time

from .appraisal import Appraisal, appraise_text, direct_text


def appraise_conversation(text, history=(), *, now=None):
    """Use the most recent delivered exchange only for explicit short follow-ups.

    History is newest-first. Ambiguous/unavailable/stale context falls back to the
    current message; instructions and topic changes always take precedence.
    """
    current = appraise_text(text)
    value = direct_text(text)
    if not value.strip():
        return current
    # Explicit current signals are authoritative, including withdrawal of distress.
    if current.kind in {"boundary", "correction", "uncertain", "support"}:
        return current
    if re.search(
        r"\b(?:het buon|khong con buon|on roi|doi chu de|chuyen khac|stop|move on)\b",
        value,
    ):
        return current
    if re.search(r"\b(?:hay qua|gioi qua|tuyet voi|vui qua)\b", value) and re.search(
        r"\b(?:lai sai|lai hong|mat het|hong het|that bai|sai het)\b", value
    ):
        return Appraisal(
            kind="support",
            cue="listen",
            confidence=0.6,
            relevance=0.8,
            congruence=-0.2,
            certainty=0.35,
        )
    if current.kind != "conversation" or current.cue != "conversation":
        return current
    if re.match(
        r"\s*(?:mao[, ]*)?(?:y (?:toi|minh|papa) la|khong phai y (?:toi|minh|papa))\b",
        value,
    ):
        return Appraisal(
            kind="correction",
            cue="repair",
            confidence=0.8,
            relevance=1,
            certainty=0.3,
            controllability=0.8,
        )
    continuation = re.sub(r"[^\w\s]", " ", value).strip()
    continuation = " ".join(continuation.split())
    affirmations = {"u", "co", "dung", "dung roi", "u nhe"}
    negatives = {"khong", "khong nhe", "thoi", "khong can", "khong muon"}
    if continuation not in affirmations | negatives | {
        "van vay",
        "van nhu vay",
        "van chua het",
        "van con",
        "kho noi lam",
        "chang biet noi sao",
        "khong biet nua",
        "ke tiep nhe",
        "cho toi ke tiep",
    }:
        return current
    now = time.time() if now is None else now
    if not isinstance(history, (list, tuple)) or not history:
        return current
    previous = history[0]
    if not isinstance(previous, dict) or previous.get("delivery_status") != "completed":
        return current
    observed = previous.get("observed_at")
    if type(observed) not in (int, float) or not 0 <= now - observed <= 600:
        return current
    question = direct_text(str(previous.get("delivered_response") or "")[:1500])
    # Only a short, single-option question can anchor an elliptical yes/no.
    # An assistant's words alone never become a user feeling or preference.
    single_question = (
        len(question) <= 180
        and question.count("?") == 1
        and not re.search(r"\b(?:hay|hoac|or)\b", question)
        and not re.search(
            r"\b(?:khong (?:muon|can)|chua (?:muon|can)|chang|dung)\b", question
        )
        and re.search(r"\b(?:muon|can)\b", question)
    )
    if single_question and (
        continuation in affirmations
        and re.search(r"\b(?:lang nghe|nghe thoi)\b", question)
        or continuation in negatives
        and re.search(r"\b(?:dua|treu)\b", question)
    ):
        return Appraisal(kind="boundary", cue="boundary", confidence=0.75, relevance=1)
    if continuation in affirmations | negatives:
        return current
    prior = appraise_text(str(previous.get("user_claim") or "")[:1000])
    if prior.kind in {"support", "boundary"}:
        return Appraisal(
            kind="support",
            cue="listen",
            confidence=0.55,
            relevance=0.8,
            congruence=-0.1,
            certainty=0.35,
        )
    return current
