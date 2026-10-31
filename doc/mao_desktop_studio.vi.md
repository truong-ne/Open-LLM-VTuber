# Mao Desktop — giao diện livestream (31/10/2026)

Ứng dụng Electron chỉ còn giao diện Mao: avatar Draco, phụ đề, thanh tiêu đề hệ điều hành và chế độ pet. Đã gỡ toàn bộ Settings, thanh bên/lịch sử dạng drawer, header Studio, composer, ảnh nền/camera nền, chọn nhân vật và renderer Cubism cũ. Không có nút hoặc phím tắt mở Settings cũ. Thông số vận hành tiếp tục nằm trong cấu hình backend và các công cụ quản trị hiện có.

`scripts/desktop/mao-runtime.js` là bundle nền duy nhất được quản lý trong Git; build tạo `private/tools/vtuber-desktop-unpacked/out/renderer/assets/mao-draco-shell.js`. Không còn bundle gốc để quay lại giao diện cũ. `scripts/build_draco_shell.mjs` cập nhật bốn khối có đánh dấu từ delivery.mjs, draco-shell-component.js, mao-studio-component.js và mao-app-component.js. Không chèn lại bundle cũ. `index.html` là lối vào duy nhất của desktop.

`scripts/configure_draco_desktop.mjs` đóng gói cùng mã vào app.asar, loại file cũ và chỉ giữ hai dependency runtime Electron Toolkit. Thư viện frontend đã nằm trong bundle; không cần bản node_modules rời của chúng. Các thư viện VAD/WASM đang dùng và tài nguyên avatar/phòng 3D vẫn được giữ. Đã xóa bản sao app.asar.original và các thư mục thư viện rời cũ khỏi ổ đĩa: 241 mục, 538.476.450 byte. Không còn mục cần xóa tay. Frontend web và backend là các sản phẩm riêng, không nằm trong lần loại bỏ UI desktop này.

Kiểm tra: test_mao_desktop_runtime.mjs xác minh mã UI cũ không có trong bundle và bảo toàn audio/motion delivery; test_mao_studio_ui.mjs và test_mao_studio_layout.py kiểm tra phụ đề. Đã kiểm tra cửa sổ Electron thực tế, avatar, phụ đề và kết nối hoạt động.
