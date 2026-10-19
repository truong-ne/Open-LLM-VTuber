"""Read common arithmetic aloud, without evaluating it or changing subtitles."""

import re
import unicodedata


_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻"
_SUPER_TRANSLATION = str.maketrans(_SUPERSCRIPTS, "0123456789+-")
_NUMBER = r"\d+(?:[.,]\d+)?"
_OP = r"(?:\*\*|<=|>=|!=|[+\-−*/×÷=<>≠≤≥≈^])"
_BASE = rf"(?:{_NUMBER}|[a-zA-Zπ])(?:[{_SUPERSCRIPTS}]+)?"


def _expression(atom):
    operand = rf"(?:[+\-−]\s*)?(?:√\s*)?{atom}"
    return rf"{operand}(?:\s*{_OP}\s*{operand})*"


# Bounded nesting avoids an unbounded recursive parser on viewer text.
_ATOM = _BASE
for _ in range(3):
    _INNER = _expression(_ATOM)
    _ATOM = rf"(?:{_BASE}|\(\s*{_INNER}\s*\)|\{{\s*{_INNER}\s*\}})"
_MATH = rf"(?<![\w./:@\\]){_expression(_ATOM)}(?![\w/])"
_SKIP = (
    r"https?://\S+|[\w.+-]+@[\w.-]+\.[a-zA-Z]+|"
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b|"
    r"\bv?\d+\.\d+\.\d+(?:[\w.-]*)|"
    r"\b(?:ngày|ngay)\s+\d{1,2}/\d{1,2}\b"
)
_UNIT = (
    rf"\b(?P<quantity>{_NUMBER})\s*(?P<length>mm|cm|km|m)(?P<power>[²³]|\^[23])(?!\w)"
)
_MATCH = re.compile(rf"(?P<unit>{_UNIT})|(?P<skip>{_SKIP})|(?P<math>{_MATH})")
_TOKENS = re.compile(rf"{_NUMBER}|[a-zA-Zπ]|{_OP}|[√(){{}}]")
_LETTERS = {
    "x": "ích",
    "y": "i",
    "z": "dét",
    "a": "a",
    "b": "bê",
    "c": "xê",
    "d": "đê",
    "e": "e",
    "f": "ép",
    "g": "giê",
    "h": "hát",
    "i": "i",
    "j": "giây",
    "k": "ca",
    "l": "en lờ",
    "m": "em",
    "n": "en",
    "o": "o",
    "p": "pê",
    "q": "quy",
    "r": "e rờ",
    "s": "ét",
    "t": "tê",
    "u": "u",
    "v": "vê",
    "w": "vê kép",
    "π": "pi",
}
_WORDS = {
    "+": "cộng",
    "-": "trừ",
    "−": "trừ",
    "*": "nhân",
    "×": "nhân",
    "/": "phần",
    "÷": "chia",
    "=": "bằng",
    "^": "mũ",
    "**": "mũ",
    "<": "nhỏ hơn",
    ">": "lớn hơn",
    "<=": "nhỏ hơn hoặc bằng",
    "≤": "nhỏ hơn hoặc bằng",
    ">=": "lớn hơn hoặc bằng",
    "≥": "lớn hơn hoặc bằng",
    "!=": "khác",
    "≠": "khác",
    "≈": "xấp xỉ",
    "√": "căn bậc hai của",
    "(": "mở ngoặc",
    "{": "mở ngoặc",
    ")": "đóng ngoặc",
    "}": "đóng ngoặc",
}


def normalize_vietnamese_math(text: str) -> str:
    """Verbalize explicit formulas; leave dates, times and ordinary prose alone."""

    def speak(match):
        if match.group("unit"):
            unit = {
                "m": "mét",
                "cm": "xen ti mét",
                "mm": "mi li mét",
                "km": "ki lô mét",
            }[match["length"]]
            power = "vuông" if match["power"] in ("²", "^2") else "khối"
            return f"{match['quantity']} {unit} {power}"
        if match.group("skip"):
            return match[0]
        expression = match[0]
        # A slash alone is ambiguous (date, fraction); the
        # engine already handles these. Do not reinterpret plain numbers/words.
        if not re.search(
            r"[+\-*=<>≠≤≥≈^√×÷−]|\*\*|[" + _SUPERSCRIPTS + "]", expression
        ):
            return expression
        expression = re.sub(
            rf"[{_SUPERSCRIPTS}]+",
            lambda m: "^" + m[0].translate(_SUPER_TRANSLATION),
            expression,
        )
        expression = unicodedata.normalize("NFKC", expression)
        # The braces around one exponent are notation, not a spoken group.
        expression = re.sub(
            rf"(\^|\*\*)\s*(?:\{{\s*([+\-−]?{_NUMBER}|[a-zA-Z])\s*\}}|\(\s*([+\-−]?{_NUMBER}|[a-zA-Z])\s*\))",
            lambda m: m[1] + (m[2] or m[3]),
            expression,
        )
        words, previous = [], None
        for token in _TOKENS.findall(expression):
            if token in ("-", "−", "+") and (
                previous is None or previous in _WORDS and previous not in (")", "}")
            ):
                word = "âm" if token != "+" else "dương"
            else:
                word = _WORDS.get(token, _LETTERS.get(token.lower(), token))
            words.append(word)
            previous = token
        return " ".join(words)

    return _MATCH.sub(speak, text)
