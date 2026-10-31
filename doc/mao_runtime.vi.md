# Mao runtime M1–M7

Ngày cập nhật: 29/10/2026. Các module và đường tích hợp M1–M7 đã được triển khai. Trạng thái nghiệm thu lấy từ báo cáo kiểm thử; việc có code không đồng nghĩa đã đạt gate phiên thật hoặc SLO vận hành.

| Mốc | Đường chạy đã có |
|---|---|
| M1 | Actor proof do host cấp; host proposal có chữ ký riêng; event dedup; journal/turn/outbox chung transaction; turn/segment/epoch; ACK thật từ Audio; phục hồi unknown; khóa một backend mỗi scope. |
| M2 | Queue 20, ưu tiên/aging/deadline, direct input thay đề xuất nền đang đợi, floor chung cho single/group, interrupt/disconnect, shadow và fallback có báo từ chối rõ ràng. |
| M3 | Episode theo actor/room/visibility/session; knowledge có nguồn, hiệu lực và phiên bản; lọc scope trước retrieval; vector + lexical; context budget; sửa/quên/retention và chống tạo lại từ nguồn đã xóa. |
| M4 | Focus có expiry, câu hỏi đang chờ, tín hiệu sửa hiểu nhầm, open thread; shared story có canon hư cấu, revision, expiry và action idempotency; chuyện public chỉ chia sẻ trong phòng. |
| M5 | Core/affect/preferences/development tách riêng; affect theo actor/phòng/visibility, appraisal có ngữ cảnh ngắn đã phát; choice/evidence/counterexample; ít nhất 3 episode qua 2 session; áp yêu cầu hiện tại và ranh giới rõ ràng trước nét đang thử; khóa/bỏ nét qua UI. |
| M6 | Lesson/candidate, 40 development + 20 held-out, trial tối đa 20 lượt, feedback có nguồn và kiểm tra SQL, promotion/rollback; không nhận scalar làm bằng chứng phiên thật. |
| M7 | Dashboard, metrics theo text/voice và first-use/warm, source inspector, kiểm thử lỗi, baseline, soak runner, launcher và dừng server có xác thực host. |

Lõi persona trong `character_profiles` vẫn chỉ đọc đối với runtime role. Migration bổ sung không nhập lại ký ức cũ. Báo cáo xác minh ở `logs/mao-runtime-migration.json` chỉ chứa digest/count, không chứa bản sao persona hoặc ký ức.

### Nghiệm thu cập nhật 31/10/2026

Soak tại `logs/mao-contextual-soak.json` đã đạt 7200,09 giây, 80 lượt và source không đổi, không ghi nhận lỗi. Đối chiếu PostgreSQL: cả 80 lượt completed, 131 đoạn audio completed, không có lượt speech recovery. Backend test đã tự dừng qua lifecycle sau bài chạy. Đây là WebSocket/LLM/TTS thực với player giả lập, chưa phải nghiệm thu microphone hoặc người thật nghe audio.

Trong tập lượt text/kể chuyện hỗn hợp đó, first-audio p50 là 3453 ms và p95 là 8157 ms. RSS tổng process tree cuối bài giảm khoảng 1,94 GiB so với mẫu warm thứ sáu; database tăng 360448 byte. Đây là quan sát của workload, không phải cam kết latency hoặc chứng minh không có memory leak.

Đã thu riêng 101 mẫu mỗi modality (100 warm), tổng cộng 202 lượt completed, không lỗi hoặc ASR báo không rõ; bài hủy sau audio đầu đạt interrupted và không nhận playback-completed. Báo cáo `logs/mao-warm-latency.json` và tổng hợp `logs/mao-warm-latency-summary.json`. Token probe giữ native-provider/tool routing và có bài kiểm thử riêng. Mẫu lịch sử chỉ có một warm observation mỗi modality, với probe cũ làm thay đổi routing, nên chưa đủ cơ sở kết luận gate p95 tăng không quá 15%. Trạng thái tổng hợp ở `logs/mao-contextual-validation.json`.

| Warm, 100 mẫu mỗi loại | ASR hoàn tất p50 / p95 | Token đầu p50 / p95 | Audio đầu p50 / p95 |
|---|---|---|---|
| Text | Không áp dụng | 765 / 766 ms | 1469 / 1656 ms |
| Voice fixture | 3937 / 3985 ms | 4750 / 4906 ms | 5266 / 6438 ms |

Các mốc tính từ khi nhận input; voice đã là buffer audio có sẵn, không đo thời gian người nói hoặc microphone/VAD. Đây là fixture cố định và playback giả lập. First-use chỉ có một mẫu mỗi loại, không phải model cold start hay phân phối p95. Các bài runtime chưa thay đổi sau soak. Phần còn lại cần người dùng nghiệm thu theo [checklist phiên thật](mao_acceptance_2026-10-31.vi.md).

