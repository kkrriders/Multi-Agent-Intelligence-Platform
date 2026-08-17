from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm import generate


class AgentState(TypedDict):
    input: str
    output: str
    history: list[dict]
    memory_context: list[str]


def run_agent(state: AgentState) -> AgentState:
    messages: list[dict] = []
    if state["memory_context"]:
        context_text = "\n".join(state["memory_context"])
        messages.append(
            {
                "role": "system",
                "content": f"Relevant memory from earlier in this project:\n{context_text}",
            }
        )
    messages.extend(state["history"])
    messages.append({"role": "user", "content": state["input"]})
    return {**state, "output": generate(messages)}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", run_agent)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()


agent_graph = build_graph()
