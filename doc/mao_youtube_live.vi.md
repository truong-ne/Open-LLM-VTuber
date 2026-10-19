# Mao đọc chat YouTube

Nguồn mặc định: **YouTube @sejuly-02**, https://www.youtube.com/@sejuly-02/live. `live_config.active_platform: youtube`; username TikTok cũ được bỏ khỏi cấu hình đang dùng. Transport TikTok vẫn giữ trong mã để không phá chức năng cũ, nhưng không chạy cùng YouTube.

## Chạy

Mở desktop bằng `scripts/start_mao_desktop.ps1 -Mode window` như trước. Launcher tự bật bộ đọc YouTube và đúng một host trò chuyện chủ động. `scripts/start_mao_live.ps1 -Restart` khởi động lại riêng bộ đọc; các helper chỉ dừng tiến trình thuộc Python của workspace này.

Kiểm tra kênh mà không chuyển bình luận vào Mao:

```powershell
.venv/Scripts/python.exe scripts/run_youtube_live.py --check
```

Nếu cần chỉ định một buổi live không công khai, điền URL đó vào `live_config.youtube_live.video_url` rồi khởi động lại bộ đọc. Để trống thì kiểm tra endpoint `/live` của kênh mỗi 30 giây khi offline. Chỉ video được trang YouTube xác nhận đang phát mới được nối chat; video đã kết thúc, lịch hẹn và trang kênh không có live đều không phát lại chat cũ.

## Hành vi

- Đọc luồng **Live chat**, chuyển khỏi **Top chat** bằng continuation trong phản hồi chat; token điều hướng trên trang watch không dùng làm token API.
- Nhận bình luận văn bản và phần lời nhắn Super Chat. Không suy diễn số tiền, lượt xem hoặc người mới vào. YouTube không cung cấp sự kiện cho từng người xem vừa mở live qua luồng này, nên không giả thông báo tham gia như TikTok trước đây.
- Gộp bình luận thành tối đa 3 ý chính, hàng đợi 20 bình luận; quá tải bỏ bình luận cũ nhất và tóm phần còn lại. Giữ nickname để Mao chào đúng tên khi được chào; không đọc điểm danh toàn bộ chat.
- Khi tác giả bình luận là một kênh khác đã xác minh có hơn 10.000 sub công khai, Mao nói “Wow!” và cảm ơn như một VTuber nhỏ được khách lớn ghé. Dùng channel ID gốc và metadata kênh, không tin tên hiển thị/tự xưng. Chạy kiểm tra bất đồng bộ có cache, không chặn bình luận và không nhận diện người xem thầm. Quy tắc, giới hạn và ngữ cảnh fan Độ Mixi xem [`mao_creator_guests.vi.md`](mao_creator_guests.vi.md).
- Chỉ gửi khi câu chuyện/lượt trả lời trước đã kết thúc thực sự. Không dùng timeout để cắt lời. Cùng ID bình luận được đánh dấu lâu dài trong `private/mao-comment-state.db`, namespace theo video YouTube; không trùng với ID TikTok.
- Trả lời bằng giọng nói qua VieNeu hiện tại. Bộ đọc không đăng bình luận lên YouTube, không điều khiển tài khoản, không mở buổi live hoặc gửi tin nhắn thay người dùng.
- Host chủ động dùng cùng luồng bận/rảnh; trả lời bình luận xong không tự lặp lại câu đó như một câu chuyện mới. Ký ức nhóm chat YouTube cũ được rút gọn và gắn nhãn đã xử lý.

Trạng thái: `private/mao-youtube-status.json`; log: `logs/youtube.stderr.log`, `logs/youtube.stdout.log`. `waiting-for-live` nghĩa là đang chờ buổi phát, không phải đã nối được chat thật. `error` giữ lý do ngắn để chẩn đoán. Không lưu tên/nội dung khán giả trong file trạng thái hoặc cơ sở dữ liệu chống trùng; hội thoại Mao vẫn dùng cơ chế lịch sử hiện có.

## Cách nối và giới hạn

Adapter dùng HTTP bất đồng bộ để đọc giao thức chat công khai của web YouTube, lấy cấu hình web hiện tại từ trang watch. Không yêu cầu API key cá nhân hoặc cookie đăng nhập; chỉ dùng HTTPX vốn đã có trong dự án. Có timeout mạng, hủy được khi tắt, thử lại khi kênh offline/lỗi. Không thêm thư viện đọc chat bên ngoài sau khi thư viện thử nghiệm không tương thích dữ liệu hiện tại.

Đây là adapter web không chính thức; khi YouTube thay đổi giao thức có thể cần cập nhật. API chính thức có [liveChatMessages.streamList](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/streamList); dự án hiện không cấu hình luồng xác thực đó.

## Kiểm tra

`tests/test_youtube_live.py` kiểm tra URL, live/replay/scheduled, giải mã tin nhắn, thông tin nickname, nguồn `youtube-live`, xác nhận lượt trả lời, chống trùng sau khởi động lại, gộp/bỏ bình luận khi quá tải và không lặp ở host chủ động. Bộ test TikTok/host/ngữ cảnh cũ vẫn qua sau khi tách hàng đợi dùng chung sang `buffered_chat.py`.

Ngày 19/10/2026: endpoint của @sejuly-02 trả trang kênh, chưa thấy video đang live. Đã kiểm tra adapter nhận tin nhắn từ một livestream công khai khác chỉ để xác minh giao thức; dữ liệu thử không được gửi vào Mao và không lưu tên khán giả. Việc Mao trả lời bình luận thật trên @sejuly-02 cần kiểm tra khi kênh bắt đầu phát và bật live chat.
