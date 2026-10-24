# Vũ đạo của Mao khi hát

Khi khán giả gọi `!sing`, Mao có thể nhảy một vũ đạo riêng cho từng bài thay vì chỉ lắc hông. Vũ đạo là **dữ liệu** (một file), không phải mã: thêm bài mới chỉ cần thêm một file và một dòng trong danh mục. Vũ đạo điều khiển cả **tay, thân, hông, gối và hai bàn chân**.

## Dùng vũ đạo cho một bài

1. Tạo hoặc chép file vũ đạo vào `web_tool/mao-5070/draco/dances/<tên>.mjs` (định dạng bên dưới). Tên chỉ gồm chữ thường a–z, số và dấu gạch ngang.
2. Trong `knowledge/mao_songs.vi.json`, thêm trường `dance` cho bài:

```json
{
  "id": "ten-bai",
  "title": "Tên bài",
  "file": "ten-bai-mao.wav",
  "bpm": 124,
  "dance": "white-top-dance"
}
```

3. Khởi động lại backend để nạp danh mục. Bài không có `dance` (hoặc file vũ đạo thiếu/lỗi) vẫn lắc hông như trước, không báo lỗi giữa tiết mục.

`dance` là tên module sẽ được nạp trong trình duyệt nên backend chỉ chấp nhận `[a-z0-9-]{1,64}`; tên khác làm cả danh mục bị từ chối, giống các lỗi cấu hình còn lại.

## Vũ đạo có sẵn: `white-top-dance`

Đo từ **cô áo trắng, quần jean ống loe** (người thứ ba từ trái trong nhóm bên dưới của clip tham chiếu), không còn đọc bằng mắt. Mỗi khung hình (30 khung/giây, khoảng 12 giây) được nhận diện khung xương 3D rồi đổi thành hướng cánh tay trên và cẳng tay, nghiêng và xoay thân, dịch và hạ hông, vị trí và độ nhấc hai bàn chân. Nhịp đo từ âm thanh của clip là khoảng **124 BPM**.

Các đoạn chính: đứng chân rộng và vắt chéo tay trước ngực/bụng; bắt chéo chân, nhấc và đá chân; chống hông, đưa tay lên ngực và vươn tay qua đầu; bước chéo chân rồi lunge sâu sang bên; nhún gối trên chân rộng, hông và thân nghiêng theo từng nhịp.

Vũ đạo lặp lại khi bài dài hơn 12 giây, đã nối liền chỗ lặp. Tốc độ chạy theo bài: nhân với `bpm` của bài chia cho nhịp của vũ đạo, giới hạn từ 0,75 đến 1,35 lần. Chưa có bài nào gắn với vũ đạo này vì danh sách bài hát đang trống.

## Chạy mượt khi phát nhạc

- Thời gian phát (`audio.currentTime`) được trình duyệt báo theo từng nấc thô, không đều. Vũ đạo vì thế chạy trên đồng hồ riêng, chỉ được kéo nhẹ về thời gian của nhạc (`setDance(..., {live:true})`); nếu lệch từ 0,25 giây trở lên (tua bài) thì đồng bộ lại ngay.
- Hướng tay được lưu bằng véc-tơ chứ không bằng góc, nên không có điểm kỳ dị khi tay chĩa thẳng về phía camera.
- Tay được đặt như vai + bản lề khuỷu: trục khuỷu là trục gập hướng cánh tay trên thành hướng cẳng tay, giữ liên tục theo thời gian. Cánh tay trên xoay theo khuỷu như tay thật, cẳng tay không tự xoắn quanh mình nó. Cách cũ (quay từng xương ngắn nhất từ tư thế nghỉ) sinh ra xoắn giả tới gần 800°/giây, làm tay trông khựng và giật.
- Bàn tay trễ theo cẳng tay khoảng 70 ms (cổ tay thả lỏng), không lệch quá 35°.
- Bản xem trước và clip quay tiến thời gian vũ đạo ở từng bước mô phỏng 1/120 giây, nên tóc và vải nhận chuyển động liên tục.
- Khi vũ đạo bắt đầu hoặc dừng, lớp vũ đạo hòa vào/ra trong khoảng nửa giây thay vì giật.
- Khi nâng tay lên cao, vai nhấc nhẹ; khi bàn chân đặt xa hơn chân với tới, hông tự hạ thêm (tối đa 12% chiều cao thân) để chân vẫn đặt đúng chỗ.
- Trong lúc nhảy, áo choàng được giữ gọn để vạt áo và ống tay không bay lên che tay (`GARMENT` trong `dance-body.mjs`). Hết nhảy, áo trở lại độ rủ bình thường.
  - Vạt áo: cứng hơn, tắt dao động nhanh hơn, góc lệch tối đa 0,05 rad thay vì 0,18.
  - Ống tay (chuỗi `cuff` treo ở khuỷu): cứng gấp 5 lần, nhẹ hơn một nửa.
  - Đo trên cả bài, tốc độ đung đưa trung vị của ống tay giảm từ 363 xuống khoảng 40°/giây, của vạt áo từ 65 xuống 21°/giây.
