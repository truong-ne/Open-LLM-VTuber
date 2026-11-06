"""Build a reproducible, attributed classroom expansion from local source caches."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def normalize(text):
    flat = "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.findall(r"[a-z0-9]+", flat))


def clean(text):
    text = re.sub(r"\[[^]]*\]", "", text)
    return re.sub(r"\s+", " ", text).strip(" ;,.")


# Keep vocabulary appropriate to an everyday word game, rather than a technical dictionary.
BLOCK = re.compile(
    r"\b("
    + "|".join(
        [
            "cũ",
            "ít dùng",
            "phương ngữ",
            "địa phương",
            "từ cổ",
            "từ cũ",
            "viết tắt",
            "tiếng lóng",
            "thông tục",
            "thô tục",
            "giải phẫu",
            "hoá học",
            "hóa học",
            "vật lí",
            "vật lý",
            "sinh học",
            "toán học",
            "y học",
            "chính trị",
            "quân sự",
            "tôn giáo",
            "phật giáo",
            "thiên chúa",
            "phong kiến",
            "tư sản",
            "vô sản",
            "chiến tranh",
            "súng",
            "đạn",
            "thuốc nổ",
            "chất nổ",
            "sinh dục",
            "giao cấu",
            "dâm dục",
            "tình dục",
            "bộ phận sinh",
            "thuốc phiện",
            "ma tuý",
            "ma túy",
            "phóng xạ",
            "hạt nhân",
            "đảng",
            "chính phủ",
            "quốc hội",
            "quốc phòng",
            "chính quyền",
            "công quyền",
            "nghị sĩ",
            "nghị định",
            "pháp lệnh",
            "tố tụng",
            "bị cáo",
            "bị can",
            "khởi tố",
            "tội phạm",
            "trại giam",
            "cảnh sát",
            "công an",
            "giết",
            "tàn sát",
            "thảm sát",
            "tội ác",
            "cắt cổ",
            "sát hại",
            "đâm chém",
            "do thám",
            "đột kích",
            "trinh sát",
            "tình báo",
            "sinh thiết",
            "huyết thanh",
            "ung thư",
            "vi khuẩn",
            "vi rút",
            "virus",
            "tế bào",
            "nhiễm sắc",
            "hoóc môn",
            "hormone",
            "kinh nguyệt",
            "tinh dịch",
            "tử cung",
            "dương vật",
            "âm hộ",
            "vú",
            "bú",
            "đĩ",
            "địt",
            "đụ",
            "đéo",
            "cặc",
            "lồn",
            "tục tĩu",
            "chửi",
            "nhục mạ",
            "mê tín",
            "đồng bóng",
            "phong thuỷ",
            "nguyên tử",
            "phân tử",
            "điện tử học",
            "định lí",
            "định lý",
            "hàm số",
            "đạo hàm",
            "tích phân",
            "phương trình",
            "toạ độ",
            "tọa độ",
            "vector",
            "vectơ",
            "vật chất",
            "vô tận",
            "xem",
            "nói như",
            "cũng như",
            "tức là",
            "cách mạng",
            "xã hội chủ nghĩa",
            "chủ nghĩa",
            "công nghiệp hoá",
            "công nghiệp hóa",
            "hoàng đế",
            "triều đình",
            "vua chúa",
            "tội danh",
            "thể chế",
            "quán triệt",
            "chứng khoán",
            "cổ phiếu",
            "đầu cơ",
            "thuật ngữ",
            "chuyên môn",
            "đơn vị đo",
            "quặng",
            "hợp kim",
            "dung dịch",
            "axit",
            "acid",
            "kiềm",
            "hợp chất",
            "nguyên tố",
            "bức xạ",
            "điện phân",
            "động mạch",
            "tĩnh mạch",
            "thần kinh",
            "vũ khí",
            "chiến đấu",
            "đánh giặc",
            "giặc",
            "thủ tướng",
            "bộ trưởng",
            "đại biểu",
            "cấy ghép",
            "suy tim",
            "nội tạng",
            "ngoại khoa",
            "nội khoa",
            "xã hội hoá",
            "xã hội hóa",
            "ngu xuẩn",
            "dở hơi",
            "bất tài",
            "vô dụng",
            "đần độn",
            "ngu ngốc",
            "đểu",
            "chết bầm",
            "thằng",
            "con đĩ",
            "chủ nghĩa",
            "kết liễu",
            "thằng cha",
            "tiên sinh",
            "giáo chủ",
            "chi hội",
            "phê chuẩn",
            "liều mạng",
            "chủ lực",
            "cộng hưởng",
            "hệ số",
            "giải ngân",
            "bán kính",
            "lưu lượng",
            "phần tử",
            "đương quyền",
            "quốc vương",
            "ngôi báu",
            "công tước",
            "bá tước",
            "công nương",
            "đại thần",
            "hoàng hậu",
            "tiểu thư",
            "thời loạn",
            "thời chiến",
            "giáo sĩ",
            "giáo hoàng",
            "tăng ni",
            "sang chấn",
            "hậu phẫu",
            "ma mút",
            "nội tiếp",
            "câm họng",
            "nghị trường",
            "cổ văn",
            "quốc hiệu",
            "đối sách",
            "phẫn uất",
            "phỉ nhổ",
            "bi ai",
            "bút tích",
            "tất thắng",
            "đốc thúc",
            "tiên liệu",
            "tương khắc",
            "án ngữ",
            "ứng nghiệm",
            "tiết niệu",
            "chúng sinh",
            "nghĩa quân",
            "cầm quân",
            "bại trận",
            "khuyến nông",
            "diệt vong",
            "thê thảm",
            "hiểm nghèo",
            "hèn hạ",
            "ăn mày",
            "tra hỏi",
            "truyền bá",
            "tiếp tay",
            "bịt mắt",
            "ngược đãi",
            "gian thần",
            "hán gian",
            "địa chủ",
            "quan lại",
            "tiết chế",
            "chủ nghĩa",
            "chết chóc",
            "điện trở",
            "điện dung",
            "tam giác",
            "tứ giác",
            "thuỷ ngân",
            "thủy ngân",
            "gen",
            "nghiệp chướng",
            "nghiệp báo",
            "phong kiến",
            "mê tín",
            "quả báo",
            "thần học",
            "thiền",
            "sư",
            "phật",
            "đạo giáo",
            "chúa",
            "thánh",
            "quân",
            "binh",
            "chuẩn tướng",
            "đại tá",
            "tiểu đoàn",
            "bộ đội",
            "chi bộ",
            "đảng uỷ",
            "tỉnh uỷ",
            "hành chính",
            "hộ khẩu",
            "thần linh",
            "thần thánh",
            "thờ cúng",
            "linh thiêng",
            "mê hoặc",
            "hành quyết",
            "nghĩa địa",
            "tử thi",
            "giang hồ",
            "cá độ",
            "đánh bạc",
            "thuốc lá",
            "rượu chè",
            "say xỉn",
            "gợi cảm",
            "dâm đãng",
            "chết tiệt",
            "mất dạy",
            "khốn nạn",
            "mẹ kiếp",
            "đồ khốn",
            "khốn kiếp",
            "đểu cáng",
            "dâm",
            "đĩ điếm",
            "tàn phế",
            "phản loạn",
            "pháp chế",
            "pháp quyền",
            "phác đồ",
            "phân khối",
            "mẫu số",
            "tử số",
            "quá độ",
            "xiềng xích",
            "bôi nhọ",
            "trần trụi",
            "hãm hại",
            "thoát thân",
            "quyền hành",
            "công tố",
            "thượng tá",
            "chuẩn úy",
            "binh sĩ",
            "khuếch đại",
            "điện báo",
            "nhục nhã",
            "tư pháp",
            "hiến pháp",
            "chế tài",
            "biện chứng",
            "duy vật",
            "duy tâm",
            "siêu hình",
            "thực dân",
            "đế quốc",
            "đối lập",
            "giải phóng",
            "lao phổi",
            "thương hàn",
            "thương tích",
            "bệnh tật",
            "bệnh lý",
            "phản động",
            "tội",
            "tù",
            "giam",
            "âm mưu",
            "mưu sát",
            "mưu hại",
            "giật gân",
            "đầu độc",
            "cướp",
            "hiếp",
            "bạo lực",
            "đe doạ",
            "đe dọa",
        ]
    )
    + r")\b",
    re.I,
)

TOPICS = [
    (
        "Ăn uống",
        r"\b(bếp|nấu|thức ăn|món ăn|gia vị|thực phẩm|ăn uống|bữa ăn|đồ uống|ăn cơm|bánh|trái cây|quả chín)\b",
    ),
    (
        "Đồ dùng",
        r"\b(dụng cụ|đồ dùng|vật dụng|dùng để đựng|dùng để chứa|đồ đạc|vật đựng)\b",
    ),
    (
        "Đi lại",
        r"\b(xe|tàu|giao thông|đường đi|đi bộ|phương tiện|chuyến đi|vận chuyển|chở|lái)\b",
    ),
    (
        "Học tập",
        r"\b(học|trường|lớp|sách|vở|bài|thi cử|kiến thức|học sinh|sinh viên|giảng dạy)\b",
    ),
    (
        "Công việc",
        r"\b(công việc|làm việc|nghề|lao động|nhân viên|sản xuất|công nhân|xưởng|thợ)\b",
    ),
    (
        "Gia đình",
        r"\b(gia đình|cha mẹ|vợ chồng|con cái|anh em|họ hàng|ông bà|con cháu)\b",
    ),
    (
        "Thiên nhiên",
        r"\b(mưa|gió|nắng|biển|sông|núi|thời tiết|khí hậu|bầu trời|mây|thiên nhiên)\b",
    ),
    ("Cây cối", r"\b(cây|lá|hoa|cành|rễ|trồng|vườn|rừng|hạt giống)\b"),
    (
        "Động vật",
        r"\b(động vật|loài vật|loài chim|loài cá|con vật|gia súc|gia cầm|côn trùng)\b",
    ),
    (
        "Mua sắm",
        r"\b(mua|bán|hàng hoá|hàng hóa|cửa hàng|khách hàng|giá cả|tiền bạc|thanh toán|buôn bán)\b",
    ),
    (
        "Giao tiếp",
        r"\b(nói|lời nói|giao tiếp|trò chuyện|thông báo|kể chuyện|ngôn ngữ|nghe|hỏi|trả lời)\b",
    ),
    (
        "Cảm xúc",
        r"\b(tình cảm|cảm xúc|vui|buồn|nhớ|thương|yêu|lo lắng|lo âu|hạnh phúc|xúc động)\b",
    ),
    (
        "Ứng xử",
        r"\b(cư xử|thái độ|đối xử|tính nết|tính tình|phẩm chất|tôn trọng|giúp đỡ)\b",
    ),
    ("Thể thao", r"\b(thể thao|bóng đá|bơi|chạy|vận động viên|thi đấu|sân bóng)\b"),
    (
        "Nghệ thuật",
        r"\b(nghệ thuật|âm nhạc|âm thanh|hát|đàn|nhạc|vẽ|tranh|văn học|thơ|sân khấu|điệu múa)\b",
    ),
    (
        "Công nghệ",
        r"\b(máy tính|điện thoại|máy móc|thiết bị|phần mềm|internet|mạng|dữ liệu|máy ảnh)\b",
    ),
    (
        "Nhà cửa",
        r"\b(ngôi nhà|nhà cửa|căn phòng|cửa|mái|tường|sàn|trần|cầu thang|sân|giường)\b",
    ),
    ("Trang phục", r"\b(quần áo|mặc|áo|quần|giày|dép|vải|may|khăn|trang phục)\b"),
    (
        "Số lượng và hình dáng",
        r"\b(số lượng|hình dáng|hình dạng|kích thước|hình tròn|hình vuông|chiều dài|chiều rộng)\b",
    ),
]


def category(answer, definition, pos):
    text = answer + " " + definition
    for name, pattern in TOPICS:
        if re.search(pattern, text, re.I):
            return name
    return {
        "N": "Đời sống quanh ta",
        "V": "Hoạt động thường ngày",
        "A": "Tính chất quen thuộc",
    }[pos]


def build():
    dictionary_file = ROOT / "private/classroom-dictionary-source.json"
    frequency_file = ROOT / "private/classroom-compound-frequency.tsv"
    expected = {
        "dictionary": "fb41663096d6a24de8854567e5a4c5aded5bf39ce7bc2172d3cd0211c360c763",
        "frequency": "8f644d06173600f8acb0d2b1a9dd0111c53ef304b9974b76e2cb24bad81fe04d",
    }
    for name, file in [("dictionary", dictionary_file), ("frequency", frequency_file)]:
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected[name]:
            raise ValueError(
                f"{name} source checksum changed; review before rebuilding"
            )
    dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
    rank = {}
    for line in frequency_file.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            rank[parts[2].replace("_", " ")] = int(parts[0])
    old = []
    for file in [
        "vua_tieng_viet.vi.json",
        "classroom.vi.json",
        "classroom.hard.vi.json",
    ]:
        old += json.loads((ROOT / "knowledge" / file).read_text(encoding="utf-8"))

    def canonical(text):
        return re.sub(r"^(cai|con|qua|chiec) ", "", normalize(text))

    excluded = {canonical(w["answer"]) for w in old}
    function_words = set(
        "không là tôi có của anh được cho các trong với đi phải để cô làm ta em biết đến ra lại về con nói vào đang cậu còn thì cái chỉ bạn nhiều muốn từ sao trên mình năm hơn bị thấy thế việc cần nhà tới lên sau thôi theo nên chuyện sự nghĩ vì điều ngày mới trước thứ khác hay thật tốt nghe qua đúng mẹ tìm cùng lần nước cách đừng tên giờ đưa ngay giúp nhìn nhau chết lúc xem gặp bằng tin bên lấy đều cháu gọi chính tao cao nơi".split()
    )
    rows = []
    for answer, senses in dictionary.items():
        if (
            answer in function_words
            or answer not in rank
            or rank[answer] > 15000
            or canonical(answer) in excluded
            or answer != answer.lower()
            or not 3 <= len(answer) <= 32
            or not all(c.isalpha() or c == " " for c in answer)
            or not 1 <= len(answer.split()) <= 4
            or BLOCK.search(answer)
            or (len(answer.split()) == 1 and rank[answer] > 2000)
        ):
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(answer) + r"(?!\w)", re.I)
        choices = []
        for sense in senses:
            raw = sense.get("definition", "")
            definition = clean(raw)
            pos = sense.get("pos", "")
            if (
                pos not in ("N", "V", "A")
                or not 22 <= len(definition) <= 140
                or BLOCK.search(raw)
                or "(" in raw
                or ")" in raw
                or normalize(answer) in normalize(definition)
            ):
                continue
            examples = [
                clean(x)
                for x in sense.get("example", "").split("~")
                if 12 <= len(clean(x)) <= 100
                and pattern.search(x)
                and not BLOCK.search(x)
            ]
            examples = [
                x
                for x in examples
                if not re.search(
                    r"(?<!\w)" + re.escape(normalize(answer)) + r"(?!\w)",
                    normalize(pattern.sub("...", x)),
                )
            ]
            if not examples:
                continue
            example = min(examples, key=lambda x: abs(len(x) - 42))
            if example.count(" ") - answer.count(" ") < 2:
                continue
            choices.append(
                (len(definition) + abs(len(example) - 42), pos, definition, example)
            )
        if choices:
            _, pos, definition, example = min(choices)
            rows.append((rank[answer], answer, pos, definition, example))
    rows.sort()
    seen = set()
    unique = []
    for row in rows:
        key = normalize(row[1])
        if key not in seen:
            unique.append(row)
            seen.add(key)
    # Moderately challenging familiar qualities/actions, not obscure specialist terms.
    hard = [
        row
        for row in unique
        if row[2] in ("A", "V")
        and 500 < row[0] < 11000
        and len(row[1].split()) >= 2
        and 6 <= len(row[1]) <= 22
    ][:470]
    hard_keys = {row[1] for row in hard}
    normal = [row for row in unique if row[1] not in hard_keys][:2000]
    if len(normal) != 2000 or len(hard) != 470:
        raise ValueError((len(unique), len(normal), len(hard)))
    result = []
    for row, difficulty in [(r, "normal") for r in normal] + [
        (r, "hard") for r in hard
    ]:
        frequency, answer, pos, definition, example = row
        masked = re.sub(
            r"(?<!\w)" + re.escape(answer) + r"(?!\w)", "...", example, flags=re.I
        )
        hint1 = definition[0].upper() + definition[1:] + "."
        cloze = masked[0].upper() + masked[1:] + "."
        hint2 = next(
            prefix + cloze
            for prefix in ["Điền từ còn thiếu: ", "Hoàn thành câu: ", "Ví dụ: ", ""]
            if not re.search(
                r"(?<!\w)" + re.escape(normalize(answer)) + r"(?!\w)",
                normalize(prefix + cloze),
            )
        )
        parts = answer.split()
        hint3 = (
            f"Từ gồm {len(parts)} tiếng. Tiếng đầu là “{parts[0]}”; tiếng sau bắt đầu bằng “{parts[1][0]}”."
            if len(parts) > 1
            else f"Từ có {len(answer)} chữ cái, bắt đầu bằng chữ “{answer[0]}”."
        )
        explanation = hint1 + " Ví dụ: " + example[0].upper() + example[1:] + "."
        result.append(
            {
                "answer": answer,
                "category": category(answer, definition, pos),
                "difficulty": difficulty,
                "hints": [hint1, hint2, hint3],
                "explanation": explanation,
            }
        )
    proverb_rows = json.loads(
        (ROOT / "knowledge/classroom.proverbs-new.vi.json").read_text(encoding="utf-8")
    )
    assert len(proverb_rows) == 30
    result.extend(proverb_rows)
    (ROOT / "knowledge/classroom.expanded.vi.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    policy = {
        "version": 1,
        "excluded_answers": [w["answer"] for w in old],
        "reason": "Operator requested skipping the original 257 questions; retain their data.",
    }
    (ROOT / "knowledge/classroom-bank-policy.json").write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = {
        "new_questions": len(result),
        "legacy_questions": len(old),
        "total_questions": len(old) + len(result),
        "active_questions": len(result),
        "difficulty": dict(Counter(w["difficulty"] for w in result)),
        "categories": dict(Counter(w["category"] for w in result)),
        "dictionary_sha256": hashlib.sha256(dictionary_file.read_bytes()).hexdigest(),
        "frequency_sha256": hashlib.sha256(frequency_file.read_bytes()).hexdigest(),
    }
    (ROOT / "logs/classroom-expansion-build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    print("SAMPLE_NORMAL:", ", ".join(w["answer"] for w in result[:70]))
    print("SAMPLE_END:", ", ".join(w["answer"] for w in result[1920:2000]))
    print("SAMPLE_HARD:", ", ".join(w["answer"] for w in result[2000:2050]))


if __name__ == "__main__":
    build()
