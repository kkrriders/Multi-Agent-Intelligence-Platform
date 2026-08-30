# AI Engineering Platform

A production-focused runtime and control plane for LLM applications. It
bundles the building blocks you normally re-implement on every project —
multi-agent orchestration, retrieval-augmented generation, memory, tool
calling, guardrails, evaluation, observability, and cost control — behind a
single API and web workspace.

It is **not** a workflow builder. It is the layer you run your agents and
prompts *on*: every request goes through the same lifecycle (guardrails →
prompt resolution → memory recall → retrieval → orchestration → guardrails
→ response) and every request is recorded as an inspectable, costed run.

The full design rationale and scope live in
[`docs/superpowers/specs/`](docs/superpowers/specs/).

---

## Features

| Area | What it does |
|---|---|
| **Multi-agent orchestration** | A LangGraph graph with an `orchestrator` node that routes over `researcher`, `tool_runner`, `executor` and `verifier` workers. Bounded loop (`MAX_TURNS=4`, `MAX_TOOL_CALLS=3`, `MAX_RESEARCHER_RERUNS=1`). Every node emits a timestamped `run_events` row. |
| **Advanced RAG** | Upload documents → chunk → embed (`BAAI/bge-small-en-v1.5`) → store in Qdrant. Hybrid retrieval (vector + Postgres full-text keyword) with per-chunk citations attached to the answer. Source files live in a private Supabase Storage bucket with owner-scoped RLS. |
| **Memory** | Per-conversation history is replayed into the prompt; long-term semantic memory is written to Qdrant after each run and recalled across conversations by similarity. |
| **Tool calling** | Register REST tools per project; the agent loop uses Groq-native function calling over the **GET-only** subset (non-GET tools are never callable by the model, and the model never sets the URL or headers). Tools can also be invoked directly through the API. |
| **Guardrails** | Pre-hook: heuristic prompt-injection patterns plus one Groq classifier when the heuristics are clean, and configurable `input_constraint` policies (max length, term blocklist). A blocked run returns HTTP 422 with no graph spend. Post-hook: regex PII masking applied to the answer *before* it reaches the run output, the timeline, or memory. |
| **Prompt management** | Append-only prompt templates with versioning. `{{variable}}` placeholders are inferred from the body. A run takes either a raw `input` or `{template_id, variables}`; the latest version is rendered server-side and logged as a `prompt_used` event. |
| **Evaluation** | Golden datasets of `{input, expected}` items. `POST /eval-datasets/{id}/run` produces one bare answer + one Groq judge verdict (`score`, `hallucinated`, `reason`) per item, then aggregates `accuracy` (fraction ≥ 0.7), `hallucination_rate`, and `mean_score`. Synchronous, capped at 20 items, offline (not wired into `create_run`). |
| **Observability** | `GET /projects/{id}/runs` lists every run across a project. A trace view merges graph events and guardrail events by time with client-derived per-step durations, expandable payloads, tool I/O, the retrieval path, and captured errors. |
| **Token optimization** | A second, cheaper Groq model tier (`MODEL_CHEAP`) for classification-shaped calls (routing, verification, judging, injection classification). A whole-run response cache keyed on project + input + retrieved chunk set + history length. Threshold-triggered summarization of older conversation turns. Per-call token usage and USD cost are recorded on every run. |
| **Cost analytics** | `GET /projects/{id}/cost` returns project totals, a per-model breakdown, a 30-day daily series, estimated cache savings, and recent-run rows. Per-node model/token/cost also appears inline in the trace view. |
| **Production hardening** | Per-authenticated-user run rate limiting (default 20/min, `429` on exceed). Per-project alert rules (`error_rate`, `daily_spend`, `p95_latency`) evaluated after every run; a breach writes an `alert_events` row and optionally fires a webhook. All alerting is fail-open. |
| **Deployment** | Hardened multi-stage, digest-pinned, non-root container images with health checks. A deploy-target registry stores registry/repo/env-var config. `POST /deployments` builds and pushes tagged images and records a build/publish history; it shells out to `docker`/`git` and is gated behind `ENABLE_DEPLOY_API` (off by default). |

