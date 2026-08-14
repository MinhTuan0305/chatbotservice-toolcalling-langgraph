# 🚀 Langfuse Setup — Quick Start

> **Phase 1** của [Langfuse Integration Plan](./docs/langfuse-integration-plan.md)

## Prerequisites

- Docker Desktop đang chạy
- Python environment đã setup (`.venv`)

---

## Step-by-Step

### 1️⃣ Generate Secrets (2 phút)

```bash
# Chạy script để tạo secrets
python scripts\generate_langfuse_secrets.py
```

Output sẽ hiển thị 3 dòng:
```
NEXTAUTH_SECRET=...
ENCRYPTION_KEY=...
SALT=...
```

**→ Copy toàn bộ 3 dòng này.**

### 2️⃣ Cập nhật `.env.langfuse` (1 phút)

Mở file `.env.langfuse`, tìm các dòng sau và **REPLACE**:

```env
# Tìm dòng này:
NEXTAUTH_SECRET=changeme-nextauth-secret-min-32-chars

# Thay bằng giá trị từ step 1:
NEXTAUTH_SECRET=<paste-value-từ-script>
```

Làm tương tự với `ENCRYPTION_KEY` và `SALT`.

### 3️⃣ Start Langfuse (5 phút — lần đầu sẽ download images)

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

**Đợi ~1-2 phút** để tất cả services khởi động.

Kiểm tra status:
```bash
docker compose -f docker-compose.langfuse.yml ps
```

Tất cả phải hiển thị `(healthy)`:
```
langfuse-clickhouse    Up (healthy)
langfuse-minio         Up (healthy)
langfuse-postgres      Up (healthy)
langfuse-redis         Up (healthy)
langfuse-web           Up (healthy)
langfuse-worker        Up (healthy)
```

### 4️⃣ Truy cập UI và tạo account (3 phút)

1. Mở browser: **http://localhost:3000**
2. Click **Sign Up**
3. Điền:
   - Email: `your-email@example.com`
   - Password: `<choose-strong-password>`
   - Name: `Your Name`
4. Click **Create Account**

### 5️⃣ Tạo Project và lấy API Keys (2 phút)

1. Sau khi đăng nhập → click **New Project**
2. Project name: `shop-langgraph`
3. Click **Create**
4. Vào project → click **Settings** (góc phải trên)
5. Tab **API Keys** → copy:
   - **Public Key** (bắt đầu `pk-lf-...`)
   - **Secret Key** (bắt đầu `sk-lf-...`)

### 6️⃣ Lưu keys vào `.env` chính (1 phút)

Mở file `.env` (KHÔNG phải `.env.langfuse`), thêm vào cuối:

```env
# Langfuse Observability
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxxxxxxxxxx
```

**Paste giá trị thật từ step 5.**

---

## ✅ Verify Setup

```bash
# Check tất cả services healthy
docker compose -f docker-compose.langfuse.yml ps

# Check logs nếu có issue
docker compose -f docker-compose.langfuse.yml logs -f langfuse-web
```

Mở browser: http://localhost:3000 → phải thấy dashboard với project `shop-langgraph`

---

## 🎉 Done!

**Phase 1 hoàn thành!** Bạn đã có:

- ✅ Langfuse v4 self-hosted đang chạy
- ✅ Database (Postgres, ClickHouse) được provision
- ✅ S3 storage (MinIO) sẵn sàng
- ✅ API keys đã được tạo và lưu

**Next:** Phase 2 — Install Python SDK

```bash
pip install langfuse>=2.0.0
```

Xem chi tiết roadmap trong [docs/langfuse-integration-plan.md](./docs/langfuse-integration-plan.md)

---

## Troubleshooting

### Port 3000 bị chiếm
```bash
# Tìm process đang dùng port
netstat -ano | findstr :3000

# Kill process hoặc đổi port trong docker-compose.langfuse.yml
```

### Container không start
```bash
# Xem logs
docker compose -f docker-compose.langfuse.yml logs langfuse-web

# Restart specific service
docker compose -f docker-compose.langfuse.yml restart langfuse-web
```

### Quên password UI
Stop containers → xóa Postgres volume → start lại:
```bash
docker compose -f docker-compose.langfuse.yml down -v
# Lưu ý: -v sẽ xóa toàn bộ data
docker compose -f docker-compose.langfuse.yml up -d
```

Xem thêm troubleshooting trong [docs/LANGFUSE_SETUP.md](./docs/LANGFUSE_SETUP.md)

---

## Useful Commands

```bash
# Stop (giữ data)
docker compose -f docker-compose.langfuse.yml stop

# Start lại
docker compose -f docker-compose.langfuse.yml start

# Xem logs realtime
docker compose -f docker-compose.langfuse.yml logs -f

# Restart toàn bộ
docker compose -f docker-compose.langfuse.yml restart

# Xóa toàn bộ (bao gồm volumes)
docker compose -f docker-compose.langfuse.yml down -v
```
