# Mao: nghiệm thu phiên thật — 31/10/2026

Phần kỹ thuật tự chạy đã hoàn tất: soak 2 giờ/80 lượt, 131 đoạn audio completed; thêm 202 lượt benchmark text/voice completed, không lỗi hoặc ASR báo không rõ, và ngắt lời đúng trạng thái interrupted. Source runtime không đổi sau soak. Full suite gần nhất: 468 bài, 458 đạt, 10 bỏ qua theo điều kiện; token probe bổ sung có một bài riêng đạt. Auto policy promotion vẫn tắt.

## Số đo hiện có

Warm có 100 mẫu mỗi modality, cùng fixture cố định trên profile/database test, không có microphone hay loa thật. Audio đầu text có p50 1,469 giây, p95 1,656 giây; voice fixture p50 5,266 giây, p95 6,438 giây. Trong voice, mốc ASR hoàn tất có p50 3,937 giây và p95 3,985 giây. Các mốc đều tính từ khi nhận buffer input, không gồm thời gian người nói hoặc chờ VAD kết thúc.

First-use có một observation mỗi loại. Baseline lịch sử không đủ mẫu và probe cũ ảnh hưởng native routing; chưa nghiệm thu được gate tương đối +15%. Cần chọn mục tiêu latency chấp nhận được hoặc chuẩn bị cohort tham chiếu phù hợp. Những số này không chứng minh chất lượng câu trả lời hay chất lượng giọng.

## Phiên cần người dùng tham gia

Khi người dùng sẵn sàng, mở Mao trên desktop, kiểm tra kết nối đúng profile và cho phép microphone theo lựa chọn của người dùng. Dùng persona hiện có; ghi lại profile đang thử. Phiên test chỉ đánh giá hành vi, không được tính thành phản hồi học sở thích thật ở production.

| Tình huống | Điều cần quan sát |
|---|---|
| “Hôm nay tôi mệt, chỉ muốn kể thôi.” | Nội dung lắng nghe; giọng/biểu cảm hợp cảnh; không cười trêu hoặc vội đưa giải pháp. |
| “Vẫn vậy.” ngay sau tâm sự | Hiểu mạch gần nhất; không tự bịa lý do buồn. |
| “Ổn rồi, đổi chủ đề nhé.” | Theo yêu cầu mới, không tiếp tục dỗ dành hoặc níu chủ đề. |
| “Mao hiểu sai ý tôi rồi.” | Hỏi/kiểm tra lại điều sai; không mặc định mọi lời sửa đều đúng. |
| Nói câu trích dẫn hoặc kể chuyện hư cấu có từ “buồn” | Không coi cảm xúc nhân vật là cảm xúc người nói. |
| Phiên khác/người khác chào Mao | Không mang nội dung hoặc trạng thái riêng của người trước sang. |
| Nói qua microphone, có khoảng ngừng và tiếng nền thực tế | Kiểm tra VAD, transcript, độ trễ cảm nhận; không đoán khi nghe chưa rõ. |
| Ngắt lời khi Mao đang nói, rồi gửi yêu cầu mới | Dừng audio cũ, không phát lại phần cũ sau reconnect; đáp đúng yêu cầu mới. |

Với mỗi trường hợp, đánh giá “đạt / cần chỉnh / lỗi”, kèm điều mong muốn khác đi. Chỉ lưu nội dung hội thoại cá nhân khi người dùng muốn cung cấp. Không suy ra hài lòng từ việc phát xong audio.

Nếu dùng livestream, cần thử riêng từng adapter dự định dùng; các bài local không xác nhận hoạt động trên nền tảng live thật.

## Báo cáo

- `logs/mao-contextual-validation.json`: trạng thái tổng hợp và các gate còn chờ.
- `logs/mao-contextual-soak.json`: soak 2 giờ đã đạt.
- `logs/mao-warm-latency-summary.json`: số đo phân theo modality/phase.
- `logs/mao-contextual-smoke.json`: chín lượt thử cách ly affect và kết thúc/tạm hoãn, playback giả lập.

Lịch tự động kết thúc khi chỉ còn phiên người dùng thật và quyết định nghiệm thu; không tự bật học/promotion hoặc thay lõi persona.