Every capability has a matching panel in the web workspace — there are no
placeholder screens.

---

## Architecture

```
User → Web workspace → Project → Run
  │
  ├─ Guardrails (pre)      prompt-injection + input policy check → block or continue
  ├─ Prompt resolution     raw input, or render the latest template version
  ├─ Memory recall         conversation history + semantic memory from Qdrant
  ├─ Retrieval             hybrid search over the project's documents (Qdrant + Postgres FTS)
  ├─ Response cache         exact-context hit → skip the graph entirely
  ├─ Orchestration          LangGraph: orchestrator → researcher / tool_runner / executor / verifier
  ├─ Guardrails (post)      PII masking on the answer
  └─ Persist                run row + run_events + per-call token/cost + memory upsert + alert evaluation
```

- **Backend** — FastAPI. One router per capability under `app/api/`. The
  orchestration graph is an `app/graph/` package; retrieval, memory,
  guardrails, cost, cache, history-compression and deploy logic are
  separate modules so each is unit-testable in isolation.
- **LLM Gateway** — `app/llm.py` wraps the Groq client. Two model
  constants: `MODEL` (`openai/gpt-oss-120b`) for generation and
  `MODEL_CHEAP` (`openai/gpt-oss-20b`) for classification-shaped calls. A
  context-var accumulator records token usage per call without threading
  state through call sites.
- **Auth & permissions** — Supabase Auth issues JWTs; the backend verifies
  them via JWKS and forwards the caller's token to a per-request Supabase
  client. **Row Level Security is the only authorization mechanism** —
  there is no application-level permission code.
- **Frontend** — Next.js (App Router) with a landing page, auth screens, a
  project dashboard, and a per-project workspace whose left nav switches
  between the capability panels.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| Agent orchestration | LangGraph |
| LLM | Groq (`openai/gpt-oss-120b` + `openai/gpt-oss-20b`) |
| Database + Auth | Supabase (Postgres, Row Level Security, Supabase Auth) |
| Object storage | Supabase Storage (private `documents` bucket) |
| Vector store | Qdrant (self-hosted via Docker) |
| Embeddings | `fastembed` — `BAAI/bge-small-en-v1.5` (384-dim, cosine) |
| Frontend | Next.js (App Router), shadcn/ui, Tailwind CSS |
| Tests | pytest, Vitest, Playwright |
| Packaging | Docker Compose |

---

## Repository layout

```
backend/
  app/
    api/                FastAPI routers, one per capability
      projects.py  conversations.py  runs.py  tools.py  documents.py
      memories.py  guardrails.py  prompts.py  evals.py
      analytics.py  alerts.py  deployments.py
    graph/              LangGraph orchestration package
      routing.py  workers.py  state.py  tool_schemas.py
    guardrails/         injection heuristics + classifier, PII patterns
    tools/              REST tool adapter
    llm.py             Groq client + model tiers + usage accumulator
    rag.py              chunking, embedding, hybrid retrieval
    memory.py           conversation + semantic memory
    prompts.py           template rendering + variable inference
    evals.py              answer + judge harness, aggregation
    cost.py               per-model USD pricing
    cache.py               response-cache key
    history.py             conversation-history summarization
    analytics.py          cost aggregation
    alerts.py             alert-rule evaluation + webhook
    deploy.py             docker/git argv builders + input validation
    auth.py  db.py  config.py  models.py
  migrations/          0001_init.sql … 0010_deployment.sql
  tests/               pytest suite (unit + gated integration)
frontend/
  app/                 landing, login, signup, dashboard, workspace routes
  components/           workspace panels (Chat, Knowledge Hub, Tool Manager,
                        Memory Explorer, Guardrails, Observability, Prompt
                        Manager, Evaluation, Cost Analytics, Settings,
                        Deployment) + trace/timeline views
  lib/                  Supabase client + typed API wrapper
  e2e/                  Playwright specs (one per capability)
docker-compose.yml
docs/superpowers/       design specs + implementation plans
```

