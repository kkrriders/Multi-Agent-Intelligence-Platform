"""Cost Analytics (Phase 3, SP2) — pure aggregation over the runs +
run_llm_calls rows written by Token Optimization. No storage of its own."""

from collections import defaultdict
from datetime import date, timedelta

DAILY_WINDOW = 30
RECENT_LIMIT = 50


def _num(x) -> float:
    return float(x) if x is not None else 0.0


def _run_date(row: dict) -> str:
    return row["created_at"][:10]


def aggregate_cost(runs: list[dict], llm_calls: list[dict], today: date) -> dict:
    cached = [r for r in runs if r.get("cache_hit")]
    noncached_costs = [
        _num(r["cost_usd"])
        for r in runs
        if not r.get("cache_hit") and r.get("status") == "completed" and _num(r["cost_usd"]) > 0
    ]
    mean_noncached = sum(noncached_costs) / len(noncached_costs) if noncached_costs else 0.0

    totals = {
        "run_count": len(runs),
        "cached_run_count": len(cached),
        "prompt_tokens": sum(int(_num(r["prompt_tokens"])) for r in runs),
        "completion_tokens": sum(int(_num(r["completion_tokens"])) for r in runs),
        "cost_usd": round(sum(_num(r["cost_usd"]) for r in runs), 6),
        "runs_missing_cost": sum(1 for r in runs if r.get("cost_usd") is None),
        "estimated_cache_savings_usd": round(mean_noncached * len(cached), 6),
    }

    by_model_acc: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    )
    models_by_run: dict[str, list[str]] = defaultdict(list)
    for c in llm_calls:
        m = by_model_acc[c["model"]]
        m["calls"] += 1
        m["prompt_tokens"] += int(_num(c["prompt_tokens"]))
        m["completion_tokens"] += int(_num(c["completion_tokens"]))
        m["cost_usd"] = round(m["cost_usd"] + _num(c["cost_usd"]), 6)
        if c["model"] not in models_by_run[c["run_id"]]:
            models_by_run[c["run_id"]].append(c["model"])
    by_model = [{"model": k, **v} for k, v in sorted(by_model_acc.items())]

    day_acc: dict[str, dict] = defaultdict(lambda: {"run_count": 0, "cost_usd": 0.0, "cached_run_count": 0})
    for r in runs:
        d = day_acc[_run_date(r)]
        d["run_count"] += 1
        d["cost_usd"] = round(d["cost_usd"] + _num(r["cost_usd"]), 6)
        if r.get("cache_hit"):
            d["cached_run_count"] += 1
    daily = []
    for i in range(DAILY_WINDOW - 1, -1, -1):
        key = (today - timedelta(days=i)).isoformat()
        daily.append({"date": key, **day_acc.get(key, {"run_count": 0, "cost_usd": 0.0, "cached_run_count": 0})})

    recent = sorted(runs, key=lambda r: r["created_at"], reverse=True)[:RECENT_LIMIT]
    recent_runs = [
        {
            "id": r["id"],
            "created_at": r["created_at"],
            "status": r["status"],
            "cache_hit": bool(r.get("cache_hit")),
            "prompt_tokens": int(_num(r["prompt_tokens"])),
            "completion_tokens": int(_num(r["completion_tokens"])),
            "cost_usd": _num(r["cost_usd"]),
            "models": models_by_run.get(r["id"], []),
        }
        for r in recent
    ]

    return {"totals": totals, "by_model": by_model, "daily": daily, "recent_runs": recent_runs}
