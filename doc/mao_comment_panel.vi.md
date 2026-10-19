# Bảng bình luận Mao Link

Bảng kính nổi bên trái dùng xanh ngọc, bạc và kem theo Mao: huy hiệu chữ M, lưới hologram nhẹ, viền cắt góc và thẻ bình luận. Hiện tên người gửi, nền tảng và nội dung; `!vuatiengviet`, `!sing`, `!songs`, `!baihat` có màu và nhãn riêng. Không tự tạo người xem hoặc bình luận mẫu trong desktop thật.

Disco hiển thị tối đa bốn bình luận gần nhất, mới nhất ở trên; khi chơi hoặc hiện kết quả, bảng thu thành một thẻ dưới bên trái, không đè ô chữ. Vùng hiển thị tính theo phần 3D còn lại phía trên footer. Pet Mode ẩn bảng; khung quá hẹp dưới 420 px cũng ẩn để không che nhân vật. Tôn trọng giảm chuyển động của hệ thống.

Sau mỗi vòng Vua tiếng Việt có CD chung 30 giây. Footer Mao Link hiển thị “Vòng mới sau Ns”, tự đếm theo thời gian server. Sau 15 giây kết quả, Mao trở về disco và thời gian chờ còn lại vẫn hiện ở đây; spam lệnh không mở vòng mới hoặc khiến Mao đọc nhắc lại.

Trong lúc chuẩn bị/hát, footer báo “Tiết mục của Mao”; hết bài đếm CD hát 30 giây bằng “Bài mới sau Ns”. Bảng bình luận vẫn nhận nội dung khi hát. Phản hồi `!songs` hoặc lỗi chọn bài hiện trên thẻ âm nhạc bên phải, không tạo lượt nói cho mỗi lệnh.

## Luồng dữ liệu

- `BufferedLiveChat` gửi sự kiện `live-comment` ngay khi có bình luận được chấp nhận, kể cả trong lúc Mao đang nói. Hàng đợi hiển thị tối đa 60 mục; lỗi kết nối giữ mục để thử lại. Hàng đợi trả lời bằng giọng vẫn riêng và không bị ngắt.
- Bình luận/đáp án trò chơi lấy từ `game-comment`, lệnh và chat desktop lấy từ `text-input` thật. Không đưa hướng dẫn host hoặc bản tóm tắt nội bộ lên bảng. Sự kiện hiển thị không được gửi vào agent hay dùng để bắt đầu/chấm trò chơi.
- `CommentFeed` giữ tối đa 60 bình luận trong RAM, giới hạn tên 40 và nội dung 300 ký tự, chống trùng theo nguồn + mã sự kiện. Không lưu thêm lịch sử bình luận xuống đĩa. Backend khởi động lại tạo session mới.
- `GET /api/comments?after=...&session=...` trả phần mới. `comment-panel.mjs` lấy dữ liệu mỗi 700 ms khi cửa sổ hiển thị, lùi nhịp khi mất kết nối; giữ tối đa 20 mục phía client. Hủy bộ lấy dữ liệu khi renderer đóng.
- Nội dung người xem được gán bằng `textContent`, không nội suy thành HTML hoặc lệnh. Bảng không nhận chuột và không tự gửi lệnh từ nội dung bình luận.

Mã giao diện: `web_tool/mao-5070/draco/comment-panel.mjs`; gắn trong `native-avatar.mjs`. API thuộc proxy đang dùng, không mở thêm một kết nối phát tiếng.

Xem trước: `http://127.0.0.1:12393/web-tool/mao-5070/word-game-scene-preview.html`. Dữ liệu trên trang này được đánh dấu minh họa và lấy từ fixture riêng, không gửi vào game hoặc bộ đọc live thật.

Kiểm tra: `tests/test_comment_feed.py`, `tests/test_comment_panel.mjs`, các kiểm tra luồng gộp bình luận, trò chơi và shell desktop hiện có.
