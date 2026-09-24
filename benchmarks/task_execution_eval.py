"""Real-traffic task-execution eval — the metric agent_performance_report.py
documents as missing: "no ground-truth label for what a task should
accomplish exists outside the offline 20-item golden dataset in evals.py,
which isn't wired to real traffic." This drives the same judge_item()/
aggregate() grading the offline eval uses, but over real POST /runs calls
through the live orchestrator (guardrails -> graph -> persistence), so
task success is measured against actual production-path behavior.

Auth: logs in through the backend's POST /auth/login (signing up on first
use) with a fixed test-fixture account.

Needs the platform backend reachable (default http://localhost:8010) and
GROQ_API_KEY/DATABASE_URL/JWT_SECRET loadable from the repo-root .env (same
as every other backend/app import already assumes).

    python benchmarks/task_execution_eval.py
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.evals import PASS_THRESHOLD, aggregate, judge_item  # noqa: E402

from _task_suite import TASKS, TOOL_NAME, TOOL_URL  # noqa: E402

PLATFORM_URL = "http://localhost:8010"
EMAIL = "taskeval@local.dev"
PASSWORD = "hunter2-hunter2"
PROJECT_NAME = "engineer-task-eval"
DELAY_SEC = 4  # settings.run_rate_limit_per_min defaults to 20/min


def sign_in() -> str:
    body = {"email": EMAIL, "password": PASSWORD}
    resp = requests.post(f"{PLATFORM_URL}/auth/login", json=body)
    if resp.status_code >= 400:
        requests.post(f"{PLATFORM_URL}/auth/signup", json=body)
        resp = requests.post(f"{PLATFORM_URL}/auth/login", json=body)
        resp.raise_for_status()
    return resp.json()["access_token"]


def get_or_create_project(auth: dict, name: str = PROJECT_NAME) -> str:
    existing = requests.get(f"{PLATFORM_URL}/projects", headers=auth).json()
    for p in existing:
        if p["name"] == name:
            return p["id"]
    created = requests.post(f"{PLATFORM_URL}/projects", json={"name": name}, headers=auth)
    created.raise_for_status()
    return created.json()["id"]


def ensure_tool(auth: dict, project_id: str) -> None:
    tools = requests.get(f"{PLATFORM_URL}/projects/{project_id}/tools", headers=auth).json()
    if any(t["name"] == TOOL_NAME for t in tools):
        return
    body = {"name": TOOL_NAME, "type": "rest", "config": {"url": TOOL_URL, "method": "GET"}, "permissions": {}}
    requests.post(f"{PLATFORM_URL}/projects/{project_id}/tools", json=body, headers=auth).raise_for_status()


def ensure_guardrail_policies(auth: dict, project_id: str) -> None:
    for kind, config in (
        ("input_constraint", {"max_length": 300, "blocklist": ["forbidden_test_term"]}),
    ):
        requests.put(
            f"{PLATFORM_URL}/projects/{project_id}/guardrail-policies/{kind}",
            json={"enabled": True, "config": config},
            headers=auth,
        ).raise_for_status()


def new_conversation(auth: dict, project_id: str) -> str:
    resp = requests.post(f"{PLATFORM_URL}/projects/{project_id}/conversations", json={}, headers=auth)
    resp.raise_for_status()
    return resp.json()["id"]


def run_task(auth: dict, project_id: str, task: dict) -> dict:
    conv_id = new_conversation(auth, project_id)
    t0 = time.monotonic()
    resp = requests.post(
        f"{PLATFORM_URL}/conversations/{conv_id}/runs",
        json={"input": task["input"]},
        headers=auth,
        timeout=60,
    )
    latency_sec = round(time.monotonic() - t0, 2)

    record = {"id": task["id"], "category": task["category"], "mode": task["mode"], "latency_sec": latency_sec}

    if task["mode"] == "expect_block":
        record["success"] = resp.status_code == 422
        record["detail"] = resp.json().get("detail") if resp.status_code == 422 else f"HTTP {resp.status_code}"
        return record

    if resp.status_code != 200:
        record["success"] = False
        record["detail"] = f"unexpected HTTP {resp.status_code}: {resp.text[:200]}"
        return record

    run = resp.json()
    record["cost_usd"] = run.get("cost_usd")
    output = run.get("output") or ""

    if task["mode"] == "expect_pii_mask":
        record["success"] = "[REDACTED:" in output
        record["detail"] = output[:200]
        return record

    # mode == "judge"
    verdict = judge_item(task["input"], task["expected"], output)
    record.update(verdict)
    record["success"] = verdict["score"] >= PASS_THRESHOLD
    if task["category"] == "tool_use":
        record["tool_called"] = any(e["step_name"] == "tool_called" for e in run.get("events", []))
    return record


def print_report(records: list[dict]) -> None:
    print("AI Engineering Platform — Task Execution Eval")
    print("=" * 60)
    categories = sorted({r["category"] for r in records})
    for cat in categories:
        rows = [r for r in records if r["category"] == cat]
        n = len(rows)
        success = sum(1 for r in rows if r["success"])
        latencies = [r["latency_sec"] for r in rows]
        print(f"\n[{cat}] {success}/{n} succeeded ({success / n:.0%})  "
              f"mean latency {sum(latencies) / n:.1f}s")
        judged = [r for r in rows if "score" in r]
        if judged:
            agg = aggregate(judged)
            print(f"  mean_score={agg['mean_score']:.2f}  hallucination_rate={agg['hallucination_rate']:.0%}")
        if cat == "tool_use":
            used = sum(1 for r in rows if r.get("tool_called"))
            print(f"  actually called the tool: {used}/{n}")
        costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
        if costs:
            print(f"  mean cost_usd={sum(costs) / len(costs):.5f}")
        for r in rows:
            if not r["success"]:
                print(f"  FAILED {r['id']}: {r.get('detail') or r.get('reason')}")

    overall_success = sum(1 for r in records if r["success"])
    print(f"\nOVERALL: {overall_success}/{len(records)} succeeded ({overall_success / len(records):.0%})")


def write_markdown(records: list[dict], path: Path) -> None:
    categories = sorted({r["category"] for r in records})
    lines = [f"# Task execution eval — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", ""]
    lines.append(
        "Real POST /conversations/{id}/runs traffic through the live orchestrator "
        "(guardrails -> graph -> persistence) against a fixed 16-task suite: 4 "
        "code-gen, 4 debugging/analysis, 4 multi-step tool-use, 4 guardrail/PII "
        "probes. Judged tasks use the same judge_item()/PASS_THRESHOLD (0.7) as "
        "the offline golden eval; guardrail probes are graded deterministically "
        "(blocked / masked or not)."
    )
    lines.append("")
    lines.append("| Category | Success | Mean latency | Mean score | Hallucination rate |")
    lines.append("|---|---|---|---|---|")
    for cat in categories:
        rows = [r for r in records if r["category"] == cat]
        n = len(rows)
        success = sum(1 for r in rows if r["success"])
        latencies = [r["latency_sec"] for r in rows]
        judged = [r for r in rows if "score" in r]
        agg = aggregate(judged) if judged else None
        mean_score = f"{agg['mean_score']:.2f}" if agg else "n/a"
        halluc = f"{agg['hallucination_rate']:.0%}" if agg else "n/a"
        lines.append(
            f"| {cat} | {success}/{n} ({success / n:.0%}) | {sum(latencies) / n:.1f}s | {mean_score} | {halluc} |"
        )
    overall_success = sum(1 for r in records if r["success"])
    lines.append("")
    lines.append(f"**Overall: {overall_success}/{len(records)} succeeded ({overall_success / len(records):.0%})**")
    lines.append("")
    lines.append("## Per-task detail")
    lines.append("")
    lines.append("| Task | Category | Success | Latency | Detail |")
    lines.append("|---|---|---|---|---|")
    for r in records:
        detail = (r.get("reason") or r.get("detail") or "").replace("|", "/")[:120]
        lines.append(f"| {r['id']} | {r['category']} | {r['success']} | {r['latency_sec']}s | {detail} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    token = sign_in()
    auth = {"Authorization": f"Bearer {token}"}
    project_id = get_or_create_project(auth)
    ensure_guardrail_policies(auth, project_id)

    records = []
    for i, task in enumerate(TASKS, 1):
        print(f"[{i}/{len(TASKS)}] {task['id']} ...")
        task_project_id = project_id
        if task["category"] == "tool_use":
            # ponytail: tool_use tasks are near-duplicate phrasings of the
            # same todo_lookup request, and the platform's semantic memory
            # recall is project-scoped -- sharing a project let an earlier
            # tool_use task's context bleed into a later one's tool-call
            # reasoning (2 real Groq function-calling failures, 2026-09-14).
            # Give each task its own project so there's no prior memory to
            # recall from.
            task_project_id = get_or_create_project(auth, name=f"{PROJECT_NAME}-{task['id']}")
            ensure_tool(auth, task_project_id)
        try:
            records.append(run_task(auth, task_project_id, task))
        except Exception as exc:  # noqa: BLE001 - one bad task shouldn't kill the run
            records.append({"id": task["id"], "category": task["category"], "mode": task["mode"],
                             "latency_sec": None, "success": False, "detail": f"exception: {exc}"})
        if i < len(TASKS):
            time.sleep(DELAY_SEC)

    print()
    print_report(records)
    out_path = Path(__file__).parent / "task_execution_results.md"
    write_markdown(records, out_path)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
