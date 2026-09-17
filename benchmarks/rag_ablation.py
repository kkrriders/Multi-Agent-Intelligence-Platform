"""Retrieval-quality benchmark: vector vs. keyword vs. hybrid vs. hybrid+rerank.

Runs against the REAL stack — a real Supabase project/document_chunks rows
(Postgres full-text search via the generated `content_tsv` column, migration
0004_rag.sql) and a real Qdrant collection — through the actual `app.rag`
functions (`embed_and_store_chunks`, `retrieve_chunks`). Nothing here is
simulated. Needs the backend + qdrant containers running
(`docker compose up -d backend qdrant`) and a live Supabase project.

Auth: mints a one-shot, in-memory-only access token via the same shared test
account AIRRA's `labs/integration/run-traffic.ps1` already uses (password
grant against the real hosted Supabase project). The token is never written
to disk and never printed — set SUPABASE_URL / SUPABASE_ANON_KEY via
backend/.env (already required for the backend itself to run) and the
account's email/password via SUPABASE_TEST_EMAIL / SUPABASE_TEST_PASSWORD
env vars (falls back to the shared test account's known values so this stays
runnable without extra setup, matching run-traffic.ps1's own defaults).

    python benchmarks/rag_ablation.py
    python benchmarks/rag_ablation.py --json out.json

All seeded rows/vectors are deleted at the end regardless of outcome.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config import settings  # noqa: E402
from app.db import get_user_client  # noqa: E402
from app.rag import delete_document_vectors, embed_and_store_chunks, retrieve_chunks  # noqa: E402

RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"  # fastembed cross-encoder, already an
# installed dependency (qdrant-client[fastembed]) — no new package for this.
FETCH_DEPTH = 10  # candidates pulled before scoring/reranking; pool is ~16 chunks.
RECALL_KS = (1, 3, 5)

# Each case owns exactly one query -> target_chunk pair. "near_miss" (when set)
# is an EXTRA chunk seeded into the shared pool that is topically close to the
# query but is NOT the answer — this is what makes Recall@K/MRR non-trivial
# instead of the old benchmark's 100%-or-nothing hit@1 over 5 easy cases.
EVAL_CASES = [
    # -- paraphrase: query shares no keywords with the source chunk --
    {"kind": "paraphrase",
     "content": "Employees may expense a meal up to fifty dollars per day while traveling for work.",
     "query": "what's the daily food budget when I'm on a business trip"},
    {"kind": "paraphrase",
     "content": "The office closes at six in the evening on weekdays and stays shut on public holidays.",
     "query": "when do people have to leave the building"},
    {"kind": "paraphrase",
     "content": "Remote employees receive a one-time $500 stipend to set up their home office.",
     "query": "money for setting up a desk at home"},
    {"kind": "paraphrase",
     "content": "Employees accrue fifteen vacation days per calendar year, prorated for new hires.",
     "query": "how much paid time off do I get annually"},
    {"kind": "paraphrase",
     "content": "Employees working past 8pm can expense a rideshare home instead of taking public transit.",
     "query": "can I get a cab paid for if I stay late"},
    # -- rare_term: query is an exact code the source chunk hinges on --
    {"kind": "rare_term",
     "content": ("All expense reimbursements are processed by the finance team within two weeks of "
                 "submission, provided the request includes a manager approval and, for purchases "
                 "made on a department card, the corresponding order code QX-88214-B."),
     "query": "QX-88214-B"},
    {"kind": "rare_term",
     "content": ("Our on-call rotation covers infrastructure, payments, and the mobile gateway, with "
                 "handoff notes posted at the start of each shift; the latest outage postmortem for "
                 "the payments queue is filed as ticket INFRA-77219."),
     "query": "INFRA-77219"},
    {"kind": "rare_term",
     "content": ("The staging database credentials rotate automatically; the current vault path is "
                 "SECRET/db/staging-v7."),
     "query": "SECRET/db/staging-v7"},
    {"kind": "rare_term",
     "content": ("Escalate payment failures over $10,000 to the finance on-call via PagerDuty "
                 "service FIN-ESC-04."),
     "query": "FIN-ESC-04"},
    # -- either: plainly phrased, either strategy should find it --
    {"kind": "either",
     "content": "New hires get a laptop and a monitor on their first day of onboarding.",
     "query": "laptop monitor first day onboarding"},
    {"kind": "either",
     "content": "The engineering all-hands happens every other Thursday at 10am Pacific.",
     "query": "when is the engineering all hands meeting"},
    {"kind": "either",
     "content": "New parents get twelve weeks of paid leave, which can be split across the first year.",
     "query": "parental leave policy duration"},
    # -- ambiguous: a genuine near-miss chunk competes for the same query --
    {"kind": "ambiguous",
     "content": "Full-time employees are eligible for the annual bonus after six months of employment.",
     "near_miss": "Contractors are not eligible for the annual bonus program regardless of tenure.",
     "query": "am I eligible for the annual bonus"},
    {"kind": "ambiguous",
     "content": "The VPN client must be updated before connecting from outside the corporate office network.",
     "near_miss": "The office WiFi password rotates monthly and is posted in the #it-announcements channel.",
     "query": "how do I connect from outside the office"},
    {"kind": "ambiguous",
     "content": "Expense reports over $200 require a manager's written approval before reimbursement.",
     "near_miss": ("All expense reimbursements are processed by the finance team within two weeks of "
                   "submission, provided the request includes a manager approval and order code QX-88214-B."),
     "query": "do I need approval for a $250 expense"},
]


def _mint_token() -> str:
    email = os.environ.get("SUPABASE_TEST_EMAIL", "anshuman.aroraak+airra-traffic@gmail.com")
    password = os.environ.get("SUPABASE_TEST_PASSWORD", "hunter2-hunter2")
    resp = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.supabase_anon_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]  # kept in-process only; never logged/persisted


def _seed_pool(client, project_id: str) -> tuple[dict[str, str], list[str]]:
    """Insert one document+chunk per case content (and per near_miss), real
    DB rows + real Qdrant vectors. Returns {content: chunk_id} and the list
    of document_ids created (for cleanup)."""
    chunk_id_by_content: dict[str, str] = {}
    document_ids: list[str] = []

    contents = []
    for case in EVAL_CASES:
        contents.append(case["content"])
        if "near_miss" in case:
            contents.append(case["near_miss"])

    for content in contents:
        if content in chunk_id_by_content:
            continue  # the rare_term/ambiguous overlap case reuses existing content verbatim
        document_id = str(uuid.uuid4())
        doc_row = client.table("documents").insert(
            {"id": document_id, "project_id": project_id, "filename": "benchmark.txt",
             "mime_type": "text/plain", "storage_path": f"{project_id}/{document_id}/benchmark.txt",
             "status": "indexed"}
        ).execute().data[0]
        chunk_row = client.table("document_chunks").insert(
            {"document_id": doc_row["id"], "project_id": project_id, "chunk_index": 0, "content": content}
        ).execute().data[0]
        embed_and_store_chunks(
            project_id=project_id, document_id=doc_row["id"], filename="benchmark.txt",
            chunks=[{"chunk_id": chunk_row["id"], "chunk_index": 0, "content": content}],
        )
        chunk_id_by_content[content] = chunk_row["id"]
        document_ids.append(doc_row["id"])

    return chunk_id_by_content, document_ids


def _rank(target_id: str, ranked_ids: list[str]) -> int | None:
    """1-based rank of target_id in ranked_ids, or None if absent."""
    try:
        return ranked_ids.index(target_id) + 1
    except ValueError:
        return None


def _score(ranks: list[int | None]) -> dict:
    n = len(ranks)
    mrr = sum((1.0 / r) if r else 0.0 for r in ranks) / n if n else 0.0
    out = {f"recall_at_{k}": round(sum(1 for r in ranks if r and r <= k) / n, 3) if n else 0.0 for k in RECALL_KS}
    out["mrr"] = round(mrr, 3)
    out["n"] = n
    return out


def run(client, project_id: str, chunk_id_by_content: dict[str, str], reranker) -> dict:
    per_mode_ranks: dict[str, list[int | None]] = {"vector": [], "keyword": [], "hybrid": [], "hybrid_rerank": []}
    per_case_detail = []

    for case in EVAL_CASES:
        target_id = chunk_id_by_content[case["content"]]
        row = {"kind": case["kind"], "query": case["query"]}

        for mode in ("vector", "keyword", "hybrid"):
            results = retrieve_chunks(client, project_id, case["query"], top_k=FETCH_DEPTH, mode=mode)
            ranked_ids = [r["chunk_id"] for r in results]
            r = _rank(target_id, ranked_ids)
            per_mode_ranks[mode].append(r)
            row[mode] = r

        hybrid_results = retrieve_chunks(client, project_id, case["query"], top_k=FETCH_DEPTH, mode="hybrid")
        if hybrid_results:
            scores = list(reranker.rerank(case["query"], [r["content"] for r in hybrid_results]))
            reranked = [r for _, r in sorted(zip(scores, hybrid_results), key=lambda x: x[0], reverse=True)]
            ranked_ids = [r["chunk_id"] for r in reranked]
        else:
            ranked_ids = []
        r = _rank(target_id, ranked_ids)
        per_mode_ranks["hybrid_rerank"].append(r)
        row["hybrid_rerank"] = r

        per_case_detail.append(row)

    return {
        "by_mode": {mode: _score(ranks) for mode, ranks in per_mode_ranks.items()},
        "cases": per_case_detail,
    }


def _print(report: dict) -> None:
    print("RAG retrieval benchmark — real Postgres FTS + Qdrant + fastembed reranker")
    print("=" * 74)
    print(f"{len(EVAL_CASES)} queries against a shared pool of "
          f"{len({c['content'] for c in EVAL_CASES} | {c['near_miss'] for c in EVAL_CASES if 'near_miss' in c})} chunks\n")
    header = f"{'mode':<16}" + "".join(f"R@{k:<6}" for k in RECALL_KS) + "MRR"
    print(header)
    for mode, m in report["by_mode"].items():
        vals = "".join(f"{m[f'recall_at_{k}']:<8.3f}" for k in RECALL_KS)
        print(f"{mode:<16}{vals}{m['mrr']:.3f}")

    regressions = [c for c in report["cases"] if (c["hybrid_rerank"] or 999) > (c["hybrid"] or 999)]
    print(f"\nreranker regressed vs. hybrid alone on: "
          + (", ".join(c["query"] for c in regressions) if regressions else "none"))

    ambiguous_misses = [c for c in report["cases"] if c["kind"] == "ambiguous" and (c["hybrid"] or 999) > 1]
    print(f"ambiguous cases where hybrid did NOT rank the target #1: "
          + (", ".join(c["query"] for c in ambiguous_misses) if ambiguous_misses else "none — all ranked #1"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    from fastembed.rerank.cross_encoder import TextCrossEncoder
    reranker = TextCrossEncoder(model_name=RERANK_MODEL)

    token = _mint_token()
    client = get_user_client(token)
    project = client.table("projects").insert({"name": "rag-benchmark"}).execute().data[0]
    project_id = project["id"]

    document_ids: list[str] = []
    try:
        chunk_id_by_content, document_ids = _seed_pool(client, project_id)
        report = run(client, project_id, chunk_id_by_content, reranker)
    finally:
        for document_id in document_ids:
            delete_document_vectors(document_id)
        client.table("documents").delete().eq("project_id", project_id).execute()
        client.table("projects").delete().eq("id", project_id).execute()

    _print(report)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
        print(f"\nreport -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
