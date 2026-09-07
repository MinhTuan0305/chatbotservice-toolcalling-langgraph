# Web Gateway Architecture: Socket, JWT, Nginx, Docker

Tài liệu này giải thích các thành phần được thêm/sửa trong quá trình tách chatbot từ 1 monolith (`socket_server.py` ôm hết mọi thứ) thành kiến trúc nhiều lớp: Nginx → Socket gateway → AI Agent service → Redis/Postgres.

Mỗi mục dưới đây trả lời 3 câu hỏi: **nó là gì, nó làm gì, nó có tác dụng gì trong project này.**

---

## Bức tranh tổng thể

```
Browser/mobile client
        │  WebSocket (Socket.IO) + REST, qua origin duy nhất
        ▼
   Nginx (:80)
        │  route theo path
        ▼
  socket_server.py (:5000)        ← gateway real-time
        │  HTTP (POST /chat) / SSE (POST /chat/stream)
        ▼
  api_server.py (:8000)           ← service AI, chỉ gọi nội bộ
        │
        ▼
   Redis (checkpointer) + PostgreSQL (dữ liệu shop)
```

Trước đây `socket_server.py` vừa lo Socket.IO (kết nối, room, rate limit) vừa trực tiếp gọi LangGraph/LLM. Giờ 2 việc này tách hẳn thành 2 service độc lập, nói chuyện với nhau qua HTTP — lý do: 2 mối quan tâm khác nhau (real-time connection vs AI logic) có thể scale, deploy, debug riêng.

---

## 1. `app/api_server.py` — AI Agent Service

**Là gì:** Service FastAPI, port 8000.

**Làm gì:** Sở hữu duy nhất phần LangGraph agent (LLM, tools, checkpointer) — chính là `ChatService` đã có sẵn từ trước, giờ được bọc thành REST API:
- `POST /chat` — nhận `{message, thread_id, tool_enabled}`, trả về câu trả lời hoàn chỉnh (không streaming)
- `POST /chat/stream` — như trên nhưng trả về Server-Sent Events (SSE), mỗi token/chunk là 1 event `data: {...}\n\n` trên **cùng 1 kết nối HTTP giữ mở**, không phải 1 request mới cho mỗi token
- `GET /health`

**Tác dụng:** Đây là biên giới rõ ràng cho "AI logic" — không biết gì về Socket.IO, room, hay có bao nhiêu client đang connect. Được bảo vệ bởi header `x-api-key` (secret dùng chung service-to-service, khác với JWT của user — xem mục 4).

---

## 2. `app/socket_server.py` — Real-time Gateway

**Là gì:** Service Flask-SocketIO, port 5000. Đây là **cổng duy nhất mà client (browser) thực sự kết nối tới**.

**Làm gì:** Quản lý toàn bộ vòng đời kết nối real-time — không còn tự xử lý AI nữa:
- `connect` — verify JWT (mục 4), reject nếu thiếu/sai/hết hạn
- `join_thread` / `leave_thread` — join/leave 1 room Socket.IO ứng với 1 `thread_id`
- `chat_message` / `chat_stream` — forward sang `api_server` qua `ai_client.py`, rồi `emit` kết quả về đúng room
- `toggle_tools` — bật/tắt tool cho 1 thread
- HTTP routes: `POST /auth/token` (mục 4), `/health`, `/stats`, `/metrics` (đều có thể yêu cầu `X-API-Key`)
- Rate limiting theo IP (`flask-limiter`)

**Tác dụng:** Tách biệt "hạ tầng kết nối" khỏi "logic AI". `socket_server.py` không còn import `ChatService` nữa — grep sẽ không thấy dòng nào cả.

**Chi tiết kỹ thuật quan trọng:** file này chạy dưới `eventlet` (async cooperative), nên dòng đầu tiên của file là:
```python
os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")
import eventlet
eventlet.monkey_patch()
```
`eventlet.monkey_patch()` bắt buộc phải chạy **trước mọi import khác**, để các lời gọi blocking (như `requests` trong `ai_client.py`) không làm treo toàn bộ event loop (tức treo luôn mọi client khác đang connect). `EVENTLET_NO_GREENDNS=yes` tắt bộ resolver DNS tự chế của eventlet — bản tự chế này từng bị treo 20-30s khi resolve `"localhost"` trên Windows và tên service Docker Compose (`api_server`) trong container — dùng resolver hệ thống ổn định hơn nhiều.

