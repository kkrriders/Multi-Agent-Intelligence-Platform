# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

An AI Engineering Platform: multi-agent orchestration, RAG, memory, tool
calling, guardrails, evaluation, observability, and cost/token control,
built against the design spec in
`docs/superpowers/specs/2026-08-09-ai-engineering-platform-design.md`.
**Read that spec before making any architectural decision** — it is the
source of truth for scope, phasing, and the reasoning behind each choice.
This file covers execution rules only; it does not restate the spec.

## Status

The full platform is implemented. Every workspace nav tab is backed by a
real panel — there are no placeholder/empty-state panels.

Capabilities in the codebase today:

- **Orchestration** — an `app/graph/` LangGraph package: an `orchestrator`
  node routes over `researcher` / `tool_runner` / `executor` / `verifier`
  workers, bounded by `MAX_TURNS` / `MAX_TOOL_CALLS` / `MAX_RESEARCHER_RERUNS`
  in `app/graph/routing.py`. `runs.py` streams the graph and writes
  `run_events` per node.
- **Tool calling** — Groq-native function calling over the project's
  **GET-only** REST tools (non-GET tools are excluded from the loop; the
  model never sets the URL or headers).
- **RAG** — document upload → chunk → embed → Qdrant; hybrid
  (vector + keyword) retrieval with citations. Source files live in a
  private Supabase Storage bucket (`documents`) with owner-scoped RLS.
- **Memory** — per-conversation history plus semantic recall from Qdrant.
- **Guardrails** — `app/guardrails/`: heuristic + one Groq-classifier
  injection check (pre-hook, blocks with HTTP 422 and no graph spend) and
  regex PII masking (post-hook, before the answer reaches `runs.output`,
  the timeline, or memory). Both always on; classifier is fail-open.
- **Prompt management** — append-only `prompt_templates` /
  `prompt_template_versions`; a run takes `input` xor
  `{template_id, variables}` and renders the latest version.
- **Evaluation** — golden datasets with a synchronous answer + Groq-judge
  harness (`app/evals.py`); offline, not wired into `create_run`.
- **Observability** — `GET /projects/{id}/runs` + a trace view with
  client-derived per-step durations.
- **Token optimization** — a second Groq model tier (`MODEL_CHEAP`) for
  classification-shaped calls, a whole-run `response_cache`, and
  threshold-triggered conversation-history summarization; per-call token
  usage and USD cost recorded on every run.
- **Cost analytics** — `GET /projects/{id}/cost` aggregation + panel.
- **Production hardening** — per-user run rate limiting; per-project
  `alert_rules` (error rate / daily spend / p95 latency) evaluated after
  each run, writing `alert_events` and optionally firing a webhook.
- **Deployment** — hardened multi-stage non-root images, `deploy_targets`
  config, and a build/publish history; the build endpoint shells out to
  `docker`/`git` and is gated behind `ENABLE_DEPLOY_API` (default off).

## Stack (locked — do not swap without updating the spec first)

- Backend: Python, FastAPI
- Agent orchestration: LangGraph
- LLM Gateway: Groq. `MODEL` for generation, `MODEL_CHEAP` for
  classification-shaped calls — both are Groq models. Do **not** add a
  provider-abstraction interface unless a second provider is actually being
  wired in.
- DB + Auth: Supabase (Postgres + Supabase Auth). No custom
  auth/permission system — Row Level Security is the entire permissions
  story.
- Vector store: Qdrant, self-hosted via Docker.
- Frontend: Next.js (App Router), shadcn/ui, Tailwind.
- Deployment: Docker Compose (backend, frontend, Qdrant); Supabase is
  hosted, not in compose.

## Strict Practices for This Repo

On top of (not a replacement for) the user's global coding/testing/security
rules:

1. **Nothing beyond what a spec covers.** Check the spec's scope and
   phase boundaries before adding any capability; don't scaffold future
   work "since we're in there anyway."
2. **No wrapper layers around the four core dependencies** (LangGraph,
   Supabase client, Qdrant client, Groq client) unless a second concrete
   consumer of the abstraction already exists in the code.
3. **Exit criteria in the spec are the acceptance test.** Integration
   tests run against real Groq / Supabase / Qdrant — never mock those
   three. Pure-logic unit tests may use fixtures.
4. **Never back a panel with fake or hardcoded data.**
5. **`context compression` has two distinct owners — keep them separate:**
   RAG-time chunk compression in the retrieval path vs. run-history
   summarization for cost control in the token-optimization path.

## Operational Notes

- **Migrations** (`backend/migrations/0001…0010`) are applied by hand in
  the Supabase SQL editor. All are currently applied. A new migration is
  not live until that manual step is done.
- Supabase Auth email confirmation is disabled for test signups.
- Qdrant is pinned to `qdrant/qdrant:v1.19.0` in `docker-compose.yml`.
  **Do not downgrade below the version that last wrote `qdrant_data`** — it
  panics on the older on-disk collection format.
- The frontend runtime image sets `ENV HOSTNAME=0.0.0.0` (Next standalone
  otherwise binds to Docker's per-container `HOSTNAME` and the healthcheck
  fails). The backend image runs as a non-root user with a writable
  `$HOME` so fastembed / `huggingface_hub` can cache the embedding model.
- `playwright.config.ts` pins `workers: 1`. Specs pass individually and in
  small batches; running all of them back-to-back can transiently flake on
  the single shared Supabase project (concurrent-signup contention) — this
  is environmental, not a product bug.
- One pre-existing `ruff` `F841` in `app/api/documents.py:26` is known and
  unrelated to any current work.

## Commands

Backend (from `backend/`):
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`
- Test: `pytest -v` — single: `pytest tests/test_runs.py::test_name -v`
- Running backend or tests **outside** `docker compose up` needs
  `QDRANT_URL=http://localhost:6333` (plus `docker compose up -d qdrant`);
  the default `http://qdrant:6333` only resolves inside Compose.
- Gated integration tests also need real `.env` values and a
  `SUPABASE_TEST_USER_TOKEN` (a signed-in test user's access token).

Frontend (from `frontend/`):
- Install: `npm install` — Run: `npm run dev`
- Unit tests: `npx vitest run` — single:
  `npx vitest run components/ChatPanel.test.tsx`
- E2E: `npx playwright test` (needs the full stack up via
  `docker compose up`, migrations applied, email confirmation off).

Full stack: `docker compose up` from the repo root, after `.env` has real
Supabase/Groq values.

## Working with Agents & Skills in This Repo

The agents in the user's global `agents.md` (planner, tdd-guide,
security-reviewer, …) are **not installed** here — only
`senior-code-reviewer` exists as a custom agent. Use this mapping:

| Need | Use |
|---|---|
| Multi-step planning | `superpowers:writing-plans`, or the `Plan` agent for a second-opinion pass |
| Locating code / "where is X" | `Explore` agent |
| New feature or bugfix | `superpowers:test-driven-development` (test first) |
| After non-trivial code changes | `senior-code-reviewer` agent |
| Auth, input handling, secrets, new endpoints | `security-review` skill |
| Frontend Playwright flows | `e2e-testing` / `e2e` skill |
| Docker / Compose changes | `docker-patterns` skill |
| Anything LLM-call-shaped | `claude-api` does **not** apply — this project uses Groq; check Groq's own docs |

## Spec Documents

`docs/superpowers/specs/` holds the master design spec plus one design
spec per sub-project; `docs/superpowers/plans/` holds the matching
implementation plans. Consult the relevant spec for design rationale and
the deferred/non-goal list before extending any capability.
