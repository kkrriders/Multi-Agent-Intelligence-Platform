import os
import pytest

from app.config import settings
from app.llm import generate
import app.llm as llm_module


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