- Ống tay hình loa của áo choàng được **thu hẹp** khi nạp model (`narrowSleeves` trong `garment-rig.mjs`, áp dụng cả lúc không nhảy).
  - Phần vải sát cánh tay (trong 18% chiều dài cẳng tay tính từ trục cẳng tay) giữ nguyên.
  - Phần loe ra ngoài được kéo về phía trục còn 40%, nên miệng ống tay từ khoảng một cẳng tay còn khoảng nửa cẳng tay.
  - Áo choàng không dùng ánh sáng (unlit) nên không phải tính lại pháp tuyến.
- Trục khuỷu tay không xoay nhanh hơn 600°/giây, nên cú vung tay qua tư thế duỗi thẳng không làm cẳng tay bị vặn.
- **Tay không xuyên người** (`keepArmOutOfBody` trong `dance-body.mjs`).
  - Thân của Mao được mô tả bằng các lát cắt đo từ áo len, áo sơ mi, cà vạt và váy ở tư thế gốc (`TORSO`). Lát cắt bám theo xương ngực ở phần trên và xương chậu ở phần dưới, nên nghiêng, xoắn hay xoay người theo.
  - Trước khi đặt tay, khuỷu, giữa cẳng tay, cổ tay và bàn tay được kiểm tra. Điểm nào lọt vào thân bị đẩy ra bề mặt, cộng thêm khoảng hở cho ống tay áo và bàn tay, rồi cánh tay được hướng lại qua điểm mới.
  - Lực đẩy bắt đầu êm từ 2 cm trước bề mặt (`TORSO_SOFT`), nên tay đặt lên người chứ không bị bật ra.
  - Đầu và tay đụng tay chưa được kiểm tra.

## Xem trước (không cần bật Mao)

Chạy `scripts/start_draco_preview.ps1` rồi mở `http://127.0.0.1:12394/mao-5070/draco/`. Mục **Vũ đạo theo bài hát** có:

- **Nhảy theo nhịp**: chạy vũ đạo liên tục, không cần nhạc.
- **Thanh thời điểm**: kéo để dừng đúng một khung và so với clip gốc.

Trang này là web tĩnh, không nạp LLM, TTS hay RVC. Mã trang còn có hook `window.dracoPreview` (`startClip`, `stepClip`, `setClipLook`) để quay clip từng khung với kích thước cố định, dùng khi cần xuất video so sánh.

## Tạo vũ đạo từ một video

Công cụ nhận diện khung xương không nằm trong dự án (cần tải về riêng). Quy trình đã dùng:

1. Cắt video quanh người nhảy bằng ffmpeg, 30 khung/giây, chừa chỗ phía trên đầu để không cắt mất tay giơ cao.
2. Chạy **MediaPipe Pose Landmarker** (gói npm `@mediapipe/tasks-vision` và mô hình `pose_landmarker_heavy.task`) ở chế độ ảnh đơn, `numPoses: 4`, trên CPU. Chế độ ảnh đơn trả về mọi người trong khung nên việc chọn đúng người do bộ chuyển đổi làm; chế độ video của MediaPipe chỉ giữ một người và hay chuyển sang người bên cạnh. Lưu kết quả thành JSON `{fps, frames:[{i, poses:[{image, world}]}]}` (`image` chuẩn hóa theo vùng cắt).
3. Nên chạy máy dò **nhiều lượt** trên cùng các khung: ảnh gốc, ảnh lật gương, ảnh thu nhỏ 0,82 và ảnh thu nhỏ có lật. Với lượt lật, đổi lại toạ độ x và hoán đổi các mốc trái/phải. Mỗi lượt có lỗi riêng, gộp lại sẽ ổn định hơn.
4. Chạy bộ chuyển đổi (chỉ cần Node). Các lượt cách nhau bằng dấu phẩy:

