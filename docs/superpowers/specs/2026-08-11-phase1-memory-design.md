# Phase 1, Sub-project 2: Memory

**Date:** 2026-08-11
**Status:** Approved for planning
**Builds on:** `2026-08-09-ai-engineering-platform-design.md` (master spec), Phase 1 Sub-project 1 (Tool Calling + Frontend Design System, complete)

## Scope

Second Phase 1 sub-project, per the master spec's sequencing decision: Tool
Calling → **Memory** → RAG → Multi-Agent Orchestration, dependency-first.
Implements the master spec's Memory line: "session memory (Postgres, scoped
to a run/conversation), long-term/semantic memory (Qdrant, retrievable
across runs)."

Unlike Tool Calling — which proved itself standalone via a direct `/invoke`
endpoint and explicitly deferred wiring into the agent's reasoning loop to
the Multi-Agent Orchestration sub-project — this sub-project wires memory
into the live agent call. The current graph (`graph.py`) is a single node
with no multi-agent structure, so injecting prior conversation turns and
retrieved semantic context into the Groq prompt is a small, self-contained
change that doesn't depend on Orchestration existing first. Without this
wiring, "recall prior session memory" (the master spec's Phase 1 exit
criterion) wouldn't be demonstrable — storage without recall isn't memory,
it's just a table.

Qdrant is self-hosted via Docker (per the decision recorded in the Tool
Calling sub-project spec); Qdrant Cloud remains the fallback if Docker
hosting becomes a problem. It is added to this repo for the first time here.

**Explicitly not in this sub-project:** memory pruning/summarization/decay
(long-term memory just accumulates), a delete-memory UI, cross-project
memory sharing, an explicit "remember this fact" tool-style affordance,
reranking beyond raw vector similarity. All reasonable later additions, none
required to prove the capability.

## Conversations

Today every chat send is a stateless, independent `run` — there is no
"conversation" entity, and `ChatPanel` only ever displays the single latest
run (it overwrites, doesn't append). Session memory requires a scope to
recall *within*, so this sub-project introduces `conversations` as an
explicit entity: a project can hold multiple named threads, each with its
own growing history. `runs` now belong to a conversation (and, transitively,
its project).

## Backend: Data Model

New migration `0003_memory.sql`:

```sql
create table conversations (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    title text not null default 'New conversation',
    created_at timestamptz not null default now()
);

alter table runs add column conversation_id uuid not null references conversations(id) on delete cascade;

alter table conversations enable row level security;

create policy "owner can access own conversations" on conversations
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
```

RLS follows the same owner-via-`project_id` pattern already established for
`tools`. Session memory itself gets **no new table** — it's `runs` rows
filtered by `conversation_id` and ordered by `created_at`. This reuses
storage that already exists rather than duplicating it.

`runs.project_id` is unchanged and stays populated on every insert — it's
what the existing `runs`/`run_events` RLS policies already key off, and
denormalizing it (instead of deriving it via a join through
`conversation_id → conversations.project_id`) avoids touching those
policies at all.

## Backend: Long-term / Semantic Memory (Qdrant)

**Infra:**
- `docker-compose.yml` gains a `qdrant` service (`qdrant/qdrant` image, port
  6333, a named volume for persistence).
- `backend/requirements.txt` gains `qdrant-client[fastembed]`.
- `Settings` (`config.py`) gains `qdrant_url` (default
  `http://qdrant:6333` inside compose).

**Why FastEmbed, not a hosted embedding API:** the stack's locked rule is
"Groq is the only provider until Phase 3," and Groq doesn't serve
embeddings. `qdrant-client[fastembed]` bundles a local ONNX embedding model
(`BAAI/bge-small-en-v1.5`, 384-dim) — no API key, no network call, no second
LLM/embedding *provider* in the sense the locked-stack rule means. This
keeps the rule intact instead of requesting an exception for it.

**Collection:** one collection, `memory`. Point id = `run_id` (uuid). Payload:
```json
{"project_id": "...", "conversation_id": "...", "run_id": "...", "input": "...", "output": "..."}
```
Embedded text: `f"User: {input}\nAssistant: {output}"`.

**Write:** after a run completes (output generated, `runs` row updated),
embed and upsert one point.

**Read:** on each new run, before invoking the graph, embed the new input
and search the `memory` collection filtered by `project_id` (long-term
memory is project-wide — it spans conversations, which is what
distinguishes it from session memory), `top_k=3`, with a score-threshold
cutoff so a project with little history doesn't inject noise.

## Backend: Graph & LLM

`app/llm.py`: `generate(prompt: str) -> str` becomes
`generate(messages: list[dict]) -> str`. It already builds a one-message
list internally (`[{"role": "user", "content": prompt}]`), so this is a
signature widening, not a rewrite. The one existing call site (`graph.py`)
and `tests/test_llm.py` update accordingly.

`app/graph.py`: `AgentState` gains two fields:
- `history: list[dict]` — prior turns in the conversation, converted to
  alternating `user`/`assistant` messages (each prior run's `input` →
  `user`, `output` → `assistant`).
- `memory_context: list[str]` — retrieved semantic snippets from Qdrant,
  injected as a leading system message when non-empty.

`run_agent` builds the full message list (system memory-context message, if
any → history messages → final user message) and passes it to
`llm.generate`.

## Backend: API

- `POST /projects/{project_id}/conversations` — create a conversation
  (name optional, defaults to `'New conversation'`)
- `GET /projects/{project_id}/conversations` — list a project's conversations
- `POST /conversations/{conversation_id}/runs` — **replaces**
  `POST /projects/{project_id}/runs`. Loads conversation history from
  `runs`, does the Qdrant search, invokes the graph with both, writes the
  Qdrant point after completion. Same response shape as before
  (`RunOut`).
- `GET /conversations/{conversation_id}/runs` — full ordered history for a
  conversation (used by both `ChatPanel` and Memory Explorer)
- `GET /projects/{project_id}/memories/search?q=` — semantic search over
  the project's long-term memory, for Memory Explorer

One new `run_events` step, `memory_recalled`, logging what was retrieved
(snippet count, top score) — so recall is visible in the Timeline, not just
happening invisibly inside the prompt.

## Frontend

- `ChatPanel`: gains a conversation selector (create new / pick existing)
  and renders the full growing message list for the selected conversation
  instead of only the latest run. This is a necessary fix, not scope creep
  — without it there's no visible evidence recall is working.
- New `MemoryExplorerPanel`, becomes the next enabled `WorkspaceNav` tab
  (after Chat/Run and Tool Manager): conversation list, and a semantic
  search box hitting `/projects/{id}/memories/search` that shows matched
  past turns with score and source conversation — matching the master
  spec's "Memory Explorer: conversation history, semantic memory search."

## Testing

Same discipline as prior sub-projects: real Supabase + real Qdrant for
integration tests (`docker compose up`, no mocking core dependencies),
credential-gated the same way existing Supabase integration tests are.
Unit tests for the FastEmbed embed/search helper and the
history-to-messages conversion (pure functions, no network needed).
Frontend: Vitest for `ChatPanel`'s history rendering and
`MemoryExplorerPanel`. Playwright: extend the golden path to cover "send
two messages in one conversation, second response reflects recall from the
first" and "semantic search finds an earlier turn from a different
conversation in the same project."

## Non-goals (explicit, so scope doesn't creep mid-build)

- Memory pruning, summarization, or decay — long-term memory just accumulates
- Delete-memory UI
- Cross-project memory sharing
- An explicit "remember this fact" tool-style affordance
- Reranking beyond raw vector similarity
- Multi-agent coordination (Orchestration sub-project's concern)
