# Socket Server Implementation Plan

**Project:** Shop Customer Service Chatbot - Socket Server Integration  
**Framework:** Flask-SocketIO  
**Date:** 2026-08-14  
**Estimate:** 10-16 hours

---

## 📋 Overview

Transform the CLI chatbot into a socket-based service that can be consumed by web/mobile clients.

**Current Architecture:**
```
User (Terminal) → CLI (main.py) → LangGraph → Database
```

**Target Architecture:**
```
Client (Browser/App) ↔ Socket Server ↔ AI Service → LangGraph → Database
```

---

## 🎯 Goals

1. **Separate concerns:** CLI, Service, Socket Server
2. **Enable real-time communication** with Socket.IO
3. **Support streaming responses** token-by-token
4. **Maintain existing features** (tools, memory, Langfuse)
5. **Allow concurrent users** via thread-safe state

---

## 📐 Phase 1: Refactor AI Service (3-4 hours)

### 1.1 Create Service Module

**File:** `app/service.py`

**Purpose:** Extract chatbot logic from CLI into reusable service

**Class Structure:**
```python
class ChatService:
    def __init__(self):
        # Initialize graph once
        self.graph = build_graph()
        
    def process_message(self, user_input, thread_id, tool_enabled=True):
        # Non-streaming: Return final answer
        
    def process_message_stream(self, user_input, thread_id, tool_enabled=True):
        # Streaming: Yield chunks
        
    def get_langfuse_handler(self):
        # Return Langfuse handler if enabled
```

**Methods to Extract from `main.py`:**

1. **`process_message()` - Non-streaming**
   - Input: `user_input`, `thread_id`, `tool_enabled`
   - Process: Invoke graph with config
   - Output: `{"final_answer": str, "tool_calls": list, "execution_metrics": dict}`

2. **`process_message_stream()` - Streaming**
   - Input: Same as above
   - Process: Stream graph with `stream_mode=["messages", "values"]`
   - Output: Generator yielding `{"type": "chunk|done|error", "data": ...}`

3. **`_extract_final_answer()` - Helper**
   - Extract final answer from messages

4. **`_extract_tool_calls()` - Helper**
   - Extract tool calls from current turn

**Edge Cases:**
- Empty input → Return error
- Graph timeout → Return error after 30s
- Tool calls fail → Capture in response

---

### 1.2 Update CLI to Use Service

**File:** `app/main.py`

**Changes:**
```python
from app.service import ChatService

def chat():
    service = ChatService()
    
    # Replace graph.stream() with service.process_message_stream()
    for event in service.process_message_stream(user_input, THREAD_ID, tool_enabled):
        if event["type"] == "chunk":
            print(event["data"], end="", flush=True)
        elif event["type"] == "done":
            # Final answer received
            pass
```

**Testing:**
```bash
python app/main.py
# Should work exactly as before
```

---

## 🔌 Phase 2: Socket Server (4-5 hours)

### 2.1 Install Dependencies

**Add to `requirements.txt`:**
```
flask==3.0.0
flask-socketio==5.3.0
python-socketio==5.10.0
flask-cors==4.0.0
```

**Install:**
```bash
pip install flask flask-socketio flask-cors
```

---

### 2.2 Create Socket Server

**File:** `app/socket_server.py`

**Structure:**
```python
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize AI service
chat_service = ChatService()

# Socket events
@socketio.on('connect')
def handle_connect():
    # Client connected
    
@socketio.on('disconnect')
def handle_disconnect():
    # Client disconnected
    
@socketio.on('join_thread')
def handle_join_thread(data):
    # Join room for thread_id
    
@socketio.on('chat_message')
def handle_chat_message(data):
    # Non-streaming response
    
@socketio.on('chat_stream')
def handle_chat_stream(data):
    # Streaming response
    
@socketio.on('toggle_tools')
def handle_toggle_tools(data):
    # Toggle tools on/off (stored in session)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

---

### 2.3 Socket Events Design

#### **Event 1: `connect`**
**Client → Server:** (automatic)
**Server → Client:** `emit('connected', {'status': 'ok'})`

#### **Event 2: `join_thread`**
**Client → Server:**
```json
{
  "thread_id": "shop-001"
}
```
**Server → Client:** 
```json
{
  "status": "joined",
  "thread_id": "shop-001"
}
```

#### **Event 3: `chat_message` (Non-streaming)**
**Client → Server:**
```json
{
  "message": "Top 5 khách hàng",
  "thread_id": "shop-001",
  "tool_enabled": true
}
```
**Server → Client:** `emit('bot_response', {...})`
```json
{
  "final_answer": "Top 5 khách hàng là...",
  "tool_calls": [...],
  "execution_metrics": {...}
}
```

#### **Event 4: `chat_stream` (Streaming)**
**Client → Server:** (same as chat_message)

**Server → Client:** Multiple emissions
```json
// Chunk
{"type": "chunk", "data": "Top"}
{"type": "chunk", "data": " 5"}
{"type": "chunk", "data": " khách"}

