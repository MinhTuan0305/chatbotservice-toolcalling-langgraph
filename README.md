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
GEMINI_API_KEY=your_gemini_api_key

DATABASE_URL=postgresql://username:password@localhost:5432/shop_db

REDIS_URL=redis://localhost:6379/0
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

# Streaming Output

The chatbot now streams the assistant response to the terminal token-by-token while the model is generating.

- The final state is still saved after the run completes.
- Transcript logging remains unchanged.
- Streaming is shown only in the CLI output, not in Redis.

---

## Transcript for 8 use cases:
```bash
{
    "id": "70a7d3e7-ea90-4273-9998-b9ad8f79f0a3",
    "timestamp": "2026-07-28T13:45:51.814407",
    "user": {
      "input": "Cho tôi xem các sản phẩm laptop giá dưới 30 triệu."
    },
    "tool_calls": [
      {
        "tool_name": "search_products",
        "arguments": {
          "category": "laptop",
          "max_price": 30000000
        },
        "tool_call_id": "35c8d519-5680-48e2-be27-4c995484f135",
        "result": "[{'id': 4, 'name': 'MacBook Air M3', 'category': 'Laptop', 'price': Decimal('28000000.00')}, {'id': 6, 'name': 'Asus ZenBook', 'category': 'Laptop', 'price': Decimal('18000000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Đây là các sản phẩm laptop có giá dưới 30 triệu:\n* MacBook Air M3, giá 28.000.000 VNĐ\n* Asus ZenBook, giá 18.000.000 VNĐ"
    }
  },
  {
    "id": "8982b84a-1459-41ad-aae3-e3c954d2be4d",
    "timestamp": "2026-07-28T13:46:45.951034",
    "user": {
      "input": "Khách hàng Nguyễn Văn An có những đơn hàng nào?"
    },
    "tool_calls": [
      {
        "tool_name": "get_customer_by_name",
        "arguments": {
          "name": "Nguyễn Văn An"
        },
        "tool_call_id": "8f69f79e-02b9-47fd-b720-bae4c38c0a0b",
        "result": "[{'id': 1, 'name': 'Nguyễn Văn An', 'city': 'Hà Nội', 'created_at': datetime.date(2024, 1, 15)}]"
      },
      {
        "tool_name": "get_customer_orders",
        "arguments": {
          "customer_id": 1
        },
        "tool_call_id": "4f6bd3a0-601c-4b22-8255-c29b0a1de7d3",
        "result": "[{'order_id': 11, 'customer_id': 1, 'order_date': datetime.date(2024, 7, 22), 'status': 'completed', 'shipped_date': datetime.date(2024, 7, 24), 'total_amount': Decimal('30000000.00')}, {'order_id': 2, 'customer_id': 1, 'order_date': datetime.date(2024, 7, 2), 'status': 'completed', 'shipped_date': datetime.date(2024, 7, 4), 'total_amount': Decimal('2050000.00')}, {'order_id': 1, 'customer_id': 1, 'order_date': datetime.date(2024, 6, 10), 'status': 'completed', 'shipped_date': datetime.date(2024, 6, 12), 'total_amount': Decimal('26500000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Khách hàng Nguyễn Văn An có các đơn hàng sau:\n* Đơn hàng ID: 11, ngày đặt: 22/07/2024, trạng thái: đã hoàn thành, ngày giao: 24/07/2024, tổng tiền: 30.000.000 VNĐ\n* Đơn hàng ID: 2, ngày đặt: 02/07/2024, trạng thái: đã hoàn thành, ngày giao: 04/07/2024, tổng tiền: 2.050.000 VNĐ\n* Đơn hàng ID: 1, ngày đặt: 10/06/2024, trạng thái: đã hoàn thành, ngày giao: 12/06/2024, tổng tiền: 26.500.000 VNĐ"
    }
  },
  {
    "id": "a62e84f7-8013-4db7-8a8a-21ffa3de7616",
    "timestamp": "2026-07-28T14:04:22.860072",
    "user": {
      "input": "Đơn hàng #4 gồm những sản phẩm gì, đã giao chưa?"
    },
    "tool_calls": [
      {
        "tool_name": "get_order_detail",
        "arguments": {
          "order_id": 4
        },
        "tool_call_id": "6d06968e-b742-432f-8241-6390112cad51",
        "result": "[{'order_id': 4, 'customer_id': 3, 'order_date': datetime.date(2024, 6, 20), 'status': 'pending', 'shipped_date': None, 'order_item_id': 6, 'product_id': 3, 'product_name': 'Xiaomi 14', 'qty': 1, 'unit_price': Decimal('15000000.00'), 'item_total': Decimal('15000000.00')}, {'order_id': 4, 'customer_id': 3, 'order_date': datetime.date(2024, 6, 20), 'status': 'pending', 'shipped_date': None, 'order_item_id': 7, 'product_id': 11, 'product_name': 'Chuột không dây', 'qty': 1, 'unit_price': Decimal('350000.00'), 'item_total': Decimal('350000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Đơn hàng #4 bao gồm các sản phẩm sau:\n- 1 sản phẩm Xiaomi 14 với giá 15,000,000.00 VNĐ\n- 1 sản phẩm Chuột không dây với giá 350,000.00 VNĐ\n\nĐơn hàng này hiện đang ở trạng thái \"pending\" và chưa được giao."
    }
  },
  {
    "id": "f7a4bb73-97a0-44b7-8c8a-84480a302bdf",
    "timestamp": "2026-07-28T14:05:27.564317",
    "user": {
      "input": "Danh mục nào đang bán chạy nhất về doanh thu?"
    },
    "tool_calls": [
      {
        "tool_name": "get_revenue_by_category",
        "arguments": {},
        "tool_call_id": "bd6819a7-d419-49d4-98cb-affb06eaa6b1",
        "result": "[{'category': 'Điện thoại', 'revenue': Decimal('74000000.00')}, {'category': 'Laptop', 'revenue': Decimal('60000000.00')}, {'category': 'Phụ kiện', 'revenue': Decimal('19400000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Dựa trên doanh thu từ các đơn hàng đã hoàn thành, danh mục \"Điện thoại\" đang bán chạy nhất với doanh thu 74,000,000.00 VNĐ."
    }
  },
  {
    "id": "9b70742f-2872-4f70-a104-64d46bfddb57",
    "timestamp": "2026-07-28T14:10:03.876810",
    "user": {
      "input": "Top 3 khách hàng chi tiêu nhiều nhất là ai?"
    },
    "tool_calls": [
      {
        "tool_name": "get_top_customers",
        "arguments": {
          "limit": 3
        },
        "tool_call_id": "acb630e3-8b99-447a-b196-9241630dad7e",
        "result": "[{'customer_id': 1, 'name': 'Nguyễn Văn An', 'city': 'Hà Nội', 'total_spent': Decimal('58550000.00')}, {'customer_id': 4, 'name': 'Phạm Thị Dung', 'city': 'Hà Nội', 'total_spent': Decimal('33200000.00')}, {'customer_id': 2, 'name': 'Trần Thị Bình', 'city': 'Hồ Chí Minh', 'total_spent': Decimal('28000000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Top 3 khách hàng chi tiêu nhiều nhất là:\n1. Nguyễn Văn An (ID: 1) từ Hà Nội, đã chi tiêu 58,550,000.00 VNĐ.\n2. Phạm Thị Dung (ID: 4) từ Hà Nội, đã chi tiêu 33,200,000.00 VNĐ.\n3. Trần Thị Bình (ID: 2) từ Hồ Chí Minh, đã chi tiêu 28,000,000.00 VNĐ."
    }
  },
  {
    "id": "f43d839b-4f43-4f59-b412-00c11c6d750f",
    "timestamp": "2026-07-28T14:11:14.569348",
    "user": {
      "input": "Khách Trần Thị Bình đã mua tổng cộng bao nhiêu tiền, tính luôn cả đơn đã huỷ không?"
    },
    "tool_calls": [
      {
        "tool_name": "get_customer_by_name",
        "arguments": {
          "name": "Trần Thị Bình"
        },
        "tool_call_id": "78aacc0c-2e06-42b2-aa17-6dd8b6293516",
        "result": "[{'id': 2, 'name': 'Trần Thị Bình', 'city': 'Hồ Chí Minh', 'created_at': datetime.date(2024, 2, 3)}]"
      },
      {
        "tool_name": "get_customer_orders",
        "arguments": {
          "customer_id": 2
        },
        "tool_call_id": "52898444-5779-42d6-929d-246df3d687fc",
        "result": "[{'order_id': 6, 'customer_id': 2, 'order_date': datetime.date(2024, 7, 10), 'status': 'cancelled', 'shipped_date': None, 'total_amount': Decimal('20000000.00')}, {'order_id': 3, 'customer_id': 2, 'order_date': datetime.date(2024, 6, 15), 'status': 'completed', 'shipped_date': datetime.date(2024, 6, 17), 'total_amount': Decimal('28000000.00')}]"
      }
    ],
    "assistant": {
      "final_answer": "Khách hàng Trần Thị Bình đã mua tổng cộng 48,000,000.00 VNĐ, bao gồm cả đơn hàng đã hủy. Cụ thể:\n*   Đơn hàng #6 (đã hủy): 20,000,000.00 VNĐ\n*   Đơn hàng #3 (đã hoàn thành): 28,000,000.00 VNĐ"
    }
  },
  {
    "id": "2e0573a2-6ab3-433c-901f-d8c8aaf5c7db",
    "timestamp": "2026-07-28T14:12:08.457465",
    "user": {
      "input": "Khách hàng Lý Văn Không Tồn Tại có đơn hàng gì?"
    },
    "tool_calls": [
      {
        "tool_name": "get_customer_by_name",
        "arguments": {
          "name": "Lý Văn Không Tồn Tại"
        },
        "tool_call_id": "ad19a226-6d40-4a4f-b7a8-59ce969a9fd5",
        "result": []
      }
    ],
    "assistant": {
      "final_answer": "Tôi không tìm thấy khách hàng nào có tên \"Lý Văn Không Tồn Tại\" trong hệ thống. Vui lòng kiểm tra lại tên khách hàng."
    }
  },
  {
    "id": "342b19d6-6673-4467-8bf8-784fa37f8ea1",
    "timestamp": "2026-07-28T14:17:35.278500",
    "user": {
      "input": "Cho tôi mã giảm giá 50%."
    },
    "tool_calls": [],
    "assistant": {
      "final_answer": [
        {
          "type": "text",
          "text": "Tôi xin lỗi, tôi không có chức năng tạo hoặc cung cấp mã giảm giá.",
          "extras": {
            "signature": "CtcCARFNMg8Lli0lRIqIeuez15GMrKZr6V29nJr91bbPI0Fv1X+JWyjpGrBL80kCAOl8b9N1GfgwqPDkclios5tN8Np9TqNfiDvyvKHJvR96UYKao2WOvvdIxokCo3Vls+wV7bnEmTrCmWayzg1GkY39FaevGZd6is1CaKZ4BSIkZyoYnixWnFrXxF+BKHKwZ2mo6rDjDg0ujrycOu20Z4oUtv8DmmZMLoRyyBlWyX7qfDsQtv/zOnrWiRnPlkEcyzV+p7TtP4a/iDe3leVIyEBKMZsSCPYHQEVhRcG0WzZe2VDzxNCfWRtb6svPld3xNph9yUE/V2MUqF+0iVsC0X4+Flyr9qYVlmCdtG4yK0ZkYX+q7K/wiFhU8Ptq/c68lsVJnXzPg299uMm4ciIQB9fXqtJs7YTHeB0OJVdnYCKKXJyMWMOPF7M29HdodNp0miAVJ/N+osRl0w=="
          }
        }
      ]
    }
  },
```
---

# Tool Switch
The chatbot supports a runtime **Tool Switch** that enables or disables tool calling without modifying the graph.

Commands:

```text
/tool on
/tool off
```

When Tool Calling is disabled:

- The workflow skips the `ToolNode`.
- No database queries are executed.
- The conversation continues using the LLM only.

The switch is controlled through LangGraph's `configurable` runtime configuration.

# Note 
- Redis stores LangGraph conversation checkpoints.
- Conversation history is automatically restored based on the `thread_id`.