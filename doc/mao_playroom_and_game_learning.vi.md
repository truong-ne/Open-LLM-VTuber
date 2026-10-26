# Mao Playroom và học từ game thật

Mao chơi trang bên ngoài https://2048game.com/ trong Google Chrome riêng. Dự án không tạo lại game, không dùng iframe giả và không sửa bàn cờ hay điểm của website. Tab Chrome cá nhân không được dùng làm phiên điều khiển.

## Đường đi hiện tại

```text
Website 2048 thật → đọc ô DOM → chọn mũi tên → Chrome thực hiện
                         ↓                         ↓
                 luật kiểm chứng ← đọc bàn cờ / điểm mới
                         ↓
              PostgreSQL: lịch sử + chọn chiến thuật
                         ↓
               Qwen: gợi ý thử nghiệm, chưa xác minh
                         ↓
              bộ nhớ skill của Mao + pgvector

Chrome Window Capture → OBS 1920×1080 → khung xanh/vàng + Mao 3D
                                          ↓
                          bản xem trước localhost, ảnh ~2 fps
```

OBS dùng ba lớp: nền Browser Source, Window Capture đúng cửa sổ Chrome, rồi Browser Source trong suốt chứa khung và Mao 3D. OBS lấy video cửa sổ trực tiếp ở cấu hình 30 fps; bản xem trong trình duyệt lấy ảnh cập nhật tối đa khoảng 2 fps. Không thu mic hoặc âm thanh máy; không có lệnh phát công khai trong công cụ này. Avatar dùng renderer có sẵn với chế độ portrait; cảnh phòng, nhảy và hát mặc định vẫn giữ nguyên.

## Chạy lại trên máy đã thiết lập

Từ thư mục dự án, mở PowerShell. Cần Docker Desktop engine hoạt động, PostgreSQL đã migrate bằng hướng dẫn hybrid, Python `.venv`, Playwright và Google Chrome đã cài. OBS portable riêng đã được thiết lập bằng hướng dẫn `mao_daily_learning_and_rehearsal.vi.md`. Không dùng OBS đang phát của bạn.

```powershell
docker compose -f compose.mao-hybrid.yaml --env-file private/mao-hybrid.env up -d
powershell -File scripts/start_mao_playroom.ps1
.\.venv\Scripts\python.exe scripts/mao_2048.py --games 6 --moves 250 --seconds 600 --learn --reflect --hold 300
```

Lệnh chơi chiếm cửa sổ PowerShell tới khi kết thúc. Chỉ chạy một bộ điều khiển với profile này. Trong cửa sổ PowerShell thứ hai, sau khi Chrome game đã mở:

```powershell
powershell -File scripts/start_mao_playroom_obs.ps1
```

Mở `http://127.0.0.1:12395/mao-5070/playroom.html?obs=1&game=2048`. Bấm **Che màn hình** hoặc Ctrl+Shift+H để che trong bản xem và tắt nguồn game thật trong OBS. Bấm **Hiện nội dung** để hiện lại. Chọn nguồn lại nếu cửa sổ game đóng. Lệnh OBS chỉ cấu hình khi không có stream/recording; không bắt đầu ghi hay phát.

Không có `--learn`, Mao sử dụng chiến thuật đã lưu thay vì luân phiên thử hai chiến thuật. `--reflect` cần Ollama localhost:11434 và model `mao-companion`. Nếu Qwen không chạy, phiên chơi vẫn lưu bằng chứng và báo reflection không khả dụng. Embedding dùng cấu hình hybrid hiện có; không đổi profile embedding âm thầm.

## Học được gì và giới hạn