// Done
{
  "type": "done",
  "final_answer": "...",
  "tool_calls": [...],
  "execution_metrics": {...}
}
```

#### **Event 5: `toggle_tools`**
**Client → Server:**
```json
{
  "thread_id": "shop-001",
  "enabled": false
}
```
**Server → Client:**
```json
{
  "status": "ok",
  "tool_enabled": false
}
```

#### **Event 6: `error`**
**Server → Client:**
```json
{
  "error": "Error message",
  "details": "..."
}
```

---

### 2.4 Session Management

**Store per-thread state:**
```python
# In-memory (simple)
thread_states = {}

@socketio.on('join_thread')
def handle_join_thread(data):
    thread_id = data['thread_id']
    
    if thread_id not in thread_states:
        thread_states[thread_id] = {
            'tool_enabled': True,
            'connected_clients': 0
        }
    
    thread_states[thread_id]['connected_clients'] += 1
    join_room(thread_id)
```

**Alternative: Use Redis for multi-server:**
```python
import redis
r = redis.Redis()

# Store: r.hset(f"thread:{thread_id}", "tool_enabled", "true")
# Get: r.hget(f"thread:{thread_id}", "tool_enabled")
```

---

### 2.5 Error Handling

**Pattern:**
```python
@socketio.on('chat_message')
def handle_chat_message(data):
    try:
        # Validate input
        if not data.get('message'):
            emit('error', {'error': 'Empty message'})
            return
            
        # Process
        response = chat_service.process_message(...)
        
        # Send response
        emit('bot_response', response)
        
    except Exception as e:
        emit('error', {
            'error': str(e),
            'thread_id': data.get('thread_id')
        })
```

---

## 🧪 Phase 3: Testing (2-3 hours)

### 3.1 Unit Tests

**File:** `tests/test_service.py`

```python
from app.service import ChatService

def test_process_message():
    service = ChatService()
    response = service.process_message(
        "test message",
        "test-thread",
        tool_enabled=False
    )
    assert "final_answer" in response
    
def test_process_message_stream():
    service = ChatService()
    events = list(service.process_message_stream(...))
    assert events[-1]["type"] == "done"
```

---

### 3.2 Integration Test

**Start server:**
```bash
python app/socket_server.py
# Server running on http://localhost:5000
```

**Test with browser console:**
```javascript
// Load Socket.IO client
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

// Connect
const socket = io('http://localhost:5000');

// Listen for connection
socket.on('connect', () => {
  console.log('Connected!');
});

// Join thread
socket.emit('join_thread', {thread_id: 'test-001'});

// Send message (non-streaming)
socket.emit('chat_message', {
  message: 'Top 5 khách hàng',
  thread_id: 'test-001',
  tool_enabled: true
});

// Listen for response
socket.on('bot_response', (data) => {
  console.log('Bot:', data.final_answer);
});

// Listen for errors
socket.on('error', (data) => {
  console.error('Error:', data);
});
```

---

### 3.3 Test Scenarios

| Scenario | Expected Result |
|----------|-----------------|
| Connect to server | Receive 'connected' event |
| Join thread | Join room successfully |
| Send valid message | Receive bot_response |
| Send empty message | Receive error |
| Send with tools off | Bot responds without tools |
| Send stream request | Receive multiple chunks |
| Disconnect | Clean up resources |
| Multiple clients same thread | Both receive responses |

---

## 🚀 Phase 4: Streaming Implementation (2-3 hours)

### 4.1 Server-Side Streaming

**Challenge:** Flask-SocketIO với threading

**Solution:**
```python
@socketio.on('chat_stream')
def handle_chat_stream(data):
    thread_id = data['thread_id']
    
    try:
        for event in chat_service.process_message_stream(
            data['message'],
            thread_id,
            data.get('tool_enabled', True)
        ):
            # Emit to specific room
            emit('bot_chunk', event, room=thread_id)
            
            # Small delay to prevent flooding
            socketio.sleep(0.01)
            
    except Exception as e:
        emit('error', {'error': str(e)}, room=thread_id)
```

---

### 4.2 Client-Side Streaming

```javascript
// Request stream
socket.emit('chat_stream', {
  message: 'Top 5 khách hàng',
  thread_id: 'test-001',
  tool_enabled: true
});

