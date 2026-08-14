from langchain_core.messages import AIMessage, AIMessageChunk

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
)

from app.tools import ALL_TOOLS


llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0,
    streaming=True,
)


llm_with_tools = llm.bind_tools(
    ALL_TOOLS
)


SYSTEM_PROMPT_NO_TOOLS = """Bạn là chatbot chăm sóc khách hàng cho Shop.

Hiện tại bạn KHÔNG có quyền truy cập vào các công cụ (tools) để truy vấn database.

NẾU người dùng hỏi về:
- Thông tin khách hàng cụ thể
- Đơn hàng  
- Doanh thu
- Sản phẩm

HÃY trả lời rằng: "Xin lỗi, tôi không thể truy vấn dữ liệu hiện tại vì chức năng công cụ (Tools) đang tắt. Vui lòng bật công cụ (Tools toggle) để tôi có thể giúp bạn tra cứu thông tin từ database."

Chỉ trả lời các câu hỏi chung chung hoặc hướng dẫn sử dụng.
Trả lời bằng tiếng Việt.
"""

SYSTEM_PROMPT = """Bạn là chatbot chăm sóc khách hàng cho Shop.

Bạn có quyền sử dụng các tool được cung cấp
để truy vấn dữ liệu thật từ database.

NGUYÊN TẮC BẮT BUỘC:

1. Các câu hỏi về khách hàng,
   sản phẩm, đơn hàng hoặc doanh thu
   phải sử dụng tool để lấy dữ liệu thật.

2. Không được tự bịa số liệu.

3. Nếu tool trả về dữ liệu rỗng,
   phải nói rõ rằng không tìm thấy dữ liệu.

4. Không được tự suy diễn dữ liệu
   không có trong database.

5. Nếu câu hỏi ngoài phạm vi các tool,
   hãy từ chối lịch sự.

6. Khi cần nhiều tool,
   hãy gọi các tool cần thiết theo thứ tự phù hợp.

7. Khi nhận được kết quả từ tool,
   hãy sử dụng dữ liệu đó để trả lời người dùng.

8. Không được tự tạo ra ID,
   giá tiền, doanh thu hoặc thông tin đơn hàng.

9. Nếu một câu hỏi yêu cầu thông tin
   mà database không cung cấp,
   hãy nói rõ rằng không có dữ liệu phù hợp.

10. Trả lời bằng tiếng Việt.
"""


def call_llm(state, config):
    """LLM node that invokes the model (streaming handled by LangGraph)."""
    messages = state["messages"]
    
    # Check if tools are enabled from config
    configurable = config.get("configurable", {})
    tool_enabled = configurable.get("tool_enabled", True)
    
    # Use different system prompt based on tool_enabled
    system_prompt = SYSTEM_PROMPT if tool_enabled else SYSTEM_PROMPT_NO_TOOLS
    
    # Use LLM with or without tools based on tool_enabled
    llm_to_use = llm_with_tools if tool_enabled else llm

    prompt_messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *messages,
    ]

    # Get callbacks from config (Langfuse handler passed from main.py)
    callbacks = config.get("callbacks", [])
    
    # Simply invoke - LangGraph handles streaming via stream_mode="messages"
    # Pass callbacks to capture LLM call in Langfuse
    response = llm_to_use.invoke(prompt_messages, config={"callbacks": callbacks})

    # Ensure response is AIMessage, not AIMessageChunk
    if isinstance(response, AIMessageChunk):
        response = AIMessage(
            content=response.content,
            additional_kwargs=response.additional_kwargs,
            response_metadata=response.response_metadata,
            tool_calls=response.tool_calls if hasattr(response, 'tool_calls') else [],
            invalid_tool_calls=response.invalid_tool_calls if hasattr(response, 'invalid_tool_calls') else [],
        )

    return {
        "messages": [response]
    }