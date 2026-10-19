# Mao 5070 — preview mesh, 17/10/2026

## Lần sửa tỷ lệ và cử chỉ theo phản hồi tiếp theo

- Chân/bốt hẹp hơn khoảng 29% và ngắn hơn khoảng 7% so với preview trước. Đây là điều chỉnh mesh khi dựng hình, không sửa ảnh atlas gốc.
- Thêm không gian 2.5D và phép chiếu phối cảnh: hông, vai và mặt có góc xoay riêng; bề mặt mặt có độ sâu để tạo parallax. Tay đưa ra trước có thay đổi phối cảnh.
- Hai chân dùng nghiệm IK hai đoạn trong không gian 3D, gối hướng ra trước, bàn chân giữ cố định. Lưới nối qua hông–gối–cổ chân bằng nội suy Hermite liên tục.
- Thêm bốn action: giải thích bằng tay, gật đầu, chuyển trọng tâm và quay vai/đầu. Chào và ngượng có biên độ tay rõ hơn. Hai tay trong động tác giải thích có đường thời gian khác nhau: đổi lượt đưa ra, thu vào, kết hợp nhịp đầu.
- Sửa lỗi hạ tay quá nhanh khi chuyển từ chào sang giải thích bằng blend mục tiêu trong 0,65 giây, giữ vận tốc lò xo hiện tại.
- Test mở rộng 12 trạng thái đều không có tam giác đảo chiều ở các mẫu kiểm tra. Kiểm tra chiều dài xương đùi/cẳng chân, hướng gối và bàn chân không trượt. Chuỗi 27 giây đổi động tác giữa chừng ở 60 Hz: bước lớn nhất của điểm theo dõi giảm từ 37 xuống 17,93 đơn vị tọa độ mô hình, không phải pixel màn hình.
- Có nút ghi clip 28 giây ngay trong preview, xuất WebM local để kiểm tra chuyển động. Không có thao tác phát lên livestream.

Đây vẫn là hình minh họa mặt trước trên rig 2.5D, không phải nhân vật 3D hoàn chỉnh. Chưa có mặt sau, bàn tay rig từng ngón hay độ che khuất đúng ở các góc xoay lớn. Không coi các kiểm tra hình học là bằng chứng rằng chất lượng diễn xuất đã đạt anime chuyên nghiệp.

Mở http://localhost:12393/web-tool/mao-5070/ khi server dự án đang chạy.
Bản vector SVG bị từ chối đã được gỡ khỏi nguồn và gói desktop. Desktop tiếp tục dùng `mao_pro`; không đăng ký hoặc tự chuyển sang Mao 5070.

## Hình ảnh và kỹ thuật

- Hình minh họa tạo bằng ImageGen tích hợp, dựa trên concept đã chọn. Prompt lưu tại `web_tool/mao-5070/asset-prompt.txt`, atlas RGBA tại `parts-atlas.png` cùng thư mục.
- Sáu lớp texture: đầu, thân/trang phục, hai tay và hai chân; WebGL vẽ 49.088 tam giác. Đây là rig riêng, không phải model Cubism `.moc3`.
- Khớp tay dùng phép uốn theo cung tròn để giữ thể tích tay áo. Tóc, mái, nơ, vạt áo và gấu váy biến dạng cục bộ theo chuỗi lò xo; không lắc nguyên một ảnh.
- Chào có lấy đà, đưa tay lên, vài nhịp cổ tay và hạ tay; đầu, thân và tay có nhịp khác nhau. Cười có các nhịp ngắn giảm dần.
- Mắt liếc trước đầu, chớp nhanh khi đóng và chậm hơn khi mở; khoảng chớp thay đổi và đôi khi chớp hai lần. Chớp mắt không hủy biểu cảm đang diễn.
- Miệng dùng RMS của âm thanh; cử chỉ nói được kích hoạt có khoảng nghỉ theo điểm nhấn âm lượng. Không phải nhận dạng âm vị/viseme. Mẫu Mỹ Duyên dài 6,77 giây, phát local khi bấm nút.
- Checkbox trình diễn tự động lần lượt chạy chào, tò mò, cười, ngượng, buồn, nghỉ. Không kết nối chat hoặc phát lên livestream.

## Tài liệu đã tham khảo

- [Live2D: thiết lập physics](https://docs.live2d.com/en/cubism-editor-manual/physical-operation-setting/): chuỗi phản ứng cho chuyển động phụ.
- [Live2D: motion fade](https://docs.live2d.com/en/cubism-editor-manual/about-fade/): nối động tác với thời gian chuyển tiếp.
- [Live2D: tự chớp mắt](https://docs.live2d.com/en/cubism-sdk-manual/autoeyeblink/): tách thời gian đóng, giữ và mở mắt.

Áp dụng nguyên tắc vào rig WebGL hiện có; không cài skill bên thứ ba và không tuyên bố đang dùng Cubism SDK.

## Kiểm tra

`node tests/test_mao_mesh.mjs` kiểm tra tám trạng thái trong 9 giây/trạng thái. Mỗi trạng thái kiểm tra 168.003 lượt tam giác hiển thị ở chín thời điểm: không có tam giác đảo chiều. Kết quả trạng thái tại 30/60/120 FPS trùng nhau nhờ bước mô phỏng 240 Hz.

Kiểm tra bổ sung: 13 lần chớp trong 45 giây với khoảng không đều; bốn cử chỉ theo bốn đợt âm thanh; không tự tạo cử chỉ nói khi im lặng; chuyển động không nhảy tư thế ngay khi đổi action; chớp mắt không hủy cảm xúc. Test adapter Mao cũ và kiểm tra cú pháp JS/Python đều qua.

Đã kiểm tra trực tiếp giao diện: tư thế chào, mắt nhắm cận cảnh, nói theo mẫu Mỹ Duyên; âm thanh kết thúc thì miệng về 0. Console không có lỗi trong lần kiểm tra. Đây không phải thử độ bền livestream 8 giờ.

## Giới hạn và điều kiện phát hành

Tóc/mặt và ngón tay chưa được vẽ tách thành đầy đủ các lớp như một model Cubism do họa sĩ rig thủ công. Chưa hỗ trợ góc quay đầu lớn, xoay người, cử động từng ngón hay khẩu hình theo từng âm vị. Ngoại hình vẫn cần người dùng đối chiếu với concept và duyệt preview trước khi thay Mao cũ.

Cache tokenizer ONNX trùng được tạo khi làm mẫu giọng vẫn còn ngoài dự án: công cụ từ chối thao tác xóa do chính sách. Script tạo mẫu đã được sửa để các lần sau dùng `models/` của dự án ở chế độ offline.
