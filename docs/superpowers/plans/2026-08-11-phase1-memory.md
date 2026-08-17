# Phase 1, Sub-project 2: Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire session memory (prior turns in a conversation) and long-term semantic memory (Qdrant, project-wide) into the live agent call, and prove recall works end-to-end: a second message in a conversation reflects a fact stated in the first, and a semantic search finds a matching turn from a different conversation in the same project.

**Architecture:** `conversations` becomes a first-class entity (a project holds many, each with its own growing `runs` history) so there's a scope to recall *within*. Session memory needs no new table — it's `runs` rows filtered by `conversation_id`. Long-term memory is one Qdrant collection (`memory`), embedded locally via `qdrant-client[fastembed]` (no second LLM/embedding provider), searched project-wide and injected as a system message alongside conversation history when the agent graph runs. `POST /projects/{project_id}/runs` is replaced by `POST /conversations/{conversation_id}/runs`, which loads history, searches Qdrant, invokes the graph with both, and upserts the new turn into Qdrant afterward.

**Tech Stack:** Same backend/frontend stack as prior sub-projects, plus `qdrant-client[fastembed]` (new backend dependency) and a `qdrant/qdrant` Docker Compose service (new infra, self-hosted per the Tool Calling sub-project's decision).

**Spec:** `docs/superpowers/specs/2026-08-11-phase1-memory-design.md`

## Global Constraints

- Groq remains the only LLM provider. FastEmbed's local ONNX model (`BAAI/bge-small-en-v1.5`, 384-dim) is not a second provider in the locked-stack sense — no API key, no network call at inference time (only a one-time model-weight fetch, cached afterward).
- Qdrant is self-hosted via Docker Compose (`qdrant/qdrant` image, port 6333, named volume). Qdrant Cloud is the documented fallback if Docker hosting becomes a problem — do not build that fallback now, nothing here depends on it.
- Session memory gets **no new table** — it's `runs` rows filtered by `conversation_id`, ordered by `created_at`. Do not duplicate that storage.
- `runs.project_id` stays populated and denormalized on every insert (derived from the conversation once, at insert time) — this is what the existing `runs`/`run_events` RLS policies key off. Do not derive it via a join through `conversation_id → conversations.project_id` in policies or queries that don't already need the join.
- Qdrant collection name is `memory`. Point id = `run_id`. Payload = `{project_id, conversation_id, run_id, input, output}`. Embedded text = `f"User: {input}\nAssistant: {output}"`. Search is `top_k=3` with a score-threshold cutoff, filtered by `project_id` (long-term memory is project-wide, spanning conversations).
- Do not build: memory pruning/summarization/decay (long-term memory just accumulates), a delete-memory UI, cross-project memory sharing, an explicit "remember this fact" tool-style affordance, reranking beyond raw vector similarity, or any multi-agent coordination (that's the Orchestration sub-project's concern).
- Testing discipline matches prior sub-projects: real Supabase + real Qdrant for integration tests (`docker compose up`, no mocking core dependencies), credential/service-gated the same way existing integration tests are. Unit tests for pure functions (history-to-messages conversion, message-building) need no live service.

---

### Task 1: Memory migration — `conversations` table and `runs.conversation_id`

**Files:**
- Create: `backend/migrations/0003_memory.sql`

**Interfaces:**
- Produces: table `conversations(id, project_id, title, created_at)`, owner-scoped RLS policy identical in shape to `tools`'. `runs` gains a required `conversation_id` column referencing it.

- [ ] **Step 1: Write the migration**

`backend/migrations/0003_memory.sql`:
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

- [ ] **Step 2: Apply the migration**

In the Supabase project's SQL Editor, paste and run the contents of `backend/migrations/0003_memory.sql`. Manual step for the human operator — pause here and ask if Supabase access isn't available. Note: `alter table runs add column conversation_id ... not null` will fail if any `runs` rows already exist from prior testing, since there's no default. If that happens, either truncate the `runs`/`run_events` tables first (test data only, confirm with the human operator before deleting) or add the column nullable and backfill — do not silently relax the `not null` constraint in the migration file itself.

- [ ] **Step 3: Verify**

In the Supabase SQL Editor, run:
```sql
select relname, relrowsecurity from pg_class where relname = 'conversations';
select column_name, is_nullable from information_schema.columns where table_name = 'runs' and column_name = 'conversation_id';
```
Expected: first query returns one row with `relrowsecurity` = `true`; second returns one row with `is_nullable` = `NO`.

---

### Task 2: Qdrant infra — Docker Compose, dependency, config

**Files:**
- Modify: `docker-compose.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`

**Interfaces:**
- Produces: `settings.qdrant_url: str` (default `http://qdrant:6333`), a running Qdrant container reachable at `localhost:6333` from the host.

- [ ] **Step 1: Add the `qdrant` service to Compose**

`docker-compose.yml` — add a `qdrant` service, a `depends_on` entry on `backend` (mirrors the existing `frontend` → `backend` `depends_on`), and the named volume:
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - qdrant

  frontend:
    build:
      context: ./frontend
      args:
        NEXT_PUBLIC_SUPABASE_URL: ${NEXT_PUBLIC_SUPABASE_URL}
        NEXT_PUBLIC_SUPABASE_ANON_KEY: ${NEXT_PUBLIC_SUPABASE_ANON_KEY}
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    ports:
      - "3000:3000"
    env_file:
      - .env
    depends_on:
      - backend

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

- [ ] **Step 2: Add the dependency**

`backend/requirements.txt` — add a line after `langgraph>=0.2`:
```
qdrant-client[fastembed]>=1.9
```

- [ ] **Step 3: Add the setting**

`backend/app/config.py` (full file):
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str
    qdrant_url: str = "http://qdrant:6333"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Install and verify**

Run: `cd backend && pip install -r requirements.txt`
Run: `docker compose up -d qdrant`
Run: `curl http://localhost:6333/healthz`
Expected: `healthz check passed`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml backend/requirements.txt backend/app/config.py
git commit -m "chore: add self-hosted Qdrant service and client dependency"
```

---

### Task 3: Memory module — history conversion and Qdrant embed/search helpers

**Files:**
- Create: `backend/app/memory.py`
- Create: `backend/tests/test_memory.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `settings.qdrant_url` (Task 2).
- Produces: `history_to_messages(history: list[dict]) -> list[dict]`, `upsert_memory(run_id: str, project_id: str, conversation_id: str, input: str, output: str) -> None`, `search_memory(project_id: str, query: str, top_k: int = 3) -> list[dict]` (each result dict has keys `score, project_id, conversation_id, run_id, input, output`). `qdrant_available` pytest fixture (skips if no live Qdrant).

- [ ] **Step 1: Write the failing unit tests for `history_to_messages`**

`backend/tests/test_memory.py`:
```python
from app.memory import history_to_messages


def test_history_to_messages_converts_runs_to_alternating_turns():
    history = [
        {"input": "hello", "output": "hi there"},
        {"input": "how are you", "output": "doing well"},
    ]
    assert history_to_messages(history) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "user", "content": "how are you"},
        {"role": "assistant", "content": "doing well"},
    ]


def test_history_to_messages_empty_history_returns_empty_list():
    assert history_to_messages([]) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.memory'`

- [ ] **Step 3: Write `backend/app/memory.py`**

```python
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from app.config import settings

COLLECTION = "memory"
SCORE_THRESHOLD = 0.5
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_client = QdrantClient(url=settings.qdrant_url)
_embedder: TextEmbedding | None = None


def _ensure_collection() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
        if not _client.collection_exists(COLLECTION):
            _client.create_collection(
                collection_name=COLLECTION,
                vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
            )
    return _embedder


def history_to_messages(history: list[dict]) -> list[dict]:
    messages = []
    for run in history:
        messages.append({"role": "user", "content": run["input"]})
        messages.append({"role": "assistant", "content": run["output"]})
    return messages


def upsert_memory(run_id: str, project_id: str, conversation_id: str, input: str, output: str) -> None:
    embedder = _ensure_collection()
    document = f"User: {input}\nAssistant: {output}"
    vector = next(iter(embedder.embed([document])))
    _client.upsert(
        collection_name=COLLECTION,
        points=[
            models.PointStruct(
                id=run_id,
                vector=vector.tolist(),
                payload={
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "run_id": run_id,
                    "input": input,
                    "output": output,
                },
            )
        ],
    )


def search_memory(project_id: str, query: str, top_k: int = 3) -> list[dict]:
    embedder = _ensure_collection()
    vector = next(iter(embedder.embed([query])))
    results = _client.query_points(
        collection_name=COLLECTION,
        query=vector.tolist(),
        query_filter=models.Filter(
            must=[models.FieldCondition(key="project_id", match=models.MatchValue(value=project_id))]
        ),
        limit=top_k,
    ).points
    return [{"score": r.score, **r.payload} for r in results if r.score >= SCORE_THRESHOLD]
```

`qdrant-client[fastembed]>=1.9` no longer ships the `QdrantFastembedMixin` convenience API (`.add()`/`.query()`/`.set_model()`) that earlier versions had — the plan originally assumed it, but the installed version (1.19.0) only exposes `list_text_models()`/`get_embedding_size()` alongside the standard `upsert`/`query_points`. `_ensure_collection()` embeds via `fastembed.TextEmbedding` directly and stores/searches raw vectors through `upsert`/`query_points`, deferring both the model load (one-time weight download) and the collection-creation check until a helper that actually needs them is called — so importing `app.memory` and calling `history_to_messages`, the pure function, never touches the network or requires a live Qdrant instance.

- [ ] **Step 4: Run to verify the unit tests pass**

Run: `cd backend && pytest tests/test_memory.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Add the `qdrant_available` fixture**

`backend/tests/conftest.py` — add below the existing `auth_headers` fixture:
```python
@pytest.fixture
def qdrant_available():
    from qdrant_client import QdrantClient

    from app.config import settings

    try:
        QdrantClient(url=settings.qdrant_url).get_collections()
    except Exception:
        pytest.skip("Real Qdrant instance required for this integration test (docker compose up -d qdrant)")
```

- [ ] **Step 6: Write the failing integration test for embed/search**

Append to `backend/tests/test_memory.py`:
```python
import uuid

from app.memory import search_memory, upsert_memory


def test_upsert_then_search_returns_matching_memory(qdrant_available):
    run_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())

    upsert_memory(
        run_id=run_id,
        project_id=project_id,
        conversation_id=conversation_id,
        input="The launch codeword for our rocket is Bluebird.",
        output="Got it, noted.",
    )

    results = search_memory(project_id, "rocket launch codeword")

    assert any(r["run_id"] == run_id for r in results)
    assert all(r["project_id"] == project_id for r in results)
