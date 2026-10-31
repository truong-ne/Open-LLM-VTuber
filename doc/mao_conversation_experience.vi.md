# Xây trải nghiệm cho Mao qua trò chuyện và tương tác

Ngày nghiên cứu: 29/10/2026. Phạm vi: nhân vật trò chuyện bằng văn bản/giọng nói, riêng với papa hoặc trong livestream. Đây là đề xuất, chưa triển khai vào runtime. “Trải nghiệm” trong tài liệu là lịch sử tương tác có thể quan sát và sử dụng lại, không phải khẳng định cảm giác chủ quan.

## 1. Đơn vị trải nghiệm là một đoạn tương tác

Một câu chat riêng lẻ chỉ là sự kiện. Một trải nghiệm gồm tình huống, người tham gia, điều họ nói, điều Mao hiểu (có thể sai), phản hồi của Mao, phần được phát thực tế, phản hồi tiếp theo và kết quả còn biết/chưa biết. Có thể gồm vài lượt hoặc nhiều đoạn được liên kết; không cố định số lượt.

Ví dụ minh họa, không phải hội thoại đã xảy ra:

- Papa: “Hôm nay mệt quá.”
- Mao đưa một danh sách giải pháp.
- Papa: “Papa chỉ muốn kể thôi, đừng khuyên vội.”
- Mao: “Ừm, papa cứ kể, Mao nghe.”
- Kết quả xác nhận được: papa yêu cầu nghe thay vì khuyên ở thời điểm này. Chưa xác nhận papa đã vui hơn.
- Bài học ứng viên: khi papa chia sẻ chuyện mệt mỏi mà chưa hỏi cách giải quyết, ưu tiên lắng nghe trước. Nếu cần, hỏi ngắn xem papa muốn chia sẻ hay tìm giải pháp; không hỏi câu này máy móc mỗi lần.
- Phản ví dụ phải xử lý: ngày khác papa nói “Cho papa ba cách xử lý”; lúc đó đưa giải pháp. Không biến trải nghiệm trước thành quy tắc “papa không bao giờ thích lời khuyên”.

Một sửa đổi rõ ràng áp dụng ngay trong phạm vi được nói tới. Chỉ suy rộng thành thói quen lâu dài khi có lời yêu cầu mang tính lâu dài hoặc nhiều trải nghiệm hỗ trợ; không bắt người dùng lặp lại cùng yêu cầu để được nghe theo.

## 2. Năm lớp ký ức đề xuất

| Lớp | Nội dung | Cách cập nhật |
|---|---|---|
| Ngữ cảnh hiện tại | Chủ đề, người đang nói, câu hỏi chưa trả lời, trạng thái phát âm thanh | Ngắn hạn; không suy tâm trạng hôm nay thành tính cách |
| Hồ sơ người tham gia | Cách gọi papa, sở thích đã nói, lựa chọn giao tiếp có phạm vi | Có nguồn, thời hạn áp dụng và phiên bản thay thế |
| Trải nghiệm chung | Một lần hiểu lầm, sửa sai, trò đùa chung, buổi chơi hoặc câu chuyện đã kể | Liên kết sự kiện thật; cho phép nhắc lại khi phù hợp |
| Kỹ năng giao tiếp | Khi nào lắng nghe, hỏi thêm, giải thích, đùa hoặc chờ | Bài học có điều kiện, kết quả thử và phản ví dụ |
| Quan điểm của Mao và việc còn dang dở | Sở thích nhân vật, điều còn tò mò, chủ đề muốn kể tiếp | Phân biệt tự chọn/suy luận với sự kiện; không tự nhận đã thực hiện lời hứa |

Trích lời người dùng chứng minh họ đã nói câu đó, không chứng minh mọi nội dung trong câu là sự thật. Ký ức riêng và chat công khai phải có scope khác nhau. Tên “papa” chỉ là cách gọi, không phải chứng thực danh tính.

## 3. Luồng xử lý đề xuất

