"""Explicit, temporary conversation controls; no inference from silence."""

import re

from ..character.appraisal import direct_text


def request_clauses(value):
    return re.split(
        r"(?<=[.!?;])\s+|\n|\b(?:bay gio|gio thi|thay vao do)\b|,\s*(?=(?:hay|cho|giup|chi|dung)\b)",
        value,
    )


def _quiet_clause(text):
    value = " ".join(re.sub(r"[^\w\s]", " ", text).split())
    prefix = r"(?:mao )?(?:(?:papa|toi|minh) )?"
    suffix = r"(?: (?:nhe|nha|di|nua|thoi))?"
    if re.fullmatch(
        prefix + r"(?:muon yen tinh|can yen tinh|im lang(?: mot chut| chut)?|"
        r"yen lang(?: mot chut| chut)?|dung tu (?:mo chuyen|noi chuyen)|"
        r"dung chu dong (?:mo chuyen|noi chuyen))" + suffix,
        value,
    ):
        return "quiet"
    if re.fullmatch(
        prefix + r"(?:noi tiep|noi chuyen tiep|noi chuyen lai|"
        r"cu chu dong (?:mo chuyen|noi chuyen)(?: lai)?|het gio yen tinh)" + suffix,
        value,
    ):
        return "resume"
    return None


def quiet_request(text):
    controls = [
        control
        for clause in request_clauses(direct_text(text))
        if (control := _quiet_clause(clause))
    ]
    return controls[-1] if controls else None


def continues_topic(text):
    value = " ".join(re.sub(r"[^\w\s]", " ", direct_text(text)).split())
    return value in {
        "u",
        "um",
        "vang",
        "roi",
        "co",
        "khong",
        "dung roi",
        "van vay",
        "van nhu vay",
        "van chua het",
        "van con",
        "ke tiep nhe",
        "cho toi ke tiep",
        "cho papa ke tiep",
        "de minh ke tiep",
        "kho noi lam",
        "chang biet noi sao",
        "mao hieu sai roi",
        "mao hieu nham roi",
    }
