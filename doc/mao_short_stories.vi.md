# Truyện ngắn và phản ứng bị hù

Yêu cầu kể chuyện ma, chuyện hài hoặc chủ đề khác được tách khỏi trò chuyện thường. Mao soạn trọn một truyện khoảng 100–160 từ (giới hạn 70–200 từ), có mở đầu, diễn biến và kết thúc cùng nhân vật/bối cảnh. Không tự chuyển lời hù Mao thành yêu cầu kể truyện.

Mô hình trả ba phần theo JSON schema trước khi phát âm thanh. Bộ kiểm tra từ chối thiếu đoạn kết, đoạn chưa xong câu, vượt độ dài, hẹn phần sau hoặc giải quyết bằng tỉnh giấc. Thử viết lại một lần nếu không đạt; không cắt ngang bản nháp để vừa độ dài, không đọc JSON hoặc thẻ định dạng. Kiểm tra cấu trúc không bảo đảm tuyệt đối chất lượng văn học hoặc logic; các mẫu sinh thật vẫn cần được đọc đánh giá.

Khi khán giả nói có ma dưới giường Mao/sau lưng Mao hoặc hù Mao, guidance ở lượt đó yêu cầu diễn sợ đáng yêu kiểu anime: kêu giật mình, gọi đúng tên người trêu nếu có, trách yêu họ làm Mao sợ, đáp ngắn và có thể trêu lại. Không xác nhận có ma thật, không giảng giải AI không biết sợ, không gán phản ứng này cho khán giả đang chia sẻ nỗi sợ thật. Biểu cảm surprise được chọn từ thẻ hoặc câu kêu sợ.

Kiểm thử: tests/test_story.py bao gồm nhận diện yêu cầu, phủ định, lời trích dẫn, bình luận TikTok, lỗi mô hình, truyện thiếu kết, thử lại và chỉ phát/lưu phần lời kể hoàn chỉnh. Mẫu sinh thật lưu riêng trong logs/mao-short-story-check.json.

Tên KAITO KID được chuẩn hóa riêng trên luồng âm thanh thành Kaito Kid trước bước viết tắt của VieNeu. Bộ G2P thực tế cho /kaɪɾoʊ kɪd/ thay vì ca a i tê ô ca i đê; tên hiển thị và các chữ viết tắt AI/CPU/GPU được giữ nguyên. Kiểm thử: tests/test_pronunciation.py.