// Listen for chunks
let fullResponse = '';
socket.on('bot_chunk', (event) => {
  if (event.type === 'chunk') {
    fullResponse += event.data;
    console.log(event.data);  // Display incrementally
  } else if (event.type === 'done') {
    console.log('Complete:', event.final_answer);
  }
});
```

---

## 🔒 Phase 5: Production Readiness (2-3 hours)

### 5.1 Configuration

**File:** `app/config.py`

```python
# Socket server configuration
SOCKET_HOST = os.getenv("SOCKET_HOST", "0.0.0.0")
SOCKET_PORT = int(os.getenv("SOCKET_PORT", "5000"))
SOCKET_DEBUG = os.getenv("SOCKET_DEBUG", "False").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
```

**File:** `.env.example`

```env
# Socket Server
SOCKET_HOST=0.0.0.0
SOCKET_PORT=5000
SOCKET_DEBUG=False
CORS_ORIGINS=*
```

---

### 5.2 Logging

**Add to `socket_server.py`:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

@socketio.on('chat_message')
def handle_chat_message(data):
    logger.info(f"Received message from thread {data.get('thread_id')}")
    # ... process ...
    logger.info(f"Sent response to thread {data.get('thread_id')}")
```

---

### 5.3 Rate Limiting

**Install:**
```bash
pip install Flask-Limiter
```

**Add:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

@limiter.limit("20 per minute")
@socketio.on('chat_message')
def handle_chat_message(data):
    # ... process ...
```

---

### 5.4 Health Check

```python
@app.route('/health')
def health_check():
    return {
        'status': 'ok',
        'service': 'shop-chatbot-socket',
        'langfuse_enabled': is_langfuse_enabled()
    }

@app.route('/stats')
def stats():
    return {
        'active_threads': len(thread_states),
        'total_clients': sum(s['connected_clients'] for s in thread_states.values())
    }
```

---

## 📦 Phase 6: Deployment (Optional)

### 6.1 Docker

**File:** `Dockerfile.socket`

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY .env .

EXPOSE 5000

CMD ["python", "app/socket_server.py"]
```

**Build & Run:**
```bash
docker build -f Dockerfile.socket -t shop-chatbot-socket .
docker run -p 5000:5000 --env-file .env shop-chatbot-socket
```

---

### 6.2 Docker Compose Integration

**Add to `docker-compose.yml`:**
```yaml
services:
  socket-server:
    build:
      context: .
      dockerfile: Dockerfile.socket
    ports:
      - "5000:5000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - LANGFUSE_HOST=${LANGFUSE_HOST}
    depends_on:
      - redis
      - postgres
```

---

### 6.3 Production Server

**Use Gunicorn + eventlet:**

**Install:**
```bash
pip install gunicorn eventlet
```

**Run:**
```bash
gunicorn --worker-class eventlet -w 1 \
  --bind 0.0.0.0:5000 \
  app.socket_server:app
```

**Note:** Use 1 worker with eventlet for Socket.IO

---

## 📊 File Structure After Implementation

```
shop-langgraph/
├── app/
│   ├── main.py              (existing - CLI using service)
│   ├── service.py           (NEW - AI service)
│   ├── socket_server.py     (NEW - Socket server)
│   ├── config.py            (updated - socket config)
│   ├── graph/               (existing - no change)
│   ├── tools/               (existing - no change)
│   ├── db/                  (existing - no change)
│   └── observability/       (existing - no change)
│
├── tests/
│   ├── test_service.py      (NEW)
│   └── test_socket.py       (NEW)
│
├── client-examples/         (NEW - optional)
│   ├── test.html           (Browser test client)
│   └── test.js             (Node.js test client)
│
├── requirements.txt         (updated - add Flask-SocketIO)
├── .env.example             (updated - socket config)
└── Dockerfile.socket        (NEW - optional)
```

---

## ✅ Acceptance Criteria

**Phase 1 - Service:**
- [ ] `ChatService` class created
- [ ] `process_message()` works (non-streaming)
- [ ] `process_message_stream()` works (streaming)
- [ ] CLI still works using service

**Phase 2 - Socket:**
- [ ] Socket server starts on port 5000
- [ ] Clients can connect
- [ ] `chat_message` event works
- [ ] Multiple clients can connect

**Phase 3 - Testing:**
- [ ] Unit tests pass
- [ ] Browser test client works
- [ ] Errors are handled gracefully

**Phase 4 - Streaming:**
- [ ] `chat_stream` event works
- [ ] Chunks arrive in order
- [ ] No dropped messages

