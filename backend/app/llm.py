from contextvars import ContextVar

from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

MODEL = "openai/gpt-oss-120b"
MODEL_CHEAP = "openai/gpt-oss-20b"

# Per-request usage accumulator. generate() appends one entry per call;
# runs.py drains it after the graph stream to write run_llm_calls + run
# totals. Outside a run it is simply never drained. contextvar (not an
# arg threaded through 8 call sites) is deliberate — see the Phase 3
# overview spec.
# default None (not []) — a mutable ContextVar default is shared across
# contexts. None means "no active run"; generate() then drops usage instead
# of accumulating into a shared list.
_usage_log: ContextVar[list[dict] | None] = ContextVar("_usage_log", default=None)
_current_node: ContextVar[str] = ContextVar("_current_node", default="llm")


def reset_usage() -> None:
    _usage_log.set([])
    _current_node.set("llm")


def drain_usage() -> list[dict]:
    entries = _usage_log.get() or []
    _usage_log.set([])
    return entries


def set_node(name: str) -> None:
    _current_node.set(name)


def generate(
    messages: list[dict],
    *,
    tools: list[dict] | None = None,
    response_format: dict | None = None,
    model: str = MODEL,
):
    # Groq rejects tool_choice / response_format when passed as None — only
    # include a kwarg when it actually has a value.
    kwargs: dict = {"model": model, "messages": messages, "timeout": 30}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = _client.chat.completions.create(**kwargs)

    usage = getattr(response, "usage", None)
    log = _usage_log.get()
    if usage is not None and log is not None:
        log.append(
            {
                "model": model,
                "node": _current_node.get(),
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
            }
        )

    message = response.choices[0].message
    return message if tools else message.content
