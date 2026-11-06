"""Requested short fiction: finish and validate the whole story before speech."""

import json
import re

from ..character.appraisal import direct_text, folded

STORY_RULE = (
    "Lượt này người xem yêu cầu kể chuyện: kể ngay đúng MỘT truyện hư cấu ngắn bằng tiếng Việt, "
    "khoảng 100–160 từ (tối đa 200 từ), cùng một nhân vật chính và một mạch sự kiện. "
    "Mở đầu nêu nhân vật, nơi chốn và tình huống; diễn biến có nguyên nhân dẫn đến sự việc; "
    "kết thúc giải quyết sự việc đã mở, không bỏ lửng hoặc hẹn phần sau. "
    "Giữ cùng một địa điểm, thời điểm và nhân vật chính từ đầu đến cuối. "
    "Không dùng giấc mơ, tỉnh giấc hay đổi cảnh bất ngờ để né giải quyết câu chuyện. "
    "Đoạn cuối phải chỉ rõ nguyên nhân sự việc và nhân vật đã xử lý nó ra sao. "
    "Chuyện ma cần có tình huống rùng rợn và lời giải hoặc cú chốt cụ thể; "
    "chuyện hài cần một tình huống dẫn tới câu chốt gây cười. "
    "Bám chủ đề người xem yêu cầu, không chuyển sang chuyện khác hoặc lặp truyện đã kể. "
    "Không chỉ đồng ý sẽ kể, hỏi lại thể loại đã rõ, giải thích cách kể hoặc bịa đây là "
    "trải nghiệm có thật của Mao/người xem. Không kéo sang lời khuyên hay lời mời nghe tiếp. "
    "Chỉ xuất JSON có đúng ba chuỗi beginning, middle, ending. Mỗi chuỗi là lời kể "
    "hoàn chỉnh để đọc thành tiếng, cùng thuộc một truyện; không tiêu đề, markdown, "
    "thẻ biểu cảm hoặc ghi chú sân khấu. Không gọi công cụ."
)


def story_request(text):
    value = direct_text(text)
    result = None
    for clause in re.split(r"[.!?;\n,]|\b(?:nhung|thay vao do|bay gio)\b", value):
        if re.search(
            r"\b(?:dung|khong|chua)(?: can| muon)?(?: mao)? (?:ke|nghe)\b", clause
        ):
            result = None
            continue
        if re.search(r"\b(?:toi|minh|papa|to|em)(?: se| dang| muon)? ke\b", clause):
            continue
        if re.search(r"\b(?:cach ke|huong dan|phan tich|co nen|tai sao)\b", clause):
            continue
        match = re.search(
            r"\bke\b.{0,45}\b(?:chuyen|truyen)\b|\b(?:muon|cho.{0,15}) nghe\b.{0,25}\b(?:chuyen|truyen)\b",
            clause,
        )
        if match:
            requested = clause[match.start() :]
            result = (
                "horror"
                if re.search(r"\b(?:ma|kinh di|rung ron)\b", requested)
                else "comedy"
                if re.search(r"\b(?:hai|cuoi|vui)\b", requested)
                else "general"
            )
    return result


def story_text(raw):
    value = raw.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value)
    try:
        data = json.loads(value)
    except (ValueError, TypeError) as error:
        raise ValueError("Story is not a complete structured response") from error
    if not isinstance(data, dict) or set(data) != {"beginning", "middle", "ending"}:
        raise ValueError("Story requires a beginning, middle and ending")
    parts = []
    for key in ("beginning", "middle", "ending"):
        part = data[key]
        if (
            not isinstance(part, str)
            or len(part.split()) < 8
            or not re.search(r'[.!…]["”’]?$', part.strip())
        ):
            raise ValueError("Story sections must be complete spoken sentences")
        if any(char in part for char in ("{", "}", "[", "]", "`")):
            raise ValueError("Story contains non-spoken formatting")
        parts.append(part.strip())
    story = "\n\n".join(parts)
    if not 70 <= len(story.split()) <= 200:
        raise ValueError("Story is outside its short spoken budget")
    if re.search(
        r"\b(?:con tiep|phan sau|muon nghe tiep|de lan sau ke|se ke sau)\b",
        folded(story),
    ):
        raise ValueError("Story leaves a continuation instead of an ending")
    if re.search(
        r"\b(?:nam mo|giac mo|ac mong|tinh giac|tinh day)\b", folded(parts[-1])
    ):
        raise ValueError("Story must resolve its setup rather than escape into a dream")
    return story


async def collect_story_response(stream):
    raw = ""
    try:
        async for event in stream:
            if isinstance(event, str):
                raw += event
            elif isinstance(event, dict) and event.get("type") == "text_delta":
                raw += event.get("text", "")
            else:
                raise RuntimeError("Unexpected non-story model event")
            if len(raw) > 12000:
                raise ValueError("Story draft exceeded its bounded response size")
    finally:
        close = getattr(stream, "aclose", None)
        if close:
            await close()
    return raw


async def generate_story(llm, messages, system, genre):
    genre_rule = {
        "horror": "Thể loại đã yêu cầu: chuyện ma.",
        "comedy": "Thể loại đã yêu cầu: chuyện hài.",
        "general": "Chủ đề theo yêu cầu hiện tại.",
    }[genre]
    schema = {
        "type": "object",
        "properties": {
            key: {"type": "string"} for key in ("beginning", "middle", "ending")
        },
        "required": ["beginning", "middle", "ending"],
        "additionalProperties": False,
    }
    for attempt in range(2):
        prompt = system + "\n" + STORY_RULE + "\n" + genre_rule
        if attempt:
            prompt += "\nBản trước thiếu cấu trúc hoặc vượt độ dài. Viết lại trọn truyện trong 100–160 từ, kết thúc ngay ở ending."
        try:
            structured = getattr(llm, "structured_completion", None)
            stream = (
                structured(messages, prompt, schema)
                if structured
                else llm.chat_completion(messages, prompt, tools=None)
            )
            raw = await collect_story_response(stream)
            return story_text(raw)
        except ValueError:
            if attempt:
                raise
