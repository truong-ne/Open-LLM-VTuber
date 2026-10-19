# Action kể chuyện của model Draco / Mao preview

Bản sửa tay/tay áo mới nhất: [rà soát v4](draco_hand_pose_review.vi.md). Các số liệu v3 bên dưới là kết quả của phiên bản trước.

Preview: http://127.0.0.1:12394/mao-5070/draco/

Có 17 action, gồm 7 cử chỉ cơ bản và 10 action mới:

| Action | Tên | Diễn xuất cơ thể |
|---|---|---|
| chuckle | Cười khúc khích | Tay gần má, đầu nghiêng nhẹ, vai rung theo vài nhịp giảm dần |
| laugh | Cười vui | Tay gần miệng và tay trước bụng, lòng bàn tay hướng về cơ thể, thân hơi nghiêng tới trước và vai/ngực nhấn nhịp cười |
| surprise | Ngạc nhiên | Nâng hai tay, mở lòng bàn tay, đầu lùi nhẹ |
| think | Suy nghĩ | Tay nâng gần cằm về một bên, đầu nghiêng và nhìn lệch |
| shy | Ngượng ngùng | Tay trước cổ áo, cúi và xoay đầu nhẹ |
| sad | Buồn nhẹ | Hạ đầu, khép vai, thân hơi chùng |
| shrug | Nhún vai bối rối | Nhún hai vai, mở lòng bàn tay |
| emphasize | Nhấn mạnh ý | Đưa tay lên, ngón trỏ duỗi, các ngón còn lại cong |
| reassure | An ủi, dịu dàng | Tay trước ngực và tay mở nhẹ, đầu nghiêng |
| celebrate | Vui mừng | Hai tay nâng, ngón tay co, thân nhấn hai nhịp nhỏ; chân vẫn giữ đất |

Các động tác có chuẩn bị, giữ ngắn và thu về; đổi action dùng bộ lọc lò xo. Ngón tay gập quanh trục rút ra từ chính xương ngón và mặt phẳng bàn tay, thay cho một trục chung cho mọi ngón. Các vị trí tay gần mặt/ngực dùng IK hai đoạn. Đã dời tay ra ngoài và phía trước để phù hợp với tay áo rộng, tránh che kín mặt hoặc ép tay áo vào thân.

## Diễn theo câu chuyện

Nhập mỗi câu trên một dòng rồi bấm **Diễn đoạn này**. Mỗi câu chạy khoảng 7,6 giây, hiển thị phụ đề và ghép với một action. Luồng này là preview diễn xuất không âm thanh; nút Mỹ Duyên riêng vẫn phát mẫu giọng hiện có. Không gọi API, không tự gửi nội dung ra mạng.

Có thể chỉ định action:

```
[think] Mao đang nghĩ một chuyện rất khó hiểu.
[surprise] Bỗng chiếc máy tính kêu meo!
[chuckle] Hihi, hóa ra là tiếng chuông báo của papa.
[laugh] Cả hai cùng bật cười.
[reassure] Thôi, không sao đâu. Mình kể tiếp nhé.
```

Nếu không có nhãn, các từ/cụm từ tiếng Việt được ghép theo quy tắc trong `actions.mjs`. Đây là bộ chọn theo từ khóa, chưa phải bộ hiểu cảm xúc bằng LLM. Nhãn tường minh được ưu tiên; câu không có dấu hiệu rõ dùng `talk`. Câu phủ định như “không cười nổi” không bị ghép thành cười. Nhập tối đa 40 dòng cho một đoạn diễn; nhấn một action, bật tự diễn hoặc bấm dừng sẽ kết thúc đoạn đang diễn theo thao tác của người dùng. Tạm dừng giữ nguyên tiến độ câu.

Dữ liệu nhãn/metadata và mẫu tám câu nằm trong `web_tool/mao-5070/draco/actions.mjs`. Có thể dùng cùng các tên action này khi nối bộ sinh truyện của Mao sau này. Lần thay đổi này chỉ cập nhật preview 3D riêng, chưa thay model hay nối chế độ diễn này vào livestream TikTok.

