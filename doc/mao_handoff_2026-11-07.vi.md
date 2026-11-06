# Mao: ghi chú bàn giao 2026-11-07 (dành cho AI/người đọc ở máy có PostgreSQL)

Tài liệu này ghi lại phiên làm việc trên máy dev (VRAM thấp, không chạy app, không có `.venv`). **Mọi thay đổi chưa được chạy hay kiểm thử**, mới kiểm tra cú pháp bằng `py_compile`. Hãy chạy test và kiểm chứng trước khi tin.

## Bối cảnh người dùng
- Dùng Mao gần như chỉ để **livestream TikTok**, ít khi dùng mic.
- Kênh phát cũng là tài khoản của người tạo ra Mao: `@thanhoathirty6` (tên hiển thị "Mèo Gian Khổ"). PostgreSQL chạy ở **máy này (máy kia so với máy dev)**; máy dev chỉ để sửa mã.
- Mục tiêu: Mao trò chuyện tự nhiên hơn, phân biệt người tạo ra Mao với khán giả, thông minh hơn, và có tính cách phát triển dần.
- Người dùng muốn trả lời bằng tiếng Việt.

## Nguyên nhân gốc đã tìm ra
1. `conf.yaml` từng là cấu hình chơi game: persona streamer, `use_mcpp` chỉ có tool game, **không bật `hybrid`** nên không có ký ức/học/cảm xúc.
2. Mô hình `qwen3-vl:8b-instruct`, ngữ cảnh 8192 (biến môi trường Ollama), thiên về đọc ảnh.
3. Mọi câu qua mic gắn nhãn cố định "Khán giả", actor ngẫu nhiên mỗi kết nối nên ký ức không giữ qua lần mở lại. Không có nhận diện người nói.
4. Cơ chế học hằng ngày hẹp: chỉ chỉnh độ dài lời chủ động 40–60 từ, báo `quality_improvement_verified: false`. Phong cách ứng viên chỉ lên active sau 40 mẫu phát triển, 20 mẫu giữ riêng, 3 lần thử thật có phản hồi có nguồn, do người vận hành duyệt (`auto_policy_promotion: false`).

## Việc phải làm trên máy có PostgreSQL

### 1. `conf.yaml` bị git bỏ qua: sửa tay
Dưới `character_config.agent_config.agent_settings.basic_memory_agent`:

```yaml
        use_mcpp: True
        mcp_enabled_servers: ["time", "ddg-search"]   # bỏ "game-control"
        hybrid:
          enabled: true
          creator_mic: true
          creator_name: papa
          input_gate:
            enabled: true
            min_seconds: 0.3
            min_rms: 0.003          # đoán, chỉnh theo log "Input gate dropped"
            drop_hallucinations: true
            require_wake_word: false
            wake_words: [mao]
            follow_up_seconds: 30
          persona_source: postgres
          database_url_env: MAO_DATABASE_URL
          database_env_file: private/mao-hybrid.env
          scope: mao
          # phần còn lại lấy từ config_templates/mao.hybrid.yaml
```

Dưới `live_config.tiktok_live`:

```yaml
    unique_id: "@thanhoathirty6"
    creator_unique_ids: ['@thanhoathirty6']
    creator_name: 'papa'
```

`character_config.persona_prompt` có thể là một dòng ghi chú (ở chế độ `postgres` nó bị bỏ qua).

### 2. DB và persona
```powershell
.\.venv\Scripts\python.exe scripts/mao_hybrid.py migrate
.\.venv\Scripts\python.exe scripts/mao_profile.py show          # xem "revision"
# sửa "revision" trong prompts/mao_profile.vi.json cho khớp, rồi:
.\.venv\Scripts\python.exe scripts/mao_profile.py save --file prompts/mao_profile.vi.json
.\.venv\Scripts\python.exe scripts/mao_profile.py show          # xác nhận status=active
ollama pull qwen3-embedding:0.6b
```
- Markdown/txt **không tự import vào DB**. Chỉ JSON qua `mao_profile.py save` (persona, tối đa 16.000 ký tự) và `mao_learning.py teach --lesson-file` (bài học JSON ≤10 KB, trường `kind`/`content`/`evidence` mỗi trường ≤1.000 ký tự).
- Nguồn persona để sửa: `prompts/mao_persona.vi.txt` (3.475 ký tự). `prompts/mao_profile.vi.json` là bản đóng gói; sửa txt xong phải tạo lại JSON (ghi `json.dumps` của nội dung vào trường `prompt`, giữ `status: active`) rồi `save`.
- Chưa có persona active hoặc DB không đọc được thì Mao **không gọi LLM**, chỉ trả thông báo lỗi. Kiểm tra DB trước giờ live.
- `private/tools/uv/bin/uvx.exe` (dùng bởi `mcp_servers.json` cho `time` và `ddg-search`) và `private/mao-ingress.key` phải có ở máy này.

