"""
AI Chat Service Module

Provides reusable chatbot service that can be consumed by CLI, Socket Server, or other interfaces.
Extracts chatbot logic from main.py into a clean service layer.
"""

from typing import Generator, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage

from app.graph.workflow import build_graph
from app.observability.langfuse_client import get_langfuse_handler


class ChatService:
    """
    Chat service that processes messages through LangGraph workflow.
    
    Supports both streaming and non-streaming responses.
    Maintains existing features: tools, memory, Langfuse observability.
    """
    
    def __init__(self):
        """Initialize the chat service with LangGraph workflow."""
        self.graph = build_graph()
    
    def process_message(
        self,
        user_input: str,
        thread_id: str,
        tool_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single message and return final response (non-streaming).
        
        Args:
            user_input: User's message text
            thread_id: Conversation thread identifier
            tool_enabled: Whether to enable tool calls
            
        Returns:
            Dict containing:
                - final_answer (str): Bot's final response
                - tool_calls (list): List of tool calls made (if any)
                - error (str): Error message if processing failed
                
        Raises:
            ValueError: If user_input is empty
        """
        # Validate input
        if not user_input or not user_input.strip():
            return {
                "final_answer": "",
                "tool_calls": [],
                "error": "Empty message not allowed"
            }
        
        try:
            user_message = HumanMessage(content=user_input)
            
            # Get Langfuse handler (if enabled)
            langfuse_handler = get_langfuse_handler()
            callbacks = [langfuse_handler] if langfuse_handler else []
            
            # Process through graph
            result = None
            for chunk in self.graph.stream(
                {"messages": [user_message]},
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "tool_enabled": tool_enabled,
                    },
                    "callbacks": callbacks,
                    "metadata": {
                        "langfuse_session_id": thread_id,
                        "langfuse_metadata": {
                            "thread_id": thread_id,
                            "tool_enabled": str(tool_enabled),
                        },
                    },
                },
                stream_mode="values",
            ):
                result = chunk
            
            if result is None:
                return {
                    "final_answer": "",
                    "tool_calls": [],
                    "error": "No response from graph"
                }
            
            messages = result["messages"]
            
            # Extract final answer and tool calls
            final_answer = self._extract_final_answer(messages)
            tool_calls = self._extract_tool_calls(messages)
            
            return {
                "final_answer": final_answer,
                "tool_calls": tool_calls,
            }
            
        except Exception as e:
            return {
                "final_answer": "",
                "tool_calls": [],
                "error": str(e)
            }
    
    def process_message_stream(
        self,
        user_input: str,
        thread_id: str,
        tool_enabled: bool = True
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Process a message and stream response chunks in real-time.
        
        Args:
            user_input: User's message text
            thread_id: Conversation thread identifier
            tool_enabled: Whether to enable tool calls
            
        Yields:
            Dict containing one of:
                - {"type": "chunk", "data": str} - Text chunk
                - {"type": "done", "final_answer": str, "tool_calls": list} - Final result
                - {"type": "error", "error": str} - Error occurred
        """
        # Validate input
        if not user_input or not user_input.strip():
            yield {
                "type": "error",
                "error": "Empty message not allowed"
            }
            return
        
        try:
            user_message = HumanMessage(content=user_input)
            
            # Get Langfuse handler (if enabled)
            langfuse_handler = get_langfuse_handler()
            callbacks = [langfuse_handler] if langfuse_handler else []
            
            result = None
            
            # Stream through graph
            for mode, data in self.graph.stream(
                {"messages": [user_message]},
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "tool_enabled": tool_enabled,
                    },
                    "callbacks": callbacks,
                    "metadata": {
                        "langfuse_session_id": thread_id,
                        "langfuse_metadata": {
                            "thread_id": thread_id,
                            "tool_enabled": str(tool_enabled),
                        },
                    },
                },
                stream_mode=["messages", "values"],
            ):
                if mode == "messages":
                    message, _metadata = data
                    
                    # Stream AI message chunks
                    if isinstance(message, AIMessageChunk):
                        content = message.content
                        
                        # Handle string content
                        if isinstance(content, str):
                            if content:  # Only yield non-empty chunks
                                yield {
                                    "type": "chunk",
                                    "data": content
                                }
                        
                        # Handle list content (multi-part messages)
                        elif isinstance(content, list):
                            text = "".join(
                                block.get("text", "")
                                for block in content
                                if isinstance(block, dict) and block.get("type") == "text"
                            )
                            if text:
                                yield {
                                    "type": "chunk",
                                    "data": text
                                }
                
                elif mode == "values":
                    result = data
            
            # Final result
            if result is not None:
                messages = result["messages"]
                final_answer = self._extract_final_answer(messages)
                tool_calls = self._extract_tool_calls(messages)
                
                yield {
                    "type": "done",
                    "final_answer": final_answer,
                    "tool_calls": tool_calls,
                }
            else:
                yield {
                    "type": "error",
                    "error": "No response from graph"
                }
                
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e)
            }
    
    def _extract_final_answer(self, messages: list) -> str:
        """
        Extract final answer from current turn messages.
        
        Args:
            messages: List of all messages in conversation
            
        Returns:
            str: Final answer text
        """
        # Find current turn (from last HumanMessage to end)
        current_turn_start = len(messages) - 1
        for index in range(len(messages) - 1, -1, -1):
            if isinstance(messages[index], HumanMessage):
                current_turn_start = index
                break
        
        current_messages = messages[current_turn_start:]
        
        if not current_messages:
            return ""
        
        final_message = current_messages[-1]
        content = final_message.content
        
        # Handle different content types
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "\n".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            return str(content)
    
    def _extract_tool_calls(self, messages: list) -> list:
        """
        Extract tool calls from current turn messages.
        
        Args:
            messages: List of all messages in conversation
            
        Returns:
            list: List of tool call records with name, args, and results
        """
        # Find current turn
        current_turn_start = len(messages) - 1
        for index in range(len(messages) - 1, -1, -1):
            if isinstance(messages[index], HumanMessage):
                current_turn_start = index
                break
        
        current_messages = messages[current_turn_start:]
        
        # Build tool results map
        tool_results = {}
        for message in current_messages:
            if isinstance(message, ToolMessage):
                tool_results[message.tool_call_id] = message.content
        
        # Extract tool calls
        tool_calls = []
        for message in current_messages:
            if isinstance(message, AIMessage) and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_call_record = {
                        "tool_name": tool_call["name"],
                        "arguments": tool_call["args"],
                        "tool_call_id": tool_call["id"],
                    }
                    
                    # Add result if available
                    tool_result = tool_results.get(tool_call["id"])
                    if tool_result is not None:
                        tool_call_record["result"] = tool_result
                    
                    tool_calls.append(tool_call_record)
        
        return tool_calls
