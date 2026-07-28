# Shop Customer Service Chatbot

Using:

- Python
- LangGraph
- Gemini API
- Tool Calling
- PostgreSQL
- SQLAlchemy

---

## Architecture

User
↓
Gemini
↓
Tool Calling
↓
LangGraph ToolNode
↓
Database
↓
Tool Result
↓
Gemini
↓
Final Answer

---

## Tools

1. search_products
2. get_customer_by_name
3. get_customer_orders
4. get_order_detail
5. get_revenue_by_category
6. get_top_customers

---

## Installation

Create virtual environment:

```bash
python -m venv .venv
```

## Activate:

```bash
.venv\Scripts\activate
``` 

## Install dependencies:
```bash
pip install -r requirements.txt
```

## Run:
```bash
python -m app.main
```

## Test: 
8 test cases are documented in:
logs/transcripts.json