"""Ephemeral response guidance from explicit requests and scoped recent turns.

This selects a communication action, never a diagnosis or a lasting preference.
No extra model call, storage write, or raw text is inserted as a system rule.
"""

from dataclasses import dataclass
import re
import time

from ..character.appraisal import appraise_text, direct_text
from .attention import quiet_request, request_clauses


RULES = {
    "respond": (
        "Phản hồi trực tiếp lời vừa nói bằng cách xưng hô của hồ sơ; mặc định gọn, mở rộng khi được yêu cầu. "
        "Khi người nói chia sẻ tên gọi hay lựa chọn của chính họ, có thể ghi nhận điều họ vừa nói mà "
        "không đòi xác minh ngoài đời. Điều đó không chứng thực quyền quản trị. Không tự giới thiệu lại, "
        "không giải thích rằng mình chưa có ký ức hay sở thích khi không được hỏi, và không nhận đã lưu "
        "thông tin nếu thao tác lưu chưa được xác nhận."
    ),
    "recall_evidence": (
        "Đây là câu hỏi về điều người đang trò chuyện đã nói hoặc chọn. Đọc các knowledge item "
        "và user_claim hiện có trong scoped experience, tìm nội dung liên quan của đúng người nói. "
        "Nếu có nội dung đó, trả lời ngắn bằng thông tin ấy và quy nguồn tự nhiên như 'papa đã nói…'; "
        "không đòi chứng thực ngoài đời cho việc nhắc lại lời người dùng, và không trả lời 'chưa có ký ức' "
        "khi bằng chứng đang nằm ngay trong ngữ cảnh. Nếu không có bằng chứng liên quan thì nói chưa biết. "
        "Không chuyển ký ức của người khác sang người này, không dùng thông tin đã bị thay hoặc quên."
    ),
    "quiet": (
        "Người nói yêu cầu yên tĩnh. Xác nhận ngắn trong tối đa một câu, không hỏi thêm "
        "hoặc tự mở chủ đề mới. Chỉ nói đã tạm dừng mở chuyện tự động khi trạng thái hệ thống "
        "xác nhận; không hứa đã thực hiện khi chưa được xác nhận. Không hứa tắt tiếng mọi chức năng."
    ),
    "resume": (
        "Người nói muốn tiếp tục trò chuyện. Theo mạch hiện tại, không suy ra họ đã đổi tâm trạng "
        "và không yêu cầu xác nhận lại."
    ),
    "listen": (
        "Người nói đang muốn kể và được lắng nghe ở lượt này. Đáp một hoặc hai câu ngắn: "
        "phản ánh một chi tiết hoặc khó khăn họ vừa thực sự chia sẻ, rồi để họ tự chọn nhịp tiếp theo. "
        "Nếu lượt này chỉ có câu tiếp ngắn, dùng mạch gần nhất mà không thêm nguyên nhân hay sự kiện. "
        "Không tự thêm lời khuyên, chẩn đoán hoặc kết luận họ đã khá hơn. "
        "Không đặt câu hỏi, ra lệnh hoặc mời kể thêm (kể cả 'hãy kể', 'kể tiếp đi', 'cứ kể'). "
        "Không chỉ lặp câu xác nhận mình đang nghe nếu vừa xác nhận ở lượt trước. "
        "Yêu cầu mới rõ ràng luôn được ưu tiên hơn cách đáp này."
    ),
    "repair": (
        "Người nói đang sửa cách hiểu của câu trước. Xác định điều bị hiểu sai từ ngữ cảnh đã phát; "
        "nếu họ đã giải thích ý đúng thì đáp theo ý đó, không hỏi lại điều vừa được làm rõ. "
        "Nếu còn thiếu thông tin, hỏi tối đa một câu cụ thể. Không mặc định nhận lỗi về sự thật "
        "hoặc sửa ký ức khi chưa có bằng chứng; không xin lỗi dài hay chuyển chủ đề."
    ),
    "change_topic": (
        "Người nói muốn chuyển chủ đề. Theo yêu cầu mới nếu có; không kéo họ về tâm sự trước "
        "hoặc coi trạng thái cũ vẫn còn. Không gán việc đổi chủ đề thành sở thích lâu dài."
    ),
    "playful_scare": (
        "Khán giả đang hù hoặc chọc Mao bằng chuyện ma nhắm vào Mao. Đáp vui kiểu nhân vật anime "
        "trong 2–3 câu ngắn, khoảng 30–65 từ: giật mình kêu sợ, gọi đúng nickname nếu có rồi trách yêu "
        "rằng người đó chọc làm Mao sợ. Phải nói rõ cả hai ý sợ và bị trêu, ví dụ: "
        "Á, sợ quá! Bạn lại chọc Mao làm Mao sợ rồi đó, hứ! Có thể thay bạn bằng đúng nickname. "
        "Sau đó có thể đòi cả nhà bênh hoặc trêu ngược nhẹ. "
        "Dùng tiếng Việt dễ nghe, một tiếng kêu như Á hoặc Hứ là đủ, không spam tiếng Nhật. "
        "Đặt [surprise] ở đầu câu cho nét mặt giật mình; nói có nhịp, nhấn tiếng kêu sợ và kéo nhẹ một từ như nhaaa. Đây là diễn sợ vui: không xác nhận có ma thật, "
        "không giảng giải AI không biết sợ, không chuyển sang kể truyện hoặc bịa đã nhìn thấy ma."
    ),
    "story": (
        "Người nói yêu cầu một truyện ngắn. Kể một mạch có nhân vật, tình huống, diễn biến "
        "và cái kết giải quyết sự việc. Không kể lan man hoặc hẹn phần sau."
    ),
    "answer": (
        "Đáp trực tiếp yêu cầu hiện tại, kể cả khi trước đó người nói chỉ muốn được lắng nghe. "
        "Không yêu cầu họ xác nhận lại một yêu cầu đã rõ."
    ),
}


