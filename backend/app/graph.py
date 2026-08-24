from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm import generate

MAX_CHUNK_CHARS_IN_PROMPT = 500


class AgentState(TypedDict):
    input: str
    output: str
    history: list[dict]
    memory_context: list[str]
    retrieved_chunks: list[dict]


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
    if state["retrieved_chunks"]:
        sources = "\n".join(
            f"[{i + 1}] {chunk['filename']}: {chunk['content'][:MAX_CHUNK_CHARS_IN_PROMPT]}"
            for i, chunk in enumerate(state["retrieved_chunks"])
        )
        messages.append(
            {
                "role": "system",
                "content": f"Relevant sources from uploaded documents. Cite them inline as [1], [2], etc. when used:\n{sources}",
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
