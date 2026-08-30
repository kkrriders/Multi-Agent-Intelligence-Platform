import json

from app.graph.routing import MAX_TOOL_CALLS
from app.graph.tool_schemas import build_tool_schemas, execute_tool_call
from app.llm import MODEL_CHEAP, generate, set_node

CONTEXT_CHARS = 500
TOOL_RESULT_CHARS = 500
VERIFIER_CONTEXT_CHARS = 2000


def _sources_block(chunks: list[dict]) -> str:
    return "\n".join(
        f"[{i + 1}] {c['filename']}: {c['content'][:CONTEXT_CHARS]}" for i, c in enumerate(chunks)
    )


def researcher_node(state):
    parts = []
    if state["memory_context"]:
        parts.append("Memory from earlier:\n" + "\n".join(state["memory_context"]))
    if state["retrieved_chunks"]:
        parts.append("Documents:\n" + _sources_block(state["retrieved_chunks"]))
    context = "\n\n".join(parts) or "(no external context available)"
    set_node("researcher")
    brief = generate(
        [
            {
                "role": "system",
                "content": "Summarize only the context relevant to the user's question in 3-5 sentences. If nothing is relevant, say exactly: no relevant context.",
            },
            {"role": "user", "content": f"Question: {state['input']}\n\n{context}"},
        ],
        model=MODEL_CHEAP,
    )
    event = {
        "step_name": "worker_researcher",
        "payload": {
            "turn": state["turn"],
            "chunk_count": len(state["retrieved_chunks"]),
            "memory_count": len(state["memory_context"]),
        },
    }
    return {
        **state,
        "scratch": {**state["scratch"], "researcher": brief},
        "researcher_runs": state["researcher_runs"] + 1,
        "events": state["events"] + [event],
    }


def make_tool_runner(tool_configs: dict):
    def tool_runner_node(state):
        schemas = build_tool_schemas(state["tool_specs"])
        set_node("tool_runner")
        message = generate(
            [
                {
                    "role": "system",
                    "content": "If a tool helps answer the question, call it with correct arguments. Otherwise reply normally.",
                },
                {"role": "user", "content": state["input"]},
            ],
            tools=schemas,
        )
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        results = list(state["scratch"].get("tools", []))
        calls_made = state["tool_calls_made"]
        new_events = []
        for tc in tool_calls:
            if calls_made >= MAX_TOOL_CALLS:
                break
            result = execute_tool_call(tc, tool_configs)
            calls_made += 1
            results.append(result)
            new_events.append({"step_name": "tool_called", "payload": {"turn": state["turn"], **result}})
        if not tool_calls:
            new_events.append({"step_name": "no_tool_used", "payload": {"turn": state["turn"]}})
        return {
            **state,
            "scratch": {**state["scratch"], "tools": results},
            "tool_calls_made": calls_made,
            "events": state["events"] + new_events,
        }

    return tool_runner_node


def executor_node(state):
    blocks = []
    if state["scratch"].get("researcher"):
        blocks.append("Research brief:\n" + state["scratch"]["researcher"])
    if state["scratch"].get("tools"):
        blocks.append(
            "Tool results:\n"
            + "\n".join(
                f"- {r['tool']} -> {r.get('status')}: {str(r.get('body', r.get('error', '')))[:TOOL_RESULT_CHARS]}"
                for r in state["scratch"]["tools"]
            )
        )
    if state["retrieved_chunks"]:
        blocks.append("Sources (cite inline as [1], [2], ...):\n" + _sources_block(state["retrieved_chunks"]))
    tail = ("\n\n" + "\n\n".join(blocks)) if blocks else ""
    messages = [
        {
            "role": "system",
            "content": "Answer the user's question using the material provided. Cite documents inline as [n] when used.",
        }
    ]
    messages += state["history"]
    messages.append({"role": "user", "content": state["input"] + tail})
    set_node("executor")
    answer = generate(messages)
    return {
        **state,
        "scratch": {**state["scratch"], "executor": answer},
        "output": answer,
        "events": state["events"] + [{"step_name": "worker_executor", "payload": {"turn": state["turn"]}}],
    }


_VERIFIER_SYSTEM = (
    "Check whether the ANSWER is supported by the CONTEXT and addresses the QUESTION. "
    'Reply ONLY with JSON: {"supported": <true|false>, "note": "<one sentence>"}.'
)


def verifier_node(state):
    context = state["scratch"].get("researcher", "")
    for r in state["scratch"].get("tools", []):
        context += "\n" + str(r.get("body", r.get("error", "")))
    set_node("verifier")
    try:
        raw = generate(
            [
                {"role": "system", "content": _VERIFIER_SYSTEM},
                {
                    "role": "user",
                    "content": f"QUESTION: {state['input']}\n\nCONTEXT: {context[:VERIFIER_CONTEXT_CHARS]}\n\nANSWER: {state['output']}",
                },
            ],
            response_format={"type": "json_object"},
            model=MODEL_CHEAP,
        )
        parsed = json.loads(raw)
        verdict = {"supported": bool(parsed.get("supported")), "note": str(parsed.get("note", ""))}
    except Exception:  # noqa: BLE001 - any verifier-call failure passes the answer through unflagged
        verdict = {"supported": True, "note": "verifier response unparseable; passing through"}
    output = state["output"]
    if not verdict["supported"]:
        output = f"{output}\n\n⚠ unverified: {verdict['note']}"
    return {
        **state,
        "verdict": verdict,
        "output": output,
        "events": state["events"] + [{"step_name": "verifier_check", "payload": {"turn": state["turn"], **verdict}}],
    }
