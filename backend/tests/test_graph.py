import json
import os

import pytest

from app.graph import agent_graph, build_graph, make_initial_state
from app.graph.routing import orchestrator_node
from app.graph.workers import executor_node, make_tool_runner, researcher_node, verifier_node


def _state(**over):
    base = make_initial_state(
        input="What is the capital of France?",
        history=[],
        memory_context=[],
        retrieved_chunks=[],
        tool_specs=[],
    )
    base.update(over)
    return base


# ---- orchestrator ----

def test_orchestrator_increments_turn_and_records_decision(monkeypatch):
    monkeypatch.setattr(
        "app.graph.routing.generate",
        lambda *a, **k: json.dumps({"next": "researcher", "reason": "need context"}),
    )
    out = orchestrator_node(_state(turn=0))
    assert out["turn"] == 1
    assert out["route"] == "researcher"
    ev = out["events"][-1]
    assert ev["step_name"] == "orchestrator_decision"
    assert ev["payload"] == {"turn": 1, "next": "researcher", "llm_choice": "researcher"}


def test_orchestrator_unparseable_json_falls_back_to_skeleton(monkeypatch):
    monkeypatch.setattr("app.graph.routing.generate", lambda *a, **k: "not json at all")
    out = orchestrator_node(_state(turn=0))
    assert out["route"] == "researcher"


def _raise(*a, **k):
    raise RuntimeError("groq 400 json_validate_failed")


def test_orchestrator_generate_error_falls_back_to_skeleton(monkeypatch):
    monkeypatch.setattr("app.graph.routing.generate", _raise)
    out = orchestrator_node(_state(turn=0))
    assert out["route"] == "researcher"


def test_verifier_generate_error_passes_answer_through(monkeypatch):
    monkeypatch.setattr("app.graph.workers.generate", _raise)
    out = verifier_node(_state(turn=1, output="an answer", scratch={"researcher": "x", "tools": []}))
    assert out["output"] == "an answer"
    assert out["verdict"]["supported"] is True


# ---- model-tier routing (Phase 3, Token Optimization) ----

def _capture_generate(monkeypatch, target, ret):
    calls = []

    def fake(*a, **k):
        calls.append(k)
        return ret

    monkeypatch.setattr(target, fake)
    return calls


def test_orchestrator_uses_cheap_model(monkeypatch):
    from app.llm import MODEL_CHEAP

    calls = _capture_generate(monkeypatch, "app.graph.routing.generate", json.dumps({"next": "done"}))
    orchestrator_node(_state(turn=0))
    assert calls[0]["model"] == MODEL_CHEAP


def test_researcher_and_verifier_use_cheap_model_executor_does_not(monkeypatch):
    from app.llm import MODEL, MODEL_CHEAP

    r_calls = _capture_generate(monkeypatch, "app.graph.workers.generate", "brief")
    researcher_node(_state(turn=1))
    assert r_calls[0]["model"] == MODEL_CHEAP

    v_calls = _capture_generate(
        monkeypatch, "app.graph.workers.generate", '{"supported": true, "note": "ok"}'
    )
    verifier_node(_state(turn=1, output="an answer", scratch={"researcher": "x", "tools": []}))
    assert v_calls[0]["model"] == MODEL_CHEAP

    e_calls = _capture_generate(monkeypatch, "app.graph.workers.generate", "the answer")
    executor_node(_state(turn=1))
    assert e_calls[0].get("model", MODEL) == MODEL


def test_worker_nodes_set_usage_attribution(monkeypatch):
    from app.llm import reset_usage, _current_node

    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "the answer")
    reset_usage()
    executor_node(_state(turn=1))
    assert _current_node.get() == "executor"


# ---- researcher ----

def test_researcher_writes_brief_and_counts(monkeypatch):
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "Paris is the capital of France.")
    s = _state(
        turn=1,
        memory_context=["User: hi\nAssistant: hello"],
        retrieved_chunks=[{"filename": "geo.txt", "content": "France's capital is Paris."}],
    )
    out = researcher_node(s)
    assert out["scratch"]["researcher"] == "Paris is the capital of France."
    assert out["researcher_runs"] == 1
    ev = out["events"][-1]
    assert ev["step_name"] == "worker_researcher"
    assert ev["payload"] == {"turn": 1, "chunk_count": 1, "memory_count": 1}


# ---- tool_runner ----

class _FakeFn:
    def __init__(self, name, arguments):
        self.name, self.arguments = name, arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFn(name, arguments)


class _FakeMsg:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls


