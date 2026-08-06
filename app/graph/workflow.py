from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.prebuilt import (
    ToolNode,
    tools_condition,
)

from app.graph.state import ChatState

from app.graph.nodes import (
    call_llm,
)

from app.tools import (
    ALL_TOOLS,
)

from app.db.redis import(
    checkpointer,
)


def build_graph():

    builder = StateGraph(
        ChatState
    )

    builder.add_node(
        "llm",
        call_llm,
    )

    builder.add_node(
        "tools",
        ToolNode(
            ALL_TOOLS
        ),
    )

    builder.add_edge(
        START,
        "llm",
    )

    builder.add_conditional_edges(
        "llm",
        tools_condition,
    )

    builder.add_edge(
        "tools",
        "llm",
    )

    builder.add_edge(
        "llm",
        END,
    )

    return builder.compile(
        checkpointer=checkpointer
    )


graph = build_graph()