@dataclass(frozen=True)
class ResponsePlan:
    mode: str = "respond"
    context_event: str | None = None
    recall_requested: bool = False

    def prompt(self):
        rule = RULES.get(self.mode)
        if self.recall_requested:
            rule = (rule + "\n" if rule else "") + RULES["recall_evidence"]
        return (
            "\n[Current response guidance — this turn only]\n"
            + rule
            + "\n[/Current response guidance]\n"
            if rule
            else ""
        )


def playful_scare(value):
    from ..character.appraisal import folded

    value = folded(value)
    return bool(
        re.search(r"\b(?:hu|doa|choc) mao\b", value)
        or (
            re.search(r"\b(?:ma|quy|con ma|bong ma)\b", value)
            and re.search(
                r"\b(?:gam giuong(?: cua)? mao|sau lung mao|phong(?: cua)? mao|nha(?: cua)? mao|nhin mao|bat mao|tim mao)\b",
                value,
            )
            and not re.search(r"\b(?:khong co|chang co|khong phai)\b", value)
        )
    )


def _clause_mode(value):
    control = quiet_request(value)
    if control:
        return control
    value = re.sub(
        r"\b(?:khong|chua|dung) chi (?:muon|can) (?:ke|tam su|lang nghe)\b", " ", value
    )
    value = re.sub(
        r"\b(?:dung|khong|chua)(?: muon| can)? (?:doi chu de|chuyen chu de|noi chuyen khac|hieu sai|hieu nham)\b",
        " ",
        value,
    )
    if re.search(
        r"\b(?:doi chu de|chuyen chu de|noi chuyen khac|move on|change the subject)\b",
        value,
    ):
        return "change_topic"
    if appraise_text(value).kind == "correction" or re.match(
        r"\s*(?:mao[, :]+)?(?:y (?:toi|minh|to|papa) la|khong phai y (?:toi|minh|papa))\b",
        value,
    ):
        return "repair"
    if re.search(
        r"\b(?:chi (?:muon|can) (?:ke(?: thoi)?|tam su|duoc lang nghe|mao (?:lang )?nghe)|"
        r"(?:dung|chua can|khong can) (?:voi )?(?:khuyen|dua (?:ra )?(?:loi khuyen|giai phap))|"
        r"khong (?:can|muon) (?:loi khuyen|giai phap)|"
        r"(?:nghe|lang nghe) (?:toi|minh|papa) (?:ke|thoi))\b",
        value,
    ):
        return "listen"
    from .story import story_request

    if story_request(value):
        return "story"
    if playful_scare(value):
        return "playful_scare"
    if "?" in value or re.search(
        r"\b(?:hay (?:giai thich|tinh|viet|ke)|giup (?:toi|minh|papa)|"
        r"cho (?:toi|minh|papa) .{0,25}(?:cach|giai phap|loi khuyen)|"
        r"(?:muon|can) (?:loi khuyen|giai phap)|giai thich|tinh ho)\b",
        value,
    ):
        return "answer"
    return None


def _explicit(value):
    clauses = request_clauses(value)
    modes = [mode for clause in clauses if (mode := _clause_mode(clause))]
    if not modes:
        return None
    # A request for the new topic remains a topic change, while a later explicit
    # listening/repair/control instruction replaces the earlier request.
    if modes[-1] == "answer" and "change_topic" in modes:
        return "change_topic"
    return modes[-1]


def response_plan(text, history=(), *, now=None):
    """History must already be filtered to the same actor/room/visibility by host."""
    value = direct_text(text)
    mode = _explicit(value)
    if mode:
        recall = mode == "answer" and bool(
            re.search(
                r"\b(?:con nho|nhac lai|da noi|tung noi|da chon|biet danh)\b", value
            )
        )
        return ResponsePlan(mode, recall_requested=recall)
    # Carry a listening request only across a bounded, explicit short continuation.
    # Silence, unrelated messages, assistant suggestions, and retrieved facts do not qualify.
    continuation = " ".join(re.sub(r"[^\w\s]", " ", value).split())
    if continuation not in {
        "u",
        "um",
        "vang",
        "roi",
        "van vay",
        "van nhu vay",
        "van chua het",
        "ke tiep nhe",
        "cho toi ke tiep",
        "cho papa ke tiep",
        "de minh ke tiep",
        "chuyen la",
        "kho noi lam",
        "chang biet noi sao",
    } or not isinstance(history, (list, tuple)):
        return ResponsePlan()
    now = time.time() if now is None else now
    for previous in history[:4]:
        if (
            not isinstance(previous, dict)
            or previous.get("delivery_status") != "completed"
        ):
            break
        observed = previous.get("observed_at")
        if type(observed) not in (int, float) or not 0 <= now - observed <= 600:
            break
        prior_value = direct_text(previous.get("user_claim", ""))
        prior_mode = _explicit(prior_value)
        if prior_mode:
            return (
                ResponsePlan("listen", previous.get("event_id"))
                if prior_mode == "listen"
                else ResponsePlan()
            )
        prior_continuation = " ".join(re.sub(r"[^\w\s]", " ", prior_value).split())
        if prior_continuation != continuation and prior_continuation not in {
            "u",
            "um",
            "vang",
            "roi",
            "van vay",
            "van nhu vay",
            "ke tiep nhe",
        }:
            break
    return ResponsePlan()
