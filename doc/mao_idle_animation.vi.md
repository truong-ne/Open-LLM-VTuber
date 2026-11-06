# Idle sống động cho Mao (Draco)

## Vì sao trước đây trông đơ
Avatar thật là Draco 3D (`web_tool/mao-5070/draco/`), không phải Live2D. Idle nằm trong `BodyActor.step()` (`motion.mjs`) và chỉ có dao động ~0,2–0,5° (thở 0,16°, đầu 0,5°). Mắt chỉ liếc 0,024 rad, chớp theo chu kỳ gần cố định, không có nhìn quanh hay phản ứng khi nói/nghe.

## Nguyên tắc áp dụng (`idle-life.mjs`, toán thuần, không phụ thuộc three.js)
| Lớp | Cách làm |
|---|---|
| Thở | ~15 nhịp/phút, hít 40% / thở ra 60%, thỉnh thoảng thở dài sâu gấp ~1,9; nhanh hơn 18% khi nói. Ngực ngả sau nhẹ, vai nhấc. |
| Dồn trọng tâm | Mỗi 7–15 s trượt hông sang một bên trong 1,6–2,6 s (smoothstep), vai và xương chậu nghiêng ngược nhau (contrapposto), đầu giữ thăng bằng. |
| Nhìn quanh | Mắt nhảy trước (saccade), đầu theo sau ~150 ms bằng lò xo, mắt về giữa dần. Đầu nhận 68% góc, mắt phần còn lại. Có micro-saccade ±0,7°. |
| Đung đưa nhẹ | Tổng của nhiều "random walk" mượt, chu kỳ khác nhau (3,9–7,9 s), không lặp. |
| Sự kiện đầu | Mỗi 8–20 s: nghiêng đầu, gật hai nhịp hoặc lắc đầu nhẹ (≤ 4°). |
| Khi nói | Gật theo nhịp khi âm lượng bật lên (beat nod), ít liếc đi hơn, chớp nhiều hơn một chút. |
| Khi nghe | Gật chậm mỗi 3–6 s, nghiêng đầu giữ nhẹ về một bên. |
| Chớp mắt | Khoảng cách ngẫu nhiên 2,6–6,4 s, 16% chớp đôi, đôi khi chớp cùng cú liếc lớn. |
| Chuyển tiếp | Ba lớp (thân, nhìn, thở) hòa vào/ra bằng hàm mũ khi đổi cử chỉ, đi bộ hoặc nhảy; không giật. |

