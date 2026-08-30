from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.alerts import evaluate_project_alerts, record_rate_limit_event
from app.auth import get_current_user
from app.cache import cache_key
from app.config import settings
from app.cost import cost_for
from app.db import fetch_maybe_one, get_user_client
from app.graph import build_graph, make_initial_state
from app.graph.tool_schemas import sanitize_tools
from app.guardrails import apply_post, check_input
from app.history import prepare_history
from app.llm import MODEL_CHEAP, drain_usage, generate, reset_usage, set_node
from app.memory import search_memory, upsert_memory
from app.models import RunCreate, RunOut
from app.prompts import MissingVariableError, render_template
from app.rag import retrieve_chunks

router = APIRouter(tags=["runs"])

CITATION_CONTENT_CHARS = 500

_HISTORY_SUMMARY_SYSTEM = (
    "Summarize this conversation so far in 8 sentences or fewer. Preserve "
    "facts, names, numbers, and decisions the assistant may need later."
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_is_fresh(created_at: str) -> bool:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - created <= timedelta(days=settings.cache_max_age_days)


def _summarize_history(older_runs: list[dict]) -> str:
    set_node("history")
    body = "\n\n".join(f"User: {r['input']}\nAssistant: {r['output']}" for r in older_runs)
    return generate(
        [
            {"role": "system", "content": _HISTORY_SUMMARY_SYSTEM},
            {"role": "user", "content": body},
        ],
        model=MODEL_CHEAP,
    )


def _persist_llm_usage(client, run_id: str) -> dict:
    """Drain the per-run usage accumulator into run_llm_calls rows and return
    the summed {prompt_tokens, completion_tokens, cost_usd} for the run row."""
    calls = drain_usage()
    rows = []
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    for c in calls:
        cost = cost_for(c["model"], c["prompt_tokens"], c["completion_tokens"])
        totals["prompt_tokens"] += c["prompt_tokens"]
        totals["completion_tokens"] += c["completion_tokens"]
        totals["cost_usd"] += cost
        rows.append(
            {
                "run_id": run_id,
                "node": c["node"],
                "model": c["model"],
                "prompt_tokens": c["prompt_tokens"],
                "completion_tokens": c["completion_tokens"],
                "cost_usd": round(cost, 6),
            }
        )
    if rows:
        client.table("run_llm_calls").insert(rows).execute()
    totals["cost_usd"] = round(totals["cost_usd"], 6)
    return totals


def _finalize_run(
    client,
    *,
    run_id,
    project_id,
    conversation_id,
    resolved_input,
    raw_output,
    policies,
    citations,
    ckey,
    cache_hit,
):
    """Shared tail for both the cache-hit and normal paths: post-guardrails,
    agent_responded event, usage/cost persistence, run row update, memory
    upsert, cache write, and the RunOut payload."""
    post = apply_post(raw_output, policies)
    output = post.output
    for ev in post.events:
        client.table("guardrail_events").insert(
            {
                "run_id": run_id,
                "project_id": project_id,
                "phase": "post",
                "kind": ev["kind"],
                "outcome": ev["outcome"],
                "detail": ev["detail"],
            }
        ).execute()

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "agent_responded", "payload": {"output": output}}
    ).execute()

    if cache_hit:
        drain_usage()  # a cached run records no spend even if history was summarized
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0}
    else:
        totals = _persist_llm_usage(client, run_id)
        client.table("response_cache").upsert(
            {
                "project_id": project_id,
                "cache_key": ckey,
                "output": output,
                "hit_count": 0,
                "created_at": _iso_now(),  # refresh the age clock when regenerating a stale entry
            },
            on_conflict="project_id,cache_key",
        ).execute()

    updated = (
        client.table("runs")
        .update({"status": "completed", "output": output, "cache_hit": cache_hit, **totals})
        .eq("id", run_id)
        .execute()
        .data[0]
    )
    upsert_memory(run_id, project_id, conversation_id, resolved_input, output)

    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    guardrail_events = (
        client.table("guardrail_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    )
    return {
        **updated,
        "events": events,
        "citations": citations,
        "guardrails": guardrail_events,
        "llm_calls": _fetch_llm_calls(client, run_id),
    }


def _fetch_llm_calls(client, run_id: str) -> list[dict]:
    return (
        client.table("run_llm_calls")
        .select("node, model, prompt_tokens, completion_tokens, cost_usd")
        .eq("run_id", run_id)
        .order("created_at")
        .execute()
        .data
    )


@router.post("/conversations/{conversation_id}/runs", response_model=RunOut)
def create_run(conversation_id: str, body: RunCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])

    conversation = fetch_maybe_one(
        client.table("conversations")
        .select("project_id, history_summary, summary_through_run_id")
        .eq("id", conversation_id)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    project_id = conversation["project_id"]

    # Rate limit before any spend. RLS scopes `runs` to the caller's own
    # projects, so this COUNT is naturally per-user.
    if settings.run_rate_limit_per_min:
        since = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        recent = client.table("runs").select("id", count="exact").gte("created_at", since).execute().count or 0
        if recent >= settings.run_rate_limit_per_min:
            record_rate_limit_event(client, project_id, settings.run_rate_limit_per_min)
            raise HTTPException(status_code=429, detail="run rate limit exceeded; retry shortly")

    # Everything from here — the history-summary call and the graph — feeds the
    # per-run usage accumulator; drained once at the end (both cache paths).
    reset_usage()

    if body.template_id:
        # RLS on prompt_template_versions blocks other projects' templates, so a
        # missing row means "not found or not yours".
        version = fetch_maybe_one(
            client.table("prompt_template_versions")
            .select("version, body")
            .eq("template_id", body.template_id)
            .order("version", desc=True)
            .limit(1)
        )
        if not version:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        try:
            resolved_input = render_template(version["body"], body.variables)
        except MissingVariableError as exc:
            raise HTTPException(status_code=422, detail=f"missing template variable: {exc}")
        prompt_meta = {
            "template_id": body.template_id,
            "version": version["version"],
            "variables": body.variables,
        }
    else:
        resolved_input = body.input
        prompt_meta = None

    prior_runs = (
        client.table("runs")
        .select("id, input, output")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    history, compression = prepare_history(
        prior_runs,
        stored_summary=conversation.get("history_summary"),
        summary_through_run_id=conversation.get("summary_through_run_id"),
        summarize=_summarize_history,
    )
    if compression and not compression["summary_reused"]:
        client.table("conversations").update(
            {
                "history_summary": compression["summary"],
                "summary_through_run_id": compression["summary_through_run_id"],
            }
        ).eq("id", conversation_id).execute()

    memories = search_memory(project_id, resolved_input)
    memory_context = [f"User: {m['input']}\nAssistant: {m['output']}" for m in memories]

    chunks = retrieve_chunks(client, project_id, resolved_input)
    citations = [
        {
            "index": i + 1,
            "document_id": chunk["document_id"],
            "filename": chunk["filename"],
            "content": chunk["content"][:CITATION_CONTENT_CHARS],
        }
        for i, chunk in enumerate(chunks)
    ]

    run = client.table("runs").insert(
        {
            "project_id": project_id,
            "conversation_id": conversation_id,
            "status": "running",
            "input": resolved_input,
        }
    ).execute().data[0]
    run_id = run["id"]

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "run_started", "payload": {"input": resolved_input}}
    ).execute()

    if prompt_meta:
        client.table("run_events").insert(
            {"run_id": run_id, "step_name": "prompt_used", "payload": {"turn": 0, **prompt_meta}}
        ).execute()

    if memories:
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "memory_recalled",
                "payload": {"turn": 0, "count": len(memories), "top_score": memories[0]["score"]},
            }
        ).execute()

    if chunks:
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "retrieval_performed",
                "payload": {
                    "turn": 0,
                    "count": len(chunks),
                    "top_score": chunks[0]["score"],
                    "sources": [{"filename": c["filename"], "score": c["score"]} for c in chunks],
                },
            }
        ).execute()

    if compression:
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "history_compressed",
                "payload": {
                    "turn": 0,
                    "runs_summarized": compression["runs_summarized"],
                    "tokens_before": compression["tokens_before"],
                    "tokens_after": compression["tokens_after"],
                    "summary_reused": compression["summary_reused"],
                },
            }
        ).execute()

    policy_rows = (
        client.table("guardrail_policies")
        .select("kind, enabled, config")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    policies = {r["kind"]: {"enabled": r["enabled"], "config": r["config"]} for r in policy_rows}

    verdict = check_input(resolved_input, [c["content"] for c in chunks], policies)
    client.table("guardrail_events").insert(
        {
            "run_id": run_id,
            "project_id": project_id,
            "phase": "pre",
            "kind": verdict.kind or "injection",
            "outcome": "pass" if verdict.ok else "blocked",
            "detail": verdict.detail,
        }
    ).execute()
    if not verdict.ok:
        client.table("runs").update({"status": "blocked"}).eq("id", run_id).execute()
        evaluate_project_alerts(client, project_id)
        reason = verdict.detail.get("reason") or verdict.detail.get("matched") or verdict.kind
        raise HTTPException(status_code=422, detail=f"blocked by guardrail: {reason}")

    ckey = cache_key(project_id, resolved_input, [c["chunk_id"] for c in chunks], len(prior_runs))
    cached = fetch_maybe_one(
        client.table("response_cache")
        .select("*")
        .eq("project_id", project_id)
        .eq("cache_key", ckey)
    )
    if cached and _cache_is_fresh(cached["created_at"]):
        client.table("response_cache").update(
            {"hit_count": cached["hit_count"] + 1, "last_hit_at": _iso_now()}
        ).eq("id", cached["id"]).execute()
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "cache_hit",
                "payload": {"turn": 0, "hit_count": cached["hit_count"] + 1},
            }
        ).execute()
        result = _finalize_run(
            client,
            run_id=run_id,
            project_id=project_id,
            conversation_id=conversation_id,
            resolved_input=resolved_input,
            raw_output=cached["output"],
            policies=policies,
            citations=citations,
            ckey=ckey,
            cache_hit=True,
        )
        evaluate_project_alerts(client, project_id)
        return result

    tool_rows = client.table("tools").select("name, type, config").eq("project_id", project_id).execute().data
    tool_specs, tool_configs = sanitize_tools(tool_rows)

    graph = build_graph(tool_configs)
    initial = make_initial_state(
        input=resolved_input,
        history=history,
        memory_context=memory_context,
        retrieved_chunks=chunks,
        tool_specs=tool_specs,
    )

    flushed = 0
    final_state = initial
    try:
        for snapshot in graph.stream(initial, stream_mode="values"):
            final_state = snapshot
            for event in snapshot["events"][flushed:]:
                client.table("run_events").insert(
                    {"run_id": run_id, "step_name": event["step_name"], "payload": event["payload"]}
                ).execute()
            flushed = len(snapshot["events"])
    except Exception as exc:  # noqa: BLE001 - persist the failure, then surface it
        client.table("run_events").insert(
            {"run_id": run_id, "step_name": "error", "payload": {"detail": str(exc)[:500]}}
        ).execute()
        client.table("runs").update({"status": "failed"}).eq("id", run_id).execute()
        evaluate_project_alerts(client, project_id)
        raise HTTPException(status_code=500, detail="Run failed during orchestration")

    result = _finalize_run(
        client,
        run_id=run_id,
        project_id=project_id,
        conversation_id=conversation_id,
        resolved_input=resolved_input,
        raw_output=final_state["output"],
        policies=policies,
        citations=citations,
        ckey=ckey,
        cache_hit=False,
    )
    evaluate_project_alerts(client, project_id)
    return result


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    run = fetch_maybe_one(client.table("runs").select("*").eq("id", run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**run, "events": events, "llm_calls": _fetch_llm_calls(client, run_id)}


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
def list_project_runs(project_id: str, limit: int = 50, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    project = fetch_maybe_one(client.table("projects").select("id").eq("id", project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conv_ids = [
        c["id"]
        for c in client.table("conversations").select("id").eq("project_id", project_id).execute().data
    ]
    if not conv_ids:
        return []

    runs = (
        client.table("runs")
        .select("*")
        .in_("conversation_id", conv_ids)
        .order("created_at", desc=True)
        .limit(min(limit, 200))
        .execute()
        .data
    )
    run_ids = [r["id"] for r in runs]
    if not run_ids:
        return []

    events = client.table("run_events").select("*").in_("run_id", run_ids).order("created_at").execute().data
    guardrails = (
        client.table("guardrail_events").select("*").in_("run_id", run_ids).order("created_at").execute().data
    )
    events_by_run: dict[str, list] = {}
    for event in events:
        events_by_run.setdefault(event["run_id"], []).append(event)
    guards_by_run: dict[str, list] = {}
    for guard in guardrails:
        guards_by_run.setdefault(guard["run_id"], []).append(guard)

    return [
        {
            **run,
            "events": events_by_run.get(run["id"], []),
            "guardrails": guards_by_run.get(run["id"], []),
            "citations": [],
        }
        for run in runs
    ]


@router.get("/conversations/{conversation_id}/runs", response_model=list[RunOut])
def list_conversation_runs(conversation_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    runs = (
        client.table("runs")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    run_ids = [r["id"] for r in runs]
    events = (
        client.table("run_events").select("*").in_("run_id", run_ids).order("created_at").execute().data
        if run_ids
        else []
    )
    events_by_run: dict[str, list] = {}
    for event in events:
        events_by_run.setdefault(event["run_id"], []).append(event)
    return [{**run, "events": events_by_run.get(run["id"], [])} for run in runs]
