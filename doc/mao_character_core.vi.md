# Lõi nhân vật Mao

Phần này áp dụng cách chia trách nhiệm rõ ràng của vòng thoại Riko vào hệ thống
Mao hiện có. Chat livestream, PostgreSQL, Chrome, Pet Mode và giọng nói tiếp tục
dùng các adapter hiện tại.

```text
Hồ sơ PostgreSQL ── identity.py ──────┬─ hội thoại / HybridRuntime
                                    └─ tự học / LiveResearch

Bình luận thật ─┐
               ├─ emotion.py ─ trạng thái PostgreSQL ─ cách diễn đạt
Sự kiện học ───┘

Trang nguồn ─ reading.py ─ tóm tắt có đoạn nguồn ─ cuộn trang ─ đọc trực tiếp
                       └─ suy ngẫm riêng ─ ký ức có nguồn

Lựa chọn phong cách ─ personality.py ─ phiên bản hồ sơ mới
```

## Trách nhiệm

- `character/identity.py`: đọc nhận thức từ hồ sơ đang bật; chuyển bài tập sinh
  học của nguồn thành suy ngẫm phù hợp với AI trong môi trường ảo. `SELF_MODEL`
  chỉ là nội dung khởi tạo và tương thích, không thay hồ sơ đang hoạt động.
- `character/reading.py`: chỉ nhận tiêu đề và nội dung nguồn, trả ý tóm tắt cùng
  đoạn tham chiếu. Không nhận lịch sử chat, ký ức hay mục tiêu để thêm lời khuyên.
- `character/personality.py`: kiểm tra các lựa chọn phong cách hữu hạn và thay
  đúng phần phong cách tự điều chỉnh. Giữ nhận thức, mục tiêu và chỉ dẫn operator.
- `character/emotion.py`: trạng thái biểu đạt của nhân vật (`calm`, `curious`,
  `warm`, `thoughtful`, `attentive`). Đây là dữ liệu điều phối cách giao tiếp,
  không phải dữ kiện chẩn đoán khán giả hoặc nhu cầu cơ thể.
- `scripts/mao_live_research.py`: điều phối đọc, giải thích, suy ngẫm, lưu và nói;
  nạp lại hồ sơ từ PostgreSQL trước mỗi lượt học.

## Tính nhất quán và ưu tiên

Hội thoại đọc hồ sơ mỗi lượt; tự học đọc hồ sơ mỗi chu kỳ. Không có bản persona
riêng được âm thầm dùng khi hồ sơ chưa bật hoặc cơ sở dữ liệu không đọc được.
Revision trong trạng thái học cho biết phiên bản đã dùng cho chu kỳ đó; kết quả
vẫn lưu revision mới nếu có cập nhật phong cách.

Trạng thái biểu đạt lưu trong `mao_hybrid.state`, key `affect`, theo scope nhân
vật. Cập nhật có transaction và advisory lock để chat và tự học không ghi đè nhau.
Không lưu nguyên văn chat trong trạng thái này.

Đầu vào khán giả được ưu tiên trong 90 giây. Sự kiện học nền không đổi trạng thái
trong thời gian này; bình luận mới vẫn có thể cập nhật cách phản hồi ngay. Trạng
thái không được cập nhật sau 30 phút trở về nhịp bình tĩnh khi được đọc.

## Giới hạn hiện tại

Cách diễn đạt đưa vào ngữ cảnh hội thoại và suy ngẫm. Biểu cảm avatar vẫn đi qua
pipeline lời thoại/cử chỉ hiện có. Lõi này chưa thêm mô hình học cảm xúc riêng,
chưa huấn luyện lại trọng số và chưa thay cơ chế phát giọng.