### Bổ sung vòng 2 (tự thoại, tay chân, biểu cảm)
Đánh giá: trước đó chỉ có 5 nét mặt cố định và 19 cử chỉ làm sẵn, đầu là bộ phận duy nhất sống động; chưa đủ cho tự thoại kéo dài. Tra cứu: nghiên cứu về VTuber ([AlterEcho, ISMAR 2021](https://www.cs.purdue.edu/cgvlab/www/resources/papers/Tang-ISMAR-2021-AlterEcho_loose_avatar_streamer_coupling_expressive_vtubing.pdf)) cho thấy cử chỉ nhấn (beat) làm avatar tự nhiên và cuốn hút hơn; chớp mắt tăng khi nói ([PLoS ONE 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8500445/)); cử động vùng mắt/lông mày xảy ra thường xuyên khi nói nhưng không khớp 1-1 với cao độ, nên dùng nhịp nhấn kèm dao động chậm thay vì ánh xạ cứng.

| Lớp mới | Cách làm |
|---|---|
| Tâm trạng khuôn mặt | `MOODS`: calm, happy, sad, worried, annoyed, curious, sleepy, smug. Mỗi tâm trạng đặt cười/lông mày/mí mắt và nghiêng đầu nhẹ, chuyển mượt ~1 s. Cử chỉ cảm xúc (buồn, cười, nghĩ, ngạc nhiên, nhún vai) tự chọn tâm trạng; có thể gọi `actor.idle.setMood(tên, độ mạnh)`. |
| Mặt tự nhiên | Nụ cười nền rất nhẹ, lông mày trôi chậm, lông mày nhướng khi nhấn, mí mắt sụp khi nhìn xuống, mắt híp nhẹ khi cười (Duchenne), nhìn lên-sang một bên rồi nhướng mày khi bắt đầu nói. |
| Chớp mắt theo lời nói | Chớp sau mỗi ngắt cụm, chớp đôi cách 0,6–0,8 s, chớp theo cú liếc lớn. |
| Tay | Mỗi tay trôi riêng, đối trọng với hông, nhấc theo hơi thở, thỉnh thoảng "đặt lại tay" (dạng vai nhẹ + gập khuỷu); khi nói mỗi cú nhấn có thể nhấc một tay (hiếm khi cả hai). Cổ tay lỏng, ngón tay thả lỏng thay đổi chậm. |
| Chân | Xoay bàn chân quanh mắt cá (mắt cá vẫn cố định), bàn chân chịu ít tải xoay nhiều hơn và thỉnh thoảng chạm mũi chân. Gối gập theo dịch hông (IK có sẵn). |
| Thân | Biên độ nghiêng/xoay chậm của thân ×1,5, vai trôi riêng, xoay xương chậu và ngực ngược nhau. |

Mọi cơ chế cũ (nói, nhảy, hát, biểu cảm, motor) giữ nguyên: idle chỉ cộng thêm vào pose, và giảm về 0 khi đi bộ, nhảy hay đang làm cử chỉ lớn.

## Chỉnh được
- `actor.setIdleIntensity(0..2)`: cường độ chung (0 = đứng im như cũ). Trang xem trước có thanh trượt.
- `actor.setListening(true/false)`: bật kiểu "đang nghe". **Chưa nối vào native-avatar**, vì chưa có tín hiệu "đang nghe" từ bridge. Cần gọi từ nơi biết người dùng đang nói.
- `IDLE_TUNING` trong `idle-life.mjs`: nhịp thở, độ rộng liếc, tần suất dồn trọng tâm/chớp mắt, biên độ gật, nghiêng…; có thể truyền `tuning` khi tạo `IdleLife`.
- Hạt giống ngẫu nhiên cố định (`seed`) để test lặp lại được; chuỗi chuyển động vẫn không tuần hoàn.

## Tệp thay đổi
`idle-life.mjs` (mới), `motion.mjs` (cộng lớp idle, `setIdleIntensity`, `setListening`), `performance-face.mjs` (mắt và chớp dùng chung idle của thân), `app.mjs` + `index.html` (bảng "Idle sống động", `?idle`), `native-avatar.mjs` (nối `face.idleSource`), cùng tăng `?v=` các import để tránh cache cũ. Test mới: `tests/test_draco_idle_life.mjs`.

## Xem trước
Chạy file server tĩnh trong thư mục `web_tool/mao-5070` rồi mở `/draco/index.html?idle`. Không cần backend/LLM/TTS.

## Lỗi đã sửa (vòng 3)
- **Mặt biến mất / vòng tròn trước miệng**: trọng số lớp mặt (`idleMix.face`) chưa được khởi tạo, nên cười/lông mày/mí mắt thành NaN. Lưới mặt và môi bị hỏng và biến mất, chỉ còn vành môi phủ và khoang miệng (hiện ra khi chọn nét mặt mở miệng). Đã khởi tạo trọng số, chặn mọi giá trị không hữu hạn ở `IdleLife.update` và `PerformanceFaceRig.update`, thêm test hồi quy. Ảnh kiểm tra: `mao_idle_preview/expressions_after_fix.jpg` (5 nét mặt × tâm trạng dỗi/vui).
- **Tâm trạng bị ghi đè**: `setMood` từ bên ngoài bị cử chỉ đặt lại về "bình thường" mỗi khung hình. Nay cử chỉ cảm xúc dùng `gestureMood` tạm thời, xong thì trả về tâm trạng nền.
- Tăng `?v=` các import (kể cả `idle-life.mjs?v=3`) để trình duyệt/desktop không dùng bản lỗi trong cache.

## Vòng 4: Mao tự chọn cử chỉ theo lời nói
`selectPerformance` (`performance-context.mjs`) đọc **câu Mao đang nói** (không phải bình luận của khán giả) và trả về `{action, face, mood, look}`; desktop (`native-avatar.mjs`) và bản xem trước áp dụng cả bốn cho mỗi câu, hết lượt nói thì tâm trạng về "bình thường".

| Mao nói | Mao làm |
|---|---|
| "Mao chỉ biết lắc hông thôi, xem nè!", "Nhảy hả? Mao nhảy thử cho xem nhé!" | lắc hông, mặt cười, tâm trạng vui |
| "Hông chịu đâu…", "Còn lâu Mao mới làm!", "Không đâu nha…" | động tác "không chịu đâu", mắt --, tâm trạng dỗi |
| "Á! Sau lưng Mao có gì hả?" | giật mình + ngoái ra sau (thân xoay theo, chân giữ chỗ) |
| "Bên trái hả?", "bên phải có ai vậy?" | nhìn sang trái / phải (bên của chính Mao) rồi quay lại |
| "Tiếng gì vậy ta?" | nhìn quanh hai bên |
| "Đúng rồi…", "Ừ…" | gật đầu |
| "Hehe, Mao giỏi chưa!" / "Buồn ngủ quá…" | tâm trạng tự hào / buồn ngủ |
| "Tạm biệt mọi người nha!" | vẫy tay |

Câu phản hồi kiểu "đừng lắc hông nữa", "lắc hông mạnh quá" không kích hoạt lắc hông. Từ dễ nhầm khi bỏ dấu ("mà"/"ma", "đã"/"dạ", "thời gian") không kích hoạt gì. Nhãn `[hipSway]`, `[refuse]`… và `motions` từ agent vẫn ưu tiên như cũ.

API mới: `actor.lookToward('left'|'right'|'behind'|'around')`, `actor.setMood(tên, độ mạnh)`. Bản xem trước có nút "Nhìn trái / Nhìn phải / Ngoái ra sau / Nhìn quanh", và ô "Diễn theo câu chuyện" hiển thị cử chỉ, tâm trạng, hướng nhìn đã chọn cho từng câu.

Giới hạn: chọn theo từ khóa trong câu Mao nói, chưa dùng LLM để chọn. Nếu Mao không nhắc tới bên trái/sau lưng trong câu trả lời thì sẽ không nhìn.

## Sửa lỗi khác
- **Vòng tròn cạnh miệng khi đầu xoay** (mắt ><, --, ngơ ngác): vành môi phủ (`mao_lip_rim`) được dựng trên mặt phẳng z=0,089, nổi trước môi thật 3–8 mm, nên khi đầu xoay nó lệch thành vòng tròn bên cạnh miệng. Nay mỗi đỉnh của vành (cả khi miệng mở) được đặt sát bề mặt môi/da (`seatLipRim`), có test hồi quy.
- **Lớp ren dưới váy**: hai lớp `V17_Lace_*` nhô ra ngoài váy ~0,7‰ đơn vị cơ thể ở vùng eo (bị áo len che). Nay được kéo vào trong váy 4‰ (`SkirtClearance.tuckUnderlayers`, chỉ vùng eo, không đụng diềm ren ở gấu váy). Đo hình học dưới mép áo len không thấy lớp nào xuyên váy; vết lốm đốm người dùng chụp chưa tái hiện được trên bản xem tĩnh.

## Vòng 5: váy phía trước bị nhô
Nguyên nhân (có từ trước, không do idle): `SkirtClearance` coi mỗi đùi là một ống tròn với **một** bán kính lấy từ điểm da xa nhất — rơi vào vùng hông/mông phía trên khớp háng (t≈0), 0,114 + lề 0,012 = 0,126 đơn vị, trong khi đùi thật dọc theo trục chỉ ~0,104 và mặt trước còn mỏng hơn. Ống quá to đẩy các mảng váy phía trước (lệch ~30° khỏi giữa) ra ngoài tới 0,018 đơn vị, thành dáng phồng như cái trống.

Sửa: chỉ lấy da phía dưới khớp háng, và đo bán kính riêng cho 16 hướng quanh đùi; khi đẩy váy dùng bán kính của phía mà tia đi ra. Khi đứng (kể cả idle) váy gần như không bị đẩy (≤0,004 thay vì ~0,034); các test che đùi khi bước trái/phải, đi, xoay, lắc hông vẫn đạt. Ảnh so sánh: `mao_idle_preview/skirt_before_after.jpg` (hàng trên: cũ, hàng dưới: mới; đã ẩn áo choàng và tóc để thấy rõ). Có test hồi quy trong `test_draco_idle_life.mjs`.

## Chưa kiểm chứng
- Chưa chạy trên ứng dụng desktop thật (máy dev không đủ VRAM); chỉ chạy test node và bản xem tĩnh.
- Cảm giác "tự nhiên" cần người xem đánh giá; biên độ mặc định chọn theo các nguyên tắc trên, có thể cần chỉnh.
- Kiểu "đang nghe" chưa được nối tín hiệu thật.
- `test_mao_desktop_runtime.mjs` vẫn fail sẵn (thiếu `private/tools/vtuber-desktop-unpacked`).
