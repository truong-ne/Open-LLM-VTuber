# Vua tiếng Việt cùng Mao

## Cách chơi

- Bình luận `!vuatiengviet` trong live YouTube/TikTok, hoặc nhập lệnh trong chat desktop.
- Mao chờ lượt nói hiện tại kết thúc và rèm chuyển cảnh mở xong, rồi mở vòng **đủ 60 giây**. Gửi đáp án trực tiếp trong bình luận hoặc dùng `!doan đáp án`. Cả lúc vào và trở về phòng đều có rèm Mao Theatre; xem `doc/mao_scene_transitions.vi.md`.
- Mao mặc định ở phòng disco; khi bắt đầu chơi sẽ chuyển sang cảnh TV. TV hiển thị ô trống theo từng tiếng, chữ cái xáo trộn, chủ đề, số người tham gia và đồng hồ. Hết phần kết quả sẽ trở về disco. Trong pet mode, TV nổi trên desktop.
- **Gợi ý 1, 2, 3** mở tại giây 0, 20, 40, dùng cách nói đời thường, hình ảnh và ví dụ quen thuộc. Các gợi ý sau giúp khoanh vùng đáp án rõ hơn, không yêu cầu kiến thức khoa học chuyên sâu. Mao đọc gợi ý bằng giọng đang cấu hình, hiện là Linh Lan Ch; đọc mẫu bình luận ở các khoảng 10, 30, 50 giây khi có đáp án.
- Vẫn chơi hết 60 giây kể cả khi có người đoán đúng. Hết giờ mới công bố đáp án, người thắng và top 5; bảng kết quả hiện trong 15 giây.
- Sau mỗi từ, Mao công bố đáp án và giải thích nghĩa ngắn, dễ hiểu. Nếu có người đúng, Mao chúc mừng người đúng sớm nhất; nếu chưa ai đúng, Mao nói tiếc nuối vui vẻ và nhắc người gần nhất nếu có. Vòng chưa có câu trả lời dùng lời động viên riêng. Câu phản ứng thay đổi để tránh lặp; phần đọc bỏ ví dụ phụ và lời mời chơi tiếp để giữ nhịp nhanh.
- Đúng hoàn toàn được 100 điểm; chấp nhận không dấu, chữ hoa/thường và dấu câu. Câu gần đúng nhận điểm tương đồng dưới 100. Xếp theo điểm tốt nhất, rồi thời điểm đạt điểm đó sớm nhất. Không dùng mô hình AI để quyết định thắng thua.
- Mỗi tài khoản tối đa 12 lần đoán/vòng, cách nhau ít nhất 1 giây. Lệnh lặp không đặt lại đồng hồ. Sau mỗi vòng có **CD chung 60 giây** tính từ lúc hết giờ; mọi tài khoản đều phải chờ. Spam lệnh không kéo dài CD, không xếp sẵn vòng mới và không khiến Mao đọc nhắc lại. Lệnh có thời điểm gửi trong CD nhưng đến muộn cũng không tự mở vòng mới sau đó. Hết CD cần gửi lệnh mới.
- Bảng kết quả và Mao Link hiển thị thời gian chờ còn lại. Sau 15 giây kết quả, Mao vẫn trở lại disco như trước; CD tiếp tục ở bảng Mao Link tới khi hết 60 giây. CD tính bằng đồng hồ đơn điệu của server, không phụ thuộc đồng hồ máy người xem.

Trò chơi đọc bình luận từ phiên live đã kết nối. Không tự đăng bình luận lên nền tảng. Bình luận trong vòng chơi được xử lý như đáp án; Mao tạm dừng dẫn chuyện tự động trong vòng chơi và khi đang hiển thị kết quả. Chat desktop cũng chơi được khi kênh chưa live.

## Cấu hình và vận hành

