# Trường quay Mao VTuber

Desktop mặc định là **phòng disco/lounge**, giữ tên **Mao VTuber**. Mao đứng giữa phòng và không tự đi lang thang; lệnh di chuyển, quay hướng và cử chỉ vẫn hoạt động. Chỉ khi có vòng `!vuatiengviet` mới chuyển sang cảnh Mao đứng trước TV. Sau khi bảng kết quả hết 15 giây, tự trở về disco; vị trí trong disco được giữ riêng với vị trí dẫn trò chơi.

Cảnh chơi dùng nền phòng sinh hoạt câu lạc bộ theo phong cách anime được tạo bằng **ChatGPT ImageGen built-in**: tường kem, rèm xanh ngọc, sàn gỗ, cửa sổ nắng ấm, đàn piano và cây xanh. Asset gốc được sao chép nguyên vẹn vào `web_tool/mao-5070/draco/assets/mao-anime-game-room-v3.png`; prompt và nguồn lưu trong `doc/mao_anime_game_room_v3.prompt.txt`. Chỉ đổi cảnh chơi; phòng disco mặc định giữ nguyên. Mao tiếp tục là nhân vật 3D sống, không bị vẽ cố định vào nền.

Phần hiển thị trên TV dùng phong cách riêng của Mao: xanh ngọc lục bảo, bạc và giấy kem theo bộ đồng phục, chữ serif, các ô chữ như lá bài, gợi ý như tờ giấy và lời dẫn “Mao bày trò”. Sticker Mao tóc vàng, mắt xanh, cà vạt xanh bạc được tạo bằng ChatGPT ImageGen từ tham chiếu ngoại hình renderer; lưu tại `web_tool/mao-5070/draco/assets/mao-ui-sticker-v3.png`. Prompt nguyên văn: `doc/mao_ui_sticker_v3.prompt.txt`. Sticker chỉ trang trí UI; model 3D và persona không thay đổi.

Giao diện chờ, chơi và kết quả cùng một hệ màu. Ảnh sticker nạp với CORS và kích hoạt vẽ lại khi tải xong, để canvas có thể dùng làm texture WebGL trong Electron.

Nội dung chơi là một bảng phẳng 3,40 × 1,91 m trên nền anime, bên cạnh Mao cao 1,80 m. Đã bỏ toàn bộ viền TV, kính/vỏ máy, chân đỡ, đế và vòng bục dưới chân Mao. Góc máy vẫn thấy đủ người và nội dung chơi; nền tự phủ kín khung nhìn khi đổi kích thước cửa sổ.

Bối cảnh gửi cho AI cũng nhận diện trường quay mới từ trạng thái renderer, để lời dẫn không tiếp tục dùng đồ đạc của phòng cũ.

## Màn hình TV

- **Không có vòng chơi:** Mao sinh hoạt trong phòng disco, không hiện cảnh TV.
- **Chuẩn bị:** báo Mao đang kết thúc lượt nói, chưa trừ thời gian chơi.
- **Chơi:** ô trống, chữ cái xáo trộn, chủ đề, số người đoán, đồng hồ vòng tròn 60 giây và Gợi ý 1/2/3. Mười giây cuối đồng hồ chuyển màu san hô.
- **Kết quả:** đáp án, người đoán tốt nhất, bảng top 5 với điểm và thời gian. Sau 15 giây trở về phòng disco.

TV dùng trạng thái trò chơi thật của backend; không cần nhập lệnh đổi cảnh. Phụ đề lớn tạm ẩn trong lúc chơi/hiện kết quả để không che nội dung TV; Mao vẫn đọc bằng giọng Linh Lan.

## Điều khiển

- Đã bỏ nút **Điều khiển** ở góc phải. Thanh chat và cài đặt gốc vẫn mở/thu gọn bằng mũi tên bên trái, mặc định thu gọn để ưu tiên nhân vật.
- Góc máy cố định, tự căn theo kích thước cửa sổ. Phòng disco dùng ống kính dài gần chính diện, ngang tầm nhân vật; Mao chiếm khoảng hai phần ba chiều cao khung hình, vẫn thấy bàn chân. Khung hình tập trung vào Mao và hậu cảnh, tránh các mép cắt/trống bên ngoài phòng. Cảnh chơi giữ góc máy đủ nhân vật và nội dung trò chơi. Không còn nút đổi góc nhìn, xoay camera hoặc thu phóng trong window mode.
- La bàn không hiển thị. Hướng Bắc/Nam/Đông/Tây, tọa độ, góc quay và hướng nhìn của Mao vẫn được tính nội bộ và gửi cho AI; lệnh di chuyển vẫn hoạt động.
- Chat nhập chữ, mic, ngắt lời, lịch sử, chọn nhân vật và chế độ pet vẫn dùng hệ thống desktop hiện có.
- Trong pet mode, trò chơi dùng TV phẳng nổi trên desktop và ẩn sau khi hết thời gian hiển thị kết quả.
- Pet mode vẫn giữ thao tác đổi kích thước nhân vật bằng con lăn theo cài đặt hiện có.

Xem trước ba trạng thái TV tại `http://127.0.0.1:12393/web-tool/mao-5070/word-game-preview.html`. Đây là dữ liệu minh họa, không tạo vòng chơi thật.

Xem trước cảnh anime với Mao 3D tại `http://127.0.0.1:12393/web-tool/mao-5070/word-game-scene-preview.html`; có nút xem đang chơi, kết quả và trở về disco. Không tạo vòng chơi hoặc phát lời thoại thật.

## Mã giao diện

- `tv-screen.mjs`: đồ họa Canvas 1920×1080 dùng chung cho TV 3D và pet/preview; nickname, bình luận được vẽ như văn bản.
- `word-game-overlay.mjs`: lấy trạng thái, đồng hồ, nội dung trợ năng và cung cấp canvas cho TV.
- `tv-studio.mjs`: màn hình TV thật trong cảnh 3D, viền sáng, nền sân khấu và bục nhân vật.
- `game-scene.mjs`: chọn disco hay TV theo giai đoạn vòng chơi và thời hạn hiển thị kết quả.
- `room-view.mjs`: góc máy trường quay ưu tiên TV, lưu kết quả phép chiếu khi kích thước không đổi.
- `scripts/build_draco_shell.mjs`: tích hợp tên mới, nút điều khiển và bố cục desktop.

Hai cảnh được nạp trước; mỗi thời điểm chỉ vẽ một cảnh. Chỉ tải lại texture khi nội dung hoặc số giây hiển thị thay đổi; không tạo lại ảnh TV ở mỗi khung hình 3D. Cảnh TV ẩn không cập nhật texture. Texture được giải phóng khi đóng renderer.

Kiểm tra chính:

```powershell
node --test tests/test_tv_studio.mjs tests/test_word_game_overlay.mjs tests/test_draco_original_shell.mjs tests/test_draco_room_view.mjs
```

Kiểm tra trực tiếp chuyển cảnh được lưu ở `logs/mao-scene-cycle-check.json`: chơi ở TV → hiển thị kết quả ở TV → tự trở về disco.
