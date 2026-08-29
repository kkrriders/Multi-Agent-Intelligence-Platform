from langgraph.graph import END, StateGraph

from app.graph.routing import orchestrator_node, route_edge
from app.graph.state import AgentState
from app.graph.workers import executor_node, make_tool_runner, researcher_node, verifier_node

_WORKERS = ("researcher", "tool_runner", "executor", "verifier")


def build_graph(tool_configs: dict | None = None):
    graph = StateGraph(AgentState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("tool_runner", make_tool_runner(tool_configs or {}))
    graph.add_node("executor", executor_node)
    graph.add_node("verifier", verifier_node)
    graph.set_entry_point("orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        route_edge,
        {
            "researcher": "researcher",
            "tool_runner": "tool_runner",
            "executor": "executor",
            "verifier": "verifier",
            END: END,
        },
    )
    for worker in _WORKERS:
        graph.add_edge(worker, "orchestrator")
    return graph.compile()


agent_graph = build_graph()


def make_initial_state(*, input, history, memory_context, retrieved_chunks, tool_specs) -> AgentState:
    return {
        "input": input,
        "history": history,
        "memory_context": memory_context,
        "retrieved_chunks": retrieved_chunks,
        "tool_specs": tool_specs,
        "scratch": {},
        "events": [],
        "turn": 0,
        "tool_calls_made": 0,
        "researcher_runs": 0,
        "route": "",
        "verdict": {},
        "output": "",
    }
