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
        "retrieved_chunks": [],
    }
    result = run_agent(state)

    assert result["output"] == "final answer"
    assert captured["messages"][0] == {
        "role": "system",
        "content": "Relevant memory from earlier in this project:\nUser: old q\nAssistant: old a",
    }
    assert captured["messages"][1:3] == state["history"]
    assert captured["messages"][3] == {"role": "user", "content": "new question"}


def test_run_agent_skips_system_messages_when_no_context(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {"input": "hello", "output": "", "history": [], "memory_context": [], "retrieved_chunks": []}
    run_agent(state)

    assert captured["messages"] == [{"role": "user", "content": "hello"}]


def test_run_agent_builds_sources_message_from_retrieved_chunks(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {
        "input": "What is the codeword?",
        "output": "",
        "history": [],
        "memory_context": [],
        "retrieved_chunks": [
            {"filename": "notes.txt", "content": "The codeword is Bluebird."},
            {"filename": "backup.txt", "content": "Backup codeword is Cardinal."},
        ],
    }
    run_agent(state)

    assert captured["messages"][0] == {
        "role": "system",
        "content": (
            "Relevant sources from uploaded documents. Cite them inline as [1], [2], etc. when used:\n"
            "[1] notes.txt: The codeword is Bluebird.\n"
            "[2] backup.txt: Backup codeword is Cardinal."
        ),
    }
    assert captured["messages"][1] == {"role": "user", "content": "What is the codeword?"}


def test_run_agent_truncates_long_chunks_in_sources_message(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    long_content = "x" * 600
    state = {
        "input": "hello",
        "output": "",
        "history": [],
        "memory_context": [],
        "retrieved_chunks": [{"filename": "notes.txt", "content": long_content}],
    }
    run_agent(state)

    sources_message = captured["messages"][0]["content"]
    assert "x" * 500 in sources_message
    assert "x" * 501 not in sources_message


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_agent_graph_produces_output():
    result = agent_graph.invoke(
        {
            "input": "Say the word 'pong' and nothing else.",
            "output": "",
            "history": [],
            "memory_context": [],
            "retrieved_chunks": [],
        }
    )
    assert result["output"]
    assert result["input"] == "Say the word 'pong' and nothing else."
