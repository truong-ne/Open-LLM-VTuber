# Mao: hướng phát triển và đợt cải thiện hội thoại 03/11/2026

## Nhận định từ mã nguồn

Mao đã có voice, avatar, bộ nhớ theo người/phòng, event/delivery, biểu cảm, hoạt động và vòng đánh giá. Ưu tiên tiếp theo là chất lượng sử dụng những thành phần này trong hội thoại nhiều lượt. Việc đã có module không chứng minh người dùng thấy hội thoại tự nhiên hoặc Mao chơi tốt hơn.

Các điểm phát hiện ở đợt này:

- `dialogue/context.py` bỏ lịch sử hội thoại trước ký ức truy hồi khi quá ngân sách. Vì vậy câu ngắn hoặc lời sửa có thể mất lượt trao đổi làm mốc.
- Runtime chèn lại toàn bộ `memories` vào khối hybrid sau khi chúng đã qua ngân sách scoped context. Điều này làm nội dung bị lặp và đưa ký ức đã bị loại vì quá dài trở lại prompt.
- Affect có thể đánh dấu boundary/correction, nhưng chưa có hướng dẫn riêng để phản hồi yêu cầu lắng nghe, sửa cách hiểu hoặc chuyển chủ đề. Nhu cầu giao tiếp và cảm xúc biểu đạt cần được xử lý riêng.
- `Focus.input` lấy đầu vào hiện tại làm topic; đó chưa phải bản tóm tắt chủ đề có ý nghĩa qua nhiều lượt. Sửa phần này cần kiểm tra cùng episode, source và thao tác quên, không chỉ đổi chuỗi trong prompt.

## Đã triển khai trong đợt này

1. Giữ lượt trao đổi mới nhất ưu tiên hơn ký ức truy hồi, hoạt động và focus quá dài. Vẫn bỏ cả bản ghi thay vì cắt JSON. Đảm bảo ngân sách phần JSON kể cả khi metadata dài, và không sửa danh sách hoạt động của bên gọi.
2. Trong đường scoped interaction, ký ức chỉ đi qua scoped context, không được chèn lại vào hybrid state. Bộ nhớ cho công cụ truy hồi vẫn được giữ; đường legacy vẫn dùng khối hybrid hiện có.
3. Thêm `dialogue/intent.py` để chọn chỉ dẫn theo lượt: lắng nghe, sửa cách hiểu, chuyển chủ đề hoặc trả lời yêu cầu rõ ràng. Chỉ dùng chỉ dẫn cố định, không chèn lời người dùng thành system rule và không thêm lượt gọi LLM.
4. Yêu cầu lắng nghe có thể tiếp nối qua một số câu ngắn đã định nghĩa, dựa trên tối đa bốn lượt có trạng thái completed trong mười phút, đã được lọc theo actor/phòng/visibility. Không lấy câu đề nghị của assistant làm nhu cầu người dùng; dừng khi gặp yêu cầu mới, ngữ cảnh không rõ hoặc trạng thái phát chưa chắc chắn.
5. Chỉ dẫn được đặt lại mỗi lượt; không ghi thành sở thích lâu dài hoặc sửa persona. Clipboard, host proposal, dữ liệu game và diễn tập không chọn chỉ dẫn giao tiếp của người dùng.

Đây là quy tắc diễn giải hẹp cho tiếng Việt có/không dấu, không phải bộ hiểu ngôn ngữ đầy đủ. Chỉ dẫn không bảo đảm model luôn tuân thủ, và “completed” chỉ là trạng thái phát chứ không xác nhận con người đã nghe.

## Đợt tiếp theo: giữ chủ đề và yêu cầu yên tĩnh

Đã bổ sung mã nguồn và migration cộng thêm `010_dialogue_attention.sql`:

- “Ừ”, “vẫn vậy” và một số câu tiếp ngắn giữ chủ đề cũ. Nguồn chủ đề tách khỏi nguồn đầu vào mới nhất; khi xóa một trong các nguồn dẫn xuất có liên quan, focus bị gỡ. Chủ đề hết hạn hoặc bị xóa không được dùng tiếp.
- Trong hội thoại riêng/test, “Papa muốn yên tĩnh”, “Mao im lặng một chút nhé”, “Đừng tự mở chuyện nữa” đặt thời hạn mười phút. Chặn đề xuất proactive/narration tại thời điểm bắt đầu lượt, kể cả đề xuất đã xếp hàng; dùng trạng thái từ chối `declined_policy` hiện có để host không bị kẹt busy.
- Vẫn nhận và trả lời đầu vào trực tiếp. “Mao nói tiếp đi” hoặc “Cứ chủ động nói chuyện lại nhé” của đúng actor gỡ yêu cầu của actor đó. Nhiều actor cùng dùng một loa riêng: chỉ dẫn yên tĩnh của một người không bị người khác hủy.
- Trạng thái giới hạn theo scope/phòng/visibility, không tự kéo dài khi Mao phát âm thanh. Người xem public không thể dùng cơ chế này để tắt một phòng live. Không ngừng game, hát hoặc mọi loại âm thanh; đây là chặn đề xuất mở chuyện tự động.
- Phủ định, trích dẫn, code và chuyện kể không đặt quiet; host proposal và nguồn synthetic không thay focus qua đường input.
- Database chưa có migration 010 dùng đường focus cũ. Kiểm tra version trước khi đọc cột mới; thao tác quên vẫn tương thích schema cũ. Lời thoại không được nhận đã tạm dừng tự động nếu hệ thống chưa xác nhận.

