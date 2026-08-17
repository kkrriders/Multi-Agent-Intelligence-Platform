import os
import pytest

from app.graph import agent_graph, run_agent


def test_run_agent_builds_messages_with_memory_and_history(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {
        "input": "new question",
        "output": "",
        "history": [
            {"role": "user", "content": "prior q"},
            {"role": "assistant", "content": "prior a"},
        ],
        "memory_context": ["User: old q\nAssistant: old a"],
    }
    result = run_agent(state)

    assert result["output"] == "final answer"
    assert captured["messages"][0] == {
        "role": "system",
        "content": "Relevant memory from earlier in this project:\nUser: old q\nAssistant: old a",
    }
    assert captured["messages"][1:3] == state["history"]
    assert captured["messages"][3] == {"role": "user", "content": "new question"}


def test_run_agent_skips_system_message_when_no_memory_context(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {"input": "hello", "output": "", "history": [], "memory_context": []}
    run_agent(state)

    assert captured["messages"] == [{"role": "user", "content": "hello"}]


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_agent_graph_produces_output():
    result = agent_graph.invoke(
        {"input": "Say the word 'pong' and nothing else.", "output": "", "history": [], "memory_context": []}
    )
    assert result["output"]
    assert result["input"] == "Say the word 'pong' and nothing else."
