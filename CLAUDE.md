# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

An AI Engineering Platform (multi-agent orchestration, RAG, memory, tool
calling, guardrails, evaluation, observability, cost/token control) built
against the spec in `docs/superpowers/specs/2026-08-09-ai-engineering-platform-design.md`.
**Read that file before making any architectural decision** — it is the
source of truth for scope, phasing, and the reasoning behind each choice.
This CLAUDE.md only covers execution rules; it does not restate the spec.

## Status

All four Phase 1 sub-projects are implemented:

- Phase 0 (walking skeleton).
- Phase 1 sub-project 1 (tool calling + "Signal & Trace" design system, per
  `docs/superpowers/specs/2026-08-09-phase1-tool-calling-and-design-system.md`).
- Phase 1 sub-project 2 (memory, per
  `docs/superpowers/specs/2026-08-11-phase1-memory-design.md` and
  `docs/superpowers/plans/2026-08-11-phase1-memory.md`).
- Phase 1 sub-project 3 (RAG, per
  `docs/superpowers/specs/2026-08-22-phase1-rag-design.md` and
  `docs/superpowers/plans/2026-08-22-phase1-rag.md`).
- Phase 1 sub-project 4 (multi-agent orchestration, per
  `docs/superpowers/specs/2026-08-29-phase2-multi-agent-orchestration-design.md`
  and `docs/superpowers/plans/2026-08-29-phase2-multi-agent-orchestration.md`) —
  implemented 2026-08-29. The single-node graph is now an `app/graph/`
  package: an `orchestrator` node (Groq JSON-mode routing, clamped in
  `routing.py` to `MAX_TURNS=4` / `MAX_TOOL_CALLS=3` / `MAX_RESEARCHER_RERUNS=1`)
  loops over `researcher` / `tool_runner` / `executor` / `verifier` workers.
  `tool_runner` uses Groq-native tool calling over the project's **GET-only**
  REST tools (`config.method != GET` → excluded from the loop; the model never
  sets the URL or headers). `runs.py` streams the graph and flushes
  `run_events` per node; setup events (`memory_recalled`, `retrieval_performed`)
  carry `turn: 0`. Tool config gained an optional `parameters` (JSON Schema)
  field — no migration, it lives inside the existing `config` JSONB. Frontend
  `Timeline` groups events into per-turn blocks with a summary line.
  Completes the master spec's Phase 1 exit criterion.

All seven migrations (`0001_init.sql`..`0007_eval.sql`) are applied. Supabase
Auth email confirmation is disabled for test signups. Qdrant is wired into
`docker-compose.yml` as a `qdrant` service (self-hosted, port 6333). A
private Supabase Storage bucket, `documents`, holds uploaded RAG source
files, with RLS on `storage.objects` scoping access by project ownership.
Phase 1 sub-project 4 and Phase 2 sub-project 2 (Observability) need no new
migration; Phase 2 adds `0005`/`0006`/`0007` and no new infra.

**Full-stack verification (2026-08-29, `docker compose up` — real Supabase +
Groq + Qdrant, no mocking): backend `pytest` 116 passed / 0 failed;** every
gated integration test green, including the multi-agent graph
(orchestrator → workers → verifier, `turn ≤ 4`), guardrail block + PII-mask
on completed runs, the Observability run-list, template-backed runs with a
`prompt_used` event, and a full evaluation run (answer + judge + persisted
metrics). Frontend: 54 vitest pass, `tsc --noEmit` + `ruff` clean.
**Playwright E2E: all 9 specs pass** — `golden-path`, `tool-calling`, `rag`,
`memory-recall` (×2), `guardrails`, `observability`, `prompt-manager`,
`evaluation` — run individually or in batches of ≤4. Running all 9
back-to-back still transiently fails a *different* spec each time under
concurrent-signup load on the single Supabase project (project link / auth
race) — resource contention in this environment, not a product bug;
`playwright.config.ts` pins `workers: 1`. Several E2E specs now assert with
`.first()` because the grouped `Timeline` / `TraceView` render event
payloads as JSON `<pre>` blocks that also contain the run's input/output
text. The tool-calling integration test and E2E hit `https://example.com`
(IANA-run) rather than the old flaky `https://httpbin.org/get`.