```bash
node scripts/dance_from_pose.mjs goc.json,lat.json,nho.json,nho_lat.json web_tool/mao-5070/draco/dances/ten.mjs --id ten --label "Tên" --bpm 124 --fixes scripts/dance_fixes/ten.json
```

Bộ chuyển đổi (`scripts/dance_from_pose.mjs`, có test trong `tests/test_dance_from_pose.mjs`) làm lần lượt:

- **Chọn đúng người:** gần vị trí lần trước, cùng cỡ thân, bán kính tìm kiếm chặt nên không nhảy sang người bên cạnh.
- **Sửa nhầm trái/phải** của máy dò (khi xoay người, bắt chéo chân) bằng tính liên tục giữa các khung.
- **Gộp các lượt:** với mỗi mốc, chọn nhóm lượt khớp nhau mà máy dò chắc chắn nhất, rồi lấy trung bình. Mốc mà các lượt không đồng ý sẽ bị hạ độ tin cậy.
- **Độ sâu (trước/sau) tính từ độ dài xương:** một camera đo độ sâu rất kém, nhưng đo rất tốt độ dài xương nhìn thấy trên hình. Xương dài L mà chỉ hiện d trên hình thì phải chĩa về trước hoặc ra sau một đoạn √(L²−d²).
  - Chiều trước/sau chỉ có thể đổi khi xương đi qua mặt phẳng hình. Vì vậy giữa hai lần đi qua, chiều được giữ cố định và quyết định bằng ước lượng 3D của máy dò trên cả đoạn.
  - Độ sâu rất nhỏ (dưới khoảng 15°) bị xoá dần, vì đó thường là nhiễu.
  - Khớp mà máy dò mất dấu (tay bị hông che) thì dùng ước lượng 3D của máy dò thay cho độ dài.
- **Mặt sàn:** chỉ bù góc cúi của camera. Mỗi bàn chân có mức “đứng trên sàn” riêng, nên chân không lơ lửng khi máy dò đặt mắt cá hai bên cao thấp khác nhau. Bước chân ra trước/ra sau đo bằng độ sâu thật của mắt cá so với hông.
- **Giữ cả mốc kém tin cậy** (bị che hoặc nhòe) nhưng cho chúng ít trọng số khi làm mượt.
  - Một chuỗi mẫu kém tin cậy lệch quá 60° so với đường nối hai mẫu chắc chắn hai bên (tối đa 10 khung) là lỗi đo, nên được thay bằng đường nối đó.
  - Mẫu kém tin cậy mà vẫn khớp hướng thì giữ nguyên, nhờ vậy động tác cuộn tay nhanh ở đầu clip vẫn còn.
- Loại điểm lệch bất thường (Hampel) ở thân và chân, loại gai một khung trên véc-tơ hướng tay, làm mượt (Gauss ≈ 40 ms cho tay). Tốc độ tay chỉ bị chặn ở 2.100°/giây, mức của cú vung tay nhanh nhất trong clip mẫu.
- **Đo trong hệ trục của thân:** tay tính theo thân người nhảy chứ không theo camera. Ngoài nghiêng và xoắn thân, bộ chuyển đổi còn đo **xoay cả người** (`turn`) và **cúi người** (`pitch`). Sàn, trục giữa và chiều cao hông chuẩn được ước lượng bằng cửa sổ trượt, nên bước đi hay xê dịch của người nhảy không làm Mao trôi khỏi chỗ.
- **Sửa bằng mắt (`--fixes`):** file JSON (ví dụ `scripts/dance_fixes/white-top-dance.json`). Số khung là **khung vũ đạo**, giống số khung trong trình chỉnh và trong clip xem trước. `offset` là khung trong file tư thế ứng với khung vũ đạo 0 (bộ chuyển đổi in ra dưới tên `startFrame`).
  - `side: "front"/"back"` khoá chiều trước/sau của một xương. `min` là độ sâu tối thiểu, vào/ra dần trong 3 khung (ví dụ tay ra sau đầu).
  - `dir: [x,y,z]` thay hẳn hướng của một đoạn tay trong hệ trục thân, cho đoạn máy dò mất dấu (ví dụ tay giơ cao lẫn vào tán cây).
  - `keys: [[khung, [x,y,z]], ...]` là khung khoá cho cả một chuỗi động tác máy dò không theo kịp. Hai khoá được nối bằng đường cong mượt (Hermite/Catmull-Rom): đi qua khoá giữa không đổi tốc độ đột ngột, và vào/ra tư thế đứng yên thì chậm dần/nhanh dần. Khoá phải đặt tay ở ngoài thân (engine vẫn đẩy ra, nhưng tư thế đúng ngay từ đầu thì chuyển động mượt hơn). Hai khoá liên tiếp nên cách nhau ít nhất 3 khung khi tay đổi hẳn tư thế. Bài `white-top-dance` dùng khung khoá cho khung 0–61: hai cẳng tay **đổi chéo trước ngực ngang vai** (tay trái 2–7 và 28–34, tay phải 13–21 và 42–46), cuộn tay ở giữa, rồi hai tay duỗi bắt chéo chữ X trước hông (54–61). Ở đoạn này cẳng tay nằm đè lên thân và bị nhòe, nên máy dò đo ra cẳng tay chĩa vào camera. Khung 108–168 cũng dùng khung khoá:
    - Nắm tay trước hông: 120–123 và 153.
    - Tay phải vung ngang sang bên: 126–132 và 156–162.
    - **Chống hông, khuỷu mở ra ngoài**: 135–141, 150 và 165.
    - Cẳng tay trái vắt ngang ngực hoặc tầm vai: 114–117, 129–132, 144–147 và 159.
    - Khung 74–107: tay trái đưa lên rồi bàn tay ra **sau đầu** (82–88), mở lên cao rồi hạ xuống; tay phải dang chéo xuống bên.
    - Khung 166–215: hai tay lần lượt giơ thẳng lên cao (tay trái 173–176 và 198–206, tay phải 185–190) rồi hạ xuống phía trước. Máy dò hay mất tay giơ cao vì lẫn vào tán cây.
