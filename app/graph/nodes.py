from functools import lru_cache

from langchain_core.messages import AIMessage, AIMessageChunk, trim_messages

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_MODEL,
    MAX_CONTEXT_TOKENS,
)

from app.tools import ALL_TOOLS


class ProviderConfigError(ValueError):
    """Raised when the requested LLM provider/API key combination is invalid."""


@lru_cache(maxsize=32)
def _build_llm(provider: str, model: str, api_key: str, bind_tools: bool):
    """
    Build (and cache) a chat model for one (provider, model, api_key) combo.

    Cached because api_key is user-suppliable per thread (see
    app/socket_server.py `set_provider`) — without caching, every single
    message would re-construct the provider's HTTP client from scratch.
    """
    if provider == "openai":
        model_instance = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0,
            streaming=True,
        )
    else:
        model_instance = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0,
            streaming=True,
        )

    if bind_tools:
        model_instance = model_instance.bind_tools(ALL_TOOLS)

    return model_instance


def get_llm(provider: str | None, api_key: str | None, tool_enabled: bool):
    """
    Resolve the chat model to use for one request.

    - "gemini" (default): uses the client-supplied api_key if given, else
      falls back to the server's GEMINI_API_KEY from .env.
    - "openai": always requires a client-supplied api_key — there is no
      server-side default, by design (see app/config.py).
    """
    provider = (provider or "gemini").strip().lower()

    if provider == "openai":
        if not api_key:
            raise ProviderConfigError(
                "OpenAI yêu cầu API key riêng — vui lòng nhập API key trước khi chuyển sang OpenAI."
            )
        model = OPENAI_MODEL
    elif provider == "gemini":
        api_key = api_key or GEMINI_API_KEY
        model = GEMINI_MODEL
    else:
        raise ProviderConfigError(f"Provider không được hỗ trợ: {provider}")

    return _build_llm(provider, model, api_key, tool_enabled)


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
    provider = configurable.get("provider")
    api_key = configurable.get("api_key")

    # Use different system prompt based on tool_enabled
    system_prompt = SYSTEM_PROMPT if tool_enabled else SYSTEM_PROMPT_NO_TOOLS

    # Resolve LLM for the requested provider (defaults to Gemini + server key)
    try:
        llm_to_use = get_llm(provider, api_key, tool_enabled)
    except ProviderConfigError as e:
        return {"messages": [AIMessage(content=str(e))]}

    # Trim messages to prevent context window overflow
    # Keep recent messages within token limit
    trimmed_messages = trim_messages(
        messages,
        max_tokens=MAX_CONTEXT_TOKENS,
        strategy="last",  # Keep most recent messages
        token_counter=len,  # Simple character-based counting
        allow_partial=False,
    )

    prompt_messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *trimmed_messages,
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