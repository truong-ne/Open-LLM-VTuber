# Mao: phối tư thế và ghi nhớ hiệu chỉnh cơ thể

Bản `adaptive-motor-v1` cho phép mô hình tạo ý định bằng tham số liên tục, sau đó bộ điều khiển dựng tư thế trên rig Draco. Đây là phiên bản đầu của điều khiển thích nghi; không phải tự huấn luyện lại trọng số hoặc tự học vô hạn từ việc bật livestream.

## Đã có

- Tự phối độ nghiêng/cúi đầu, cúi thân, mức mở từng tay, độ cao tay, nụ cười, nhướng mày và mắt mở to theo câu nói. Không cần tạo một clip cho mỗi tổ hợp.
- Ý định được gửi cùng câu âm thanh và chỉ bắt đầu khi phát câu đó; hết hạn sau 2–7 giây, chuyển về tư thế nền có làm mượt.
- Bộ điều khiển giải IK, giới hạn cổ tay, giữ chân, tính tóc/quần áo và chống đùi xuyên váy như trước. Ý định không được truy cập tên xương, chạy mã hoặc đổi vị trí/hướng phòng. Khi đang đi, hiệu lực tư thế tự phối giảm xuống; khóa camera và vị trí trong lượt nói vẫn được ưu tiên.
- Kiểm tra sai số chân có thể hủy ý định lỗi. Đây là phản hồi hình học, chưa phải bộ đánh giá thẩm mỹ bằng thị giác.
- Hiệu chỉnh do người vận hành gõ trực tiếp trong ô chat desktop được lưu ngoài lịch sử hội thoại. Không phụ thuộc cửa sổ 24 tin nhắn. Tham số được dùng lại sau khi đóng/mở app; có 32 bước hoàn tác.

## Cách dạy trong app desktop

Gõ đúng một câu ngắn dưới đây (có thể thêm `Mao` ở đầu):

| Câu gõ | Điều chỉnh cho các tư thế tự phối tiếp theo |
|---|---|
| `Mao cử động nhẹ hơn` / `Mao cử động mạnh hơn` | Biên độ đầu, thân và mở tay |
| `Mao cử động nhanh hơn` / `Mao cử động chậm hơn` | Nhịp chuyển đầu/thân và tay |
| `Mao tay thấp hơn` / `Mao tay cao hơn` | Độ cao đích IK tay |
| `Mao biểu cảm rõ hơn` / `Mao biểu cảm nhẹ hơn` | Cường độ nét mặt liên tục |

Các câu chỉnh thông thường vẫn được gửi tới hội thoại, đồng thời xuất thông báo lưu cục bộ. Đây là các mẫu hiệu chỉnh được hỗ trợ rõ ràng, chưa hiểu mọi câu góp ý tự do. Các clip cũ vẫn có thể được chọn làm phương án dự phòng và không bị các hiệu chỉnh này viết lại.

Lệnh cục bộ, không gửi tới LLM: `/co-the xem`, `/co-the hoan-tac`, `/co-the mac-dinh`. Đặt mặc định vẫn có thể hoàn tác. Để xóa hoàn toàn dữ liệu hiệu chỉnh, xóa khóa `mao.draco.motor-learning.v1` trong localStorage của app; không cần xóa lịch sử trò chuyện hoặc model.

Chỉ luồng gõ trực tiếp của desktop được gọi hàm học. Văn bản mô hình sinh ra, bình luận TikTok và bản chép ASR không được tự sửa hồ sơ. Chưa dùng lời nói để dạy vì luồng hiện tại chưa xác thực được người nói là chủ máy. Nếu không ghi được storage, app báo rõ chưa lưu được.

## Luồng thực thi

`Mô hình → [pose:tham_số] → bộ lọc luồng token → Actions.pose → hàng đợi âm thanh gốc → hồ sơ hiệu chỉnh → mục tiêu đầu/thân/tay/mặt → IK/vải/giới hạn → render`.

Ví dụ ý định nội bộ: `[pose:right=0.65,left=0.2,tilt=-4,smile=0.4,duration=4]`. Thẻ không được đọc thành tiếng hoặc lưu làm nội dung ký ức assistant. Tên trường ngoài danh sách, bool, NaN, Infinity và lệnh thực thi bị loại; giá trị hữu hạn vượt miền bị giới hạn ở cả Python và JavaScript. Bộ bảo vệ token giữ nguyên số thập phân qua các mảnh streaming và không phát lệnh còn dang dở.

Backend chỉ cung cấp khả năng này khi renderer Draco đang có trạng thái mới. Mô hình vẫn quyết định dùng cử chỉ lúc nào; không đảm bảo mỗi câu đều có ý định mới. Câu sửa đã lưu ảnh hưởng các ý định tương lai; không có lời hứa model đã nhìn thấy và tự đánh giá tư thế của mình.

## Xem thử và giới hạn

Trang preview Draco có mục **Tự phối tư thế**, cho thử các mức liên tục trên cùng bộ điều khiển. Preview không sửa bộ nhớ của desktop.

Khả năng hiện tại bị giới hạn bởi rig và các vùng biến dạng đã dựng: chưa tự phát minh một dáng đi mới, động tác nhào lộn, biểu cảm ngoài topology hiện có hoặc tự học chuyển động từ video. Muốn tiến tới đó cần dữ liệu chuyển động, retarget, bộ đánh giá và huấn luyện/kiểm định riêng. Cho app chạy một năm chỉ tạo dữ liệu; cần vòng phản hồi có chất lượng mới cải thiện được hành vi.

## Kiểm tra

- `tests/test_motor_intent.py`: tham số, lệnh lỗi, token bị chia ở dấu thập phân, thẻ nghĩ, pending qua ranh giới câu, renderer chưa sẵn sàng.
- `tests/test_draco_motor_learning.mjs`: hồi phục bộ nhớ sau khởi tạo lại, hoàn tác, giới hạn học, lỗi storage, hai tư thế khác nhau trên mesh thật, chuyển mềm, thời hạn, chân/sàn, váy và khóa nói hướng camera.
- `tests/test_draco_original_shell.mjs`: ý định pose đi xuyên hàng đợi âm thanh cũ; UI/IPC/drag/zoom gốc giữ nguyên.

Kiểm tra app đang chạy ngày 19/10/2026: mô hình tự sinh `{right: 0.55, tilt: -3, smile: 0.4}` cho câu chào ngắn. Quan sát telemetry mới trong lúc phát giọng: `lastMotorAccepted=true`, `motorActive=true`, `speechFocused=true`, `audioErrors=0`, `motorRejected=0`; sai số hướng camera khoảng 0,0000083 rad. Lượt kết thúc bình thường. Kiểm tra mesh offline có sai số chân tối đa khoảng 0,000000106 m, đùi ngoài váy 0 trong các mẫu đã kiểm tra; đây không phải bảo đảm mọi tư thế có thể tưởng tượng đều đẹp hoặc không va chạm.

Hướng dùng phản hồi và ký ức bên ngoài trọng số có tham khảo [Reflexion](https://arxiv.org/abs/2303.11366). Bản này triển khai hồ sơ hiệu chỉnh cơ thể có giới hạn; không phải tái hiện toàn bộ thuật toán trong bài báo.