A real Guardrails bug was found and fixed during this verification: the Groq
injection classifier (`_CLASSIFIER_SYSTEM` in `app/guardrails/engine.py`)
over-flagged benign formatting instructions ("reply with just the word",
"reply 'ok'") as prompt injection → HTTP 422 → three pre-existing
memory/RAG-recall integration tests started failing. Fixed by tightening the
classifier prompt to exclude terse-answer / output-format / task-role
requests; real override/exfiltration/jailbreak attacks are still blocked
(re-verified live). The classifier stays fail-open.

Three pre-existing bugs, all outside their discovering sub-project's
original scope, were found and fixed because each sub-project's new
integration tests were the first to exercise these paths against the real
stack:
- `app/auth.py`'s JWT verification had no clock-skew leeway, so any client
  clock a few seconds behind Supabase's server clock made every fresh login
  fail with "the token is not yet valid". Fixed with `leeway=30` in
  `jwt.decode`.
- This `supabase-py` version's `.maybe_single().execute()` returns `None`
  outright (not a response with `.data = None`) when zero rows match, which
  crashed every "not found" 404 path once actually exercised with a real,
  authenticated, non-owning request. Fixed with a `fetch_maybe_one()` helper
  in `app/db.py`, applied in `runs.py` (`create_run`, `get_run`),
  `memories.py`, and `tools.py::invoke_tool` (fixed 2026-08-18, with a
  `test_invoke_nonexistent_tool_returns_404` regression test).
- `app/db.py::get_user_client` only propagated the authenticated user's JWT
  to the Postgres client (`client.postgrest.auth(token)`), not to the
  Storage client, which silently used the anon key for every Storage
  request. This went unnoticed until RAG's document upload needed
  owner-scoped Storage RLS. Fixed by also setting
  `client.options.headers["Authorization"]` before `client.storage` is
  first accessed (fixed 2026-08-22, with a `test_get_user_client_sets_
  bearer_token_for_storage_requests` regression test).

RAG's own frontend also had a real race condition, not a pre-existing bug:
`KnowledgeHubPanel`'s mount-time `listDocuments()` fetch could resolve
*after* a fast local upload (the first embedding call downloads model
weights, briefly making the upload request the slow one), silently
overwriting the just-uploaded document with the stale empty list. Fixed
with a `hasLocalUpdate` ref guard, the same pattern `ChatPanel` already uses
(`skipNextFetch`) for an analogous race.

**Phase 2 — Trust & Quality** — all four sub-projects implemented 2026-08-29
(specs + plans dated 2026-08-29 in `docs/superpowers/`):

1. **Guardrails** — `app/guardrails/` (heuristic injection patterns + one
   Groq JSON classifier when heuristics are clean; regex PII masking).
   `runs.py` pre-hook blocks (HTTP 422, `run.status="blocked"`, no graph
   spend) on injection or an `input_constraint` policy; post-hook masks PII
   in the answer **before** it reaches `runs.output`, the timeline, and
   `upsert_memory`. `guardrail_policies` + `guardrail_events` tables
   (`0005_guardrails.sql`). Injection + PII always on; GET-only tools in the
   loop; classifier is fail-open. `GuardrailsPanel` + a blocked notice in
   `ChatPanel` + pre/post rows in `Timeline`.
