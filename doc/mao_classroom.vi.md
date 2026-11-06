# Vua Tiếng Việt trong Mao Desktop

Tính năng nằm trong **ứng dụng Mao Desktop**, mở bằng nút **Vua Tiếng Việt** góc trên bên phải. Không có website hoặc trang điều khiển trình duyệt riêng.

## Dùng trong app

1. Mở Mao Desktop ở chế độ cửa sổ.
2. Bấm **Vua Tiếng Việt**. Chọn **Xem bố cục lớp** để xem thiết kế với tên/điểm minh họa mà không mở phiên thật.
3. Chọn kênh `@thanhoathirty6`, bấm **Mở lớp mới** để bắt đầu phiên thật.
4. **Tắt lớp · Mao thường** khôi phục cảnh và trò chuyện thông thường. **Đóng xem bố cục** chỉ đóng phần xem trước.

Mao trong lớp là **model 3D đang dùng trong Desktop**, hiển thị từ khoảng eo trở lên. Cùng một renderer, cùng bộ âm thanh, khớp miệng, biểu cảm và cử chỉ của app; không tạo một Mao thứ hai hoặc phát giọng hai lần. Lời nói xuất hiện trong khung bên dưới Mao. Chỉ số miệng và hành động tiếp tục dùng cơ chế kiểm chứng runtime hiện có.

Bộ đọc TikTok do backend quản lý: dùng chung cho lớp và Phòng của Mao, tắt backend thì dừng tiến trình con. Không tạo thêm idle host. Người xem trên TikTok bình luận để chơi; ứng dụng không tự mở buổi TikTok LIVE hoặc đăng nhập thay người dùng. Phòng cần đang phát để nhận được bình luận thật.

## Cập nhật và khởi chạy

```powershell
# Nạp lại desktop và backend sau khi cập nhật mã:
./scripts/start_mao_classroom.ps1 -ReloadBackend -ControlsOnly
# Sau đó bấm Vua Tiếng Việt trong app.

# Hoặc mở luôn một phiên thật không giới hạn:
./scripts/start_mao_classroom.ps1 -ReloadBackend
```

Các lệnh vận hành vẫn có thể dùng mà không mở trình duyệt:

```powershell
.venv/Scripts/python.exe scripts/mao_classroom.py on --account @thanhoathirty6
.venv/Scripts/python.exe scripts/mao_classroom.py off
.venv/Scripts/python.exe scripts/mao_classroom.py status
```

Quyền bật/tắt đi qua IPC của chính cửa sổ Electron. Main process ký yêu cầu bằng khóa host, không gửi khóa vào DOM hoặc URL. Người xem không có quyền đổi chế độ.

## OBS / TikTok

Dùng **Window Capture → Mao VTuber** như đối với Mao thường. Âm thanh tiếp tục từ nguồn **Mao Voice**. Không tạo Browser Source và không dùng URL lớp học. Khi mở lớp hoặc xem bố cục, app tự chuyển cửa sổ sang khung dọc vừa màn hình; tắt lớp khôi phục kích thước Mao thường trước đó. Vùng phát hình luôn giữ **9:16**, thiết kế cho **1080×1920**, gồm bảng câu hỏi, Mao nửa người và 40 chỗ phía dưới. Thanh tiêu đề app nằm ngoài vùng 9:16 (30px phía trên); khi đưa vào OBS, cắt thanh này rồi khớp vùng lớp học vào canvas dọc.

## Thiết kế và asset

Bố cục dùng bảng xanh có vân phấn, nền giấy kem, viền gỗ và chữ dễ đọc. 40 chỗ ngồi là các ô avatar có tên, số câu đúng và huy hiệu hạng; top 3 dùng màu vàng, bạc xanh và đồng. Bàn trống dùng dấu hỏi nhẹ, không hiển thị người giả.

