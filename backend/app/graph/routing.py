import json

import httpx
from langgraph.graph import END

from app.config import settings
from app.llm import MODEL_CHEAP, generate, set_node

MAX_TURNS = 4
MAX_TOOL_CALLS = 3
MAX_RESEARCHER_RERUNS = 1

JEV_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "~typesafe/jev-latest"
_JEV_ROUTE_CRITERIA = {
    "researcher": "background/context is still needed: summarizes memory + documents",
    "tool_runner": "an external REST tool still needs to be called for data the answer requires",
    "executor": "enough is known and the final answer still needs to be written",
    "verifier": "an answer has been drafted but not yet checked for support",
    "done": "the task is fully complete: an answer was drafted and already verified as supported",
}


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


def _jev_route(question: str, progress: str) -> str | None:
    """Backup router used only when the Groq call above fails — Jev
    (TypeSafe, via OpenRouter) benchmarked at 100% accuracy on this 5-way
    decision vs Groq's 87% (benchmarks/jev_vs_groq_routing.py), but Groq
    stays primary since it's the already-live dependency and this path only
    runs on a Groq failure/timeout. Never raises: returns None if
    OPENROUTER_API_KEY isn't configured or the call fails, so the caller
    falls through to the fixed skeleton exactly as it did before this
    backup existed."""
    if not settings.openrouter_api_key:
        return None
    try:
        resp = httpx.post(
            JEV_DECISIONS_URL,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": JEV_MODEL,
                "state": f"User question: {question}\n\nProgress:\n{progress}\n\nWhat next?",
                "questions": {
                    "next_step": {
                        "type": "choice",
                        "instructions": "Choose which worker should act next to answer the user's question.",
                        "criteria": _JEV_ROUTE_CRITERIA,
                    }
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        choice = resp.json()["answers"]["next_step"]["choice"]
        return choice if choice in _JEV_ROUTE_CRITERIA else None
    except Exception:  # noqa: BLE001 - backup path must never raise; a broken backup just falls through to the skeleton
        return None


def orchestrator_node(state):
    turn = state["turn"] + 1
    set_node("orchestrator")
    progress = _progress_summary(state)
    try:
        raw = generate(
            [
                {"role": "system", "content": _ORCHESTRATOR_SYSTEM},
                {"role": "user", "content": f"User question: {state['input']}\n\nProgress:\n{progress}\n\nWhat next?"},
            ],
            response_format={"type": "json_object"},
            model=MODEL_CHEAP,
        )
        choice = json.loads(raw).get("next", "")
    except Exception:  # noqa: BLE001 - Groq failure falls back to the Jev backup, then the fixed skeleton
        choice = _jev_route(state["input"], progress) or ""
    route = decide_route({**state, "turn": turn}, choice)
    event = {"step_name": "orchestrator_decision", "payload": {"turn": turn, "next": route, "llm_choice": choice}}
    return {**state, "turn": turn, "route": route, "events": state["events"] + [event]}