- Hai chiến thuật hiện có là `merge` và `corner`, do bộ lập kế hoạch luật chọn nước đi. Qwen phân tích kết quả sau phiên, không quyết định từng phím trong adapter này.
- Mỗi lượt hợp lệ phải khớp độc lập: ghép đúng một lần, tăng điểm đúng, rồi chỉ xuất hiện đúng một ô 2 hoặc 4. Sai lệch thì ngừng và không tính ván đó vào bằng chứng thăng chiến thuật.
- Chỉ so sánh các ván cùng giới hạn lượt. Cần ít nhất 3 ván thật mỗi chiến thuật, trung bình tối đa 5 mẫu gần nhất; đổi khi ứng viên hơn 10%. Ván dừng vì hết thời gian không dùng để thăng chiến thuật.
- Đây là lựa chọn chiến thuật từ mẫu nhỏ, chưa phải kiểm định chất lượng tổng quát. Không huấn luyện trọng số Qwen. Gợi ý Qwen luôn có `hypothesis_verified=false`, không được tự sửa quyền hoặc tự chấm là đã tiến bộ.
- PostgreSQL scope `mao-game-2048` lưu `2048_runs` (40 ván gần nhất), `2048_strategy`, event lượt đi. Tóm tắt có nguồn và ID ván được lưu dạng skill ở scope Mao, có embedding khi dịch vụ sẵn sàng. Không thêm SQLite hoặc bảng DB mới.
- Mỗi phiên bị chặn ở 1–8 ván, 20–600 lượt/ván, 30–900 giây chơi, giữ cửa sổ thêm tối đa 300 giây. Chạy lại phiên sau sẽ đọc chiến thuật và ký ức đã lưu. Chưa bật lịch chạy nền hằng ngày.
- Chưa có adapter tự chơi game desktop bất kỳ hoặc Neuro SDK. Có thể dàn cảnh một cửa sổ thật khác bằng bộ chọn nguồn thông thường; để Mao hiểu và điều khiển game khác vẫn cần adapter/quan sát và phép đánh giá riêng.
- Đồng bộ khẩu hình/phụ đề/chat từ backend Mao là kết nối tùy chọn, chỉ đọc; cần backend và TTS đang chạy. Bài thử game này chưa thử thoại trực tiếp cùng phiên chơi.

## Quyền và quan sát

Chrome có profile riêng, sandbox bật, chỉ cho tài nguyên HTTPS cùng host game và GET/HEAD. Popup, download, service worker, websocket và quyền camera/mic bị chặn. Adapter chỉ đọc các ô số/điểm và gửi bốn phím mũi tên; văn bản website không được làm chỉ thị. Không có công cụ đọc file cá nhân, đăng nhập, thanh toán hoặc thực thi lệnh từ trang trong adapter này.

Máy chủ xem trước chỉ bind 127.0.0.1, phục vụ `web_tool/`. API ảnh cần token ngẫu nhiên; lệnh hide/show còn kiểm tra Origin và Host. Không có CORS mở; token và mật khẩu OBS không nằm trong URL hoặc log. Chọn cửa sổ theo tiêu đề chính xác; cửa sổ mất thì bản xem che và tắt nguồn thay vì nhận nhầm Chrome khác. Điều này không làm cho toàn bộ Windows trở thành một môi trường tự động an toàn; quyền computer-use tổng quát vẫn theo cấu hình hybrid riêng.

Log bằng chứng: `logs/mao-2048-session.json`, `logs/mao-game-review.json`; trạng thái giao diện tạm thời: `web_tool/mao-5070/state/game2048.json` (không commit). Che nguồn không phải nút dừng chơi: để ngừng bộ điều khiển, Ctrl+C tại cửa sổ chạy lệnh; phiên còn dở không được ghi như một ván hoàn tất.

## Cơ sở thiết kế

- OBS Window Capture: https://obsproject.com/kb/window-capture-sources
- OBS Browser Source: https://obsproject.com/kb/browser-source
- Screen Capture API: https://developer.mozilla.org/en-US/docs/Web/API/Screen_Capture_API/Using_Screen_Capture
- Tự phản tỉnh từ phản hồi bên ngoài: https://arxiv.org/abs/2303.11366
- Giới hạn tự sửa lỗi khi thiếu phản hồi đáng tin: https://arxiv.org/abs/2310.01798

Chọn đo trạng thái/điểm thật trước khi lưu kinh nghiệm, vì lời tự đánh giá của LLM không đủ làm bằng chứng tiến bộ.
