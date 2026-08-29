from typing import TypedDict


class AgentState(TypedDict):
    input: str
    history: list[dict]
    memory_context: list[str]
    retrieved_chunks: list[dict]
    tool_specs: list[dict]
    scratch: dict
    events: list[dict]
    turn: int
    tool_calls_made: int
    researcher_runs: int
    route: str
    verdict: dict
    output: str
