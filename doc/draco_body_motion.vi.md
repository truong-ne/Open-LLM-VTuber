# Chuyển động cơ thể — bản tự nhiên hơn (v2)

Ghi chú: bản hiện tại đã bổ sung 10 action kể chuyện (tổng 17); xem `draco_story_actions.vi.md`. Nội dung dưới ghi lại kiểm tra của v2 trước đó.

Preview riêng: http://127.0.0.1:12394/mao-5070/draco/

Model nguồn: Draco_Malfoy — xunbile, [Sketchfab](https://sketchfab.com/3d-models/draco-malfoy-40ee60d6a7214c949ff0b1338a48309c), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Giữ geometry, texture và skin weights nguồn; không sửa tệp gốc trong Downloads.

## Thay đổi lần này

- Cử chỉ trò chuyện thành từng ý: chuẩn bị, nhấn, giữ ngắn, thu tay. Hai tay xuất hiện lệch nhau; bỏ cách vung đồng thời theo sóng sin.
- Vai dẫn động tác, khuỷu và cổ tay theo sau. Xoay lòng bàn tay được chia giữa cẳng tay, cổ tay và các MMD twist helper đang có trọng số, hạn chế nếp xoắn ở tay áo.
- Đầu, cổ, ngực và hông phối hợp; chuyển động nhỏ dùng nội suy biến thiên chậm thay cho lắc đều liên tục. Gật đầu có nhịp giảm dần; chào chỉ vẫy ở phần giữa động tác.
- Ngón tay có độ cong khác nhau và mở theo cử chỉ. Hai chân vẫn dùng IK giữ cổ chân.
- 218 đoạn tóc, tay áo, vạt áo và váy dùng spring tail trong không gian thế giới: quán tính, lực kéo về dáng gốc, trọng lực, cản và ràng buộc chiều dài/góc. Các phần có độ cứng khác nhau.
- Capsule đơn giản ở đầu/thân/đùi/cẳng chân giúp đẩy các đầu chuỗi ra khỏi cơ thể. Loại trừ các điểm đã nằm trong vùng va chạm ngay từ bind pose để không làm hỏng gốc tóc.
- Giới hạn tay áo nhỏ hơn sau kiểm tra hình: biên độ quá lớn làm lộ hạn chế skin weights gốc. Chưa thay trọng số hay dựng lại mesh.
- Bảy clip GLB có 0,6 giây cuối hòa về đúng pose đầu, tránh giật ở điểm lặp. Preview chạy liên tục với bước mô phỏng 120 Hz.

Tham khảo cơ chế spring tail, chiều dài và capsule trong [đặc tả VRMC_springBone](https://raw.githubusercontent.com/vrm-c/vrm-specification/master/specification/VRMC_springBone-1.0/README.md). Đây là solver riêng cho rig nguồn, không phải tuyên bố xuất model VRM.

## Kiểm tra

`node tests/test_draco_body_motion.mjs` đã đạt:

- Bảy động tác, mỗi động tác chín giây; quaternion hữu hạn, chuẩn hóa, tay chào nâng lên và chuyển trọng tâm thật sự hoạt động.
- Sai lệch cổ chân tối đa khoảng 7,3e-7 đơn vị nguồn.
- Bước dịch tay tối đa ở 60 Hz khoảng 0,0194 đơn vị; xoay cổ tay tối đa khoảng 0,0784 rad giữa hai frame trong các động tác được kiểm tra.
- 218 đoạn tóc/vải không bị kéo dài; 150 lần xử lý tiếp xúc trong toàn bộ các chuỗi thử. Sai số còn lại tại các đầu xương khoảng 2,15e-8 đơn vị nguồn. Đây là kiểm tra đầu xương/capsule, không chứng minh toàn bộ bề mặt vải không xuyên nhau.
- Fixture va chạm cưỡng bức được tách ra, solver đẩy điểm ra khỏi capsule.
- Chuỗi ngắt và đổi động tác dài 21 giây, kiểm tra giữ chân và bước dịch tay. Kết quả động tác ở 30/60/120 FPS khớp nhau.
- Bảy clip hợp lệ, binding duy nhất, pose đầu/cuối khớp; phát lại bằng AnimationMixer và kiểm tra tư thế tay.

Dữ liệu số: `web_tool/mao-5070/draco/motion-test-report.json`.

## Tệp và giới hạn

- `web_tool/mao-5070/draco/draco-body-motion.glb`: model với bảy clip, xuất lại từ preview và nạp lại kiểm tra.
- `web_tool/mao-5070/draco/draco-body-motion.webm`: clip preview 30 giây.
- `scripts/start_draco_preview.ps1`: bật server cục bộ ẩn, không cần admin.

Đây vẫn là animation thủ tục trên rig có sẵn. Tóc/vải mô phỏng theo xương và capsule, chưa có va chạm giữa mọi tam giác, tự va chạm của vải hay cloth solver đầy đủ. Model nguồn chưa có morph mắt–miệng; chưa thêm khẩu hình hoặc chớp mắt. Không thay model Mao trong cấu hình desktop/livestream.

## Kiểm tra bàn giao v2

Đã xem preview ở góc chính diện, nghiêng khi cúi, và phía sau khi chuyển trọng tâm. Console không có lỗi trong lần kiểm tra cuối. GLB xuất lại có nhãn `natural-body-v2`, 55.149.648 byte, đủ 7 clip; sai khác pose đầu/cuối trong dữ liệu GLB thực tế tối đa khoảng 2,98e-7. Clip 30 giây đã ghi lại và kiểm tra khung hình ở giây 2,3 / 8,9 / 10,8 / 24,5 (chào, hai tay lần lượt, chuyển trọng tâm). Ảnh xác nhận tạm của lần kiểm tra này đã dọn theo yêu cầu.
