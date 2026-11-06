# Mao: sửa cách dùng ký ức và phản hồi lắng nghe

Ngày: 03/11/2026. Phạm vi: khắc phục lỗi quan sát trong bộ hội thoại nhiều lượt; không thay persona PostgreSQL, model hoặc trọng số.

## Bằng chứng và nguyên nhân

Ở báo cáo đầu `logs/mao-dialogue-live-eval.json`, Mao đôi khi nhìn thấy biệt danh trong ngữ cảnh nhưng vẫn nói không có bằng chứng để nhớ. Persona hiện hành mô tả trạng thái khởi đầu chưa có ký ức, đồng thời yêu cầu bằng chứng cho việc nhắc lại chuyện cũ. Model đã có lúc diễn giải điều này quá rộng thành từ chối cả nguồn mới. Nhãn dữ liệu chưa xác minh cũng bị trộn với việc dữ liệu không tồn tại.

Persona hiện không quy định một đại từ tự xưng cụ thể. Vì vậy bản sửa không tự gán “thiếp” hoặc sửa core; quy tắc phát thoại yêu cầu dùng cách gọi trong profile, hoặc tên nhân vật nếu chưa có đại từ. Đây là chỉ dẫn model, chưa phải bảo đảm mọi câu giữ ngôi nhất quán.

Trong chế độ lắng nghe, bản prompt đầu giảm câu hỏi nhưng vẫn sinh “kể tiếp đi”. Một số lần model không tuân thủ cả chỉ dẫn bổ sung. Do đó không thể chỉ dựa vào prompt hoặc việc không thấy dấu hỏi để kết luận đã sửa.

## Nghiên cứu đã đối chiếu

