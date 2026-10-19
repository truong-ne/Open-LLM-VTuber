# Rà soát bàn tay và tay áo — v6

Preview: http://127.0.0.1:12394/mao-5070/draco/

Đã xem ảnh tham khảo và kiểm tra trực tiếp model ở góc trước, cận tay và góc nghiêng:

- [Cười che miệng — Tobias Gaisbauer](https://www.tobiasgaisbauer.de/10.html): lòng bàn tay quay về mặt, ngón tay nghiêng vào trong, cổ tay không bẻ vuông.
- [Cười, tay trước bụng — kues / Depositphotos](https://depositphotos.com/photo/young-pretty-blonde-woman-laughing-out-loud-some-hilarious-joke-378632462.html): mu tay hướng ra ngoài, ngón cái ở phía trên, thân hơi nghiêng tới trước.
- [Tư thế suy nghĩ — LanguagePod101](https://wordlist.languagepod101.com/wordlist/media/27044%26v%3Dmedium.jpg): ngón tay gần cằm, các ngón còn lại co và cổ tay tương đối thẳng với cẳng tay.
- [Bàn tay đặt lên ngực — Ueno no Mori Counseling](https://www.kokorono119.com/cont3/main.html): ảnh cận tay đặt chéo lên ngực; lòng bàn tay hướng vào thân, ngón nằm theo bề mặt áo thay vì dựng đứng phía trước.

Các ảnh chỉ dùng để tham khảo tư thế, không được đưa vào texture hay phân phối cùng model.

## Sửa lỗi

Trước đây mọi động tác IK dùng cùng pháp tuyến lòng bàn tay hướng ra camera. Điều này làm tay trước bụng lật ngược, ngón cái chúc xuống. Một số cử chỉ còn dồn toàn bộ góc xoay vào cổ tay; tư thế ngượng có góc cổ tay gần 89°.

`motion.mjs` hiện có hướng lòng bàn tay, hướng ngón tay và vị trí đích riêng cho từng cử chỉ. Tay cười được đưa vào giữa hơn, hạ nhẹ và tiến gần mặt để đầu ngón nằm ngay dưới miệng, thay vì ở xa bên má; tay trước bụng có ngón cái hướng lên. Giới hạn uốn cổ tay đích là 52°, phần xoay sấp/ngửa chia cho cẳng tay và các khớp roll. Bộ lọc quaternion và giới hạn tốc độ giúp tay không lật khi đổi cảm xúc. Tư thế suy nghĩ được hạ tay và co thêm các ngón giữa/áp út/út.

`garment-rig.mjs` thêm 8 khớp roll riêng cho mesh áo choàng. Bàn tay dùng skeleton gốc, tay áo nhận 10% độ xoay cẳng tay để giữ dáng ống tay rộng. Hình học, UV, trọng số skin và texture gốc được giữ nguyên. Skeleton runtime có 526 khớp, so với 518 khớp nguồn. Các khớp phụ được bake vào GLB xuất ra.

Ống tay có thể gập thêm khi gặp capsule thân người, thay vì bộ giới hạn góc ép vải trở lại vào cơ thể. Đây là mô phỏng khớp lò xo với capsule, chưa phải mô phỏng vải có tự va chạm đầy đủ.

## Kiểm tra

Cập nhật độ nghiêng tay che ngực: `shy/reassure` đặt hướng ngón nghiêng vào thân khoảng 18–19° trong hệ trục ngực ở tư thế giữ, đồng thời giảm độ dốc hướng lên. Đầu ngón lùi vào so với cổ tay khoảng 3,6–3,9 cm trong tọa độ rig nguồn. Điểm cổ tay được đưa ra trước đủ để tránh ngón chui vào áo; điểm hướng khuỷu tay riêng được lọc bằng lò xo, không chỉ ép góc cổ tay. Giữ giới hạn uốn cổ tay 52° và xoay cẳng tay phân bổ như trước. Đã xem mesh skin thật ở góc trước và nghiêng 65° cho cả hai tay; ảnh tham khảo/QA tạm được dọn sau kiểm tra.

Cập nhật theo phản hồi tay che ngực quá cao: `shy` (tay trái của nhân vật) và `reassure` (tay phải) dùng điểm neo theo khớp ngực, thay cho offset từ khớp đầu. Bàn tay được hạ về trước ngực, ngón đặt chéo vào trong và gần áo hơn. Đầu cúi/nghiêng không kéo điểm đặt tay lên vùng cổ. Vị trí neo và hướng bàn tay được pha bằng lò xo khi đổi giữa động tác theo đầu và theo ngực, tránh nhảy IK. Tay che miệng trong `laugh/chuckle`, tay suy nghĩ gần cằm và tay nhấn mạnh vẫn giữ mục đích riêng.

Kiểm tra thêm trong `tests/test_draco_hand_poses.mjs`: tâm lòng bàn tay nằm quanh cao độ khớp ngực, đầu ngón dưới cổ ít nhất 6,5 cm trên rig nguồn, khoảng cách trước thân hợp lý; đồng thời giữ giới hạn góc cổ tay, lòng bàn tay và độ mượt khi chuyển tư thế. Bản QA lấy mẫu vertex đã skin của GLB thật ở góc trước của `reassure`, không thao tác hoặc chụp desktop. Ảnh QA tạm đã xóa theo yêu cầu dọn dung lượng; giữ mã lấy mẫu/render để tái tạo khi cần.

- `node tests/test_draco_garment_rig.mjs`: bind pose không đổi; mesh áo và da dùng khớp roll độc lập; không thêm khớp trùng khi khởi tạo lại.
- `node tests/test_draco_hand_poses.mjs`: hướng lòng bàn tay của 6 cử chỉ, ngón cái tay trước bụng, góc cổ tay dưới 55°, chuyển tiếp cả cổ tay và cẳng tay, tiếp xúc tay áo với thân.
- `node tests/test_draco_body_motion.mjs`: 17 action, chuyển tiếp, chân giữ đất, giới hạn vải, clip bake và phát lại; góc cúi thân khoảng 30°.
- Rà soát hình model thực tế: cười ở góc trước/cận/nghiêng, suy nghĩ, ngượng và an ủi; ghi lại clip 30 giây và kiểm tra các khung hình.

Kết quả số được lưu ở `hand-pose-test-report.json`, `motion-test-report.json` và `export-validation.json` trong thư mục preview. Model nguồn không có morph mặt/miệng; lần sửa này tập trung vào cử chỉ cơ thể và tay áo.
