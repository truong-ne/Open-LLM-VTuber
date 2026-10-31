"""Bounded appraisals. Text rules are a fallback, not a mood detector."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Cue = Literal[
    "conversation",
    "listen",
    "welcome",
    "question",
    "celebrate",
    "repair",
    "verify",
    "boundary",
    "playful",
]
Kind = Literal[
    "conversation",
    "support",
    "greeting",
    "question",
    "celebration",
    "correction",
    "uncertain",
    "boundary",
    "task_success",
    "task_failure",
    "study_started",
    "source_explained",
    "lesson_saved",
]


class Appraisal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    kind: Kind = "conversation"
    cue: Cue = "conversation"
    source: Literal["user_text", "host_result", "background"] = "user_text"
    confidence: float = Field(0.35, ge=0, le=1)
    relevance: float = Field(0.4, ge=0, le=1)
    congruence: float = Field(0, ge=-1, le=1)
    controllability: float = Field(0.5, ge=0, le=1)
    certainty: float = Field(0.5, ge=0, le=1)
    novelty: float = Field(0, ge=0, le=1)
    urgency: float = Field(0, ge=0, le=1)


def folded(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", str(text).casefold())
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


def direct_text(text):
    """Remove quoted/code/reported clauses before interpreting personal signals."""
    text = str(text or "")[:3000]
    direct = re.sub(r"```[\s\S]*?```|`[^`]*`|[\"“][^\"”]*[\"”]|‘[^’]*’", " ", text)
    value = folded(direct)
    # Ignore reported clauses unless the clause starts with an explicit request.
    report_pattern = r"\b(?:nhan vat|trong truyen|trong phim|vi du|gia su|dich cau|tac gia|ban toi|co ay|anh ay|he said|she said|character|translate)\b"
    clauses = re.split(r"(?<=[.!?;])\s+|\n", value)
    value = " ".join(
        clause
        for clause in clauses
        if not re.search(report_pattern, clause)
        or re.match(r"\s*(?:mao[, ]*)?(?:hay|dung|nghiem tuc)\b", clause)
    )
    return value


def appraise_text(text):
    value = direct_text(text)
    value = re.sub(
        r"\b(?:khong|chua|chang)(?: can| muon| phai| he)?(?: noi(?: rang)?| bao)?\s+(?:(?:mao|ban)\s+)?(?:tinh sai|tra loi sai|hieu sai|sua lai|kiem tra lai|sai)\b",
        " ",
        value,
    )
    value = re.sub(r"\b(?:not|never|no longer)\s+(?:sad|worried|happy)\b", " ", value)
    if re.search(
        r"\b(?:dung (?:dua|treu|gheo|choc)|nghiem tuc|chi (?:muon|can).{0,18}(?:lang nghe|ke thoi|nghe thoi))\b",
        value,
    ):
        return Appraisal(
            kind="boundary", cue="boundary", confidence=0.95, relevance=1, urgency=0.6
        )
    if re.search(
        r"\b(?:tra loi sai|tinh sai|hieu sai|ban sai|mao sai|sua lai|kiem tra lai|not correct|you are wrong)\b",
        value,
    ):
        return Appraisal(
            kind="correction",
            cue="repair",
            confidence=0.9,
            relevance=1,
            congruence=-0.4,
            certainty=0.25,
            controllability=0.8,
            novelty=0.3,
        )
    if re.search(
        r"\b(?:nghe khong ro|khong nghe ro|chua chac|khong chac chan|not sure|unclear)\b",
        value,
    ):
        return Appraisal(
            kind="uncertain",
            cue="verify",
            confidence=0.85,
            relevance=0.8,
            certainty=0.1,
            novelty=0.4,
        )
    recovered = re.search(
        r"\b(?:het buon|khong con buon|(?:minh|papa|toi) on roi|cu dua|hay dua|treu di)\b",
        value,
    )
    if recovered:
        return Appraisal(
            cue="playful" if re.search(r"dua|treu", recovered[0]) else "conversation",
            confidence=0.8,
            congruence=0.2,
        )
    value = re.sub(
        r"\b(?:khong|chang|chua)(?: he| con| thay| cam thay| phai)?\s+(?:buon|lo lang|kho chiu|vui)\b",
        " ",
        value,
    )
    reported = re.search(
        r"\b(?:nhan vat|trong truyen|trong phim|vi du|gia su|dich cau|tu buon|cau buon|tac gia|ban toi|co ay|anh ay)\b",
        value,
    )
    if not reported and re.search(
        r"\b(?:buon|lo lang|kho chiu|met moi|co don|sad|worried|qua doi|mat mat)\b",
        value,
    ):
        return Appraisal(
            kind="support",
            cue="listen",
            confidence=0.7,
            relevance=0.9,
            congruence=-0.2,
            urgency=0.4,
            certainty=0.45,
        )
    if re.search(
        r"\b(?:lai hong|lai that bai|that vong|tuyet vong|sarcasm|mia mai)\b", value
    ):
        return Appraisal(
            cue="listen",
            kind="support",
            confidence=0.65,
            relevance=0.8,
            congruence=-0.2,
        )
    if not reported and re.search(
        r"\b(?:vui qua|vui lam|toi vui|minh vui|papa vui|thanh cong roi|lam duoc roi|chuc mung|happy|great news)\b",
        value,
    ):
        return Appraisal(
            kind="celebration",
            cue="celebrate",
            confidence=0.75,
            relevance=0.7,
            congruence=0.6,
            novelty=0.3,
        )
    if re.search(r"\b(?:cam on|xin chao|chao mao|hello|thank you)\b", value):
        return Appraisal(kind="greeting", cue="welcome", confidence=0.8, congruence=0.3)
    if "?" in value:
        return Appraisal(
            kind="question",
            cue="question",
            confidence=0.65,
            relevance=0.7,
            novelty=0.5,
            certainty=0.4,
        )
    return Appraisal()


def outcome_appraisal(success):
    if type(success) is not bool:
        raise ValueError("Task outcome must be an observed boolean")
    return Appraisal(
        kind="task_success" if success else "task_failure",
        source="host_result",
        cue="celebrate" if success else "repair",
        confidence=1,
        relevance=1,
        congruence=0.8 if success else -0.8,
        controllability=0.7 if success else 0.4,
        certainty=0.8,
        novelty=0.2,
    )


def background_appraisal(event):
    if event not in {"study_started", "source_explained", "lesson_saved"}:
        raise ValueError("Unsupported background event")
    return Appraisal(
        kind=event,
        source="background",
        confidence=1,
        relevance=0.4,
        novelty=0.4 if event == "study_started" else 0.2,
        congruence=0.2 if event == "lesson_saved" else 0,
    )