2. **Observability** — `GET /projects/{id}/runs` (all runs across a
   project's conversations); `retrieval_performed` payload gains
   `sources: [{filename, score}]`. `ObservabilityPanel` = run browser +
   `TraceView` (events + guardrails merged by time, **client-derived**
   per-step durations from `created_at` deltas, expandable payloads, error
   row). No migration, no `duration_ms`.
3. **Prompt Management** — `prompt_templates` + `prompt_template_versions`
   (append-only; `0006_prompts.sql`). `{{variable}}` inferred from the body
   (`app/prompts.py`). `RunCreate` takes `input` **xor**
   `{template_id, variables}`; `create_run` renders the latest version →
   `resolved_input` (used everywhere downstream) and logs a `prompt_used`
   event. `PromptManagerPanel` (library, editor = new version, history,
   test) + a template picker in `ChatPanel`.
4. **Evaluation** — golden datasets (`eval_datasets` / `eval_items` /
   `eval_runs` / `eval_results`; `0007_eval.sql`). `POST
   /eval-datasets/{id}/run` — per item one bare `generate()` answer + one
   Groq JSON judge call `{score, hallucinated, reason}` (`app/evals.py`);
   `aggregate()` → `accuracy` (fraction score≥0.7) / `hallucination_rate` /
   `mean_score`. Synchronous, `MAX_ITEMS=20`, judge fail-open. Not wired
   into `create_run` — an explicit offline harness. `EvaluationPanel`
   (dataset row editor, run, results table, history).

**Phase 2 verification status:** backend unit/API + pure-logic tests pass
(93 passed / 23 skipped with a real `GROQ_API_KEY`; skips need real
Supabase), `ruff` clean on all new code (one pre-existing `F841` in
`app/api/documents.py:26` is unrelated). Frontend: 54 vitest pass,
`tsc --noEmit` clean. Verified live against real Supabase + Groq:
`0005_guardrails.sql` applied and its API roundtrip + injection-block path
pass; the Groq injection classifier catches subtle attacks; PII masking
works; the eval judge scores correct answers 1.0 and a deliberately wrong
answer 0.0/hallucinated. **Pending:** `0006_prompts.sql` and
`0007_eval.sql` are **not yet applied** to Supabase (same manual step as
`0005`); Qdrant/Docker is down in this environment so the completed-run
post-hook path, the Prompt/Eval integration tests, and all Phase 2
Playwright specs (`guardrails`, `observability`, `prompt-manager`,
`evaluation`) + acceptance runs still need a full `docker compose up` stack.

Next up: master-spec **Phase 3 — Production Hardening** (Token Optimization
incl. the first second-model/provider tier + response caching + history
compression, Deployment, Cost Analytics, rate limiting/alerting).

Explicitly deferred, per each sub-project's spec non-goals (none started):
- **Sub-project 1 (tools):** SQL/Python/GitHub tool adapters.
- **Sub-project 2 (memory):** pruning/summarization/decay, a delete-memory
  UI, cross-project memory sharing, an explicit "remember this fact"
  affordance, reranking beyond raw vector similarity.
- **Sub-project 3 (RAG):** async/background indexing, cross-encoder
  re-ranking, semantic chunking, OCR for scanned PDFs, LLM-based chunk
  summarization, document versioning/re-upload, cross-project document
  sharing.
- **Sub-project 4 (multi-agent orchestration):** background/async run
  execution and a streaming (live) timeline; the `tool_permissions` table /
  per-tool `agent_callable` opt-in (the loop uses a blunt GET-only guard
  instead); verifier self-correction (bounce back to executor); free-form
  orchestrator routing (drop the fixed skeleton, raise `MAX_TURNS`);
  a second Groq model tier for cheap routing/verify calls (that is
  master-spec Phase 3); prompt-injection *detection* on RAG-sourced context
  (delivered by Phase 2 Guardrails).
- **Phase 2 sub-project 1 (Guardrails):** ML/NER-based PII, a policy rule
  DSL, output JSON-Schema enforcement, per-tool/per-agent policies,
  streaming redaction, rate limiting (Phase 3).
- **Phase 2 sub-project 2 (Observability):** explicit per-span
  `duration_ms` + its migration, OpenTelemetry/OTLP export, metrics
  rollups (p50/p95/error-rate), trace retention/TTL, run-list pagination,
  a live trace tail, log search.
- **Phase 2 sub-project 3 (Prompt Management):** declared variable metadata
  (defaults/required/types), per-run version pinning, rollback/diff UI,
  template delete/tags/search, templating logic (conditionals/loops),
  template-aware eval datasets.
- **Phase 2 sub-project 4 (Evaluation):** graph-backed or RAG/memory-aware
  eval, template datasets, dataset/item mutation after creation,
  import/export, scheduled/CI-triggered runs, run-to-run regression diff,
  latency/cost columns, a second judge model.

## Stack (locked — do not swap without updating the spec first)

- Backend: Python, FastAPI
- Agent orchestration: LangGraph
- LLM Gateway: Groq — the only provider until Phase 3. Do not add a
  provider-abstraction interface before a second provider is actually
  being wired in.
- DB + Auth: Supabase (Postgres + Supabase Auth). No custom auth/permission
  system — Row Level Security is the permissions story.
- Vector store: Qdrant, self-hosted via Docker.
- Frontend: Next.js (App Router), shadcn/ui, Tailwind.
- Deployment: Docker Compose (backend, frontend, Qdrant); Supabase is
  hosted, not in compose.

## Strict Practices for This Repo

These are enforcement rules specific to this project, on top of (not a
replacement for) the user's global coding/testing/security rules:

1. **No feature outside the current phase.** Check the spec's phase
   boundaries before adding any capability. Something belonging to a later
   phase does not get scaffolded early "since we're in there anyway."
2. **No wrapper layers around the four core dependencies** (LangGraph,
   Supabase client, Qdrant client, Groq client) unless a second concrete
   consumer of the abstraction already exists in the code.
3. **Every phase's exit criteria (in the spec) is its acceptance test.**
   Run against real Groq/Supabase/Qdrant — no mocking out these three in
   integration tests. Unit tests for pure logic may still use fixtures.
4. **Frontend nav items for un-built panels stay as disabled/empty states.**
   Never back a panel with fake or hardcoded data ahead of its phase.
5. **`context compression` has two owners, don't merge them:** RAG-time
   chunk compression is Phase 1 code in the retrieval path; run-history
   compression for cost control is Phase 3 code in the token-optimization
   path. See spec's "Resolved ambiguity" note.

## Commands

Backend (from `backend/`):
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`
- Test: `pytest -v`
- Single test: `pytest tests/test_runs.py::test_create_run_requires_auth -v`
- `QDRANT_URL` defaults to `http://qdrant:6333` (the Compose-internal
  hostname). Running the backend or tests **outside** `docker compose up`
  (e.g. `uvicorn` directly on the host) needs
  `QDRANT_URL=http://localhost:6333` — `docker compose up -d qdrant`
  publishes that port to the host — or `qdrant` won't resolve.

