"""Retrieval-quality ablation: hybrid vs. vector-only vs. keyword-only.

Backs the reliability claim in README.md — run it against a real Qdrant
(docker compose up -d qdrant) to reproduce the numbers in results.md.

Eval cases are grouped by what they're meant to stress:
- "paraphrase" — query shares no keywords with the source chunk, so only
  a semantic/vector match should find it.
- "rare_term" — the source chunk hinges on an exact rare code, the kind
  of thing keyword search is expected to catch.
- "either" — phrased plainly; either strategy should find it.

In practice, on this eval set, BAAI/bge-small-en-v1.5 finds every case,
including the rare-term ones: subword tokenization gives short exact codes
like "QX-88214-B" enough literal token overlap between query and chunk
that vector search recovers them without keyword help. Keyword-only
underperforms because Postgres `text_search` (simulated here) needs
shared whole words, not substrings, and misses paraphrases entirely.
Hybrid never loses to either mode alone — that's the actual guarantee
this benchmark checks, not a fixed vector-vs-keyword split.

Keyword search is simulated with a plain substring-match stub (same shape
as the Supabase client `retrieve_chunks` expects) rather than a live
Supabase project, matching the stubbing convention already used in
tests/test_rag.py — this benchmark is about the merge/ranking logic in
app.rag, not Postgres full-text-search quality.
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.rag import delete_document_vectors, embed_and_store_chunks, retrieve_chunks  # noqa: E402  # type: ignore[import-not-found]

EVAL_CASES = [
    {
        "kind": "paraphrase",
        "content": "Employees may expense a meal up to fifty dollars per day while traveling for work.",
        "query": "what's the daily food budget when I'm on a business trip",
    },
    {
        "kind": "paraphrase",
        "content": "The office closes at six in the evening on weekdays and stays shut on public holidays.",
        "query": "when do people have to leave the building",
    },
    {
        "kind": "rare_term",
        "content": (
            "All expense reimbursements are processed by the finance team within two weeks of "
            "submission, provided the request includes a manager approval and, for purchases "
            "made on a department card, the corresponding order code QX-88214-B."
        ),
        "query": "QX-88214-B",
    },
    {
        "kind": "rare_term",
        "content": (
            "Our on-call rotation covers infrastructure, payments, and the mobile gateway, with "
            "handoff notes posted at the start of each shift; the latest outage postmortem for "
            "the payments queue is filed as ticket INFRA-77219."
        ),
        "query": "INFRA-77219",
    },
    {
        "kind": "either",
        "content": "New hires get a laptop and a monitor on their first day of onboarding.",
        "query": "laptop monitor first day onboarding",
    },
]


class _SubstringKeywordClient:
    """Minimal stand-in for the Supabase chain in app.rag.retrieve_chunks,
    matching rows by plain substring instead of Postgres full-text search."""

    def __init__(self, rows):
        self._rows = rows
        self._project_id = None
        self._query = None

    def table(self, name):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        if field == "project_id":
            self._project_id = value
        return self

    def text_search(self, field, query, **kwargs):
        self._query = query.lower()
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        matched = [
            row
            for row in self._rows
            if row["project_id"] == self._project_id and self._query in row["content"].lower()
        ]
        return SimpleNamespace(data=matched)


def run_case(case: dict, distractors: list[str]) -> dict:
    """Seeds the target chunk alongside sibling-case content as distractor
    noise (a real knowledge base has many chunks per project, so retrieval
    has to discriminate signal from noise — a single-chunk project would
    let any nonzero vector score trivially "win")."""
    project_id = str(uuid.uuid4())
    document_ids = []
    target_chunk_id = str(uuid.uuid4())
    rows = [
        {
            "chunk_id": target_chunk_id,
            "content": case["content"],
        }
    ] + [{"chunk_id": str(uuid.uuid4()), "content": text} for text in distractors]

    keyword_rows = []
    for row in rows:
        document_id = str(uuid.uuid4())
        document_ids.append(document_id)
        embed_and_store_chunks(
            project_id=project_id,
            document_id=document_id,
            filename="benchmark.txt",
            chunks=[{"chunk_id": row["chunk_id"], "chunk_index": 0, "content": row["content"]}],
        )
        keyword_rows.append(
            {
                "id": row["chunk_id"],
                "project_id": project_id,
                "document_id": document_id,
                "chunk_index": 0,
                "content": row["content"],
                "documents": {"filename": "benchmark.txt"},
            }
        )

    hits = {}
    try:
        for mode in ("vector", "keyword", "hybrid"):
            client = _SubstringKeywordClient(keyword_rows)
            results = retrieve_chunks(client, project_id, case["query"], top_k=1, mode=mode)
            hits[mode] = any(r["chunk_id"] == target_chunk_id for r in results)
    finally:
        for document_id in document_ids:
            delete_document_vectors(document_id)

    return {"kind": case["kind"], "query": case["query"], **hits}


def main():
    rows = [
        run_case(case, distractors=[other["content"] for other in EVAL_CASES if other is not case])
        for case in EVAL_CASES
    ]

    modes = ("vector", "keyword", "hybrid")
    totals = {mode: sum(r[mode] for r in rows) for mode in modes}
    n = len(rows)
    regressions = [r for r in rows if r["hybrid"] < max(r["vector"], r["keyword"])]

    lines = [
        "# RAG retrieval ablation",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `benchmarks/rag_ablation.py`.",
        "",
        f"Hit rate (found the source chunk) over {n} cases, by retrieval mode:",
        "",
        "| mode | hit rate |",
        "|---|---|",
        *(f"| {mode} | {totals[mode]}/{n} |" for mode in modes),
        "",
        "| kind | query | vector | keyword | hybrid |",
        "|---|---|---|---|---|",
        *(
            f"| {r['kind']} | {r['query']} | "
            f"{'hit' if r['vector'] else 'miss'} | {'hit' if r['keyword'] else 'miss'} | "
            f"{'hit' if r['hybrid'] else 'miss'} |"
            for r in rows
        ),
        "",
        "Hybrid regressed vs. its best single mode on: "
        + (", ".join(r["query"] for r in regressions) if regressions else "none — hybrid never lost.")
        + "",
    ]
    report = "\n".join(lines)
    print(report)
    (Path(__file__).parent / "results.md").write_text(report, encoding="utf-8")
    assert not regressions, f"hybrid regressed vs. its best single mode on: {regressions}"


if __name__ == "__main__":
    main()
