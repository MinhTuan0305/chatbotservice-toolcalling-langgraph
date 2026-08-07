from langgraph.prebuilt import tools_condition
from langgraph.graph import END

def tool_router(state, config):
    configurable = config.get("configurable", {})

    if not configurable.get("tool_enabled", True):
        return END

    return tools_condition(state)