Frontend (from `frontend/`):
- Install: `npm install`
- Run: `npm run dev`
- Unit tests: `npx vitest run`
- Single unit test: `npx vitest run components/ChatPanel.test.tsx`
- E2E (needs the full stack running via `docker compose up` first, plus the Supabase migration applied and email confirmation disabled for test signups): `npx playwright test`

Full stack: `docker compose up` (from repo root, after `.env` has real Supabase/Groq values).

## Working with Agents & Skills in This Repo

The agents named in the user's global `agents.md` (planner, tdd-guide,
security-reviewer, etc.) are **not installed** in this environment — only
`senior-code-reviewer` exists as a custom agent. Use this mapping instead:

| Need | Use |
|---|---|
| Multi-step planning for a phase | `superpowers:writing-plans` skill, or the `Plan` agent for a second-opinion architecture pass |
| Locating code / "where is X" | `Explore` agent |
| New feature or bugfix | `superpowers:test-driven-development` skill (write test first) |
| After writing/changing non-trivial code | `senior-code-reviewer` agent |
| Auth, input handling, secrets, new endpoints | `security-review` skill |
| Frontend Playwright flows | `e2e-testing` / `e2e` skill |
| Docker/Compose changes | `docker-patterns` skill |
| Anything Groq/LLM-call-shaped that looks Claude-specific | `claude-api` skill does **not** apply here (this project uses Groq) — verify against Groq's own docs instead |

## Spec & Plan Documents

- `docs/superpowers/specs/` — design specs (one per major decision point;
  phase 0 spec already written, later phases may get sub-specs if they
  outgrow a single implementation plan — decided when reached, not now).
- Implementation plans (via `writing-plans`) will live alongside specs once
  Phase 0 planning starts.