## Chạy và dừng

```powershell
./scripts/start_mao_local.ps1 -Profile local_companion -Doctor
./scripts/start_mao_local.ps1 -Profile local_companion
```

Chat: `http://127.0.0.1:12393/`. Dashboard: `http://127.0.0.1:12395/mao-5070/runtime.html`. Launcher mở helper dashboard nếu port còn trống; có thể bỏ bằng `-NoDashboard`. Nó không bật adapter live mặc định.

Frontend đóng gói nhận delivery bridge qua HTML do server phục vụ; không sửa JavaScript minified của frontend. Desktop Draco nhận hook qua `node scripts/build_draco_shell.mjs`. Nạp lại trang hoặc khởi động lại desktop sau khi cập nhật. Audio vẫn phát khi avatar chưa sẵn sàng; lỗi `play()` được ghi là failed.

```powershell
.venv/Scripts/python.exe scripts/mao_control.py stop --profile local_companion --dashboard
```

Lệnh dùng host secret và dừng Uvicorn qua lifecycle. Actor token/nickname không có quyền dừng server hay sửa core. Ollama và PostgreSQL là dịch vụ riêng; lệnh dừng backend không kill process không liên quan.

## Cấu hình và rollback

Các cờ dưới `character_config.agent_config.agent_settings.basic_memory_agent.hybrid`:

```yaml
interaction_enabled: true
coordinator_enabled: true
coordinator_shadow: false
emotion_enabled: true
auto_policy_promotion: false
```

Đổi cờ rồi khởi động lại backend. `coordinator_shadow: true` giữ đường queue cũ để đối chiếu; `coordinator_enabled: false` tắt điều phối mới nhưng vẫn giữ journal của M1. `interaction_enabled: false` quay về đường legacy và các đặc tính lưu trữ của đường đó.

`learning_enabled` điều khiển worker DailyLearning cũ. Khi interaction mới bật, ExperienceWorker thay worker đó; thu thập candidate không tự cấp quyền promote. `auto_policy_promotion` mặc định tắt. Operator có thể đánh giá, trial, promote khi đủ bằng chứng, hoặc rollback tại dashboard.

Bản đầu giữ một policy đang áp dụng cho mỗi actor/phòng và thử một chiều giao tiếp trong mỗi candidate từ baseline cố định. Những chiều hiện có: độ dài, mức chủ động, ví dụ, hài hước. Nó không tự sinh code/skill thực thi hoặc thay lõi. Bộ 40/20 hiện kiểm tra hợp đồng/controller; điểm này không chứng minh chất lượng hội thoại hay sở thích tâm lý. Gate feedback thật vẫn bắt buộc.

## Dữ liệu và nguồn

- Private chỉ vào context của đúng actor/phòng; public claim có nhãn publisher và vẫn chưa được xác minh. Nickname không chứng minh danh tính hoặc quyền.
- Public story có thể tiếp tục bởi người khác trong cùng phòng. Fiction được lưu riêng khỏi factual knowledge.
- Completed xác nhận trình phát báo xong; không xác nhận con người đã nghe, đồng ý hay thích. ACK thiếu/sai epoch không biến generated thành delivered.
- Canon và delivery được chốt trước tín hiệu kết thúc lượt; disconnect không cắt ngang transaction chốt, và output muộn của lượt đã kết thúc bị bỏ.
- Sửa một item tạo revision và giữ nguồn gốc ban đầu. Quên nguồn xóa các dẫn xuất đã liên kết, gỡ style liên quan, giữ tombstone để replay không nhập lại dữ liệu đó.
- Working memory của đường mới được dựng lại từ scoped context và các đoạn đã xác nhận phát; summary cũ bị vô hiệu hóa bằng generation khi reset.
- Journal raw và text phát được redacted sau 30 ngày; metrics 7 ngày; episode 90 ngày; knowledge thường 180 ngày, tạm thời 1 ngày. Focus 10 phút, open thread 7 ngày. Story action hết hạn sau 7 ngày, bản lưu quá hạn được dọn theo retention.
- Redact raw theo tuổi khác với yêu cầu quên: memory còn hiệu lực vẫn có thể tồn tại cùng evidence ID. Yêu cầu quên xử lý graph nguồn.
- Retention chạy khi worker khởi động và theo giờ trong lúc backend hoạt động; nếu backend tắt, việc dọn tiếp tục khi khởi động lại.

Dashboard yêu cầu token local và kiểm tra Host/Origin. Nội dung nguồn được render bằng text, không thực thi HTML. Sửa dùng expected revision; xung đột trả 409 để đọc lại. Các báo cáo/metrics mới không xuất transcript, DSN hoặc credential.

