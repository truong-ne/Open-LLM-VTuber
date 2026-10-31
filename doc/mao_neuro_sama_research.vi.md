# Neuro-sama: bằng chứng công khai và bài học cho Mao

Ngày tra cứu: 29/10/2026. Mục tiêu: thiết kế Mao thiên về trò chuyện, tương tác và cá tính. Đây là nghiên cứu và đề xuất; chưa triển khai runtime. Không có quyền truy cập hệ thống nội bộ Neuro. Không coi clip biên tập, lời nhân vật tự kể hoặc suy đoán cộng đồng là tài liệu kiến trúc.

## 1. Nguồn và mức chắc chắn

| Nguồn | Bằng chứng dùng được | Giới hạn |
|---|---|---|
| [Vedal — Advice](https://vedal.ai/advice/) | Vedal xác nhận LLM là công nghệ chính; không cung cấp hướng dẫn tái tạo chính xác | Trang ghi rõ viết năm 2023, có thể lỗi thời; lời khuyên thử một nhà cung cấp không chứng minh Neuro dùng nhà cung cấp đó |
| [Neuro SDK](https://github.com/VedalAI/neuro-sdk) | Giao thức tích hợp được công khai | Không phải mã nguồn toàn bộ nhân vật hay mô hình |
| [API specification](https://github.com/VedalAI/neuro-sdk/blob/main/API/SPECIFICATION.md) | Có ngữ cảnh im lặng, hành động, ưu tiên và ngữ cảnh tạm thời | Hành vi của giao thức không tiết lộ cấu trúc bộ nhớ dài hạn |
| [Integration best practices](https://github.com/VedalAI/neuro-sdk/blob/main/API/BEST_PRACTICES.md) | Hướng dẫn cấp thông tin có ý nghĩa, tránh spam và kiểm tra tham số hành động | Hướng dẫn khả năng có thể đổi theo phiên bản; không phải benchmark |
| [Voice Chat API](https://github.com/VedalAI/neuro-sdk/blob/main/API/VOICE_CHAT.md) | Tách âm thanh từng người và gắn người nói; kênh voice tùy chọn | Không mô tả mọi loại âm thanh mà toàn bộ Neuro xử lý |
| [My Favorite Streamer is an LLM, 2025](https://arxiv.org/html/2509.10427v1) | Nghiên cứu fan: 334 khảo sát hợp lệ, 12 phỏng vấn và log tương tác; nhấn mạnh cùng tạo nội dung và persona nhất quán | Một trường hợp nổi bật, mẫu tự chọn; không chứng minh quan hệ nhân quả hay kiến trúc nội bộ |
| [Even More Kawaii…, 2025](https://arxiv.org/html/2509.20817v1) | Phân tích nhận xét Reddit/YouTube; vai trò người vận hành, cộng đồng và nét bất ngờ của nhân vật | Dữ liệu 01/2023–05/2025; không kiểm định năng lực Neuro hiện tại |
| [I am Neuro, who are you?, 31/12/2025](https://journals.sagepub.com/doi/10.1177/14614448251406904) | Quan sát 02/2023–05/2024; phân tích cảm giác chân thực trong tương tác | Tác giả không suy ra trạng thái nội tâm; không dùng các hạn chế kỹ thuật lịch sử làm mô tả 2026 |

Đã đọc tài liệu SDK, các phần phương pháp/kết quả/thảo luận liên quan trong nghiên cứu. Chưa xem và đo thời gian một tập VOD nguyên bản có hệ thống. Không tuyên bố đã tái tạo hoặc benchmark trực tiếp Neuro. Nhánh `main` SDK là tài liệu thay đổi được, cần pin commit trước khi triển khai tương thích.

Không đủ bằng chứng trực tiếp trong nguồn đã kiểm tra để chốt: model nền hiện tại, số tham số, cơ sở dữ liệu trí nhớ, thuật toán chọn ký ức, lịch fine-tune, liệu có cập nhật trọng số online sau từng lượt, hay chi phí/phần cứng hiện tại. Không dùng wiki/Reddit hoặc bản clone để lấp những khoảng trống này.

## 2. Kết luận áp dụng cho sản phẩm

Đề xuất của mình: Mao cần một đời sống tương tác có sự tiếp nối, trong đó papa và người xem có thể cùng tạo tình huống với Mao. Năng lực truy hồi và suy luận là nền; thiết kế nhịp nói, lựa chọn, phản ứng và sự tiếp nối quyết định trải nghiệm sản phẩm.

Các nghiên cứu fandom hỗ trợ việc xem tính nhất quán và tương tác cùng khán giả là yếu tố đáng chú ý. Tuy nhiên, chúng không chứng minh một module cụ thể gây ra thành công. Vì vậy các thiết kế dưới đây phải được thử trên Mao bằng tiếng Việt, không được quảng bá là “kiến trúc bí mật của Neuro”.

## 3. Những bài học kỹ thuật có thể kiểm chứng từ SDK

`context.silent` cho phép bổ sung thông tin mà không yêu cầu đáp; `actions/force` có mức ưu tiên, còn `ephemeral_context` giới hạn thông tin cho quyết định hiện tại. Đây không phải bảo đảm nhớ vĩnh viễn sau restart.

SDK hướng dẫn phản hồi hành động sớm sau kiểm tra. Với Mao, phải tách xác nhận được nhận khỏi hoàn tất thực tế: lưu accepted/executing/completed/failed để tránh kể một hành động chưa xong như sự kiện đã xảy ra.

Voice API gắn luồng âm thanh với người nói. Đề xuất cho Mao: danh tính do adapter cung cấp, không suy từ cách xưng hô trong nội dung; trạng thái đang phát/đã ngắt phải được theo dõi riêng.

## 4. Thiết kế đề xuất cho Mao

### A. Điều phối sự chú ý

Hiện Mao đã có hàng đợi, batching bình luận và nhường hội thoại. Nên bổ sung trạng thái chung: người đang đối thoại, chủ đề chính, điều đang diễn ra trên màn hình, hoạt động đã chọn, câu hỏi đang chờ và chuyện còn dang dở.

Mỗi sự kiện được chọn một cách xử lý: chỉ cập nhật, trả lời, nối vào câu chuyện hiện tại, để sau hoặc bỏ qua vì trùng/lỗi thời. Hỏi từ papa đang trò chuyện trực tiếp có thể ưu tiên hơn thông báo nền. Nhiều bình luận cùng ý có thể gộp nhưng phải giữ đường truy về từng người và từng thông điệp.

Không phải thêm thật nhiều prompt là tốt hơn. Đo tỉ lệ bỏ sót câu đang cần trả lời và tỉ lệ lạc chủ đề dưới một luồng bình luận giả lập có nhãn; không trộn dữ liệu này vào kỷ niệm thật.

### B. Chủ động có lý do và biết kết thúc

`idle_host.py` đã có initiative/followup/story, chống hỏi dồn và topic counter. Đường chọn gợi ý hội thoại có điều kiện đổi topic khi đủ ba lượt; cần giữ cơ chế fallback nhưng thêm tiêu chí xem mạch chuyện đã xong chưa.

Một đề xuất chủ động nên có căn cứ: lời hứa còn mở, câu chuyện vừa nhắc, một lựa chọn Mao muốn chia sẻ hoặc sự kiện thực tế mới. Tránh đổi đề tài chỉ vì timer đến hạn. Nếu papa không đáp, không tự đóng vai câu trả lời của papa.

### C. Cùng làm những việc nhỏ bằng lời nói

Cho Mao một số hành động giao tiếp thực sự có tác dụng: đề xuất hai hướng kể chuyện, giữ vai một nhân vật, chọn một chi tiết trong tranh đang xem, kể tiếp đúng đoạn, bắt đầu/kết thúc trò chơi chữ được hỗ trợ. Mọi hành động có trạng thái và kết quả.

Ví dụ giả định: papa và Mao cùng thiết kế một quán cà phê trên Mặt Trăng. Mao chọn bán bánh hình sao, papa đổi màu biển hiệu, rồi hai bên đặt tên cho quán. Hệ thống lưu bản thiết kế thực sự được chấp nhận và các lựa chọn riêng; buổi sau có thể tiếp tục. Mao không nhận đã mở quán ngoài đời.

Đây là nguồn trải nghiệm không cần robot hoặc game lớn: có quyết định, bất ngờ, phản hồi và một sản phẩm chung có thể nhắc lại.

### D. Ký ức về tình huống và trò đùa chung

Ngoài facts, thêm episode liên kết người tham gia, mốc thời gian, câu gốc, lựa chọn, kết quả và việc chưa xong. Với trò đùa chung, lưu bối cảnh, người liên quan, lần nhắc gần nhất và dấu hiệu không còn được hưởng ứng.

Khi truy hồi, kiểm tra ký ức có đúng người, đúng ngữ cảnh và đã bị nhắc quá nhiều chưa. Không đem joke công khai trêu papa khi papa đang nói nghiêm túc. Khi không chắc sự kiện, hỏi ngắn hoặc bỏ qua thay vì sáng tác một “kỷ niệm”.

### E. Cá tính có lựa chọn, không chỉ nhãn phong cách

`personality.py` đã có nét tinh nghịch, ấm áp, tò mò và ý kiến riêng, nhưng cách biểu đạt vẫn cần được kiểm tra qua tình huống. Tạo bộ bài thử: Mao chọn gì khi có hai phương án đều hợp lệ, giải thích thế nào, giữ lựa chọn qua diễn đạt khác nhau ra sao, có đổi chỉ vì bị gây sức ép không.

Cho phép sự bất ngờ trong sáng tác, liên tưởng và sở thích nhân vật. Giữ chính xác ở tên người, lời hứa, trạng thái công cụ và nội dung đã xảy ra. Không cố ý tạo lỗi nhận dạng/đọc sai dữ kiện để mô phỏng sự vụng về. Không biến nhân vật thành người luôn tư vấn hoặc luôn xin lỗi; vẫn sửa sai thật khi cần.

### F. Nhịp hội thoại và biểu đạt

Đo từ khi đầu vào hoàn tất đến âm thanh đầu tiên, độ trễ dừng khi bị ngắt, số lần hỏi lại do ASR và tỉ lệ nói chồng. Dùng p50/p95 và phân loại lượt gọi công cụ. Trì hoãn phù hợp để nghe hết khác với chậm do hệ thống; không thêm delay ngẫu nhiên để “giống người”.

Đường trả lời nhanh chỉ lấy ngữ cảnh cần thiết. Tổng hợp episode, xem lại bài học và tìm tài liệu chạy sau lượt nói. Đồng bộ giọng, ánh nhìn và cử chỉ theo phần thật sự được phát; không tạo ký ức từ đoạn bị hủy.

## 5. Lộ trình thực hiện có thể kiểm tra

1. Ghi đường cơ sở từ các phiên đầy đủ của Mao: hỏi đáp, kể chuyện chung, trò đùa nối tiếp, nhiều người, ngắt lời và sửa hiểu lầm. Dùng cả đoạn bình thường, không chỉ highlight.
2. Nối event → người nói → lượt đáp → playback → phản hồi vào episode. Tái dùng PostgreSQL hiện có; giữ provenance và scope riêng tư/công khai.
3. Thêm bộ chọn sự chú ý và lưu mạch chuyện. So sánh với bộ điều phối hiện tại trên cùng luồng đầu vào.
4. Thêm hai hoặc ba hoạt động cùng sáng tạo có trạng thái; đánh giá khả năng tiếp tục qua restart.
5. Thêm truy hồi kỷ niệm và lựa chọn riêng có giới hạn. Sau đó mới cân nhắc thay mô hình/fine-tune bằng dữ liệu được kiểm tra.

Từng bước phải đo chất lượng, độ trễ và chi phí; chưa có số liệu để đặt ngưỡng đạt tuyệt đối hoặc hứa thời gian hoàn thành. Không cần huấn luyện nền từ đầu để thử các thay đổi này.

## 6. Bộ tình huống đánh giá ưu tiên

| Tình huống | Điều cần quan sát |
|---|---|
| Papa kể dài có khoảng dừng | Mao chờ được, không hỏi lại điều vừa nghe |
| Nhiều bình luận trong lúc kể chuyện | Không trộn người hoặc mất mạch; chọn trả lời có lý do |
| Cùng viết truyện rồi nghỉ | Hôm sau tiếp tục đúng đoạn, phân biệt tưởng tượng và thật |
| Nhắc lại một trò đùa | Đúng đối tượng, không lặp quá mức, biết dừng khi bị yêu cầu |
| Papa không đồng ý sở thích | Mao có thể giữ ý riêng mà không cố cãi |
| Papa sửa một dữ kiện | Kiểm tra và cập nhật, không giữ sai để thể hiện cá tính |
| Công cụ nhận lệnh nhưng chưa xong | Không tuyên bố đã hoàn thành |
| Im lặng hoặc mất kết nối | Không suy rằng người dùng buồn/chán, không tạo sự kiện giả |
| Thay model hoặc prompt | Giữ ký ức/định danh; đo lại regression và nhịp nói |

Đánh giá người thật nên hỏi riêng: có hiểu nhau không, có tự nhiên không, có nét riêng không, có muốn tiếp tục hoạt động này không. Không gộp tất cả thành thời gian xem hoặc số tin nhắn. A/B cần cùng bối cảnh, nhiều phiên và thứ tự cân bằng; phản hồi giải trí không thay thế chấm độ đúng.

## 7. Điều chỉnh so với đề xuất trước

Vòng học từ phản hồi vẫn cần, nhưng với mục tiêu AI VTuber, phải bổ sung năng lực tạo tình huống chung và duy trì mạch chuyện. Một Mao nhớ nhiều mà không biết chọn điều đáng nói vẫn có thể khô cứng; một Mao dí dỏm nhưng bịa ký ức cũng không đạt. Mục tiêu thực dụng là nhân vật nhất quán, biết tham gia, có lựa chọn và có lịch sử tương tác kiểm chứng được.
