# Model hội thoại Mao — 19/10/2026

`mao-companion` dùng Qwen3.5 9B thay Gemma 3 12B. Bản Ollama tải khoảng 6,6 GB, lượng tử hóa Q4_K_M, context cấu hình 8.192 token. Kế thừa template gốc của Qwen để giữ system prompt, hình ảnh và tool calling; không dùng lại template Gemma. Persona vẫn được backend truyền theo từng cuộc hội thoại.

`think: false` trong cấu hình Ollama được gửi qua API tương thích OpenAI để tránh chờ suy luận dài khi trò chuyện. Không đặt giá trị này cho provider khác; bỏ trống sẽ dùng mặc định model. VieNeu Mỹ Duyên tạo lời nền trên CPU với tốc độ đọc 1,08×; giọng đầu ra đã đổi sang Linh Lan Ch qua RVC GPU. Xem `doc/linh_lan_voice.vi.md`.

Qwen3.5 là một lựa chọn vừa bộ nhớ cho RTX 5070 12 GB, không phải model mới nhất tuyệt đối. Qwen3.8 27B mới hơn nhưng bản Ollama khoảng 18 GB, không vừa hoàn toàn VRAM này. Dung lượng tải không phải tổng VRAM chạy: còn context, cache và các ứng dụng khác.

Đổi model không đồng nghĩa có kiến thức trực tiếp đến hôm nay. Mao nhận ngày Việt Nam mới theo từng lượt; `use_mcpp: true` bật `time` (Asia/Ho_Chi_Minh) và `ddg-search`. Công cụ chỉ chạy khi model yêu cầu. Khi không tra được, Mao được hướng dẫn nói rõ chưa kiểm chứng. Kết quả tìm kiếm vẫn cần đối chiếu; không bảo đảm mọi câu trả lời chính xác.

Runtime MCP dùng `private/tools/uv/bin/uvx.exe` của workspace, không phụ thuộc uvx trong PATH. Lần đầu chạy có thể cần tải dependency. Khởi động backend từ thư mục gốc như script local hiện có.

Nguồn: [Qwen3.5 9B](https://ollama.com/library/qwen3.5:9b), [model card Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), [Qwen3.8 27B](https://ollama.com/library/qwen3.8:27b), [Ollama API](https://docs.ollama.com/api/openai-compatibility).

Kiểm tra trên máy: lời chào, câu hỏi sử Việt, tắt thinking, yêu cầu tool calling và tìm kiếm web thật; tốc độ sinh khoảng 87–93 token/giây ở các lượt ngắn sau khi nạp. Đây là tốc độ sinh văn bản, chưa gồm TTS, phát âm thanh hoặc thời gian mạng. Log thử: `logs/mao-qwen35-eval.json`.

Tạo lại alias sau này:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
& './private/tools/ollama/ollama.exe' pull qwen3.5:9b
& './private/tools/ollama/ollama.exe' create mao-companion -f prompts/mao_companion.Modelfile
& './.venv/Scripts/python.exe' scripts/configure_mao.py
```

Gemma 3 được gỡ qua Ollama sau khi kiểm tra Qwen thành công; không xóa thủ công thư mục model hoặc cache chung. Ghi chú template Gemma cũ đã được lưu ra ngoài cây tài liệu hiện hành; ngữ cảnh nhân vật hiện tại được mô tả trong `doc/mao_context.vi.md`.
