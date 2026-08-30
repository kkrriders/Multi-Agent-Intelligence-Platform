"""Alerting / error budgets (Phase 3, SP3). A few per-project rule rows are
evaluated synchronously after each run settles; a breach writes an
alert_events row and optionally fires a webhook. Fail-open — an alerting
error never fails the run."""

import logging
import math
from datetime import date, datetime, timezone

import httpx

logger = logging.getLogger(__name__)

ALERT_KINDS = ("error_rate", "daily_spend", "p95_latency")
WEBHOOK_TIMEOUT_S = 2.0
RUN_LOOKBACK = 500  # ponytail: widen if a project does >500 runs/day (daily_spend window)


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def error_rate(runs: list[dict]) -> float:
    if not runs:
        return 0.0
    bad = sum(1 for r in runs if r.get("status") in ("failed", "blocked"))
    return bad / len(runs)


def daily_spend(runs: list[dict], today: date) -> float:
    key = today.isoformat()
    return round(sum(float(r["cost_usd"] or 0) for r in runs if r["created_at"][:10] == key), 6)


def p95_latency_ms(events_by_run: dict[str, list[dict]]) -> float:
    """Per-run latency = last event ts - first event ts. Nearest-rank p95
    over runs with >= 2 events."""
    spans = []
    for evs in events_by_run.values():
        if len(evs) < 2:
            continue
        ts = sorted(_ts(e["created_at"]) for e in evs)
        spans.append((ts[-1] - ts[0]).total_seconds() * 1000)
    if not spans:
        return 0.0
    spans.sort()
    idx = max(0, math.ceil(0.95 * len(spans)) - 1)
    return round(spans[idx], 1)


def observed_for(kind: str, runs: list[dict], events_by_run: dict[str, list[dict]], today: date) -> float:
    if kind == "error_rate":
        return error_rate(runs)
    if kind == "daily_spend":
        return daily_spend(runs, today)
    if kind == "p95_latency":
        return p95_latency_ms(events_by_run)
    raise ValueError(f"unknown alert kind: {kind}")


def evaluate_project_alerts(client, project_id: str, *, today: date | None = None) -> None:
    """Fetch the project's enabled rules, compute each observed value, write an
    alert_events row + fire the webhook for any breach. Never raises."""
    today = today or datetime.now(timezone.utc).date()
    try:
        rules = (
            client.table("alert_rules")
            .select("*")
            .eq("project_id", project_id)
            .eq("enabled", True)
            .execute()
            .data
        )
        if not rules:
            return

        runs = (
            client.table("runs")
            .select("id, status, created_at, cost_usd")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(RUN_LOOKBACK)
            .execute()
            .data
        )

        events_by_run: dict[str, list[dict]] = {}
        if any(r["kind"] == "p95_latency" for r in rules):
            window = max(r["window_n"] for r in rules if r["kind"] == "p95_latency")
            ids = [r["id"] for r in runs[:window]]
            if ids:
                evs = (
                    client.table("run_events")
                    .select("run_id, created_at")
                    .in_("run_id", ids)
                    .execute()
                    .data
                )
                for e in evs:
                    events_by_run.setdefault(e["run_id"], []).append(e)

        for rule in rules:
            kind = rule["kind"]
            subset = runs if kind == "daily_spend" else runs[: rule["window_n"]]
            observed = observed_for(kind, subset, events_by_run, today)
            if observed <= float(rule["threshold"]):
                continue
            _record_breach(client, project_id, rule, observed)
    except Exception:  # noqa: BLE001 - alerting is fail-open
        logger.warning("alert evaluation failed for project %s", project_id, exc_info=True)


def record_rate_limit_event(client, project_id: str, limit: int) -> None:
    """A throttled run never becomes a run row; log it as an alert_events row
    so the Settings panel shows throttling history. Never raises."""
    try:
        client.table("alert_events").insert(
            {
                "project_id": project_id,
                "kind": "rate_limit",
                "observed": limit,
                "threshold": limit,
                "detail": {"limit": limit, "window_s": 60},
            }
        ).execute()
    except Exception:  # noqa: BLE001
        logger.warning("could not record rate_limit event for project %s", project_id, exc_info=True)


def _record_breach(client, project_id: str, rule: dict, observed: float) -> None:
    client.table("alert_events").insert(
        {
            "project_id": project_id,
            "rule_id": rule["id"],
            "kind": rule["kind"],
            "observed": round(observed, 6),
            "threshold": rule["threshold"],
            "detail": {"window_n": rule["window_n"]},
        }
    ).execute()
    url = rule.get("webhook_url")
    if url:
        try:
            httpx.post(
                url,
                json={
                    "project_id": project_id,
                    "kind": rule["kind"],
                    "observed": observed,
                    "threshold": rule["threshold"],
                },
                timeout=WEBHOOK_TIMEOUT_S,
            )
        except Exception:  # noqa: BLE001 - fire-and-forget
            logger.info("alert webhook to %s failed", url, exc_info=True)