---

## 3. `app/ai_client.py` — Cầu nối giữa 2 service

**Là gì:** HTTP client mỏng, không chứa logic nghiệp vụ.

**Làm gì:**
- `chat(...)` — gọi `POST /chat`, trả JSON
- `chat_stream(...)` — gọi `POST /chat/stream` với `stream=True`, đọc từng dòng SSE, `yield` từng event ngay khi nhận được (generator) — đây là cách né đúng anti-pattern "1 request/webhook cho mỗi chunk", giữ đúng 1 kết nối HTTP xuyên suốt cả câu trả lời

**Tác dụng:** Là điểm duy nhất `socket_server.py` biết về sự tồn tại của `api_server.py`. Mọi request đều set header `Connection: close` — tắt hẳn HTTP keep-alive để tránh việc pool giữ 1 connection cũ trỏ tới `api_server` đã restart (deploy lại, crash...), vì phát hiện connection chết dưới eventlet có thể mất tới 20-30 giây (timeout TCP cấp OS) thay vì báo lỗi ngay.

---

## 4. `app/auth.py` + luồng JWT

**Là gì:** Module ký/verify JWT bằng `JWT_SECRET_KEY` (khác hẳn `API_KEY` ở trên — 2 secret, 2 mục đích khác nhau).

**Làm gì:**
- `create_token(user_id)` — ký JWT chứa claim `sub=user_id`, hết hạn sau `JWT_EXPIRE_MINUTES` (mặc định 60 phút)
- `verify_token(token)` — verify chữ ký + hạn, trả về `user_id`, raise `TokenError` nếu hỏng

**Luồng thực tế:**
1. Client gọi `POST /auth/token` với `{"user_id": "bất kỳ"}` → nhận JWT (đây là **demo issuer, không check password** — chỉ để có cái test end-to-end, phải thay bằng xác thực thật trước khi lên production)
2. Client connect Socket.IO kèm `auth: {token}`
3. `socket_server.handle_connect` verify token, lưu `user_id` vào `authenticated_users[sid]`
4. Mọi thao tác sau đó (`join_thread`, `chat_message`...) đều bị `authorize_thread()` kiểm tra: **`thread_id` phải đúng bằng `user_id` đã xác thực** — 1 user chỉ sở hữu đúng 1 thread là chính mình

**Tác dụng:** Trước khi có JWT, ai connect vào cũng join được **bất kỳ** `thread_id` nào — đọc/ghi được hội thoại của người khác chỉ cần đoán đúng chuỗi. JWT đóng lỗ hổng này bằng cách gắn danh tính vào từng kết nối thay vì tin tưởng client tự khai.

---

## 5. `nginx/nginx.conf` — Reverse proxy

**Là gì:** Cấu hình Nginx, dùng trong `docker-compose.yml`, là **cổng public duy nhất** (port 80) đứng trước `socket_server`.

**Làm gì:** Route theo path:
- `/socket.io/*` → `socket_server:5000`, kèm header bắt buộc để nâng cấp WebSocket:
  ```nginx
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  ```
  Thiếu 2 header này, Socket.IO sẽ rớt về long-polling hoặc connect fail hẳn.
- `/auth/*`, `/health`, `/stats`, `/metrics` → cũng route sang `socket_server`
- **Không** route gì tới `api_server` — đúng thiết kế "chỉ gọi nội bộ", Nginx còn không biết `api_server` tồn tại

**Tác dụng:** Client chỉ cần biết 1 origin (`http://your-domain`) thay vì nhớ nhiều port; là chỗ tự nhiên để làm TLS termination sau này.

**Đi kèm:** `TRUST_PROXY_HEADERS=true` (config mới, `app/config.py`) bật `ProxyFix` (Werkzeug middleware) trong `socket_server.py`, để Flask đọc đúng IP thật của client từ header `X-Forwarded-For` do Nginx set — nếu không, mọi request sẽ trông như đến từ chính Nginx, làm rate-limit theo IP (`flask-limiter`) trở nên vô nghĩa. Biến này **chỉ nên bật khi thực sự đứng sau đúng 1 lớp reverse proxy tin cậy** — bật bừa khi chạy trực tiếp (không qua Nginx) sẽ cho phép client tự spoof `X-Forwarded-For` để né rate limit.

