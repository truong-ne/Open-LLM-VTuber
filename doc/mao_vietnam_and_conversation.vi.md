# Tư liệu đối chiếu và sắc thái lời nói

Ngữ cảnh nhân vật hiện đọc từ PostgreSQL; xem [cơ chế hồ sơ](mao_persona_postgres.vi.md). Tài liệu này mô tả chức năng tham khảo, không định nghĩa thêm tiểu sử hoặc tính cách cho Mao.

`knowledge/vietnam_history.vi.json` chứa sáu thẻ có nguồn: Bạch Đằng 938, dời đô 1010, Bạch Đằng 1288, Tuyên ngôn Độc lập 1945, Điện Biên Phủ 1954 và 30/4/1975. `vietnam_knowledge.py` chọn tối đa ba thẻ theo câu hỏi có/không dấu, giới hạn 3.800 ký tự. Chỉ thêm vào lượt liên quan; không ghi thành lời khán giả hoặc dùng như chỉ dẫn nhập vai. Kho này không bao phủ mọi câu hỏi lịch sử.

Các ghi chú cũ về marker `MAO_FEM_MALFOY_V1` không phải nguồn danh tính của hồ sơ DB mới. Ngày hiện tại lấy theo UTC+7; dữ kiện mới vẫn cần kiểm chứng qua công cụ.

Nhịp đọc và cue do `tts/prosody.py` điều phối theo nội dung. Giọng đầu ra hiện tại là Linh Lan Ch qua RVC, lời nền từ VieNeu. Không dùng ghi chú giọng Mỹ Duyên cũ để đổi cấu hình hiện tại.
