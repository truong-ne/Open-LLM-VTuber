# Dọn workspace và tối ưu — 19/10/2026

Đã dọn 156 file, 136.021.047 byte (129,72 MiB): audio cache tự sinh đã cũ, log debug ngày cũ, archive Linh Lan đã giải nén, package được tải để xem xét và các script kiểm tra tạm của lần nâng cấp model/giọng. Mẫu giọng đã chia sẻ, model đang dùng, runtime, lịch sử chat, bộ nhớ, avatar và nguồn build desktop được giữ lại. Báo cáo chi tiết ở `logs/workspace-cleanup.json`.

`scripts/cleanup_workspace.ps1` mặc định chỉ thống kê; dùng `-Apply` để dọn. Chỉ chọn danh sách file tạm đã biết, WAV có tên cache chuẩn cũ hơn một giờ và log debug của ngày trước đã ngừng ghi ít nhất một giờ. Archive Linh Lan chỉ được xóa khi SHA256 của hai file đã giải nén khớp bản đã kiểm tra. Mọi đường dẫn phải nằm trong workspace; từ chối symlink/junction ở đường dẫn, tổ tiên hoặc bên trong thư mục cần xóa. Không dùng script để xóa venv, model cache hay nguồn build.

MCP khởi tạo prompt, schema và executor từ cùng một lần khám phá công cụ, thay cho hai lượt mở lại các server time/search trên mỗi context. Điều này giảm một nửa các lần khám phá khi khởi tạo kết nối; không phải cam kết giảm một nửa độ trễ trả lời.

Log backend mặc định theo mức INFO; `--verbose` vẫn bật DEBUG. Không lặp toàn bộ message và schema công cụ trong mỗi yêu cầu LLM. Log file ghi qua hàng đợi, xoay ở 10 MB, nén gzip và giữ bảy ngày thay vì ba mươi ngày.

RVC đóng cả hai pipe, kết thúc thread đọc và bỏ exit hook khi không còn dùng. Broken pipe, dữ liệu phản hồi lỗi và timeout đóng worker để tránh giữ tiến trình/GPU không còn hoạt động đúng. Cấu hình giọng, tốc độ và xử lý âm thanh không đổi.

Kiểm tra: 146 bài Python đạt; gồm khám phá MCP một lần, lỗi khám phá, vòng đời RVC, input/sample rate, timeout, biểu cảm, xếp hàng hội thoại và luồng live chat. Kiểm tra thực tế lại âm thanh qua WebSocket sau khi nạp backend.
