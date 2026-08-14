# ✅ Phase 3 Complete: Langfuse Integration vào LangGraph

## Tóm Tắt

Phase 3 đã tích hợp Langfuse tracking vào LangGraph workflow sử dụng **CallbackHandler** (SDK v4).

## Files Đã Tạo/Sửa

### 1. Tạo Mới: `app/observability/langfuse_client.py`
- `is_langfuse_enabled()` - kiểm tra credentials có được config chưa
- `get_langfuse_client()` - singleton Langfuse client
- `get_langfuse_handler()` - tạo CallbackHandler với metadata
- `flush_langfuse()` - flush events khi thoát

**SDK v4 approach:** Dùng standalone `CallbackHandler()` thay vì `trace.get_langchain_handler()`

**Import path:** `from langfuse.langchain import CallbackHandler` (NOT `langfuse.callback`)

### 2. Cập Nhật: `app/config.py`
```python
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
```

### 3. Cập Nhật: `app/graph/nodes.py`
```python
# Lấy callbacks từ config
callbacks = config.get("callbacks", [])

# Pass vào LLM invoke
response = llm_to_use.invoke(prompt_messages, config={"callbacks": callbacks})
```

### 4. Cập Nhật: `app/main.py`
```python
# Import
from app.observability.langfuse_client import (
    get_langfuse_handler, is_langfuse_enabled, flush_langfuse
)

# Tạo handler (no parameters!)
langfuse_handler = get_langfuse_handler()

# Pass vào graph.stream() với metadata
config={
    "configurable": {...},
    "callbacks": [langfuse_handler] if langfuse_handler else [],
    "metadata": {
        "langfuse_session_id": THREAD_ID,
        "langfuse_metadata": {
            "thread_id": THREAD_ID,
            "tool_enabled": str(tool_enabled),
        },
    },
}

# Flush khi exit
flush_langfuse()
```

**LangChain integration v4 API:**
- `CallbackHandler()` không nhận parameters
- Trace attributes set qua `config["metadata"]["langfuse_*"]`

## Cách Hoạt Động

1. **Khi chạy `app/main.py`:**
   - Kiểm tra Langfuse credentials có được config chưa
   - Hiện thông báo tracking enabled/disabled

2. **Mỗi chat turn:**
   - Tạo `CallbackHandler` với `trace_name` và `session_id`
   - Pass handler vào `graph.stream()` qua `config["callbacks"]`
   - LangGraph tự động forward callbacks vào các node

3. **Trong `call_llm` node:**
   - Lấy callbacks từ config
   - Pass vào `llm.invoke()` để Langfuse capture:
     - LLM input (system prompt + messages)
     - LLM output (response content)
     - Model info (gemini-2.5-flash)
     - Latency, tokens (nếu Gemini cung cấp)
     - Tool calls (nếu có)

4. **Tool execution:**
   - LangGraph's `ToolNode` tự động forward callbacks
   - Langfuse auto-captures tool name, args, result

5. **Khi exit:**
   - `flush_langfuse()` gửi tất cả pending events

## Điều Chỉnh So Với Plan Ban Đầu

| Plan (v2 API) | Reality (v4 API) |
|---|---|
| `trace = client.trace()` | `handler = CallbackHandler()` |
| `trace.get_langchain_handler()` | Standalone handler |
| Manual trace update | Auto-capture qua callback |

**v4 đơn giản hơn:** Không cần manual trace management, chỉ cần pass handler!

## Testing

### 1. Chạy Bot
```bash
python app/main.py
```

### 2. Kiểm tra output
```
Conversation ID: test-123
SHOP CUSTOMER SERVICE CHATBOT
Nhập 'exit' để thoát.
✅ Langfuse tracking enabled
```

### 3. Chat thử
```
User: top 5 khách hàng mua nhiều nhất
Bot: [gọi tool get_top_customers → trả lời]
```

### 4. Xem Langfuse UI
```
http://localhost:3000
```

**Trong UI sẽ thấy:**
- Trace name: `chat_turn_test-123`
- Session ID: `test-123`
- Metadata: `{"thread_id": "test-123", "tool_enabled": "True"}`
- Spans:
  - LLM generation (system prompt + user input → AI response)
  - Tool calls (nếu có): tool name, args, result
  - Latency, tokens (nếu có)

## Auto-Captured Data

Langfuse CallbackHandler tự động capture:

✅ **LLM Calls:**
- Model name (gemini-2.5-flash)
- Input messages (system + user)
- Output content
- Latency
- Tokens (nếu Gemini trả về usage metadata)

✅ **Tool Calls:**
- Tool name (get_top_customers, etc.)
- Arguments (limit, filters)
- Result/output
- Latency

✅ **Metadata:**
- Session ID (thread_id)
- Custom metadata (tool_enabled, etc.)

❌ **Không tự động capture:**
- Final answer text formatting (vì đó là post-processing)
- Transcript JSON format (vẫn cần `save_transcript()`)

## Nếu Không Muốn Enable Langfuse

**Option 1:** Không config credentials trong `.env`
```bash
# Để trống hoặc xóa
# LANGFUSE_HOST=...
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
```

Bot vẫn chạy bình thường, chỉ không track vào Langfuse:
```
⚠️  Langfuse tracking disabled (credentials not configured)
```

**Option 2:** Stop Docker stack
```bash
docker compose -f docker-compose.langfuse.yml down
```

## Next Steps

✅ **Phase 1:** Infrastructure ✓  
✅ **Phase 2:** SDK Installation ✓  
✅ **Phase 3:** Integration ✓  

**Phase 4 (optional):** Tích hợp vào GUI (`app/gui_main.py`)  
**Phase 5 (optional):** Custom spans cho specific functions  
**Phase 6:** Dashboard & alerts setup trong Langfuse UI

## Troubleshooting

### Handler không được pass vào tool calls
**Nguyên nhân:** LangGraph's `ToolNode` cần config callbacks  
**Fix:** ✅ Đã xử lý - callbacks được forward tự động qua config

### Không thấy traces trong UI
```bash
# Check Langfuse running
docker compose -f docker-compose.langfuse.yml ps

# Check credentials đúng
cat .env | grep LANGFUSE

# Check có errors không
python scripts/verify_langfuse_connection.py
```

### Metadata lỗi "must be dict[str, str]"
**Fix:** ✅ Đã xử lý - `langfuse_client.py` auto-convert values sang string

## Kết Luận

Phase 3 hoàn thành tích hợp Langfuse vào LangGraph với:
- ✅ Auto-capture LLM calls (input/output/latency/tokens)
- ✅ Auto-capture tool calls (name/args/result)
- ✅ Session tracking (thread_id)
- ✅ Metadata propagation
- ✅ Graceful degradation (bot vẫn chạy nếu Langfuse disabled)

**Approach đơn giản:** 1 CallbackHandler → pass vào config → auto-capture everything!
