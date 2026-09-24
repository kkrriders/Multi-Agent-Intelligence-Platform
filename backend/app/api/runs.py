import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.alerts import evaluate_project_alerts, record_rate_limit_event
from app.cache import cache_key
from app.config import settings
from app.cost import cost_for
from app.db import get_db, maybe_one, one, rows
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


def _add_event(conn: Connection, run_id: str, step_name: str, payload: dict) -> None:
    conn.execute(
        text("insert into run_events (run_id, step_name, payload) values (:r, :s, cast(:p as jsonb))"),
        {"r": run_id, "s": step_name, "p": json.dumps(payload)},
    )


def _add_guardrail_event(
    conn: Connection, run_id: str, project_id: str, phase: str, kind: str, outcome: str, detail: dict
) -> None:
    conn.execute(
        text(
            "insert into guardrail_events (run_id, project_id, phase, kind, outcome, detail) "
            "values (:r, :p, :ph, :k, :o, cast(:d as jsonb))"
        ),
        {"r": run_id, "p": project_id, "ph": phase, "k": kind, "o": outcome, "d": json.dumps(detail)},
    )


def _events_for(conn: Connection, table: str, run_id: str) -> list[dict]:
    # `table` is one of two literals below, never request data.
    assert table in ("run_events", "guardrail_events")
    return rows(conn.execute(text(f"select * from {table} where run_id = :r order by created_at"), {"r": run_id}))


def _persist_llm_usage(conn: Connection, run_id: str) -> dict:
    """Drain the per-run usage accumulator into run_llm_calls rows and return
    the summed {prompt_tokens, completion_tokens, cost_usd} for the run row."""
    calls = drain_usage()
    call_rows = []
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    for c in calls:
        cost = cost_for(c["model"], c["prompt_tokens"], c["completion_tokens"])
        totals["prompt_tokens"] += c["prompt_tokens"]
        totals["completion_tokens"] += c["completion_tokens"]
        totals["cost_usd"] += cost
        call_rows.append(
            {
                "run_id": run_id,
                "node": c["node"],
                "model": c["model"],
                "prompt_tokens": c["prompt_tokens"],
                "completion_tokens": c["completion_tokens"],
                "cost_usd": round(cost, 6),
            }
        )
    if call_rows:
        conn.execute(
            text(
                "insert into run_llm_calls (run_id, node, model, prompt_tokens, completion_tokens, cost_usd) "
                "values (:run_id, :node, :model, :prompt_tokens, :completion_tokens, :cost_usd)"
            ),
            call_rows,
        )
    totals["cost_usd"] = round(totals["cost_usd"], 6)
    return totals


