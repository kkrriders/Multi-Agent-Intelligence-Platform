"""Agent performance report — groundedness/hallucination rate and tool-call
success rate, aggregated from existing run_events (no new instrumentation):

- verifier_check events (graph/workers.py verifier_node) already carry a real
  LLM-judged {"supported": bool, "note": str} verdict per run.
- tool_called events (graph/workers.py tool_runner_node) already carry
  {"tool": ..., "status": ...} per call.

Needs the local Postgres (DATABASE_URL) — see benchmarks/_platform_data.py.

Deliberately does NOT report a "task success rate": no ground-truth label for
what a task should accomplish exists outside the offline 20-item golden
dataset in evals.py, which isn't wired to real traffic. Approximating it with
the groundedness verdict would conflate "the answer is supported by context"
with "the agent did what the user asked" — those are different claims.

    python benchmarks/agent_performance_report.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from _platform_data import load  # noqa: E402


def main() -> int:
    data = load()
    events = data["events"]

    verifier_events = [e for e in events if e["step_name"] == "verifier_check"]
    tool_events = [e for e in events if e["step_name"] == "tool_called"]
    turn_events = [e for e in events if "turn" in (e.get("payload") or {})]

    print("AI Engineering Platform — Agent Performance Report")
    print("=" * 60)

    if verifier_events:
        supported = sum(1 for e in verifier_events if e["payload"].get("supported"))
        print(f"groundedness rate:  {supported}/{len(verifier_events)} "
              f"({supported / len(verifier_events):.1%})")
        print(f"hallucination rate: {len(verifier_events) - supported}/{len(verifier_events)} "
              f"({1 - supported / len(verifier_events):.1%})")
    else:
        print("groundedness/hallucination rate: no verifier_check events found "
              "(no run traffic recorded for this account yet)")

    if tool_events:
        statuses = Counter(e["payload"].get("status") for e in tool_events)
        success = statuses.get("ok", 0) + statuses.get("success", 0)
        print(f"\ntool-call success rate: {success}/{len(tool_events)} "
              f"({success / len(tool_events):.1%})")
        print(f"  status breakdown: {dict(statuses)}")
    else:
        print("\ntool-call success rate: no tool_called events found")

    if turn_events:
        max_turn_by_run: dict[str, int] = {}
        for e in turn_events:
            run_id = e["run_id"]
            turn = e["payload"]["turn"]
            max_turn_by_run[run_id] = max(max_turn_by_run.get(run_id, 0), turn)
        turns = list(max_turn_by_run.values())
        print(f"\navg turns/run: {sum(turns) / len(turns):.2f}  "
              f"(n={len(turns)} runs, max observed={max(turns)})")
    else:
        print("\nturn count: no turn-labeled events found")

    print(
        "\nTASK SUCCESS RATE: not measured here — no ground-truth label exists for "
        "what a real task should accomplish outside the offline 20-item golden "
        "dataset (evals.py), which isn't wired to live traffic. Groundedness is a "
        "different claim (the answer is supported by retrieved context) and is not "
        "substituted for it above."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
