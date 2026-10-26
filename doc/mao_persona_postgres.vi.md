# Mao mới: persona trong PostgreSQL

Đã ngừng dùng persona Markdown/YAML cho Mao. Cấu hình `hybrid.persona_source: postgres` được bật ở `conf.yaml` và `characters/mao_live.yaml`; `persona_prompt` trong hai tệp đều rỗng. Định danh hội thoại mới là `mao_db_20261026_001`, không tái sử dụng lịch sử các Mao trước.

## Viết persona mới

Mở http://127.0.0.1:12395/mao-5070/persona.html. Trang bắt đầu trống, trạng thái **Bản nháp · chưa nhập vai**. Viết tính cách theo ý bạn, rồi chọn **Lưu bản nháp** hoặc **Lưu và bật persona**. Không cần chỉnh Markdown hoặc restart backend khi đổi persona.

Phần chính là văn bản do bạn tự định nghĩa: tên, danh tính, xưng hô, tính cách, sở thích và cách nói chuyện. Không có nội dung mẫu được tự chèn, không mặc định xưng “thiếp”, Malfoy, Papa, fan Độ Mixi hay tính cách nhí nhảnh. Các phần tự mở chuyện/tự khám phá cũng để trống; có thể thiết kế sau.

DB: `mao_hybrid.character_profiles`, dòng `scope='mao'`.

| Cột | Ý nghĩa |
|---|---|
| `prompt` | Persona do operator viết |
| `status` | `draft` hoặc `active`; prompt rỗng không được active |
| `revision` | Phiên bản, tăng khi lưu; chống ghi đè thay đổi ở tab khác |
| `proactive_prompt` | Chỉ dẫn tự mở chuyện; trống thì chưa tự mở chuyện |
| `autonomy_prompt` | Chỉ dẫn tự khám phá; trống thì chưa tự khám phá |
| `topics` | Danh sách chủ đề operator cho khám phá |
| `updated_at` | Thời điểm lưu |

Runtime đọc profile mỗi lượt. Đổi phiên bản bỏ bộ nhớ làm việc/summary của phiên trước. Nếu profile draft/rỗng hoặc DB không đọc được, hệ thống trả thông báo cấu hình và không gọi LLM để tự nhập vai. Không fallback sang persona cũ trong YAML, Markdown hay avatar.

`mao_app` chỉ có SELECT trên bảng persona. Chỉ công cụ operator dùng quyền ghi. API trên localhost yêu cầu đúng Host, Origin và token; kiểm tra kích thước, cấu trúc và revision. Profile không phải tool mà model có thể tự sửa.

CLI operator:

```powershell
.\.venv\Scripts\python.exe scripts/mao_profile.py show
.\.venv\Scripts\python.exe scripts/mao_profile.py save --file path/to/profile.json
```

Định dạng JSON khớp các cột chỉnh sửa, kèm `revision` hiện tại. Cách đơn giản hơn là dùng trang giao diện. Tự mở chuyện và tự khám phá hiện đã tắt trong cấu hình/control để bạn thiết kế xong trước; bật lại riêng khi cần.

## Prompt cũ từng nằm ở đâu

Tính từ thư mục dự án `C:\Users\LeDinhTruong\Desktop\workspace\Open-LLM-VTuber`:

- `prompts/mao_context.vi.md`: bản Markdown persona.
- `conf.yaml` và `characters/mao_live.yaml`: hai bản persona inline.
- `prompts/utils/mao_expressions.vi.txt`, `mao_pet_actions.txt`, `mao_rehearsal_prompt.txt`: chỉ dẫn giọng/diễn/xưng hô bổ sung.
- `src/open_llm_vtuber/live/idle_host.py`: lời dẫn tự nói, tính cách và lời nhắc donate viết cứng.
- `src/open_llm_vtuber/live/buffered_chat.py`, `youtube_live.py`: cách xưng hô, chào người nổi tiếng và fandom.
- `src/open_llm_vtuber/agent/hybrid/runtime.py`, `autonomy.py`: các lớp chỉ dẫn tính cách, gu khám phá và cách phản ứng.
- `scripts/configure_mao.py` và vài script trong `private/`: chép/khôi phục persona cũ.

Các tệp prompt/script phục hồi cũ đã được đưa khỏi vị trí sử dụng; nội dung tính cách viết cứng đã gỡ khỏi các đường chạy trên. Chỉ dẫn giao thức công cụ, nguồn không tin cậy và kiểm soát quyền vẫn là phần hạ tầng chung, không định nghĩa tính cách mới.

Model Ollama `mao-companion` đã kiểm tra có SYSTEM prompt dài 0 ký tự; không chứa persona cũ. Modelfile còn lại chỉ cấu hình Qwen và tham số chạy, không có SYSTEM. Không huấn luyện lại hoặc xóa trọng số model.

## Reset ký ức và dữ liệu

Đã xóa dữ liệu đang dùng thuộc scope `mao` và `mao-game-2048`: ký ức, trạng thái, event, approval và dữ liệu học tập. Năm thư mục lịch sử `mao_*` cũ đã đưa khỏi `chat_history/`. Cache chủ đề, truyện cười, trạng thái khám phá và các bản cấu hình phục hồi cũ cũng đưa khỏi đường dùng.

Đã giữ một bản khôi phục riêng trong `private/persona-reset-<thời điểm>/`, kèm SQL dump DB trước reset. Vị trí chính xác ở `private/last-persona-reset.txt`. Đây là bản lưu trữ, không được ứng dụng hoặc model nạp; không phải xóa an toàn Git history hay bản sao đã xuất ra trước đây. Không đưa SQL dump/lịch sử riêng vào máy chủ web hoặc outputs.

Hạ tầng PostgreSQL/pgvector, Qwen, TTS và avatar vẫn được giữ. Desktop và host cũ đã dừng để không còn hội thoại trong RAM. Trang tạo persona mới là nơi bắt đầu tiếp theo.