def _finalize_run(
    conn: Connection,
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
        _add_guardrail_event(conn, run_id, project_id, "post", ev["kind"], ev["outcome"], ev["detail"])

    _add_event(conn, run_id, "agent_responded", {"output": output})

    # Persisted for both paths: even a cache hit still paid for the pre-hook
    # injection classifier call (real Groq spend before the cache check runs),
    # so cost accounting must record it rather than reporting a cache hit as free.
    totals = _persist_llm_usage(conn, run_id)
    if not cache_hit:
        conn.execute(
            text(
                "insert into response_cache (project_id, cache_key, output, hit_count, created_at) "
                "values (:p, :k, :o, 0, :t) "
                "on conflict (project_id, cache_key) do update set output = excluded.output, "
                "hit_count = 0, created_at = excluded.created_at"  # refresh the age clock on regeneration
            ),
            {"p": project_id, "k": ckey, "o": output, "t": _iso_now()},
        )

    updated = one(
        conn.execute(
            text(
                "update runs set status = 'completed', output = :o, cache_hit = :h, "
                "prompt_tokens = :pt, completion_tokens = :ct, cost_usd = :c where id = :i returning *"
            ),
            {
                "o": output,
                "h": cache_hit,
                "pt": totals["prompt_tokens"],
                "ct": totals["completion_tokens"],
                "c": totals["cost_usd"],
                "i": run_id,
            },
        )
    )
    upsert_memory(run_id, project_id, conversation_id, resolved_input, output)

    events = _events_for(conn, "run_events", run_id)
    guardrail_events = _events_for(conn, "guardrail_events", run_id)
    return {
        **updated,
        "events": events,
        "citations": citations,
        "guardrails": guardrail_events,
        "llm_calls": _fetch_llm_calls(conn, run_id),
    }


def _fetch_llm_calls(conn: Connection, run_id: str) -> list[dict]:
    return rows(
        conn.execute(
            text(
                "select node, model, prompt_tokens, completion_tokens, cost_usd from run_llm_calls "
                "where run_id = :r order by created_at"
            ),
            {"r": run_id},
        )
    )


@router.post("/conversations/{conversation_id}/runs", response_model=RunOut)
def create_run(conversation_id: str, body: RunCreate, conn: Connection = Depends(get_db)):
    conversation = maybe_one(
        conn.execute(
            text(
                "select project_id, history_summary, summary_through_run_id "
                "from conversations where id = :i"
            ),
            {"i": conversation_id},
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    project_id = conversation["project_id"]

    # Rate limit before any spend. RLS scopes `runs` to the caller's own
    # projects, so this COUNT is naturally per-user.
    if settings.run_rate_limit_per_min:
        since = datetime.now(timezone.utc) - timedelta(seconds=60)
        recent = conn.execute(
            text("select count(*) from runs where created_at >= :s"), {"s": since}
        ).scalar_one()
        if recent >= settings.run_rate_limit_per_min:
            record_rate_limit_event(conn, project_id, settings.run_rate_limit_per_min)
            raise HTTPException(status_code=429, detail="run rate limit exceeded; retry shortly")

    # Everything from here — the history-summary call and the graph — feeds the
    # per-run usage accumulator; drained once at the end (both cache paths).
    reset_usage()

    if body.template_id:
        # RLS on prompt_template_versions blocks other projects' templates, so a
        # missing row means "not found or not yours".
        version = maybe_one(
            conn.execute(
                text(
                    "select version, body from prompt_template_versions where template_id = :t "
                    "order by version desc limit 1"
                ),
                {"t": body.template_id},
            )
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
        assert body.input is not None  # guaranteed by RunCreate's exactly-one-of validator
        resolved_input = body.input
        prompt_meta = None

    prior_runs = rows(
        conn.execute(
            text("select id, input, output from runs where conversation_id = :c order by created_at"),
            {"c": conversation_id},
        )
    )
    memories = search_memory(project_id, resolved_input)
    memory_context = [f"User: {m['input']}\nAssistant: {m['output']}" for m in memories]

    chunks = retrieve_chunks(conn, project_id, resolved_input)
    citations = [
        {
            "index": i + 1,
            "document_id": chunk["document_id"],
            "filename": chunk["filename"],
            "content": chunk["content"][:CITATION_CONTENT_CHARS],
        }
        for i, chunk in enumerate(chunks)
    ]

    run = one(
        conn.execute(
            text(
                "insert into runs (project_id, conversation_id, status, input) "
                "values (:p, :c, 'running', :i) returning *"
            ),
            {"p": project_id, "c": conversation_id, "i": resolved_input},
        )
    )
    run_id = run["id"]

    _add_event(conn, run_id, "run_started", {"input": resolved_input})

    if prompt_meta:
        _add_event(conn, run_id, "prompt_used", {"turn": 0, **prompt_meta})

    if memories:
        _add_event(
            conn,
            run_id,
            "memory_recalled",
            {"turn": 0, "count": len(memories), "top_score": memories[0]["score"]},
        )

    if chunks:
        _add_event(
            conn,
            run_id,
            "retrieval_performed",
            {
                "turn": 0,
                "count": len(chunks),
                "top_score": chunks[0]["score"],
                "sources": [{"filename": c["filename"], "score": c["score"]} for c in chunks],
            },
        )

    policy_rows = rows(
        conn.execute(
            text("select kind, enabled, config from guardrail_policies where project_id = :p"),
            {"p": project_id},
        )
    )
    policies = {r["kind"]: {"enabled": r["enabled"], "config": r["config"]} for r in policy_rows}

    verdict = check_input(resolved_input, [c["content"] for c in chunks], policies)
    _add_guardrail_event(
        conn,
        run_id,
        project_id,
        "pre",
        verdict.kind or "injection",
        "pass" if verdict.ok else "blocked",
        verdict.detail,
    )
    if not verdict.ok:
        conn.execute(text("update runs set status = 'blocked' where id = :i"), {"i": run_id})
        evaluate_project_alerts(conn, project_id)
        reason = verdict.detail.get("reason") or verdict.detail.get("matched") or verdict.kind
        raise HTTPException(status_code=422, detail=f"blocked by guardrail: {reason}")

    ckey = cache_key(project_id, resolved_input, [c["chunk_id"] for c in chunks], len(prior_runs))
    cached = maybe_one(
        conn.execute(
            text("select * from response_cache where project_id = :p and cache_key = :k"),
            {"p": project_id, "k": ckey},
        )
    )
    if cached and _cache_is_fresh(cached["created_at"]):
        conn.execute(
            text("update response_cache set hit_count = :h, last_hit_at = :t where id = :i"),
            {"h": cached["hit_count"] + 1, "t": _iso_now(), "i": cached["id"]},
        )
        _add_event(conn, run_id, "cache_hit", {"turn": 0, "hit_count": cached["hit_count"] + 1})
        result = _finalize_run(
            conn,
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
        evaluate_project_alerts(conn, project_id)
        return result

    # Only reached on a cache miss: prepare_history() may call MODEL_CHEAP to
    # summarize older turns (real Groq spend) — deferred past the cache check
    # above so a hit never pays for a summary its cached output doesn't need.
    history, compression = prepare_history(
        prior_runs,
        stored_summary=conversation.get("history_summary"),
        summary_through_run_id=conversation.get("summary_through_run_id"),
        summarize=_summarize_history,
    )
    if compression and not compression["summary_reused"]:
        conn.execute(
            text(
                "update conversations set history_summary = :s, summary_through_run_id = :r where id = :i"
            ),
            {
                "s": compression["summary"],
                "r": compression["summary_through_run_id"],
                "i": conversation_id,
            },
        )
    if compression:
        _add_event(
            conn,
            run_id,
            "history_compressed",
            {
                "turn": 0,
                "runs_summarized": compression["runs_summarized"],
                "tokens_before": compression["tokens_before"],
                "tokens_after": compression["tokens_after"],
                "summary_reused": compression["summary_reused"],
            },
        )

    tool_rows = rows(
        conn.execute(text("select name, type, config from tools where project_id = :p"), {"p": project_id})
    )
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
                _add_event(conn, run_id, event["step_name"], event["payload"])
            flushed = len(snapshot["events"])
    except Exception as exc:  # noqa: BLE001 - persist the failure, then surface it
        _add_event(conn, run_id, "error", {"detail": str(exc)[:500]})
        conn.execute(text("update runs set status = 'failed' where id = :i"), {"i": run_id})
        evaluate_project_alerts(conn, project_id)
        raise HTTPException(status_code=500, detail="Run failed during orchestration")

    result = _finalize_run(
        conn,
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
    evaluate_project_alerts(conn, project_id)
    return result


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, conn: Connection = Depends(get_db)):
    run = maybe_one(conn.execute(text("select * from runs where id = :i"), {"i": run_id}))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = _events_for(conn, "run_events", run_id)
    return {**run, "events": events, "llm_calls": _fetch_llm_calls(conn, run_id)}


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
def list_project_runs(project_id: str, limit: int = 50, conn: Connection = Depends(get_db)):
    project = maybe_one(conn.execute(text("select id from projects where id = :i"), {"i": project_id}))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conv_ids = [
        c["id"]
        for c in rows(conn.execute(text("select id from conversations where project_id = :p"), {"p": project_id}))
    ]
    if not conv_ids:
        return []

    project_runs = rows(
        conn.execute(
            text(
                "select * from runs where conversation_id = any(cast(:ids as uuid[])) "
                "order by created_at desc limit :n"
            ),
            {"ids": conv_ids, "n": min(limit, 200)},
        )
    )
    run_ids = [r["id"] for r in project_runs]
    if not run_ids:
        return []

    events = rows(
        conn.execute(
            text("select * from run_events where run_id = any(cast(:ids as uuid[])) order by created_at"),
            {"ids": run_ids},
        )
    )
    guardrails = rows(
        conn.execute(
            text("select * from guardrail_events where run_id = any(cast(:ids as uuid[])) order by created_at"),
            {"ids": run_ids},
        )
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
        for run in project_runs
    ]


@router.get("/conversations/{conversation_id}/runs", response_model=list[RunOut])
def list_conversation_runs(conversation_id: str, conn: Connection = Depends(get_db)):
    conversation_runs = rows(
        conn.execute(
            text("select * from runs where conversation_id = :c order by created_at"),
            {"c": conversation_id},
        )
    )
    run_ids = [r["id"] for r in conversation_runs]
    events = (
        rows(
            conn.execute(
                text("select * from run_events where run_id = any(cast(:ids as uuid[])) order by created_at"),
                {"ids": run_ids},
            )
        )
        if run_ids
        else []
    )
    events_by_run: dict[str, list] = {}
    for event in events:
        events_by_run.setdefault(event["run_id"], []).append(event)
    return [{**run, "events": events_by_run.get(run["id"], [])} for run in conversation_runs]
