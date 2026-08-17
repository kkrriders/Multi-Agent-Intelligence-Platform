# AI Engineering Platform — Design Spec v1

**Date:** 2026-08-09
**Source:** `AI_Engineering_Platform_Blueprint_v1.pdf`
**Status:** Approved for planning

## Vision

A production-focused AI Engineering Platform that gives developers reusable AI
engineering building blocks — multi-agent orchestration, RAG, memory, tool
calling, guardrails, evaluation, observability, and cost/token control. It is
not a workflow builder (not a replacement for n8n or LangGraph); it's the
runtime and control plane you'd put those workflows on top of.

## Scope & Anti-Bloat Principles

These govern every phase below. When a phase's implementation plan is written,
anything that violates these gets cut or deferred, not built "for later":

1. **Each phase ships a working vertical slice.** No scaffolding, interfaces,
   or config for a capability that isn't being built in that phase.
2. **Reuse platform primitives directly.** LangGraph for orchestration,
   Supabase for DB/Auth, Qdrant client, shadcn/ui components — used as-is, no
   adapter/wrapper layers "for flexibility" until a second concrete need
   proves the abstraction is real.
3. **One LLM provider (Groq) until Phase 3.** No provider-abstraction
   interface until model routing actually requires a second provider.
4. **Observability starts as a Postgres table + structured logs.** No tracing
   pipeline (OpenTelemetry collectors, etc.) until Phase 2's Observability
   capability needs more than that.
5. **No custom permission system.** Supabase Auth + Row Level Security is the
   entire multi-user/permissions story unless a concrete gap appears.
6. **Frontend panels are built only as deep as the current phase's backend
   justifies.** A nav item for a future panel can exist as an empty state;
   it never ships with mock/fake data standing in for a real backend.

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| Agent orchestration | LangGraph |
| LLM Gateway | Groq |
| Relational DB + Auth | Supabase (Postgres + Supabase Auth, credentials provided when Phase 0 storage is built) |
| Vector store | Qdrant (self-hosted via Docker) |
| Frontend | Next.js (App Router) + shadcn/ui + Tailwind |
| Deployment | Docker Compose locally (backend, frontend, Qdrant); cloud targets in Phase 3 |

## Architecture Overview

Matches the PDF's High-Level Architecture Flow exactly:

```
User → Dashboard → Project → Run
  → Orchestration Runtime → Agent Runtime (Hub)
      → Knowledge | Tools | Memory | Prompt Manager
  → LLM Gateway → Guardrails → AI Response
      → Evaluation | Observability | Cost Analytics
```

And the Request Lifecycle (11 steps) is the contract every phase builds
toward — each phase implements the steps its capabilities own; steps owned by
a later phase are simply absent until then (e.g., no Guardrails validation
step exists until Phase 2 — the run just skips straight through).

## Traceability: PDF → Phase

Every PDF item maps 1:1 onto the PDF's own three-phase roadmap. The only
addition is **Phase 0**, which is not a fourth capability phase — it's the
minimum scaffolding (auth, project/run records, one agent, one LLM call, a
basic log) that the PDF's own Phase 1 silently assumes already exists.

| PDF item | PDF roadmap phase | This spec's phase |
|---|---|---|
| User/Dashboard/Project/Run records | *(implied prerequisite)* | Phase 0 |
| Orchestration Runtime / Agent Runtime (single agent) | *(implied prerequisite)* | Phase 0 |
| LLM Gateway | *(implied plumbing)* | Phase 0 |
| 1. Multi-Agent Orchestration (Planner/Researcher/Executor/Verifier) | 1 | 1 |
| 2. Advanced RAG | 1 | 1 |
| 3. Memory | 1 | 1 |
| 4. Tool Calling | 1 | 1 |
| 5. Guardrails | 2 | 2 |
| 6. Evaluation | 2 | 2 |
| 7. Observability (full trace store) | 2 | 2 |
| 9. Prompt Management | 2 | 2 |
| 8. Token Optimization | 3 | 3 |
| 10. Deployment | 3 | 3 |
| 11. Cost Analytics | 3 | 3 |

