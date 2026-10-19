# Mao trong Pet Mode

Mao là nhân vật desktop trong suốt với động tác theo ngữ cảnh. Cài đặt desktop hiện tại ở `private/tools/vtuber-desktop/`, dùng proxy local `ws://127.0.0.1:12393/proxy-ws` và giọng VieNeu.

Adapter `web_tool/pet-context.js` gắn cử động với câu đang phát: chào/đồng ý → gật đầu, tò mò → nghiêng đầu, phản đối → lắc đầu, được khen → ngượng, chuyện vui → đung đưa nhẹ. Backend chuyển thẻ hợp lệ thành `actions.motions` rồi bỏ thẻ khỏi văn bản được đọc. Client phản hồi `pet-motion-played` khi động tác đã bắt đầu hiển thị.

Các vòng Idle/Talk ngẫu nhiên của desktop và bộ hẹn tự nói mặc định vẫn tắt để tránh nhiều nguồn nói cùng lúc. Chớp mắt, hơi thở và tương tác chạm được giữ. Lượt chủ động sau 10 giây yên chat do `IdleHost` trong bộ đọc TikTok quản lý, độc lập với hoạt ảnh.

Chạy `scripts/start_mao_live.ps1` để bật server và đọc chat. Mở desktop client; nếu vừa khởi động lại server mà chưa nối lại, tải lại cửa sổ desktop. Xem `doc/mao_livestream_design.vi.md` cho cấu hình persona, bộ nhớ và nhịp hội thoại.

Nhận diện tiếng Việt dùng Faster Whisper `large-v3-turbo`, CPU int8, 8 luồng; GPU dành cho Gemma 3 12B. Không cần API key. Bản ghi có độ tin cậy thấp khiến Mao hỏi lại thay vì đoán nội dung; khoảng lặng không gửi sang mô hình hội thoại. Âm thanh PCM 16-bit từ VAD được chuẩn hóa về khoảng [-1, 1] trước khi nhận diện. Độ tin cậy không phát hiện được mọi trường hợp nghe nhầm.

Các script thử ASR tạm dùng trong lúc thiết lập đã được dọn. Kiểm tra lại bằng microphone thật khi cần đánh giá độ chính xác với giọng của người dùng.