Trước khi đáp: xác định phiên/người tham gia từ adapter đáng tin → đọc ngữ cảnh gần → truy hồi vài ký ức phù hợp → phân biệt yêu cầu hiện tại với thói quen cũ → chọn mục đích giao tiếp → tạo lời thoại và cử chỉ.

Sau khi đáp: ghi việc đã phát/đã bị ngắt/không rõ trạng thái → nối phản hồi tiếp theo khi đủ rõ → cập nhật đoạn tương tác → tạo bài học ứng viên → kiểm tra nguồn và phạm vi → lưu nếu có giá trị. Việc tổng hợp nên chạy sau lượt nói hoặc lúc rảnh để tránh kéo dài thời gian phản hồi.

Mục đích giao tiếp có thể là trả lời, chia sẻ ý riêng, phản ánh điều vừa nghe, hỏi làm rõ, đùa, sửa sai hoặc chờ. Không buộc mọi câu kết thúc bằng câu hỏi. Cử chỉ phải phù hợp với lời nói; thiếu tín hiệu âm thanh/hình ảnh thì không bịa rằng đã nghe tiếng cười hoặc thấy nét mặt.

Không cần lưu độc thoại suy luận dài. Có thể lưu quyết định ngắn, nguồn tham chiếu và điểm chưa chắc để kiểm tra hành vi; những ghi chú này vẫn là đầu ra của mô hình, không phải phép đo trực tiếp quá trình bên trong.

## 4. Dữ liệu tối thiểu

Đề xuất mở rộng PostgreSQL hiện có, chưa cần thêm một hệ database khác:

- `interaction_events`: event_id, session_id, participant_id từ host nếu có, visibility_scope, event_time, event_type, message reference, turn_id, playback state. Đầu vào nghe không rõ phải có cờ riêng.
- `conversation_episodes`: event references, participants, topic, explicit request, inferred intent (tách riêng), Mao action, observed outcome, unresolved questions. Một episode có thể có kết quả `unknown`.
- `memory_facts`: subject, claim type, source event, valid_from/valid_until, recorded_at, supersedes, visibility, retention. Tránh ghi đè mất lịch sử hoặc lấy ngày lưu làm ngày sự kiện.
- `conversation_lessons`: trigger conditions, action, evidence events, counterexamples, status candidate/tested/retired, observed outcomes, policy version.
- `open_threads`: chuyện còn muốn kể, câu hỏi chưa giải đáp, người liên quan, điều kiện nhắc lại, thời hạn, trạng thái. Lời hứa không tự tạo automation nếu chưa có scheduler hỗ trợ.

Embedding giúp tìm theo ý nghĩa nhưng không thay thế lọc đúng người, thời điểm, nguồn và phiên bản. Không đưa toàn bộ transcript vào prompt mỗi lần. Khi xóa một nguồn ký ức, cần xóa hoặc tính lại các bản tóm tắt/bài học phụ thuộc, tránh để thông tin đã quên còn xuất hiện qua bản dẫn xuất.

## 5. Hiểu phản hồi mà không đọc tâm trí

| Tín hiệu | Có thể suy ra | Không được tự suy ra |
|---|---|---|
| “Gọi papa nhé” | Yêu cầu cách xưng hô | Bằng chứng danh tính của người lạ cùng nickname |
| “Đừng khuyên lúc này” | Điều chỉnh hành vi hiện tại | Không bao giờ muốn lời khuyên |
| “Câu đó vui, kể tiếp đi” | Phản hồi tích cực với câu đó | Mọi kiểu trêu đều được thích |
| Người dùng sửa nội dung | Có yêu cầu kiểm tra/sửa | Điều sửa luôn đúng về mặt sự thật |
| Ngắt lời | Lượt nói bị ngắt | Chắc chắn bực mình hoặc câu trả lời dở |
| Im lặng/rời phiên | Chưa có phản hồi quan sát được | Chán Mao, đồng ý, hài lòng hoặc buồn |

