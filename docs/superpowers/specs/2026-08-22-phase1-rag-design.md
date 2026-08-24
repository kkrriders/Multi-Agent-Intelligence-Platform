# Phase 1, Sub-project 3: RAG

**Date:** 2026-08-22
**Status:** Approved for planning
**Builds on:** `2026-08-09-ai-engineering-platform-design.md` (master spec), Phase 1 Sub-project 1 (Tool Calling, complete), Phase 1 Sub-project 2 (Memory, complete)

## Scope

Third Phase 1 sub-project, per the master spec's sequencing decision: Tool
Calling → Memory → **RAG** → Multi-Agent Orchestration, dependency-first.
Implements the master spec's Advanced RAG line: "document upload → chunking
→ embedding → Qdrant storage; hybrid retrieval (keyword + vector) with
metadata filtering; citations attached to responses; retrieved-chunk
compression before prompt insertion."

Like Memory, this sub-project wires directly into the live agent call
(`graph.py`) rather than deferring to Multi-Agent Orchestration — the
current graph is still a single node, so injecting retrieved document
context into the Groq prompt is a small, self-contained addition alongside
the `memory_context` injection already there. Without this wiring,
"pull cited context from uploaded documents" (the master spec's Phase 1
exit criterion) isn't demonstrable.

**Explicitly not in this sub-project:** async/background indexing (upload
is synchronous), chunk re-ranking beyond a simple merge of keyword+vector
results, semantic (non-fixed-size) chunking, OCR for scanned PDFs,
retrieved-chunk compression via an LLM summarizer (compression here means a
hard character cap, not summarization), document versioning/re-upload,
cross-project document sharing.

## Backend: Data Model

New migration `0004_rag.sql`:

```sql
create table documents (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    filename text not null,
    mime_type text not null,
    storage_path text not null,
    status text not null default 'pending', -- pending | indexed | failed
    error text,
    created_at timestamptz not null default now()
);

create table document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    project_id uuid not null references projects(id) on delete cascade,
    chunk_index int not null,
    content text not null,
    content_tsv tsvector generated always as (to_tsvector('english', content)) stored,
    created_at timestamptz not null default now()
);

create index document_chunks_tsv_idx on document_chunks using gin (content_tsv);

alter table documents enable row level security;
alter table document_chunks enable row level security;

create policy "owner can access own documents" on documents
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own document chunks" on document_chunks
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
```

RLS follows the same owner-via-`project_id` pattern as `tools` and
`conversations`. `document_chunks.project_id` is denormalized (not derived
via a join through `document_id`) for the same reason `runs.project_id` is
denormalized in the Memory sub-project: it's what RLS and queries key off
directly.

A Supabase Storage bucket `documents` (private) holds the original
uploaded file at `storage_path` (`{project_id}/{document_id}/{filename}`).

## Backend: Ingestion Pipeline (`app/rag.py`)

Mirrors `app/memory.py`'s shape (module-level Qdrant client, lazily
initialized embedder, plain functions — no new abstraction layer).

**Accepted mime types:** `text/plain`, `text/markdown`, `application/pdf`.
Anything else is rejected with 422 at the API boundary (input validation
at a trust boundary — this is user-uploaded content).

**New dependency:** `pypdf` for PDF text extraction. No new dependency for
txt/md (read as UTF-8 text directly).

**Pipeline (`ingest_document`):**
1. Upload bytes to Supabase Storage at `storage_path`.
2. Insert `documents` row (`status='pending'`).
3. Extract text (plain read, or `pypdf` page-by-page join for PDF).
4. Chunk: fixed-size, ~800 chars with ~100 char overlap (`chunk_text`
   helper — pure function, easy to unit test without network).
5. Embed each chunk with the same `fastembed` model already loaded for
   memory (`BAAI/bge-small-en-v1.5`, 384-dim) — reuses the existing
   dependency, no second embedding provider.
6. Insert `document_chunks` rows (one per chunk) and upsert corresponding
   Qdrant points into a new collection `documents` (payload:
   `project_id, document_id, chunk_id, chunk_index, content`).
7. Update `documents.status` to `indexed`, or `failed` + `error` message on
   any exception in steps 3–6 (delete any already-inserted chunks/vectors
   first, so a failed document never appears half-indexed).

Synchronous within the request — acceptable for today's scope (small
text/PDF files, no job queue introduced).

## Backend: Hybrid Retrieval (`app/rag.py`)

`retrieve_chunks(project_id: str, query: str, top_k: int = 5) -> list[dict]`:

- **Vector:** Qdrant `query_points` on the `documents` collection, filtered
  by `project_id`, same score-threshold pattern as `search_memory`.
