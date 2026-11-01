from langgraph.graph import END, START, StateGraph

from seller_support.graph.nodes import AssessmentNodes
from seller_support.graph.state import AssessmentState
from seller_support.tools import ReadTools


def after_preflight(state):
    return END if state["recommendation"] else "agent"


def after_agent(state):
    if state.get("error"):
        return END
    return "tools" if state["messages"][-1].tool_calls else "finalise"


def after_tools(state):
    return END if state.get("error") else "agent"


def after_finalise(state):
    return END if state.get("error") or state.get("recommendation") else "agent"


def build_graph(
    tools: ReadTools,
    agent_model=None,
    final_model=None,
    *,
    model_factory=None,
    max_model_calls: int = 8,
    max_tool_calls: int = 16,
):
    """A fresh, read-only session. Runtime models are created only after preflight."""
    nodes = AssessmentNodes(
        tools=tools,
        agent_model=agent_model,
        final_model=final_model,
        model_factory=model_factory,
        max_model_calls=max_model_calls,
        max_tool_calls=max_tool_calls,
    )
    graph = StateGraph(AssessmentState)
    graph.add_node("preflight", nodes.preflight)
    graph.add_node("agent", nodes.agent)
    graph.add_node("tools", nodes.execute_tools)
    graph.add_node("finalise", nodes.finalise)
    graph.add_edge(START, "preflight")
    graph.add_conditional_edges("preflight", after_preflight, [END, "agent"])
    graph.add_conditional_edges("agent", after_agent, [END, "tools", "finalise"])
    graph.add_conditional_edges("tools", after_tools, [END, "agent"])
    graph.add_conditional_edges("finalise", after_finalise, [END, "agent"])
    return graph.compile()
