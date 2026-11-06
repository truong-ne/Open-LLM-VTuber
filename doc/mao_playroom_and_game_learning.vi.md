# Mao Playroom — chia sẻ cửa sổ

Bộ chơi 2048 đã được gỡ theo yêu cầu. Playroom chỉ còn chia sẻ một cửa sổ do người vận hành chọn, ghép avatar/phụ đề và xem trước qua OBS; nó không tự điều khiển game.

Có thể chọn nguồn trong playroom bằng cơ chế chia sẻ cửa sổ của trình duyệt. Với OBS portable đã được thiết lập riêng, chạy `scripts/start_mao_playroom.ps1`, sau đó `scripts/start_mao_playroom_obs.ps1 -WindowTitle "TIÊU ĐỀ CHÍNH XÁC TRONG BỘ CHỌN OBS"`. Script chỉ nhận đúng một cửa sổ khớp tiêu đề; không tự chọn Chrome hay tự mở game. Không bắt đầu stream hoặc recording.

Mở bản xem tại `http://127.0.0.1:12395/mao-5070/playroom.html?obs=1`. Các nút che/hiện nguồn và kết nối phụ đề Mao vẫn dùng được. Tài liệu tự tìm hiểu, giao diện persona, ký ức và runtime giữ nguyên đường dẫn hiện có.

Đã xóa driver, luật bàn cờ, bộ chọn chiến thuật, script đánh giá kết quả, kiểm thử riêng và cơ chế đọc trạng thái game từ giao diện. Các giới hạn capture và xác thực API cục bộ vẫn được giữ.