---

## 6. Docker: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

**Là gì:** Đóng gói toàn bộ stack trên thành các container chạy được bằng `docker compose up -d`.

**Làm gì:**
- `Dockerfile` — 1 image dùng chung cho cả `api_server` và `socket_server` (cùng `requirements.txt`, cùng code `app/`), chỉ khác `command:` mỗi service trong compose
- `docker-compose.yml` — 4 service:
  - `redis` — dùng image `redis/redis-stack-server`, **không phải** `redis:7-alpine` thường. Lý do: `langgraph-checkpoint-redis` cần lệnh `FT.*` (module RediSearch) để tạo index cho checkpoint — Redis thường (bản < 8) không có
  - `api_server`, `socket_server` — build từ `Dockerfile`, **không map port ra host** (chỉ nội bộ mạng Docker), override `REDIS_URL`/`AI_SERVICE_URL` trỏ vào tên service thay vì `localhost`
  - `nginx` — map port 80 ra host, mount `nginx/nginx.conf`
- `.dockerignore` — loại `.venv/`, `.git/`, `logs/`, `.env` khỏi build context cho nhẹ và tránh leak secret

**Tác dụng:** Cho phép chạy toàn bộ stack giống hệt production trên máy dev bằng 1 lệnh, không cần cài Python/Redis/Nginx thủ công. Lưu ý: Redis trong Docker Compose là **instance riêng biệt**, không chia sẻ dữ liệu với Redis bạn chạy trực tiếp trên host (nếu có) — thread hội thoại giữa 2 cách chạy không liên thông.

---

## 7. Config mới trong `app/config.py`

| Biến | Dùng cho | Ghi chú |
|---|---|---|
| `AI_SERVICE_URL` | `ai_client.py` biết gọi `api_server` ở đâu | Mặc định `http://127.0.0.1:8000` (không dùng `localhost` — né bug DNS eventlet); trong Docker override thành `http://api_server:8000` |
| `JWT_SECRET_KEY` | Ký/verify JWT (`app/auth.py`) | Bắt buộc, khác `API_KEY` |
| `JWT_EXPIRE_MINUTES` | Hạn token | Mặc định 60 |
| `TRUST_PROXY_HEADERS` | Bật `ProxyFix` khi đứng sau Nginx | Mặc định `False`, chỉ bật khi thực sự có reverse proxy |

---

## 8. `client-examples/test.html` — UI test cập nhật theo

- Thêm màn login: nhập **Gateway URL** (đổi được giữa `http://localhost:5000` khi chạy trực tiếp và `http://localhost` khi chạy qua Nginx/Docker) + **User ID** → gọi `POST /auth/token` → connect Socket.IO kèm `auth: {token}`
- Ô "Thread ID" giờ tự khớp với User ID và khoá lại (readonly) — đúng theo rule "1 user = 1 thread" phía server, không cho gõ tay `thread_id` tuỳ ý nữa

---

## Các bug đã gặp và vá trong session này (đáng nhớ để tránh lặp lại)

1. **`graph.stream()` thiếu `stream_mode="values"`** (`app/service.py`) — mặc định LangGraph trả về `{"node_name": {...}}` (update per-node) chứ không phải full state, gây `KeyError: 'messages'`.
2. **`ConnectionRefusedError` sai loại** (`app/socket_server.py`) — phải import từ `flask_socketio`, không phải builtin của Python, nếu không việc reject connection thiếu JWT sẽ in traceback lỗi thay vì reject "sạch".
3. **eventlet + DNS** — `EVENTLET_NO_GREENDNS=yes` (xem mục 2) để tránh treo 20-30s khi resolve `localhost` (Windows) hoặc tên service Docker.
4. **`Connection: close` trong `ai_client.py`** — tránh treo lâu khi connection pool giữ 1 kết nối cũ tới `api_server` đã restart.