### 3. Chạy test (chưa từng chạy)
```powershell
uv run pytest tests/test_creator_account.py tests/test_input_gate.py tests/test_lean_tool.py
uv run pytest   # toàn bộ, đặc biệt test_tiktok_batching, test_youtube_live, test_hybrid_*, test_wesnoth, test_mao_runtime
```
Nếu test cũ fail vì đoạn hướng dẫn live bị rút gọn, kiểm tra các câu bắt buộc: "Chỉ nói câu chào và cảm ơn đó rồi dừng", "THÊM Ở CUỐI", tiêu đề "bình luận YouTube thật".

### 4. Kiểm chứng khi live thử
- Bình luận từ `@thanhoathirty6` có được gắn `creator_nickname` và Mao gọi "papa" không (cần xác nhận TikTokLive trả `user.unique_id` đúng dạng).
- Tìm web (`ddg-search`) hoạt động không.
- Độ trễ có chấp nhận được không (hybrid thêm truy vấn DB + embedding mỗi lượt; Ollama nạp thêm mô hình embedding).
- Persona 3.475 ký tự có đủ giọng cho mô hình 8B không; cân nhắc mô hình mạnh hơn hoặc tăng ngữ cảnh.

## Đã thay đổi trong mã
- **Danh tính người tạo (mic):** `interaction/ingress.py` thêm `creator_actor()`/`is_creator()` (actor cố định sinh từ khóa host). `conversations/conversation_handler.py` gắn actor này cho tin `mic-audio-end` không có dấu host. `interaction/service.py` thêm `speaker_role`. `agent/hybrid/runtime.py` thêm `speaker_prompt()` (mục `[SPEAKER]`, không cấp quyền).
- **Danh tính người tạo (TikTok):** `live/tiktok_live.py` truyền `account=user.unique_id`; `live/buffered_chat.py` so với `creator_unique_ids` (không theo nickname; cùng nickname + nội dung từ hai tài khoản thì không tin), thêm `creator_nickname` vào nhóm bình luận, đưa bình luận của người tạo lên đầu lượt trả lời, thêm hướng dẫn gọi `creator_name`. Cấu hình: `config_manager/live.py`, `scripts/run_tiktok_live.py`, hai template `conf.default.yaml`/`conf.ZH.default.yaml`.
- **Lọc mic:** `dialogue/input_gate.py` (bỏ đoạn quá ngắn/quá nhỏ, chữ Whisper bịa, lặp vô tận, tùy chọn wake word), nối vào `conversations/conversation_utils.py::process_user_input` (tham số `gate`) và `single_conversation.py`. Cấu hình `InputGateConfig` trong `agent/hybrid/config.py`.
- **Rút gọn ngữ cảnh:** persona 5.295 → 3.475 ký tự; đoạn hướng dẫn mỗi lượt live trong `buffered_chat.py::_build_turn_text` ~3.990 → ~2.010 ký tự; `agent/hybrid/runtime.py::lean_tool()` chỉ gửi 5 thao tác ký ức khi `computer`, `exploration_enabled`, `wesnoth_enabled` đều tắt (`basic_memory_agent.py` dùng nó thay `TOOL`).
- **Đã xóa (có trong git):** `character/affect.py`, `character/core.py`, `character/preferences.py`, `utils/install_utils.py` (không có nơi nào dùng). Dòng nhắc `core.py` trong `doc/mao_implementation_plan.vi.md` còn sót.
- **File mới:** `prompts/mao_persona.vi.txt`, `prompts/mao_profile.vi.json`, `tests/test_input_gate.py`, `tests/test_creator_account.py`, `tests/test_lean_tool.py`.

## Giới hạn đã biết
- Mic = người tạo cho **mọi** client nối vào backend. Không mở server ra internet khi `creator_mic: true`.
- Chưa phân biệt giọng (không voiceprint): người khác nói to sát mic vẫn bị coi là người tạo.
- Chữ gõ trong app vẫn là khách (actor ngẫu nhiên), không dùng chung ký ức với giọng nói.
- Trên live, bình luận đến theo nhóm công khai, nên ký ức riêng từng người chỉ qua `viewer_memory` (sqlite, theo `author_id`).
- `min_rms: 0.003` chưa được hiệu chỉnh với mic thật.
- Chưa dọn hàm chết bên trong các file còn dùng; chưa xóa engine ASR/TTS/LLM tùy chọn của dự án gốc.

## Bước phát triển tiếp theo (theo ưu tiên)
1. Chạy thật, sửa lỗi phát sinh từ các thay đổi chưa kiểm thử ở trên.
2. Live thử, ghi lại câu hay/ngượng, tinh chỉnh `mao_persona.vi.txt` rồi `save` lại. Thêm "gu" cụ thể (bài hát, món ăn yêu thích) nếu muốn.
3. Chấm lượt trả lời bằng `mao_learning.py feedback --turn MA_LUOT --label useful|too_long|too_short|incorrect|unsafe`; dạy kiến thức bằng `teach`; duyệt ứng viên phong cách thủ công.
4. Cân nhắc đổi sang mô hình mạnh hơn `qwen3-vl:8b-instruct`; đây là trần chất lượng lớn nhất.
5. Bật dần `autonomy`/`exploration` sau khi viết `autonomy_prompt` và `topics` trong profile; hiện tắt.
6. Tùy chọn: voiceprint, cho chữ gõ dùng danh tính người tạo, script tạo JSON từ file txt.
