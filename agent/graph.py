from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    planner_node,
    reconciler_node,
    reflection_node,
    report_writer_node,
    web_search_node,
)
from agent.state import AgentState


def _route_reflection(state: AgentState) -> str:
    if state.get("status") == "retry":
        return "web_search"
    return END


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("reconciler", reconciler_node)
    graph.add_node("report_writer", report_writer_node)
    graph.add_node("reflection", reflection_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "web_search")
    graph.add_edge("web_search", "reconciler")
    graph.add_edge("reconciler", "report_writer")
    graph.add_edge("report_writer", "reflection")

    graph.add_conditional_edges(
        "reflection",
        _route_reflection,
        {"web_search": "web_search", END: END},
    )

    return graph.compile()
