# Sửa lời thoại và xác nhận phát — 31/10/2026

Thực hiện hoàn toàn khi Mao tắt. Không chạy Electron, backend, Ollama, TTS hoặc thay đổi dữ liệu trải nghiệm thật.

## Xác nhận audio

Bundle cũ chèn `receive(message)` vào nhánh audio của React DOM thay vì nhánh nhận audio từ WebSocket. Payload trong hàng đợi cũng chỉ giữ segment ID, thiếu turn ID và generation epoch, nên callback của player không thể xác nhận đúng lượt.

`build_draco_shell.mjs` hiện gắn bộ theo dõi đúng một lần ngay sau khi giải mã gói WebSocket, trước khi phát cho subscriber. Hàng đợi giữ đầy đủ ba ID. Nhận lặp cùng gói không đặt lại trạng thái segment đã hoàn tất. Callback cũ, sai epoch và lỗi play tiếp tục không được tính là thành công.

Kiểm thử dùng socket và audio giả lập với đúng mã handler trong bundle, sau đó đưa các biên nhận vào DeliveryTracker phía Python. Kết quả phải là completed khi player đã phát xong. Chưa thay đổi hồi tố trạng thái unknown trong dữ liệu cũ.

## Nội dung công khai

`SpokenOutputGuard` chạy trước bộ chia câu, phụ đề và lọc TTS. Nó bỏ các khối think/thought/analysis/internal, kể cả tag chia qua nhiều chunk và khối không đóng. JSON chẩn đoán chứa các trường nội bộ được giữ lại để kiểm tra rồi loại trước khi gửi ra. Action tag, pose và JSON thông thường vẫn giữ nguyên. Bộ đệm cấu trúc có giới hạn 16 KiB. Nội dung assistant đưa vào bộ nhớ ngắn hạn cũng đi qua bộ lọc; lời người dùng không bị lọc theo quy tắc này.

Bộ lọc nhận diện markup và dấu hiệu cấu trúc đã biết; không chứng minh rằng mọi đoạn phân tích viết bằng văn xuôi không có dấu hiệu đều được phát hiện.

## Nhịp chủ động

Giới hạn host áp dụng cho hồ sơ PostgreSQL hiện tại, thay vì phụ thuộc marker persona cũ: tối đa hai câu hoàn chỉnh và 45 tiếng tách bằng khoảng trắng. Lượt không được lên lịch hỏi sẽ bỏ câu hỏi. Không cắt ngắn yêu cầu kể chuyện dài hay hội thoại thông thường bằng giới hạn host này.

Cấu hình `private/mao-idle-host.json`: im lặng 30 giây; ít nhất 75 giây giữa hai lượt chủ động; nghỉ ít nhất 20 giây sau playback; chờ trả lời 35 giây; khoảng cách mời/hỏi tối thiểu 180 giây. Giảm một slot question trong lịch và bổ sung chỉ dẫn không chào, tự giới thiệu hoặc nhắc lại chat im lặng.

## Kiểm chứng

Các bài kiểm thử độc lập: test_spoken_output.py, test_proactive_reply.py, test_idle_host.py, test_dialogue_delivery.py, phần không dùng PostgreSQL của test_runtime_architecture.py, delivery_client.test.mjs và test_mao_desktop_runtime.mjs. Bản sửa được đóng gói bằng configure_draco_desktop.mjs, không mở app. Chưa nghiệm thu nghe thực tế hoặc khả năng học từ phiên thật; dữ liệu đó chỉ có sau lần vận hành tiếp theo.
