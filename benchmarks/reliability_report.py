"""Reliability report — request/dependency/LLM-gateway error rates.

Two data sources, both already existing, no new instrumentation:
- app.alerts.error_rate / daily_spend (over Supabase `runs` rows) — needs
  SUPABASE_TEST_USER_TOKEN, see benchmarks/_platform_data.py.
- service_dependency_failures_total / llm_gateway_errors_total Prometheus
  counters, scraped directly from the running backend's /metrics (no auth).

    python benchmarks/reliability_report.py
    python benchmarks/reliability_report.py --metrics-url http://localhost:8010/metrics
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.alerts import daily_spend, error_rate  # noqa: E402

from _platform_data import load  # noqa: E402

_COUNTER_LINE = re.compile(r'^(\w+)\{([^}]*)\}\s+([\d.eE+-]+)\s*$')


def _parse_labels(label_str: str) -> dict:
    labels = {}
    for part in label_str.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        labels[k.strip()] = v.strip().strip('"')
    return labels


def scrape_counters(metrics_url: str, names: tuple[str, ...]) -> dict[str, list[dict]]:
    """Minimal Prometheus text-exposition parser — no server-side Prometheus
    runs for this stack (confirmed: docker-compose.yml has no prometheus
    service), so read the counters straight off /metrics instead of PromQL."""
    resp = httpx.get(metrics_url, timeout=10, follow_redirects=True)
    resp.raise_for_status()
    out: dict[str, list[dict]] = defaultdict(list)
    for line in resp.text.splitlines():
        if line.startswith("#"):
            continue
        m = _COUNTER_LINE.match(line)
        if not m:
            continue
        name, label_str, value = m.groups()
        if name in names:
            out[name].append({"labels": _parse_labels(label_str), "value": float(value)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics-url", default="http://localhost:8010/metrics")
    args = ap.parse_args()

    print("AI Engineering Platform — Reliability Report")
    print("=" * 60)
    try:
        runs = load()["runs"]
        today = datetime.now(timezone.utc).date()
        print(f"runs analyzed: {len(runs)}")
        print(f"request error rate (failed+blocked / total): {error_rate(runs):.3%}")
        print(f"spend today: ${daily_spend(runs, today)}")
    except SystemExit as exc:
        print(f"request-level error rate / spend: SKIPPED — {exc}")

    try:
        counters = scrape_counters(
            args.metrics_url,
            ("service_dependency_failures_total", "llm_gateway_errors_total", "http_requests_total"),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\nPrometheus /metrics unreachable at {args.metrics_url}: {exc}")
        print("(dependency-failure / gateway-error breakdown skipped)")
        return 0

    reqs = counters.get("http_requests_total", [])
    total_reqs = sum(r["value"] for r in reqs)
    error_reqs = sum(r["value"] for r in reqs if r["labels"].get("status") not in (None, "200"))
    print(f"\nhttp_requests_total (all graph-node executions): {total_reqs:.0f}")
    print(f"  5xx/error rate: {error_reqs / total_reqs:.3%}" if total_reqs else "  (no requests recorded yet)")

    deps = counters.get("service_dependency_failures_total", [])
    print(f"\nservice_dependency_failures_total: {sum(d['value'] for d in deps):.0f} total")
    for d in sorted(deps, key=lambda x: -x["value"])[:10]:
        print(f"  {d['labels']}: {d['value']:.0f}")
    if not deps:
        print("  (zero — no dependency failures observed on this /metrics snapshot)")

    gw = counters.get("llm_gateway_errors_total", [])
    print(f"\nllm_gateway_errors_total: {sum(g['value'] for g in gw):.0f} total")
    for g in sorted(gw, key=lambda x: -x["value"])[:10]:
        print(f"  {g['labels']}: {g['value']:.0f}")
    if not gw:
        print("  (zero — no gateway errors observed on this /metrics snapshot)")

    print(
        "\nNote: /metrics is a live in-process counter snapshot, not a time-series "
        "database — it only reflects activity since the backend container last "
        "restarted, and this stack runs no local Prometheus to query historical rates."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
