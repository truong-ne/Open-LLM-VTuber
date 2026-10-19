"""Ephemeral proprioception for Mao's local 3D avatar, not human sentience."""

import json
import math
import re
import time
from pathlib import Path

STATUS_PATH = Path(__file__).resolve().parents[3] / "private/draco-desktop-status.json"
BODY_COMMANDS = frozenset(
    (
        "north",
        "south",
        "east",
        "west",
        "center",
        "dj",
        "lounge-west",
        "lounge-east",
        "spin",
    )
)
BODY_TAG = re.compile(r"\[body\s*:\s*([^\]\r\n]{0,80})\]", re.IGNORECASE)
DIRECTIONS = (
    "Bắc (N)",
    "Đông Bắc (NE)",
    "Đông (E)",
    "Đông Nam (SE)",
    "Nam (S)",
    "Tây Nam (SW)",
    "Tây (W)",
    "Tây Bắc (NW)",
)


def read_body_state(path=None, now=None):
    try:
        data = json.loads((path or STATUS_PATH).read_text(encoding="utf-8"))
        age = (time.time() if now is None else now) * 1000 - data["updatedAt"]
        if (
            data.get("model") != "draco"
            or not data.get("ready")
            or not data.get("visible")
            or data.get("socket") != "open"
            or not 0 <= age < 8000
        ):
            return None
        for key in ("spaceX", "spaceZ", "spaceYaw"):
            value = data[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                return None
        if (
            data.get("mode") not in ("pet", "window")
            or abs(data["spaceX"]) > 4
            or not -5 <= data["spaceZ"] <= 1
        ):
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def body_context(path=None, now=None):
    state = read_body_state(path, now)
    if not state:
        return ""
    if state["mode"] == "pet":
        return (
            "\n\n[Trạng thái renderer hiện tại, không lưu làm ký ức]\n"
            "Mao có cơ thể avatar 3D đang ở Pet Mode; phòng đang ẩn. "
            "Có thể cử động và biểu cảm, không phát lệnh đi tới nội thất."
        )
    x, z, yaw = state["spaceX"], state["spaceZ"], state["spaceYaw"]
    heading = (180 - math.degrees(yaw)) % 360
    direction = DIRECTIONS[int((heading + 22.5) // 45) % 8]
    phase = state.get("bodyPhase", "idle")
    busy = phase != "idle"
    stopped = state.get("bodyStopped") is True
    location = "khu giữa sàn nhảy"
    if z < -2.8:
        location = "gần bàn DJ ở phía Bắc"
    elif x < -1.9:
        location = "bên Tây, gần ghế lounge"
    elif x > 1.9:
        location = "bên Đông, gần ghế lounge"
    elif z > -0.5:
        location = "phía Nam, gần phía cửa mở"
    if state.get("roomTheme") == "mao-tv-studio":
        scene = (
            "Mao VTuber đang trong phòng anime tông kem-xanh ngọc, cạnh bảng chữ phẳng. "
            "Bảng hiển thị Vua tiếng Việt, 60 giây, Gợi ý 1/2/3 hoặc kết quả theo vòng thật."
        )
        location = "bên phải bảng chữ" if x >= 0 else "bên trái bảng chữ"
    else:
        scene = "Mao đang ở phòng riêng đã được trang trí sẵn; đây chỉ là bối cảnh nền."
    parts = [
        "\n\n[Trạng thái renderer mới nhất — thay thế cảnh/vị trí cũ, không lưu làm ký ức]",
        scene,
        f"Mao có cơ thể avatar 3D: x={x:.2f}, z={z:.2f} m, {location}; hướng {direction}, {heading:.0f}°.",
        "Đang di chuyển hoặc xoay; chờ kết thúc, không phát thêm lệnh."
        if busy
        else "Đang đứng tại chỗ, có thể cử động tay và biểu cảm.",
    ]
    if stopped:
        parts.append("Papa đã yêu cầu dừng tự đi: giữ vị trí, không tự phát lệnh body.")
    if state.get("speechFocused"):
        parts.append(
            "Đang hướng về camera để nói; chờ hết toàn bộ lượt nói mới đi nếu được phép."
        )
    if busy:
        tx, tz = state.get("bodyTargetX"), state.get("bodyTargetZ")
        if all(isinstance(v, (float, int)) and math.isfinite(v) for v in (tx, tz)):
            parts.append(f"Đích x={tx:.2f}, z={tz:.2f} m; chưa đồng nghĩa đã tới nơi.")
    if state.get("lastBodyCommand") in BODY_COMMANDS:
        parts.append(
            "Lệnh body gần nhất "
            + (
                "đã được renderer nhận."
                if state.get("lastBodyAccepted") is True
                else "không được nhận; không nhận đã thực hiện."
            )
        )
    parts.append(
        "Hướng nội bộ: Bắc là z giảm, Nam z tăng, Đông x tăng, Tây x giảm; không có la bàn hiển thị."
    )
    if not stopped and not busy:
        parts.append(
            "Chỉ khi được yêu cầu, có thể đặt một thẻ ở câu kết: "
            "[body:north], [body:south], [body:east], [body:west], [body:center], [body:spin]. "
            + (
                ""
                if state.get("roomTheme") == "mao-tv-studio"
                else "Có thêm [body:dj], [body:lounge-west], [body:lounge-east]. "
            )
            + "Lệnh chờ hết toàn bộ lượt nói mới đi; chỉ nhận hoàn tất khi renderer xác nhận."
        )
    parts.append(
        "Không đọc thẻ/tọa độ hay tự kể lại trạng thái mỗi lượt. "
        "Không tự giới thiệu, khen hoặc lấy căn phòng làm chủ đề; chỉ nhắc khi được hỏi hay có thay đổi liên quan; "
        "không bịa chạm, đau hoặc nhìn thấy khán giả."
    )
    return "\n".join(parts)


def extract_body_tag(text):
    matches = list(BODY_TAG.finditer(text))
    command = next(
        (
            m[1].strip().lower()
            for m in matches
            if m[1].strip().lower() in BODY_COMMANDS
        ),
        None,
    )
    return BODY_TAG.sub("", text).strip(), command
