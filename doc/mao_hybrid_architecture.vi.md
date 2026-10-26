# Mao hybrid: PostgreSQL, pgvector và trình duyệt có kiểm soát

## Kiến trúc và phạm vi

`BasicMemoryAgent` vẫn là agent chính. Model `mao-companion`/Qwen, ASR, giọng
VieNeu/RVC Linh Lan Ch, tách câu, các token cảm xúc/cử chỉ và Draco 3D tiếp tục
dùng pipeline hiện tại. Mỗi kết nối có agent/hội thoại/browser/nonce duyệt riêng;
stateless model client, ASR và TTS vẫn dùng chung để không tải lại model nặng.
Ngắt kết nối, lỗi kết nối và shutdown server đóng pool/browser thuộc phiên đó.
Hybrid là phần mở rộng có công tắc, không thay model hay
sửa persona trong `prompts/mao_context.vi.md`.

Luồng: đầu vào → đọc ngữ cảnh/nhớ liên quan → persona gốc + chính sách hybrid →
Qwen → công cụ có giới hạn → lời thoại → xử lý cảm xúc/cử chỉ/TTS/avatar cũ.
Các lệnh trình duyệt và ký ức dùng công cụ `mao_hybrid`, tích hợp cả native tool
calling và chế độ prompt hiện có. Giới hạn mặc định 6 vòng, tối đa 4 công cụ/vòng.

## Vì sao PostgreSQL + pgvector và tìm kiếm kết hợp

PostgreSQL lưu ký ức, trạng thái tính cách, mục tiêu, kết quả đánh giá, nhật ký và
yêu cầu duyệt; pgvector lưu embedding trong cùng cơ sở dữ liệu. Có giao dịch,
unique key, giới hạn lưu trữ, TTL và khóa giữa nhiều phiên. Không có SQLite hay
cơ chế âm thầm đổi sang cơ sở dữ liệu khác.

Ba loại ký ức là `long_term`, `social`, `skill`. Mỗi bản ghi có scope, subject,
nguồn, ngày tạo/hết hạn, profile embedding, bí danh công khai, bằng chứng trích
nguyên văn và nội dung. Hai bí danh nói cùng một câu không bị dedup chung.
Nguồn người xem/model luôn
là `unverified_claim`; chỉ người vận hành mới ghi dữ kiện `operator`. Chỉ bộ
đánh giá hoặc operator được tạo skill, không lấy lời tự nhận thành kỹ năng thật.

Truy hồi dùng Qwen3 Embedding 0.6B (1024 chiều) qua Ollama `/api/embed`, cosine
distance của pgvector, PostgreSQL full-text và pg_trgm. Từ khóa tiếng Việt được
chuẩn hóa dấu, `đ`, loại một tập hư từ và truy vấn OR. Hợp nhất bằng weighted
Reciprocal Rank Fusion: `1/(60+semantic_rank) + 1.2/(60+lexical_rank)`. Điều này
giúp giữ tên riêng/từ khóa chính xác và vẫn tìm được cách diễn đạt khác.
Với câu dài, nhánh từ khóa cần ít nhất `lexical_min_overlap` từ nội dung (mặc định
2); câu ngắn/tên đã biết có ngưỡng riêng. Không dùng điểm RRF như xác suất đúng.
Điều này giảm kết quả giả do một từ phổ biến hoặc do bỏ dấu tiếng Việt gây nhập nhằng.

Profile gồm model tag, digest thực tế từ Ollama và chiều vector. Digest được
đối chiếu trước/sau sinh vector; thay model giữa chừng bị từ chối. Có thể pin
`embedding_digest` trong config. Vector của profile khác không được trộn vào nhánh
ngữ nghĩa, kể cả khi model tag không đổi. Sai số chiều/NaN/
vector rỗng bị loại. Khi embedding ngừng hoạt động, văn bản vẫn lưu vào PostgreSQL,
trạng thái báo `unavailable_keyword_only`, và `reembed` bổ sung vector sau.

