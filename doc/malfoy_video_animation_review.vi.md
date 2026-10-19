# Đối chiếu video Malfoy với rig Mao

Video được người dùng cung cấp: `C:/Users/LeDinhTruong/Downloads/malfoy.mp4`, dài 14,74 giây, 360 × 640, 30 fps. Phân tích từ khung hình cách nhau 0,5 giây và các khung cận mặt; thời gian bên dưới là khoảng quan sát, không phải dữ liệu motion capture. Báo cáo này chưa thay animation hoặc nhân vật đang chạy.

## Những gì thấy trong video

| Khoảng thời gian | Quan sát |
| --- | --- |
| 0–1,5 giây | Góc cận từ trên xuống; thân hơi nghiêng, khuỷu tay đưa về sau, đầu/vai đổi góc nhỏ; mắt xanh đang mở. |
| 2–3,5 giây | Toàn thân: chuyển trọng tâm qua hai chân, hông đưa ngang/đổi góc; thân trên và đầu bù chuyển động. Tóc và tà áo theo sau. |
| 4–5 giây | Hai mắt thành nét `><`, miệng mở/cười, phối với thân nhún và nghiêng đầu. Đây là biểu cảm cách điệu rõ ràng. |
| 6–7,5 giây | Góc trung: hông, vai và đầu tiếp tục diễn; tư thế tay/khuỷu góp phần tạo dáng. |
| 8–9 giây | Mắt thành hai nét `--`, miệng nhỏ dạng tam giác; tạo cảm giác hờn/bất lực hoặc hát tùy ngữ cảnh. Không suy ra cảm xúc chắc chắn chỉ từ một khung. |
| 10–11 giây | Quay lại toàn thân và đổi trọng tâm. |
| 11,5–13 giây | Biểu cảm mắt `><` lặp lại, phối với miệng và thân. |
| 14–14,7 giây | Trở lại mắt mở và góc trung. |

Độ sinh động còn đến từ cắt cảnh, đổi cỡ cảnh và góc máy. Những cú chuyển cận/toàn cảnh cần phân biệt với chuyển động thật của hông, đầu và vai. Khung hình không đủ để suy ra chính xác góc khớp, độ sâu hoặc thông số vật lý của animation gốc. Biểu cảm “ngơ ngác” và động tác “không chịu đâu” là các yêu cầu có thể thiết kế từ phong cách này; không gán chúng thành tên clip gốc chưa có dữ liệu xác nhận. Phần miệng nhỏ trong video không đủ để đo chính xác độ thò/cong của lưỡi.

Khung đối chiếu từ video: mắt mở, mắt `><`, mắt `--`.

![Khung biểu cảm Malfoy ở 0–1, 4–5 và 8–9 giây](C:/Users/LeDinhTruong/Desktop/workspace/Open-LLM-VTuber/doc/references/malfoy-expression-reference.jpg)

## Kiểm tra trực tiếp model và mã đang dùng

- `character.glb` không có animation clip hay morph target gốc. Các chuyển động hiện tại được bổ sung ở runtime.
- `BodyActor` có 17 action, điều khiển hông/thân/vai/đầu/tay/ngón tay, có IK giữ chân và mô phỏng tóc/quần áo. Có `shift`, `turn`, `shy`, `surprise`, `laugh` làm nền, nhưng chưa có clip lắc hông hoặc từ chối riêng như yêu cầu.
- `FaceRig` hiện dựng khẩu hình theo âm lượng và khoang miệng/răng/lưỡi. `update(volume, playing, dt)` chưa nhận trạng thái cảm xúc, chưa có chớp mắt, nhắm mí, nhướng mày hoặc mắt `><`/`--`.
- Model vẫn có hai khớp điều khiển tròng mắt: `draco_bone_0019` và `draco_bone_0021`. Kiểm tra skin weights cho thấy mỗi khớp điều khiển một nửa mesh iris (100 đỉnh mỗi bên). Tên khớp chung chung không có nghĩa là mất rig mắt. Có thể dùng chúng cho hướng nhìn.
- Mặt và mi trên chủ yếu gắn vào khớp đầu; lưỡi gốc `material_15` cũng gắn vào đầu. Mesh `mao_tongue` hiện thêm ở runtime mới theo độ mở miệng, chưa có thao tác đưa lưỡi ra.
- Ở desktop, nội dung câu nói chọn action cho thân; mặt hiện chỉ nhận âm lượng/đang phát. Thêm action cho thân đơn thuần sẽ chưa tạo biểu cảm mắt tương ứng.

