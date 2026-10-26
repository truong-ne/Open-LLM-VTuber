# Tài liệu Mao — rà soát 27/10/2026

Persona và ký ức Mao được đọc từ PostgreSQL. Các file `doc/*.md` là tài liệu
cho người phát triển/vận hành; không được tự nạp làm ký ức hay persona.
`prompts/mao_context.vi.md` và `scripts/configure_mao.py` hiện không còn trong
workspace. Không làm theo hướng dẫn gọi hai đường dẫn đó trong các ghi chú cũ.

## Điểm bắt đầu còn phù hợp

| Tài liệu | Phạm vi |
|---|---|
| [mao_character_core.vi.md](mao_character_core.vi.md) | Lõi nhận thức, biểu đạt, đọc nguồn và tự điều chỉnh phong cách |
| [mao_persona_postgres.vi.md](mao_persona_postgres.vi.md) | Cơ chế hồ sơ trong DB; đoạn “trang bắt đầu trống” mô tả lần khởi tạo, hiện đã có hồ sơ hoạt động |
| [mao_hybrid_architecture.vi.md](mao_hybrid_architecture.vi.md) | Kiến trúc lưu/truy hồi ký ức và quyền; đối chiếu công tắc với cấu hình thực tế |
| [linh_lan_voice.vi.md](linh_lan_voice.vi.md) | VieNeu tạo lời nền → RVC Linh Lan Ch |
| [mao_voice_expression.vi.md](mao_voice_expression.vi.md) | Pipeline biểu cảm giọng; phần đọc bài mới dùng `live/narration_speech.py`, không dùng nhịp chia 18 từ của game |
| [mao_math_speech.vi.md](mao_math_speech.vi.md) | Chuẩn hóa công thức cho lời đọc |
| [mao_youtube_live.vi.md](mao_youtube_live.vi.md) | Bộ đọc chat YouTube; không lấy mô tả persona/fan trong tài liệu cũ làm danh tính hiện tại |
| [vua_tieng_viet.vi.md](vua_tieng_viet.vi.md) | Logic trò chơi; hiện bắt đầu bằng gợi ý, không đọc giới thiệu luật |

Vòng học đang dùng là `scripts/mao_live_research.py`, chạy cùng bộ đọc live:
tập trung cảm xúc và phát triển bản thân, đọc/tóm tắt nguồn, cuộn theo nội dung,
ưu tiên chat và giữ Pet Mode. Hồ sơ DB cùng cấu hình hiện tại là căn cứ vận hành.

## Đã lỗi thời hoặc cần cập nhật một phần

| Tài liệu | Kết luận dựa trên mã/cấu hình hiện tại |
|---|---|
| [mao_comment_panel.vi.md](mao_comment_panel.vi.md) | Mô tả bảng chat thường trực đã cũ; hiện popup chỉ hiện khi Mao trả lời rồi tự ẩn |
| [mao_autonomy.vi.md](mao_autonomy.vi.md) | Mô tả dịch vụ tự đọc nguồn nền cũ; `hybrid.autonomy.enabled` hiện tắt, khác vòng Chrome/LiveResearch đang dùng |
| [mao_draco_desktop.vi.md](mao_draco_desktop.vi.md) | Nhật ký nhiều đợt thay đổi; dòng giọng Mỹ Duyên đầu ra/host cũ không còn đúng, phần renderer vẫn hữu ích |
| [mao_vietnam_and_conversation.vi.md](mao_vietnam_and_conversation.vi.md) | Tham khảo bộ chọn kiến thức, nhưng đường dẫn persona Markdown/marker cũ không còn là nguồn danh tính |
| [mao_daily_learning_and_rehearsal.vi.md](mao_daily_learning_and_rehearsal.vi.md) | Cơ chế đo/tổng kết và diễn tập riêng; `hybrid.learning_enabled` hiện tắt, không phải vòng học nội tâm đang chạy |

## Giữ làm tài liệu kỹ thuật hoặc lịch sử

Chưa có căn cứ để bỏ các tài liệu dưới đây chỉ vì tính năng không xuất hiện
trong phiên live hiện tại. Chúng vẫn là mô tả adapter, renderer, tài sản hoặc
biên bản thay đổi; không có nghĩa mọi tính năng đang được bật.

- Avatar/chuyển động: [draco_body_motion.vi.md](draco_body_motion.vi.md),
  [draco_hand_pose_review.vi.md](draco_hand_pose_review.vi.md),
  [draco_story_actions.vi.md](draco_story_actions.vi.md),
  [mao_motor_learning.vi.md](mao_motor_learning.vi.md).
- Tài sản và ghi công: [draco_model_import_audit.vi.md](draco_model_import_audit.vi.md),
  [malfoy_video_animation_review.vi.md](malfoy_video_animation_review.vi.md).
- Tính năng/cảnh tùy chọn: [mao_dance.vi.md](mao_dance.vi.md),
  [mao_singing.vi.md](mao_singing.vi.md), [mao_tv_studio.vi.md](mao_tv_studio.vi.md),
  [mao_scene_transitions.vi.md](mao_scene_transitions.vi.md),
  [mao_playroom_and_game_learning.vi.md](mao_playroom_and_game_learning.vi.md),
  [mao_creator_guests.vi.md](mao_creator_guests.vi.md). Sở thích fan được nhắc trong
  ghi chú khách cũ không tự trở thành sở thích của hồ sơ DB mới.
- Bảo trì/lịch sử dọn: [workspace_cleanup.vi.md](workspace_cleanup.vi.md).

Đã xóa sáu hướng dẫn không còn dùng: `mao_context.vi.md`,
`mao_preferences.vi.md`, `mao_livestream_design.vi.md`, `mao_proactive_chat.vi.md`,
`mao_pet_mode.vi.md`, `mao_model_upgrade.vi.md`. Các tài liệu kỹ thuật còn liên
quan và biên bản tài sản/ghi công vẫn được giữ để tra cứu.

## Ký ức Livestream 27.10.2026

Đã gộp thành **một ký ức hoạt động**, ID `405`, với embedding trong PostgreSQL,
tên **Livestream 27.10.2026**, thay tên Livestream v1. Phiên này kéo dài qua đêm
26–27/10 theo giờ Việt Nam. Đã xóa khỏi DB 123 ký ức lẻ và 8 bản nhóm thuộc
bản tổng hợp. Chỉ các ID đã gộp được xóa, không xóa theo phạm vi toàn bộ DB.
Đã xóa toàn bộ bản chụp, manifest, bản tổng hợp file và script tạm trong
`private/memory-archives/` theo yêu cầu. Ký ức duy nhất được giữ trong PostgreSQL;
không còn bản lưu file riêng trong thư mục này.

Tài liệu dự án gốc: [documentation site](https://open-llm-vtuber.github.io/) và
[source repository](https://github.com/Open-LLM-VTuber/open-llm-vtuber.github.io).