Học sinh dùng **DiceBear Avataaars 10.x** từ `https://api.dicebear.com/10.x/avataaars/svg?seed=...`. Mỗi tài khoản có một seed UUID ngẫu nhiên, lưu cùng điểm để hình không đổi khi lên/xuống hạng hoặc khởi động lại phiên. Seed không chứa tên, ID TikTok hay bình luận. Dùng ảnh SVG qua thẻ img, không chèn SVG bên ngoài vào DOM. Nếu tải ảnh lỗi, hiện chữ đầu tên thay thế; trò chơi vẫn tiếp tục.

- DiceBear: https://www.dicebear.com/styles/avataaars/
- Avataaars gốc: Pablo Stanley, https://avataaars.com/ (free for personal and commercial use, theo trang DiceBear).
- Không gọi lại API khi chỉ điểm số thay đổi. Khi xem bố cục, mỗi người minh họa cũng có avatar khác nhau.

Sách và cây trang trí lấy từ **Kenney Furniture Pack 1.0**, giấy phép **CC0**, kết xuất lại từ OBJ ở 768px với nền trong suốt. Đã gỡ sprite bàn/ghế và hình học sinh vẽ bằng CSS cũ khỏi phần chỗ ngồi.

- Tác giả/nguồn gốc: https://kenney.nl/assets/furniture-kit
- Bản gói do Kenney đăng: https://opengameart.org/content/furniture-kit
- Download: https://opengameart.org/sites/default/files/kenney_furniturePack.zip
- Giấy phép gốc lưu cùng asset: `web_tool/mao-5070/draco/assets/classroom/KENNEY-LICENSE.txt`.
- Kết xuất lại bằng `scripts/render_classroom_assets.py`; cần gói ZIP trên trong `private/kenney-classroom-furniture.zip`.
- Model Mao tiếp tục dùng ghi công của model Draco trong `web_tool/mao-5070/draco/ATTRIBUTION.txt`.

Các file `classroom.html`, `classroom.css`, `classroom.mjs` độc lập và chức năng mở trình duyệt đã được gỡ. Các module trong `draco/classroom-*` là thành phần giao diện của Electron, không phải website riêng.

## Luật chơi

257 câu/từ có lời giải gần gũi, gồm câu thường và nhóm câu thử thách đời thường. Câu thường có 25 giây, câu khó có 40 giây; câu thường có 2 gợi ý ở giây 0 và 12,5, câu khó có 3 gợi ý ở giây 0, khoảng 13,3 và 26,7. Sau đáp án, nghỉ ít nhất 20 giây và chờ Mao nói xong mới tiếp tục. Chỉ bắt đầu đồng hồ khi giao diện lớp trong app và model Mao đã sẵn sàng.

Mỗi người đúng một câu được +1 câu đúng. Bằng số câu thì xét tốc độ, sau đó thứ tự có điểm. Top 40 có chỗ mang tên, top 3 vào bảng vàng. Không cộng theo số bình luận; gửi lặp không tăng điểm. Có dấu/không dấu và chữ hoa/thường đều được, nhập đúng đáp án hoặc `!doan đáp án`.

Điểm chốt sau mỗi vòng vào `private/mao-classroom.sqlite3`. Khởi động lại khôi phục bảng tổng và chuẩn bị câu mới; vòng dở không tính. Phiên không có giới hạn thời gian và chỉ kết thúc khi chủ phòng bấm tắt. Không có đếm ngược thời lượng phiên hoặc lựa chọn số giờ. Dùng hết kho từ mới xáo lại, nên có thể gặp lại từ ở chu kỳ sau. Giới hạn 1.000 người đoán/câu và 5.000 tài khoản có điểm/phiên.

