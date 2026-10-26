# Mao tự vận hành khi rảnh

Ứng dụng có dịch vụ tìm hiểu riêng chạy cùng vòng đời backend. Đã bật ở `conf.yaml` và `characters/mao_live.yaml`; mẫu cấu hình chung vẫn mặc định tắt. Không cần nhắc từng lượt hoặc mở tab xem trước. Cần máy đang bật, backend Mao, PostgreSQL và Internet; Qwen/Ollama giúp chọn chủ đề, diễn giải.

## Vòng hoạt động

1. Chờ 120 giây không có đầu vào tương tác; kiểm tra không có hội thoại, tin nhắn chờ, hát hoặc game tương tác đang hoạt động. Không suy ra số người xem từ sự im lặng.
2. Xin lease và ngân sách từ PostgreSQL. Chỉ một phiên được chạy; restart không xóa ngân sách/lịch sử.
3. Qwen chọn chủ đề theo tính cách Mao: nhí nhảnh, hơi kiêu, đáng yêu và thích bày trò nhỏ. Ưu tiên mèo, bánh ngọt, trà sữa, game thư giãn/âm nhạc, phụ kiện và đồ thủ công; danh sách còn mở rộng từ bài đã đọc. Chủ đề đã học trong 24 giờ được bỏ qua; lỗi truy cập làm giảm ưu tiên. Kiến thức nghiêm túc vẫn dùng được khi người xem hỏi.
4. Đọc tóm tắt Wikipedia và tối đa 8 liên kết cho hàng đợi tò mò. Tối đa hai GET nối tiếp/lượt, host cố định, không gọi URL do model hoặc trang cung cấp.
5. Qwen chọn mã của trích đoạn nguồn đã cắt sẵn, rồi viết một ý nghĩ riêng của thiếp: phản ứng thích thú, ý tưởng nghịch ở dạng giả định, một điều nhỏ muốn thử hoặc điều tò mò gần gũi. Không bắt buộc đặt câu hỏi và không biến mọi lượt thành nghiên cứu. Không cho model thay nội dung bằng chứng; lỗi/mã không hợp lệ thì chỉ giữ trích đoạn thật. Chặn một số lỗi thường gặp như tự nhận sở hữu thú cưng hoặc vừa ăn/mua thứ gì; đây không phải bộ kiểm chứng mọi đầu ra model.
6. Lưu kiến thức có nguồn, revision/hash vào ký ức dài hạn PostgreSQL/pgvector. Các chủ đề khởi đầu có nhãn tiếng Việt được định nghĩa sẵn để truy hồi cả khi nguồn tiếng Anh; không tự đặt bí danh người xem. Lịch sử và nhận xét chưa kiểm chứng nằm trong state. Hội thoại Mao nhận được kết quả gần nhất và có thể truy hồi kiến thức này.
7. Nghỉ tới lượt sau, nhường ưu tiên khi nhận đầu vào mới. Không tự nói đè lên hội thoại.

Giới hạn mặc định: 60 giây/lượt, ít nhất 300 giây giữa các lần bắt đầu, 24 lần thử/ngày theo Asia/Ho_Chi_Minh. Lượt lỗi/ngắt cũng tiêu ngân sách. Đồng hồ DB, khóa/lease/token chống chạy trùng và worker cũ ghi đè; lease quá hạn không được đánh dấu hoàn thành. Không tự chạy lại lượt còn dở sau crash.

## Khởi động và điều khiển

Từ thư mục dự án, sau khi đã thiết lập PostgreSQL và model theo hướng dẫn hybrid:

```powershell
docker compose -f compose.mao-hybrid.yaml --env-file private/mao-hybrid.env up -d
powershell -File private/start-local.ps1
powershell -File scripts/start_mao_playroom.ps1
```

Mở `http://127.0.0.1:12395/mao-5070/playroom.html?obs=1&game=2048`. Góc trên phải có **Sổ tò mò của thiếp** và nút **Tạm dừng / Tiếp tục tự tìm hiểu**. Ý nghĩ của Mao hiện trước; trích đoạn/nguồn thật mở riêng trong **Thiếp vừa đọc gì?**. Bảng điều khiển được ẩn khỏi các lớp OBS/chế độ clean. Đóng tab không dừng dịch vụ.

Không mở giao diện vẫn có thể dùng:

```powershell
.\.venv\Scripts\python.exe scripts/mao_autonomy.py status
.\.venv\Scripts\python.exe scripts/mao_autonomy.py pause
.\.venv\Scripts\python.exe scripts/mao_autonomy.py resume
```

