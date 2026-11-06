"""Randomly pick a supplied everyday food option; leave constraints to dialogue."""

import random
import re
from ..character.appraisal import folded

FOODS = (
    "xoi",
    "pho",
    "bun",
    "banh mi",
    "com",
    "pizza",
    "mi",
    "chao",
    "lau",
    "sushi",
    "ga ran",
    "hamburger",
    "banh cuon",
    "banh xeo",
)


def pick_food(text, rng=None):
    value = folded(text)
    if re.search(
        r"di ung|an chay|kieng|tranh|khong an|khong duoc|benh|dau bung", value
    ):
        return None
    text = re.sub(r"^[^:]{0,50}:\s*", "", text.strip())
    text = re.sub(
        r"^(?:Mao\s*(?:ơi|oi)?[,! ]*)?(?:(?:chọn giúp|chon giup|tôi nên ăn|toi nen an|mình nên ăn|minh nen an|nên ăn|nen an|chọn|chon|chốt|chot|ăn|an)\s+)?",
        "",
        text,
        flags=re.I,
    )
    options = [
        re.sub(r"[?!.,~]+$", "", part).strip()
        for part in re.split(r"\s+(?:hay|hoặc|hoac)\s+", text, flags=re.I)
    ]
    if not 2 <= len(options) <= 4 or any(
        not 1 <= len(o) <= 35
        or not any(
            folded(o) == food or folded(o).startswith(food + " ") for food in FOODS
        )
        for o in options
    ):
        return None
    return (rng or random.SystemRandom()).choice(options)