Mặc định tìm vector **exact**: với 2.000 ký ức/scope, ưu tiên độ đầy đủ và bộ lọc
đúng trước khi tối ưu ANN. Đã tạo HNSW cosine index và có `search_mode: ann` với
iterative scan cho dữ liệu lớn. Scope, subject, kind, source và TTL được lọc trong
cả hai nhánh truy hồi. HNSW không làm mọi truy vấn nhanh hơn; cần đo trên dữ liệu thật.

Hiện nickname chỉ là **bí danh công khai chưa xác minh**. Agent lưu social claims
vào subject `shared`, lưu bí danh ở metadata riêng. Khi truy vấn có bí danh đã biết,
bộ lọc áp dụng trước cả hai nhánh xếp hạng để tránh lấy sở thích của tên khác.
Ký ức do model ghi phải trích nguyên văn đầu vào người dùng hiện tại; nội dung
trang web và lời model tự tạo không được đưa vào đường ghi này. Prompt sản xuất
của host bị loại, chỉ lấy phần bình luận thật trong payload YouTube/TikTok.
Không dùng nickname làm khóa
bí mật hay xác thực. Storage hỗ trợ subject riêng, nhưng chưa nối ID người xem
đã xác thực từ từng nền tảng vào agent. Không nên dùng bản này cho hồ sơ riêng tư
giữa nhiều tài khoản. Mẫu nhận diện credential thông thường bị chặn trước khi lưu;
đây không phải bộ phát hiện mọi loại dữ liệu nhạy cảm.

## Persona, cảm xúc và hài hước

Persona gốc không bị thay bởi ký ức/feedback. `playfulness` thích nghi trong khoảng
0.2–0.8; feedback phải khớp yêu cầu tăng/giảm trêu trong lời người dùng hiện tại,
tối đa một lần/lượt và mỗi lần chỉ đổi 0.03. Cập nhật có khóa PostgreSQL chống
mất thay đổi giữa các phiên. Trạng thái buồn/nghiêm túc hướng model giảm trêu.
Ngữ cảnh điều khiển cách diễn đạt và giữ token biểu cảm hiện
có; không huấn luyện lại trọng số hay thay voice.

Phép cộng/trừ/nhân đơn giản trong yêu cầu ngắn có đường tính xác định, không dùng
`eval`. Khi được mời đùa, Mao có thể nói một đáp án giả có gắn tín hiệu trêu rồi
đưa ngay đáp án đúng; yêu cầu nghiêm túc kế tiếp sẽ chỉ sửa/đáp đúng. Không lưu đáp
án đùa. Với nội dung phức tạp, hành vi hài hước/cảm xúc là chính sách cho Qwen,
không phải bảo đảm mọi đầu ra mô hình đều đúng. Điểm game và kết quả công cụ luôn
lấy dữ liệu thật.

## Mục tiêu, khám phá và đánh giá

Qwen đề xuất objective và tối đa 3 bước: `recall`, `navigate`, `observe`,
`screenshot`. Tạo plan không tự chạy plan. Khám phá mặc định tắt; khi bật, chạy
qua công cụ `explore` hoặc lượt chủ động mà host hiện tại cấp. Công cụ này không
tự sửa code, tự cài phần mềm hoặc nâng quyền. Ngoài công cụ này, dịch vụ tò mò
đọc nguồn công khai có vòng nền riêng, opt-in bằng `hybrid.autonomy.enabled`;
xem `mao_autonomy.vi.md`. Dịch vụ không mở quyền browser/Windows tổng quát.

Mỗi plan có cursor và trạng thái bền vững. Giới hạn mặc định 30 giây, cooldown 60
giây; khóa và lease PostgreSQL dùng đồng hồ database chống hai client thực hiện
cùng plan. Lease có token sở hữu; worker cũ không được ghi đè plan đã hủy/thay thế.
Timeout/crash chuyển stopped, hủy rõ ràng chuyển cancelled; không tự chạy lại
hành động cũ sau restart. Một bước cần duyệt dừng `needs_operator`.

Mỗi bước được đánh giá theo kết quả công cụ: recall rỗng không tính thành công;
quan sát phải có nội dung; nếu plan có `expected_text` thì bằng chứng phải khớp.
Không đạt thì dừng `needs_revision`. Thành công cơ học không đồng nghĩa đã xác minh
nội dung trang. Skill journal chỉ lưu recipe gọn không thực thi và `verified_truth:false`;
feedback người xem cũng không được tự nâng thành kiến thức đã xác minh.

