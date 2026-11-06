# Cải thiện Mao sau các phiên LIVE ngày 05–06/11/2026

## Các thay đổi

| Nhóm | Kết quả |
|---|---|
| 1. Bình luận bị sót | Thêm nhật ký theo ID sự kiện: nhận, chờ, tiếp nhận lượt, tạo giọng, đang phát, đã phát; ghi lý do bỏ qua và trạng thái chưa xác nhận. Không coi socket mở là bằng chứng nhận đủ bình luận. |
| 2. Ưu tiên bình luận | Mỗi lượt tối đa 3 ý khác nhau; phần dư giữ nguyên thứ tự trong hàng chờ. Hủy lượt tự thoại còn chờ khi có câu hỏi mới và gửi trạng thái hủy cho host. Không cắt lời đang phát. |
| 3. Cách đáp | Độ dài theo câu hỏi, ví dụ hội thoại ngắn, không tự chào hay mở cuộc phỏng vấn. Chọn món đơn giản có lựa chọn ngẫu nhiên thực sự từ các món được cung cấp; tránh tự chọn khi có điều kiện sức khỏe. |
| 4. Tính cách | Gom các thiết lập vào một hồ sơ có phiên bản, lưu PostgreSQL làm nguồn thực thi. Giữ papa, AI Việt Nam, avatar female Malfoy, cách trêu, không chia sẻ link model và giới hạn chủ đề chủ quyền. Sao lưu hồ sơ cũ trước khi áp dụng. |
| 5. Tự thoại | Xoay cả kho chủ đề có sẵn và chủ đề của hồ sơ, lưu lịch sử chủ đề/góc nhìn qua lần khởi động. Kiểm tra lại hàng chờ sau lúc chuẩn bị câu tự thoại. Chỉ hoạt động khi LIVE và desktop đang kết nối. |
| 6. Rủ chia sẻ | Khoảng cách tối thiểu 180 giây, ít nhất 3 lượt khác xen giữa; không rủ share trong 60 giây sau tương tác mới. Không biến mọi đoạn tự thoại thành quảng cáo. |
| 7. Ký ức | Thêm bộ nhớ có nguồn theo nền tảng + tài khoản LIVE + ID người xem. Nhớ cách gọi, món ăn, đồ uống, màu sắc, âm nhạc từ lời tự chia sẻ rõ ràng, cùng chuyện người xem chủ động hẹn kể tiếp. Không dùng tên hiển thị làm ID. Bỏ qua lời người thứ ba, câu trích dẫn, tình huống giả định, lời đùa và thông tin nhạy cảm. Có lệnh quên của chính người xem. |
| 8. Kết nối | Phân biệt offline, kết nối lại, kết nối và trạng thái quá cũ. Offline là trạng thái bình thường, kiểm tra lại sau 60 giây; lỗi kết nối kiểm tra lại sau 15 giây. Giữ mốc nhận gần đây trong quá trình thử lại, chống trả lời lặp bằng ID bền vững, đóng HTTP client khi kết thúc. |
| 9. Bảng điều khiển | Mở menu chế độ → **Theo dõi LIVE · Hàng chờ và bình luận**. Xem số câu chờ, câu tiếp theo, trạng thái Mao, lỗi phát và lịch sử từng bình luận. Bảng nằm trong menu vận hành, không tự mở trên khung phát. |
| 10. Lớp học | Giữ lịch sử câu hỏi qua phiên mới, tách theo tài khoản; ưu tiên đổi chủ đề nếu có câu phù hợp. Giữ 40 chỗ, 2 gợi ý/25 giây cho câu thường, 3 gợi ý/40 giây cho câu khó, bảng vinh danh và toàn bộ tệp câu hỏi. |

## Dữ liệu và phục hồi

- Nhật ký bình luận lưu cục bộ tối đa 20.000 mục, nội dung trong 7 ngày. Khóa chống lặp cũ vẫn được giữ theo cơ chế hiện có.
- Sở thích người xem tối đa 2.000 mục, chỉ dùng mục còn hạn 90 ngày; mỗi mục giữ nguồn sự kiện và được đánh dấu chưa kiểm chứng. Đây là ghi nhớ có chọn lọc, không phải tự huấn luyện hay tự sửa persona.
- Có thể bình luận **“Quên sở thích của tôi”** để xóa các mục của đúng ID đó trong kênh. Không xử lý yêu cầu xóa của người khác dựa trên tên hiển thị.
- Khi người xem nói rõ **“để lần sau kể tiếp”**, Mao có thể dùng lại mạch chuyện có nguồn của đúng ID đó. **“Chuyện đó xong rồi”** đóng mạch chuyện này, không xóa các sở thích khác.
- Lượt bị từ chối vì bận được trả về hàng chờ. Sau đứt kết nối, lượt gửi lại dùng cùng ID để backend chống lặp. Không tự nhận đã phát khi thiếu xác nhận desktop.
- Khôi phục các bình luận chưa gửi, còn trong 120 giây khi bộ đọc khởi động lại. Không tự phát lại lượt đã gửi mà chưa biết kết quả.
- SQLite được sao lưu nhất quán trong `private/backups/live-review-2026-11-06/`. Hồ sơ cũ ở `private/mao-profile-before-live-review-r*.json`.
- `scripts/review_mao_live.py --verify` kiểm tra checksum 6 tệp ngân hàng/chính sách, trạng thái lớp, điểm vinh danh và sổ trao thưởng.

## Kiểm tra

- Hàng chờ, sự kiện lặp, thử lại, phục hồi và xác nhận phát: `tests/test_tiktok_batching.py`.
- Nhường lượt, thời gian nghỉ, xoay chủ đề và rủ share: `tests/test_idle_host.py`.
- Di trú audit, phạm vi ký ức, điều kiện chọn món và API vận hành: `tests/test_live_operations.py`.
- Lưu điểm, vinh danh, lịch sử câu hỏi qua phiên/tài khoản, ngân hàng 2.500 câu: `tests/test_classroom.py`, `tests/test_classroom_bank.py`.
- Chơi game, nhận diện và tạm chờ câu trả lời: `tests/test_vua_tieng_viet.py`, `tests/test_mao_self_model.py`, `tests/test_dialogue_attention.py` (database test riêng).
- Bố cục dọc, 40 avatar offline, vinh danh cập nhật, popup và bảng theo dõi: `tests/test_classroom_layout.py`, cùng các bài kiểm tra Node về desktop/IPC/phụ đề.
- Thử trực tiếp 5 tình huống với model đang dùng; kết quả và câu trả lời ở `logs/mao-live-review-style-eval.json`.

## Giới hạn cần đối chiếu ở phiên LIVE tiếp theo

LIVE đã kết thúc trong lúc triển khai. Kiểm tra cục bộ không chứng minh TikTok chuyển đủ mọi bình luận trong phiên tiếp theo. Các câu chưa từng đến bộ đọc không thể tự khôi phục từ nhật ký này; không suy ra rằng Mao chặn riêng Mèo Gian Khổ. Việc đánh giá độ duyên, mức lặp và nhịp nói vẫn cần nghe thực tế trong phiên tiếp theo.

Không nhập lại hàng loạt bình luận cũ thành ký ức, không sửa điểm người chơi, không mở lớp mới và không bật tự huấn luyện hoặc tự tiến hóa persona.
