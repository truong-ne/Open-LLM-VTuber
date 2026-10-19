# Mao Theatre — chuyển cảnh bằng rèm

Áp dụng trong chế độ cửa sổ: phòng disco ↔ Vua Tiếng Việt ↔ sân khấu hát. Cảnh thường không đổi. Chế độ pet giữ nền trong suốt, không dùng rèm toàn màn hình.

Phiên bản 2 dùng ảnh rèm nhung xanh ngọc được tạo mới bằng **ChatGPT imagegen**, hoa văn ánh bạc ở gấu rèm, đường thêu giữa hai cánh và monogram M nhẹ. Đã bỏ nếp sọc gradient và diềm tam giác bản đầu. Ảnh được lưu tại `web_tool/mao-5070/draco/assets/mao-theatre-curtain-v2.png`; prompt đầy đủ ở [`mao_curtain_v2.prompt.txt`](mao_curtain_v2.prompt.txt).

Hai tấm vải được vẽ bằng hai mesh Three.js, mỗi tấm 48×16 ô: kéo từ giữa về hai cánh, dồn nếp, mép trên dẫn và gấu theo sau, gợn nhẹ rồi dừng. Easing bậc 5 giữ cả vận tốc và gia tốc bằng không ở đầu/cuối. Chỉ render khi chuyển động; lúc rèm đóng đứng yên không vẽ lại liên tục. Pixel ratio giới hạn 1,5 để giảm tải; khi WebGL không khả dụng có lớp dự phòng dùng chính ảnh gen. Tài nguyên nằm trong dự án, không gọi dịch vụ gen hoặc website tham khảo lúc chạy.

## Nhịp chuyển

1. **900 ms** khép hai cánh rèm, vẫn giữ nguyên cảnh cũ phía sau.
2. Khi đã kín **mới đổi cảnh**. Hai cánh có phần chồng nhỏ ở giữa để không hở cảnh. Giữ tối thiểu **420 ms**, chờ ảnh rèm và cảnh mới sẵn sàng; hiện tên tiết mục cùng “Sân khấu sẵn sàng, Mao ra ngay…”.
3. **1.200 ms** mở rèm để giới thiệu cảnh mới. Tổng thông thường khoảng **2,52 giây**. Hát chỉ bắt đầu sau lúc mở xong.

## Âm thanh kéo rèm

Mỗi lần khép/mở phát đúng một âm kéo rèm riêng, có tiếng vải và ray thật; không dùng tiếng whoosh thay thế. Các đoạn Ogg nhẹ được tải trước, co thời gian khớp chuyển động và fade hai đầu. Âm lượng giảm còn 20% mức hiệu ứng khi Mao đang nói. Đây là lớp âm riêng, không xóa, ngắt hoặc đổi hàng đợi TTS/nhạc. Trình duyệt khóa autoplay thì bỏ âm chưa được phép thay vì phát dồn trễ; tương tác click/phím sẽ thử mở AudioContext cho các lần tiếp theo.

Nguồn là [“21. curtain open close.wav” — btherad2000](https://freesound.org/people/btherad2000/sounds/328031/), giấy phép CC BY 4.0. Đã cắt, lọc, chỉnh tempo và fade thành `assets/curtain-close-v2.ogg`, `assets/curtain-open-v2.ogg`. Ghi công đầy đủ và thay đổi nằm trong [`curtain-audio-credits.md`](../web_tool/mao-5070/draco/assets/curtain-audio-credits.md), giữ kèm khi phân phối.

Hiệu ứng âm mặc định bật; tùy chọn `localStorage['mao.curtain.sound']='off'` hoặc `transition.setSoundEnabled(false)` tắt riêng. Không thêm nút điều khiển lên cảnh của Mao. Chế độ giảm chuyển động dùng fade ngắn và bỏ tiếng kéo dài để không lệch pha.

Vua Tiếng Việt ở `waiting` trong lúc này. Desktop gọi `POST /api/vuatiengviet/presentation` với đúng `round_id` sau khi mở rèm. Backend chỉ bắt đầu bộ đếm 60 giây khi đã nhận xác nhận này, lượt nói hiện tại đã kết thúc và hàng đợi thoại rảnh. Khi dùng backend mà không có giao diện Mao mở, game chờ giao diện; không tự tính giờ ngoài màn hình.

`CurtainTimeline` giữ một đích đang chờ. Đổi đích liên tục trong lúc đóng/giữ rèm thì gộp sang đích mới; lúc mở thì đợi mở xong mới khép lại cho lần kế tiếp. Poll lại cùng một cảnh không phát lại hiệu ứng. Khi người dùng bật giảm chuyển động, dùng lớp mờ ngắn 120/180/180 ms thay cho rèm trượt.

## Tham khảo

- [OBS — Track Matte Stinger Transitions](https://obsproject.com/kb/track-matte-stinger-transitions): hiệu ứng phủ trên điểm cắt giữa hai cảnh. Lấy nguyên tắc đổi cảnh khi đã che kín; không tích hợp OBS hoặc dùng video stinger.
- [ShowTex — Types of track movement](https://www.showtex.com/en/knowledge-hub/types-track-movement): kiểu rèm traveler dồn nếp và hai cánh chồng ở giữa khi đóng.
- [Motion Array — Curtain Opener Pack](https://motionarray.com/stock-motion-graphics/curtain-opener-pack-197142/): tham khảo cách trình bày rèm nhung mở màn; không sử dụng tài nguyên stock của gói này.
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion): tôn trọng tùy chọn giảm chuyển động.
- [MDN — Web Audio best practices](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices): mở/resume AudioContext theo tương tác, tránh phát trễ khi bị khóa autoplay.

Hiệu ứng cụ thể là thiết kế riêng cho Mao, không sao chép một opening anime. Các nguồn được tham khảo ngày 19/10/2026.

Bản minh họa không cần backend: `web_tool/mao-5070/performance-scene-preview.html`. Kiểm tra ảnh bằng `scripts/check_mao_scenes.cjs` dùng Playwright và Chrome headless với hồ sơ tạm; không khởi động Mao/backend/model. Kiểm tra logic bằng `tests/test_scene_transition.mjs`, `tests/test_singing_player.mjs`, `tests/test_singing.py`.

Bản xem thử v2 có tiếng: `logs/mao-curtain-v2-demo.mp4`, xuất bằng `scripts/render_mao_curtain_demo.cjs`. Đây là video ghi giao diện fixture offline, ghép đúng hai mẫu âm theo thời điểm phát BufferSource ghi được trong trình duyệt; không phải buổi live thật. Ghi công âm thanh lưu kèm ở `logs/mao-curtain-v2-demo.json` và trong metadata MP4. Bộ kiểm tra v2 bổ sung `tests/test_curtain_sound.mjs`, kiểm tra hình dạng vải, easing, chỉ phát một lần/chiều, ducking khi đang nói và không phát âm trễ sau mở khóa autoplay.
