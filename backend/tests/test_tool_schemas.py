import json

import pytest

from app.graph.tool_schemas import build_tool_schemas, execute_tool_call, sanitize_tools


def test_sanitize_keeps_only_get_rest_tools():
    rows = [
        {"name": "Weather API", "type": "rest", "config": {"url": "https://api.example.com/w", "method": "GET"}},
        {"name": "Create Order", "type": "rest", "config": {"url": "https://api.example.com/o", "method": "POST"}},
        {"name": "Some SQL", "type": "sql", "config": {}},
        {"name": "No Method", "type": "rest", "config": {"url": "https://api.example.com/n"}},
    ]
    specs, configs = sanitize_tools(rows)

    names = {s["name"] for s in specs}
    assert names == {"Weather_API", "No_Method"}
    assert configs["Weather_API"] == {"url": "https://api.example.com/w", "method": "GET", "headers": {}}
    assert set(configs) == names


def test_sanitize_uses_declared_parameters_or_empty_object():
    params = {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    rows = [
        {"name": "A", "type": "rest", "config": {"url": "https://x/a", "method": "GET", "parameters": params}},
        {"name": "B", "type": "rest", "config": {"url": "https://x/b", "method": "GET"}},
    ]
    specs, _ = sanitize_tools(rows)
    by_name = {s["name"]: s for s in specs}

    assert by_name["A"]["parameters"] == params
    assert by_name["B"]["parameters"] == {"type": "object", "properties": {}}


def test_sanitize_slugifies_names_to_groq_function_name_rules():
    rows = [{"name": "My Cool Tool! (v2)", "type": "rest", "config": {"url": "https://x", "method": "GET"}}]
    specs, configs = sanitize_tools(rows)
    assert specs[0]["name"] == "My_Cool_Tool___v2_"
    assert specs[0]["name"] in configs


def test_build_tool_schemas_wraps_each_spec():
    specs = [{"name": "A", "description": "d", "parameters": {"type": "object", "properties": {}}}]
    assert build_tool_schemas(specs) == [
        {"type": "function", "function": {"name": "A", "description": "d", "parameters": {"type": "object", "properties": {}}}}
    ]


class _FakeFn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeFn(name, arguments)


def test_execute_tool_call_unknown_tool_returns_error_dict():
    result = execute_tool_call(_FakeToolCall("nope", "{}"), {})
    assert result == {"tool": "nope", "status": None, "args": {}, "error": "unknown tool"}


def test_execute_tool_call_bad_json_args_defaults_to_empty(monkeypatch):
    import app.graph.tool_schemas as ts
    monkeypatch.setattr(ts, "rest_invoke", lambda config, args: {"status": 200, "body": "ok"})
    result = execute_tool_call(_FakeToolCall("A", "not json"), {"A": {"url": "https://x", "method": "GET", "headers": {}}})
    assert result["args"] == {}
    assert result["status"] == 200
    assert result["body"] == "ok"


def test_execute_tool_call_truncates_body(monkeypatch):
    import app.graph.tool_schemas as ts
    monkeypatch.setattr(ts, "rest_invoke", lambda config, args: {"status": 200, "body": "x" * 5000})
    result = execute_tool_call(_FakeToolCall("A", "{}"), {"A": {"url": "https://x", "method": "GET", "headers": {}}})
    assert len(result["body"]) == 2000


def test_execute_tool_call_catches_tool_config_error(monkeypatch):
    import app.graph.tool_schemas as ts

    def boom(config, args):
        raise ts.ToolConfigError("blocked private address")

    monkeypatch.setattr(ts, "rest_invoke", boom)
    result = execute_tool_call(_FakeToolCall("A", "{}"), {"A": {"url": "https://x", "method": "GET", "headers": {}}})
    assert result["status"] is None
    assert "blocked" in result["error"]
