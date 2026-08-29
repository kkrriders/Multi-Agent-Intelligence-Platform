from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import fetch_maybe_one, get_user_client
from app.evals import MAX_ITEMS, aggregate, judge_item
from app.llm import generate
from app.models import (
    EvalDatasetCreate,
    EvalDatasetDetailOut,
    EvalDatasetOut,
    EvalRunOut,
    EvalRunSummary,
)

router = APIRouter(tags=["evals"])

_ANSWER_SYSTEM = "Answer the question concisely and factually."


def _items(client, dataset_id: str):
    return (
        client.table("eval_items")
        .select("*")
        .eq("dataset_id", dataset_id)
        .order("created_at")
        .execute()
        .data
    )


def _latest_run(client, dataset_id: str):
    return fetch_maybe_one(
        client.table("eval_runs")
        .select("*")
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=True)
        .limit(1)
    )


@router.post("/projects/{project_id}/eval-datasets", response_model=EvalDatasetDetailOut)
def create_dataset(project_id: str, body: EvalDatasetCreate, user: dict = Depends(get_current_user)):
    if not body.items or len(body.items) > MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"items must be between 1 and {MAX_ITEMS}")
    client = get_user_client(user["token"])
    if fetch_maybe_one(
        client.table("eval_datasets").select("id").eq("project_id", project_id).eq("name", body.name)
    ):
        raise HTTPException(status_code=400, detail="A dataset with that name already exists")

    dataset = (
        client.table("eval_datasets").insert({"project_id": project_id, "name": body.name}).execute().data[0]
    )
    items = (
        client.table("eval_items")
        .insert([{"dataset_id": dataset["id"], "input": it.input, "expected": it.expected} for it in body.items])
        .execute()
        .data
    )
    return {
        "id": dataset["id"],
        "name": dataset["name"],
        "item_count": len(items),
        "latest_run": None,
        "created_at": dataset["created_at"],
        "items": items,
    }


@router.get("/projects/{project_id}/eval-datasets", response_model=list[EvalDatasetOut])
def list_datasets(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    datasets = (
        client.table("eval_datasets")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "item_count": len(_items(client, d["id"])),
            "latest_run": _latest_run(client, d["id"]),
            "created_at": d["created_at"],
        }
        for d in datasets
    ]


@router.get("/eval-datasets/{dataset_id}", response_model=EvalDatasetDetailOut)
def get_dataset(dataset_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    dataset = fetch_maybe_one(client.table("eval_datasets").select("*").eq("id", dataset_id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    items = _items(client, dataset_id)
    return {
        "id": dataset["id"],
        "name": dataset["name"],
        "item_count": len(items),
        "latest_run": _latest_run(client, dataset_id),
        "created_at": dataset["created_at"],
        "items": items,
    }


@router.post("/eval-datasets/{dataset_id}/run", response_model=EvalRunOut)
def run_dataset(dataset_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    items = _items(client, dataset_id)
    if not items:
        raise HTTPException(status_code=404, detail="Dataset has no items")

    scored = []
    for item in items:
        output = generate(
            [
                {"role": "system", "content": _ANSWER_SYSTEM},
                {"role": "user", "content": item["input"]},
            ]
        )
        verdict = judge_item(item["input"], item["expected"], output)
        scored.append({"item_id": item["id"], "output": output, **verdict})

    summary = aggregate(scored)
    run = (
        client.table("eval_runs")
        .insert({"dataset_id": dataset_id, "item_count": len(items), **summary})
        .execute()
        .data[0]
    )
    results = (
        client.table("eval_results")
        .insert(
            [
                {
                    "eval_run_id": run["id"],
                    "item_id": s["item_id"],
                    "output": s["output"],
                    "score": s["score"],
                    "hallucinated": s["hallucinated"],
                    "reason": s["reason"],
                }
                for s in scored
            ]
        )
        .execute()
        .data
    )
    return {**run, "results": results}


@router.get("/eval-datasets/{dataset_id}/runs", response_model=list[EvalRunSummary])
def list_runs(dataset_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    return (
        client.table("eval_runs")
        .select("*")
        .eq("dataset_id", dataset_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
