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

Phase 0 (walking skeleton), Phase 1 sub-project 1 (tool calling + "Signal &
Trace" design system, per
`docs/superpowers/specs/2026-08-09-phase1-tool-calling-and-design-system.md`),
and Phase 1 sub-project 2 (memory, per
`docs/superpowers/specs/2026-08-11-phase1-memory-design.md` and
`docs/superpowers/plans/2026-08-11-phase1-memory.md`) are all implemented and
verified live as of 2026-08-17. All three migrations (`0001_init.sql`,
`0002_tools.sql`, `0003_memory.sql`) are applied; Supabase Auth email
confirmation is disabled for test signups. Qdrant is wired into
`docker-compose.yml` as a `qdrant` service (self-hosted, port 6333).

Verified against the real stack (real Supabase + Groq + Qdrant, no mocking):
29/30 backend pytest cases pass — the one failure
(`test_tools.py::test_create_list_and_invoke_tool`) is external `httpbin.org`
flakiness (503/timeout from httpbin itself), unrelated to any code here. All
24 frontend vitest cases pass. 3/4 Playwright E2E specs pass
(`golden-path.spec.ts`, `memory-recall.spec.ts` ×2); `tool-calling.spec.ts`
fails for the same unrelated httpbin reason.

Two pre-existing bugs, both outside the Memory sub-project's original scope,
were found and fixed because Memory's new integration tests were the first
to exercise these paths against real Supabase:
- `app/auth.py`'s JWT verification had no clock-skew leeway, so any client
  clock a few seconds behind Supabase's server clock made every fresh login
  fail with "the token is not yet valid". Fixed with `leeway=30` in
  `jwt.decode`.
- This `supabase-py` version's `.maybe_single().execute()` returns `None`
  outright (not a response with `.data = None`) when zero rows match, which
  crashed every "not found" 404 path once actually exercised with a real,
  authenticated, non-owning request. Fixed with a `fetch_maybe_one()` helper
  in `app/db.py`, applied in `runs.py` (`create_run`, `get_run`) and
  `memories.py`. **Not yet applied to `tools.py::invoke_tool`**, which has
  the identical latent bug — worth a follow-up fix when that file is next
  touched.

Next up per the master spec's sequencing (Tool Calling → Memory → RAG →
Multi-Agent Orchestration): the RAG sub-project — no spec/plan written yet.
Explicitly deferred from Phase 1 sub-project 1 (not started): SQL/Python/
GitHub tool adapters, and wiring tool calls into the LangGraph agent's
reasoning loop (belongs to the Multi-Agent Orchestration sub-project).
Explicitly deferred from Phase 1 sub-project 2 (not started, per its spec's
non-goals): memory pruning/summarization/decay, a delete-memory UI,
cross-project memory sharing, an explicit "remember this fact" tool-style
affordance, and reranking beyond raw vector similarity.

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
