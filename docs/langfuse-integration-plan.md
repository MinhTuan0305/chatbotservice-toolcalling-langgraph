# Langfuse Integration Plan — shop-langgraph

## 1. Tổng quan

Mục tiêu tích hợp Langfuse vào project để:
- Thay thế / bổ sung cho cơ chế `logs/transcripts.json` hiện tại
- Observe toàn bộ vòng đời một request: LLM call → tool call(s) → final answer
- Track các metadata tương tự transcript hiện có: user input, tool calls (name, args, result), final answer
- Track thêm: prompt, latency, token usage, model info, streaming flag, errors

Self-hosted Langfuse sẽ chạy trên Docker (local hoặc server riêng).

---

## 2. Kiến trúc hiện tại cần hiểu

```
main.py / gui_main.py
    └── graph.stream(...)                   ← LangGraph workflow
            ├── llm node (nodes.py)         ← Gemini via ChatGoogleGenerativeAI
            │       └── llm_with_tools.invoke(prompt_messages)
            └── tools node (ToolNode)       ← ALL_TOOLS
                    └── customer_tools / order_tools / product_tools / revenue_tools

trace_logger.py                             ← hiện đang ghi transcripts.json thủ công
```

**Vấn đề hiện tại với transcripts.json:**
- Không có token count
- Không có latency chi tiết từng bước (chỉ có `execution_metrics.total_time` ở một số record)
- Không có prompt content đầy đủ (system prompt + conversation history)
- Tool calls ở một số record thiếu `result` (do streaming race condition)
- Không có dashboard để query / filter / visualize

---

## 3. Self-hosted Langfuse Setup

### 3.1 Yêu cầu
- Docker & Docker Compose
- Tối thiểu 2GB RAM, 10GB disk

### 3.2 Stack Docker Compose
Langfuse self-hosted cần các service:
| Service | Mục đích |
|---|---|
| `langfuse-web` | Web UI + API server |
| `langfuse-worker` | Background jobs (ingestion, scoring) |
| `postgres` | Database chính của Langfuse |
| `redis` | Queue & cache cho Langfuse worker |
| `clickhouse` | Analytics/OLAP engine (từ Langfuse v3) |
| `minio` (optional) | Object storage cho media/attachments |

> ⚠️ **Lưu ý:** Redis này là Redis riêng của Langfuse, **khác** với Redis checkpointer đang dùng cho LangGraph (`REDIS_URL` trong `.env` hiện tại).

### 3.3 Các biến môi trường cần thêm vào `.env`
```env
# Langfuse self-hosted
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

---

## 4. Langfuse Concepts — Mapping vào project

| Langfuse Concept | Ánh xạ trong project | Dữ liệu nguồn |
|---|---|---|
| **Trace** | Một lượt user hỏi → bot trả lời (1 record trong transcripts.json) | `transcript["id"]`, `timestamp`, `user.input` |
| **Span** | Một bước trong workflow: llm node, tools node | Thời gian bắt đầu/kết thúc từng node |
| **Generation** | Mỗi lần gọi LLM (`llm.invoke`) | `prompt_messages`, `response`, token usage, model name |
| **Event** | Tool call cụ thể | `tool_name`, `arguments`, `result`, `tool_call_id` |
| **Score** (optional) | Đánh giá chất lượng answer | Có thể add sau |

### Ví dụ trace hierarchy cho 1 request:

```
Trace: "id: 70a7d3e7"
  ├── metadata: user_input, timestamp, thread_id, tool_enabled
  ├── Span: "llm_call_1"
  │     └── Generation: model=gemini-2.5-flash, input=prompt_messages, output=tool_calls_request
  │                     tokens={input: X, output: Y}, latency=Zms
  ├── Span: "tool_execution"
  │     ├── Event: tool=search_products, args={category:laptop, max_price:30M}, result=[...]
  │     └── latency=Zms
  ├── Span: "llm_call_2"  (nếu có second LLM call sau tool)
  │     └── Generation: input=..., output=final_answer, tokens={...}
  └── output: final_answer, total_latency, total_tool_count
