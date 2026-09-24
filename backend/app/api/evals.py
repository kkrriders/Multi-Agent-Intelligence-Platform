from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, text

from app.db import get_db, maybe_one, one, rows
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


def _items(conn: Connection, dataset_id: str):
    return rows(
        conn.execute(
            text("select * from eval_items where dataset_id = :d order by created_at"), {"d": dataset_id}
        )
    )


def _latest_run(conn: Connection, dataset_id: str):
    return maybe_one(
        conn.execute(
            text("select * from eval_runs where dataset_id = :d order by created_at desc limit 1"),
            {"d": dataset_id},
        )
    )


@router.post("/projects/{project_id}/eval-datasets", response_model=EvalDatasetDetailOut)
def create_dataset(project_id: str, body: EvalDatasetCreate, conn: Connection = Depends(get_db)):
    if not body.items or len(body.items) > MAX_ITEMS:
        raise HTTPException(status_code=400, detail=f"items must be between 1 and {MAX_ITEMS}")
    if maybe_one(
        conn.execute(
            text("select id from eval_datasets where project_id = :p and name = :n"),
            {"p": project_id, "n": body.name},
        )
    ):
        raise HTTPException(status_code=400, detail="A dataset with that name already exists")

    dataset = one(
        conn.execute(
            text("insert into eval_datasets (project_id, name) values (:p, :n) returning *"),
            {"p": project_id, "n": body.name},
        )
    )
    items = [
        one(
            conn.execute(
                text(
                    "insert into eval_items (dataset_id, input, expected) "
                    "values (:d, :i, :e) returning *"
                ),
                {"d": dataset["id"], "i": it.input, "e": it.expected},
            )
        )
        for it in body.items
    ]
    return {
        "id": dataset["id"],
        "name": dataset["name"],
        "item_count": len(items),
        "latest_run": None,
        "created_at": dataset["created_at"],
        "items": items,
    }


@router.get("/projects/{project_id}/eval-datasets", response_model=list[EvalDatasetOut])
def list_datasets(project_id: str, conn: Connection = Depends(get_db)):
    datasets = rows(
        conn.execute(
            text("select * from eval_datasets where project_id = :p order by created_at desc"),
            {"p": project_id},
        )
    )
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "item_count": len(_items(conn, d["id"])),
            "latest_run": _latest_run(conn, d["id"]),
            "created_at": d["created_at"],
        }
        for d in datasets
    ]


@router.get("/eval-datasets/{dataset_id}", response_model=EvalDatasetDetailOut)
def get_dataset(dataset_id: str, conn: Connection = Depends(get_db)):
    dataset = maybe_one(conn.execute(text("select * from eval_datasets where id = :i"), {"i": dataset_id}))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    items = _items(conn, dataset_id)
    return {
        "id": dataset["id"],
        "name": dataset["name"],
        "item_count": len(items),
        "latest_run": _latest_run(conn, dataset_id),
        "created_at": dataset["created_at"],
        "items": items,
    }


@router.post("/eval-datasets/{dataset_id}/run", response_model=EvalRunOut)
def run_dataset(dataset_id: str, conn: Connection = Depends(get_db)):
    items = _items(conn, dataset_id)
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
    run = one(
        conn.execute(
            text(
                "insert into eval_runs (dataset_id, item_count, accuracy, hallucination_rate, mean_score) "
                "values (:d, :n, :a, :h, :m) returning *"
            ),
            {
                "d": dataset_id,
                "n": len(items),
                "a": summary["accuracy"],
                "h": summary["hallucination_rate"],
                "m": summary["mean_score"],
            },
        )
    )
    results = [
        one(
            conn.execute(
                text(
                    "insert into eval_results (eval_run_id, item_id, output, score, hallucinated, reason) "
                    "values (:r, :i, :o, :s, :h, :why) returning *"
                ),
                {
                    "r": run["id"],
                    "i": s["item_id"],
                    "o": s["output"],
                    "s": s["score"],
                    "h": s["hallucinated"],
                    "why": s["reason"],
                },
            )
        )
        for s in scored
    ]
    return {**run, "results": results}


@router.get("/eval-datasets/{dataset_id}/runs", response_model=list[EvalRunSummary])
def list_runs(dataset_id: str, conn: Connection = Depends(get_db)):
    return rows(
        conn.execute(
            text("select * from eval_runs where dataset_id = :d order by created_at desc"),
            {"d": dataset_id},
        )
    )
