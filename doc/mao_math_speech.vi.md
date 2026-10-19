# Đọc công thức trong lời thoại Mao

`character_config.tts_preprocessor_config.vietnamese_math: true` bật cách
đọc toán tiếng Việt trước khi bộ lọc xóa ngoặc, dấu mũ hoặc dấu nhân. Mặc
định tắt ở nhân vật khác để tránh ép ngôn ngữ tiếng Việt. Engine VieNeu cũng
áp dụng khi được gọi trực tiếp. Công thức trên phụ đề và lịch sử giữ nguyên;
chỉ phần phát giọng được đổi sang lời. Không tính toán hay sửa đáp án.

| Văn bản | Cách đọc |
| --- | --- |
| `x^2`, `x²` | ích mũ hai |
| `x^{-2}` | ích mũ âm hai |
| `2**3=8` | hai mũ ba bằng tám |
| `(1+2)*3=9` | mở ngoặc một cộng hai đóng ngoặc nhân ba bằng chín |
| `2 * 3 * 4` | hai nhân ba nhân bốn |
| `x<=2`, `x≤2` | ích nhỏ hơn hoặc bằng hai |
| `x≠2`, `x≈2` | ích khác hai; ích xấp xỉ hai |
| `√9=3` | căn bậc hai của chín bằng ba |
| `1/2 + 1/2 = 1` | một phần hai cộng một phần hai bằng một |
| `20 m²`, `3 cm³` | hai mươi mét vuông; ba xen ti mét khối |

Số, số thập phân, ngày giờ và phần trăm tiếp tục qua normalizer của VieNeu.
Bộ đọc bổ sung không diễn giải lại ngày đầy đủ, giờ, phiên bản ba thành phần,
URL, email hoặc lệnh `!sing + tên bài`. Phân số đứng riêng có thể trùng ngày
rút gọn, nên giữ cho normalizer hiện có đọc (ví dụ `1/2`: một trên hai).

Phạm vi là biểu thức sơ cấp với biến một chữ, ngoặc lồng tối đa ba tầng và
một số cách viết số mũ bằng ngoặc nhọn. Chưa phải trình đọc LaTeX đầy đủ:
ma trận, tích phân, `\frac`, `\sqrt`, chỉ số dưới và tên hàm nhiều chữ chưa
được bổ sung. Với công thức phức tạp nên viết lời giải thích bằng chữ.

Kiểm tra: `python -m unittest discover -s tests -p 'test_math_speech.py'` và
`test_speech_expression.py`; bao gồm luồng lời thoại/phụ đề và VieNeu gọi trực tiếp.
