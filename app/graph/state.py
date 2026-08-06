from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ChatState:
    messages: Annotated[
        list[AnyMessage],
        add_messages,
    ]