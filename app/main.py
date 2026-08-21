from app.service import ChatService
from app.observability.langfuse_client import (
    is_langfuse_enabled,
    flush_langfuse,
)


def chat():
    # Initialize chat service
    service = ChatService()
    
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
        user_input = input("\nUser: ")
        
        # Skip empty input
        if not user_input.strip():
            continue

        if user_input.lower() == "/tool off":
            tool_enabled = False
            print("Tool disabled.")
            continue
        elif user_input.lower() == "/tool on":
            tool_enabled = True
            print("Tool enabled.")
            continue

        if user_input.lower() == "exit":
            print("Đã thoát chatbot.")
            # Flush Langfuse events before exit
            flush_langfuse()
            break

        # Process message through service (streaming)
        streamed_output_started = False
        
        for event in service.process_message_stream(user_input, THREAD_ID, tool_enabled):
            if event["type"] == "chunk":
                if not streamed_output_started:
                    print("\nBot:", end=" ", flush=True)
                    streamed_output_started = True
                print(event["data"], end="", flush=True)
            
            elif event["type"] == "done":
                if streamed_output_started:
                    print()  # New line after streaming
                else:
                    # No chunks received, print final answer directly
                    print("\nBot:", event["final_answer"])
            
            elif event["type"] == "error":
                print(f"\n❌ Error: {event['error']}")

if __name__ == "__main__":
    chat()