- Kho 30 từ/cụm từ: `knowledge/vua_tieng_viet.vi.json`. Mỗi mục có `answer`, `category`, đúng 3 `hints` và `explanation` bắt buộc, dài tối đa 300 ký tự. Giải thích nghĩa hoặc đặc điểm của từ bằng cách nói quen thuộc, có ví dụ; không chỉ nhắc số tiếng/chữ cái hay đọc lại gợi ý. Viết gợi ý ngắn, gần gũi với sinh hoạt hằng ngày; tránh thuật ngữ khoa học, phân tích ngữ pháp hoặc kiến thức ít người biết. Từ không lặp lại cho đến khi dùng hết kho.
- Logic và đồng hồ: `src/open_llm_vtuber/live/vua_tieng_viet.py`.
- Mức CD mặc định ở `VuaTiengViet.cooldown_seconds = 60`; trạng thái API có `cooldown_seconds`, `cooldown_remaining` và `cooldown_ends_at`. Trạng thái CD tồn tại trong phiên backend, không bị đặt lại do người xem đổi nickname hoặc kết nối lại.
- Giao diện desktop: `web_tool/mao-5070/draco/word-game-overlay.mjs`, tích hợp qua `scripts/build_draco_shell.mjs`.
- Trạng thái chỉ đọc: `GET http://127.0.0.1:12393/api/vuatiengviet/state`. Không trả đáp án hoặc điểm người chơi trước khi hết giờ.
- Xem trước giao diện: `http://127.0.0.1:12393/web-tool/mao-5070/word-game-preview.html` (dữ liệu minh họa, không phải vòng thật).
- Lượt nói trò chơi dùng thẳng TTS/RVC đang chạy; không chờ LLM tạo câu, không thêm bình luận/đáp án vào bộ nhớ hội thoại. Phản ứng, đáp án, phần giải thích và lời mời chơi tiếp nằm chung trong một lượt tổng kết, đọc bằng giọng Linh Lan Ch đang cấu hình. Giải thích chỉ được dùng khi kết thúc vòng, không công bố sớm trong trạng thái chơi. Âm thanh xếp hàng theo lượt phát desktop; đồng hồ và gợi ý trên màn hình không phụ thuộc thời gian tạo giọng.
- Vòng chơi và điểm chỉ tồn tại trong phiên backend hiện tại; khởi động lại sẽ về trạng thái chờ lệnh. Chưa có bảng xếp hạng tích lũy qua nhiều vòng.

## Kiểm tra

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_draco_original_shell.mjs tests/test_word_game_overlay.mjs
```

Chạy thử một vòng thật trên desktop đang mở bằng tên người chơi “Kiểm thử”:

```powershell
.venv/Scripts/python.exe scripts/check_vua_tieng_viet.py --play
```

Lệnh này mất hơn 60 giây, phát giọng trực tiếp, kiểm tra ba gợi ý, đọc bình luận, đồng hồ đủ 60 giây, chấm đúng/không dấu, thứ tự người đoán đúng và chống nhận lại sự kiện. Báo cáo nằm tại `logs/vua-tieng-viet-live-check.json`. Không gửi bình luận lên YouTube/TikTok.
## Nhịp đọc và phụ đề (19/10/2026)

Lời dẫn được tổng hợp và gửi từng câu/cụm tối đa 18 từ, một tác vụ TTS tại
một thời điểm. Câu đã tạo xong phát ngay trong lúc câu tiếp theo được tạo;
không chờ tổng hợp cả đoạn kết. “Hết giờ!” và đáp án đi trước phần phản ứng.
Gợi ý đầu đi thẳng vào nội dung, đồng hồ trên màn hình hiển thị 60 giây.
Giọng gợi ý đầu được chuẩn bị trong lúc chờ vào game; hai gợi ý tiếp theo
chuẩn bị giữa các lượt nói trước mốc 20/40 giây. Bộ đệm WAV giữ tối đa 16
cụm, không giữ file chuẩn bị trên ổ đĩa. Trong lúc chuẩn bị giữ quyền TTS
để không chạy trùng công việc với lời nói trực tiếp. Lỗi chuẩn bị thì dùng
TTS bình thường, không giữ trạng thái chờ vô hạn. Kết quả vẫn chúc mừng/tiếc nuối và giải
thích nghĩa bằng câu đầu trong ngân hàng từ; bỏ lời mời chơi lại và ví dụ phụ
ở phần đọc để tránh kéo dài sang cảnh khác. Nhịp đọc game tối thiểu 1.06×,
giữ sắc thái từng câu, khoảng nghỉ tối đa 60 ms; không đổi giọng Linh Lan Ch.

Phụ đề desktop xuống dòng và tăng chiều cao theo nội dung, không có thanh
cuộn. Đoạn quá dài ở màn hình hẹp được giới hạn số dòng; lời game gửi từng
cụm nên không còn nhét cả đoạn kết vào một ô.