## Kiểm tra

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p test_classroom.py
.venv/Scripts/python.exe -m unittest discover -s tests -p test_classroom_layout.py
.venv/Scripts/python.exe -m unittest discover -s tests -p test_vua_tieng_viet.py
node --test tests/test_classroom_ui.mjs
node tests/test_mao_desktop_runtime.mjs
node tests/test_draco_room_view.mjs
```

Kiểm tra giao diện dựng component Desktop với IPC giả, nạp model 3D thật, kiểm tra camera, miệng theo audio, phụ đề, tên an toàn và đổi lại Mao thường. Chỉ dữ liệu giả được dùng trong test. Việc đọc bình luận TikTok thật cần kiểm tra khi phòng đang LIVE.

Đã sửa tiêu đề sang Segoe UI hỗ trợ đầy đủ dấu tiếng Việt, bỏ kiểu serif trộn glyph. Bảng vàng có ba ô riêng với avatar, tên và số câu đúng. Đã bỏ toàn bộ cụm chữ ở chân màn hình; trạng thái xem thử chỉ nằm trong nút điều khiển.

Khi mở lớp thật, Mao đọc gợi ý; hết giờ công bố, giải thích đáp án và chúc mừng người đúng nhanh nhất. Trong lúc đang đoán, không đọc lại nguyên lượt đoán và không xác nhận đúng sớm. Các lượt mở chuyện hoặc chat thường đang chờ bị chặn khi lớp hoạt động. Xem bố cục chỉ là bản trình bày với dữ liệu giả, không bật bộ đọc TikTok và không phải kiểm chứng tương tác khán giả thật.

## Nhạc nền

Lớp thật phát lặp đoạn nhạc không lời 2 phút lấy từ bản nhạc đã có tại máy, qua trình phát media của Mao Desktop. Âm lượng mặc định 35%, giữ cố định khi Mao nói. Thanh âm lượng trong nút Vua Tiếng Việt cho phép chỉnh 0–100%; chọn 0 để tắt. Nhạc đi cùng tiến trình Mao để nguồn capture ứng dụng nhận cả giọng và nhạc. Xem bố cục và tắt lớp không phát nhạc.

## Câu hỏi xen kẽ

Bổ sung 24 câu khó về cách nói, cảm xúc và sinh hoạt quen thuộc trong `knowledge/classroom.hard.vi.json`. Ưu tiên một câu khó sau bốn câu thường khi còn câu chưa dùng trong nhóm; vẫn không lặp từ cho tới khi hết kho. Ba gợi ý đi từ tình huống đời thường đến dấu hiệu cụ thể hơn. Mao nói “Câu tiếp theo, chủ đề…”; bảng không hiển thị số thứ tự câu. Số câu đúng của người chơi vẫn là điểm số.

Nhóm câu khó được điều chỉnh về mức trung bình: gợi ý có ví dụ sinh hoạt cụ thể, gợi ý cuối cho một phần cụm từ để điền phần còn thiếu. Giữ nguyên 24 đáp án và cách tính điểm.

Đã bổ sung 20 tục ngữ và dòng ca dao quen thuộc vào nhóm thử thách (giữ toàn bộ câu cũ). Với ca dao, gợi ý nói rõ cần tìm câu/dòng mở đầu; gợi ý cuối cho một phần lời để người xem dễ nhớ ra. Tổng kho 257 câu. Câu thường chỉ phát/hiển thị 2 gợi ý; dữ liệu gợi ý thứ ba cũ vẫn được giữ trong kho.

## Mao đọc gợi ý và giải thích đáp án

Đã khôi phục chế độ dẫn trò chơi: đầu câu Mao đọc chủ đề và gợi ý đầu; các gợi ý tiếp theo được đọc theo thời gian trên bảng. Câu thường có 2 gợi ý trong 25 giây, câu khó có 3 gợi ý trong 40 giây. Hết giờ Mao công bố đáp án, chúc mừng người đúng nhanh nhất và đọc giải thích từ/câu. Giữa các gợi ý, Mao gọi tên người đoán, cảm ơn, nhắc gợi ý và cổ vũ như chế độ dẫn lớp ban đầu. Không đọc lại nguyên lượt đoán hoặc xác nhận đúng trước khi công bố. Không hiển thị hoặc đọc số thứ tự câu. Phần hội thoại LLM với bình luận đã tắt trong phiên chơi; bình luận vẫn dùng để chấm đáp án. Kho câu hỏi, điểm và người chơi được giữ nguyên.

## Mở rộng và bỏ qua kho cũ

Hiện có 2.500 câu mới được chọn để chơi: 2.000 câu thường, 500 câu thử thách; tổng dữ liệu lưu 2.757 câu. Cả 257 câu cũ vẫn nằm trong file nhưng không được chọn, kể cả khi hết một chu kỳ. Danh sách bỏ qua lưu trong `knowledge/classroom-bank-policy.json`. Xem nguồn và cách dựng tại `knowledge/CLASSROOM_BANK_SOURCES.md`.

Tiến độ chọn câu lưu thêm khóa đáp án đã chuẩn hóa, đồng thời giữ dữ liệu index cũ để tương thích. Không lặp trong một chu kỳ 2.500 câu. Khi hết kho, xáo vòng mới và tránh 100 câu gần nhất khi còn lựa chọn khác. Nạp lại giữ nguyên session, bảng điểm, avatar và tiến độ; không mở lớp mới để áp dụng cập nhật.

## Vinh danh dài hạn, 40 chỗ và kết quả minh bạch

Vinh danh dài hạn chỉ thưởng **top ngày**: hạng 1 +10, hạng 2 +6, hạng 3 +3 điểm, một lần sau 00:00 giờ Việt Nam. Không thưởng vinh danh từng câu. Cộng số câu đúng qua các phiên trong cùng ngày; hòa thì xét tổng điểm tốc độ, thời điểm đúng đầu tiên và ID ổn định. Khi máy chủ tắt qua nửa đêm, tự chốt các ngày còn thiếu khi chạy lại. Điểm và sổ chốt ngày lưu nguyên tử, tách theo tài khoản TikTok. Bảng hiện top 3 trên màn hình và top 40 trong điều khiển. Điểm vinh danh theo câu cũ được lưu ở `classroom_honor_before_daily` để kiểm toán; tổng mới giữ các bục LIVE đã được xác minh. Dữ liệu phiên cũ chỉ có tổng tích lũy, nên được chuyển vào ngày bắt đầu phiên; các câu mới ghi chính xác theo ngày chốt câu.

SQLite hiện hành được bổ sung hai bảng `classroom_honor` và `classroom_round_awards`, không xóa bảng/dữ liệu cũ. Điểm lớp, thưởng dài hạn và kết quả câu được ghi chung một transaction; khóa account/session/round ngăn thưởng trùng. Câu chưa hoàn tất không nhận thưởng.

Lớp hiển thị **40 chỗ**, lưới 5 cột × 8 hàng, xếp theo số câu đúng/điểm tốc độ trong ngày. Phía trên là bảng câu hỏi cùng Mao, bình luận trực tiếp, bảng kết quả từng câu và vinh danh dài hạn. Âm thanh, thời gian 25/40 giây và kho 2.500 câu vẫn giữ cấu hình hiện tại.

Bình luận hiển thị ngay, có tên, mã người chơi tạm trong câu, nội dung và mốc thời gian từ lúc bắt đầu. Trong lúc đoán chỉ ghi nhận lượt, không xác nhận đúng sớm; sau hết giờ đánh dấu đúng/chưa đúng và thứ hạng của lần đúng đầu tiên. Bình luận bị giới hạn lượt/ngoài giờ không được tính điểm. Giới hạn hiện hành là tối đa một lượt đoán được chấm mỗi giây, 12 lượt/người/câu. Xếp hạng căn cứ **thứ tự máy chủ Mao nhận đáp án đúng đầu tiên**, không khẳng định là thứ tự hiển thị trên mọi thiết bị TikTok; nếu mốc đồng hồ bằng nhau, dùng thứ tự nhận thực tế. Mã người chơi tạm giúp phân biệt tên trùng, không lộ ID tài khoản ổn định.

Sau câu hiện top 3 đúng kèm thời gian và thưởng. Mục điều khiển **Kết quả 10 câu gần đây** đọc dữ liệu đã chốt qua `GET /api/classroom/results`; kết quả lưu trong SQLite để đối chiếu. API chỉ trả dữ liệu công khai (tên, câu trả lời, thứ hạng, thời gian và thưởng), không trả ID tài khoản ổn định. Bình luận trực tiếp chỉ giữ tối đa 60 lượt trong RAM, hiển thị 4 lượt mới nhất; lịch sử kết quả lưu các đáp án đúng đầu tiên của câu.

## Tên lớn hơn, vinh danh cập nhật trực tiếp và lưu lịch sử phiên

Lưới vẫn hiện đủ 40 người, tăng phần chiều cao cho lớp. Avatar lớn hơn; tên thông thường hiển thị tối đa hai dòng, tên dài tự giảm cỡ và dùng ba/bốn dòng; avatar và tên ở vinh danh cũng lớn hơn. Bảng vinh danh lấy dữ liệu thật cả khi đang xem bố cục, không thay bằng tên minh họa, và cập nhật theo vòng làm mới giao diện (khoảng 750ms) mà không cần nạp lại ứng dụng.

Bổ sung `classroom_sessions` lưu trạng thái từng phiên trước khi mở lớp mới, và `classroom_session_awards` ghi thưởng khôi phục một lần cho bục vinh danh của LIVE cũ. Công cụ operator `scripts/restore_classroom_honor.py` đối chiếu dữ liệu khôi phục với báo cáo tổng cũ trước khi áp dụng, từ chối suy đoán nếu bản ghi còn thiếu có thể thay đổi top 3. Lần khôi phục phiên cũ chỉ cộng 10/6/3 cho bục cuối phiên một lần, không bịa lại thưởng từng câu trong lịch sử. Điểm lớp và phiên hiện hành giữ nguyên. Không đưa dữ liệu khôi phục riêng tư vào kho mã nguồn.

## Avatar cục bộ và Phòng của Mao

Avatar Avataaars được tạo ngay tại máy bằng DiceBear core/styles 10.6.0 (`vendor/dicebear-avataaars.mjs`), cùng seed UUID có sẵn, không chờ API ảnh bên ngoài. Cả ô lớp và vinh danh có ảnh dự phòng cục bộ. Công cụ dựng: `scripts/build_classroom_avatars.mjs`; giấy phép core và ghi công Avataaars kèm trong thư mục vendor. Không đổi dữ liệu người chơi hoặc điểm.

Nhãn chế độ phản ánh cảnh đang mở: **Phòng của Mao** khi lớp tắt, **Vua Tiếng Việt** khi đang học/xem bố cục. Một bộ đọc TikTok do backend quản lý dùng chung: lớp bật thì bình luận vào game; lớp tắt thì bình luận vào hội thoại bình thường, không tạo thêm idle host. Khi tắt lớp, lời đọc game đang phát được ngắt để nhường chế độ phòng. Trong phòng, bình luận Mao đang trả lời chỉ xuất hiện khi giọng trả lời thực sự bắt đầu; có bố cục cho cửa sổ dọc nhỏ, không hiện tiêu đề trống sau khi rời lớp.

Hồ sơ nhân vật đang hoạt động đã bổ sung ngoại hình hiện tại: phiên bản nữ hóa Draco Malfoy (female Malfoy), model nền Draco_Malfoy của xunbile. Nội dung này là thiết lập của operator, không thay tên Mao, tính cách hay ký ức hiện hành.

Phông phòng thường đã bỏ chữ neon MAO VTUBER lớn ở phía sau để cửa sổ dọc nhỏ không cắt chữ. Model, ánh sáng và các trang trí còn lại giữ nguyên.

Cửa sổ mặc định hiện là chế độ window dọc: Phòng của Mao và Vua Tiếng Việt cùng dùng khung 9:16 cộng 30px thanh tiêu đề, vừa màn hình hiện hành. Quay về phòng giữ chiều dọc. Chế độ pet vẫn có thể chọn riêng. Phụ đề thường chỉ hiện văn bản của audio đang phát, tự ẩn khi hết lời, tạm dừng hoặc bị ngắt; không giữ chữ trạng thái/lời cũ ở cuối màn hình.

Nhạc nền hiện phát cả trong Phòng của Mao và lớp thật ở chế độ cửa sổ, âm lượng mặc định 35% hoặc mức operator đã lưu, không tự giảm khi Mao nói. Chế độ xem bố cục và pet không tự phát nhạc.
