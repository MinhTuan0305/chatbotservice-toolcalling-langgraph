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
)


llm_with_tools = llm.bind_tools(
    ALL_TOOLS
)


SYSTEM_PROMPT = """
Bạn là chatbot chăm sóc khách hàng cho Shop.

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


def call_llm(state):

    messages = state["messages"]

    response = llm_with_tools.invoke(
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *messages,
        ]
    )

    return {
        "messages": [
            response
        ]
    }