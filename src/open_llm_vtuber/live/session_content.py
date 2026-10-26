"""Local content rotation for long livestreams, independent of the LLM window."""

import random
from pathlib import Path

from .idle_host_storage import read_json, write_json


ENGAGEMENT_TOPICS = (
    "chọn phe anh hùng hay phản diện trong anime",
    "chọn bảng màu trang phục cho nhân vật",
    "chọn một đối thủ hư cấu để nhân vật đấu khẩu trong anime",
    "chọn một siêu năng lực chỉ tiện cho việc nhỏ",
    "chọn linh vật hư cấu cho hội người xem nhân vật",
    "đặt một câu châm ngôn tự trào cho nhân vật",
    "chọn mở màn bằng biểu cảm kiêu hay vui",
    "chọn một từ tiếng Việt làm biệt danh cho ngày hôm nay",
)

TOPICS = (
    *ENGAGEMENT_TOPICS,
    "mèo ngủ giữa giờ làm",
    "món ăn vặt tuổi thơ",
    "một buổi tối mưa",
    "ngủ nướng và đồng hồ báo thức",
    "cây xanh trên bàn làm việc",
    "sở thích ngộ nghĩnh",
    "trà sữa và cà phê",
    "nghe nhạc thư giãn",
    "lập trình viên đi tìm bug",
    "chiếc ổ mèo thật êm",
    "điện thoại báo pin yếu",
    "tập thể dục rồi thèm bánh",
    "mùi bánh mì mới ra lò",
    "chỗ ngồi yêu thích khi đi xe",
    "chọn một siêu năng lực nhỏ",
    "quyển sổ ghi ý tưởng",
    "món ăn Việt muốn tìm hiểu",
    "đi chợ chỉ mua một món",
    "đồ vật hay biến mất",
    "tiếng mưa và tiếng quạt",
    "một lá thư gửi tương lai",
    "thói quen trước giờ ngủ",
    "một cái kết anime khiến người xem bất ngờ",
    "nuôi một cây từ hạt",
    "chụp ảnh những điều bé xíu",
    "món quà không cần đắt",
    "đồ handmade hơi vụng",
    "một ngày không mạng",
    "đặt tên chiêu thức hư cấu nghe kiêu mà buồn cười",
    "chiếc túi luôn thiếu đúng món cần",
    "học một kỹ năng mới",
    "hát sai lời mà vẫn tự tin",
    "một lời khen đúng lúc",
    "chọn tên cho một ngôi sao tưởng tượng",
    "nhạc nền hợp một buổi tán gẫu",
    "món ăn có tên lạ",
    "thích ở nhà hay đi picnic",
    "bàn làm việc gọn hay bừa",
    "chờ một chiếc bánh chín",
    "thử thách tiết kiệm một việc nhỏ",
    "đặt tên cho các ngày trong tuần",
    "một thói quen dễ thương của người xem đã được chia sẻ",
    "chiếc ô đi lạc",
    "chọn màu cho tâm trạng",
    "sắp xếp một kệ sách",
    "một khu vườn trên ban công",
    "một điều mới học được từ cuộc trò chuyện",
    "bữa sáng vội và bữa sáng thong thả",
    "một cuộc thi phát minh vô dụng",
    "thú vui ngắm mây",
    "mèo hay chó trong anime",
    "một bức tranh vẽ dở",
    "đi bộ tìm chi tiết thú vị",
    "chọn âm thanh làm báo thức",
    "công thức món ăn tưởng tượng",
    "thể loại phim hoạt hình yêu thích",
    "chọn ghế ngồi bên cửa sổ",
    "sửa một món đồ cũ",
    "một nhân vật phụ xứng đáng có câu chuyện riêng",
    "chọn nhạc mở đầu cho một trận đấu anime hư cấu",
    "hội những chiếc tất mất đôi",
    "đặt biệt danh cho một con robot hư cấu",
    "một nét mặt hợp tâm trạng hiện tại",
    "ngày nghỉ không có kế hoạch",
    "một từ tiếng Việt nghe thật thân thương",
    "món ăn Việt thường được nhắc trong dịp sum họp",
    "cách nói cảm ơn thật có lòng",
    "giữ gìn một góc phố sạch đẹp",
    "sự đáng yêu của những cách xưng hô tiếng Việt",
    "một món quà nhỏ giới thiệu nét đẹp Việt Nam với bạn bè",
)

