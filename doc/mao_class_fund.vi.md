# Quỹ lớp và bình luận phòng thường

Phòng thường dùng thẻ bình luận màu kem/xanh lá, tên và nội dung rõ hơn. Bảng Quỹ lớp ở góc trên phải hiển thị tổng coin và top 5 người tặng quà tích lũy theo tài khoản TikTok (màn hình rất hẹp hiện top 3). Độc lập với điểm lớp và vinh danh ngày. Không chèn dữ liệu minh họa vào bảng thật.

Bộ đọc TikTok nhận `GiftEvent`. Giá trị hiển thị = metadata `gift.diamond_count` × `repeat_count`, đơn vị giao diện là coin; không quy đổi thành doanh thu hay tiền mặt. Combo chỉ ghi sau khi `event.streaking` kết thúc, khử trùng bằng phòng + combo + người gửi + loại quà; quà đơn dùng ID sự kiện. Không dùng ID loại quà làm ID giao dịch. Nguồn hành vi combo: [TikTokLive — Gift streaks](https://ttl.docs.isaackogan.com/guides/gifts/).

Sổ quà SQLite `private/mao-gifts.sqlite3` lưu riêng, chống cộng trùng qua kết nối lại/khởi động lại. API GET `/api/live/gifts` chỉ trả tên công khai và tổng quà/coin, không trả ID người dùng. Quà mới đợi Mao kết thúc lượt đang nói rồi ưu tiên lời cảm ơn tiếp theo, không cắt tiếng. Không xen khi đang chơi hoặc hát. Lời cảm ơn là văn bản có chữ ký host, phát thẳng qua TTS; không đưa nickname/quà vào prompt LLM.

Sổ thông báo ghi khi xếp hàng thành công, không phải xác nhận người nghe đã nghe. Nếu ứng dụng dừng đột ngột sau khi xếp hàng thì lời cảm ơn đang chờ có thể không phát; tổng coin vẫn được lưu. Quà cũ hơn 10 phút vẫn có trên bảng nhưng không đọc lại khi mở ứng dụng. Kiểm thử dùng cơ sở dữ liệu tạm và giao diện minh họa riêng trong logs.