```

- [ ] **Step 7: Run to verify**

Run: `docker compose up -d qdrant` (if not already running), then `cd backend && QDRANT_URL=http://localhost:6333 pytest tests/test_memory.py -v`
Expected: PASS (3 tests). If Qdrant isn't reachable, the third test SKIPs instead of failing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/memory.py backend/tests/test_memory.py backend/tests/conftest.py
git commit -m "feat: add history-to-messages conversion and Qdrant memory helpers"
```

---

### Task 4: Widen `llm.generate` to accept a message list

**Files:**
- Modify: `backend/app/llm.py:10-15`
- Modify: `backend/tests/test_llm.py`

**Interfaces:**
- Produces: `generate(messages: list[dict]) -> str` (was `generate(prompt: str) -> str`).

- [ ] **Step 1: Update the test to call the new signature**

`backend/tests/test_llm.py`:
```python
import os
import pytest

from app.config import settings
from app.llm import generate


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_generate_returns_nonempty_string():
    result = generate([{"role": "user", "content": "Say the word 'pong' and nothing else."}])
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && GROQ_API_KEY=<real key> pytest tests/test_llm.py -v`
Expected: FAIL — the old `generate(prompt: str)` builds `messages=[{"role": "user", "content": <the list>}]`, which the Groq API rejects with a 400 (surfaces as an unhandled exception from the SDK).

- [ ] **Step 3: Widen the implementation**

`backend/app/llm.py`:
```python
from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