`enable` bật cấu hình cho lần khởi động backend sau, giữ bản sao trước sửa trong `private/`. `once` chỉ là phép thử operator gọi, vẫn bị giới hạn ngân sách/lease; bình thường không cần gọi. Muốn tắt hẳn, đặt `hybrid.autonomy.enabled: false` và restart backend. Pause được giữ sau restart; file điều khiển hỏng được coi là pause.

Backend tắt thì dịch vụ dừng và đóng tài nguyên. Chưa cài Windows Startup/dịch vụ hệ thống; sau reboot cần khởi động Mao. Máy ngủ/mất mạng thì không học tiếp được. Không khởi động phát livestream.

## Phạm vi và giới hạn

- Tự vận hành **tìm hiểu nguồn công khai**, chưa phải tự thao tác toàn bộ Windows. Dịch vụ không có shell, file cá nhân, đăng nhập, cài phần mềm, mua hàng, gửi tin hoặc phát stream.
- Browser computer-use tổng quát/công cụ explore cũ vẫn có công tắc và allowlist riêng. Vòng này dùng API đọc có cấu trúc, không giả vờ đang bấm Chrome. Adapter 2048 vẫn chạy bằng lệnh riêng, chưa tự mở game trong vòng tò mò.
- Text, micro, live/game comment và ngắt lời hủy công việc đang làm. Kiểm tra lại trước khi lưu; thao tác ghi DB đã bắt đầu có thể hoàn tất, chỉ ghi trích đoạn đã đọc, không thực hiện hành động bên ngoài.
- “Rảnh” là không có tương tác trong ứng dụng, không có nghĩa máy AFK hoặc không người xem. Không thu camera hoặc theo dõi hoạt động cá nhân để suy ra điều đó.
- Nguồn/model là dữ liệu không tin cậy. Chỉ tiêu đề hợp lệ trong danh sách ứng viên được nhận; GET tới Wikipedia cố định, TLS, không redirect, tối đa 64 KiB/phản hồi và timeout. Nội dung trang không có công cụ để thực hiện chỉ thị.
- Ký ức ghi `unverified_claim`, evidence giữ nguồn/revision/hash, `verified_truth=false`. Xác minh đã đọc nguồn không chứng minh mọi dữ kiện đúng; nhận xét Qwen vẫn chưa kiểm chứng.
- Kiến thức tích lũy và chọn chủ đề thích nghi theo tính mới/lỗi truy cập; không huấn luyện lại Qwen, tự sửa code/persona hay bảo đảm tốt lên mỗi ngày.
- Voice/TTS/avatar/chat giữ pipeline cũ. Vòng nền không tự phát âm thanh; kết quả cấp cho hội thoại và nhật ký. Cửa sổ game cũ đóng thì cảnh game vẫn che dù dịch vụ tìm hiểu đang chạy.

## Dữ liệu và kiểm tra

Không thêm bảng. State key `autonomy` trong scope Mao giữ ngân sách ngày, lease, 40 lượt gần nhất, 60 chủ đề gợi ý, 100 mốc đã đọc. Event `autonomy_cycle` ghi completed/failed/interrupted. Ký ức dài hạn dùng TTL/cap/embedding profile hiện có; embedding lỗi thì vẫn lưu văn bản và báo chế độ từ khóa.

`private/mao-autonomy-status.json` là trạng thái có heartbeat; DB là nguồn lịch sử/ngân sách. `private/mao-autonomy-control.json` là công tắc operator, không đăng ký như tool model. API localhost:12395 yêu cầu token/Host/Origin cho pause/resume, không mở CORS và không mở rộng quyền.

Đã thử provenance, đầu ra không bám nguồn, URL ngoài danh sách, redirect/nguồn quá lớn, model offline, pause/file lỗi, đầu vào giữa lúc đọc, chờ idle, bỏ qua chủ đề đã học, budget/lease/cooldown/ngày mới bằng PostgreSQL thật, và API chống origin lạ. Đây không phải kiểm định độ đúng của kiến thức hay bảo đảm chất lượng LLM.

## Cơ sở thiết kế

- Wikimedia User-Agent và tốc độ: https://www.mediawiki.org/wiki/API:Etiquette/en ; https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- Hủy task và đóng tài nguyên: https://docs.python.org/3/library/asyncio-task.html
- Phản tỉnh cần phản hồi/bằng chứng: https://arxiv.org/abs/2303.11366 ; https://arxiv.org/abs/2310.01798

Áp dụng ở mức nhỏ: request nối tiếp, cooldown, lỗi thì nghỉ; task có thời hạn/đường hủy; trích đoạn bám nguồn và nhận xét luôn chưa kiểm chứng.
