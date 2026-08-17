from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client
from app.graph import agent_graph
from app.memory import history_to_messages, search_memory, upsert_memory
from app.models import RunCreate, RunOut

router = APIRouter(tags=["runs"])


@router.post("/conversations/{conversation_id}/runs", response_model=RunOut)
def create_run(conversation_id: str, body: RunCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])

    conversation = fetch_maybe_one(
        client.table("conversations").select("project_id").eq("id", conversation_id)
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    project_id = conversation["project_id"]

    prior_runs = (
        client.table("runs")
        .select("input, output")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    history = history_to_messages(prior_runs)

    memories = search_memory(project_id, body.input)
    memory_context = [f"User: {m['input']}\nAssistant: {m['output']}" for m in memories]

    run = client.table("runs").insert(
        {
            "project_id": project_id,
            "conversation_id": conversation_id,
            "status": "running",
            "input": body.input,
        }
    ).execute().data[0]
    run_id = run["id"]

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "run_started", "payload": {"input": body.input}}
    ).execute()

    if memories:
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "memory_recalled",
                "payload": {"count": len(memories), "top_score": memories[0]["score"]},
            }
        ).execute()

    result = agent_graph.invoke(
        {"input": body.input, "output": "", "history": history, "memory_context": memory_context}
    )

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "agent_responded", "payload": {"output": result["output"]}}
    ).execute()

    updated = client.table("runs").update(
        {"status": "completed", "output": result["output"]}
    ).eq("id", run_id).execute().data[0]

    upsert_memory(run_id, project_id, conversation_id, body.input, result["output"])

    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**updated, "events": events}


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    run = fetch_maybe_one(client.table("runs").select("*").eq("id", run_id))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**run, "events": events}


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