## Computer use

Phạm vi hiện tại là **trình duyệt Chromium riêng**. Ưu tiên DOM/selector, có ảnh
PNG chuyển vào native tool image path của Qwen; khi selector không duy nhất trả
`vision_required`. Model có thể yêu cầu `vision_click` theo ảnh mới và vẫn cần
duyệt. Không có điều khiển toàn màn hình Windows, clipboard, shell, arbitrary JS,
tải file hoặc chọn file. Model cần hỗ trợ ảnh để dùng fallback thị giác thực tế.
Observation cung cấp selector và URL của link; cuộn trang có giới hạn ±720 px,
không được cấp quyền gửi mạng, trả ảnh mới và fingerprint gồm vị trí cuộn.

Mặc định `computer.enabled:false`, allowlist rỗng. Chỉ nhận http(s) và origin
chính xác, gồm scheme/port; không ngầm cho subdomain. Chặn credential trong URL,
service worker, WebSocket, popup, download và quyền thiết bị. HTTP redirect bị
chặn; hãy điều hướng trực tiếp tới URL cuối đã cho phép. Mỗi POST/PUT/PATCH/DELETE
cần duyệt riêng **đúng request**, gồm session, method, URL, body và hash headers.
Duyệt click không tự duyệt request; một request được duyệt không cấp quyền cho
request gửi ké. Fill không được tự gửi autosave. Tối đa 4 request có thể được đề
xuất trong một thao tác, body tối đa 8 KB. GET vẫn có thể có
tác dụng phụ ở website thiết kế sai; chỉ cho phép origin mà operator tin cậy.

Mọi click/fill/vision click và URL chứa query/fragment đều cần duyệt một lần.
Yêu cầu gắn với phiên browser, nội dung thao tác, URL và fingerprint DOM hiện tại, hết hạn sau
120 giây. Có giới hạn 12 lần gọi/phút/scope trong PostgreSQL. Không dùng ảnh/DOM
cũ để tương tác. Vision click yêu cầu ảnh đã lấy từ quan sát hiện tại.
Fingerprint được kiểm tra lại sau khi đọc quyền duyệt; vision kiểm tra cả hash ảnh.
Các request tức thời được chờ tối đa 1.5 giây để ghi nhận kết quả trước khi trả về.
Quan sát UI hoặc HTTP 200 không tự chứng minh giao dịch nghiệp vụ đã thành công.

DOM, ảnh, kết quả web và ký ức luôn được đóng nhãn dữ liệu không đáng tin. Chúng
không thể đổi allowlist, bật computer hoặc duyệt yêu cầu. Công cụ không có API
`approve`. Tài khoản PostgreSQL của runtime không có quyền UPDATE/INSERT cột
approved hay đổi schema; operator dùng kết nối riêng. Prompt injection vẫn có
thể ảnh hưởng lời nói hoặc đề xuất của LLM, nên ranh giới cứng nằm ở adapter,
quyền database và xác nhận của người vận hành.

Các MCP read tools cũ được giữ qua allowlist riêng (`search`, `fetch_content`,
`get_current_time`, `convert_time`). Operator phải kiểm tra đúng công cụ/server
trước khi thêm tên; allowlist này không tự chứng minh một MCP tool là an toàn.

## Thiết lập trên Windows

Trong thư mục dự án, dùng Python của `.venv` hoặc uv đã có ở `private/tools/uv/bin`:

```powershell
.\private\tools\uv\bin\uv.exe sync --python .venv/Scripts/python.exe --extra hybrid --extra computer
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/mao_hybrid.py init-env
docker compose -f compose.mao-hybrid.yaml up -d
.\.venv\Scripts\python.exe scripts/mao_hybrid.py migrate
.\.venv\Scripts\python.exe scripts/mao_hybrid.py enable
.\private\tools\ollama\ollama.exe pull qwen3-embedding:0.6b
.\.venv\Scripts\python.exe scripts/mao_hybrid.py status
```