**Resolved ambiguity:** "context compression" appears twice in the source PDF
(under Advanced RAG #2 and Token Optimization #8). Split as:
- Phase 1: compressing *retrieved chunks* before they enter the prompt (RAG concern).
- Phase 3: compressing *conversation/context history* across a run for cost control (token-budget concern).

## Phase 0 — Walking Skeleton

**Goal:** prove User → Dashboard → Project → Run → Orchestrator → Agent → LLM
Gateway → Response end-to-end, deployed via Docker Compose. Nothing else.

**Backend:**
- Supabase Auth (email/password) wired into FastAPI via JWT verification.
- Schema: `projects`, `runs`, `run_events` (id, run_id, step_name, payload, created_at).
- One LangGraph graph: single agent node → Groq call → response.
- `POST /projects/:id/runs` — creates a run, executes the graph synchronously, writes `run_events` rows, returns the response.
- `GET /runs/:id` — returns run status + events for the timeline.

**Frontend:**
- Login/signup (Supabase Auth UI).
- Dashboard: list of projects, "new project" action.
- Project Workspace: Chat/Run panel only (send message, see response), minimal execution timeline rendered from `run_events`. All other workspace tabs (Prompt Manager, Knowledge Hub, etc.) exist as disabled/empty nav entries only.
- Landing page: hero + feature cards (static content, links to login).

**Explicitly deferred:** multi-agent, RAG, memory, tools, guardrails, evaluation, prompt management, token optimization, deployment UI, cost analytics.

**Exit criteria:** a logged-in user creates a project, starts a run, gets a real Groq-generated response, and sees it recorded as a run with events — running entirely from `docker compose up`.

## Phase 1 — Core Agent Capabilities

**Backend:**
- Expand the LangGraph graph to Planner → Researcher → Executor → Verifier, coordinated through the Orchestration Runtime.
- Advanced RAG: document upload → chunking → embedding → Qdrant storage; hybrid retrieval (keyword + vector) with metadata filtering; citations attached to responses; retrieved-chunk compression before prompt insertion.
- Memory: session memory (Postgres, scoped to a run/conversation), long-term/semantic memory (Qdrant, retrievable across runs).
- Tool Calling: REST, SQL, Python, GitHub adapters behind a common tool interface; a `tool_permissions` table gating which tools a project can use.

**Frontend:**
- Knowledge Hub: upload, indexing status, search, chunk inspection, citations.
- Tool Manager: connected tools, permissions, health/latency.
- Memory Explorer: conversation history, semantic memory search.
- Execution timeline upgraded to show agent handoffs, tool calls, and retrieval steps.

**Exit criteria:** a run can involve multiple coordinated agents, pull cited context from uploaded documents, recall prior session memory, and call at least one real tool — all visible in the timeline.

## Phase 2 — Trust & Quality

**Backend:**
- Guardrails: pre-hook (prompt injection detection, input schema validation) and post-hook (PII masking, output schema validation, policy checks) on the graph — implements lifecycle steps 3 and 7.
- Evaluation: golden dataset storage, regression test runner, quality scoring, confidence metrics — an offline/CI-able harness, not inline to every run.
- Observability: promote `run_events` into a proper trace store — full execution traces, tool logs, retrieval logs, latency, failure capture.
- Prompt Management: prompt template library with variables, version history, and a test-run feature — implements lifecycle step 2 (runs now load a template instead of a raw message).

**Frontend:**
- Guardrails panel: policies, validation rules, violations log.
- Evaluation panel: accuracy, hallucination rate, confidence, benchmark results.
- Observability panel: trace viewer, retrieval path, tool calls, timings.
- Prompt Manager panel: library, variables, version history, testing.

**Exit criteria:** a malicious/malformed input is caught by Guardrails and logged; a golden-dataset regression suite runs and scores a set of prompts; every run's full trace is inspectable in the Observability panel; prompts are versioned and editable without a code deploy.

## Phase 3 — Production Hardening

**Backend:**
- Token Optimization: response caching, conversation-history compression, model routing (this is the first point a second LLM/provider tier may appear), token analytics.
- Deployment: Docker image build/publish, cloud target configuration, deployment history.
- Cost Analytics: per-run token, latency, and model cost breakdown, cache-hit savings.
- General production hardening: rate limiting, error budgets/alerting on the observability data already collected.

**Frontend:**
- Cost Analytics panel: token usage, model costs, cache hits/savings.
- Deployment panel: Docker/cloud config, environments, deployment history.
- Settings panel.

**Exit criteria:** repeated runs hit cache and show reduced cost; a cost breakdown is visible per run and aggregated per project; the app can be deployed to a cloud target from the Deployment panel.

## Repo Structure

```
backend/
  app/
    api/            # FastAPI routers (projects, runs, knowledge, tools, ...)
    graph/           # LangGraph agent graphs, one module per phase's additions
    db/               # Supabase/Postgres models + queries
    vector/           # Qdrant client + retrieval logic
    llm/              # Groq client (LLM Gateway)
  tests/
frontend/
  app/                # Next.js App Router routes matching the Frontend IA
  components/
docker-compose.yml
docs/superpowers/specs/
```

## Cross-Cutting: Testing & Verification

Each phase's implementation plan (written separately via writing-plans) owns
its own test detail. At the spec level: every phase's exit criteria above is
the acceptance test for that phase — a phase isn't done until its exit
criteria is demonstrably true, run against the real Groq/Supabase/Qdrant
stack (no mocked-out core dependencies), per this project's standing testing
rules.

## Next Steps

Each phase above gets its own implementation plan (via `writing-plans`),
starting with Phase 0. Subsystems within Phase 1 and Phase 2 (RAG, Memory,
Tools; Guardrails, Evaluation, Observability, Prompt Management) may be
split into their own sub-specs if they prove too large for a single plan
once we're there — decided at that time, not speculatively now.
