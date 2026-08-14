from langchain_core.messages import (
    HumanMessage, AIMessage, AIMessageChunk, ToolMessage,
)

from app.graph.workflow import (
    build_graph,
)

from app.observability.langfuse_client import (
    get_langfuse_handler,
    is_langfuse_enabled,
    flush_langfuse,
)


def chat():

    graph = build_graph()

    THREAD_ID = input("Conversation ID: ")
    print("SHOP CUSTOMER SERVICE CHATBOT")
    print("Nhập 'exit' để thoát.")
    
    # Check Langfuse status
    if is_langfuse_enabled():
        print("✅ Langfuse tracking enabled")
    else:
        print("⚠️  Langfuse tracking disabled (credentials not configured)")

    tool_enabled = True
    while True:
        user_input = input(
            "\nUser: "
        )

        if user_input.lower() == "/tool off":
            tool_enabled = False
            print(
                "Tool disabled."
            )
            continue
        elif user_input.lower() == "/tool on":
            tool_enabled = True
            print(
                "Tool enabled."
            )
            continue

        if user_input.lower() == "exit":
            print(
                "Đã thoát chatbot."
            )
            # Flush Langfuse events before exit
            flush_langfuse()
            break

        user_message = HumanMessage(
            content=user_input
        )
        
        # Get Langfuse handler (if enabled)
        langfuse_handler = get_langfuse_handler()
        
        # Build callbacks list
        callbacks = [langfuse_handler] if langfuse_handler else []

        result = None
        streamed_output_started = False

        for mode, data in graph.stream(
            {
                "messages": [user_message]
            },
            config={
                 "configurable": {
                        "thread_id": THREAD_ID,
                        "tool_enabled": tool_enabled,
                    },
                 "callbacks": callbacks,
                 # Set trace attributes via metadata
                 "metadata": {
                     "langfuse_session_id": THREAD_ID,
                     "langfuse_metadata": {
                         "thread_id": THREAD_ID,
                         "tool_enabled": str(tool_enabled),
                     },
                 },
            },
            stream_mode=["messages", "values"],
        ):
            if mode == "messages":
                message, _metadata = data
                if isinstance(message, AIMessageChunk):
                    content = message.content

                    if isinstance(content, str):
                        if not streamed_output_started:
                            print(
                                "\nBot:",
                                end=" ",
                                flush=True,
                            )
                            streamed_output_started = True

                        print(
                            content,
                            end="",
                            flush=True,
                        )
                    elif isinstance(content, list):
                        text = "".join(
                            block.get("text", "")
                            for block in content
                            if isinstance(block, dict)
                            and block.get("type") == "text"
                        )

                        if text:
                            if not streamed_output_started:
                                print(
                                    "\nBot:",
                                    end=" ",
                                    flush=True,
                                )
                                streamed_output_started = True

                            print(
                                text,
                                end="",
                                flush=True,
                            )
            elif mode == "values":
                result = data

        if result is None:
            continue

        messages = result[
            "messages"
        ]

        # xác định các message trong turn hiện tại
        current_turn_start = len(messages) - 1
        for index in range(len(messages) - 1,-1,-1,):
            if isinstance(messages[index],HumanMessage,):
                current_turn_start = index
                break

        current_messages = messages[current_turn_start:]

        final_message = current_messages[-1]

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

# lấy tool calls
        tool_calls = []

        tool_results = {}
        for message in current_messages:
            if isinstance(
                message,
                ToolMessage,
            ):
                tool_results[
                    message.tool_call_id
                ] = message.content

        for message in current_messages:
            if isinstance(message,AIMessage,) and message.tool_calls:
                for tool_call in (
                    message.tool_calls
                ):
                    tool_call_record = {
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

                    tool_result = tool_results.get(
                        tool_call["id"]
                    )

                    if tool_result is not None:
                        tool_call_record[
                            "result"
                        ] = tool_result

                    tool_calls.append(
                        tool_call_record
                    )

        if streamed_output_started:
            print()
        else:
            print(
                "\nBot:",
                final_answer,
            )

if __name__ == "__main__":
    chat()