**Trạng thái xác minh cập nhật:** đã mở lại Docker Desktop, chạy migration database test và đạt cả 10 bài attention, không skip. Migration 010 đã áp dụng vào database Mao, runtime role đọc được cột mới; digest persona và số bản ghi memories/knowledge/events trước/sau không đổi. Báo cáo: `logs/mao-attention-migration.json`. Bộ Python tổng sau khi bổ sung evaluator có 545 bài, 535 đạt, 10 bỏ qua theo điều kiện, không failure/error; lint đạt. Chưa nghiệm thu bằng microphone/giọng nói thật.

Khi Docker hoạt động, chạy database test và kiểm tra trước:

```powershell
docker compose --env-file private/mao-test.env -f compose.mao-test.yaml up -d
.\.venv\Scripts\python.exe scripts/mao_test_db.py migrate
.\.venv\Scripts\python.exe scripts/mao_test.py --postgres --pattern test_dialogue_attention.py
```

Đã triển khai bằng `.\.venv\Scripts\python.exe scripts/mao_apply_attention_migration.py`, công cụ chỉ áp dụng migration cộng thêm 010 và ghi kiểm tra digest/count trước/sau. Có thể dùng lại khi cần xác minh. Không reset database hoặc nhập lại ký ức để triển khai tính năng. Backend đang chạy bản cũ cần khởi động lại để nạp Python mới.

## Đã có bộ đánh giá nhiều lượt

Xem [hướng dẫn đánh giá](mao_dialogue_evaluation.vi.md). Tám tình huống/22 lượt kiểm tra logic đã đạt; phép thử model local với và không có chỉ dẫn theo lượt chạy tổng 44 lượt, không lỗi contract, có bốn lượt được heuristic đánh dấu để đọc lại. Đây chưa phải đánh giá chất lượng độc lập hoặc chứng minh cải thiện. Dữ liệu evaluator trong database test đã được dọn; kiểm tra số hàng còn lại trong events/knowledge/focus bằng 0.

Đợt sửa tiếp theo sau nghiên cứu đã hoàn thành: [bằng chứng, thiết kế và kết quả bản cuối](mao_dialogue_grounding_research.vi.md). Thêm đọc ký ức có nguồn, trích nguyên văn có giới hạn, lọc lời hỏi/thúc kể trước TTS và tính số học đơn giản độc lập với lời assistant cũ. Bản cuối kiểm tra 82 lượt trên ba bộ, không lỗi contract; 560 bài Python/PostgreSQL có 550 đạt và 10 bỏ qua theo điều kiện. Các giới hạn còn lại và cờ báo nhầm được giữ trong báo cáo; không thay persona hoặc tự bật policy promotion.

## Lộ trình tiếp theo

| Thứ tự | Công việc | Điều kiện đánh giá |
|---|---|---|
| 1 | Đánh giá hội thoại thật trên cùng model/persona, trước và sau cải thiện | Kiểm tra nghe đúng nhu cầu, hỏi lặp, lời khuyên không được yêu cầu, sửa hiểu lầm và độ trễ; có người đánh giá lời thoại thực tế |
| 2 | Focus nhiều lượt và yêu cầu yên tĩnh có phạm vi | Không thay topic bằng “ừ/vẫn vậy”; nhường lời đúng người/phòng; yêu cầu yên tĩnh chặn đề xuất nền và có cách tiếp tục rõ ràng; xóa nguồn không để trạng thái cũ tồn tại |
| 3 | Ký ức về chuyện dang dở và thông tin đã sửa | Tiếp nối đúng chuyện qua restart; không dùng thông tin đã bị thay; không gộp hai người hoặc coi chuyện hư cấu là tiểu sử; thiếu nguồn thì nói chưa chắc |
| 4 | Giọng, nhịp và biểu cảm | Đo ASR/VAD/audio đầu trên microphone thật; nghe kiểm tra ngữ điệu; ngắt lời không phát lại phần cũ; đánh giá đồng bộ avatar |
| 5 | Tăng chiều sâu hoạt động và học có bằng chứng | Wesnoth được đánh giá nhiều trận cùng điều kiện; kiểm tra rủi ro đội trưởng, lượt bỏ phí và kết quả; chỉ kết luận tiến bộ sau so sánh độc lập |

Chưa nên mở tự thay persona hoặc tự nâng chính sách từ vài lời tự nhận xét. Nên giữ quyền sửa/quên dữ liệu rõ ràng và tách kiểm thử khỏi Mao thật.

## Bộ tình huống nghiệm thu hội thoại

- “Hôm nay papa mệt, chỉ muốn kể thôi” → phản hồi ngắn theo điều vừa nghe, không tự đưa danh sách giải pháp.
- “Vẫn vậy” ngay sau đó → tiếp nối đúng mạch; không tự bịa nguyên nhân hoặc nói papa đã vui hơn.
- “Cho papa ba cách xử lý” → chuyển sang đáp yêu cầu hiện tại.
- “Ý papa là đổi giờ hẹn, không phải hủy” → dùng ý đã làm rõ, không hỏi lại thông tin vừa được nói.
- “Mao hiểu sai rồi” khi chưa rõ sai ở đâu → hỏi một câu cụ thể, không nhận mọi sửa đổi thành sự thật.
- “Ổn rồi, đổi chủ đề nhé” → theo mạch mới; “đừng đổi chủ đề” không được hiểu thành yêu cầu chuyển chủ đề.
- Trích dẫn, kể chuyện hư cấu, người khác hoặc phiên khác → không mang nhu cầu cá nhân cũ sang.

Kiểm thử tự động kiểm tra lựa chọn chỉ dẫn, phạm vi lịch sử, reset từng lượt và ngân sách context. Chúng chưa chấm chất lượng lời model tạo ra, tiếng nói hoặc cảm nhận của người dùng. Kết quả tổng được lưu ở `logs/mao-dialogue-intent-tests.log`.
