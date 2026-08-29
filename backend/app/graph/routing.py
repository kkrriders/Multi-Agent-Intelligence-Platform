import json

from langgraph.graph import END

from app.llm import generate

MAX_TURNS = 4
MAX_TOOL_CALLS = 3
MAX_RESEARCHER_RERUNS = 1


def allowed_routes(state: dict) -> list[str]:
    routes: list[str] = []
    if state["researcher_runs"] < 1 + MAX_RESEARCHER_RERUNS:
        routes.append("researcher")
    if state["tool_specs"] and state["tool_calls_made"] < MAX_TOOL_CALLS:
        routes.append("tool_runner")
    routes.append("executor")
    if state["scratch"].get("executor"):
        routes.append("verifier")
    return routes


def _next_skeleton_step(state: dict) -> str:
    if not state["scratch"].get("researcher"):
        return "researcher"
    if not state["scratch"].get("executor"):
        return "executor"
    if not state["verdict"]:
        return "verifier"
    return "done"


def decide_route(state: dict, llm_choice: str) -> str:
    """Clamp the orchestrator LLM's choice into a bounded route. `state["turn"]`
    is the already-incremented current turn."""
    if state["turn"] >= MAX_TURNS:
        if not state["scratch"].get("executor"):
            return "executor"
        if not state["verdict"]:
            return "verifier"
        return "done"

    if llm_choice == "done":
        # Premature "done" — advance through the fixed skeleton instead of
        # ending. researcher -> executor -> verifier -> done, in order.
        return _next_skeleton_step(state) if not state["verdict"] else "done"

    # No repeating a worker back-to-back, except the one allowed researcher re-run.
    if llm_choice == state.get("route") and llm_choice != "researcher":
        return _next_skeleton_step(state)

    if llm_choice in allowed_routes(state):
        return llm_choice

    return _next_skeleton_step(state)


def route_edge(state: dict) -> str:
    return END if state["route"] == "done" else state["route"]


_ORCHESTRATOR_SYSTEM = (
    "You coordinate a small team answering the user's question. Workers: "
    "researcher (summarizes memory + documents), tool_runner (calls an external REST tool), "
    "executor (writes the final answer), verifier (checks the answer). "
    'Reply ONLY with JSON: {"next": "<researcher|tool_runner|executor|verifier|done>", "reason": "<short>"}.'
)


def _progress_summary(state: dict) -> str:
    lines = []
    if state["scratch"].get("researcher"):
        lines.append("- researcher has produced a brief")
    if state["scratch"].get("tools"):
        lines.append(f"- tool_runner has {len(state['scratch']['tools'])} tool result(s)")
    if state["scratch"].get("executor"):
        lines.append("- executor has drafted an answer")
    if state["verdict"]:
        lines.append(f"- verifier says supported={state['verdict'].get('supported')}")
    if state["tool_specs"]:
        lines.append(f"- {len(state['tool_specs'])} tool(s) are available")
    return "\n".join(lines) or "- nothing done yet"


def orchestrator_node(state):
    turn = state["turn"] + 1
    raw = generate(
        [
            {"role": "system", "content": _ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": f"User question: {state['input']}\n\nProgress:\n{_progress_summary(state)}\n\nWhat next?"},
        ],
        response_format={"type": "json_object"},
    )
    try:
        choice = json.loads(raw).get("next", "")
    except (json.JSONDecodeError, AttributeError, TypeError):
        choice = ""
    route = decide_route({**state, "turn": turn}, choice)
    event = {"step_name": "orchestrator_decision", "payload": {"turn": turn, "next": route, "llm_choice": choice}}
    return {**state, "turn": turn, "route": route, "events": state["events"] + [event]}