MODEL = "llama-3.3-70b-versatile"


def generate(messages: list[dict]) -> str:
    response = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    return response.choices[0].message.content
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && GROQ_API_KEY=<real key> pytest tests/test_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/test_llm.py
git commit -m "feat: widen llm.generate to accept a message list"
```

---

### Task 5: Graph — inject history and memory context

**Files:**
- Modify: `backend/app/graph.py`
- Modify: `backend/tests/test_graph.py`

**Interfaces:**
- Consumes: `generate(messages: list[dict]) -> str` (Task 4).
- Produces: `AgentState` gains `history: list[dict]` and `memory_context: list[str]`. `run_agent(state: AgentState) -> AgentState` builds `[system? , *history, final user message]` and calls `generate`.

- [ ] **Step 1: Write the failing unit test for message building**

`backend/tests/test_graph.py` — add above the existing integration test:
```python
from app.graph import run_agent


def test_run_agent_builds_messages_with_memory_and_history(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {
        "input": "new question",
        "output": "",
        "history": [
            {"role": "user", "content": "prior q"},
            {"role": "assistant", "content": "prior a"},
        ],
        "memory_context": ["User: old q\nAssistant: old a"],
    }
    result = run_agent(state)

    assert result["output"] == "final answer"
    assert captured["messages"][0] == {
        "role": "system",
        "content": "Relevant memory from earlier in this project:\nUser: old q\nAssistant: old a",
    }
    assert captured["messages"][1:3] == state["history"]
    assert captured["messages"][3] == {"role": "user", "content": "new question"}


def test_run_agent_skips_system_message_when_no_memory_context(monkeypatch):
    captured = {}

    def fake_generate(messages):
        captured["messages"] = messages
        return "final answer"

    monkeypatch.setattr("app.graph.generate", fake_generate)

    state = {"input": "hello", "output": "", "history": [], "memory_context": []}
    run_agent(state)

    assert captured["messages"] == [{"role": "user", "content": "hello"}]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && pytest tests/test_graph.py -v -k build_messages or skips_system`
Expected: FAIL — `AgentState`/`run_agent` don't build messages this way yet, and `state["history"]`/`state["memory_context"]` raise `KeyError`.

- [ ] **Step 3: Update the graph**

`backend/app/graph.py`:
```python
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm import generate


class AgentState(TypedDict):
    input: str
    output: str
    history: list[dict]
    memory_context: list[str]


def run_agent(state: AgentState) -> AgentState:
    messages: list[dict] = []
    if state["memory_context"]:
        context_text = "\n".join(state["memory_context"])
        messages.append(
            {
                "role": "system",
                "content": f"Relevant memory from earlier in this project:\n{context_text}",
            }
        )
    messages.extend(state["history"])
    messages.append({"role": "user", "content": state["input"]})
    return {**state, "output": generate(messages)}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", run_agent)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()


agent_graph = build_graph()
```

- [ ] **Step 4: Update the existing integration test's invoke call**

`backend/tests/test_graph.py` — the existing `test_agent_graph_produces_output` invokes `agent_graph` directly, so it must supply the two new required state keys:
```python
@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_agent_graph_produces_output():
    result = agent_graph.invoke(
        {"input": "Say the word 'pong' and nothing else.", "output": "", "history": [], "memory_context": []}
    )
    assert result["output"]
    assert result["input"] == "Say the word 'pong' and nothing else."
```

- [ ] **Step 5: Run to verify all pass**

Run: `cd backend && pytest tests/test_graph.py -v`
Expected: PASS (2 unit tests always run; the integration test runs and passes if `GROQ_API_KEY` is real, else skips)

- [ ] **Step 6: Commit**

```bash
git add backend/app/graph.py backend/tests/test_graph.py
git commit -m "feat: inject conversation history and memory context into the agent graph"
```

---

### Task 6: Conversations API

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/api/conversations.py`
- Modify: `backend/app/main.py:1-18`
- Create: `backend/tests/test_conversations.py`

**Interfaces:**
- Produces: `POST /projects/{project_id}/conversations`, `GET /projects/{project_id}/conversations`, Pydantic models `ConversationCreate(title: str = "New conversation")` and `ConversationOut(id, project_id, title, created_at)`.

- [ ] **Step 1: Write the failing auth test**

`backend/tests/test_conversations.py`:
```python
import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_conversation_requires_auth():
    response = client.post("/projects/some-id/conversations", json={})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_and_list_conversations(auth_headers):
    project_response = client.post("/projects", json={"name": "Conversation Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "First thread"}, headers=auth_headers
    )
    assert create_response.status_code == 200
    conversation = create_response.json()
    assert conversation["title"] == "First thread"

    list_response = client.get(f"/projects/{project_id}/conversations", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(c["id"] == conversation["id"] for c in list_response.json())
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_conversations.py -v`
Expected: FAIL — 404, route doesn't exist yet.

- [ ] **Step 3: Add the models**

`backend/app/models.py` — add after `ProjectOut`:
```python
class ConversationCreate(BaseModel):
    title: str = "New conversation"


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: datetime
```

- [ ] **Step 4: Add the router**

`backend/app/api/conversations.py`:
```python
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ConversationCreate, ConversationOut

router = APIRouter(tags=["conversations"])


@router.post("/projects/{project_id}/conversations", response_model=ConversationOut)
def create_conversation(project_id: str, body: ConversationCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("conversations").insert(
        {"project_id": project_id, "title": body.title}
    ).execute()
    return result.data[0]


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationOut])
def list_conversations(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = (
        client.table("conversations")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data
```

- [ ] **Step 5: Register the router**

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, projects, runs, tools

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(tools.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && pytest tests/test_conversations.py -v`
Expected: PASS — the auth test always runs; the integration test runs and passes with a real Supabase project (after Task 1's migration is applied), else skips.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/api/conversations.py backend/app/main.py backend/tests/test_conversations.py
git commit -m "feat: add conversations API"
```

---

### Task 7: Runs API — conversation-scoped, with memory recall and upsert

**Files:**
- Modify: `backend/app/api/runs.py`
- Modify: `backend/tests/test_runs.py`

**Interfaces:**
- Consumes: `history_to_messages`, `search_memory`, `upsert_memory` (Task 3); `agent_graph` now requires `history`/`memory_context` (Task 5); `ConversationOut`/conversations table (Task 6).
- Produces: `POST /conversations/{conversation_id}/runs` (replaces `POST /projects/{project_id}/runs`), `GET /conversations/{conversation_id}/runs`, `GET /runs/{run_id}` (unchanged).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_runs.py` (full file):
```python
import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_run_requires_auth():
    response = client.post("/conversations/some-id/runs", json={"input": "hello"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_create_run_executes_graph_and_records_events(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Run Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Run Test Conversation"}, headers=auth_headers
    )
    conversation_id = conversation_response.json()["id"]

    run_response = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "Say the word 'pong' and nothing else."},
        headers=auth_headers,
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["output"]
    step_names = [e["step_name"] for e in run["events"]]
    assert step_names == ["run_started", "agent_responded"]

    get_response = client.get(f"/runs/{run['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == run["id"]


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_second_run_in_conversation_recalls_first(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Recall Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_response = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Recall Test Conversation"}, headers=auth_headers
    )
    conversation_id = conversation_response.json()["id"]

    first = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "My favorite color is teal. Reply with just 'ok'."},
        headers=auth_headers,
    )
    assert first.status_code == 200

    second = client.post(
        f"/conversations/{conversation_id}/runs",
        json={"input": "What is my favorite color? Reply with just the color."},
        headers=auth_headers,
    )
    assert second.status_code == 200
    assert "teal" in second.json()["output"].lower()

    history_response = client.get(f"/conversations/{conversation_id}/runs", headers=auth_headers)
    assert history_response.status_code == 200
    assert len(history_response.json()) == 2
```

- [ ] **Step 2: Run to verify the auth test fails against the old route**

Run: `cd backend && pytest tests/test_runs.py::test_create_run_requires_auth -v`
Expected: FAIL — `/conversations/some-id/runs` doesn't exist yet (404, not 401/422).

- [ ] **Step 3: Rewrite the router**

`backend/app/api/runs.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_user_client
from app.graph import agent_graph
from app.memory import history_to_messages, search_memory, upsert_memory
from app.models import RunCreate, RunOut

router = APIRouter(tags=["runs"])


@router.post("/conversations/{conversation_id}/runs", response_model=RunOut)
def create_run(conversation_id: str, body: RunCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])

    conversation = (
        client.table("conversations")
        .select("project_id")
        .eq("id", conversation_id)
        .maybe_single()
        .execute()
        .data
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    project_id = conversation["project_id"]

    prior_runs = (
        client.table("runs")
        .select("input, output")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    history = history_to_messages(prior_runs)

    memories = search_memory(project_id, body.input)
    memory_context = [f"User: {m['input']}\nAssistant: {m['output']}" for m in memories]

    run = client.table("runs").insert(
        {
            "project_id": project_id,
            "conversation_id": conversation_id,
            "status": "running",
            "input": body.input,
        }
    ).execute().data[0]
    run_id = run["id"]

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "run_started", "payload": {"input": body.input}}
    ).execute()

    if memories:
        client.table("run_events").insert(
            {
                "run_id": run_id,
                "step_name": "memory_recalled",
                "payload": {"count": len(memories), "top_score": memories[0]["score"]},
            }
        ).execute()

    result = agent_graph.invoke(
        {"input": body.input, "output": "", "history": history, "memory_context": memory_context}
    )

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "agent_responded", "payload": {"output": result["output"]}}
    ).execute()

    updated = client.table("runs").update(
        {"status": "completed", "output": result["output"]}
    ).eq("id", run_id).execute().data[0]

    upsert_memory(run_id, project_id, conversation_id, body.input, result["output"])

    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**updated, "events": events}


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    run = client.table("runs").select("*").eq("id", run_id).maybe_single().execute().data
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**run, "events": events}


