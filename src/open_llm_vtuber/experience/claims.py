import re
from ..character.appraisal import folded


def explicit_address_request(text):
    value = folded(re.sub(r'["“][^"”]*["”]|`[^`]*`', " ", text))
    if re.search(r"(?:dung|khong).{0,12}goi|hom nay|luc nay|today|for now", value):
        return False
    return bool(
        re.search(
            r"(?:^|[,;\n])\s*(?:mao(?: oi)?[,\s]*)?(?:(?:tu nay|hay|cu|vui long|please)\s+)*(?:goi (?:to|minh|toi|papa|em|anh) la|call me)\s+\w",
            value,
        )
    )


def classify_claim(text, session):
    value = folded(text)
    temporary = bool(re.search(r"hom nay|luc nay|today|for now", value))
    slot = None
    if re.search(r"thich|ua |prefer|goi (?:to|minh|toi|papa)|xung ho", value):
        for key, pattern in (
            ("address", r"goi (?:to|minh|toi|papa)|xung ho"),
            ("drink", r"ca phe|tra |cacao|do uong|nuoc ep|soda"),
            ("color", r"mau |color"),
            ("food", r"mon an|pizza|com |pho |bun "),
        ):
            if re.search(pattern, value):
                slot = key
                break
    key = (
        ("temporary:" + session + ":" if temporary else "preference:") + slot
        if slot
        else None
    )
    return {
        "claim_type": "user_preference" if slot else "user_claim",
        "item_key": key,
        "temporary": temporary,
    }


def forget_requested(text):
    value = folded(re.sub(r'["“][^"”]*["”]|`[^`]*`', " ", text))
    if re.search(
        r"khong.{0,15}(?:quen|xoa)|dung (?:quen|xoa)|do not (?:forget|delete)|don.t (?:forget|delete)",
        value,
    ):
        return False
    return bool(
        re.search(
            r"quen (?:di|thong tin|ky uc|so thich)|xoa (?:ky uc|thong tin)|forget (?:that|memory|my|the)|delete memory",
            value,
        )
    )


def lasting_boundary(text):
    value = folded(re.sub(r'["“][^"”]*["”]|`[^`]*`', " ", text))
    if not re.search(r"tu nay|luon luon|ve sau|henceforth|always", value):
        return None
    if re.search(r"dung (?:dua|treu)|khong (?:dua|treu)|no jokes", value):
        return "gentle"
    if re.search(r"cu (?:dua|treu)|co the (?:dua|treu)|allow jokes", value):
        return "playful"
    return None
