import os
import pytest

from app.config import settings
from app.llm import MODEL, MODEL_CHEAP, drain_usage, generate, reset_usage, set_node
import app.llm as llm_module


class _Usage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


def _fake_create_with_usage(prompt_tokens=10, completion_tokens=5):
    def fake_create(**kwargs):
        completion = _FakeCompletion()
        completion.usage = _Usage(prompt_tokens, completion_tokens)
        return completion

    return fake_create


@pytest.fixture(autouse=True)
def _fresh_usage_log():
    reset_usage()
    yield
    reset_usage()


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_generate_returns_nonempty_string():
    result = generate([{"role": "user", "content": "Say the word 'pong' and nothing else."}])
    assert isinstance(result, str)
    assert len(result) > 0


class _FakeMessage:
    def __init__(self):
        self.content = "hello"
        self.tool_calls = ["sentinel"]


class _FakeChoice:
    def __init__(self):
        self.message = _FakeMessage()


class _FakeCompletion:
    def __init__(self):
        self.choices = [_FakeChoice()]


def test_generate_without_tools_returns_content_string(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeCompletion()

    monkeypatch.setattr(llm_module._client.chat.completions, "create", fake_create)

    result = llm_module.generate([{"role": "user", "content": "hi"}])

    assert result == "hello"
    assert captured["timeout"] == 30
    assert captured.get("tools") is None
    assert captured.get("tool_choice") is None


def test_generate_with_tools_returns_message_and_sets_tool_choice(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeCompletion()

    monkeypatch.setattr(llm_module._client.chat.completions, "create", fake_create)

    schemas = [{"type": "function", "function": {"name": "x", "parameters": {"type": "object", "properties": {}}}}]
    result = llm_module.generate([{"role": "user", "content": "hi"}], tools=schemas)

    assert result.tool_calls == ["sentinel"]
    assert captured["tools"] == schemas
    assert captured["tool_choice"] == "auto"


def test_generate_passes_response_format(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        llm_module._client.chat.completions, "create",
        lambda **kwargs: (captured.update(kwargs), _FakeCompletion())[1],
    )

    llm_module.generate([{"role": "user", "content": "hi"}], response_format={"type": "json_object"})

    assert captured["response_format"] == {"type": "json_object"}


def test_generate_records_usage_into_the_log(monkeypatch):
    monkeypatch.setattr(
        llm_module._client.chat.completions, "create", _fake_create_with_usage(10, 5)
    )

    llm_module.generate([{"role": "user", "content": "hi"}])

    assert drain_usage() == [
        {"model": MODEL, "node": "llm", "prompt_tokens": 10, "completion_tokens": 5}
    ]


def test_set_node_attributes_the_recorded_usage(monkeypatch):
    monkeypatch.setattr(
        llm_module._client.chat.completions, "create", _fake_create_with_usage()
    )

    set_node("executor")
    llm_module.generate([{"role": "user", "content": "hi"}])

    assert drain_usage()[0]["node"] == "executor"


def test_model_override_is_passed_through_and_recorded(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        completion = _FakeCompletion()
        completion.usage = _Usage(1, 1)
        return completion

    monkeypatch.setattr(llm_module._client.chat.completions, "create", fake_create)

    llm_module.generate([{"role": "user", "content": "hi"}], model=MODEL_CHEAP)

    assert captured["model"] == MODEL_CHEAP
    assert drain_usage()[0]["model"] == MODEL_CHEAP


def test_drain_usage_empties_the_log(monkeypatch):
    monkeypatch.setattr(
        llm_module._client.chat.completions, "create", _fake_create_with_usage()
    )
    llm_module.generate([{"role": "user", "content": "hi"}])

    assert len(drain_usage()) == 1
    assert drain_usage() == []


def test_generate_without_usage_field_records_nothing(monkeypatch):
    monkeypatch.setattr(
        llm_module._client.chat.completions, "create", lambda **kw: _FakeCompletion()
    )

    llm_module.generate([{"role": "user", "content": "hi"}])

    assert drain_usage() == []