## Kiểm tra

- `node tests/test_draco_story_actions.mjs`: 13 tình huống tiếng Việt, nhãn ưu tiên, mẫu tám câu, giới hạn đầu vào đều đạt.
- `node tests/test_draco_body_motion.mjs`: đủ 17 động tác, mỗi động tác chín giây; thêm chuỗi đổi động tác 51 giây. Kiểm tra cả hai cổ tay, IK chân, chiều dài và va chạm của 218 đoạn tóc/vải.
- Kiểm tra cử chỉ rõ ràng của các action mới: nâng tay trái/phải, cúi đầu buồn, quaternion hữu hạn/chuẩn hóa, giới hạn bước dịch/xoay giữa hai frame.
- Các clip đều có pose đầu/cuối khớp để lặp. Phát lại action chào bằng AnimationMixer vẫn nâng tay đúng.
- Kết quả số lưu ở `web_tool/mao-5070/draco/motion-test-report.json`.

Xuất GLB dùng bản sao skeleton, giữ nguyên trạng thái actor và tiến độ câu chuyện của preview. Model gốc trong Downloads không bị chỉnh sửa. Tệp bàn giao vẫn là `web_tool/mao-5070/draco/draco-body-motion.glb` và `draco-body-motion.webm`.

## Giới hạn

Đây là diễn xuất cơ thể trên rig gốc. Model chưa có morph mắt–miệng nên các action cười không đổi nét cười trên khuôn mặt và không tạo tiếng cười. Tóc/vải mô phỏng theo xương/capsule, chưa có tự va chạm toàn bề mặt. Nguồn và giấy phép giữ nguyên trong `ATTRIBUTION.txt`.

## Bàn giao đã kiểm tra

GLB thực tế đã được nạp lại bằng GLTFLoader trong preview: đủ 17 tên animation, có nhãn `story-actions-v3`. Tệp 68.501.452 byte; pose đầu/cuối chênh tối đa khoảng 3,58e-7. Danh sách clip và kết quả kiểm tra nằm ở `export-validation.json`. Đã ghi clip mới 30 giây, xem khung hình tại giây 2,2 / 10 / 17 / 25 cho cười khúc khích, cười vui, ngạc nhiên, suy nghĩ. Đã xem trực tiếp ngượng ngùng ở góc nghiêng, vui mừng và hai lòng bàn tay khi ngạc nhiên.

Luồng mẫu tám câu chuyển đúng từ suy nghĩ sang ngạc nhiên. Tạm dừng tại câu 2 giữ nguyên `data-story-beat=2` trong lúc kiểm tra clip, bỏ tạm dừng tiếp tục đúng câu chuyện. Console không có lỗi trong lượt xuất/preview này. Chưa nối bộ ghép câu này với backend AI hay TikTok.

## Cúi chào sâu khoảng 30°

Đã tăng góc nghiêng thân của `bow` lên π/6, chia giữa eo/cột sống/ngực theo tỷ lệ 70/22/8. Góc đo trên quaternion thế giới của ngực tối đa 30.127°. Hông dịch nhẹ ra sau, nhánh pelvis bù góc để váy giữ quanh đùi; hai tay thả tự nhiên, cổ và đầu cúi bổ sung ít hơn trước. Tóc mái ngắn dùng không gian bám đầu để tránh trễ qua vùng da đầu khi cúi sâu; tóc dài vẫn giữ quán tính thế giới.

`node tests/test_draco_body_motion.mjs` đã đạt, bao gồm assertion góc thân 29–31°, 17 action và kiểm tra IK/va chạm. Tư thế giữ để xem ở giây 2,5. Đã kiểm tra trực tiếp ở góc nghiêng và ngang người.

Đã xuất lại GLB sau chỉnh cúi chào: 68.509.268 byte, đủ 17 clip. Phát lại dữ liệu GLB thực tế tại giây 2,5 đo được thân nghiêng 29,822°; điểm lặp vẫn khớp (sai số tối đa 3,58e-7). Ảnh xác nhận tạm của lần kiểm tra này đã dọn theo yêu cầu.
