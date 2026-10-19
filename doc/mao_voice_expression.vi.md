# Giọng nói có sắc thái cho Mao

Đối chiếu ngày 16/10/2026 với [tài liệu VieNeu](https://docs.vieneu.io/docs/sdk/voice-cloning/) và [mã nguồn chính thức](https://github.com/pnnbao97/VieNeu-TTS). Máy đang cài `vieneu 3.8.3`, chạy v3 Turbo ONNX/CPU, preset Mỹ Duyên tạo lời nền rồi chuyển sang **Linh Lan Ch qua RVC**, tốc độ nền 1,08×. Cập nhật nhịp đọc ngày 19/10/2026 theo yêu cầu tăng cảm xúc.

VieNeu v3 Turbo bỏ qua tham số `style`: không có chế độ `happy`, `sad` hay `whisper` có thể bật tùy ý qua tham số này. Chất giọng cơ bản đi theo preset/reference. SDK hỗ trợ thử nghiệm ba cue phi ngôn ngữ `[cười]`, `[thở dài]`, `[hắng giọng]`, chuyển lần lượt thành token `emotion_1`, `emotion_2`, `emotion_3`. Không suy đoán ý nghĩa của các token dự phòng khác. Mức thể hiện còn phụ thuộc model và preset; các cue này không tương đương khả năng điều khiển đầy đủ mọi cảm xúc.

Mao kết hợp hai lớp:

- Lời thoại và dấu câu: phản ứng theo nội dung, câu hỏi có dấu hỏi, câu reo nhẹ có chấm than, ngắt nhẹ bằng phẩy. Chọn thẻ biểu cảm Live2D khi phù hợp. Đợi trọn câu đầu thay vì cắt ngay tại dấu phẩy để TTS có thêm ngữ cảnh.
- Kế hoạch đọc riêng cho từng câu: vui nhanh thêm 6%, ngại chậm 6%, trêu chậm 2%, tò mò chậm 3%, dịu chậm 8% so với tốc độ nền. Khoảng nghỉ sau câu 80–180 ms theo sắc thái; nhịp ngại và an ủi được phân biệt rõ hơn với reo vui. Các mức thay đổi vừa phải và giữ nguyên cao độ bằng FFmpeg `atempo`, không uốn cao độ nhân tạo. Đây là điều chỉnh nhịp, không phải chế độ cảm xúc gốc của VieNeu.

Planner nhận cả [shy], [surprised], [tilt], [refuse] khi chúng mang sắc thái giọng. `actions_extractor` giữ ý định đọc trong trường nội bộ `SentenceWithTags.speech_text` trước khi xóa thẻ cử chỉ khỏi câu; nhờ vậy [shy] không bị mất trước khi tới TTS. Câu sau không có thẻ kế thừa nhẹ trong tối đa hai câu; thẻ cảm xúc mới đổi nhịp ngay và mỗi lượt hội thoại bắt đầu lại. Dấu câu và cách viết lời thoại đưa ngữ cảnh ngắt/nhấn cho TTS; không đặt tham số `style` giả hoặc tự thay cao độ giọng Linh Lan Ch.

Cue được lấy ra trước bộ lọc TTS, lưu dưới dạng metadata nội bộ và ẩn khỏi phụ đề. Chỉ engine VieNeu nhận metadata này. Khi tạo tiếng nói, cue hợp lệ được đưa lại vào văn bản ở trước dấu kết câu, để SDK chuyển thành token; các nhãn biểu cảm hoặc cue lạ không bị đọc ra thành chữ. Mỗi lượt tối đa một cue; `[cười]` chỉ dùng khi có ý đùa thật, `[thở dài]` rất hiếm trong tình huống hư cấu tự trào. Không bật hắng giọng như thói quen mặc định, không tự tạo cue thì thầm/gợi cảm và không thêm tiếng cười vào lúc khán giả đang buồn.

Cấu hình `character_config.tts_config.vieneu_tts.expressive: false` tắt lớp đọc biểu cảm, vẫn giữ tốc độ nền. Giọng preset và reference đang chọn không bị thay bằng giọng khác. Không cần API key, không tải model mới hoặc tạo kho audio thử giọng. Kiểm tra model thật dùng waveform trong RAM; các file âm thanh phát LIVE vẫn đi qua cache ngắn hạn có sẵn và được dọn sau khi đóng gói payload.

Kiểm tra tự động bao gồm luồng cue từ đầu ra model đến TTS, không hiển thị/đọc nhãn cue, giới hạn cue theo lượt, tương thích engine khác, parser cue của SDK đang cài, giữ preset và kiểm tra cao độ/tốc độ bằng tín hiệu mẫu. Chất lượng biểu cảm cuối cùng cần được nghe đánh giá; không suy ra giọng đã giống người thật chỉ từ kiểm tra phần mềm.
