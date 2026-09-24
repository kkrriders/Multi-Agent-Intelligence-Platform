"""Cost / token efficiency report — aggregates existing runs + run_llm_calls
data via app.analytics.aggregate_cost (no new instrumentation).

Needs the local Postgres (DATABASE_URL) — see benchmarks/_platform_data.py.

    python benchmarks/cost_report.py
    python benchmarks/cost_report.py --json out.json
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.analytics import aggregate_cost  # noqa: E402

from _platform_data import load  # noqa: E402


def build_report() -> dict:
    data = load()
    runs, calls = data["runs"], data["calls"]
    today = datetime.now(timezone.utc).date()
    agg = aggregate_cost(runs, calls, today)

    completed = [r for r in runs if r.get("status") == "completed"]
    n_completed = len(completed) or 1
    n_runs = len(runs) or 1
    totals = agg["totals"]

    return {
        **agg,
        "derived": {
            "tokens_per_request": round(
                (totals["prompt_tokens"] + totals["completion_tokens"]) / n_runs, 1
            ),
            "cost_per_request_usd": round(totals["cost_usd"] / n_runs, 6),
            "cost_per_successful_task_usd": round(totals["cost_usd"] / n_completed, 6),
            "cache_hit_rate": round(totals["cached_run_count"] / n_runs, 3),
        },
        "caveat": (
            "Numbers are aggregated from whatever real traffic this test account has "
            "produced (manual/chaos-harness runs), not a controlled baseline-vs-optimized "
            "A/B experiment (cache on/off, cheap-model routing on/off). Treat as a real "
            "current snapshot, not yet a measured improvement claim."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    report = build_report()
    t, d = report["totals"], report["derived"]
    print("AI Engineering Platform — Cost / Token Report")
    print("=" * 60)
    print(f"runs: {t['run_count']}  (cached: {t['cached_run_count']}, "
          f"missing cost: {t['runs_missing_cost']})")
    print(f"tokens/request:            {d['tokens_per_request']}")
    print(f"cost/request:              ${d['cost_per_request_usd']}")
    print(f"cost/successful task:      ${d['cost_per_successful_task_usd']}")
    print(f"cache hit rate:            {d['cache_hit_rate']:.1%}")
    print(f"estimated cache savings:   ${t['estimated_cache_savings_usd']}")
    print("\nby model:")
    for m in report["by_model"]:
        print(f"  {m['model']:<24} calls={m['calls']:<4} cost=${m['cost_usd']}")
    print(f"\n{report['caveat']}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
        print(f"\nreport -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