## Kiểm thử và vận hành

DB test dùng file `private/mao-test.env`, database `mao_test` ở port 55433, tách khỏi DB chính port 55432. Nếu chưa có file, tạo một lần bằng `scripts/mao_test_db.py init-env`; không ghi đè credential đang có.

```powershell
docker compose --env-file private/mao-test.env -f compose.mao-test.yaml up -d
.venv/Scripts/python.exe scripts/mao_test_db.py migrate
.venv/Scripts/python.exe scripts/mao_test.py --postgres
node --test tests/delivery_client.test.mjs
.venv/Scripts/python.exe scripts/mao_runtime_eval.py --output logs/mao-policy-eval.json
```

Baseline text/voice thực với Qwen, ASR và VieNeu/RVC; sink giả lập thời lượng phát và được ghi nhãn rõ:

```powershell
.venv/Scripts/python.exe scripts/mao_baseline.py --samples 2 --output logs/mao-runtime-baseline.json
```

Soak WebSocket thực, fixture kể chuyện/đổi chủ đề, playback simulator, actor resume + chống phát lặp, RAM process tree và kích thước DB:

```powershell
./scripts/start_mao_local.ps1 -Profile test
.venv/Scripts/python.exe scripts/mao_soak.py --seconds 7200 --interval 90
```

Thêm `--stop-server` khi runner sở hữu backend test và cần dừng nó lúc kết thúc. Runner chỉ gửi input sau khi handshake xác nhận đúng profile/scope test. Dưới 7200 giây là smoke, không phải soak 2 giờ; sửa source giữa chừng làm gate code-unchanged không đạt. Trạng thái được cập nhật ở `logs/mao-soak-runtime.json`.

Các báo cáo hiện có: `mao-full-tests.log`, `mao-architecture-tests.log`, `mao-policy-eval.json`, `mao-browser-delivery.json`, `mao-runtime-baseline.json`, `mao-soak-runtime.json` trong `logs/`. Browser report phân biệt ACK từ AudioElement với việc con người nghe được. Máy test không có microphone cho VAD của browser; ASR được kiểm tra bằng audio fixture.

Gate soak đủ thời lượng trên source ổn định đã đạt ở bản ghi trên. V1 còn cần đánh giá mẫu warm/p95 và SLO với tham chiếu phù hợp, phiên người dùng thật và thử từng adapter live. Không sử dụng điểm fixture hoặc một smoke ngắn để tuyên bố đã đạt các gate này.

Nếu mất kết nối: turn đang chạy trở thành interrupted/unknown; restart không phát lại audio. Nếu một backend đã giữ scope, backend thứ hai bị từ chối trước recovery. Nếu không có ACK đoạn, kiểm tra bridge và reload client; không sửa status thành completed bằng tay. Với DB/provider lỗi, xem mã lỗi và worker health; không khôi phục dữ liệu đã quên từ log hoặc bản sao.

Soak 30/10/2026 phát hiện một lượt nhận token nhưng không tạo được speech sau khoảng 52 phút (35 lượt trước đó có audio); bài này không đạt 2 giờ. DialogueEngine đã được bổ sung kiểm tra sau bộ lọc sentence/tag/TTS: bỏ đoạn chỉ có ký hiệu, thử lại một lần nếu agent không dùng công cụ và chưa tạo speech/event, báo `empty-agent-reply` nếu vẫn rỗng. Không phát lại lượt đã có speech, có tool event, lỗi provider hoặc bị hủy. Lỗi được journal ghi là failed, không completed. Full suite sau sửa: 467 bài, 457 đạt, 10 bỏ qua theo điều kiện; trong đó có 7 bài mới kiểm tra retry, đóng stream, giới hạn câu, cancellation và pipeline tag/TTS thực.

Lần soak kế tiếp dừng sau 361 giây: hybrid luôn bật tool nội bộ, nên guard bảo thủ ở bản sửa đầu không thực hiện retry. Đã bổ sung `BasicMemoryAgent.recover_silent_reply`: một lượt sinh lời thoại riêng, không truyền tool schema và không vào tool loop. Chỉ dùng khi lượt đầu chưa có speech, lỗi hoặc tool event; không phát lại thao tác đã chạy. Lượt phục hồi có chỉ dẫn host yêu cầu câu hoàn chỉnh thay vì chỉ thẻ/emoji; vẫn báo failed nếu không có speech. Kiểm thử native-tool pipeline xác nhận lần đầu có schema tool, lần phục hồi không có và executor không được gọi. Full suite mới nhất: 468 bài, 458 đạt, 10 bỏ qua theo điều kiện. Soak runner ghi thêm mã lỗi có giới hạn và metadata lượt lỗi, không lưu nội dung câu chat vào report.
