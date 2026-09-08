# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Vietnamese-language shop customer-service chatbot built on LangGraph + Google Gemini, with tool calling against a PostgreSQL shop database, Redis-backed conversation memory, and Langfuse observability. It can run as a CLI, or as a web-facing real-time service (Socket.IO gateway + FastAPI agent service behind Nginx).

## Commands

There is no test suite, linter, or build step in this repo (no `pytest`/`ruff`/`pyproject.toml`/CI config exist despite `hypothesis` being listed in `requirements.txt`).

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, DATABASE_URL, JWT_SECRET_KEY, API_KEY, ...

# Run: CLI mode (simplest, no other services needed besides Redis)
docker run -d --name redis -p 6379:6379 redis:8
python app/main.py

# Run: Web/Socket mode, directly on host (two processes)
python -m app.api_server      # FastAPI AI agent service, port 8000
python -m app.socket_server   # Flask-SocketIO real-time gateway, port 5000
# then open client-examples/test.html, Gateway URL = http://localhost:5000

# Run: Web/Socket mode via Docker Compose (adds Nginx on :80, its own Redis)
docker compose up -d --build
# then open client-examples/test.html, Gateway URL = http://localhost

# Optional: Langfuse observability stack
docker compose -f docker-compose.langfuse.yml up -d   # http://localhost:3000
```

Note: the Redis started manually (`docker run redis:8`) and the Redis inside `docker-compose.yml` (`redis/redis-stack-server`) are separate instances — conversation threads are not shared between running the app directly on the host vs. via `docker compose up`. The compose Redis image must be `redis-stack-server`, not plain `redis`, because `langgraph-checkpoint-redis` needs the RediSearch (`FT.*`) module to index checkpoints.

## Architecture

### LangGraph agent (the core, shared by every entry point)

`app/service.py`'s `ChatService` builds and drives the graph from `app/graph/workflow.py`. It is consumed by `app/main.py` (CLI), and by `app/api_server.py` (web mode) — never called directly from `app/socket_server.py`.

Graph shape (`app/graph/workflow.py`): `START -> llm -> (tools -> llm | END)`, compiled with a Redis-backed checkpointer (`app/db/redis.py`) keyed by `thread_id`, so conversation state persists across turns/processes.

- `app/graph/nodes.py` — the `llm` node. Binds `ALL_TOOLS` (`app/tools/__init__.py`) to `ChatGoogleGenerativeAI`, picks between a tools-enabled and a no-tools system prompt based on `config.configurable.tool_enabled`, trims history via `trim_messages(max_tokens=MAX_CONTEXT_TOKENS)`.
- `app/graph/router.py` — `tool_router`: routes straight to `END` when `tool_enabled` is `False` in config, otherwise defers to `tools_condition`. This is how the runtime "tool toggle" feature works — no restart needed.
- `app/tools/*.py` — each tool calls `app/db/connection.py:execute_query`, which hard-rejects any query that isn't a `SELECT` (the only write-safety guard in this codebase — respect it when adding tools).
- System prompts (in `nodes.py`) are the actual behavior contract for the agent: Vietnamese-only, tool-sourced data only, no fabricated IDs/prices, refuse out-of-scope questions. Read them before changing agent behavior.

### Web/Socket service split

Two independently-run services talk over plain HTTP; see `docs/WEB_GATEWAY_ARCHITECTURE.md` for the full rationale and diagrams.

```
Browser --Socket.IO/HTTP--> Nginx(:80) --> socket_server.py(:5000) --HTTP/SSE--> api_server.py(:8000) --> Redis + Postgres
```

- **`app/api_server.py`** — FastAPI, owns the LangGraph agent exclusively. `POST /chat` (full response), `POST /chat/stream` (SSE, one open connection for the whole answer, not one request per chunk), `GET /health`. Protected by `x-api-key` (service-to-service secret, `API_KEY` env var).
- **`app/socket_server.py`** — Flask-SocketIO gateway. Knows nothing about LangGraph; forwards every chat event to `api_server` via `app/ai_client.py` and emits the result back into the caller's Socket.IO room. Owns connection lifecycle, JWT auth, per-thread rooms, rate limiting (`flask-limiter`), and `/auth/token`, `/health`, `/stats`, `/metrics`.
  - Must monkey-patch first: the file's first lines are `os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")`, `import eventlet`, `eventlet.monkey_patch()` — before any other import, or blocking calls (e.g. `requests` in `ai_client.py`) stall the whole event loop for every connected client. `EVENTLET_NO_GREENDNS` avoids eventlet's own DNS resolver hanging 20-30s on `localhost`/Docker service names.
- **`app/ai_client.py`** — the only file that knows `api_server` exists. Sends `Connection: close` on every request deliberately, to avoid a pooled keep-alive connection pointing at a since-restarted `api_server` (detecting a dead eventlet connection can otherwise take 20-30s via OS-level TCP timeout instead of failing fast).
- **`app/auth.py`** — JWT issuance/verification (`JWT_SECRET_KEY`, distinct secret from `API_KEY`). `POST /auth/token` is a demo issuer (accepts any `user_id`, no password) — replace before production. Enforced invariant: **1 authenticated user = 1 thread_id** (`authorize_thread()` in `socket_server.py` requires `thread_id == user_id`), which is what stops one client from reading/writing another's conversation by guessing a thread id.
- **`nginx/nginx.conf`** — single public entrypoint (port 80), routes `/socket.io/`, `/auth/`, `/health|/stats|/metrics` to `socket_server`; deliberately never routes to `api_server` (internal-only). Requires `Upgrade`/`Connection: upgrade` headers for the Socket.IO WebSocket upgrade.
- `TRUST_PROXY_HEADERS=true` enables Werkzeug's `ProxyFix` in `socket_server.py` so IP-based rate limiting sees the real client IP from Nginx's `X-Forwarded-For` — only enable this when actually running behind a trusted reverse proxy; otherwise clients can spoof that header to dodge rate limits.

### Config

All configuration is read from environment via `python-dotenv` in `app/config.py` (single source of truth for env var names/defaults). `.env.example` documents every variable. `AI_SERVICE_URL` defaults to `http://127.0.0.1:8000` (not `localhost`, to dodge eventlet DNS issues) and is overridden to `http://api_server:8000` inside `docker-compose.yml`.

`Dockerfile` builds one shared image for both `api_server` and `socket_server`; `docker-compose.yml` just overrides the `command:` per service.
