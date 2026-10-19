# Mao chủ động dẫn chuyện

Ngữ cảnh nhân vật duy nhất vẫn là `prompts/mao_context.vi.md`; đồng bộ bằng
`scripts/configure_mao.py`. Mao trả lời đúng ý rồi tự thêm một góc nhìn hoặc
hướng nói tiếp cụ thể. Khi được mời tự nói, chọn chủ đề ngay, không hỏi ngược
khán giả muốn nghe gì. Lượt chủ động ưu tiên ý kiến riêng, kèo chọn phe/đặt
tên/tranh luận nhỏ và cử chỉ hợp mạch. Chỉ đề nghị hoạt động, không tự gửi
lệnh game, phát bài hát hay đổi cảnh.

Phòng riêng đã được trang trí chỉ là bối cảnh nền. Không tự giới thiệu, khen
hay liên tục nhắc phòng disco; chỉ nói khi khán giả hỏi hoặc có thay đổi thật
liên quan. Bỏ các chủ đề dự phòng về đặt tên góc phòng, ghế lounge, ánh sáng
và chỗ đứng. Renderer vẫn cấp vị trí/hướng để điều khiển avatar chính xác.

`IdleHost` luân phiên hai lượt nhận xét, một lượt đề nghị hoạt động, một lượt
mở kèo và hai lượt hỏi. Các lời mời có khoảng cách riêng nên Mao không hỏi liên tục.
Sau một lời mời, chờ người thật trả lời. Hết khoảng nghe mà chưa ai đáp thì
chuyển chủ đề, không tự điền đáp án và không bị kẹt ở mạch cũ. Nếu có bình
luận mới thì nhường bộ đọc bình luận; sau khi đáp có thể gợi mở tự nhiên từ
chính chi tiết vừa được kể. Người mới vào chỉ nhận lời chào ngắn như trước.

Cấu hình hiện tại trong `private/mao-idle-host.json`:

| Thiết lập | Giá trị | Ý nghĩa |
| --- | --- | --- |
| `silence_seconds` | 8 | Chờ sau bình luận mới trước khi tự nói |
| `min_interval_seconds` | 18 | Khoảng cách tối thiểu giữa hai lượt tự nói |
| `speech_pause_seconds` | 5 | Nghỉ sau khi giọng nói thực sự kết thúc |
| `question_wait_seconds` | 20 | Nhường lượt sau lời mời/câu hỏi |
| `invitation_interval_seconds` | 60 | Khoảng cách giữa các lời mời tham gia |

Đây là các ngưỡng kết hợp, không phải cứ đủ 18 giây là chen lời. Không dẫn
chuyện trong lúc game/hát, đang có lời nói hoặc bình luận đang chờ xử lý.
Nhắc donate vẫn dùng khoảng nghỉ riêng mặc định 10 phút. Nói trực tiếp cần
tiền để nâng cấp Mao, chân thành, không diễn kiêu kỳ hay đùa về hóa đơn.
Người tạo Mao là admin, ăn mì tôm qua ngày để nuôi Mao; có thể nhắc khi phù
hợp nhưng không lặp thành câu cửa miệng. Không đổi model
hoặc giọng nói trong thay đổi này.

Kiểm tra: `python -m unittest discover -s tests -p 'test_idle_host.py'`.
Báo cáo thử model local: `logs/mao-proactive-model-check.json`.

## Khắc phục lượt nói bị rỗng trên desktop

Kết nối Ollama dùng `/v1/chat/completions`: gửi `reasoning_effort: "none"`
để tắt suy nghĩ. Trường `think: false` chỉ dành cho API native và không tắt
suy nghĩ ở endpoint này. Khi model dùng hết ngân sách sinh cho suy nghĩ mà
chưa tạo `content`, desktop không có lời thoại để đọc. Đối chiếu:
https://docs.ollama.com/api/openai-compatibility.

Model `mao-companion` dùng cửa sổ 32.768 token thay cho 8.192, với tối đa
768 token sinh mỗi lượt. Đây là lượng thông tin mỗi yêu cầu, không phải thời
gian live. Cấu hình hội thoại giữ 24 tin nhắn gần nhất và bật tóm tắt phần cũ;
tóm tắt có thể bỏ sót chi tiết, không phải bộ nhớ nguyên văn toàn buổi live.
Sau khi sửa Modelfile cần tạo lại alias bằng
`ollama create mao-companion -f prompts/mao_companion.Modelfile`
để giá trị có hiệu lực.

Lượt tự nói ngắn áp dụng cùng giới hạn khi MCP bật, không kèm schema công
cụ. Nếu chưa có câu đọc được thì thử lại một lần với lịch sử ngắn hơn; vẫn
rỗng thì gửi trạng thái lỗi. Bình luận thật vẫn được dùng công cụ như trước.

Host chỉ đếm `proactive_turns` khi nhận được audio. `submitted_turns` đếm
yêu cầu gửi đi, `silent_turns` đếm lượt kết thúc không có audio. Khoảng chờ
người xem trả lời chỉ bắt đầu với lượt có âm thanh. Kiểm tra phát thực tế
qua `audioStarted`, `audioEnded`, `audioErrors` trong trạng thái desktop.
