# Mao chơi Wesnoth: bản thử đầu tiên

Game Windows standalone được tải từ [trang chính thức trên itch.io](https://wesnoth.itch.io/battle-for-wesnoth), bản stable 1.18.8. Gói tải là ZIP portable; giải nén vào `%USERPROFILE%/Games/Wesnoth-1.18.8`, không cần Steam. Game nằm ngoài thư mục mã nguồn Mao.

## Đã làm

- Add-on `game_integrations/wesnoth/Mao_Wesnoth`: một màn tập cục bộ, Mao điều khiển phe 1, AI có sẵn điều khiển phe 2. Tắt sương mù trong màn tập này.
- Bốn thao tác: di chuyển, tấn công kẻ địch liền kề, tuyển Spearman/Bowman và kết thúc lượt.
- Game tạo danh sách tối đa 64 lựa chọn hợp lệ; Mao chọn ID. Đây là tập lựa chọn có giới hạn, chưa bao phủ mọi cách đánh hoặc toàn bộ chiến dịch.
- Công cụ `mao_hybrid`, operation `wesnoth`: `observe` để làm mới quan sát và `choose` để chọn lệnh. Trong lượt game có chữ ký host, model hiện có của Mao trả đúng một `action_id` từ danh sách hợp lệ; bộ nối kiểm tra phiên/lượt rồi thực thi. Không phát phần chọn lệnh thành lời nói. Chỉ sau phản hồi game, pipeline giọng nói mới đọc kết quả ngắn dựa trên trạng thái thực tế, bao gồm sát thương bằng 0 khi đánh trượt.
- Runner gửi đề nghị hoạt động có chữ ký host, xếp vào hàng đợi activity thay vì mở một luồng phát giọng riêng. Nội dung màn tập không được nhận thành lời người xem để ghi ký ức.
- Phản hồi game chứa kết quả, vàng và trạng thái đơn vị sau thao tác. `submitted` không có nghĩa đã hoàn thành; chỉ `confirmed=true` xác nhận game thực thi.

Không dùng Neuro SDK ở bản này; đây là bộ nối trực tiếp với Lua AI của Wesnoth. Không cần cài thêm model hoặc package Python.

## Cập nhật ngày 03/11/2026: kết quả trận và bài học

Runner đã nhận `game_end` từ Lua, chuyển trạng thái sang `finished` và gửi đề nghị có chữ ký để Mao thông báo thắng, thua hoặc hết lượt qua hàng đợi giọng nói hiện có. Trạng thái cuối được giữ sau khi game đóng; lệnh mới bị từ chối. Không dùng việc game đóng hoặc hết timeout để suy ra kết quả trận.

Chỉ trận chạy ở chế độ `mao` có kết quả xác nhận mới được lưu vào `private/wesnoth/reviews.json`, tối đa 20 trận. Chế độ manual/smoke và phiên bị đóng giữa chừng không tạo bài học. Dữ liệu gồm session, kết quả và số quan sát; không lưu hội thoại hoặc thay đổi persona. Xóa file này để bỏ lịch sử học game.

Hai quan sát hiện có: kết thúc lượt khi vẫn có lựa chọn tấn công/tuyển quân; chọn tấn công bằng đội trưởng với xác suất chết dự báo từ 25%. Chỉ đếm hành động được game xác nhận, khớp session/request/action và không đếm lại ACK trùng. ACK cuối đến sau tín hiệu kết thúc trận vẫn cập nhật báo cáo. Đây không phải kết luận nguyên nhân thắng/thua: một lựa chọn hợp lệ có thể không có lợi.

Ở trận kế tiếp, các quan sát được chuyển thành lời nhắc cố định để model cân nhắc. Chính sách chọn nước đi cũng yêu cầu so dự báo giao tranh và các lựa chọn còn lại trước khi kết thúc lượt. Chưa huấn luyện trọng số hoặc chứng minh tăng tỷ lệ thắng; `quality_improvement_verified` vẫn là false. Cần đánh giá nhiều trận thật để kết luận tiến bộ.

Kiểm thử sau cập nhật: 521 bài Python, 459 đạt và 62 bỏ qua theo điều kiện môi trường; không failure/error. Có 8 bài mới cho review, trạng thái cuối, bài học ở quyết định tiếp theo và runner nhận ACK sau `game_end`; lint đạt. Runner được thử bằng luồng game giả lập, chưa chạy lại trận Mao thật để đo chất lượng chiến thuật hoặc nghe thông báo kết thúc trận.

## Chạy bản Mao điều khiển

Trong PowerShell tại thư mục dự án:

```powershell
# Đã chạy setup trên máy hiện tại. Chỉ cần chạy lại khi cập nhật add-on.
.\.venv\Scripts\python.exe scripts/mao_wesnoth.py setup --enable-mao

# Mở Mao Desktop bằng cách đang dùng, rồi chạy:
.\scripts\start_mao_wesnoth.ps1
```

`setup --enable-mao` bật `hybrid.wesnoth_enabled` trong cấu hình đang dùng và sao lưu bản trước khi sửa vào `private/wesnoth`. Runtime cần được mở lại để đọc cấu hình. Mặc định tính năng này tắt trong schema và luôn tắt ở profile test.

Runner mở trực tiếp màn `Mao: Training Ground`. Đến lượt phe 1, game gửi trạng thái và đợi tối đa khoảng 90 giây. Nếu chưa nhận được lựa chọn, game kết thúc lượt, không tự chuyển sang AI mặc định chơi thay Mao. Giới hạn 24 quyết định/phe/lượt và 12 lượt/màn.

Runner cần Mao backend ở `127.0.0.1:12393` và desktop làm trình phát âm thanh. Không tự khởi động Mao, Ollama hoặc bộ đọc livestream. Đóng cửa sổ game hoặc Ctrl+C để dừng runner. Một khóa hệ điều hành chặn hai runner đồng thời.

## Chạy thử bộ nối mà không mở Mao

```powershell
.\.venv\Scripts\python.exe scripts/mao_wesnoth.py run --mode smoke --headless
```

Bài này chọn lệnh cố định, xác nhận tấn công, tuyển quân, di chuyển, kết thúc lượt và đi sang lượt 2. **Đây không phải bài kiểm tra Mao suy nghĩ hoặc TTS.** Kết quả nằm ở `private/wesnoth/smoke-report.json`, log ở `logs/mao-wesnoth.log`.

Để tự kiểm tra từng lệnh bằng cửa sổ game:

```powershell
.\scripts\start_mao_wesnoth.ps1 -Mode manual
# Trong PowerShell thứ hai:
.\.venv\Scripts\python.exe scripts/mao_wesnoth.py status
.\.venv\Scripts\python.exe scripts/mao_wesnoth.py choose --action-id a0
```

`a0` là kết thúc lượt. Các ID còn lại chỉ có nghĩa trong đúng snapshot vừa quan sát.

## Phạm vi và kiểm tra

Lua game vẫn nằm trong sandbox Wesnoth. Không bật `--unsafe-scripts`; không nhận Lua, WML, shell, URL hay đường dẫn tùy ý từ model. Game đọc file lệnh gồm đúng session/request/action ID, kiểm tra lại tính hợp lệ rồi mới chạy. Dữ liệu liên lạc, các claim chống trùng và userdata riêng nằm trong `private/wesnoth`.

Đã chạy game thật ở chế độ headless và nhận xác nhận thành công cho bốn thao tác qua hai lượt. Kiểm thử Python: 513 bài, 62 bài bỏ qua theo điều kiện môi trường. Phiên Mao thực ngày 01/11/2026 đã kiểm tra 12 lệnh, 12 lệnh được game xác nhận, qua 4 lượt; có đủ tấn công, tuyển quân, di chuyển và kết thúc lượt. Không thấy timeout hoặc nước di chuyển không thay đổi vị trí trong mẫu kiểm tra sau sửa; desktop không báo lỗi âm thanh, pet đứng yên. Đã đối chiếu lời thoại lưu trong delivery với kết quả game. Báo cáo mẫu ở `private/wesnoth/live-review.json`.

Phiên thử trước đã phát hiện lệnh thiếu trường `action`, request ID game bị nhầm thành yêu cầu duyệt, lỗi chia sẻ file trên Windows và ô có quân đồng minh vẫn được đưa vào danh sách di chuyển. Đã sửa các đường này, thêm lựa chọn rút lui và kiểm tra vị trí thực tế sau di chuyển. Mao hiện dùng lời mô tả kết quả ngắn theo mẫu; chưa có bình luận chiến thuật tự do. Đã kiểm tra cửa sổ game: trận này thua ở lượt 4. Mao còn kết thúc lượt khi có quân chưa tận dụng hết và bảo vệ đội trưởng chưa tốt. Bộ nối chưa gửi sự kiện thắng/thua riêng về Mao; cửa sổ game hiện chờ ở hộp thoại Defeat. Chưa đánh giá toàn bộ chiến dịch hoặc độ mượt trong phiên livestream dài.

Tài liệu API đã đối chiếu với bản Lua đi kèm game: [Lua AI](https://wiki.wesnoth.org/LuaAPI/ai), [filesystem](https://wiki.wesnoth.org/LuaAPI/filesystem), [logging](https://wiki.wesnoth.org/LuaAPI/wesnoth#Logging). Mã add-on dùng GPL-2.0-or-later như ghi trong header.
