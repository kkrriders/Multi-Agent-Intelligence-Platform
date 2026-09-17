# RAG retrieval benchmark — hardened (2026-09-13)

Replaces the old `rag_ablation.py`, which faked keyword search with a
substring-match stub and measured only hit@1 over 5 easy cases (always
100%). This version runs against the **real stack**: a real Supabase
`document_chunks` row per case (Postgres full-text search via the generated
`content_tsv` column, `migrations/0004_rag.sql`), a real Qdrant vector per
case, and the actual `app.rag.retrieve_chunks()` code path — nothing
simulated. Also adds a real reranking stage that didn't exist before.

```
python benchmarks/rag_ablation.py
```

**Two things you need locally that the old version didn't require** (both
are one-shot environment gotchas discovered by actually running this, not
code changes):
- `QDRANT_URL=http://localhost:6333` — `app/config.py`'s default
  (`http://qdrant:6333`) is the docker-network hostname, which only resolves
  from inside `docker compose`. Running the benchmark from the host needs
  the published port instead.
- `HF_HUB_DISABLE_XET=1` — the `fastembed` cross-encoder's first download
  from huggingface.co hit intermittent `ConnectError`/`RemoteProtocolError`
  resets on this network via the default xet-accelerated transfer path;
  disabling it downloads over plain HTTPS instead. Only needed once (model
  caches locally after).

## Real numbers

15 queries against a shared pool of 18 chunks (13 case chunks + 3 deliberate
near-miss "ambiguous" chunks — see below):

| mode | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|
| vector only | 0.867 | 0.933 | 1.000 | 0.917 |
| keyword only (real Postgres FTS) | 0.467 | 0.467 | 0.467 | 0.467 |
| hybrid (vector + FTS) | 0.867 | 0.933 | 1.000 | 0.917 |
| **hybrid + rerank** (fastembed cross-encoder, `Xenova/ms-marco-MiniLM-L-6-v2`) | **0.933** | **1.000** | 1.000 | **0.967** |

**Resume line**: *"Reranking a hybrid vector+FTS retrieval pipeline with a
cross-encoder improved Recall@1 from 86.7% to 93.3% and MRR from 0.917 to
0.967 on a 15-query live benchmark; keyword-only search alone recovered
only 46.7% of paraphrased queries, confirming semantic retrieval is load-
bearing, not redundant, in this system."*

## What the reranker actually fixed, and where it made things worse

Reranking corrected both of vector-only's misses:
- *"when do people have to leave the building"* → office-hours chunk moved
  from rank 2 to rank 1.
- *"how much paid time off do I get annually"* → vacation-days chunk moved
  from **rank 4** to rank 1 (the biggest single fix).

**It also caused one real regression — reported honestly, not hidden**: on
the deliberately ambiguous case *"am I eligible for the annual bonus"*,
hybrid alone correctly ranked "Full-time employees are eligible... after
six months" at #1. The reranker demoted it to #2, promoting "Contractors
are not eligible for the annual bonus program" instead — both chunks are
about the same policy area and the query doesn't specify employment type,
so the cross-encoder's more nuanced semantic judgment picked the wrong side
of a genuinely ambiguous case. This is the expected failure mode of
reranking on close near-misses, not a bug — and it's exactly why the
"ambiguous" case category exists in this eval instead of only easy cases.

Keyword-only's weakness is exactly what real Postgres FTS should show: it
found all 4 rare-term/exact-code cases and 3 cases sharing literal
vocabulary, but **zero** of the 5 pure-paraphrase cases (`content_tsv` needs
shared words, not meaning) — the honest reason hybrid/vector dominates here.

## Caveats — read before quoting these numbers elsewhere

- **n=15 queries is still small.** These numbers will move with more cases;
  treat them as directionally real, not a tight confidence interval.
- Case difficulty was hand-authored (including which chunk is the ambiguous
  "target"), not drawn from real user queries or graded by an independent
  judge — this is a controlled benchmark of the retrieval *mechanism*, not
  a production-traffic relevance study.
- Cleanup: every seeded project/document/chunk/vector is deleted at the end
  of the run regardless of outcome (confirmed: 0 leftover Supabase rows
  after this run). The reused shared test account's OTHER data (from
  `run-traffic.ps1`, etc.) is untouched.
- Still not built: nDCG (Recall@K + MRR cover the resume-relevant claims
  here; nDCG matters more with graded relevance labels, which this binary
  target/non-target eval doesn't have), and a production-scale
  relevance-judged benchmark (hundreds of real queries against real
  documents with independent relevance grading) — this stays a controlled
  mechanism test, not a claim about real-world RAG quality at scale.
