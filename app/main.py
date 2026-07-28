from langchain_core.messages import (
    HumanMessage, AIMessage, ToolMessage,
)

from app.graph.workflow import (
    graph,
)

from app.logging.trace_logger import (
    save_transcript,
)


def chat():

    print(
        "=============================="
    )

    print(
        "SHOP CUSTOMER SERVICE CHATBOT"
    )

    print(
        "Powered by Gemini + LangGraph"
    )

    print(
        "Nhập 'exit' để thoát."
    )

    print(
        "=============================="
    )

    messages = []

    while True:
        user_input = input(
            "\nUser: "
        )

        if user_input.lower() == "exit":
            print(
                "Đã thoát chatbot."
            )
            break

        previous_message_count = len(
            messages
        )
        user_message = HumanMessage(
            content=user_input
        )

        messages.append(
            user_message
        )

#chạy langgraph
        result = graph.invoke(
            {
                "messages": messages
            }
        )

        messages = result[
            "messages"
        ]

        #lấy các message mới từ lần gọi trước
        new_messages = messages[
            previous_message_count:
        ]

        final_message = messages[-1]

        content = final_message.content

        if isinstance(content, str):
            final_answer = content
        elif isinstance(content, list):
                final_answer = "\n".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                )
        else:
                final_answer = str(content)

#lấy tool calls
        tool_calls = []
        for message in new_messages:
            # Gemini gọi tool
            if isinstance(
                message,
                AIMessage,
            ):
                if message.tool_calls:
                    for tool_call in (
                        message.tool_calls
                    ):
                        tool_calls.append(
                            {
                                "tool_name":
                                    tool_call[
                                        "name"
                                    ],

                                "arguments":
                                    tool_call[
                                        "args"
                                    ],

                                "tool_call_id":
                                    tool_call[
                                        "id"
                                    ],
                            }
                        )
            # Tool trả kết quả
            elif isinstance(
                message,
                ToolMessage,
            ):
                for tool_call in tool_calls:
                    if (
                        tool_call[
                            "tool_call_id"
                        ]
                        == message.tool_call_id
                    ):
                        tool_call[
                            "result"
                        ] = message.content

# lưu transcript
        save_transcript(
                    user_input=user_input,

                    tool_calls=tool_calls,

                    final_answer=final_answer,
                )

        
        print(
            "\nBot:",
            final_answer,
        )

if __name__ == "__main__":
    chat()