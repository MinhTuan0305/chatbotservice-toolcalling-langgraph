# Socket Server Test Clients

Test clients for Shop Customer Service Chatbot Socket Server.

## 📁 Files

- **`test.html`** - Browser-based test client (recommended for quick testing)

## 🚀 Quick Start

### 1. Start the Socket Server

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start Redis (required)
docker compose up -d redis

# Start socket server
python -m app.socket_server
```

Server will start on `http://localhost:5000`

### 2. Open Test Client

Open `test.html` in your browser:

```bash
# Windows
start test.html

# Or just double-click test.html
```

### 3. Test the Connection

1. **Enter Thread ID** (e.g., `test-001`)
2. **Click "Join Thread"**
3. **Send a message** (e.g., "Có bao nhiêu đơn hàng đang pending?")
4. **See the response** stream in real-time

## 🧪 Test Scenarios

### Basic Chat
```
Thread ID: test-001
Message: Có bao nhiêu đơn hàng đang pending?
Expected: Bot responds with count of pending orders
```

### Toggle Tools
```
1. Uncheck "Tools Enabled"
2. Message: Top 5 khách hàng
3. Expected: Bot responds without calling any tools
```

### Streaming vs Non-Streaming
```
1. Uncheck "Streaming"
2. Send message
3. Expected: Full response appears at once (no streaming)
```

### Multiple Clients
```
1. Open test.html in multiple browser tabs
2. Join same thread ID in all tabs
3. Send message in one tab
4. Expected: All tabs receive the response
```

## 🔧 Socket Events

### Client → Server

| Event | Data | Description |
|-------|------|-------------|
| `join_thread` | `{thread_id}` | Join a conversation thread |
| `leave_thread` | `{thread_id}` | Leave a thread |
| `chat_message` | `{message, thread_id, tool_enabled}` | Send message (non-streaming) |
| `chat_stream` | `{message, thread_id, tool_enabled}` | Send message (streaming) |
| `toggle_tools` | `{thread_id, enabled}` | Enable/disable tools |

### Server → Client

| Event | Data | Description |
|-------|------|-------------|
| `connected` | `{status, langfuse_enabled}` | Connection established |
| `thread_joined` | `{status, thread_id, tool_enabled}` | Joined thread |
| `thread_left` | `{status, thread_id}` | Left thread |
| `bot_response` | `{final_answer, tool_calls, thread_id}` | Non-streaming response |
| `bot_chunk` | `{type, data}` or `{type, final_answer, tool_calls}` | Streaming chunk/done |
| `tools_toggled` | `{status, thread_id, tool_enabled}` | Tools toggled |
| `error` | `{error, thread_id?}` | Error occurred |

## 📊 Test Checklist

- [ ] Connect to server
- [ ] Join thread
- [ ] Send message (streaming)
- [ ] Send message (non-streaming)
- [ ] Toggle tools off
- [ ] Toggle tools on
- [ ] Leave thread
- [ ] Multiple clients same thread
- [ ] Error handling (empty message, invalid thread)

## 🔗 Useful Links

- Socket.IO Client Docs: https://socket.io/docs/v4/client-api/
- Server URL: http://localhost:5000
- Health Check: http://localhost:5000/health
- Stats: http://localhost:5000/stats