- **Nối liền vòng lặp** (hòa 12 khung cuối vào đầu).

## Chỉnh tay bằng trình chỉnh vũ đạo

Máy dò khung xương hay đo sai tay khi tay áo, cổ tay áo hoặc tay bị che. Trình chỉnh vũ đạo đặt clip gốc cạnh Mao để sửa từng khung bằng mắt. Nó chỉ cần Node và trình duyệt, không nạp LLM, TTS hay RVC:

```bash
powershell -ExecutionPolicy Bypass -File scripts/start_dance_editor.ps1 -Video "C:\duong\dan\clip-goc.mp4"
```

Thêm `-Dance <id>` để mở vũ đạo khác (mặc định `white-top-dance`) và `-Port` để đổi cổng (mặc định 12394). Lệnh chạy `scripts/serve_dance_editor.mjs` ẩn, chỉ nghe trên 127.0.0.1, ghi log vào `private/dance-editor*.log`, rồi mở trang `dance-editor.html?dance=<id>`. Nếu không truyền `-Video`, bấm **Mở clip…** để chọn clip ngay trên máy.

- **Clip gốc:** mục **Phóng to người nhảy** cắt clip theo vùng `reference.crop` trong file vũ đạo. Ô **Lệch** là thời điểm trong clip ứng với giây 0 của vũ đạo (mặc định `reference.offset`). Ô này được nhớ riêng cho từng vũ đạo.
- **Mao:**
  - Áo choàng có thể để **Hiện**, **Làm mờ** hoặc **Ẩn** để thấy rõ cánh tay.
  - **Khung xương** vẽ đè xương lên Mao: đỏ là tay/chân phải, xanh là tay/chân trái, cam là đoạn đang chỉnh. Phải/trái là của người nhảy.
  - Góc nhìn có ba lựa chọn: chính diện, cận thân trên, nghiêng.
- **Chỉnh khớp:**
  - Chọn bộ phận (cánh tay trên hoặc cẳng tay mỗi bên, xoay thân, hông…).
  - Với tay, kéo thanh **Hướng** (0° chỉ xuống, 90° dang ra, 180° chỉ lên, 270° bắt chéo trước người) và thanh **Ra phía trước**.
  - **Độ lan** quyết định số khung lân cận được kéo theo đường cong mềm, nên một lần sửa không tạo cú giật.
- **Thời gian:**
  - Phím ←/→ lùi hoặc tiến một khung. Space phát hoặc dừng. Có thể phát chậm 0,25x hoặc 0,5x.
  - Chấm cam trên thanh thời gian đánh dấu khung đã chỉnh.
- **Hoàn tác** (Ctrl+Z) bỏ lần sửa cuối. **Trả khung này về số đo** đưa khung đang xem (và vùng lân cận) về số liệu gốc của máy dò.
- **Lưu vào dự án:**
  - Ghi đè `web_tool/mao-5070/draco/dances/<id>.mjs`, sau khi máy chủ kiểm tra lại file bằng `validateDance`.
  - Bản cũ được sao lưu vào `private/dance-backups/`.
  - Chỉ chính trang chỉnh trên máy này được lưu; trang web khác bị từ chối.