## Khả năng thực hiện

| Yêu cầu | Khả thi trên model hiện có | Phần cần bổ sung |
| --- | --- | --- |
| Lắc hông | Có; đủ khớp và IK | Chuyển trọng tâm hai bên, xoay/nghiêng hông, vai đối pha, đầu bù nhẹ; nhịp vào/ra và tóc/váy trễ nhịp. |
| “Không chịu đâu” | Có | Clip kết hợp lắc đầu, nhún vai, tư thế tay và thân nghiêng/lùi nhẹ; ghép mặt hờn hoặc `><`. |
| Ngơ ngác | Có | Mí mở hơn, mày nâng, tròng mắt đổi hướng, miệng nhỏ “ơ”, đầu nghiêng và khoảng dừng. |
| Lè lưỡi | Có; cần tạo pose mới | Morph/mesh lưỡi có phần đưa ra và đầu lưỡi bo cong; phối hàm/môi, kiểm tra không xuyên mặt/răng. |
| Mắt `><` | Có | Đóng mí, tạm ẩn tròng mắt/ánh mắt, hiện nét mắt anime bám theo mặt; giữ đúng che khuất khi quay đầu. |
| Mắt `--` | Có | Nhắm mí thư giãn, nét mắt ngang, phối mày/miệng theo trạng thái hờn hoặc bất lực. |

Không cần mua model khác để bắt đầu. Nếu có bản PMX/Blend gốc còn morph mặt, có thể khảo sát lại để tái sử dụng; bản GLB hiện tại không chứa sẵn các biểu cảm đó. Một video 2D không khôi phục nguyên vẹn keyframe/morph gốc, nên độ giống cần đối chiếu qua nhiều góc và chuyển động thực tế.

## Cách xây để tự nhiên và dùng được khi trò chuyện

1. **Mặt trước:** thêm các kênh blink, mí mắt, mày, gaze, cười, bĩu, ngạc nhiên, tongue-out; giữ khẩu hình giọng nói thành kênh riêng. Mắt cách điệu dùng bộ hình học gắn vào đầu và đóng mí đồng bộ. Chuyển trạng thái ngắn, có giữ biểu cảm và nhả về nghỉ; không đổi đột ngột ở mỗi câu.
2. **Hai clip cơ thể:** lắc hông và từ chối. Tạo nhịp lấy đà → diễn → hạ xuống, vai/đầu trễ và đối pha vừa phải. Một điểm xuất phát để thử là dịch hông 2–4 cm và xoay/nghiêng vài độ; đây là tham số đề xuất, chưa đo được từ video. Giữ chân trụ, cho phép gối bù, hạn chế biên độ khi đang đi. Tóc, tay áo và váy vẫn nhận động lực từ cùng khung xương.
3. **Bộ phối diễn xuất:** câu vui/chọc → mặt cười hoặc `><`; từ chối nhẹ → clip từ chối + mặt hờn; ngạc nhiên → mày/mắt/miệng “ơ”; lè lưỡi chỉ là cử chỉ ngắn đúng ngữ cảnh. Mỗi lượt chọn ít động tác, có thời gian nghỉ và chuyển mềm, không kích hoạt lại liên tục.
4. **Ưu tiên và kiểm tra:** đang di chuyển thì giảm hoặc hoãn các động tác hông lớn; khẩu hình và tongue-out có quy tắc phối rõ; chớp mắt không chen vào mắt `><`/`--`. Kiểm tra mặt trước/nghiêng, đồng bộ audio, chân trụ và `test_draco_native_skirt.mjs` với từng clip mới để không tái phát lỗi đùi xuyên váy.

Ưu tiên triển khai: bộ mặt (blink, nhắm mí, `><`, `--`, ngơ ngác) → hai clip cơ thể → lè lưỡi → bộ chọn cảm xúc theo câu nói. Đây là phần tạo khác biệt lớn nhất so với Mao hiện tại.

## Bản preview đã triển khai

Mở `http://127.0.0.1:12394/mao-5070/draco/` (chạy lại bằng `scripts/start_draco_preview.ps1` nếu cần).