ANGLES = (
    "chọn một điều nhân vật thích và nói ngắn lý do",
    "so sánh hai lựa chọn bằng một khác biệt cụ thể",
    "nêu một điều hơi bất tiện bằng giọng tự trào nhẹ",
    "chú ý một chi tiết nhỏ dễ bị bỏ qua",
    "nêu một điều nhân vật muốn thử, không nhận đã thực hiện",
    "đổi ý nhẹ nếu có một lý do thuyết phục trong hội thoại",
    "nhận xét dí dỏm về một thói quen quen thuộc",
    "liên tưởng đến một màu sắc hoặc âm thanh phù hợp",
    "nêu một điểm dễ hiểu nhầm, không dựng nhân vật hoặc cốt truyện",
    "trêu nhẹ một nghịch lý nhỏ mà không nhắm vào người xem",
    "chọn một sở thích hơi khác thường và giải thích gọn",
    "chỉ ra một nét đối lập thú vị bằng một câu",
    "nói điều nhân vật chưa hiểu rõ, không tự bịa kiến thức",
    "nêu một điều tò mò, chỉ đặt câu hỏi khi lượt này cho phép",
    "nối với một chi tiết thật trong hội thoại nếu có",
    "so sánh cách đơn giản với cách cầu kỳ",
    "chọn một thay đổi nhỏ có thể làm điều này dễ chịu hơn",
    "chia sẻ một ý ấm áp mà không khuyên dạy",
    "dùng một ví von ngắn, không phát triển thành chuyện kể",
    "nói một điều khác với điều nhân vật đoán ban đầu",
    "đưa một ý kiến khác số đông mà không phán xét",
    "nhận xét về tên gọi hoặc cách diễn đạt nghe thú vị",
    "liên hệ với sở thích đã được xác nhận, không bịa ký ức",
    "nói một lựa chọn vui rồi dừng, không thêm kết luận đạo đức",
)


class SessionContent:
    def __init__(self, path: Path, rng=None):
        self.path = path
        self.rng = rng or random.Random()
        saved = read_json(path)
        saved_used = saved.get("used", [])
        saved_topics = saved.get("recent_topics", [])
        self.used = [
            tuple(item)
            for item in (saved_used if isinstance(saved_used, list) else [])
            if isinstance(item, list)
            and len(item) == 2
            and item[0] in TOPICS
            and item[1] in ANGLES
        ][-4096:]
        self.recent_topics = [
            t
            for t in (saved_topics if isinstance(saved_topics, list) else [])
            if t in TOPICS
        ][-16:]
        self.turns = saved.get("turns", 0)
        if type(self.turns) is not int or self.turns < 0:
            self.turns = 0

    def topic(self, exclude=None, preferred=None):
        counts = {
            t: sum(used_topic == t for used_topic, _ in self.used) for t in TOPICS
        }
        eligible = [t for t in TOPICS if counts[t] <= len(ANGLES) - 2 and t != exclude]
        if not eligible:
            self.used.clear()
            eligible = [t for t in TOPICS if t != exclude]
            counts = dict.fromkeys(TOPICS, 0)
        if preferred:
            eligible = [t for t in eligible if t in preferred] or eligible
        available = [t for t in eligible if t not in self.recent_topics] or eligible
        least_used = min(counts[t] for t in available)
        return self.rng.choice([t for t in available if counts[t] <= least_used + 2])

    def angle(self, topic):
        available = [a for a in ANGLES if (topic, a) not in self.used]
        if not available:
            self.used = [(t, a) for t, a in self.used if t != topic]
            available = list(ANGLES)
        return self.rng.choice(available)

    def commit(self, topic, angle):
        self.used = (self.used + [(topic, angle)])[-4096:]
        if not self.recent_topics or self.recent_topics[-1] != topic:
            self.recent_topics = (self.recent_topics + [topic])[-16:]
        self.turns += 1
        write_json(
            self.path,
            {
                "turns": self.turns,
                "used": self.used,
                "recent_topics": self.recent_topics,
            },
        )