```

---

## 5. Implementation Plan

### Phase 1 — Infrastructure (Self-hosted Langfuse)

**Việc cần làm:**
1. Tải `docker-compose.yml` chính thức từ Langfuse repo
2. Cấu hình các biến môi trường cho Langfuse services (database URL, secret key, encryption key)
3. Chạy `docker compose up -d`
4. Truy cập UI tại `http://localhost:3000`, tạo project, lấy API keys
5. Lưu `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` vào `.env`

**File thay đổi:** `.env`, `.env.example`

---

### Phase 2 — Cài đặt dependencies

**Packages cần thêm vào `requirements.txt`:**
```
langfuse>=2.0.0          # core SDK (v4.x được install)
```

> **Lưu ý:** Langfuse SDK v4.x sẽ được install (mới nhất). API đã thay đổi so với v2/v3:
> - Không còn `client.trace()`, thay bằng `client.start_observation()`
> - Dùng `@observe()` decorator cho auto-instrumentation
> - Xem [v3 → v4 migration guide](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4)

---

### Phase 3 — Tạo Langfuse callback handler

**Cách tiếp cận:** Dùng `CallbackHandler` của Langfuse — đây là cách tích hợp sâu nhất với LangChain/LangGraph, **tự động** capture:
- Mọi LLM invocation (prompt, response, token count)
- Tool calls và results
- Latency từng step
- Model name, temperature

**File mới cần tạo:** `app/observability/langfuse_client.py`

Nội dung sẽ:
- Khởi tạo `Langfuse` client từ env vars
- Export một hàm `get_langfuse_handler(trace_id, metadata)` trả về `CallbackHandler` đã được configure với trace metadata

---

### Phase 4 — Instrument `call_llm` node (nodes.py)

**Thay đổi trong `app/graph/nodes.py`:**

Truyền `CallbackHandler` vào `llm.invoke(...)` thông qua `config["callbacks"]`:
```python
# Ý tưởng (chưa code):
response = llm_to_use.invoke(
    prompt_messages,
    config={"callbacks": [langfuse_handler]}
)
```

Langfuse callback handler sẽ tự động log:
- Full prompt (system + conversation history)
- Model response
- Token usage (input tokens, output tokens, total)
- Latency của LLM call
- Model name (`gemini-2.5-flash`)

---

### Phase 5 — Instrument `main.py` — Wrap mỗi turn thành 1 Trace

**Thay đổi trong `app/main.py`:**

Mỗi lần user gửi message → tạo 1 trace mới trước khi gọi `graph.stream()`:

```python
# Ý tưởng (chưa code):
trace = langfuse.trace(
    id=str(uuid.uuid4()),       # ← khớp với transcript id
    name="chat_turn",
    input=user_input,
    metadata={
        "thread_id": THREAD_ID,
        "tool_enabled": tool_enabled,
        "timestamp": get_timestamp(),
    }
)
handler = trace.get_langchain_handler()
# truyền handler vào graph.stream config
```

Sau khi stream xong, update trace với:
```python
trace.update(
    output=final_answer,
    metadata={
        "tool_count": len(tool_calls),
        "tool_names": [t["tool_name"] for t in tool_calls],
    }
)
```

**Metadata sẽ được track (mapping từ transcripts.json):**

| transcripts.json field | Langfuse field |
|---|---|
| `id` | `trace.id` |
| `timestamp` | `trace.timestamp` |
| `user.input` | `trace.input` |
| `tool_calls[].tool_name` | span/event name |
| `tool_calls[].arguments` | span/event input |
| `tool_calls[].result` | span/event output |
| `tool_calls[].tool_call_id` | span metadata |
| `assistant.final_answer` | `trace.output` |
| `execution_metrics.total_time` | trace latency (auto) |
| `execution_metrics.tool_count` | `trace.metadata.tool_count` |
| *(new)* prompt content | `generation.input` (auto via callback) |
| *(new)* input tokens | `generation.usage.input` (auto) |
| *(new)* output tokens | `generation.usage.output` (auto) |
| *(new)* per-step latency | span latency (auto via callback) |
| *(new)* model name | `generation.model` (auto) |

