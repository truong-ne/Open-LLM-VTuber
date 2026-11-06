# Nguồn và cách xây kho Vua Tiếng Việt mở rộng

Kho đang chọn: **2.500 câu mới** (2.000 thường, 500 thử thách mức vừa), gồm 30 câu tục ngữ/ca dao biên soạn thêm. Kho lưu trữ tổng cộng 2.757 câu; 257 câu cũ được giữ nguyên trong ba file gốc nhưng bị loại khỏi lựa chọn bởi `classroom-bank-policy.json` theo yêu cầu người vận hành.

## Dữ liệu từ điển

- Nguồn: [VNTK dictionary](https://github.com/vntk/dictionary), `data/dictionary.json`.
- URL tải: https://raw.githubusercontent.com/vntk/dictionary/master/data/dictionary.json
- SHA-256: `fb41663096d6a24de8854567e5a4c5aded5bf39ce7bc2172d3cd0211c360c763`.
- Kho gốc ghi giấy phép MIT, Copyright (c) 2017 Vietnamese Natural Language Processing (VNTK). Giữ bản đầy đủ tại `classroom-dictionary-LICENSE.txt`.
- Câu từ điển được chọn theo nghĩa, ví dụ và tần suất; bỏ tham chiếu chéo, từ trùng sau chuẩn hóa, nhiều mục quá chuyên môn và mục không có ví dụ phù hợp. Gợi ý đầu lấy nghĩa, gợi ý thứ hai che từ trong ví dụ; giải thích nêu nghĩa cùng ví dụ đầy đủ. Đây là dữ liệu lọc tự động có kiểm tra và xem mẫu, không tuyên bố đã duyệt thủ công từng câu.

## Xếp hạng độ phổ biến

- Nguồn tham khảo xếp hạng: [tabidots/vn-freqs](https://github.com/tabidots/vn-freqs), `vn_word_frequencies.tsv` (kho mô tả nguồn Leipzig và OpenSubtitles, tách từ bằng pyvi).
- URL tải: https://raw.githubusercontent.com/tabidots/vn-freqs/main/vn_word_frequencies.tsv
- SHA-256: `8f644d06173600f8acb0d2b1a9dd0111c53ef304b9974b76e2cb24bad81fe04d`.
- Chỉ dùng thứ hạng để chọn từ; không đóng gói bảng tần suất vào kho câu hỏi.

## Dựng lại và kiểm tra

Đặt hai nguồn đã tải trong `private/classroom-dictionary-source.json` và `private/classroom-compound-frequency.tsv`, rồi chạy `scripts/build_classroom_bank.py`. Script kiểm tra checksum trước khi dựng. 30 câu tục ngữ mới ở `classroom.proverbs-new.vi.json` là nguồn biên soạn riêng được ghép vào file mở rộng; runtime chỉ nạp bản ghép để không đếm hai lần.

Kiểm tra bằng `tests/test_classroom_bank.py` và `tests/test_classroom.py`: đủ số lượng, không trùng đáp án, gợi ý không chứa đáp án ngay cả khi bỏ dấu, giới hạn độ dài, giữ điểm/phiên khi nạp lại, chọn hết 2.500 câu không lặp và tiếp tục bỏ qua 257 câu cũ ở chu kỳ sau.