- **Tải file .mjs:** lưu bản chỉnh về máy mà không ghi vào dự án.
- **Bản nháp:** khi chưa lưu, bản nháp được giữ trong trình duyệt. Lần mở sau, trang hỏi có khôi phục không.

## Định dạng file vũ đạo

```js
export default {
  id: 'ten-vu-dao',                 // trùng tên file
  label: 'Tên hiển thị',
  bpm: 124,                         // nhịp của vũ đạo gốc
  fps: 30,                          // số hàng mỗi giây
  loop: true,
  overlay: { bounce: 0, sway: 0 },  // tùy chọn: nảy/lắc thêm theo nhịp
  columns: ['RuX', 'RuY', /* ... */ 'Rz'],
  frames: [[...], ...]              // mỗi hàng một số cho mỗi cột
};
```

Bên phải/trái là của chính người nhảy (R nằm bên trái màn hình khi nhìn từ phía trước). Hướng tính trong hệ trục thân: x về bên trái người nhảy, y lên, z ra phía khán giả. Mười hai cột hướng tay là bắt buộc; các cột còn lại tùy chọn.

| Cột | Ý nghĩa | Giới hạn |
|---|---|---|
| `RuX` `RuY` `RuZ` | hướng cánh tay trên phải (vai → khuỷu) | −1…1 (tự chuẩn hóa) |
| `RfX` `RfY` `RfZ` | hướng cẳng tay phải (khuỷu → cổ tay) | −1…1 |
| `LuX…`, `LfX…` | như trên cho tay trái | −1…1 |
| `roll` `yaw` | nghiêng thân / xoay thân về bên trái người nhảy (độ) | ±30 / ±45 |
| `turn` `pitch` | xoay cả người (hông và thân, chân giữ chỗ) về bên trái người nhảy / cúi thân ra trước (độ); không bắt buộc | ±60 / ±30 |
| `hip` | dịch hông sang trái người nhảy (tỉ lệ chiều cao thân) | ±0,3 |
| `drop` | hạ hông, gập gối (tỉ lệ chiều cao thân) | −0,1…0,3 |
| `Lx` `Rx` | mỗi bàn chân đứng cách trục giữa bao xa; âm là bắt chéo qua trục | ±0,5 |
| `Ly` `Ry` `Lz` `Rz` | nhấc chân lên / đưa chân ra trước | −0,1…0,5 / ±0,5 |

Dữ liệu được kiểm tra trước khi dùng (`validateDance`): sai id, nhịp, số cột, số khung, giá trị ngoài giới hạn, hướng tay quá ngắn đều bị từ chối.

## Cách tích hợp

- `dance-body.mjs`: `DanceBodyActor` thêm một lớp vũ đạo lên bộ giải xương chung (hướng tay, nghiêng/xoay thân, dịch/hạ hông, bàn chân). Mặt, tóc, váy và chống xuyên váy vẫn chạy bên dưới.
- `motor-body.mjs`: `AdaptiveBodyActor` kế thừa từ lớp này nên cả desktop và xem trước cùng dùng.
- `native-avatar.mjs`: khi bài đang phát, lấy `song.dance`, nạp module một lần rồi truyền thời gian phát thật của file nhạc vào actor. Chưa nạp xong hoặc không có vũ đạo thì dùng lắc hông.
- `singing.py`: trường `dance` (tùy chọn) được kiểm tra và gửi cùng trạng thái bài hát.

Kiểm tra: `node tests/test_dance.mjs` và `node tests/test_dance_from_pose.mjs`; `tests/test_singing.py` (trường `dance`).

## Giới hạn

- Số đo đến từ nhận diện khung xương 3D trên clip nhỏ, mờ: cẳng tay và bàn tay lúc múa nhanh ít chính xác nhất, độ sâu (ra/vào so với camera) kém tin cậy hơn chiều ngang và chiều dọc. Dữ liệu đã được lọc nên mượt, nhưng một vài cú vung tay có thể yếu hơn clip gốc.
- Phần cô nhảy đi sang bên (bước chéo chân, lunge) được giữ tại chỗ: bước chân và độ nghiêng vẫn có, nhưng Mao không tịnh tiến.
- Tay áo choàng rộng che khuỷu tay. Chưa có cử động ngón tay và cổ tay, chưa xoay bàn chân, mặt vẫn cười như khi hát.
