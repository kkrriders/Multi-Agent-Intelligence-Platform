import json
import re

import httpx

from app.tools.rest_adapter import ToolConfigError
from app.tools.rest_adapter import invoke as rest_invoke

MAX_TOOL_BODY_CHARS = 2000

_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _slug(name: str) -> str:
    return _NAME_RE.sub("_", name)[:64]


def sanitize_tools(rows: list[dict]) -> tuple[list[dict], dict]:
    """Turn `tools` table rows into (tool_specs, tool_configs).

    Only `rest` tools whose method is GET (or unset) are kept — an autonomous
    loop must not POST/PUT/DELETE. `tool_specs` is model-facing (name,
    description, JSON-schema params); `tool_configs` holds the real URL and
    headers, keyed by slug, and never enters graph state or event payloads.
    """
    specs: list[dict] = []
    configs: dict = {}
    for row in rows:
        if row.get("type") != "rest":
            continue
        config = row.get("config") or {}
        method = (config.get("method") or "GET").upper()
        if method != "GET":
            continue
        name = _slug(row["name"])
        specs.append(
            {
                "name": name,
                "description": row.get("description") or f"Call the {row['name']} REST tool",
                "parameters": config.get("parameters") or {"type": "object", "properties": {}},
            }
        )
        configs[name] = {"url": config["url"], "method": "GET", "headers": config.get("headers", {})}
    return specs, configs


def build_tool_schemas(tool_specs: list[dict]) -> list[dict]:
    return [{"type": "function", "function": spec} for spec in tool_specs]


def execute_tool_call(tool_call, tool_configs: dict) -> dict:
    """Run one Groq tool_call via the REST adapter. Never raises — returns an
    event-safe result dict with keys {tool, status, args, body?, error?}."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError:
        args = {}

    config = tool_configs.get(name)
    if config is None:
        return {"tool": name, "status": None, "args": args, "error": "unknown tool"}

    try:
        result = rest_invoke(config, args)
        return {"tool": name, "status": result["status"], "args": args, "body": result["body"][:MAX_TOOL_BODY_CHARS]}
    except ToolConfigError as exc:
        return {"tool": name, "status": None, "args": args, "error": str(exc)}
    except (httpx.RequestError, KeyError) as exc:
        return {"tool": name, "status": None, "args": args, "error": f"request failed: {exc}"}