- Nút **Xem demo Malfoy** phối 6 lượt: lắc hông/cười nhẹ → không chịu đâu/mắt ngang → cười/mắt `><` → ngạc nhiên → ngượng/cười nhẹ → chào. Demo lặp, có thể chọn từng cử chỉ và nét mặt riêng. **Cận biểu cảm** đưa camera tới mặt.
- `performance-face.mjs`: thêm morph mí, mày, tròng mắt nhỏ khi ngạc nhiên và khóe miệng cười; nét mắt anime là mesh skinned theo đầu, có depth test. Chớp mắt định kỳ, gaze nhẹ, chuyển nét mặt mềm; giữ khẩu hình theo audio.
- `performance-motion.mjs`: kế thừa solver cũ. Bản v3 đã giảm biên độ v2 từ 11,8 cm xuống 6,4 cm trái–phải; giảm nghiêng hông từ khoảng 8° xuống 3°, xoay từ khoảng 6° xuống 2°, giảm nhún lên/xuống và độ bù đầu. Chu kỳ 0,84 giây được chọn sau đối chiếu các đỉnh vị trí váy trong đoạn 2–3,6 giây (đỉnh khoảng 2,35/3,15; đáy khoảng 2,8/3,6). Hai tay đặt cạnh hông, khuỷu hơi đưa ra sau. Tăng độ hồi và giảm độ văng của riêng tà áo trong action này, trở lại thông số cũ khi nhả động tác. Từ chối giữ nhịp cũ, có lắc đầu, lòng bàn tay hướng người xem. Chuyển động vào/ra qua spring, giữ IK chân và chỉ chạy một lượt mô phỏng vải mỗi bước.
- Theo yêu cầu mới nhất, biểu cảm lè lưỡi đã được gỡ khỏi bộ mặt, demo, UI và mã dựng mesh. Khẩu hình nói chuyện vẫn giữ các chi tiết trong miệng cần thiết.
- Bản v4 thêm độ trễ cân bằng toàn thân trên: spine, chest và vai phản ứng nhẹ với gia tốc di chuyển, đổi hướng và vận tốc dịch hông; cổ/đầu bù ngược để giữ hướng nhìn. Mỗi trục phản ứng bị giới hạn 0,012 rad, dừng thì trở về nghỉ, không chạy một dao động độc lập kéo dài. Đây là chuyển động cả khung thân, không thêm mô phỏng vùng cơ thể riêng. Tóc dài tăng giảm chấn nhẹ khi chuyển động; giữ nguyên tóc mái bám đầu, giới hạn hông v3 và solver chân/váy.
- Hai module này được dùng chung bởi preview và `native-avatar.mjs` trên desktop. `performance-context.mjs` chọn cử chỉ và nét mặt theo nội dung câu nói; bridge hỗ trợ lệnh trực tiếp cho lắc hông và không chịu đâu. Xuất GLB vẫn chỉ chứa 17 cử chỉ cơ bản; mặt và 2 cử chỉ mới là tính năng runtime của cả desktop và preview.

Kiểm tra: `node tests/test_draco_preview_expression.mjs` và `node tests/test_draco_face.mjs` đều đạt. Test preview đo liên tục 8 giây cho mỗi action mới, kiểm tra chân trụ, chuyển tay, hướng lòng bàn tay, đùi so với hình học váy, chớp mắt, khẩu hình, shader nụ cười và nét mắt bám khớp đầu. Bản v3 đo chu kỳ lắc thực từ các đỉnh dịch chuyển, giới hạn biên độ trong 5–8 cm để tránh lặp lại lỗi v2 quá mạnh, xác nhận biểu cảm lè lưỡi và mesh đưa lưỡi ra đã bị loại bỏ. Không phát hiện đùi xuyên váy ở các mẫu đã kiểm tra. Ảnh QA dựng từ vertex thực sau morph và skinning đã được xem ở chính diện và góc nghiêng 32 độ; đây là kiểm tra offline, chưa đo FPS hoặc kiểm thử UI/GPU trong trình duyệt.

Tái tạo ảnh kiểm tra khi cần: chạy `node scripts/sample_draco_expression_qa.mjs`, rồi `.venv/Scripts/python.exe scripts/render_draco_expression_qa.py`. Dữ liệu trung gian trong `private/draco-expression-qa.*` có thể xóa sau kiểm tra.
