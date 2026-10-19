# Mao hát từ danh sách chuẩn bị sẵn

Khán giả dùng `!songs` (hoặc `!baihat`, `!sing`) để xem danh sách trên màn hình Mao. Dùng `!sing tên bài`, có thể thêm dấu `+`: `!sing + tên bài`. Tên, mã bài và bí danh khớp chính xác sau khi bỏ dấu, viết hoa và dấu câu. Không tìm, tải hoặc tạo bài hát tự động từ Internet.

Hiện danh sách **trống**, chưa có bản thu giọng Mao. Khung đã hỗ trợ phát một file nhạc hoàn chỉnh có phần hát thu sẵn/chuyển giọng Mao. Không dùng VieNeu TTS để đọc lời thay cho hát. Có thể chuẩn bị bản chuyển giọng Linh Lan Ch bằng quy trình RVC riêng rồi thêm file thành phẩm.

## Thêm bài

1. Đặt file WAV, MP3, OGG hoặc FLAC trong `assets/mao_songs/`. Có thể dùng thư mục con. Bản nhạc cần bao gồm phần giọng hát và nhạc nền đã phối.
2. Sửa `knowledge/mao_songs.vi.json` theo mẫu dưới đây.
3. Khởi động lại backend để nạp danh sách. Mỗi file được kiểm tra bằng metadata âm thanh; bài thiếu/hỏng/dài hơn 15 phút không được phát.

```json
{
  "songs": [
    {
      "id": "ten-bai",
      "title": "Tên bài",
      "file": "ten-bai-mao.wav",
      "aliases": ["tên gọi ngắn"],
      "bpm": 120
    }
  ]
}
```

Đây chỉ là mẫu cấu hình, không phải một bài đã cài. `id` dùng chữ thường a–z, số và dấu gạch ngang; `bpm` trong khoảng 40–220. Đường dẫn phải tương đối bên trong thư mục bài hát. Tên/bí danh giữa hai bài không được trùng sau khi bỏ dấu. Lỗi cấu trúc hoặc tên mơ hồ làm danh sách bị từ chối để tránh hát nhầm bài.

## Luồng tiết mục

- Nhận đúng lệnh và bài có sẵn → chờ Mao nói hết lượt và xử lý các lượt đã chờ.
- Chuyển bằng rèm từ phòng sang sân khấu xanh ngọc/bạc; camera chính diện, vẫn thấy chân. Hết chuyển cảnh mới cho phép phát nhạc.
- Một màn hình nhận quyền phát cho mỗi tiết mục, tránh hai cửa sổ phát chồng. Mao đứng giữa sân khấu, lắc hông theo BPM và thời gian phát thực của file; đèn nền cùng nhịp. Nhép miệng theo mức âm lượng bản phối, chưa phải phân tích âm vị hoặc tách giọng hát.
- Tạm dừng lời dẫn tự động và lượt trả lời bình luận trong lúc hát; bình luận vẫn hiện trên Mao Link. Lượt đang nói được nghe đến hết trước khi hát.
- Hết file → đóng/mở rèm về phòng. Lỗi phát, đóng cửa sổ, mất heartbeat trên 12 giây, chuẩn bị quá 20 giây hoặc chờ lượt quá 120 giây đều giải phóng hàng đợi thoại.
- CD chung **60 giây**, bắt đầu khi tiết mục kết thúc hoặc bị dừng; thời gian chuẩn bị/hát không trừ vào CD. Lệnh spam không xếp bài mới, không kéo dài CD, không tạo tiếng nhắc liên tục. Lệnh cũ gửi trong CD rồi phát lại sau reconnect bị bỏ qua. Không nhận lệnh hát trong vòng Vua Tiếng Việt/khi bảng kết quả còn hiện; không cho mở game trong lúc chuẩn bị/hát.

Chủ phòng có thể nhập `!stopsing` trực tiếp trong ô chat desktop để dừng. Bình luận live không có quyền dừng tiết mục. Phản hồi danh sách/lỗi xuất hiện cục bộ trên giao diện, không đăng bình luận lên YouTube/TikTok.

## Các điểm tích hợp

Backend: `live/singing.py`, `ProxyHandler`, `BufferedLiveChat`, `IdleHost`, `ProxyMessageQueue.external_busy`. Trạng thái/CD dùng đồng hồ monotonic, dữ liệu theo phiên backend; khởi động lại backend sẽ đặt lại CD. Danh sách nhạc là cấu hình lâu dài.

API: `GET /api/sing/songs`, `GET /api/sing/state`, `GET /api/sing/audio/{id}`, `POST /api/sing/playback`. Playback gồm `claim`, `playing`, `heartbeat`, `ended`, `error`, `closed` với `run_id` và `client_id`. Chỉ owner của lượt hiện tại được cập nhật. Luồng bình luận vẫn đi qua proxy, không qua LLM để đoán lệnh.

Desktop: `singing-player.mjs`, `concert-stage.mjs`, `scene-transition.mjs`, `native-avatar.mjs`. Âm thanh phát tại desktop, không chạy chuyển giọng thời gian thực cho mỗi yêu cầu. Bản xem trước `performance-scene-preview.html` chỉ minh họa, không phát nhạc và không thêm bài giả vào danh sách thật.
