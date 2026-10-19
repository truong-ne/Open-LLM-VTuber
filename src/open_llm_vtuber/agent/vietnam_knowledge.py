"""Small, curated offline reference lookup; not an assertion of encyclopedic recall."""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from loguru import logger

# Gate Mao's runtime helpers by identity, independently of a biography section.
PERSONA_MARKER = "MAO_FEM_MALFOY_V1"
REFERENCE_PATH = (
    Path(__file__).resolve().parents[3] / "knowledge/vietnam_history.vi.json"
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " " + re.sub(r"[^a-z0-9]+", " ", text).strip() + " "


@lru_cache(maxsize=1)
def load_cards() -> tuple:
    try:
        cards = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))["cards"]
        if not isinstance(cards, list) or not all(
            isinstance(c, dict)
            and all(
                isinstance(c.get(k), str) for k in ("title", "facts", "source", "url")
            )
            and isinstance(c.get("aliases"), list)
            and all(isinstance(alias, str) and alias.strip() for alias in c["aliases"])
            for c in cards
        ):
            raise ValueError("Invalid reference cards")
        return tuple(cards)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Vietnam reference unavailable: {}", exc)
        return ()


def reference_context(text: str) -> str:
    """Bound to three short cards; matching ignores accents and preserves word boundaries."""
    query = normalize(text)
    ranked = []
    for card in load_cards():
        matches = [alias for alias in card["aliases"] if normalize(alias) in query]
        if matches:
            ranked.append(
                (sum(len(normalize(alias).split()) for alias in matches), card)
            )
    if not ranked:
        return ""
    ranked.sort(key=lambda item: item[0], reverse=True)
    parts = [
        "[TƯ LIỆU ĐỐI CHIẾU LOCAL — được chọn theo lượt hiện tại, không phải bình luận mới. "
        "Chỉ dùng phần liên quan. Đây là kho mốc cơ bản, không bao phủ mọi câu hỏi lịch sử. "
        "Không nhận vừa tra mạng, không suy diễn thêm ngày tháng hoặc trích dẫn. "
        "Nếu dữ liệu chưa đủ và không chắc, nói rõ phần chưa chắc. "
        "Trả lời thẳng câu hỏi lịch sử, không mở đầu bằng lời chào, không trêu bằng [smirk], "
        "không đề nghị chuyện tưởng tượng thay cho dữ kiện đang hỏi. "
        "Khi cần dẫn nguồn, nói tên cơ quan; không đọc URL ra tiếng.]"
    ]
    for _, card in ranked[:3]:
        parts.append(
            f"{card['title']}: {card['facts']} Nguồn: {card['source']}. {card['url']}"
        )
    return "\n".join(parts)[:3800]
