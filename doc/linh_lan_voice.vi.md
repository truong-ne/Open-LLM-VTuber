# Giọng Linh Lan Ch — 19/10/2026

Mao dùng VieNeu v3 Turbo tạo lời Việt, sau đó RVC đổi chất giọng sang Linh Lan Ch trước khi chỉnh tốc độ và thêm khoảng nghỉ. Giọng nền Mỹ Duyên không phải giọng đầu ra. Model hội thoại vẫn là Qwen3.5 9B.

Model từ [voice-models.com](https://voice-models.com/model/1mqfLibqJH2): Linh Lan Ch, RVC v2, 150 epochs, có F0, 40 kHz. [Archive gốc](https://huggingface.co/datasets/DangDangg/LinhLanCh/resolve/main/LinhLanChan.zip). File trong `models/rvc/linh_lan_ch/`:

- `LinhLan.pth`: SHA256 `527eb3d01f4e2de96ade20757dfa721335f33bf0db5fc90472eafef727843c73`.
- `added_IVF51_Flat_nprobe_1_LinhLan_v2.index`: SHA256 `5dacb8c9f9fa0e5785571d348f1dcb3c41e103a61f2ccb3ef26184aef4b5c5bf`.

Runtime [Applio](https://github.com/IAHispano/Applio), commit `5379cf261fa7d8085c3b077aa42dabca7c85310b`, đặt trong `private/tools/applio`. Giữ giấy phép MIT của thư viện trong checkout. ContentVec lấy từ `IAHispano/Applio/Resources/embedders/contentvec` trên Hugging Face; RMVPE từ `lj1995/VoiceConversionWebUI/rmvpe.pt`. Không phải model OpenVoice.

RVC chạy trong `private/rvc-env` với PyTorch 2.10.0+cu128 và torchaudio tương ứng, hỗ trợ RTX 5070 (sm_120). Môi trường `.venv` chính giữ PyTorch CPU. Cài lại môi trường từ thư mục gốc:

```powershell
& './private/tools/uv/bin/uv.exe' venv private/rvc-env --python './.venv/Scripts/python.exe'
& './private/tools/uv/bin/uv.exe' pip install --python private/rvc-env/Scripts/python.exe torch==2.10.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
& './private/tools/uv/bin/uv.exe' pip install --python private/rvc-env/Scripts/python.exe -r requirements-rvc.txt
```

Trong `conf.yaml` và profile Mao, bật `character_config.tts_config.vieneu_tts.rvc.enabled`. Các đường dẫn `python_path`, `applio_path`, `model_path`, `index_path` tính từ thư mục khởi động dự án. Pitch = 0, index_rate = 0.6, protect = 0.33; tốc độ đọc giữ 1.08×. Không cần tự tăng pitch chỉ vì đây là giọng nữ.

`RVCConverter` giữ một worker riêng trong bộ nhớ, gửi PCM qua pipe, không chạy Python hoặc nạp model lại mỗi câu và không ghi WAV trung gian. Model, ContentVec, RMVPE và resampler được làm nóng trước khi backend nhận hội thoại. Mỗi worker xử lý tuần tự; nhiều câu song song được khóa để không tráo âm thanh. Chờ quá hạn thì dừng worker, không lấy kết quả câu cũ cho câu mới; không âm thầm phát giọng nền khi RVC lỗi. Log: `logs/rvc-worker.log`.

Đầu ra 40 kHz được dùng đúng khi chỉnh tempo, tính khoảng nghỉ và lưu WAV. Bộ phát frontend lấy sample rate từ WAV, không ép thành 48 kHz. Kiểm tra gồm đường truyền sample rate, khoảng nghỉ, timeout, bỏ qua worker khi tắt, biểu cảm và mẫu thật trên GPU. Mẫu: `cache/linh_lan_ch_preview.wav`, `cache/linh_lan_pipeline_preview.wav`. Đo thử sau làm nóng: đổi giọng khoảng 0.13–0.31 giây cho đoạn 3–4.5 giây; chưa gồm thời gian LLM/VieNeu/phát âm thanh. Giống giọng đến đâu vẫn cần đánh giá bằng nghe thực tế.

Để trở lại giọng nền, đặt `rvc.enabled: false` rồi khởi động lại backend. `scripts/configure_mao.py` giữ cấu hình RVC đã chọn.