Phản hồi gián tiếp chỉ nên hỗ trợ giả thuyết với mức chắc chắn thấp. Không tối ưu số phút giữ chân hoặc số tin nhắn như đại diện duy nhất cho chất lượng quan hệ. Mục tiêu đề xuất là đúng ý, phù hợp, ít lặp, nhớ đúng và tôn trọng lựa chọn người dùng. Không dùng thử nghiệm gây buồn/ghen hay gây áp lực để người dùng tiếp tục tương tác.

## 6. Đối chiếu mã hiện tại

- `agent/hybrid/runtime.py`: truy hồi theo đầu vào; công cụ `remember` chỉ nhận trích đoạn lời người dùng và lưu dạng claim chưa xác minh. Đây là nền provenance hữu ích. Nên giữ đường ghi này và thêm bộ tổng hợp trải nghiệm từ event đã kiểm tra, không mở quyền cho model tự ghi “sự thật đã xác minh”.
- Cũng trong runtime: social memory hiện dùng subject `shared`, bí danh công khai; chưa có ID người xem tin cậy xuyên suốt. Cần giải quyết phân biệt người trước khi triển khai hồ sơ cá nhân lâu dài trong livestream. ID nền tảng nếu có cũng không tự chứng minh hai tài khoản khác nền tảng là một người.
- `character/emotion.py`: chọn một số chế độ biểu đạt bằng từ khóa/sự kiện; có ưu tiên tương tác và giảm về trạng thái bình tĩnh sau một khoảng thời gian. Chưa phải bộ hiểu ý định/cảm xúc nhiều lượt. Cần kiểm tra phủ định, trích dẫn, mỉa mai tiếng Việt và sự không chắc chắn.
- `_feedback` hiện điều chỉnh mức trêu từ một số yêu cầu rõ ràng; `hybrid/learning.py` ghi số liệu vận hành và điều chỉnh độ dài lời chủ động. Chưa đo trực tiếp việc nghe đúng nhu cầu trong một đoạn hội thoại.
- `conversations/single_conversation.py` lưu phản hồi và số liệu; `conversation_utils.py` có đợi báo phát xong và timeout; đường interrupt có `heard_response`. Nên nối các tín hiệu này vào episode để phân biệt generated/delivered/interrupted/unknown. Tín hiệu frontend chỉ chứng minh trạng thái player, không chứng minh người dùng đã chú ý/nghe hiểu.
- `BasicMemoryAgent` có cửa sổ gần và tóm tắt, nhưng cần đường nối từ sự kiện đến kết quả/bài học để việc nhớ làm thay đổi hành vi có thể kiểm chứng.

## 7. Trải nghiệm riêng của Mao hình thành thế nào?

Mao có thể tích lũy lịch sử lựa chọn của nhân vật: đã chọn kể chuyện gì, vì sao, phản hồi nào đã xảy ra, đã thay quan điểm ở đâu. Ví dụ sở thích “Mao thích cùng papa nghĩ ra đoạn kết bất ngờ” có thể gắn với những lần hai bên thực sự viết truyện. Nên diễn đạt là lựa chọn/sở thích nhân vật dựa trên tương tác, không bịa cảm giác cơ thể hoặc coi số lần được khen là bằng chứng cảm xúc chủ quan.

Nhân vật cần giữ nét riêng khi phản hồi chưa rõ; không đổi toàn bộ persona sau một lời chê hoặc luôn tán thành papa. Sự gần gũi nên thể hiện qua việc nhớ đúng, giữ lời trong khả năng và sửa hiểu lầm; không cần một thang “tình yêu” suy ra từ lượng chat.

## 8. Mốc triển khai và đánh giá

Ưu tiên 1: nối event, người tham gia và trạng thái phát với episode. Ưu tiên 2: ghi nhận sửa đổi có phạm vi, ký ức thời gian và truy hồi đúng người. Ưu tiên 3: bài học giao tiếp có phản hồi và chuyện còn dang dở. Sau đó mới mở rộng cách chọn biểu cảm, nhịp chờ và thích nghi lâu dài.

