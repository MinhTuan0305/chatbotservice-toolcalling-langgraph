# 🛍️ Shop Customer Service Chatbot

AI-powered customer service chatbot built with LangGraph, featuring multi-turn conversations, tool calling, and full observability.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2.9-green)
![Gemini](https://img.shields.io/badge/Google-Gemini-orange)
![Redis](https://img.shields.io/badge/Redis-Memory-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)
![Langfuse](https://img.shields.io/badge/Langfuse-Observability-purple)

---

## 📋 Overview

This chatbot helps customers query information about products, orders, and customers from a PostgreSQL database using natural language (Vietnamese). It uses LangGraph for workflow orchestration, Google Gemini as the LLM, and includes full observability through Langfuse.

### Key Features

- ✅ **Multi-turn Conversations** - Maintains context across messages
- 🛠️ **Tool Calling** - Queries database to answer customer questions
- 💾 **Persistent Memory** - Redis-based conversation state
- 🔄 **Streaming Responses** - Real-time token-by-token output (CLI, WebSocket, and SSE)
- 📊 **Full Observability** - Langfuse integration for tracing and analytics
- 🌐 **Vietnamese Support** - Native Vietnamese language responses
- ⚡ **Runtime Tool Toggle** - Enable/disable tools without restart
- 🖥️ **CLI or Web** - Run as a local CLI, or as a Socket.IO + REST service for a browser/mobile client
- 🔐 **JWT Authentication** - End-user clients authenticate before joining a conversation thread
- 🌉 **Nginx-fronted, containerized** - `docker-compose.yml` runs the full stack (Nginx, Socket gateway, AI Agent service, Redis) behind a single entrypoint

---

## 🏗️ Architecture

### Agent Workflow

![System Flow](images/system_flow.png)

Inside the agent, user input goes through the LLM, which can optionally call tools to query the database, and then generates a final response.

![Component Flow](images/component_flow.png)

**Agent Layers:**

1. **LangGraph Orchestration** - State management and workflow routing
2. **LLM Layer** - Google Gemini 2.5 Flash for natural language understanding
3. **Tool Layer** - 6 specialized tools for database queries
4. **Data Layer** - PostgreSQL for business data, Redis for conversation state
5. **Observability** - Langfuse for tracing, metrics, and debugging

### Service Architecture (Web/Socket mode)

The agent above is reused by two different front doors:

- **`app/main.py`** - a CLI loop that talks to the agent directly, in-process. Good for local testing, no other services required.
- **A 3-tier service stack**, for a real browser/mobile client:

```
Browser/mobile client
        │  WebSocket (Socket.IO) + REST
        ▼
   Nginx (:80)                    ← single public entrypoint, TLS termination point
        │  proxies /socket.io, /auth, /health, /stats, /metrics
        ▼
  socket_server.py (:5000)        ← real-time gateway (Flask-SocketIO)
   - JWT auth on connect (POST /auth/token issues a demo token)
   - enforces 1 user = 1 conversation thread
   - holds NO LangGraph/LLM logic itself
        │  HTTP (POST /chat) / SSE (POST /chat/stream), via app/ai_client.py
        ▼
  api_server.py (:8000)           ← AI Agent service (FastAPI), internal only
   - owns the LangGraph agent, LLM, tools, checkpointer
        │
        ▼
   Redis (checkpointer) + PostgreSQL (shop data)
```

Why split `socket_server` and `api_server`: the real-time/connection-handling concern (Socket.IO rooms, rate limiting, auth) is independent from the AI/agent concern (LangGraph, LLM, tools), so each can be reasoned about, scaled, and deployed separately. Streaming between them uses a single held-open SSE connection per request (`app/ai_client.py`), not a new HTTP call per token.

See [`docker-compose.yml`](docker-compose.yml) to run the whole stack, or run `api_server.py`/`socket_server.py` directly for local development (see Quick Start below).

---

## 🛠️ Available Tools

The chatbot can use these tools to answer customer queries:

| Tool | Purpose | Example Query |
|------|---------|---------------|
| `search_products` | Find products by category and price | "Cho tôi laptop dưới 30 triệu" |
| `get_customer_by_name` | Look up customer info | "Thông tin khách Nguyễn Văn An" |
| `get_customer_orders` | Get customer's order history | "Các đơn hàng của khách An" |
| `get_order_detail` | Get detailed order info | "Đơn #4 gồm những gì?" |
| `get_revenue_by_category` | Calculate revenue by category | "Danh mục nào bán chạy nhất?" |
| `get_top_customers` | Get top spending customers | "Top 5 khách hàng VIP" |

---

## 📁 Project Structure

```
shop-langgraph/
├── app/
│   ├── main.py                    # CLI entry point (talks to the agent in-process)
│   ├── service.py                 # ChatService — wraps the LangGraph agent (used by main.py and api_server.py)
│   ├── api_server.py              # AI Agent service (FastAPI, :8000) — POST /chat, POST /chat/stream (SSE)
│   ├── socket_server.py           # Real-time gateway (Flask-SocketIO, :5000) — JWT auth, rooms, rate limiting
│   ├── ai_client.py               # HTTP client socket_server uses to call api_server
│   ├── auth.py                    # JWT create/verify for end-user clients (see POST /auth/token)
│   ├── config.py                  # Environment configuration
│   │
│   ├── graph/
│   │   ├── workflow.py           # LangGraph workflow setup
│   │   ├── nodes.py              # LLM and tool nodes
│   │   ├── state.py              # Conversation state definition
│   │   └── router.py             # Conditional routing logic
│   │
│   ├── tools/
│   │   ├── customer_tools.py     # Customer-related queries
│   │   ├── order_tools.py        # Order-related queries
│   │   ├── product_tools.py      # Product search
│   │   └── revenue_tools.py      # Revenue analytics
│   │
│   ├── db/
│   │   ├── connection.py         # PostgreSQL connection
│   │   └── redis.py              # Redis checkpointer (needs RediSearch — Redis 8+ or Redis Stack)
│   │
│   └── observability/
│       └── langfuse_client.py    # Langfuse integration
│
├── client-examples/
│   └── test.html                  # Minimal browser test client (login → JWT → Socket.IO chat)
│
├── nginx/
│   └── nginx.conf                 # Reverse proxy config used by docker-compose.yml
│
├── docs/                          # Detailed documentation
├── images/                        # Architecture diagrams
├── Dockerfile                     # Shared image for api_server.py / socket_server.py
├── docker-compose.yml             # Full stack: nginx + socket_server + api_server + redis
├── docker-compose.langfuse.yml   # Langfuse observability stack (separate, optional)
├── requirements.txt              # Python dependencies
└── .env                          # Environment variables
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL database with shop data
- Redis server
- Google Gemini API key
- (Optional) Docker for Langfuse

### 1. Clone Repository

```bash
git clone <your-repository-url>
cd shop-langgraph
```

### 2. Create Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Create a `.env` file in the project root:

```env
# LLM Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/shop_db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Langfuse Observability (Optional)
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key

# Required only if you'll run socket_server.py (Web/Socket mode, see below)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-jwt-secret-here
API_KEY=your-service-api-key-here
```

See [`.env.example`](.env.example) for the full list, including Socket server / rate limiting / Nginx-related options.

### 5. Start Redis

The LangGraph checkpointer needs the RediSearch module (`FT.*` commands) — plain `redis:7` does **not** have it. Use Redis 8+ (bundles it) or `redis/redis-stack-server` for older major versions.

Using Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:8
```

Or if container exists:

```bash
docker start redis
```

### 6. (Optional) Start Langfuse

For full observability with traces and dashboards:

```bash
docker compose -f docker-compose.langfuse.yml up -d

# Wait ~30 seconds for services to initialize
# Open http://localhost:3000 to access Langfuse UI
# Create a project and get API keys for .env
```

### 7. Run the Chatbot

**Option A — CLI** (simplest, no other services):

```bash
python app/main.py
```

**Option B — Web/Socket mode** (what a browser or mobile client talks to), directly on your host — needs two terminals:

```bash
python -m app.api_server
```
```bash
python -m app.socket_server
```

Then open [`client-examples/test.html`](client-examples/test.html) in a browser, set Gateway URL to `http://localhost:5000`, log in with any user ID (issues a demo JWT via `POST /auth/token`), and chat.

**Option C — Docker Compose** (same Web/Socket mode, containerized, fronted by Nginx on port 80):

```bash
docker compose up -d --build
```

Then open `client-examples/test.html` with Gateway URL set to `http://localhost` (port 80, through Nginx) instead of `:5000`. See [`docker-compose.yml`](docker-compose.yml) — this starts its own Redis (`redis/redis-stack-server`), separate from the one in step 5, so conversation threads are not shared between the two ways of running the project.

---

## 💬 Usage Examples

### Starting a Conversation

```
Conversation ID: shop-001
SHOP CUSTOMER SERVICE CHATBOT
Nhập 'exit' để thoát.
✅ Langfuse tracking enabled

User: 
```

### Example 1: Product Search

```
User: Cho tôi xem các sản phẩm laptop giá dưới 30 triệu.

Bot: Đây là các sản phẩm laptop có giá dưới 30 triệu:
* MacBook Air M3, giá 28.000.000 VNĐ
* Asus ZenBook, giá 18.000.000 VNĐ
```

**Tools used:** `search_products(category="laptop", max_price=30000000)`

### Example 2: Customer Orders

```
User: Khách hàng Nguyễn Văn An có những đơn hàng nào?

Bot: Khách hàng Nguyễn Văn An có các đơn hàng sau:
* Đơn hàng ID: 11, ngày đặt: 22/07/2024, trạng thái: đã hoàn thành, 
  ngày giao: 24/07/2024, tổng tiền: 30.000.000 VNĐ
* Đơn hàng ID: 2, ngày đặt: 02/07/2024, trạng thái: đã hoàn thành, 
  ngày giao: 04/07/2024, tổng tiền: 2.050.000 VNĐ
```

**Tools used:** `get_customer_by_name("Nguyễn Văn An")` → `get_customer_orders(customer_id=1)`

### Example 3: Order Details

```
User: Đơn hàng #4 gồm những sản phẩm gì, đã giao chưa?

Bot: Đơn hàng #4 bao gồm các sản phẩm sau:
- 1 sản phẩm Xiaomi 14 với giá 15,000,000.00 VNĐ
- 1 sản phẩm Chuột không dây với giá 350,000.00 VNĐ

Đơn hàng này hiện đang ở trạng thái "pending" và chưa được giao.
```

**Tools used:** `get_order_detail(order_id=4)`

### Example 4: Revenue Analytics

```
User: Danh mục nào đang bán chạy nhất về doanh thu?

Bot: Dựa trên doanh thu từ các đơn hàng đã hoàn thành, 
danh mục "Điện thoại" đang bán chạy nhất với doanh thu 74,000,000.00 VNĐ.
```

**Tools used:** `get_revenue_by_category()`

### Example 5: Top Customers

```
User: Top 3 khách hàng chi tiêu nhiều nhất là ai?

Bot: Top 3 khách hàng chi tiêu nhiều nhất là:
1. Nguyễn Văn An (ID: 1) từ Hà Nội, đã chi tiêu 58,550,000.00 VNĐ.
2. Phạm Thị Dung (ID: 4) từ Hà Nội, đã chi tiêu 33,200,000.00 VNĐ.
3. Trần Thị Bình (ID: 2) từ Hồ Chí Minh, đã chi tiêu 28,000,000.00 VNĐ.
```

**Tools used:** `get_top_customers(limit=3)`

### Example 6: Out-of-Scope Query

```
User: Cho tôi mã giảm giá 50%.

Bot: Tôi xin lỗi, tôi không có chức năng tạo hoặc cung cấp mã giảm giá.
```

**Tools used:** None (LLM recognizes it's out of scope)

---

## ⚙️ Advanced Features

### Runtime Tool Toggle

Control tool calling during conversation without restarting:

```
User: /tool off
Tool disabled.

User: Cho tôi xem sản phẩm laptop
Bot: Xin lỗi, tôi không thể truy vấn dữ liệu hiện tại vì chức năng công cụ (Tools) 
đang tắt. Vui lòng bật công cụ (Tools toggle) để tôi có thể giúp bạn tra cứu 
thông tin từ database.

User: /tool on
Tool enabled.

User: Cho tôi xem sản phẩm laptop
Bot: [Uses tools to query database]
```

### Multi-turn Conversations

The chatbot maintains conversation context using Redis checkpointer:

```
User: Khách hàng Trần Thị Bình có bao nhiêu đơn hàng?
Bot: Khách hàng Trần Thị Bình có 2 đơn hàng.

User: Tính luôn cả đơn đã hủy không?
Bot: Có, tính cả đơn đã hủy. Cụ thể:
* Đơn hàng #6 (đã hủy): 20,000,000.00 VNĐ
* Đơn hàng #3 (đã hoàn thành): 28,000,000.00 VNĐ
```

Each `thread_id` creates an independent conversation with its own memory.

### Exit Conversation

```
User: exit
Đã thoát chatbot.
```

---

## 📊 Observability with Langfuse

### What Gets Tracked

When Langfuse is enabled, every conversation turn is logged as a **trace** with:

- ✅ Full conversation context (user input + system prompts)
- ✅ LLM generations (requests and responses)
- ✅ Tool calls (name, arguments, results)
- ✅ Latency per operation
- ✅ Token usage (if provided by Gemini)
- ✅ Session tracking (thread_id)

### Accessing the Dashboard

1. Open http://localhost:3000
2. Navigate to **Traces** section
3. Filter by:
   - `session_id` (thread_id) - View specific conversations
   - `metadata.tool_enabled` - See tool usage patterns
   - Date range - Analyze trends over time

### Dashboard Features

- **Trace Timeline** - Visual timeline of each conversation turn
- **Token Analytics** - Track token usage and costs
- **Latency Metrics** - Performance monitoring
- **Tool Usage Stats** - Most frequently called tools
- **Error Tracking** - Failed tool calls or LLM errors

For detailed dashboard setup, see `docs/PHASE8_DASHBOARD_SETUP.md`.

---

## 🔧 Configuration

### Environment Variables

**Core agent (needed for CLI and Web/Socket mode):**

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Model name (default: gemini-2.5-flash) |
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string |
| `REDIS_URL` | ✅ Yes | Redis connection string (needs RediSearch — Redis 8+ or Redis Stack) |
| `MAX_CONTEXT_TOKENS` | No | Trims history to this many tokens (default: 4000) |
| `LANGFUSE_HOST` | No | Langfuse server URL (for observability) |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |

**Web/Socket mode only** (`app/api_server.py` + `app/socket_server.py`):

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Recommended | Service-to-service secret: gates socket_server's `/health`/`/stats`/`/metrics` and socket_server → api_server calls. Unset = unprotected (dev only). |
| `JWT_SECRET_KEY` | ✅ Yes | Signs end-user JWTs issued by `POST /auth/token`. Different secret than `API_KEY`. |
| `JWT_EXPIRE_MINUTES` | No | Token lifetime (default: 60) |
| `AI_SERVICE_URL` | No | Where socket_server reaches api_server (default: `http://127.0.0.1:8000`; set to `http://api_server:8000` in Docker) |
| `SOCKET_HOST` / `SOCKET_PORT` | No | Bind address for socket_server (default `0.0.0.0:5000`) |
| `API_HOST` / `API_PORT` | No | Bind address for api_server (default `0.0.0.0:8000`) |
| `CORS_ORIGINS` | No | Allowed origins for Socket.IO/HTTP (default `*` — restrict in production) |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_CHAT` | No | Per-IP rate limiting |
| `TRUST_PROXY_HEADERS` | No | Set `true` only when behind exactly one trusted reverse proxy hop (e.g. the Nginx service in `docker-compose.yml`) — otherwise a client can spoof `X-Forwarded-For` to dodge rate limits |

See [`.env.example`](.env.example) for the full list with defaults.

### Database Schema

The chatbot expects these PostgreSQL tables:

- `customers` - Customer information
- `orders` - Order records
- `order_items` - Order line items
- `products` - Product catalog

### Redis Usage

Redis is used exclusively for LangGraph checkpointing:
- Key pattern: `langgraph:checkpoint:{thread_id}:{checkpoint_ns}`
- Stores conversation state (messages, metadata)
- No expiration (persistent memory)

---

## 🧪 Testing

### Manual Testing

See `logs/transcripts.json` for 8 documented test cases covering:
1. Product search by category and price
2. Customer order lookup
3. Order details with status
4. Revenue analytics by category
5. Top customer ranking
6. Multi-criteria queries
7. Non-existent entity handling
8. Out-of-scope request handling

### Running Tests

```bash
# Test with different thread IDs for isolated conversations
python app/main.py
# Enter thread_id: test-001

python app/main.py
# Enter thread_id: test-002
```

### Verifying Langfuse Integration

```bash
# Check Langfuse connection
python scripts/verify_langfuse_connection.py

# Expected output:
# ✅ Connection successful!
# Observation ID: ...
```

---

## 🐛 Troubleshooting

### Issue: Chatbot doesn't start

**Check Python version:**
```bash
python --version  # Should be 3.10+
```

**Verify dependencies:**
```bash
pip install -r requirements.txt
```

### Issue: Tool calls fail

**Check database connection:**
```bash
# Test PostgreSQL connection
psql $DATABASE_URL -c "SELECT 1;"
```

**Verify Redis:**
```bash
redis-cli ping  # Should return PONG
```

### Issue: Langfuse not tracking

**Check Langfuse container:**
```bash
docker compose -f docker-compose.langfuse.yml ps
# All services should be "Up"
```

**Verify credentials in .env:**
```bash
cat .env | grep LANGFUSE
```

**Test connection:**
```bash
python scripts/verify_langfuse_connection.py
```

### Issue: Out of memory errors

**Increase Docker resources** (for Langfuse):
- Minimum: 2GB RAM, 10GB disk
- Recommended: 4GB RAM, 20GB disk

---

## 📚 Documentation

- `docs/WEB_GATEWAY_ARCHITECTURE.md` - What each Web/Socket piece (socket_server, api_server, JWT, Nginx, Docker) is and does
- `docs/langfuse-integration-plan.md` - Langfuse architecture and implementation
- `docs/QUICKSTART_LANGFUSE.md` - Langfuse quick start

---

## 🛣️ Roadmap

### Current Version (3.0)
- ✅ CLI chatbot (`app/main.py`)
- ✅ Web/Socket mode: `socket_server.py` (Socket.IO gateway) + `api_server.py` (AI Agent REST/SSE service)
- ✅ JWT authentication for end-user clients
- ✅ Nginx reverse proxy + Docker Compose stack
- ✅ 6 database query tools
- ✅ Redis-based memory
- ✅ Langfuse observability
- ✅ Vietnamese language support

### Future Enhancements
- 🔮 Real user accounts (the current `POST /auth/token` is a demo issuer with no password check)
- 🔮 Multi-language support
- 🔮 Advanced analytics
- 🔮 Custom tool creation
- 🔮 RAG for product recommendations

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

[Add your license here]

---

## 🙏 Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Workflow orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Google Gemini](https://ai.google.dev/) - Language model
- [Langfuse](https://langfuse.com/) - Observability platform
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Redis](https://redis.io/) - In-memory store

---

**Built with ❤️ using LangGraph and Langfuse**