---

## Getting started

### Prerequisites

- Docker + Docker Compose
- A Supabase project (URL + anon key)
- A Groq API key

### 1. Environment variables

Copy `.env.example` to `.env` and fill it in:

```dotenv
SUPABASE_URL=
SUPABASE_ANON_KEY=
GROQ_API_KEY=

# Same Supabase URL/anon key again — Next.js inlines its own copies at build time
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Apply the database schema

Open the Supabase project's **SQL Editor** and run each file in
`backend/migrations/` in order, `0001_init.sql` through
`0010_deployment.sql`. Each creates its tables plus Row Level Security
policies. There is no migration runner — this is a manual step, and a
migration is not live until it has been applied here.

### 3. Configure Supabase Auth

Under **Auth → Providers → Email**, disable "Confirm email" (or
pre-confirm your test account) so signing up logs a user in immediately.

The RAG feature also needs a **private Storage bucket named `documents`**
with an RLS policy on `storage.objects` scoping access by project
ownership (created via the Supabase dashboard or SQL).

### 4. Run it

```bash
docker compose up
```

- Web workspace: <http://localhost:3000>
- API: <http://localhost:8000> — health check at `/health`
- Qdrant: <http://localhost:6333>

---

## Configuration

Backend settings (environment variables, read by `app/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | — | Supabase project |
| `GROQ_API_KEY` | — | Groq LLM Gateway |
| `QDRANT_URL` | `http://qdrant:6333` | Vector store. Use `http://localhost:6333` when running the backend outside Compose. |
| `CACHE_MAX_AGE_DAYS` | `7` | Response-cache entry TTL |
| `HISTORY_TOKEN_BUDGET` | `3000` | Replayed-history size before summarization kicks in |
| `HISTORY_KEEP_TURNS` | `3` | Recent turns always replayed verbatim |
| `RUN_RATE_LIMIT_PER_MIN` | `20` | Per-user run cap; `0` disables |
| `ENABLE_DEPLOY_API` | `false` | Enables the `POST /deployments` docker/git shell-out |

---

## API overview

All routes require a `Authorization: Bearer <supabase-jwt>` header; RLS
scopes every query to the caller.

**Projects & conversations**
```
POST   /projects
GET    /projects
POST   /projects/{id}/conversations
GET    /projects/{id}/conversations
```

**Runs**
```
POST   /conversations/{id}/runs        # input xor {template_id, variables}
GET    /conversations/{id}/runs
GET    /projects/{id}/runs             # all runs in the project (observability)
GET    /runs/{id}
```

**Knowledge (RAG)**
```
POST   /projects/{id}/documents        # multipart upload
GET    /projects/{id}/documents
DELETE /projects/{id}/documents/{doc_id}
```

**Tools**
```
POST   /projects/{id}/tools
GET    /projects/{id}/tools
POST   /tools/{id}/invoke
```

**Memory**
```
GET    /projects/{id}/memories/search?q=...
```

**Guardrails**
```
GET    /projects/{id}/guardrail-policies
PUT    /projects/{id}/guardrail-policies/{kind}
GET    /projects/{id}/guardrail-events
```

**Prompt management**
```
POST   /projects/{id}/prompt-templates
GET    /projects/{id}/prompt-templates
PUT    /prompt-templates/{id}              # new version
GET    /prompt-templates/{id}/versions
```

**Evaluation**
```
POST   /projects/{id}/eval-datasets
GET    /projects/{id}/eval-datasets
GET    /eval-datasets/{id}
POST   /eval-datasets/{id}/run
GET    /eval-datasets/{id}/runs
```

**Cost analytics**
```
GET    /projects/{id}/cost
```

**Alerting & limits**
```
GET    /config/limits
GET    /projects/{id}/alert-rules
POST   /projects/{id}/alert-rules         # upsert on (project, kind)
PATCH  /projects/{id}/alert-rules/{rule_id}
DELETE /projects/{id}/alert-rules/{rule_id}
GET    /projects/{id}/alert-events
```

