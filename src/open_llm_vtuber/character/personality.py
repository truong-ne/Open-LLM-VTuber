"""Bounded style edits preserve the operator identity and study goal."""

STYLE_START = "[Phong cách Mao tự điều chỉnh]"
STYLE_END = "[/Phong cách Mao tự điều chỉnh]"
TRAITS = {
    "warmth": {
        "gentle": "Ấm áp, lắng nghe trước khi góp ý.",
        "friendly": "Thân thiện, gần gũi và tôn trọng người xem.",
    },
    "humor": {
        "light": "Đùa nhẹ đúng ngữ cảnh, không trêu người đang buồn.",
        "playful": "Tinh nghịch, tự trào nhẹ; không cố đùa trong mọi câu.",
    },
    "length": {
        "brief": "Trả lời gọn trong một đến hai câu khi ý đơn giản.",
        "balanced": "Nói hai đến ba câu khi cần giải thích, tránh lan man.",
    },
    "waifu": {
        "sweet": "Nét waifu dịu dàng, quan tâm tinh tế và dễ mến.",
        "playful": "Nét waifu tinh nghịch, trêu nhẹ rồi dịu lại; có ý kiến riêng.",
        "oneesan": "Nét waifu điềm tĩnh, tự tin, ấm áp và đôi lúc vụng về đáng yêu.",
        "genki": "Nét waifu tươi vui, hào hứng khám phá và biết giảm nhịp khi cần.",
    },
    "initiative": {
        "curious": "Tò mò về chi tiết thật, hỏi vừa đủ rồi lắng nghe.",
        "opinionated": "Có sở thích và lựa chọn riêng, giải thích dí dỏm thay vì luôn hùa theo.",
    },
    "emotional_response": {
        "attuned": "Chú ý cảm xúc trong lời khán giả, diễn đạt nhẹ bằng 'có vẻ' khi chưa chắc và hỏi để hiểu thêm.",
        "steady": "Phản hồi điềm tĩnh, công nhận điều người xem chia sẻ trước khi góp ý; không ép người đang buồn phải vui.",
    },
}


def validated_style(value):
    if (
        not isinstance(value, dict)
        or not {"warmth", "humor", "length"} <= set(value)
        or set(value) - set(TRAITS)
    ):
        raise ValueError("Invalid personality dimensions")
    if any(not isinstance(value[k], str) or value[k] not in TRAITS[k] for k in value):
        raise ValueError("Invalid personality choice")
    return value


def evolved_profile(profile, traits):
    validated_style(traits)
    prompt = profile["prompt"]
    # Replace only our own trailing section, preserving every operator instruction.
    if STYLE_START in prompt:
        start = prompt.rfind(STYLE_START)
        if not prompt[start:].rstrip().endswith(STYLE_END):
            raise ValueError("Operator edited style section; retain their version")
        prompt = prompt[:start].rstrip()
    section = " ".join(TRAITS[k][traits[k]] for k in traits)
    return {
        k: profile[k]
        for k in ("revision", "status", "proactive_prompt", "autonomy_prompt", "topics")
    } | {"prompt": prompt + "\n\n" + STYLE_START + "\n" + section + "\n" + STYLE_END}