---

### Phase 6 — Instrument GUI (`gui_main.py`)

Tương tự Phase 5 nhưng cho GUI entry point. Cần truyền handler qua `backend_bridge.py` → `graph.stream()`.

**File thay đổi:** `app/gui/backend_bridge.py`

---

### Phase 7 — Giữ lại transcripts.json (optional)

Có hai lựa chọn:

**Option A — Replace:** Xóa `save_transcript()` call, hoàn toàn dùng Langfuse  
**Option B — Keep both:** Giữ transcripts.json như local backup, Langfuse là observability layer chính

→ Recommend **Option B** trong giai đoạn đầu để đảm bảo không mất data nếu Langfuse container down.

---

### Phase 8 — Cấu hình Dashboard Langfuse

Sau khi data đã vào Langfuse, setup trên UI:

1. **Traces view:** Filter theo `metadata.thread_id`, `metadata.tool_enabled`
2. **Metrics dashboard:**
   - Average latency per trace
   - Token usage over time
   - Tool call frequency (tool_name distribution)
   - Error rate (traces with empty final_answer)
3. **Prompt management:** Upload `SYSTEM_PROMPT` và `SYSTEM_PROMPT_NO_TOOLS` vào Langfuse Prompt Management để version-control
4. **User tracking:** Tag trace với `userId` nếu muốn theo dõi per-user (hiện chưa có auth)

---

## 6. File Changes Summary

| File | Loại thay đổi | Mô tả |
|---|---|---|
| `.env` | Update | Thêm `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| `.env.example` | Update | Thêm Langfuse env vars (không có value thật) |
| `requirements.txt` | Update | Thêm `langfuse>=2.0.0` |
| `app/observability/langfuse_client.py` | **Tạo mới** | Langfuse client init + helper function |
| `app/config.py` | Update | Load Langfuse env vars |
| `app/graph/nodes.py` | Update | Truyền callback handler vào LLM invocation |
| `app/main.py` | Update | Wrap mỗi turn thành Trace, truyền handler vào graph |
| `app/gui/backend_bridge.py` | Update | Tương tự main.py cho GUI |
| `docker-compose.langfuse.yml` | **Tạo mới** | Docker Compose cho Langfuse self-hosted stack |

---

## 7. Observations về lỗi/quirks trong transcripts.json hiện tại

Những vấn đề này sẽ được phát hiện rõ hơn sau khi có Langfuse:

1. **Tool calls không có `result`** (e.g. id `9e1c4df7`, `ac77165a`, `00c82526`): Tool được call nhưng result không được capture → có thể do timing issue trong streaming
2. **Tool calls không liên quan đến câu hỏi** (e.g. id `6a8d979d` hỏi về Nguyễn Văn An nhưng lại call 24 tools từ context cũ): Vấn đề với checkpointer Redis giữ state từ nhiều turn trước, context window bị lẫn
3. **`final_answer` rỗng** (e.g. id `e02fbdf5`, `ac77165a`, `87c76f8e`): Streaming kết thúc trước khi có LLM response hoàn chỉnh
4. **Câu trả lời từ memory không cần tool** nhưng vẫn gọi tool (id `88a9f809`): LLM đang recall từ conversation history nhưng vẫn trigger tool calls

Langfuse sẽ giúp correlate và debug những pattern này qua trace timeline view.

---

## 8. Thứ tự thực hiện đề xuất

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 8
                                              ↓
                                          Phase 6 (GUI, có thể làm sau)
                                          Phase 7 (quyết định keep/replace json)
```

Có thể verify từng phase độc lập:
- Sau Phase 1: Langfuse UI accessible tại localhost:3000
- Sau Phase 4: LLM calls xuất hiện trong Langfuse với token info
- Sau Phase 5: Full trace với input/output/tool calls/latency visible
