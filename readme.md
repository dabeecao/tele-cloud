# TeleCloud

**TeleCloud** là một dự án cho phép sử dụng chính dung lượng lưu trữ gần như vô tận của Telegram để lưu trữ và quản lý tệp.

Dự án hỗ trợ cả **Bot** và **Userbot** *(khuyến nghị dùng Userbot để có giới hạn tốt hơn)*.
Sử dụng các công nghệ như **hydrogram**, **FastAPI** và **SQLite** giúp hệ thống nhẹ, nhanh và dễ triển khai.

---

## ✨ Tính năng

* 📁 Lưu trữ file trực tiếp trên Telegram
* 🔗 Trang share có preview file tiện lợi
* 🗂️ Trang quản lý có file browser
* ⬆️ Upload nhiều file cùng lúc
* 📦 Upload chia nhỏ (chunk) để tránh giới hạn từ Cloudflare proxy
* 🤖 Hỗ trợ cả Bot và Userbot

---

## ⚙️ Cài đặt

```bash
cp ./env.example ./.env
pip install -r requirements.txt
```

---

## 🔧 Cấu hình `.env`

```env
API_ID=12xxxxx
API_HASH=abcxxxxxxxxxxx

# Để trống SESSION_STRING trước, sẽ tạo ở bước dưới
SESSION_STRING=

# Điền BOT_TOKEN nếu dùng Bot.
BOT_TOKEN=

# Thay vì ID nhóm, bạn có thể dùng "me" để lưu vào Saved Messages (chỉ áp dụng cho Userbot)
LOG_GROUP_ID=-1003900839462

ADMIN_PASSWORD=xxxxx

# Nếu có Telegram Premium bạn có thể nâng lên 4096 (chỉ Userbot)
MAX_UPLOAD_SIZE_MB=2048

PORT=8091
```

---

## 🔑 Lấy API_ID và API_HASH

1. Truy cập: https://my.telegram.org
2. Đăng nhập bằng số điện thoại Telegram
3. Chọn **API development tools**
4. Tạo app mới
5. Lấy:

   * `API_ID`
   * `API_HASH`

---

## 🤖 Lấy BOT_TOKEN (nếu dùng Bot)

1. Mở Telegram → tìm **@BotFather**
2. Gõ `/newbot`
3. Làm theo hướng dẫn
4. Nhận `BOT_TOKEN` và điền vào `.env`

---

## 🔐 Tạo SESSION_STRING (Userbot - khuyến nghị)

Dự án đã có sẵn script lấy SESSION_STRING.

---

### ▶️ Cách sử dụng

```bash
python3 get-session.py
```

* Nhập mã đăng nhập Telegram
* Sau khi xong, bạn sẽ nhận được:

```env
SESSION_STRING=xxxxxxxxxxxxxxxx
```

👉 Copy và dán lại vào file `.env`

---

## 📡 Lấy LOG_GROUP_ID

* Tạo group Telegram
* Thêm bot hoặc userbot vào
* Gửi 1 tin nhắn

ID sẽ có dạng:

```
-100xxxxxxxxxx
```

---

## 🚀 Chạy dự án

```bash
python3 main.py
```

Sau khi chạy, truy cập:

```
http://localhost:8091
```

---

## 📌 Ghi chú

* Userbot có giới hạn upload cao hơn Bot
* Có thể dùng `"me"` để lưu vào **Saved Messages**
* Chunk upload giúp bypass giới hạn Cloudflare
* SQLite giúp setup nhanh, không cần database riêng
* Hãy khai dự án trên một tên miền có SSL (bạn có thể dùng **Cloudflare Tunnel, revert proxy,...**)