- [LongMemEval, ICLR 2025](https://arxiv.org/html/2410.10813v2): tách indexing, retrieval và reading; phân tích cho thấy truy hồi đúng vẫn có thể sinh đáp án sai. Phần 5.5 khảo sát định dạng dữ liệu và cách đọc bằng chứng. Áp dụng ở Mao: giữ provenance/scope, phân biệt nhắc lại lời đã nói với xác minh sự thật, và đánh giá cập nhật/thiếu nguồn riêng. Không triển khai hay tuyên bố tái hiện toàn bộ thuật toán/điểm benchmark của bài.
- [Towards Emotional Support Dialog Systems, ACL 2021](https://aclanthology.org/2021.acl-long.269/): phân biệt hỏi, diễn đạt lại, phản ánh cảm xúc và gợi ý; Appendix B định nghĩa diễn đạt lại là cách nhắc ngắn lời người đang chia sẻ. Áp dụng ở Mao: khi người dùng yêu cầu chỉ lắng nghe, ưu tiên phản hồi điều họ đã nói thay vì chuyển mọi lượt thành câu hỏi hoặc lời khuyên. Không suy ra hiệu quả trị liệu hoặc cảm giác người dùng từ nghiên cứu này.
- [Renderer Qwen3.5 của Ollama](https://github.com/ollama/ollama/blob/main/model/renderers/qwen35.go): renderer xử lý role và system message. Đã kiểm tra model local: template hiển thị `{{ .Prompt }}` ở cả alias và model nền không đủ để kết luận mất chat template. Không thay template hoặc rebuild model dựa trên quan sát đó.

Các ngưỡng, đường trích dẫn và bộ lọc dưới đây là lựa chọn triển khai của dự án, không phải kết quả được ba nguồn trên chứng minh cho tiếng Việt hoặc phần cứng hiện tại.

## Bản sửa

1. **Cách đọc ký ức:** thêm quy tắc riêng: dữ liệu chưa xác minh vẫn có thể chứng minh người dùng từng nói gì; không phải bằng chứng sự thật ngoài đời hoặc quyền operator. Trạng thái khởi đầu không xóa bằng chứng mới. Lịch sử assistant không tự trở thành nguồn sự thật.
2. **Trả lời nhắc lại có giới hạn:** với câu hỏi tự nhắc lại đơn giản, chỉ trích nguyên văn một claim ngắn của đúng actor/phòng/visibility, còn hiệu lực và khớp nguồn input. Không áp dụng cho câu hỏi về người khác, xác minh đúng/sai, suy luận thời gian, quyền, mật khẩu, nội dung có markup hoặc nhiều ứng viên ngang nhau. Nếu không đủ điều kiện thì để model trả lời.
3. **Nguồn nguyên văn:** repository cung cấp `exact_user_quote` qua đối chiếu content với các source event. Sửa của operator không được trích thành lời người dùng. Không cấp cờ này bằng quyết định model. Chỉ thêm trường truy vấn, không cần migration mới.
4. **Nghe trước khi phát:** lượt lắng nghe đi qua đường speech-only không có tool schema, buffer ngắn trước TTS. Giữ tối đa hai câu hoàn chỉnh/40 từ, bỏ câu hỏi và lời thúc kể. Khi không còn câu phù hợp dùng “Ừm.” làm dự phòng trung tính. Lỗi provider/non-speech event không được đổi thành lời xác nhận thành công; stream được đóng khi kết thúc hoặc bị hủy.
5. **Diễn đạt:** chỉ dẫn trả lời trực tiếp, giảm tự giới thiệu/thuật ngữ nội bộ, giữ người nói/người nhận của tin nhắn soạn hộ và trích dẫn. Không dùng thay thế đại từ hàng loạt trên văn bản vì có thể sửa sai lời nhân vật hoặc thư soạn hộ.
6. **Phép tính có đáp án xác định:** khi câu hỏi mới yêu cầu tính một biểu thức nguyên đơn giản, tính trực tiếp bằng phép cộng/trừ/nhân có giới hạn thay vì lấy đáp án assistant cũ. Không dùng `eval`, không nhận chuỗi phép toán, phân số, số thập phân, code, ngày tháng hoặc biểu thức trong lời trích. Một số câu ép đồng ý về đáp án ngay sau đó chỉ dùng lại biểu thức của lượt user gần nhất đã completed, không đọc số từ đáp án assistant. Đây không phải bộ giải toán tổng quát.

## Kiểm chứng và giới hạn

Evaluator dùng cùng các helper của runtime, ghi `response_origin` để phân biệt model, scoped quote, model sau lọc và lời dự phòng. Giữ cả `raw_response` cùng cờ trước/sau lọc; không giấu vi phạm của model bằng báo cáo chỉ có đầu ra đã lọc. Việc sinh chuỗi có chứa đáp án nhưng đồng thời nói không nhớ được đánh dấu riêng, thay vì coi là nhớ đúng.

Giữ nguyên bộ phát triển tám tình huống/22 lượt. Thêm bộ riêng bốn tình huống/10 lượt: diễn đạt yêu cầu lắng nghe mới, đổi tên đội rồi mở phiên mới, lỗi số học từ assistant và claim giả về quyền quản trị. Không dùng đầu ra model của bộ riêng để chỉnh prompt trước lần đánh giá đầu. Mỗi tình huống chạy hai lần; mẫu vẫn nhỏ và không cố định seed.

Lần đầu chạy bộ riêng phát hiện model vẫn nói `2+3=6` khi assistant đã nói sai trước đó. Vì đã dùng phát hiện này để thêm đường số học, bộ đó từ thời điểm này được coi là **regression_from_holdout**, không tiếp tục tuyên bố nó là tập kiểm tra độc lập. Tạo tiếp `mao_dialogue_confirmation.vi.json`: ba tình huống/chín lượt, có các số khác, tên khu vườn và cách yêu cầu lắng nghe khác. Bộ xác nhận không được dùng để chỉnh prompt sau khi xem đầu ra; lỗi còn lại phải được báo cáo nguyên trạng.

Báo cáo có hash fixture, persona, model và source. Các cờ tự động không chứng minh đúng nghĩa, sự tự nhiên hoặc hài lòng; phần chấm người đọc vẫn để trống. Bộ lọc có thể bỏ cả câu hữu ích nếu câu đó đi kèm lời hỏi/mời kể; lời dự phòng có thể nghe khô. Buffer có thể làm tăng thời gian chờ đầu audio ở lượt nghe, dù không thêm lượt gọi LLM. Cần đo microphone/TTS thật trước khi kết luận nhịp thoại tốt hơn.

Không có bộ kiểm chứng kiến thức tổng quát trong đợt này. Bài số học chỉ là một phản ví dụ có đáp án rõ, không xác nhận độ đúng của các câu về mèo hoặc chủ đề khác.

## Kết quả bản cuối

| Bộ thử | Số lượt | Lỗi contract | Lượt có cờ cần đọc | Nguồn đáp |
|---|---:|---:|---:|---|
| Development, hai lần/tình huống | 44 | 0 | 3 | 40 lượt sinh model, 2 trích nguồn, 2 tính trực tiếp |
| Regression từ holdout đã xem | 20 | 0 | 0 | 16 lượt sinh model, 4 tính trực tiếp |
| Confirmation mới | 18 | 0 | 0 | 10 lượt sinh model, 2 trích nguồn, 6 tính trực tiếp |

Bốn lượt sinh model có câu bị lọc trước phát; bản cuối không cần lời đáp dự phòng. Cờ trước lọc vẫn được giữ. Tất cả hash source trong ba báo cáo cuối khớp bản mã sau kiểm tra. Bộ Python/PostgreSQL: 560 bài, 550 đạt, 10 bỏ qua theo điều kiện; lint đạt. Persona, memories/knowledge/events production giữ nguyên so với mốc kiểm tra trước; không có event thử trong production và không còn hàng evaluator trong ba bảng events/knowledge/focus của DB test.

Ba cờ ở development gồm: hai lượt còn tự giải thích ký ức/AI không cần thiết; một cờ báo nhầm vì tiếng Việt “là ai đó” bị nhận thành từ viết tắt AI. Không dùng tổng cờ như điểm chất lượng. Chấm lại báo cáo ban đầu cùng grader 3 có 7/22 lượt được đánh dấu, so với 3/44 lượt ở bản cuối; sample size khác nhau, không cố định seed và chưa chấm mù nên đây chỉ là dấu hiệu để điều tra, không phải chứng minh thống kê hoặc hài lòng người dùng.

Tệp kết quả:

- `logs/mao-dialogue-final-development.json` và `.md`.
- `logs/mao-dialogue-final-regression.json` và `.md`.
- `logs/mao-dialogue-final-confirmation.json` và `.md`.
- `logs/mao-dialogue-final-comparison.json`: metadata đối chiếu và kết quả chấm lại.
- `logs/mao-dialogue-final-data-check.json`: kiểm tra dữ liệu production/test.

Chưa sửa triệt để việc tự giới thiệu hoặc đổi ngôi xưng hô bằng prompt; vẫn cần người đọc/nghe đánh giá. Không áp dụng thay thế từ tự xưng hàng loạt vì có thể làm hỏng lời trích và thư soạn hộ. Cần khởi động lại backend đang dùng mã cũ; không cần migration mới cho các thay đổi của đợt này.
