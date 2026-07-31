# Shop Customer Service Chatbot with LangGraph

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-1.x-green)
![Gemini](https://img.shields.io/badge/Google-Gemini-orange)
![Redis](https://img.shields.io/badge/Redis-Memory-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-blue)

Using:

- Python
- LangGraph
- Gemini API
- Tool Calling
- PostgreSQL
- SQLAlchemy

---

## Architecture

```text
                 User
                   │
                   ▼
             Gemini (LLM)
                   │
                   ▼
              LangGraph
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   Tool Calling          Redis Checkpointer
        │                     │
        ▼                     │
     ToolNode                 │
        │                     │
        ▼                     │
   PostgreSQL Database        │
        │                     │
        └──────────┬──────────┘
                   ▼
             Final Response
```


# Project Structure

```text
app/
├── db/
│   └── redis.py
├── graph/
│   ├── nodes.py
│   ├── state.py
│   └── workflow.py
├── tools/
├── logging/
├── config.py
└── main.py
```
---

## Tools

1. search_products
2. get_customer_by_name
3. get_customer_orders
4. get_order_detail
5. get_revenue_by_category
6. get_top_customers

---

# Test

Several test cases are documented in:

```text
logs/transcripts.json
```

---

# Installation

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd shop-langgraph
```

---

## 2. Create a virtual environment

```bash
python -m venv .venv
```

---

## 3. Activate the virtual environment

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

---

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 5. Configure environment variables

Create a `.env` file in the project root.

Example:

```env
GOOGLE_API_KEY=your_gemini_api_key

DATABASE_URL=postgresql://username:password@localhost:5432/shop_db
```

---

## 6. Start Redis

The chatbot uses **Redis** as the LangGraph Checkpointer to persist conversation state.

Run Redis using Docker:

```bash
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:8
```

If the Redis container already exists:

```bash
docker start redis
```

---

## 7. Run the chatbot

```bash
python -m app.main
```

---

# Conversation Memory

Conversation state is persisted using **LangGraph Redis Checkpointer**.

Each conversation is identified by a unique `thread_id`.

Example:

```python
graph.invoke(
    {"messages": [user_message]},
    config={
        "configurable": {
            "thread_id": THEAD_ID
        }
    }
)
```

Using different `thread_id` values creates independent conversations.

---

# Note 
- Redis stores LangGraph conversation checkpoints.
- Conversation history is automatically restored based on the `thread_id`.