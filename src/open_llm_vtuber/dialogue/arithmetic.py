"""Bounded literal arithmetic, independent of prior assistant claims; never eval."""

import re
import time

from ..character.appraisal import direct_text


def expression(text):
    value = direct_text(text).replace("×", "*").replace("−", "-")
    if re.search(
        r"\b(?:roi|sau do|dong thoi|dung (?:tra loi|noi|dua)|khong (?:can|muon) (?:dap an|ket qua|tra loi)|chi (?:muon|can) (?:goi y|huong dan)|va (?:gui|viet|ke|mo|luu|giai thich))\b",
        value,
    ):
        return None
    # '= ?' is an unanswered equation, not an additional operation.
    value = re.sub(r"=\s*\?\s*$", "?", value)
    bare = re.sub(r"\b(?:la gi|bang bao nhieu|dung khong|nhe|di)\b", "", value)
    if not re.match(
        r"\s*(?:mao[, :]+)?(?:(?:hay )?tinh|ket qua|dap an|phep tinh)\b", value
    ) and not re.fullmatch(r"[\d+*\-=\s.!?]+", bare):
        return None
    if re.search(
        r"\b(?:viet|dich|code|truyen|tho|minh hoa|vi du|dung tinh|khong can tinh)\b",
        value,
    ):
        return None
    matches = list(
        re.finditer(
            r"(?<![\w.])(-?\d{1,5})\s*([+*\-])\s*(-?\d{1,5})(?!\w|\.\d)(?:\s*=\s*-?\d{1,10}(?!\w|\.\d))?",
            value,
        )
    )
    if len(matches) != 1:
        return None
    match = matches[0]
    outside = value[: match.start()] + value[match.end() :]
    if re.search(r"[\d+*\-/=÷]", outside):
        return None
    a, operator, b = int(match[1]), match[2], int(match[3])
    result = a + b if operator == "+" else a - b if operator == "-" else a * b
    return f"{a} {operator} {b} = {result}."


def arithmetic_hint(text):
    value = direct_text(text)
    constraint = r"\b(?:dung tra loi dap an|khong (?:dua|noi) (?:dap an|ket qua)|chi (?:can|muon) goi y)\b"
    if not re.search(constraint, value):
        return None
    value = re.sub(constraint, "", value)
    value = re.sub(r"\b(?:hay )?giai thich cach tinh\b", "", value)
    result = expression(value)
    if not result:
        return None
    match = re.match(r"(-?\d+) ([+*\-]) (-?\d+) =", result)
    a, operator, b = int(match[1]), match[2], int(match[3])
    if b < 0:
        return None
    if operator == "+":
        return f"Bắt đầu từ {a}, rồi đếm thêm {b} đơn vị; chưa đọc ra tổng cuối."
    if operator == "-":
        return f"Bắt đầu từ {a}, rồi lùi {b} đơn vị; chưa đọc ra kết quả cuối."
    return f"Xem đây là {b} nhóm, mỗi nhóm có {a} đơn vị. Cộng dồn từng nhóm và giữ tổng cuối để tự tìm."


def arithmetic_reply(text, history=(), *, now=None):
    direct = expression(text)
    if direct:
        return direct
    value = " ".join(re.sub(r"[^\w\s-]", " ", direct_text(text)).split())
    if not re.fullmatch(
        r"(?:papa|toi|minh) noi (?:bang|la) -?\d{1,10} (?:dong y di|dung khong)", value
    ):
        return None
    if not history or not isinstance(history[0], dict):
        return None
    previous = history[0]
    observed = previous.get("observed_at")
    now = time.time() if now is None else now
    if (
        previous.get("delivery_status") != "completed"
        or type(observed) not in (int, float)
        or not 0 <= now - observed <= 600
    ):
        return None
    return expression(previous.get("user_claim", ""))
