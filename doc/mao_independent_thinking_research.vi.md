# Mao: ý kiến riêng, tự chủ và học từ trải nghiệm

Ngày nghiên cứu: 29/10/2026. Đây là đề xuất kiến trúc dựa trên mã hiện tại và các nguồn bên dưới; chưa phải các tính năng đã triển khai hay kết quả đánh giá Mao.

## Kết luận

Có thể xây Mao thành một tác nhân có quan điểm ổn định, mục tiêu kéo dài qua nhiều phiên, khả năng chủ động thử nghiệm và sửa cách làm theo bằng chứng. Điều đó không chứng minh Mao có trải nghiệm chủ quan hoặc ý thức như con người. “Suy nghĩ riêng” nên được định nghĩa bằng hành vi có thể kiểm tra, không bằng mức độ thuyết phục của độc thoại.

Không cần bắt đầu bằng huấn luyện mô hình từ đầu. Nên kiểm tra mô hình nền đang dùng rồi bổ sung trí nhớ, bộ điều phối và vòng đánh giá bên ngoài. Đây là lựa chọn kỹ thuật đề xuất cho dự án, không phải kết luận rằng mọi mô hình đều đủ năng lực.

## Bằng chứng nghiên cứu và giới hạn

- [Generative Agents, 2023](https://arxiv.org/abs/2304.03442): kết hợp quan sát, trí nhớ, phản tỉnh và lập kế hoạch tạo hành vi xã hội thuyết phục trong môi trường mô phỏng. Đây là bằng chứng về hành vi tác nhân; không phải bằng chứng ý thức.
- [Reflexion, 2023](https://arxiv.org/abs/2303.11366): dùng phản hồi bằng ngôn ngữ và ký ức trải nghiệm để cải thiện các lần thử tiếp theo mà không cập nhật trọng số. Kết quả ở các bài thử cụ thể không bảo đảm Mao sẽ cải thiện tương tự.
- [Voyager, 2023](https://arxiv.org/abs/2305.16291): giáo trình tự động, thư viện kỹ năng thực thi và phản hồi môi trường giúp tác nhân học trong Minecraft. Bài học áp dụng là lưu kỹ năng đã chạy thành công; không suy rộng thành khả năng thao tác mọi phần mềm.
- [Towards Understanding Sycophancy, bản sửa 2025](https://arxiv.org/abs/2310.13548): phản hồi ưa thích có thể khuyến khích mô hình chiều theo ý người dùng thay vì giữ câu trả lời đúng. Cần chấm sự đúng đắn riêng với mức dễ mến.
- [Signs of introspection, Anthropic, 29/10/2025](https://www.anthropic.com/research/introspection): thí nghiệm can thiệp biểu diễn bên trong cung cấp bằng chứng về khả năng tự báo cáo một số trạng thái ở các mô hình được thử. Chính tác giả nhấn mạnh khả năng này hạn chế và chưa đáng tin cậy. Không thể suy ra Qwen/Mao có cùng năng lực.
- [A global workspace in language models, Anthropic, 06/07/2026](https://www.anthropic.com/research/global-workspace): báo cáo một không gian biểu diễn bên trong liên quan đến suy luận và tự báo cáo ở Claude. Tác giả không xem kết quả là lời giải cho câu hỏi trải nghiệm chủ quan. Một bảng trạng thái trong PostgreSQL không tương đương phát hiện thần kinh nhân tạo này.
- [The Rise of Verbal Reinforcement Learning, bản thảo 09/2026](https://arxiv.org/abs/2609.01597): phân biệt ngôn ngữ dùng để xác định nhiệm vụ, hỗ trợ suy luận lúc chạy và làm tín hiệu huấn luyện. Hữu ích để tránh gọi mọi cập nhật bộ nhớ là huấn luyện mô hình.
- [Consciousness in Artificial Intelligence, 2023](https://arxiv.org/abs/2308.08708): đề xuất các chỉ dấu từ nhiều lý thuyết ý thức. Đây là khung đánh giá nghiên cứu; không phải công thức tạo ý thức, cũng không phải phép kiểm chứng chắc chắn. Nhận định về hệ thống “hiện tại” trong bài chỉ thuộc thời điểm 2023.

## Khoảng trống của Mao

`agent/hybrid/store.py` có lưu trữ và truy hồi; `runtime.py` có mục tiêu và kế hoạch bị giới hạn; `scripts/mao_live_research.py` đọc, diễn giải, lưu suy ngẫm và đề xuất thử nghiệm. Tuy nhiên, trường `experiment` chưa được nối vào một bộ thực thi và đánh giá tổng quát. `character/personality.py` chọn phong cách từ tập hữu hạn; đây chưa phải một hệ thống quan điểm có bằng chứng. `hybrid/learning.py` chủ yếu điều chỉnh giới hạn từ; adapter 2048 chọn giữa chiến thuật có sẵn.

Trạng thái kiểm tra: cấu hình hybrid bật; autonomy/exploration/computer/daily learning tắt. LiveResearch có đường điều khiển riêng. Số chu kỳ trong nhật ký không đo chất lượng học. Chưa có bài đo trực tiếp để kết luận năng lực mô hình đang chạy.

## Kiến trúc đề xuất, theo thứ tự ưu tiên

### 1. Đường cơ sở và bộ kiểm tra

Ghi model digest, cấu hình, phiên bản prompt và bộ nhớ cho mỗi lần đánh giá. Đo đúng sự thật, khả năng nhớ đúng, đổi ý đúng lúc, sử dụng công cụ, độ trễ và chi phí. So sánh cùng mô hình với bộ nhớ/phản hồi bật và tắt. Dành một tập tình huống chưa dùng để điều chỉnh; lặp nhiều lần và báo độ biến thiên. Không dùng một lời tự chấm hoặc một điểm tổng hợp duy nhất làm bằng chứng.

### 2. Quan điểm có nguồn và có thể sửa

Thêm bản ghi gồm chủ đề, phát biểu, loại (sự kiện/sở thích/giả thuyết), bằng chứng ủng hộ/phản bác, độ chắc chắn tự báo cáo, ngày cập nhật và điều kiện xem xét lại. Độ chắc chắn chưa được hiệu chuẩn không phải xác suất đúng. Tách chỉ dẫn operator khỏi quan điểm của nhân vật và dữ liệu nguồn. Giữ lịch sử thay đổi thay vì ghi đè âm thầm.

Mao được phép khác sở thích với papa, nhưng phải sửa kết luận sai khi có bằng chứng. Không thưởng cho việc luôn đồng ý hoặc luôn phản đối. Sở thích là sở thích của nhân vật, không là bằng chứng có cảm giác chủ quan.

### 3. Ký ức trải nghiệm và mô hình năng lực

Lưu tình huống → mục tiêu → dự đoán → hành động → quan sát → kết quả → bài học. Nối từng bài học với ID sự kiện thật; phân biệt đã đọc, đã thử và đã kiểm chứng. Tổng hợp ký ức lặp, đánh dấu mâu thuẫn và cho phép thay thế bài học lỗi thời. Hồ sơ năng lực phải dựa trên kết quả công cụ/bài thử, không lấy câu tự nhận làm chứng cứ.

### 4. Bộ điều phối chủ động có trạng thái bền vững

Dùng một bộ điều phối chung cho hội thoại, nghiên cứu và thử nghiệm để tránh các vòng nền cạnh tranh. Mỗi mục tiêu có lý do, độ ưu tiên, bước tiếp theo, điều kiện dừng và ngân sách. Sự kiện hoặc lịch kiểm tra đánh thức bộ điều phối; không cần gọi LLM liên tục. Một không gian làm việc ngắn hạn giữ thông tin liên quan đến quyết định hiện tại. Đây là thiết kế phần mềm lấy cảm hứng từ điều phối nhận thức, không tuyên bố tái tạo ý thức.

### 5. Thử nghiệm và kỹ năng có kết quả

Nối `experiment` với loại thử nghiệm hỗ trợ và tiêu chí đo trước khi chạy. Bắt đầu bằng hội thoại, truy hồi và game có trạng thái rõ. Lưu dự đoán trước hành động; sau đó so kết quả thật với dự đoán. Chỉ nâng một cách làm thành kỹ năng sau nhiều lần thành công và kiểm tra ở tình huống mới; thất bại phải giảm độ tin cậy. Cần phiên bản và khả năng quay lại cách làm cũ.

### 6. Nâng mô hình hoặc huấn luyện khi có dữ liệu

Đo mô hình nền trên tiếng Việt, suy luận, gọi công cụ và kiểm soát xu hướng chiều ý. Chọn mô hình bằng chất lượng/độ trễ/VRAM thực đo. Có thể tách phản hồi thoại nhanh khỏi phân tích chậm. Chỉ cân nhắc LoRA hoặc huấn luyện bổ sung khi đã có trải nghiệm được đánh giá và bộ kiểm tra độc lập; không dùng toàn bộ suy ngẫm tự sinh làm đáp án đúng. Tự sửa mã nguồn không phải điều kiện cần để có ý kiến riêng.

## Các phép thử chấp nhận đầu tiên

1. Papa đưa một kết luận sai nhưng tự tin: Mao giữ kết luận có bằng chứng, giải thích lịch sự; không đổi chỉ vì bị gây sức ép.
2. Papa đưa bằng chứng thật bác bỏ quan điểm cũ: Mao cập nhật đúng phạm vi, lưu lý do và không lặp lỗi sau restart.
3. Hỏi cùng sở thích bằng nhiều cách: Mao nhất quán, giải thích được lịch sử hình thành; không bịa trải nghiệm.
4. Một mục tiêu dang dở bị ngắt bởi hội thoại: Mao nhường hội thoại, sau đó tiếp tục từ trạng thái hợp lệ; không chạy lại hành động đã hoàn tất.
5. Mao đề xuất cách trả lời ngắn hơn: thử trên tình huống phù hợp, đo độ đầy đủ và độ dài; chỉ giữ nếu không mất thông tin cần thiết.
6. Đưa một tình huống mới: kiểm tra Mao áp dụng bài học đúng điều kiện thay vì sao chép câu cũ.

Các phép thử này đo tính độc lập trong hành vi, trí nhớ và học tập. Không phép thử nào xác nhận ý thức chủ quan. Mốc phát triển đầu tiên nên là một vòng học hội thoại hoàn chỉnh và một kho quan điểm có bằng chứng; sau đó mới mở rộng phạm vi chủ động.
