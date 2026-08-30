import app.history as history
from app.history import estimate_tokens, prepare_history


def _runs(n, *, size=20):
    return [{"id": f"r{i}", "input": "q" * size, "output": "a" * size} for i in range(n)]


def test_estimate_tokens_is_chars_over_four():
    assert estimate_tokens([{"content": "a" * 40}]) == 10


def test_estimate_tokens_tolerates_none_content():
    # a blocked/failed prior run has output=None -> history_to_messages yields
    # a message with content None; must not crash.
    assert estimate_tokens([{"content": None}, {"content": "abcd"}]) == 1


def test_prepare_history_skips_runs_with_no_output(monkeypatch):
    monkeypatch.setattr(history, "HISTORY_TOKEN_BUDGET", 10_000)
    runs = [
        {"id": "r0", "input": "hi", "output": "hello"},
        {"id": "r1", "input": "blocked one", "output": None},
        {"id": "r2", "input": "ok", "output": "sure"},
    ]
    msgs, compression = prepare_history(
        runs, stored_summary=None, summary_through_run_id=None, summarize=lambda o: "S"
    )
    assert compression is None
    # r1 (no answer) contributes nothing; 2 usable runs -> 4 messages
    assert len(msgs) == 4
    assert all(m["content"] for m in msgs)


def test_estimate_tokens_monotonic():
    one = estimate_tokens([{"content": "a" * 40}])
    two = estimate_tokens([{"content": "a" * 40}, {"content": "a" * 40}])
    assert two > one


def test_under_budget_returns_full_history_untouched(monkeypatch):
    monkeypatch.setattr(history, "HISTORY_TOKEN_BUDGET", 10_000)
    calls = []
    msgs, compression = prepare_history(
        _runs(5), stored_summary=None, summary_through_run_id=None,
        summarize=lambda older: calls.append(older) or "SUM",
    )
    assert compression is None
    assert len(msgs) == 10  # 5 runs -> 5 user + 5 assistant
    assert calls == []


def test_over_budget_summarizes_older_and_keeps_recent(monkeypatch):
    monkeypatch.setattr(history, "HISTORY_TOKEN_BUDGET", 10)
    monkeypatch.setattr(history, "HISTORY_KEEP_TURNS", 3)
    calls = []
    msgs, compression = prepare_history(
        _runs(8), stored_summary=None, summary_through_run_id=None,
        summarize=lambda older: (calls.append([r["id"] for r in older]), "SUMMARY")[1],
    )
    assert calls == [["r0", "r1", "r2", "r3", "r4"]]
    assert msgs[0] == {"role": "system", "content": "Conversation so far:\nSUMMARY"}
    assert len(msgs) == 1 + 2 * 3
    assert compression["runs_summarized"] == 5
    assert compression["summary_through_run_id"] == "r4"
    assert compression["summary_reused"] is False
    assert compression["tokens_before"] > compression["tokens_after"]


def test_stored_summary_is_reused_without_calling_summarize(monkeypatch):
    monkeypatch.setattr(history, "HISTORY_TOKEN_BUDGET", 10)
    monkeypatch.setattr(history, "HISTORY_KEEP_TURNS", 3)
    calls = []
    msgs, compression = prepare_history(
        _runs(8), stored_summary="OLD SUMMARY", summary_through_run_id="r4",
        summarize=lambda older: calls.append(older) or "NEW",
    )
    assert calls == []
    assert compression["summary_reused"] is True
    assert msgs[0]["content"] == "Conversation so far:\nOLD SUMMARY"


def test_over_budget_but_too_few_runs_to_keep_returns_full(monkeypatch):
    monkeypatch.setattr(history, "HISTORY_TOKEN_BUDGET", 1)
    monkeypatch.setattr(history, "HISTORY_KEEP_TURNS", 3)
    msgs, compression = prepare_history(
        _runs(2), stored_summary=None, summary_through_run_id=None,
        summarize=lambda older: "SHOULD NOT BE CALLED",
    )
    assert compression is None
    assert len(msgs) == 4