Docker Desktop cần chạy. `init-env` tạo mật khẩu ngẫu nhiên vào
`private/mao-hybrid.env` và từ chối ghi đè file cũ. Trên máy đã thiết lập, bỏ qua
bước đó. PostgreSQL 17/pgvector 0.8.7 nằm ở `127.0.0.1:55432`, database `mao`,
volume `mao-hybrid_mao_pgdata`. Không dùng `docker compose down -v` nếu muốn giữ
ký ức. Dừng dịch vụ bằng `docker compose -f compose.mao-hybrid.yaml stop`.

Tài khoản runtime `mao_app`; operator/migration dùng `mao_owner` riêng. Giữ file
env trong thư mục private đã bị Git ignore, giới hạn quyền tài khoản Windows
truy cập file này. Không đưa DSN vào persona hoặc công cụ. Với server PostgreSQL
khác, đặt `MAO_DATABASE_URL` và `MAO_DATABASE_ADMIN_URL`, rồi cấp các quyền tương
đương lệnh migrate. Runtime không cần quyền superuser.

`enable` thêm block từ `config_templates/mao.hybrid.yaml` vào config chính và Mao
live, không đổi model/voice. Cần khởi động lại backend để nạp agent mới. Có thể
tắt bằng `hybrid.enabled:false`; raw history và pipeline cũ không bị xóa.

Ollama dùng model store hiện có `models/ollama` nếu khởi động qua script local.
Embedding service và chat model là hai vai trò riêng; không thay `mao-companion`
bằng embedding model. Nếu đổi model/chiều embedding phải có migration/re-embedding;
bản schema này cố định 1024 chiều. Không thay nội dung một model tag đang dùng
âm thầm; dùng tag mới để `reembed` nhận diện các bản ghi cần chuyển.

## Bật trình duyệt và phê duyệt

Sửa block `hybrid.computer` trong config đang dùng, đặt enabled true và danh sách
origin cụ thể. Ví dụ `https://example.com`; không thêm cả internet bằng wildcard.
Giữ `cdp_url:''` để tạo Chromium riêng. Nếu muốn CDP, tự chạy trình duyệt debug
riêng và đặt HTTP endpoint localhost, ví dụ `http://127.0.0.1:9222`; adapter tạo
context mới, không nhận context/cookie/tab đang có của người dùng.

```powershell
.\.venv\Scripts\python.exe scripts/mao_hybrid.py pending
.\.venv\Scripts\python.exe scripts/mao_hybrid.py approve <request_id>
.\.venv\Scripts\python.exe scripts/mao_hybrid.py deny-all
.\.venv\Scripts\python.exe scripts/mao_hybrid.py cancel
```

Lệnh approve in **chính xác** thao tác/đích/dữ liệu cần duyệt và yêu cầu operator
gõ `APPROVE`. Sau đó Mao phải thử lại trước khi hết hạn; việc echo request_id
trong chat không có hiệu lực. Nhật ký ở `mao_hybrid.events`, request payload ở
`mao_hybrid.approvals` chỉ giữ trong thời hạn cần thiết. Không ghi ảnh hoặc text
nhập vào nhật ký hành động thông thường; payload duyệt có thể chứa text cần xem.
Đã bỏ ghi raw tham số công cụ và toàn bộ messages ở các adapter OpenAI-compatible/
Claude. Lỗi xác thực tham số cũng không lặp lại giá trị đầu vào. Log ứng dụng cũ
và các MCP server ngoài vẫn cần được quản lý theo chính sách riêng.

Nếu công cụ trả `network_confirmation_required`, request chưa được gửi. Xem và
duyệt request đó, lấy observation mới và thử lại thao tác giao diện (có thể cần
duyệt click mới). Form navigation hoặc website không chịu được request bị chặn
có thể cần tải lại trang. Sau timeout của request đã gửi, phải kiểm tra trạng thái
thực tế trước khi thử lại; không coi đó là một request chắc chắn chưa thực hiện.

## Vận hành, kiểm thử và giới hạn

