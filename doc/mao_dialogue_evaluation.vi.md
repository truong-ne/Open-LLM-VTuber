# Đánh giá hội thoại nhiều lượt của Mao

Ngày tạo: 03/11/2026. Bộ thử gồm tám tình huống và 22 lượt đánh giá, cộng một lượt dựng sẵn cho tình huống sửa hiểu lầm. Fixture có version và hash: `tests/fixtures/mao_dialogue_multiturn.vi.json`.

## Phạm vi

Runner dùng Journal, Focus, Experiences, scoped context và response guidance thật trên database test riêng. Mỗi tình huống và mỗi nhánh so sánh dùng scope ngẫu nhiên; dữ liệu được xóa khi kết thúc. Lời người dùng là fixture giả lập, có visibility `test`; event đi qua nhánh input thông thường (không phải rehearsal) để kiểm tra hành vi thật của Focus. Không có worker học/chính sách production chạy trong scope này.

`--live` đọc persona đang hoạt động vào bộ nhớ, gửi dữ liệu giả lập tới model local đang cấu hình, rồi lưu **câu trả lời thực tế** vào báo cáo. Không sao chép persona vào database test hoặc báo cáo; chỉ ghi digest. Không dùng model judge để tự tuyên bố chất lượng tốt hơn. Prompt và trạng thái mỗi lượt được dựng lại từ database; cờ `restart` đổi session và kiểm tra khả năng tiếp nối mà không dùng danh sách hội thoại riêng trong Python. Đây không phải thử kill/restart process backend thật.

Phần ghi nhớ/cập nhật/quên được runner thực hiện theo fixture có nguồn; đây là kiểm tra retrieval và phản hồi từ context, không kiểm tra model tự gọi công cụ memory. Embedding được tắt có chủ đích để dùng lexical fallback. Công cụ, ASR, TTS, avatar và microphone nằm ngoài phạm vi. ACK là sink text giả lập, không xác nhận đã phát âm thanh hoặc người dùng đã nghe.

## Chạy

Chuẩn bị database test theo runbook, rồi:

```powershell
# Kiểm tra logic và database; không sinh câu trả lời model
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --output logs/mao-dialogue-contracts.json

# Chạy cùng model/persona với và không có chỉ dẫn theo lượt: 44 lượt đánh giá
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --live --guidance both --output logs/mao-dialogue-live-eval.json

# Chạy riêng tình huống để điều tra lỗi
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --live --scenario listen_then_request_help --output logs/mao-dialogue-listen-eval.json
```

Runner từ chối DSN test trùng production, yêu cầu migration 010 ở database test, giới hạn endpoint model về localhost và không có công cụ thực thi bên ngoài. Profile production chỉ được đọc trước khi chuyển tất cả thao tác ghi sang database test. Báo cáo JSON và Markdown cùng tên được tạo trong `logs/`.

`--guidance both` là phép so sánh bỏ/bật riêng chỉ dẫn theo lượt; các thành phần context và bộ nhớ khác vẫn giữ nguyên. Hai nhánh có cùng fixture, model và persona; temperature 0.2, giới hạn 384 output token. Không có bảo đảm tái lập từng từ vì không cố định seed. Một lượt cho mỗi điều kiện chỉ đủ tìm lỗi, chưa phải chứng minh cải thiện có ý nghĩa thống kê.

## Cách đọc kết quả

| Lớp | Nội dung | Có thể kết luận |
|---|---|---|
| Contract | Mode đúng kỳ vọng, trạng thái quiet đúng, không lộ nguồn đã quên hoặc dữ liệu actor khác trong context | Logic thành phần đã qua các tình huống cụ thể |
| Kiểm tra đầu ra | Rỗng, nhiều dấu hỏi, quá dài, thiếu từ cần có hoặc xuất hiện chuỗi bị cấm | Có điểm cần người kiểm tra; heuristic có thể báo nhầm hoặc bỏ sót |
| Đánh giá người đọc | Đúng ý, lắng nghe, sửa hiểu lầm, nhớ đúng, tự nhiên: 1–5 hoặc N/A | Chất lượng trong mẫu đã đọc, có ghi lý do |

`quality_improvement_verified` luôn false trong báo cáo tự động; các mục chấm người đọc ban đầu là null. Không tính “không có cờ” thành điểm hài lòng. Dấu hỏi trong lời trích vẫn có thể tạo cờ; từ khóa xuất hiện không chứng minh câu trả lời đúng nghĩa. Lỗi HTTP hoặc output bị cắt được ghi riêng, không giả thành câu trả lời thành công.

