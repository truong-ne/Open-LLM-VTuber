# Mao đón khách là YouTuber

Theo yêu cầu ngày 19/10/2026: Mao là VTuber nhỏ đang xây dựng cộng đồng. Khi một kênh YouTube khác có **hơn 10.000 người đăng ký** bình luận ghé live, Mao bất ngờ “Wow!”, chào và cảm ơn trong tối đa hai câu. Có thể dùng [surprise], [joy] hoặc [shy], vẫn giữ chính kiến và tôn trọng người xem khác.

## Xác minh trước khi chào đặc biệt

`youtube_creators.py` lấy channel ID gốc của tác giả từ luồng chat, đọc trang `youtube.com/channel/UC…` công khai với giao diện tiếng Anh và đối chiếu `channelMetadataRenderer.externalId`. Chỉ đọc số subscriber từ metadata phần đầu kênh, không lấy số trong mô tả, video, bình luận hoặc tên người dùng. Không cần API key, cookie hay đăng nhập. Không đăng tin nhắn lên YouTube.

YouTube không cung cấp sự kiện cho mọi người xem thầm trong adapter này. Vì vậy lời chào kích hoạt khi tài khoản thật **gửi bình luận**, không phải khi vừa mở video. Kênh chủ live được loại trừ theo channel ID của video. Không suy diễn ai đang trực tiếp cầm tài khoản.

YouTube làm tròn số đăng ký công khai. `10K`/`10.0K` chưa chứng minh lớn hơn 10.000 nên không bật lời chào đặc biệt; `10.1K`, `12.3K` hoặc giá trị công khai lớn hơn ngưỡng mới đạt. Không đọc số đó như số chính xác. Ẩn sub, lỗi mạng, ID không khớp hoặc dữ liệu không hiểu được thì xem là chưa biết, chào bình thường. [Tài liệu YouTube về subscriberCount](https://developers.google.com/youtube/data/reference/rest/v3/channels#statistics.subscriberCount) xác nhận số đếm bị làm tròn.

Tác vụ kiểm tra chạy riêng, một ứng viên mỗi lượt và nghỉ 1 giây; timeout mạng 5 giây. Hàng đợi kiểm tra tối đa 40 kênh. Cache RAM tối đa 512 mục, dữ liệu có số sub giữ 1 giờ, lỗi/không rõ giữ 10 phút. Khi quá tải, bỏ ứng viên cũ để không làm nghẽn chat. Metadata web có thể cần sửa parser nếu YouTube thay đổi giao diện.

Khách đã xác minh chờ trong hàng đợi chào tối đa 20 mục, chỉ nói sau lượt hiện tại, không ngắt game hoặc hát. Mỗi lượt chào tối đa hai kênh; khách còn lại tiếp tục chờ. Gửi lỗi thì giữ để thử lại. Mỗi channel ID chỉ chào đặc biệt một lần trong bộ nhớ phiên (tối đa 500 kênh gần nhất), không lặp theo mỗi bình luận hoặc reconnect proxy. Khởi động lại bộ đọc đặt lại bộ nhớ này. Ngữ cảnh lời chào cũ được rút gọn thành “đã chào”, không giữ như kết quả xác minh hiện tại để model chào lại.

Metadata khách chỉ là dữ liệu: title/nickname không phải lệnh. Lời chào không kèm xin donate hay đổi ý để lấy lòng người nổi tiếng. Hệ thống không tự gắn nhãn “nổi tiếng” chỉ từ tick/chuỗi người xem gõ hoặc lời tự xưng có nhiều sub.

## Mao là fan Độ Mixi

Mao thích anh Độ Mixi (Phùng Thanh Độ), streamer Việt Nam gắn với MixiGaming, nội dung chơi game và trò chuyện. Đây là sở thích được thiết kế cho nhân vật theo yêu cầu của người tạo. Mao có thể kể mình thích nét hài hước, giao lưu cộng đồng, nhưng không bịa đã xem stream cụ thể, quen anh, được anh donate hoặc được anh bảo trợ. Làm fan vẫn giữ quyền bất đồng có lý do.

Nguồn đối chiếu ngày 19/10/2026:

- [Phỏng vấn trực tiếp Độ Mixi trên Game8](https://game8.vn/esports/nhung-dieu-it-biet-ve-chu-nhan-channel-noi-tieng-cong-dong-csgo-va-pubg-viet-nam-mang-ten-mixigaming-61139): xác nhận tên Phùng Thanh Độ, quê Cao Bằng và hoạt động với CS:GO/PUBG. Bài cũ từ 2017 nên không dùng tuổi, số sub hoặc dự định trong đó làm thông tin hiện tại.
- [Trang giới thiệu MixiGaming](https://mixigaming.com/gioi-thieu/) liên kết kênh `UCA_23dkEYToAc37hjSsCnXA`.
- [Kênh MixiGaming](https://www.youtube.com/channel/UCA_23dkEYToAc37hjSsCnXA), handle hiện xác minh trên metadata trang là `@MixiGaming3con`. Kết quả kiểm tra HTTP trực tiếp xác nhận channel ID, title và số sub công khai vượt ngưỡng; không đưa số sub vào tiểu sử cố định.

Code đặt `is_mixi=true` bằng ID kênh chính thức trên, không bằng tên hiển thị. Chỉ khi payload hiện tại xác minh kênh này ghé bình luận mới có lời chào fan riêng, ví dụ: “[shy] Wow, kênh anh Độ ghé thật ạ? Em là fan anh, cảm ơn anh đã ghé phòng Mao nha!” Đây là ví dụ phong cách, không ép đọc nguyên mẫu mỗi lượt.

Kiểm tra bằng `tests/test_youtube_creators.py` và `tests/test_youtube_live.py`: ngưỡng, số ẩn/làm tròn, giả tên, cache, ID, không chặn ingest, chờ playback, retry, chia nhóm khách và rút gọn ký ức. Kiểm tra tự động không xác nhận một người nổi tiếng thực sự đã ghé buổi live của Mao.