@router.get("/conversations/{conversation_id}/runs", response_model=list[RunOut])
def list_conversation_runs(conversation_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    runs = (
        client.table("runs")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
    )
    run_ids = [r["id"] for r in runs]
    events = (
        client.table("run_events").select("*").in_("run_id", run_ids).order("created_at").execute().data
        if run_ids
        else []
    )
    events_by_run: dict[str, list] = {}
    for event in events:
        events_by_run.setdefault(event["run_id"], []).append(event)
    return [{**run, "events": events_by_run.get(run["id"], [])} for run in runs]
```

Note the run stays scoped by `project_id` (denormalized at insert, per Global Constraints) even though the endpoint URL only carries `conversation_id` — this keeps the existing `runs`/`run_events` RLS policies untouched.

- [ ] **Step 4: Run to verify all pass**

Run: `docker compose up -d qdrant` (if not already running), then `cd backend && QDRANT_URL=http://localhost:6333 GROQ_API_KEY=<real key> pytest tests/test_runs.py -v`
Expected: PASS. `test_create_run_requires_auth` always passes; the two integration tests pass with real Supabase/Groq/Qdrant, else skip.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/runs.py backend/tests/test_runs.py
git commit -m "feat: scope runs to conversations and wire in memory recall"
```

---

### Task 8: Memory search API

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/api/memories.py`
- Modify: `backend/app/main.py:1-19`
- Create: `backend/tests/test_memories.py`

**Interfaces:**
- Consumes: `search_memory` (Task 3).
- Produces: `GET /projects/{project_id}/memories/search?q=`, Pydantic model `MemorySearchResult(score, project_id, conversation_id, run_id, input, output)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_memories.py`:
```python
import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_memory_requires_auth():
    response = client.get("/projects/some-id/memories/search", params={"q": "hello"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_search_finds_earlier_turn_across_conversations(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Search Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    conversation_a = client.post(
        f"/projects/{project_id}/conversations", json={"title": "Thread A"}, headers=auth_headers
    ).json()
    client.post(
        f"/conversations/{conversation_a['id']}/runs",
        json={"input": "The launch codeword for our rocket is Bluebird. Reply 'ok'."},
        headers=auth_headers,
    )

    client.post(f"/projects/{project_id}/conversations", json={"title": "Thread B"}, headers=auth_headers)

    search_response = client.get(
        f"/projects/{project_id}/memories/search",
        params={"q": "rocket launch codeword"},
        headers=auth_headers,
    )
    assert search_response.status_code == 200
    results = search_response.json()
    assert any("Bluebird" in r["input"] for r in results)
    assert all(r["project_id"] == project_id for r in results)


def test_search_memory_requires_project_ownership(auth_headers):
    response = client.get(
        "/projects/00000000-0000-0000-0000-000000000000/memories/search",
        params={"q": "hello"},
        headers=auth_headers,
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_memories.py -v`
Expected: FAIL — route doesn't exist yet (404 for the auth test too, since it currently doesn't distinguish auth-missing from route-missing — confirm the first assertion fails because the status isn't 401/422).

- [ ] **Step 3: Add the model**

`backend/app/models.py` — add after `ConversationOut`:
```python
class MemorySearchResult(BaseModel):
    score: float
    project_id: str
    conversation_id: str
    run_id: str
    input: str
    output: str
```

- [ ] **Step 4: Add the router**

`backend/app/api/memories.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_user_client
from app.memory import search_memory
from app.models import MemorySearchResult

router = APIRouter(tags=["memories"])


@router.get("/projects/{project_id}/memories/search", response_model=list[MemorySearchResult])
def search_project_memory(project_id: str, q: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    project = client.table("projects").select("id").eq("id", project_id).maybe_single().execute().data
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return search_memory(project_id, q)
```

The project-ownership check (via the user's RLS-scoped client) is required here and nowhere else in this task: Qdrant has no concept of the caller's identity, so without it any authenticated user could read another user's project memories by guessing a `project_id`.

- [ ] **Step 5: Register the router**

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conversations, memories, projects, runs, tools

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(memories.router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(tools.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run to verify it passes**

Run: `docker compose up -d qdrant` (if not already running), then `cd backend && QDRANT_URL=http://localhost:6333 GROQ_API_KEY=<real key> pytest tests/test_memories.py -v`
Expected: PASS — the auth test and ownership test always run; the search test passes with real Supabase/Groq/Qdrant, else skips.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/api/memories.py backend/app/main.py backend/tests/test_memories.py
git commit -m "feat: add project-scoped semantic memory search API"
```

---

### Task 9: Frontend API client — conversations, conversation-scoped runs, memory search

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/api.test.ts`

**Interfaces:**
- Consumes: endpoints from Tasks 6-8.
- Produces: `type Conversation`, `createConversation(projectId: string, title?: string): Promise<Conversation>`, `listConversations(projectId: string): Promise<Conversation[]>`, `createRun(conversationId: string, input: string): Promise<Run>` (signature change — first argument is now a conversation id), `listConversationRuns(conversationId: string): Promise<Run[]>`, `type MemorySearchResult`, `searchMemories(projectId: string, q: string): Promise<MemorySearchResult[]>`.

- [ ] **Step 1: Write the failing tests**

`frontend/lib/api.test.ts` — add inside the `describe('api client', ...)` block, after the existing `invokeTool` test:
```ts
  it('createConversation sends an authorized POST request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'conv-1', project_id: 'project-1', title: 'New conversation', created_at: '2026-01-01T00:00:00Z' }),
    }) as unknown as typeof fetch

    const { createConversation } = await import('./api')
    await createConversation('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/conversations'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({}),
      })
    )
  })

  it('listConversations sends an authorized GET request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { listConversations } = await import('./api')
    await listConversations('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/conversations'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('createRun posts to the conversation-scoped endpoint', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'run-1', status: 'completed', output: 'pong', events: [] }),
    }) as unknown as typeof fetch

    const { createRun } = await import('./api')
    await createRun('conv-1', 'ping')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/conversations/conv-1/runs'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ input: 'ping' }),
      })
    )
  })

  it('listConversationRuns sends an authorized GET request', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { listConversationRuns } = await import('./api')
    await listConversationRuns('conv-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/conversations/conv-1/runs'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })

  it('searchMemories sends an authorized GET request with the query', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] }) as unknown as typeof fetch

    const { searchMemories } = await import('./api')
    await searchMemories('project-1', 'rocket codeword')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/memories/search?q=rocket%20codeword'),
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer test-token' }) })
    )
  })
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `createConversation`, `listConversations`, `listConversationRuns`, `searchMemories` aren't exported yet, and `createRun` still posts to `/projects/{id}/runs`.

- [ ] **Step 3: Update `frontend/lib/api.ts`**

Add types and functions after the existing `getRun` function, and replace `createRun`:
```ts
export async function createRun(conversationId: string, input: string): Promise<Run> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ input }),
  })
  if (!res.ok) throw new Error('Failed to create run')
  return res.json()
}