Bộ này hiện là tập phát triển, không phải held-out. Sau mỗi lần sửa cần bổ sung các cách diễn đạt mới vào tập kiểm tra độc lập và đánh giá mù nhiều mẫu trước khi kết luận tốt hơn.

## Bản sửa sau nghiên cứu

Chi tiết thiết kế, nguồn nghiên cứu và giới hạn ở [mao_dialogue_grounding_research.vi.md](mao_dialogue_grounding_research.vi.md). Runtime và evaluator dùng chung đường trích nguồn cho self-recall đơn giản, bộ lọc lượt nghe và phép tính xác định. Không coi mọi câu trả lời ở chế độ live là câu do LLM tạo: `response_origin` ghi riêng `scoped_quote`, `exact_arithmetic`, `model`, `model_filtered` và `listening_fallback`.

Báo cáo mới giữ `raw_response`/`raw_heuristic_flags` cùng đầu ra sau lọc và số lần fallback. Grader phiên bản 3 kiểm tra cả yêu cầu kể thêm và trường hợp có chứa chuỗi đáp án nhưng lại phủ nhận ký ức; một số câu hỏi thật về quyền/persona được miễn cờ tự giải thích hệ thống. So sánh kết quả cũ/mới phải chấm lại bằng cùng grader, không so trực tiếp tổng cờ của hai phiên bản grader khác nhau.

Chạy bản cuối với tên file mới để giữ mốc ban đầu:

```powershell
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --live --repeat 2 --output logs/mao-dialogue-final-development.json
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --live --fixture tests/fixtures/mao_dialogue_holdout.vi.json --repeat 2 --output logs/mao-dialogue-final-regression.json
.\.venv\Scripts\python.exe scripts/mao_dialogue_eval.py --live --fixture tests/fixtures/mao_dialogue_confirmation.vi.json --repeat 2 --output logs/mao-dialogue-final-confirmation.json
```

Lưu ý: file có tên `holdout` đã được dùng để phát hiện và sửa lỗi số học, nên các lần chạy sau là kiểm thử hồi quy, không phải held-out độc lập. Bộ `confirmation` là tập mới ở đợt sửa này. `--repeat 2` tạo scope mới cho mỗi lần; metadata `new_session` chỉ thay phiên trong database, không mô phỏng crash process.

## Database đang dùng

Migration 010 đã được áp dụng trên database test và database Mao. Báo cáo `logs/mao-attention-migration.json` xác nhận schema 10, runtime role đọc được cột mới, digest persona và số bản ghi memories/knowledge/events trước/sau không đổi. Không tạo bản sao transcript hoặc persona. Backend cần khởi động lại để nạp thay đổi Python nếu đang chạy bản cũ.

## Kết quả lần chạy đầu

- Logic/database: 22 lượt, không lỗi contract.
- Model `mao-companion`, hai điều kiện: 44 lượt, không lỗi contract hoặc request; bốn lượt được đánh dấu để đọc lại (ba ở nhánh tắt guidance, một ở nhánh bật). Không dùng chênh lệch này làm kết luận cải thiện vì mỗi tình huống chỉ có một mẫu và heuristic rất hẹp.
- Toàn bộ suite với PostgreSQL: 545 bài, 535 đạt, 10 bỏ qua theo điều kiện; không failure/error. Các bài mới của attention đều đã chạy trên DB thật.
- Kiểm tra sau chạy: không còn hàng evaluator trong interaction_events, knowledge_items hoặc dialogue_focus của database test. Database production không chứa lượt thử này.

Quan sát từ lời model: nhánh bật chỉ dẫn giảm câu hỏi ở một số lượt lắng nghe, nhưng vẫn nói “Kể tiếp đi” thay vì chỉ tiếp nhận. Model tự giới thiệu/giải thích mình là AI dài dòng ở nhiều lượt, thay đổi cách xưng hô giữa “Mao”, “mình”, “em”, “tôi”, và ở `actor_isolation` đã từ chối nhắc biệt danh cho đúng actor dù nguồn có trong context. Cũng có phát biểu kiến thức về mèo cần kiểm chứng riêng; bộ từ khóa hiện chưa chấm tính đúng của kiến thức. Các quan sát này không phải điểm đánh giá tâm lý hoặc xác nhận sở thích của người dùng.

Ưu tiên sửa tiếp theo: phân biệt claim có nguồn với việc thiếu ký ức, giảm tự giới thiệu và thuật ngữ hệ thống trong lời thoại, giữ cách xưng hô theo profile, và bổ sung đánh giá nội dung/ngữ nghĩa thay vì chỉ đếm dấu hỏi. Giữ báo cáo đầu làm mốc; dùng tên output mới khi chạy phiên bản đã sửa.