Bộ thử đầu tiên nên bao gồm: đổi cách gọi; không chuyển ký ức papa sang khán giả; không coi “hôm nay” là “luôn luôn”; đổi sở thích có lịch sử; kể chuyện dang dở qua restart; không nhận phần lời bị ngắt là đã nói hết; không coi timeout là phát thành công; hỏi lại khi ASR không rõ; phản hồi mỉa mai; tránh nhắc kỷ niệm không liên quan; quên nguồn và bài học dẫn xuất; giữ ý kiến trước áp lực nhưng đổi khi có bằng chứng; xử lý câu hỏi không có đáp án trong bộ nhớ.

Đánh giá bằng cả bài kiểm tra có đáp án và đánh giá hội thoại nhiều lượt của người thật. Dữ liệu mô phỏng phải gắn nhãn và không được trộn vào lịch sử tương tác thật. So sánh cùng mô hình ở ba cấu hình: cửa sổ ngắn; truy hồi hiện tại; truy hồi + episode + bài học. Kiểm soát độ dài prompt, độ trễ, chi phí và phiên bản. Đo từng tiêu chí: nhớ đúng, nhầm người, thông tin lỗi thời, bịa ký ức, sửa sai, lặp câu hỏi, phù hợp phản hồi và nhịp hội thoại. Điểm hỏi-đáp ký ức không thay thế đánh giá mức tự nhiên.

## 9. Cơ sở nghiên cứu

- [Beyond Goldfish Memory, ACL 2022](https://aclanthology.org/2022.acl-long.356/): đối thoại nhiều phiên và truy hồi/tóm tắt lịch sử là cơ sở để duy trì sự liên tục.
- [LoCoMo, ACL 2024](https://aclanthology.org/2024.acl-long.747/): đánh giá nhớ, tóm tắt sự kiện và hội thoại đa phương thức dài hạn; mô hình còn khó với quan hệ thời gian và nhân quả. Không đủ chỉ tăng cửa sổ hoặc có RAG rồi coi đã giải quyết trí nhớ.
- [LongMemEval, ICLR 2025](https://arxiv.org/abs/2410.10813): đánh giá trích xuất, suy luận nhiều phiên, thời gian, cập nhật và biết không trả lời khi thiếu dữ liệu. Gợi ý rõ các tiêu chí kiểm tra cho Mao.
- [EverMemBench, bản sửa 03/2026](https://arxiv.org/abs/2602.01313): nghiên cứu hội thoại nhiều người/nhiều nhóm, thông tin thay đổi và vai trò. Củng cố nhu cầu phân biệt người, phiên bản và truy hồi thông tin liên quan ngầm. Đây là benchmark cộng tác, không trực tiếp đo sự thân thiết của AI companion.
- [Towards Emotional Support Dialog Systems, ACL 2021](https://aclanthology.org/2021.acl-long.269/): nghiên cứu chiến lược hỗ trợ hội thoại. Áp dụng ở đây là chọn cách phản hồi theo nhu cầu; không suy ra hiệu quả điều trị hay buộc mọi cuộc trò chuyện thành tư vấn.
- [Hear You in Silence, bản thảo 02/2026](https://arxiv.org/abs/2602.06134): nghiên cứu 50 người trong hai tình huống cho thấy điều chỉnh nhịp đáp theo ngữ cảnh cải thiện một số đánh giá cảm nhận so với nhịp cố định. Phạm vi nhỏ, chưa chứng minh cùng hiệu quả trong livestream tiếng Việt; cần đo lại trên Mao.

Các đề xuất cấu trúc dữ liệu, thứ tự triển khai và quy tắc phản hồi ở trên là tổng hợp kỹ thuật cho dự án, không phải cấu hình được các bài báo chứng minh trực tiếp.
