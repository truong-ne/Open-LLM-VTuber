import re


def requested_settings(settings, text):
    result = settings.copy()
    result.setdefault("verbosity", "detailed")
    if re.search(r"chi tiết|chi tiet|detailed", text, re.I):
        result["verbosity"] = "detailed"
    elif re.search(r"ngắn|\bngan\b|\bbrief\b", text, re.I):
        result["verbosity"] = "brief"
    if re.search(r"đừng (?:đùa|trêu)|không (?:đùa|trêu)|no jokes", text, re.I):
        result["humor"] = "gentle"
    return result


def communication_prompt(settings, trial=False):
    rules = {
        "verbosity": {
            "brief": "Trả lời gọn, tối đa ba câu hoàn chỉnh.",
            "detailed": "Giải thích đủ ý; chỉ mở rộng khi có ích.",
        },
        "humor": {
            "gentle": "Giữ giọng nhẹ nhàng; không đùa hoặc trêu.",
            "playful": "Có thể đùa nhẹ nếu người dùng và ngữ cảnh cho phép; luôn ưu tiên ranh giới và trạng thái cảm xúc.",
        },
        "examples": {
            "ask": "Hỏi người dùng có muốn ví dụ trước khi thêm một ví dụ dài.",
            "use": "Đưa một ví dụ cụ thể khi nó giúp giải thích.",
        },
        "initiative": {
            "wait": "Đợi người dùng mở chuyện; không tự đề xuất một cuộc trò chuyện mới.",
            "balanced": "Có thể đề xuất một việc liên quan khi phù hợp với lượt nói hiện tại.",
        },
    }
    result = "\n".join(
        rules[key][value]
        for key, value in settings.items()
        if key in rules and value in rules[key]
    )
    if trial:
        result += "\nĐây là cách trò chuyện đang thử. Nếu nói về lựa chọn này, diễn đạt như một thử nghiệm hiện tại; không bịa rằng mình luôn thích như vậy từ lâu, và không đưa thuật ngữ vận hành vào hội thoại."
    return result