def test_tool_runner_executes_calls_and_emits_events(monkeypatch):
    monkeypatch.setattr(
        "app.graph.workers.generate",
        lambda *a, **k: _FakeMsg([_FakeToolCall("Weather", '{"city": "Paris"}')]),
    )
    monkeypatch.setattr(
        "app.graph.workers.execute_tool_call",
        lambda tc, cfg: {"tool": "Weather", "status": 200, "args": {"city": "Paris"}, "body": "sunny"},
    )
    node = make_tool_runner({"Weather": {"url": "https://x", "method": "GET", "headers": {}}})
    s = _state(
        turn=2,
        tool_specs=[{"name": "Weather", "description": "d", "parameters": {"type": "object", "properties": {}}}],
    )
    out = node(s)
    assert out["scratch"]["tools"] == [{"tool": "Weather", "status": 200, "args": {"city": "Paris"}, "body": "sunny"}]
    assert out["tool_calls_made"] == 1
    ev = out["events"][-1]
    assert ev["step_name"] == "tool_called"
    assert ev["payload"] == {"turn": 2, "tool": "Weather", "status": 200, "args": {"city": "Paris"}, "body": "sunny"}


def test_tool_runner_no_tool_call_emits_no_tool_used(monkeypatch):
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: _FakeMsg([]))
    node = make_tool_runner({})
    out = node(_state(turn=2, tool_specs=[{"name": "W", "description": "d", "parameters": {}}]))
    assert out["events"][-1] == {"step_name": "no_tool_used", "payload": {"turn": 2}}


def test_tool_runner_respects_max_tool_calls(monkeypatch):
    from app.graph.routing import MAX_TOOL_CALLS

    many = [_FakeToolCall("W", "{}") for _ in range(MAX_TOOL_CALLS + 3)]
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: _FakeMsg(many))
    monkeypatch.setattr(
        "app.graph.workers.execute_tool_call",
        lambda tc, cfg: {"tool": "W", "status": 200, "args": {}, "body": "ok"},
    )
    node = make_tool_runner({"W": {"url": "https://x", "method": "GET", "headers": {}}})
    out = node(_state(turn=2, tool_calls_made=0, tool_specs=[{"name": "W"}]))
    assert out["tool_calls_made"] == MAX_TOOL_CALLS


# ---- executor ----

def test_executor_writes_output_and_scratch(monkeypatch):
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "The capital of France is Paris [1].")
    s = _state(
        turn=3,
        scratch={"researcher": "France's capital is Paris."},
        retrieved_chunks=[{"filename": "geo.txt", "content": "France's capital is Paris."}],
    )
    out = executor_node(s)
    assert out["output"] == "The capital of France is Paris [1]."
    assert out["scratch"]["executor"] == "The capital of France is Paris [1]."
    assert out["events"][-1]["step_name"] == "worker_executor"


# ---- verifier ----

def test_verifier_supported_leaves_output_untouched(monkeypatch):
    monkeypatch.setattr(
        "app.graph.workers.generate",
        lambda *a, **k: json.dumps({"supported": True, "note": "matches context"}),
    )
    s = _state(turn=4, output="Paris.", scratch={"researcher": "Paris is the capital."})
    out = verifier_node(s)
    assert out["verdict"] == {"supported": True, "note": "matches context"}
    assert out["output"] == "Paris."
    assert out["events"][-1]["step_name"] == "verifier_check"


def test_verifier_unsupported_appends_warning(monkeypatch):
    monkeypatch.setattr(
        "app.graph.workers.generate",
        lambda *a, **k: json.dumps({"supported": False, "note": "no source for this"}),
    )
    out = verifier_node(_state(turn=4, output="Lyon.", scratch={"researcher": "Paris is the capital."}))
    assert out["output"] == "Lyon.\n\n⚠ unverified: no source for this"


def test_verifier_unparseable_passes_through(monkeypatch):
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "garbage")
    out = verifier_node(_state(turn=4, output="Paris."))
    assert out["verdict"]["supported"] is True
    assert out["output"] == "Paris."


# ---- graph assembly (fake generate, no network) ----

def test_graph_walks_orchestrator_to_workers_to_end(monkeypatch):
    monkeypatch.setattr("app.graph.routing.generate", lambda *a, **k: json.dumps({"next": "done"}))
    monkeypatch.setattr("app.graph.workers.generate", lambda *a, **k: "stub answer")
    graph = build_graph({})
    result = graph.invoke(
        make_initial_state(input="hi", history=[], memory_context=[], retrieved_chunks=[], tool_specs=[])
    )
    names = [e["step_name"] for e in result["events"]]
    assert "worker_researcher" in names
    assert "worker_executor" in names
    assert "verifier_check" in names
    assert result["output"]
    assert result["turn"] <= 4


# ---- integration (real Groq) ----

@pytest.mark.skipif(os.environ.get("GROQ_API_KEY", "test") == "test", reason="Real GROQ_API_KEY required")
def test_agent_graph_real_run_produces_verified_output():
    result = agent_graph.invoke(
        make_initial_state(
            input="Reply with the single word: pong.",
            history=[],
            memory_context=[],
            retrieved_chunks=[],
            tool_specs=[],
        )
    )
    names = [e["step_name"] for e in result["events"]]
    assert result["output"]
    assert "verifier_check" in names
    assert names.count("orchestrator_decision") >= 1
    assert result["turn"] <= 4