```powershell
.\.venv\Scripts\python.exe scripts/mao_hybrid.py reembed
.\.venv\Scripts\python.exe scripts/evaluate_mao_retrieval.py
.\.venv\Scripts\python.exe scripts/evaluate_mao_retrieval.py --keyword-only
.\.venv\Scripts\python.exe scripts/check_mao_hybrid_live.py
$env:MAO_TEST_POSTGRES='1'
$env:MAO_TEST_BROWSER='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_hybrid_*.py'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.mjs
```

`reembed` xử lý tối đa 50 ký ức chưa có vector/đang dùng model khác mỗi lần; lặp
đến khi hết. Pool giới hạn 4 connection/agent, PostgreSQL statement timeout 5s,
embedding timeout 4s; I/O được đưa sang worker thread để không chặn audio loop.
Khi PostgreSQL không sẵn sàng, ngữ cảnh báo unavailable và hội thoại vẫn có thể
tiếp tục; công cụ phụ thuộc lưu trữ không được tự bỏ qua quyền duyệt.

Đo thật ngày 25/10/2026: 10 ký ức giả lập, 20 câu hỏi (tên dễ nhầm/câu không dấu)
và 6 câu ngoài phạm vi. Hybrid: Recall@3=1.0, top-1=0.95, MRR@3=0.975, từ chối
6/6 câu ngoài phạm vi, median khoảng 74 ms khi model nóng. Chỉ từ khóa: Recall@3=0.90,
top-1=0.85, MRR@3=0.875. Đây là bộ đo nhỏ dùng hiệu chỉnh, không phải held-out benchmark
hay chứng minh chất lượng trên toàn bộ chat thực tế. Có kiểm thử riêng dùng vector xác định để kiểm tra
SQL/RRF/TTL/phân vùng; chúng không được tính là đánh giá model thật.

Chưa tích hợp định danh viewer riêng tư, reranker học máy, tối ưu ANN ở quy mô
lớn, dashboard duyệt trong avatar UI, hoặc điều khiển ứng dụng Windows ngoài
trình duyệt. Đã kiểm thử WebSocket → agent → biểu cảm → VieNeu → RVC với hai client
thật: nhận hai đoạn WAV 40 kHz, expression action và không truyền audio sang client
còn lại. Chưa đánh giá chất lượng nghe dài hạn hoặc chạy một buổi livestream dài.
Đã thử CDP với Chromium thật, xác nhận context mới không lấy cookie của owner và
đóng adapter không đóng browser của owner. Chưa kiểm chứng mọi phiên bản Chrome/Edge.
Skill learning hiện là nhật ký kết quả đã đánh giá, không phải model tự sửa mình.

## Tài liệu gốc đã đối chiếu

Đã bổ sung migration 004 và vòng đo/tổng kết hằng ngày, phản hồi operator và
phiên bản giới hạn lời mở chuyện. Xem [hướng dẫn học và diễn tập](mao_daily_learning_and_rehearsal.vi.md).
Cảnh OBS riêng đã ghi thử 720p/30 fps bằng pipeline thật, không phát công khai.
Lần đo 120 giây vẫn có 69/3600 khung hình render bỏ lỡ (~1,9%); chưa kết luận
sẵn sàng phát dài. Không có bảo đảm chất lượng sẽ tăng mỗi ngày.

- [pgvector: exact/ANN, filter, iterative scan và hybrid search](https://github.com/pgvector/pgvector)
- [pgvector-python: ví dụ hybrid search/RRF](https://github.com/pgvector/pgvector-python)
- [PostgreSQL full-text query và ranking](https://www.postgresql.org/docs/current/textsearch-controls.html)
- [PostgreSQL pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Qwen3 Embedding 0.6B: đa ngôn ngữ, chiều vector và query instruction](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Ollama embedding API](https://docs.ollama.com/api/embed)
- [Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [Playwright browser/CDP](https://playwright.dev/python/docs/api/class-browsertype)
- [Playwright network routing](https://playwright.dev/python/docs/network)
- [Ollama model tags và digest](https://docs.ollama.com/api/tags)
- [PostgreSQL explicit/advisory locking](https://www.postgresql.org/docs/17/explicit-locking.html)
- [OWASP: prompt injection, tool boundary và least privilege](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