- **Keyword:** Postgres query against `document_chunks` using
  `content_tsv @@ plainto_tsquery('english', query)`, filtered by
  `project_id`, ranked by `ts_rank`.
- **Merge:** dedupe by `chunk_id` (a chunk found by both methods keeps its
  vector score), concatenate, sort by score descending, cap to `top_k`.
  No cross-encoder re-ranking — raw score ordering, consistent with the
  Memory sub-project's "no reranking beyond raw similarity" precedent.

This needs a `get_user_client`-scoped Postgres call, so the keyword half
lives in `app/rag.py` but takes the Supabase client as a parameter (same
pattern as passing `client` around in `runs.py`), not a hidden global.

## Backend: Graph & Run Wiring

`app/graph.py`: `AgentState` gains `retrieved_chunks: list[dict]`
(each `{chunk_id, document_id, filename, content, score}`).

`run_agent`: when `retrieved_chunks` is non-empty, build a second system
message — numbered sources ("[1] {filename}: {content}", ...) — inserted
alongside (after) the existing memory-context system message. The message
instructs the model to cite sources inline as `[1]`, `[2]` etc. when used.

**Chunk compression:** each chunk's `content` is hard-capped to 500 chars
before insertion into that system message (simple truncation, not
summarization — this is the master spec's "retrieved-chunk compression"
requirement at the simplest level that satisfies it).

`app/api/runs.py::create_run`: after loading history and searching memory,
also call `retrieve_chunks(project_id, body.input)`. Pass the result into
the graph invocation. After the graph responds, emit a `retrieval_performed`
run_event (chunk count + top score, mirroring `memory_recalled`). Response
(`RunOut`) gains a `citations` field: the same list passed to the graph,
so the frontend can render "[1] filename" reference cards regardless of
whether the model's text actually uses the bracket markers.

## Backend: API

- `POST /projects/{project_id}/documents` (multipart) — upload +
  synchronously index. Returns the `documents` row.
- `GET /projects/{project_id}/documents` — list with status, for the
  Knowledge Hub panel's indexing-status view.
- `DELETE /projects/{project_id}/documents/{document_id}` — deletes the
  Storage object, `document_chunks` rows (cascade), and the Qdrant points
  for that `document_id` (`_client.delete` with a `document_id` filter).

## Frontend

- `WorkspaceNav`'s `knowledge-hub` tab already exists as an `EmptyStatePanel`
  entry in `ProjectWorkspace.tsx` — this sub-project replaces that entry
  with a real `KnowledgeHubPanel`, same wiring pattern as
  `MemoryExplorerPanel`.
- `KnowledgeHubPanel`: file upload input + button (calls the upload
  endpoint), a document list showing filename + status (pending/indexed/
  failed), and delete action per document. No separate chunk-inspection
  view beyond what's already visible via citations in Chat — kept minimal
  per today's scope.
- `ChatPanel`: renders a run's `citations` (if any) below the assistant
  message as small "[n] filename" reference chips — same minimal-effort
  spirit as the rest of today's frontend scope.
- `lib/api.ts` gains `uploadDocument`, `listDocuments`, `deleteDocument`
  functions, matching the existing `listConversations`/`searchMemories`
  style.

## Testing

Same discipline as prior sub-projects: real Supabase + real Qdrant for
integration tests, no mocking core dependencies, credential-gated the same
way existing Supabase integration tests are (`SUPABASE_TEST_USER_TOKEN`).

- Unit tests (no network): `chunk_text` (overlap/boundary behavior), PDF
  text extraction against a small fixture file, chunk-content truncation.
- Integration: upload a small `.txt` document → assert it becomes
  `indexed` with the expected chunk count; a run whose input matches the
  document's content includes it in `citations`; a chunk from project A
  never appears in project B's retrieval (RLS/filter isolation, mirrors
  the existing cross-project isolation test pattern in
  `test_memories.py`); deleting a document removes its chunks and Qdrant
  points.
- Frontend: Vitest for `KnowledgeHubPanel` (upload triggers the API call,
  status renders) and `ChatPanel`'s citation rendering.

## Non-goals (explicit, so scope doesn't creep mid-build)

- Async/background indexing — synchronous upload is fine at this scale
- Cross-encoder re-ranking beyond raw keyword+vector score ordering
- Semantic/recursive chunking — fixed-size with overlap only
- OCR for scanned PDFs
- LLM-based chunk summarization (compression = truncation only)
- Document versioning or re-upload/re-index of an existing document
- Cross-project document sharing
- Multi-agent coordination (Orchestration sub-project's concern)
