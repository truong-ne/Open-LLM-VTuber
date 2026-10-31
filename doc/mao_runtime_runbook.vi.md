# Chạy và kiểm chứng nền runtime Mao (M0)

Các lệnh dưới đây chạy từ thư mục gốc dự án, trong PowerShell. Các công cụ không sao lưu hoặc nhập lại ký ức cũ. Báo cáo chỉ chứa cấu hình được chọn lọc, số đo và loại lỗi; không chứa transcript, DSN hoặc API key.

## Profile của tiến trình backend

| Profile | Hành vi |
|---|---|
| `local_companion` | Chỉ bind loopback, nguồn live local; giữ MCP đã cấu hình; tắt autonomy, computer, exploration, daily learning |
| `local_dev` | Như local_companion, thêm tắt MCP |
| `test` | Như local_dev, port 12394, persona giả lập, DB test, scope và history ID riêng |
| `live` | Giữ cấu hình operator, không tự bật tính năng hoặc khởi động adapter |

Overlay áp dụng khi validate cấu hình, kể cả đổi character trong phiên. Không đặt profile thì entry point cũ giữ hành vi đã cấu hình. Profile không quản lý các tiến trình idle/research/live đã được chạy riêng; cần dừng chúng riêng khi muốn một phiên yên lặng.

Kiểm tra môi trường:

```powershell
.venv/Scripts/python.exe scripts/mao_doctor.py --profile local_companion --output logs/mao-doctor.json
```

Doctor chỉ đọc: ports, process names/PID trên Windows, GPU, danh sách model/digest Ollama local, migration trong transaction read-only. Không khởi động dịch vụ hay chạy migration. Exit 1 khi DB/model cần thiết chưa sẵn sàng. Nguồn provider ngoài loopback được báo skipped, không tự gửi request.

Chạy backend local ở foreground; Ctrl+C để dừng:

```powershell
./scripts/start_mao_local.ps1
# Hoặc:
.venv/Scripts/python.exe run_server.py --profile local_dev
```

Launcher khởi động Ollama từ `private/tools/ollama/ollama.exe` nếu port 11434 chưa mở, lưu PID vào `private/ollama.pid`; provider tiếp tục chạy sau khi server dừng. Nếu đã có server trên port đích thì launcher từ chối tạo server thứ hai. Không chạy live adapter hoặc idle host. Cần model đã cài và PostgreSQL production đang chạy nếu hybrid bật. Với bản cài hiện tại, có thể khởi động DB thật bằng `docker compose -f compose.mao-hybrid.yaml up -d --wait`; lệnh này không phải bước bắt buộc để chạy bộ test riêng.

## Database và dữ liệu kiểm thử riêng

Tạo credentials riêng (chạy một lần, từ chối ghi đè file có sẵn), container PostgreSQL riêng ở port 55433 và database `mao_test`:

```powershell
.venv/Scripts/python.exe scripts/mao_test_db.py init-env
docker compose -f compose.mao-test.yaml up -d --wait
.venv/Scripts/python.exe scripts/mao_test_db.py migrate
.venv/Scripts/python.exe scripts/mao_test.py --postgres
```

File `private/mao-test.env` bị Git ignore. Runtime dùng role `mao_app`; migration dùng role `mao_owner`. Test runner kiểm tra cả hai DSN, từ chối database không có hậu tố `_test`, thiếu host/port/dbname, endpoint nhiều host/service hoặc trùng endpoint/database production kể cả khác role/password và tên loopback. Production được so sánh qua cấu hình hiện hành và file credentials gốc; kiểm tra không kết nối DB thật.

Chạy test không DB:

```powershell
.venv/Scripts/python.exe scripts/mao_test.py
```

Runner in riêng số skipped, failures, errors. Không diễn giải skip thành pass kiểm thử tích hợp. Dùng `--pattern test_mao_runtime.py` để chạy riêng kiểm tra profile và cách ly. Store cũng chặn fallback sang DB thật khi các cờ integration hoặc profile test đang bật. Cơ chế này ngăn kết nối nhầm thông thường, không phải sandbox cho mã test tùy ý.

## Baseline text, voice và cancellation

```powershell
$env:HF_HOME = Join-Path (Get-Location) 'models'
$env:HF_HUB_OFFLINE = '1'
$env:PATH = (Join-Path (Get-Location) 'private/tools/ffmpeg/ffmpeg-master-latest-win64-lgpl-shared/bin') + ';' + $env:PATH
.venv/Scripts/python.exe scripts/mao_baseline.py --samples 2
```

Model Ollama, embedding, ASR, TTS và tài nguyên giọng hiện cấu hình cần có sẵn. Không tự tải model. Corpus có version tại `tests/fixtures/mao_baseline_v1.json`; chỉ chứa dữ liệu giả lập. Runner dùng ServiceContext, agent, ASR, TTS/RVC và single-conversation pipeline thật, không khởi động server HTTP. Voice đầu vào được tạo từ câu cố định bằng TTS, resample mono 16kHz rồi đưa vào ASR; không dùng microphone hoặc ghi âm cá nhân. History không được ghi, working memory được xóa giữa các mẫu; hybrid chỉ dùng DB test.

Báo cáo mặc định `logs/mao-baseline.json` gồm startup, môi trường/model/digest, corpus digest, sample size, thời gian ASR/token/audio đầu, synthesis hoàn tất, lỗi và cancellation. Một lượt bổ sung hủy sau gói audio đầu để kiểm tra đường cleanup. `first_use` là lần đầu của modality trong tiến trình đo; không đồng nghĩa model cold start. Chỉ số âm thanh là **sink giả lập** dựa trên độ dài WAV: không đo thiết bị phát, browser, microphone hoặc mạng. Không lấy mẫu nhỏ này làm SLO p95 production.

Nghiệm thu M0 đầy đủ còn cần một phiên với frontend và thiết bị thật để xác nhận text, microphone, phát và ngắt lời. M1–M7 tiếp tục theo kế hoạch kiến trúc; công cụ M0 không tự mở các module học/cá tính mới.

Dừng DB test khi không dùng:

```powershell
docker compose -f compose.mao-test.yaml stop
```

Giữ volume test để chạy lại; công cụ không tự xóa hoặc tạo backup dữ liệu.

## Kết quả trên máy local ngày 29/10/2026

379 bài test: 369 đạt, 10 skipped, không failure/error khi bật PostgreSQL riêng. Lint và format Python, parse cú pháp launcher PowerShell và entry point `run_server.py --help` đã đạt.

Baseline dùng RTX 5070, model `mao-companion`, embedding `qwen3-embedding:0.6b`, ASR faster_whisper và VieNeu/RVC hiện cấu hình. Khởi tạo context khoảng 57,88 giây. Hai mẫu cho mỗi modality, một lượt cancellation; không lỗi và ASR không báo uncertain.

| Mẫu warm | ASR xong | Token đầu từ lúc nhận input | Audio đầu từ lúc nhận input |
|---|---:|---:|---:|
| Text | Không áp dụng | 484 ms | 3312 ms |
| Voice giả lập | 3953 ms | 4484 ms | 5078 ms |

Hủy sau audio đầu thành công, không ghi nhận playback hoàn tất cho lượt bị hủy. Số đo là quan sát của mẫu cụ thể, không đại diện phân phối latency. Xem chi tiết tại `logs/mao-baseline.json`; bộ test cuối tại `logs/mao-m0-tests-final.log`. Các báo cáo nằm trong thư mục bị Git ignore. Thiết bị phát/microphone và frontend thực tế vẫn cần nghiệm thu riêng.
