"""Conversation-history compression (Phase 3, Token Optimization).

runs.py replays every prior run as user/assistant messages. Past a token
budget, this folds all but the last few turns into one LLM summary,
computed once per growth step and cached on the conversation row."""

from collections.abc import Callable

from app.config import settings
from app.memory import history_to_messages

HISTORY_TOKEN_BUDGET = settings.history_token_budget
HISTORY_KEEP_TURNS = settings.history_keep_turns

_SUMMARY_PREFIX = "Conversation so far:\n"


def estimate_tokens(messages: list[dict]) -> int:
    """4-chars-per-token heuristic — no tokenizer dependency."""
    return sum(len(m["content"] or "") for m in messages) // 4


def prepare_history(
    prior_runs: list[dict],
    *,
    stored_summary: str | None,
    summary_through_run_id: str | None,
    summarize: Callable[[list[dict]], str],
) -> tuple[list[dict], dict | None]:
    """Return (messages, compression). `compression` is None when the full
    history fits the budget (or there is too little to compress); otherwise
    it is the payload for a `history_compressed` run event.

    `summarize(older_runs) -> str` is injected so this stays pure/testable;
    runs.py passes a MODEL_CHEAP `generate` call."""
    # A blocked / failed / still-running prior run has output=None and is not
    # useful conversation history — drop it before replaying or summarizing.
    prior_runs = [r for r in prior_runs if r.get("output")]

    full = history_to_messages(prior_runs)
    if estimate_tokens(full) <= HISTORY_TOKEN_BUDGET:
        return full, None

    older = prior_runs[:-HISTORY_KEEP_TURNS]
    recent = prior_runs[-HISTORY_KEEP_TURNS:]
    if not older:
        # everything is within the keep window — nothing we can fold away
        return full, None

    through_id = older[-1]["id"]
    if stored_summary and summary_through_run_id == through_id:
        summary, reused = stored_summary, True
    else:
        summary, reused = summarize(older), False

    messages = [{"role": "system", "content": _SUMMARY_PREFIX + summary}] + history_to_messages(recent)
    compression = {
        "summary": summary,
        "summary_through_run_id": through_id,
        "runs_summarized": len(older),
        "tokens_before": estimate_tokens(full),
        "tokens_after": estimate_tokens(messages),
        "summary_reused": reused,
    }
    return messages, compression
