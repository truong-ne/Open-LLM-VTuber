"""Narrow exact-quote path for unambiguous requests to recall one's own words."""

from datetime import datetime, timezone
import re

from ..character.appraisal import direct_text, folded
from .intent import response_plan

STOP = set(
    "mao papa toi minh ban cua la gi nao da tung noi con nho khong co mot nhung hay cho voi duoc chon cuoi cung hom nay".split()
)


def quoted_recall(text, experience, *, now=None):
    value = direct_text(text)
    if (
        not re.search(r"\b(?:papa|toi|minh)\b", value)
        or not response_plan(text).recall_requested
        or re.search(
            r"\b(?:tai sao|vi sao|dung khong|chinh xac|that khong|kiem chung|"
            r"so sanh|truoc khi|bao nhieu|quyen|quan tri|persona|profile|mat khau|password)\b",
            value,
        )
    ):
        return None
    speaker = experience.get("speaker", {})
    if not all(speaker.get(key) for key in ("actor_id", "room_id", "visibility")):
        return None
    terms = set(re.findall(r"\w+", value)) - STOP
    now = now or datetime.now(timezone.utc)
    candidates = []
    for item in experience.get("items", []):
        if (
            item.get("actor_id") != speaker["actor_id"]
            or item.get("room_id") != speaker["room_id"]
            or item.get("visibility") != speaker["visibility"]
            or item.get("claim_type") not in {"user_claim", "user_preference"}
            or not item.get("evidence")
            or item.get("exact_user_quote") is not True
            or item.get("status", "active") != "active"
        ):
            continue
        expiry = item.get("valid_until")
        start = item.get("valid_from")
        if start:
            try:
                if datetime.fromisoformat(str(start).replace("Z", "+00:00")) > now:
                    continue
            except (ValueError, TypeError):
                continue
        if expiry:
            try:
                if datetime.fromisoformat(str(expiry).replace("Z", "+00:00")) <= now:
                    continue
            except (ValueError, TypeError):
                continue
        content = item.get("content", "")
        if (
            not isinstance(content, str)
            or not 1 <= len(content) <= 300
            or re.search(r"[\[\]<>`\r\n]", content)
        ):
            continue
        overlap = terms & set(re.findall(r"\w+", folded(content)))
        if len(overlap) >= 2 and terms <= set(re.findall(r"\w+", folded(content))):
            candidates.append((len(overlap), content))
    candidates.sort(key=lambda row: row[0], reverse=True)
    if not candidates or len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    # Attribute the quotation, never assert its contents are verified world facts.
    label = "Papa" if re.search(r"\bpapa\b", value) else "Bạn"
    return f"{label} đã nói: “{candidates[0][1]}”"
