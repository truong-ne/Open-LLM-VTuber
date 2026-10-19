"""Bounded motor intentions, never executable code or arbitrary skeleton access."""
import math
import re

from .body_context import read_body_state

LIMITS = {
    "tilt": (-12, 12), "nod": (-10, 12), "lean": (-4, 4),
    "left": (0, 1), "right": (0, 1), "height": (-.10, .10),
    "smile": (0, 1), "brow": (0, 1), "eyes": (0, 1),
    "duration": (2, 7),
}
POSE_TAG = re.compile(r"\[pose\s*:\s*([^\]\r\n]*)\]", re.I)


class PoseStreamGuard:
    """Hide pose punctuation from sentence segmentation until a tag is complete."""
    def __init__(self):
        self.buffer = ""
        self.tokens = {}
        self.discard = False

    def feed(self, text, final=False):
        self.buffer += text
        output = []
        while self.buffer:
            if self.discard:
                end = self.buffer.find("]")
                if end < 0:
                    self.buffer = ""
                    break
                self.buffer = self.buffer[end + 1:]
                self.discard = False
            start = self.buffer.find("[")
            if start < 0:
                output.append(self.buffer)
                self.buffer = ""
                break
            output.append(self.buffer[:start])
            self.buffer = self.buffer[start:]
            lower = self.buffer.lower()
            if not (lower.startswith("[pose") or "[pose".startswith(lower)):
                output.append("[")
                self.buffer = self.buffer[1:]
                continue
            end = self.buffer.find("]")
            if end < 0:
                if len(self.buffer) > 512:
                    self.buffer = ""
                    self.discard = True
                elif final:
                    self.buffer = ""  # Do not speak an unfinished motor instruction.
                break
            tag, self.buffer = self.buffer[:end + 1], self.buffer[end + 1:]
            if not POSE_TAG.fullmatch(tag):
                continue
            _, pose = extract_pose_tag(tag)
            if pose and len(self.tokens) < 64:
                token = f"[MAOMOTOR{len(self.tokens)}TOKEN]"
                self.tokens[token] = tag
                output.append(token)
        return "".join(output)

    def restore(self, text):
        for token, tag in self.tokens.items():
            text = text.replace(token, tag)
        return text


def validate_pose(value):
    if not isinstance(value, dict) or not value or set(value) - LIMITS.keys():
        return None
    result = {}
    for key, number in value.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            return None
        low, high = LIMITS[key]
        result[key] = max(low, min(high, number))
    return result if set(result) - {"duration"} else None


def extract_pose_tag(text):
    pose = None
    for match in POSE_TAG.finditer(text):
        if len(match[1]) > 300:
            continue
        try:
            pairs = [pair.strip().split("=") for pair in match[1].split(",")]
            if any(len(pair) != 2 for pair in pairs) or len({p[0] for p in pairs}) != len(pairs):
                continue
            candidate = validate_pose({key: float(number) for key, number in pairs})
            pose = pose or candidate
        except (ValueError, TypeError):
            continue
    # Invalid instructions must never reach speech, either.
    return POSE_TAG.sub("", text).strip(), pose


def motor_context():
    if not read_body_state():
        return ""
    return (
        "\n\n[Điều khiển cơ thể liên tục]\n"
        "Mao có thể tự phối tư thế mới bằng MỘT thẻ ẩn [pose:...] đầu câu, thay cho thẻ cử chỉ có sẵn. "
        "Chọn theo ý nghĩa câu chuyện, chỉ ở điểm cần nhấn; không dùng mỗi câu. "
        "Các tham số tùy chọn: tilt=-12..12 (nghiêng đầu, độ), nod=-10..12 (cúi đầu, độ), "
        "lean=-4..4 (nghiêng thân ra trước, độ); left=0..1 và right=0..1 (độ mở tay trái/phải), "
        "height=-0.10..0.10 (độ cao tay so với tư thế mở tay, mét theo rig); "
        "smile=0..1, brow=0..1 (nhướng mày), eyes=0..1 (mở to mắt), duration=2..7 (giây). "
        "Ví dụ khi giải thích: [pose:right=0.65,left=0.2,tilt=-4,smile=0.4,duration=4] "
        "hoặc ngạc nhiên nhẹ: [pose:brow=0.6,eyes=0.55,nod=-3,right=0.3]. "
        "Thay đổi mức độ và phối tham số theo câu, không lặp nguyên ví dụ; không kết hợp pose với thẻ cử chỉ khác cùng câu. "
        "Renderer làm mượt, giải IK và giới hạn cơ thể; tư thế tự hết hạn. "
        "Không điều khiển vị trí/hướng phòng qua pose. Khi nói vẫn đứng hướng camera. "
        "Chỉnh sửa cử động của papa được bộ điều khiển desktop lưu riêng; "
        "không tuyên bố tự huấn luyện trọng số, tự có ý thức hay đã làm đúng nếu chưa được xác nhận. "
        "Không đọc thẻ hoặc giải thích tham số trong câu trò chuyện."
    )
