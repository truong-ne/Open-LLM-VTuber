# Giọng Mao đã train — tích hợp ngày 31/10/2026

`conf.yaml` đã chọn checkpoint `../Mao-TTS/outputs/cold-queen-emotion-332-20261028/merged`, tương ứng bản nghe thử người dùng chấp nhận: 332 mẫu, metadata 102 bước train, VieNeu v3 Turbo 48 kHz. Đây không phải bản 478 mẫu đang có metadata encoding cũ. Không chạy train thêm hoặc đổi persona/ký ức.

Mẫu cấu hình có thể tái sử dụng nằm ở `config_templates/mao.trained-voice.yaml`; ghép dưới `character_config.tts_config`. Các đường dẫn tương đối được tính từ thư mục gốc Open-LLM-VTuber. Giữ thư mục checkpoint và môi trường `Mao-TTS/.train-venv` tồn tại, hoặc cập nhật hai đường dẫn khi di chuyển.

## Đường tổng hợp

Mao vẫn dùng provider `vieneu_tts`. Khi `trained_voice.enabled: true`, adapter sử dụng worker Python riêng trong môi trường đã tạo mẫu nghe thử, nạp đúng local checkpoint bằng backend PyTorch. Khởi tạo cấu hình chỉ kiểm tra đường dẫn/JSON; worker và model chỉ được nạp khi có câu đầu tiên cần đọc. Worker được giữ giữa các câu để không nạp lại model liên tục.

Giữ cấu trúc tổng hợp của mẫu đã nghe: embedding `Cold Queen · neutral`, prefix token đã train trên từng đoạn, `use_ref_codes: false`, temperature 0,7, tốc độ nền 1,0×. Không đưa giọng mới qua RVC Linh Lan; RVC trong cấu hình đã tắt. Khi lỗi, báo thất bại thay vì âm thầm quay về giọng khác. Timeout đóng worker để audio đến muộn không bị dùng cho câu tiếp theo; Windows timeout kết thúc cây tiến trình worker do adapter tạo.

`emotion_control: false` là lựa chọn ban đầu để dùng đúng nhãn neutral đã được nghe thử. Điều tiết tempo, khoảng nghỉ và native cues hiện có vẫn hoạt động. Các nhãn cảm xúc đã train khác là thử nghiệm; chỉ bật `emotion_control` sau khi nghe/đánh giá thêm. Khi bật, warm/bright/playful có thể chọn happy và solemn chọn sad; các mood còn lại giữ neutral.

## Kiểm chứng đã làm

- 37 bài kiểm thử TTS/worker/prosody đạt, dùng model giả lập, PCM nhỏ và ffmpeg CPU; báo cáo `logs/mao-trained-voice-regression.log`.
- Kiểm tra cấu hình đầy đủ, đường checkpoint và factory truyền `trained_voice` đúng; chặn `subprocess.Popen` trong bước kiểm tra đường dẫn để bảo đảm không khởi tạo worker.
- Kiểm tra prefix ở mọi chunk, không dùng reference codes, không nạp base model/RVC, đóng worker khi timeout và không nhận nhầm phản hồi muộn.

Ở bước tích hợp ban đầu, theo yêu cầu người dùng, không chạy Mao hoặc nạp checkpoint trên GPU để test tích hợp. Sau đó người dùng yêu cầu bật Mao với desktop mới. Phiên chạy thật phát hiện `HF_HOME` của Mao khác cache của Mao-TTS, khiến bộ giải mã MOSS không được tìm thấy; đã bổ sung `trained_voice.codec_path` trỏ đến snapshot local có sẵn, không tải lại model. Trường này có thể để trống nếu bộ giải mã nằm trong cache hiện hành.

Chưa đo chất lượng/độ trễ toàn pipeline của cấu hình mới; kết quả soak/p95 trước đây thuộc cấu hình giọng VieNeu + RVC cũ, không được coi là nghiệm thu giọng mới.

Phiên Mao Studio sau khi sửa cache đã tạo WAV qua worker thật và desktop báo 15 segment bắt đầu, 14 kết thúc, 0 lỗi audio tại thời điểm kiểm tra. Đây là bằng chứng tổng hợp/phát qua ứng dụng, không phải đánh giá nghe của người dùng hoặc phép đo p95.

## Sử dụng

Theo yêu cầu tiếp theo, tốc độ đọc nền trong `conf.yaml` và template là `1.1` (nhanh hơn 10%). Dùng bộ lọc ffmpeg `atempo` giữ cao độ, không thay checkpoint; điều tiết prosody hiện có tiếp tục nhân với tốc độ nền này. Bốn kiểm thử tốc độ đã đạt (`logs/mao-livestream-speed-test.log`).

Lần bật Mao tiếp theo sẽ chọn giọng mới. Câu đầu tiên có thêm thời gian nạp checkpoint; chưa đo thời gian này. Đóng cửa sổ desktop chưa chắc đã dừng backend; nếu cần giải phóng model/GPU, dừng backend:

```powershell
.venv/Scripts/python.exe scripts/mao_control.py stop --profile local_companion --dashboard
```

Để quay về cấu hình cũ: tắt `trained_voice.enabled`, đặt voice `Mỹ Duyên`, backend `onnx`, device `cpu`, temperature `0.8`, speed `1.08`, bật lại `rvc.enabled` với các đường Linh Lan hiện có, rồi khởi động lại backend. Không có thay đổi nào vào model gốc hoặc dữ liệu train.