**Deployment**
```
GET    /deploy-targets
POST   /deploy-targets
DELETE /deploy-targets/{id}
GET    /deployments
POST   /deployments                       # 503 unless ENABLE_DEPLOY_API=true
```

---

## Data model

Ten SQL migrations under `backend/migrations/`, each with Row Level
Security policies:

| Migration | Tables |
|---|---|
| `0001_init` | `projects`, `runs`, `run_events` |
| `0002_tools` | `tools` |
| `0003_memory` | `conversations` (+ `runs.conversation_id`) |
| `0004_rag` | `documents`, `document_chunks` |
| `0005_guardrails` | `guardrail_policies`, `guardrail_events` |
| `0006_prompts` | `prompt_templates`, `prompt_template_versions` |
| `0007_eval` | `eval_datasets`, `eval_items`, `eval_runs`, `eval_results` |
| `0008_token_optimization` | `run_llm_calls`, `response_cache` (+ token/cost columns on `runs`, summary columns on `conversations`) |
| `0009_production_hardening` | `alert_rules`, `alert_events` |
| `0010_deployment` | `deploy_targets`, `deployments` |

Semantic memory and document embeddings live in two Qdrant collections
(`memory`, `documents`), not in Postgres.

---

## Development

```bash
# Backend (from backend/)
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -v                     # add QDRANT_URL=http://localhost:6333 outside Compose

# Frontend (from frontend/)
npm install
npm run dev
npx vitest run                # unit + component tests
npx tsc --noEmit              # type check
npx playwright test           # E2E — needs the full stack up (see Getting started)
```

**Testing model.** Pure logic (cost math, cache keys, token estimation,
alert evaluation, deploy-argv validation, prompt rendering) is unit-tested
with fixtures. Integration tests run against **real** Groq, Supabase and
Qdrant — those three are never mocked — and are skip-gated on the
credentials being present (`.env` values plus a `SUPABASE_TEST_USER_TOKEN`
for a signed-in test user). Each capability also has a Playwright spec
under `frontend/e2e/`.

---

## Deployment & hardening

The container images are production-oriented:

- **Multi-stage** builds; the runtime stage carries only what it needs
  (the frontend uses Next.js `output: "standalone"`).
- **Digest-pinned** base images (`python:3.11-slim@sha256:…`,
  `node:20-slim@sha256:…`).
- **Non-root** at runtime (backend uid 10001 with a writable `$HOME` for
  the embedding-model cache; frontend as `node`).
- **`HEALTHCHECK`** on both, wired into Compose with `restart:
  unless-stopped` and memory limits. Qdrant is pinned to `v1.19.0` — do
  not downgrade below the version that last wrote the `qdrant_data`
  volume.

The in-app **Deployment panel** stores deploy-target config (registry,
image repo, env-var set) and, when `ENABLE_DEPLOY_API=true` and the docker
socket is mounted into the backend container, builds and pushes tagged
images and records the build log. Running the published images on a cloud
host is an operator step using the stored target config.

---

## Security model

- **Authorization is Row Level Security only.** Every table's policies
  scope rows to the owning user (via `projects.owner_id` or
  `created_by = auth.uid()`); the backend forwards the caller's JWT to
  Postgres and adds no permission checks of its own.
- **Prompt injection** is screened on both the user input and
  RAG-retrieved context before the graph runs; a match blocks the run.
- **PII** (emails, phone numbers, …) is regex-masked out of the answer
  before it is persisted or shown.
- **Tool calls** the agent can make are restricted to GET requests; the
  model cannot choose the URL or headers.
- The **deploy build endpoint** shells out only through argument lists
  (never a shell string), validates every interpolated value, is
  owner-only, and is disabled by default.

---

## Documentation

- [`docs/superpowers/specs/`](docs/superpowers/specs/) — the master design
  spec and one design spec per capability (scope, rationale, non-goals).
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — the matching
  implementation plans.
- [`CLAUDE.md`](CLAUDE.md) — engineering rules and operational notes for
  working in this repository.
