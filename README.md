# AI Engineering Platform

A production-focused AI engineering platform: reusable building blocks for
multi-agent orchestration, RAG, memory, tool calling, guardrails, evaluation,
observability, and cost/token control. It's not a workflow builder (not a
replacement for n8n or LangGraph) — it's the runtime and control plane you'd
put those workflows on top of.

Full design rationale lives in
[`docs/superpowers/specs/2026-08-09-ai-engineering-platform-design.md`](docs/superpowers/specs/2026-08-09-ai-engineering-platform-design.md).

## Status

**Phase 0 (walking skeleton) complete.** The full request lifecycle — sign
up → create a project → send a message → get a real Groq-generated response
→ see it recorded as a run with an execution timeline — works end to end,
backend and frontend both build and run under Docker Compose.

Phase 1 (multi-agent orchestration, RAG, memory, tool calling) is next. See
[`docs/superpowers/plans/2026-08-09-phase-0-walking-skeleton.md`](docs/superpowers/plans/2026-08-09-phase-0-walking-skeleton.md)
for the full task-by-task build record.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python, FastAPI |
| Agent orchestration | LangGraph |
| LLM | Groq |
| Database + Auth | Supabase (Postgres, Row Level Security, Auth) |
| Vector store | Qdrant *(arrives in Phase 1)* |
| Frontend | Next.js (App Router), shadcn/ui, Tailwind |
| Deployment | Docker Compose |

## Getting started

1. **Environment variables.** Copy `.env.example` to `.env` and fill in your
   Supabase project URL/anon key and Groq API key:

   ```
   SUPABASE_URL=
   SUPABASE_ANON_KEY=
   GROQ_API_KEY=

   NEXT_PUBLIC_SUPABASE_URL=
   NEXT_PUBLIC_SUPABASE_ANON_KEY=
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

   (The `NEXT_PUBLIC_` values are the same Supabase URL/anon key, repeated —
   Next.js needs its own copies to inline into the frontend build.)

2. **Apply the database schema.** Open your Supabase project's SQL Editor
   and run the contents of
   [`backend/migrations/0001_init.sql`](backend/migrations/0001_init.sql).
   This creates the `projects`/`runs`/`run_events` tables with Row Level
   Security policies — RLS is this project's *only* authorization
   mechanism, there's no app-level permission code.

3. **Disable email confirmation for test signups** (or pre-confirm a test
   account) under Supabase Auth → Providers → Email, so signing up logs a
   user in immediately.

4. **Run it:**

   ```bash
   docker compose up
   ```

   Frontend: [http://localhost:3000](http://localhost:3000)
   Backend health check: [http://localhost:8000/health](http://localhost:8000/health)

## Project structure

```
backend/
  app/
    api/        # FastAPI routers (projects, runs)
    graph.py     # LangGraph agent graph
    llm.py        # Groq client (LLM Gateway)
    auth.py        # JWKS-based Supabase JWT verification
    db.py            # per-request Supabase client (forwards caller's token for RLS)
  migrations/         # SQL schema + RLS policies
  tests/               # pytest suite
frontend/
  app/                  # Next.js routes (landing, login, signup, dashboard, workspace)
  components/            # Chat/Run panel, execution timeline, auth form, etc.
  lib/                     # Supabase client + typed API wrapper
  e2e/                      # Playwright golden-path test
docker-compose.yml
```

## Development

See [`CLAUDE.md`](CLAUDE.md) for exact backend/frontend commands (install,
run, test, single-test invocations) and this repo's specific engineering
rules (locked stack, phase-boundary discipline, no application-level
permission checks — RLS only).

Quick reference:

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -v

# Frontend
cd frontend && npm install
npm run dev
npx vitest run
npx playwright test   # needs the full stack running, see steps 1-3 above
```
