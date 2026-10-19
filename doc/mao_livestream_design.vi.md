# Vận hành Mao VTuber

Ngữ cảnh duy nhất cho nhân vật là [`prompts/mao_context.vi.md`](../prompts/mao_context.vi.md): Mao là anime AI Malfoy phiên bản nữ. Nghiên cứu, cách đồng bộ và phạm vi dọn ngữ cảnh xem [`mao_context.vi.md`](mao_context.vi.md). Tài liệu này chỉ mô tả vận hành.

## Khởi chạy

```powershell
& scripts/start_mao_desktop.ps1 -Mode window
```

Desktop dùng avatar Draco 3D, có thể chuyển sang Pet Mode. Giọng đầu ra hiện tại là Linh Lan Ch qua RVC, lời nền từ VieNeu; model local `mao-companion` dựa trên Qwen3.5 9B. Thay ngữ cảnh bằng `scripts/configure_mao.py` không thay các cài đặt này. Sau khi đồng bộ ngữ cảnh cần nạp lại backend; `start_mao_desktop.ps1 -Restart` chỉ khởi động lại desktop.

## Luồng trò chuyện

Bộ đọc live theo cấu hình hiện hành, gộp bình luận cùng ý và ưu tiên câu hỏi mới. Hàng đợi chờ âm thanh thực sự kết thúc mới mở lượt tiếp theo. Trạng thái chống xử lý lại bình luận lưu trong `private/mao-comment-state.db`; không coi reconnect là một sự kiện chat mới.

Lượt chủ động nối mạch ngắn, không mặc định kể chuyện. Có khoảng chờ cho người xem đáp sau câu hỏi, không tự trả lời thay họ. Nhịp thực tế lấy từ cài đặt host, không phải tiểu sử nhân vật. Chi tiết theo nguồn: [`mao_youtube_live.vi.md`](mao_youtube_live.vi.md).

## Bộ nhớ và hoạt động

Cửa sổ gần hiện giữ tối đa 24 thông điệp, tóm tắt phần cũ theo cấu hình. Đây là ngữ cảnh hội thoại, không phải huấn luyện trọng số. Profile mới tách lịch sử nhập vai cũ; các lịch sử và hiệu chỉnh trước đây được giữ để có thể phục hồi.

Trạng thái phòng/cơ thể chỉ lấy từ renderer còn mới, không ghi thành ký ức lâu dài. Phòng mặc định là disco; Vua tiếng Việt mới chuyển cảnh anime. Quy tắc trò chơi và chấm điểm xem [`vua_tieng_viet.vi.md`](vua_tieng_viet.vi.md), giao diện và camera xem [`mao_tv_studio.vi.md`](mao_tv_studio.vi.md).