export type Conversation = { id: string; project_id: string; title: string; created_at: string }

export async function createConversation(projectId: string, title?: string): Promise<Conversation> {
  const res = await fetch(`${API_URL}/projects/${projectId}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(title ? { title } : {}),
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function listConversations(projectId: string): Promise<Conversation[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/conversations`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list conversations')
  return res.json()
}

export async function listConversationRuns(conversationId: string): Promise<Run[]> {
  const res = await fetch(`${API_URL}/conversations/${conversationId}/runs`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list conversation runs')
  return res.json()
}

export type MemorySearchResult = {
  score: number
  project_id: string
  conversation_id: string
  run_id: string
  input: string
  output: string
}

export async function searchMemories(projectId: string, q: string): Promise<MemorySearchResult[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/memories/search?q=${encodeURIComponent(q)}`, {
    headers: await authHeaders(),
  })
  if (!res.ok) throw new Error('Failed to search memories')
  return res.json()
}
```
Remove the old `createRun` definition further down the file (the one posting to `/projects/${projectId}/runs`) so there's only one.

- [ ] **Step 4: Run to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/lib/api.test.ts
git commit -m "feat: add conversation and memory-search client functions"
```

---

### Task 10: ChatPanel — conversation selector and growing message list

**Files:**
- Modify: `frontend/components/ChatPanel.tsx`
- Modify: `frontend/components/ChatPanel.test.tsx`

**Interfaces:**
- Consumes: `listConversations`, `createConversation`, `listConversationRuns`, `createRun` (Task 9).

- [ ] **Step 1: Write the failing test**

`frontend/components/ChatPanel.test.tsx` (full file):
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listConversations = vi.fn().mockResolvedValue([])
const createConversation = vi.fn().mockResolvedValue({
  id: 'conv-1',
  project_id: 'project-1',
  title: 'New conversation',
  created_at: '2026-01-01T00:00:00Z',
})
const listConversationRuns = vi.fn().mockResolvedValue([])
const createRun = vi.fn().mockResolvedValue({
  id: 'run-1',
  status: 'completed',
  output: 'pong',
  events: [{ id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T00:00:00Z' }],
})

vi.mock('@/lib/api', () => ({ listConversations, createConversation, listConversationRuns, createRun }))

describe('ChatPanel', () => {
  it('sends input and displays the response and timeline', async () => {
    const { default: ChatPanel } = await import('./ChatPanel')
    render(<ChatPanel projectId="project-1" />)

    await waitFor(() => expect(listConversations).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'ping' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(createConversation).toHaveBeenCalledWith('project-1'))
    await waitFor(() => expect(createRun).toHaveBeenCalledWith('conv-1', 'ping'))
    await waitFor(() => expect(screen.getByText('pong')).toBeInTheDocument())
    expect(screen.getByText('run_started')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run components/ChatPanel.test.tsx`
Expected: FAIL — the current `ChatPanel` calls `createRun('project-1', 'ping')` directly, never calls `listConversations`/`createConversation`, so the `toHaveBeenCalledWith('conv-1', 'ping')` assertion fails.

- [ ] **Step 3: Rewrite `ChatPanel.tsx`**

```tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  createConversation,
  createRun,
  listConversationRuns,
  listConversations,
  type Conversation,
  type Run,
} from '@/lib/api'
import Timeline from './Timeline'

export default function ChatPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const skipNextFetch = useRef(false)

  useEffect(() => {
    listConversations(projectId)
      .then((list) => {
        setConversations(list)
        if (list.length > 0) setConversationId(list[0].id)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
  }, [projectId])

  useEffect(() => {
    if (!conversationId) {
      setRuns([])
      return
    }
    if (skipNextFetch.current) {
      skipNextFetch.current = false
      return
    }
    listConversationRuns(conversationId)
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversation'))
  }, [conversationId])

  async function handleNewConversation() {
    setError(null)
    try {
      const conversation = await createConversation(projectId)
      setConversations((prev) => [conversation, ...prev])
      skipNextFetch.current = true
      setRuns([])
      setConversationId(conversation.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create conversation')
    }
  }

  async function handleSend() {
    if (!message.trim()) return
    setLoading(true)
    setError(null)
    try {
      let activeId = conversationId
      if (!activeId) {
        const conversation = await createConversation(projectId)
        setConversations((prev) => [conversation, ...prev])
        skipNextFetch.current = true
        setConversationId(conversation.id)
        activeId = conversation.id
      }
      const result = await createRun(activeId, message)
      setRuns((prev) => [...prev, result])
      setMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setLoading(false)
    }
  }

  const latestRun = runs[runs.length - 1]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <label htmlFor="conversation-select" className="sr-only">Conversation</label>
        <select
          id="conversation-select"
          value={conversationId ?? ''}
          onChange={(e) => setConversationId(e.target.value || null)}
          className="border border-border bg-card px-2 py-1 text-sm"
        >
          <option value="">New conversation</option>
          {conversations.map((c) => (
            <option key={c.id} value={c.id}>{c.title}</option>
          ))}
        </select>
        <Button variant="outline" size="sm" onClick={handleNewConversation}>
          New conversation
        </Button>
      </div>

      <div className="flex gap-2">
        <label htmlFor="chat-message" className="sr-only">Message</label>
        <Input id="chat-message" value={message} onChange={(e) => setMessage(e.target.value)} />
        <Button onClick={handleSend} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {runs.length > 0 && (
        <div className="flex flex-col gap-4">
          {runs.map((run) => (
            <div key={run.id} className="punch-corner-lg card-stack-shadow border border-secondary/50 bg-card p-4">
              <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-secondary-tint uppercase">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-secondary" />
                Agent thread
              </p>
              <p>{run.output}</p>
            </div>
          ))}
          {latestRun && <Timeline events={latestRun.events} />}
        </div>
      )}
    </div>
  )
}
```

`skipNextFetch` guards a real race: when `handleSend` creates a brand-new conversation inline, `setConversationId` triggers the history-fetch effect for that id at the same time `handleSend` is about to append the just-created run locally — without the guard, the effect's `listConversationRuns` (which correctly returns `[]` for a conversation with no runs yet) can resolve after the local append and clobber it. The guard only applies to conversations *we* just created (empty by construction); switching to an existing conversation via the selector still fetches normally.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run components/ChatPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatPanel.tsx frontend/components/ChatPanel.test.tsx
git commit -m "feat: add conversation selector and growing message list to ChatPanel"
```

---

### Task 11: MemoryExplorerPanel and workspace wiring

**Files:**
- Create: `frontend/components/MemoryExplorerPanel.tsx`
- Create: `frontend/components/MemoryExplorerPanel.test.tsx`
- Modify: `frontend/components/ProjectWorkspace.tsx`
- Modify: `frontend/components/ProjectWorkspace.test.tsx`

**Interfaces:**
- Consumes: `listConversations`, `searchMemories` (Task 9).

- [ ] **Step 1: Write the failing test for the new panel**

`frontend/components/MemoryExplorerPanel.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listConversations = vi.fn().mockResolvedValue([
  { id: 'conv-1', project_id: 'project-1', title: 'Thread A', created_at: '2026-01-01T00:00:00Z' },
])
const searchMemories = vi.fn().mockResolvedValue([
  {
    score: 0.87,
    project_id: 'project-1',
    conversation_id: 'conv-1',
    run_id: 'run-1',
    input: 'The launch codeword is Bluebird.',
    output: 'ok',
  },
])

vi.mock('@/lib/api', () => ({ listConversations, searchMemories }))

describe('MemoryExplorerPanel', () => {
  it('lists conversations and shows semantic search results', async () => {
    const { default: MemoryExplorerPanel } = await import('./MemoryExplorerPanel')
    render(<MemoryExplorerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('Thread A')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText(/search memory/i), { target: { value: 'launch codeword' } })
    fireEvent.click(screen.getByRole('button', { name: /search/i }))

    await waitFor(() => expect(searchMemories).toHaveBeenCalledWith('project-1', 'launch codeword'))
    await waitFor(() => expect(screen.getByText(/Bluebird/)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run components/MemoryExplorerPanel.test.tsx`
Expected: FAIL — `./MemoryExplorerPanel` doesn't exist.

- [ ] **Step 3: Write `MemoryExplorerPanel.tsx`**

```tsx
'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { listConversations, searchMemories, type Conversation, type MemorySearchResult } from '@/lib/api'

export default function MemoryExplorerPanel({ projectId }: { projectId: string }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MemorySearchResult[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listConversations(projectId)
      .then(setConversations)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load conversations'))
  }, [projectId])

  async function handleSearch() {
    if (!query.trim()) return
    setError(null)
    try {
      setResults(await searchMemories(projectId, query))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search memory')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div>
        <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Conversations</h2>
        <ul className="flex flex-col gap-1">
          {conversations.map((c) => (
            <li key={c.id} className="punch-corner border border-border bg-card p-2 text-sm">
              {c.title}
            </li>
          ))}
        </ul>
      </div>

      <div className="punch-corner-lg card-stack-shadow flex flex-col gap-2 border border-border bg-card p-4">
        <label htmlFor="memory-search" className="text-xs tracking-wide text-muted-foreground uppercase">
          Search memory
        </label>
        <div className="flex gap-2">
          <Input id="memory-search" value={query} onChange={(e) => setQuery(e.target.value)} />
          <Button onClick={handleSearch}>Search</Button>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {results.map((r) => (
          <li key={r.run_id} className="punch-corner border border-border bg-card p-3 text-sm">
            <p className="font-mono text-xs text-muted-foreground">score: {r.score.toFixed(2)}</p>
            <p><span className="font-semibold">User:</span> {r.input}</p>
            <p><span className="font-semibold">Assistant:</span> {r.output}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run components/MemoryExplorerPanel.test.tsx`
Expected: PASS

- [ ] **Step 5: Update `ProjectWorkspace.test.tsx`**

`frontend/components/ProjectWorkspace.test.tsx` (full file) — mock the new panel, move the "empty state" assertion to a tab that's still unbuilt (`prompt-manager`), and add a real switch-to-Memory-Explorer assertion:
```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./ChatPanel', () => ({ default: () => <div>chat-panel</div> }))
vi.mock('./ToolManagerPanel', () => ({ default: () => <div>tool-panel</div> }))
vi.mock('./MemoryExplorerPanel', () => ({ default: () => <div>memory-panel</div> }))

describe('ProjectWorkspace', () => {
  it('switches between Chat/Run, Tool Manager, and Memory Explorer panels', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    expect(screen.getByText('chat-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /tool manager/i }))
    expect(screen.getByText('tool-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /memory explorer/i }))
    expect(screen.getByText('memory-panel')).toBeInTheDocument()
  })

  it('shows an empty-state panel for a not-yet-built tab', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    fireEvent.click(screen.getByRole('button', { name: /prompt manager/i }))
    expect(screen.getByText(/template library with variables/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run to verify it fails against the current `ProjectWorkspace`**

Run: `cd frontend && npx vitest run components/ProjectWorkspace.test.tsx`
Expected: FAIL — `memory-panel` never renders; `memory-explorer` still falls into the empty-state branch.

- [ ] **Step 7: Update `ProjectWorkspace.tsx`**

```tsx
'use client'

import { useState } from 'react'
import WorkspaceNav, { type WorkspaceTab } from './WorkspaceNav'
import ChatPanel from './ChatPanel'
import ToolManagerPanel from './ToolManagerPanel'
import MemoryExplorerPanel from './MemoryExplorerPanel'
import EmptyStatePanel from './EmptyStatePanel'

const EMPTY_STATES: Record<string, { title: string; phase: number; description: string }> = {
  'prompt-manager': {
    title: 'Prompt Manager',
    phase: 2,
    description: 'Template library with variables, version history, and test-run.',
  },
  'knowledge-hub': {
    title: 'Knowledge Hub',
    phase: 1,
    description: 'Upload, indexing status, search, chunk inspection, citations.',
  },
  guardrails: {
    title: 'Guardrails',
    phase: 2,
    description: 'Policies, validation rules, violations log.',
  },
  evaluation: {
    title: 'Evaluation',
    phase: 2,
    description: 'Accuracy, hallucination rate, confidence, benchmark results.',
  },
  observability: {
    title: 'Observability',
    phase: 2,
    description: 'Trace viewer, retrieval path, tool calls, timings.',
  },
  'cost-analytics': {
    title: 'Cost Analytics',
    phase: 3,
    description: 'Token usage, model costs, cache hits/savings.',
  },
  deployment: {
    title: 'Deployment',
    phase: 3,
    description: 'Docker/cloud config, environments, deployment history.',
  },
  settings: {
    title: 'Settings',
    phase: 3,
    description: 'Project and account configuration.',
  },
}

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>('chat')
  const emptyState = EMPTY_STATES[tab]

  return (
    <div className="flex flex-col gap-8 sm:flex-row">
      <WorkspaceNav active={tab} onSelect={setTab} />
      <div className="min-w-0 flex-1">
        {tab === 'chat' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Chat / Run</h1>
            <ChatPanel projectId={projectId} />
          </>
        )}
        {tab === 'tools' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Tool Manager</h1>
            <ToolManagerPanel projectId={projectId} />
          </>
        )}
        {tab === 'memory-explorer' && (
          <>
            <h1 className="font-heading text-2xl font-bold uppercase mb-6">Memory Explorer</h1>
            <MemoryExplorerPanel projectId={projectId} />
          </>
        )}
        {emptyState && <EmptyStatePanel {...emptyState} />}
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Run to verify both test files pass**

Run: `cd frontend && npx vitest run components/ProjectWorkspace.test.tsx components/MemoryExplorerPanel.test.tsx`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add frontend/components/MemoryExplorerPanel.tsx frontend/components/MemoryExplorerPanel.test.tsx frontend/components/ProjectWorkspace.tsx frontend/components/ProjectWorkspace.test.tsx
git commit -m "feat: add Memory Explorer panel and wire it into the workspace"
```

---

### Task 12: E2E — memory recall and cross-conversation semantic search

**Files:**
- Create: `frontend/e2e/memory-recall.spec.ts`

**Interfaces:**
- Consumes: the full stack via `docker compose up` (Tasks 1-11), a live Supabase project with email confirmation disabled for test signups (existing requirement, unchanged).

- [ ] **Step 1: Write the E2E spec**

`frontend/e2e/memory-recall.spec.ts`:
```ts
import { test, expect } from '@playwright/test'

test('recalls the first message when asked in the same conversation', async ({ page }) => {
  const email = `kartikarora1240+memory-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Memory Test Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /memory test project/i }).click()

  await page.getByLabel(/message/i).fill("My favorite color is teal. Reply with just 'ok'.")
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText(/ok/i)).toBeVisible({ timeout: 15000 })

  await page.getByLabel(/message/i).fill('What is my favorite color? Reply with just the color.')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText(/teal/i)).toBeVisible({ timeout: 15000 })
})

test('semantic search finds an earlier turn from a different conversation', async ({ page }) => {
  const email = `kartikarora1240+memsearch-${Date.now()}@gmail.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Memory Search Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /memory search project/i }).click()

  await page.getByLabel(/message/i).fill('The launch codeword for our rocket is Bluebird.')
  await page.getByRole('button', { name: /send/i }).click()
  await expect(page.getByText('run_started')).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: /new conversation/i }).click()
  await page.getByRole('button', { name: /memory explorer/i }).click()

  await page.getByLabel(/search memory/i).fill('rocket launch codeword')
  await page.getByRole('button', { name: /search/i }).click()

  await expect(page.getByText(/Bluebird/i)).toBeVisible({ timeout: 15000 })
})
```

- [ ] **Step 2: Run to verify both pass**

Prerequisite: `docker compose up` (all services including `qdrant`), Supabase migrations `0001`-`0003` applied, email confirmation disabled for test signups — same preconditions the existing `golden-path.spec.ts`/`tool-calling.spec.ts` already document in `CLAUDE.md`.

Run: `cd frontend && npx playwright test memory-recall.spec.ts`
Expected: PASS (2 tests)

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/memory-recall.spec.ts
git commit -m "test: add E2E coverage for conversation recall and semantic memory search"
```

---

## Post-plan: update CLAUDE.md

Once all 12 tasks pass, update the "Status" section of `CLAUDE.md` to record that Phase 1 sub-project 2 (Memory) is implemented and verified, listing the new migration (`0003_memory.sql`) alongside the existing two, and noting the Memory Explorer panel is no longer an empty state. This is documentation housekeeping, not a task with its own tests — do it by hand after Task 12 passes.