**Phase 5 - Production:**
- [ ] Logging added
- [ ] Health check endpoint
- [ ] Rate limiting configured
- [ ] Environment variables documented

---

## 🚧 Known Challenges & Solutions

### Challenge 1: Thread Safety
**Issue:** Multiple clients accessing same thread_id

**Solution:** Redis checkpointer already handles this (LangGraph built-in)

### Challenge 2: Long-Running Requests
**Issue:** LLM call takes 5-10 seconds

**Solution:** Use Socket.IO rooms, non-blocking with eventlet

### Challenge 3: Client Disconnects Mid-Stream
**Issue:** Client disconnects while bot is processing

**Solution:** Catch disconnect event, cancel processing

```python
@socketio.on('disconnect')
def handle_disconnect():
    # Mark this client's requests as cancelled
    # Stop emitting to this client's room
```

### Challenge 4: Memory Leaks
**Issue:** `thread_states` dict grows indefinitely

**Solution:** Implement TTL cleanup

```python
from datetime import datetime, timedelta

def cleanup_old_threads():
    now = datetime.now()
    for tid, state in list(thread_states.items()):
        if now - state['last_activity'] > timedelta(hours=24):
            del thread_states[tid]
```

---

## 📈 Performance Considerations

**Expected Load:**
- 10-50 concurrent users
- 2-3 messages per minute per user
- ~200ms socket latency + 2-5s LLM latency

**Bottlenecks:**
1. LLM API rate limits (Gemini)
2. Database connections (PostgreSQL)
3. Redis checkpointer I/O

**Optimizations:**
- Connection pooling (already in SQLAlchemy)
- Redis pipelining (if needed)
- Caching frequent queries (future)

---

## 🎓 Learning Resources

**Flask-SocketIO:**
- Docs: https://flask-socketio.readthedocs.io/
- Examples: https://github.com/miguelgrinberg/Flask-SocketIO

**Socket.IO Client (JavaScript):**
- Docs: https://socket.io/docs/v4/client-api/
- CDN: https://cdn.socket.io/4.5.4/socket.io.min.js

**Testing:**
- Python client: `python-socketio`
- Browser: DevTools console
- Tool: Postman (WebSocket support)

---

## 📋 Implementation Checklist

**Preparation:**
- [ ] Review current `main.py` to understand logic
- [ ] Install Flask-SocketIO dependencies
- [ ] Set up test environment

**Phase 1 (Day 1):**
- [ ] Create `app/service.py`
- [ ] Implement `ChatService` class
- [ ] Extract `process_message()` method
- [ ] Test service independently
- [ ] Update CLI to use service

**Phase 2 (Day 2):**
- [ ] Create `app/socket_server.py`
- [ ] Implement basic socket events (connect, disconnect)
- [ ] Implement `chat_message` event
- [ ] Test with browser console

**Phase 3 (Day 3):**
- [ ] Add `join_thread` event
- [ ] Add session management
- [ ] Write unit tests
- [ ] Write integration tests

**Phase 4 (Day 4):**
- [ ] Implement `chat_stream` event
- [ ] Test streaming with browser
- [ ] Handle edge cases (disconnects, errors)

**Phase 5 (Day 5):**
- [ ] Add logging
- [ ] Add health check endpoint
- [ ] Add rate limiting
- [ ] Update documentation

**Optional:**
- [ ] Create Docker setup
- [ ] Deploy to test environment
- [ ] Create example client app

---

## 🎯 Success Metrics

**Functional:**
- ✅ Socket server runs without errors
- ✅ Clients can send messages and receive responses
- ✅ Streaming works smoothly
- ✅ Multiple concurrent users supported

**Performance:**
- ✅ Socket latency < 200ms
- ✅ End-to-end response time < 5 seconds
- ✅ Supports 50+ concurrent connections

**Quality:**
- ✅ Error rate < 1%
- ✅ No memory leaks after 24 hours
- ✅ Langfuse tracking still works
- ✅ All existing features maintained

---

## 🔄 Next Steps After Completion

1. **Build Frontend Client** (separate project)
   - React/Vue web app
   - Or React Native mobile app
   
2. **Add Authentication** (JWT, OAuth)
   - Socket.IO middleware for auth
   - User-specific thread IDs

3. **Enhance Features**
   - Typing indicators
   - Read receipts
   - Message history API
   - File uploads (images, documents)

4. **Monitoring & Analytics**
   - Socket.IO admin UI
   - Grafana dashboards
   - Alert on high error rates

---

**Plan created by:** AI Assistant  
**For:** Shop Customer Service Chatbot  
**Ready to implement!** 🚀
