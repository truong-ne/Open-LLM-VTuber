# Mao: rà lỗi và sửa hồi quy hội thoại

Ngày 03/11/2026. Đợt này sửa các lỗi tái hiện được từ mã nguồn và báo cáo hiện có; không sửa persona PostgreSQL hoặc mở tự nâng chính sách.

## Lỗi đã sửa

| Tình huống | Trước | Sau |
|---|---|---|
| “Chỉ muốn kể thôi. Bây giờ cho papa ba cách…” | Chọn listen vì từ khóa đầu, có thể bỏ yêu cầu mới hoặc không chạy tool cần thiết | Tách các mệnh đề rõ ràng và dùng yêu cầu sau cùng; yêu cầu theo chủ đề mới vẫn giữ nhãn change_topic |
| “Muốn yên tĩnh. Bây giờ Mao nói tiếp đi” | Plan và trạng thái lưu có thể không thống nhất | Cùng dùng hàm tách mệnh đề ở parser và điều khiển DB; trạng thái resume cập nhật cho đúng actor |
| “Tính 2+3 rồi giúp viết câu chúc…” | Đường trả lời trực tiếp chỉ đưa 5 rồi bỏ phần việc tiếp | Yêu cầu ghép chuyển lại cho model xử lý đầy đủ |
| “Tính 2+3, đừng trả lời đáp án…” | Đường tính nhanh đưa kết quả; khi nhường lại model thì model vẫn có lúc nói đáp án | Với phép tính nguyên đơn giản được hỗ trợ, đưa cách đếm/nhóm mà không nêu kết quả cuối; yêu cầu ghép/không hỗ trợ vẫn để model xử lý |
| “Tính 2+3=?” | Dấu bằng bị coi là toán tử dư, bỏ đường tính xác định | Nhận dạng dấu hỏi là vế kết quả còn trống |
| Quiet/resume sinh nhiều câu tự giới thiệu | Cả đoạn có thể đi vào TTS và ký ức | Buffer speech-only, giữ một câu xác nhận hoàn chỉnh tối đa 35 từ, loại thuyết minh AI/metadata; chỉ lưu/phát phần được giữ |
| “Không cần phải là ai đó…” | Grader báo nhầm từ tiếng Việt ai thành acronym AI | Nhận biết AI viết hoa hoặc cụm AI VTuber/trí tuệ nhân tạo; grader lên version 4 |

Bộ giới hạn lời nói không thay đại từ hàng loạt, không áp dụng cho câu trả lời bình thường, bản dịch hoặc truyện. Khi không còn câu xác nhận phù hợp, dùng “Được rồi.”; câu này không tự khẳng định đã tắt công cụ, microphone hoặc mọi âm thanh. Lỗi provider và sự kiện không phải speech không bị biến thành xác nhận thành công. Stream được đóng qua finally.

Đường gợi ý số học không dùng `eval`, không sinh chuỗi công cụ và không nhận code/biểu thức nhiều phép toán. Nó chỉ là lối đáp hẹp cho các phép cộng/trừ/nhân có số nguyên được hỗ trợ, không phải bộ giải toán hay cơ chế giấu đáp án tổng quát.

## Kiểm chứng

- Full Python/PostgreSQL: 568 bài, 558 đạt, 10 bỏ qua theo điều kiện; không failure/error. Lint đạt.
- Có test tích hợp BasicMemoryAgent kiểm tra quiet/resume chỉ đưa phần đã giới hạn tới pipeline và `_add_message`; không chỉ kiểm tra helper offline.
- Có test PostgreSQL cho trạng thái yên tĩnh/resume trong cùng một đầu vào, cùng actor/phòng/visibility.
- Bộ lỗi mới: tám lượt, chạy hai lần với model local, tổng 16 lượt; không lỗi chọn mode, quiet state hoặc route trực tiếp. Có một `output_truncated` do câu trả lời ba phương án vượt ngân sách 384 token của evaluator; giữ nguyên lỗi đó trong báo cáo. Không có cờ nội dung sau lọc trong mẫu này; bốn lượt trước lọc có cờ. Hai lượt cần lời đáp dự phòng control.
- Bộ hồi quy ban đầu: 22 lượt, không lỗi contract hoặc cờ sau lọc trong mẫu này; không cần lời đáp dự phòng. Không coi không có cờ là chứng minh câu trả lời tự nhiên hoặc đúng mọi kiến thức.

Đầu ra gốc, đầu ra cuối và response_origin được giữ riêng. Các báo cáo:

- `logs/mao-bugfix-final-tests.log`.
- `logs/mao-bugfix-final-live.json` và `.md`.
- `logs/mao-bugfix-final-regression.json` và `.md`.

Vẫn cần sửa/đánh giá thêm: câu trả lời thông thường có thể dài, cách xưng hô chưa được bảo đảm chỉ bằng prompt, bộ phân loại ý định vẫn là quy tắc hẹp và grader còn có thể báo nhầm/bỏ sót. Chưa kiểm tra nghe microphone/TTS/loa thật ở đợt này. Backend đang chạy mã cũ cần khởi động lại; không cần migration mới.
