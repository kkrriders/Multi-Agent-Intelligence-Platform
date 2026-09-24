"""Latency report — per-node p50/p95/p99 from the existing
http_request_duration_seconds Histogram (metrics.py, populated by
instrument_node for every graph-node execution), plus an approximate
pipeline-stage breakdown (guardrails / prompt / memory / retrieval) computed
from existing run_events + guardrail_events timestamps.

No local Prometheus server runs for this stack (confirmed: docker-compose.yml
has no prometheus service — AIRRA scrapes /metrics remotely over airra-mesh),
so quantiles are computed here directly from one /metrics text-exposition
snapshot rather than via PromQL histogram_quantile().

Per-node p50/p95/p99 needs no auth. The stage breakdown needs
a reachable Postgres (DATABASE_URL; see benchmarks/_platform_data.py) and is skipped,
not faked, if that isn't set.

    python benchmarks/latency_report.py
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

_BUCKET_LINE = re.compile(r'^http_request_duration_seconds_bucket\{([^}]*)\}\s+([\d.eE+-]+)\s*$')


def _parse_labels(label_str: str) -> dict:
    labels = {}
    for part in label_str.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        labels[k.strip()] = v.strip().strip('"')
    return labels


def fetch_node_quantiles(metrics_url: str) -> dict[str, dict]:
    resp = httpx.get(metrics_url, timeout=10, follow_redirects=True)
    resp.raise_for_status()

    buckets_by_service: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for line in resp.text.splitlines():
        m = _BUCKET_LINE.match(line)
        if not m:
            continue
        labels = _parse_labels(m.group(1))
        service = labels.get("service", "unknown")
        le = labels["le"]
        le_f = float("inf") if le == "+Inf" else float(le)
        buckets_by_service[service].append((le_f, float(m.group(2))))

    out = {}
    for service, buckets in buckets_by_service.items():
        buckets.sort(key=lambda b: b[0])
        total = buckets[-1][1] if buckets else 0
        if total == 0:
            out[service] = {"count": 0, "p50": None, "p95": None, "p99": None}
            continue
        out[service] = {"count": int(total)}
        for q in (0.50, 0.95, 0.99):
            target = q * total
            prev_le, prev_cum = 0.0, 0.0
            quantile = None
            for le, cum in buckets:
                if cum >= target:
                    # linear interpolation within the bucket (standard
                    # histogram_quantile approximation for a bounded bucket)
                    if le == float("inf") or cum == prev_cum:
                        quantile = le if le != float("inf") else prev_le
                    else:
                        frac = (target - prev_cum) / (cum - prev_cum)
                        quantile = prev_le + frac * (le - prev_le)
                    break
                prev_le, prev_cum = le, cum
            out[service][f"p{int(q * 100)}"] = round(quantile, 4) if quantile is not None else None
    return out


def stage_latency_from_events() -> dict | None:
    try:
        from _platform_data import load
    except SystemExit:
        return None
    try:
        data = load()
    except SystemExit:
        return None

    by_run: dict[str, list[dict]] = defaultdict(list)
    for e in data["events"]:
        by_run[e["run_id"]].append({"step": e["step_name"], "at": e["created_at"]})
    for g in data["guardrails"]:
        by_run[g["run_id"]].append({"step": f"guardrail_{g['phase']}", "at": g["created_at"]})

    stage_deltas: dict[str, list[float]] = defaultdict(list)
    for run_id, events in by_run.items():
        events.sort(key=lambda e: e["at"])
        if len(events) < 2:
            continue
        t0 = datetime.fromisoformat(events[0]["at"].replace("Z", "+00:00"))
        prev_t, prev_step = t0, events[0]["step"]
        for e in events[1:]:
            t = datetime.fromisoformat(e["at"].replace("Z", "+00:00"))
            stage_deltas[f"{prev_step} -> {e['step']}"].append((t - prev_t).total_seconds() * 1000)
            prev_t, prev_step = t, e["step"]

    if not stage_deltas:
        return None
    return {
        transition: {"n": len(ms), "mean_ms": round(sum(ms) / len(ms), 1)}
        for transition, ms in sorted(stage_deltas.items(), key=lambda kv: -len(kv[1]))
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics-url", default="http://localhost:8010/metrics")
    args = ap.parse_args()

    print("AI Engineering Platform — Latency Report")
    print("=" * 60)
    print("PER-NODE (Prometheus http_request_duration_seconds, this /metrics snapshot)")
    try:
        node_stats = fetch_node_quantiles(args.metrics_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  /metrics unreachable at {args.metrics_url}: {exc}")
        node_stats = {}
    for service, s in sorted(node_stats.items()):
        if s["count"] == 0:
            print(f"  {service:<14} no requests recorded yet")
            continue
        print(f"  {service:<14} n={s['count']:<5} p50={s['p50']*1000:.1f}ms  "
              f"p95={s['p95']*1000:.1f}ms  p99={s['p99']*1000:.1f}ms")

    print("\nPIPELINE-STAGE BREAKDOWN (derived from run_events/guardrail_events timestamps,")
    print("approximate — includes DB round-trip time between steps, not pure compute)")
    stages = stage_latency_from_events()
    if stages is None:
        print("  SKIPPED — Postgres not reachable or no run data. Not faked.")
    else:
        for transition, s in stages.items():
            print(f"  {transition:<45} n={s['n']:<4} mean={s['mean_ms']}ms")

    print(
        "\nNote: guardrails/prompt/memory/retrieval do not have their own dedicated "
        "server-side timing metric — the pipeline-stage numbers above are inferred "
        "from event timestamps, which is honest but coarser than a purpose-built span "
        "per stage (that's the Phase-2 instrumentation gap, not fixed here)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
