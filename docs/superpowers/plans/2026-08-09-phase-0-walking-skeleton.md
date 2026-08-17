# Phase 0 — Walking Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the full request lifecycle — User → Dashboard → Project → Run → Orchestrator → Agent → LLM Gateway → Response — end-to-end, running via `docker compose up`, with no capability beyond that loop.

**Architecture:** FastAPI backend exposes `/projects` and `/runs`; a single-node LangGraph graph calls Groq for the actual reasoning step. Supabase provides Postgres (projects/runs/run_events tables) and Auth; the backend forwards each request's Supabase JWT into a per-request Supabase client so Row Level Security enforces per-owner data isolation — no application-level permission checks are written. Next.js frontend handles login/signup via Supabase Auth, a Dashboard listing projects, and a Project Workspace whose only working tab is Chat/Run (other tabs render as disabled nav entries).

**Tech Stack:** Python 3.11 + FastAPI + LangGraph + `groq` SDK + `supabase-py` + PyJWT (backend). Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + `@supabase/supabase-js` (frontend). Docker Compose (backend + frontend only — no Qdrant in this phase). Vitest + React Testing Library for frontend unit tests, Playwright for the golden-path E2E test, pytest for backend.

## Global Constraints

- Groq is the only LLM provider. No provider-abstraction interface.
- LangGraph graph in this phase has exactly one node. No multi-agent, no RAG, no memory, no tool calling — those are Phase 1.
- No Guardrails, Evaluation, Prompt Management, Token Optimization, Cost Analytics, or Deployment UI in this phase — those are Phase 2/3.
- No Qdrant in this phase's `docker-compose.yml`.
- Permissions are enforced entirely by Supabase Row Level Security via the forwarded user JWT. Do not add application-level `if owner_id != user.id` checks — if RLS isn't doing the job, fix the RLS policy, don't duplicate the check in Python.
- Required environment variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GROQ_API_KEY` (backend); `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL` (frontend). These come from the user — do not fabricate values. Any task step that calls Groq or Supabase for real will fail without them; that is expected, not a bug, until the user supplies credentials. Auth verification uses Supabase's JWKS endpoint (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`), derived from `SUPABASE_URL` — there is no separate JWT secret env var (this project's Supabase instance uses ES256 signing keys, not a shared HS256 secret).
- Frontend workspace nav items other than "Chat / Run" render disabled, with no backing data or mock content.

---

### Task 1: Backend scaffolding, config, health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/.env.example`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `.supabase_url`, `.supabase_anon_key`, `.groq_api_key` — all `str`), `app.main.app` (the FastAPI instance later tasks attach routers to via `app.include_router(...)`).

- [ ] **Step 1: Create the backend package layout and dependency file**

`backend/requirements.txt`:
```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic-settings>=2.6
supabase>=2.9
PyJWT>=2.9
groq>=0.13
langgraph>=0.2
pytest>=8.3
httpx>=0.27
```

`backend/pytest.ini`:
```ini
[pytest]
pythonpath = .
```

`backend/app/__init__.py`: empty file.

`backend/.env.example`:
```
SUPABASE_URL=
SUPABASE_ANON_KEY=
GROQ_API_KEY=
```

- [ ] **Step 2: Write `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    groq_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 3: Write `backend/app/main.py` with a health endpoint**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Engineering Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Write the failing test**

`backend/tests/test_health.py`:
```python
import os

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Install dependencies and run the test**

Run: `cd backend && pip install -r requirements.txt && pytest tests/test_health.py -v`
Expected: FAIL only if step 3 wasn't written yet — since step 3 is already written above, this should PASS. If it fails, check that `app.main` imports cleanly.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/app/__init__.py backend/app/config.py backend/app/main.py backend/.env.example backend/tests/test_health.py
git commit -m "feat: backend scaffolding with health check"
```

---

### Task 2: Groq LLM Gateway client

**Files:**
- Create: `backend/app/llm.py`
- Test: `backend/tests/test_llm.py`

**Interfaces:**
- Consumes: `app.config.settings.groq_api_key` (Task 1).
- Produces: `app.llm.generate(prompt: str) -> str`.

- [ ] **Step 1: Write the failing test**

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
    result = generate("Say the word 'pong' and nothing else.")
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run test to verify it's skipped without real credentials**

Run: `cd backend && pytest tests/test_llm.py -v`
Expected: SKIPPED (no real `GROQ_API_KEY` set yet) — this is correct, not a failure.

- [ ] **Step 3: Write the implementation**

`backend/app/llm.py`:
```python
from groq import Groq

from app.config import settings

_client = Groq(api_key=settings.groq_api_key)

MODEL = "llama-3.3-70b-versatile"


def generate(prompt: str) -> str:
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
```

- [ ] **Step 4: Run test with a real key once available**

Run: `cd backend && GROQ_API_KEY=<real key> SUPABASE_URL=http://localhost SUPABASE_ANON_KEY=test pytest tests/test_llm.py -v`
Expected: PASS, with a real Groq response. If `GROQ_API_KEY` isn't available yet, leave this step for later and proceed — Task 1's scaffolding test already proves the harness works.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/test_llm.py
git commit -m "feat: Groq LLM Gateway client"
```

---

### Task 3: Single-agent LangGraph graph

**Files:**
- Create: `backend/app/graph.py`
- Test: `backend/tests/test_graph.py`

**Interfaces:**
- Consumes: `app.llm.generate(prompt: str) -> str` (Task 2).
- Produces: `app.graph.agent_graph` (a compiled LangGraph graph); `agent_graph.invoke({"input": str, "output": ""}) -> {"input": str, "output": str}`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_graph.py`:
```python
import os
import pytest

from app.graph import agent_graph


@pytest.mark.skipif(
    os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real GROQ_API_KEY required for this integration test",
)
def test_agent_graph_produces_output():
    result = agent_graph.invoke({"input": "Say the word 'pong' and nothing else.", "output": ""})
    assert result["output"]
    assert result["input"] == "Say the word 'pong' and nothing else."
```

- [ ] **Step 2: Run test to verify it's skipped**

Run: `cd backend && pytest tests/test_graph.py -v`
Expected: SKIPPED without a real `GROQ_API_KEY`.

- [ ] **Step 3: Write the implementation**

`backend/app/graph.py`:
```python
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.llm import generate


class AgentState(TypedDict):
    input: str
    output: str


def run_agent(state: AgentState) -> AgentState:
    return {"input": state["input"], "output": generate(state["input"])}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", run_agent)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()


agent_graph = build_graph()
```

- [ ] **Step 4: Run test with a real key once available**

Run: `cd backend && GROQ_API_KEY=<real key> SUPABASE_URL=http://localhost SUPABASE_ANON_KEY=test pytest tests/test_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph.py backend/tests/test_graph.py
git commit -m "feat: single-agent LangGraph graph"
```

---

### Task 4: Supabase schema and RLS policies

**Files:**
- Create: `backend/migrations/0001_init.sql`

**Interfaces:**
- Produces: tables `projects(id, owner_id, name, created_at)`, `runs(id, project_id, status, input, output, created_at)`, `run_events(id, run_id, step_name, payload, created_at)`, each with an owner-scoped RLS policy.

- [ ] **Step 1: Write the migration**

`backend/migrations/0001_init.sql`:
```sql
create table projects (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null default auth.uid() references auth.users(id),
    name text not null,
    created_at timestamptz not null default now()
);

create table runs (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    status text not null default 'running',
    input text not null,
    output text,
    created_at timestamptz not null default now()
);

create table run_events (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references runs(id) on delete cascade,
    step_name text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

alter table projects enable row level security;
alter table runs enable row level security;
alter table run_events enable row level security;

create policy "owner can access own projects" on projects
    for all
    using (owner_id = auth.uid())
    with check (owner_id = auth.uid());

create policy "owner can access own runs" on runs
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own run_events" on run_events
    for all
    using (
        run_id in (
            select r.id from runs r
            join projects p on p.id = r.project_id
            where p.owner_id = auth.uid()
        )
    )
    with check (
        run_id in (
            select r.id from runs r
            join projects p on p.id = r.project_id
            where p.owner_id = auth.uid()
        )
    );
```

- [ ] **Step 2: Apply the migration**

In the Supabase project's SQL Editor (dashboard), paste and run the contents of `backend/migrations/0001_init.sql`. This requires the user's Supabase project URL/credentials — pause here and ask the user for them if not yet provided.

- [ ] **Step 3: Verify the tables and RLS**

In the Supabase SQL Editor, run:
```sql
select table_name from information_schema.tables where table_schema = 'public';
```
Expected: `projects`, `runs`, `run_events` are listed. Then run:
```sql
select relname, relrowsecurity from pg_class where relname in ('projects', 'runs', 'run_events');
```
Expected: `relrowsecurity` is `true` for all three.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/0001_init.sql
git commit -m "feat: Supabase schema and RLS policies for projects/runs/run_events"
```

---

### Task 5: Auth dependency and per-request Supabase client

**This project's Supabase instance uses the newer asymmetric signing-key
system (ES256 + JWKS), confirmed by fetching
`<SUPABASE_URL>/auth/v1/.well-known/jwks.json` and getting back a valid JWKS
document with an ES256 EC key. There is no shared HS256 "JWT Secret" to
configure — verification is done against the public JWKS endpoint instead,
which is derived from `SUPABASE_URL`, so no new required env var is needed.**

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/app/db.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `settings.supabase_url`, `settings.supabase_anon_key` (Task 1).
- Produces: `app.auth.get_current_user(authorization: str = Header(...)) -> dict` (FastAPI dependency; returns `{"id": str, "token": str}`, raises `HTTPException(401)` on missing/invalid token). `app.db.get_user_client(token: str) -> supabase.Client`. `tests/conftest.py`'s `auth_headers` fixture (used by this task and reused by Tasks 6/7 — do not redefine it there).

- [ ] **Step 1: Add the `cryptography` extra for ES256 support**

PyJWT's ES256 algorithm requires the `cryptography` package. In `backend/requirements.txt`, change the `PyJWT>=2.9` line to:
```
PyJWT[crypto]>=2.9
```
Run: `cd backend && pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`backend/tests/test_auth.py`:
```python
import os

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.auth import get_current_user

app = FastAPI()


@app.get("/whoami")
def whoami(user=Depends(get_current_user)):
    return {"id": user["id"]}


client = TestClient(app)


def test_missing_token_returns_401():
    response = client.get("/whoami")
    assert response.status_code in (401, 422)


def test_invalid_token_returns_401():
    response = client.get("/whoami", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.skipif(
    "SUPABASE_TEST_USER_TOKEN" not in os.environ,
    reason="Real Supabase user session token required for this integration test",
)
def test_valid_token_returns_user_id(auth_headers):
    response = client.get("/whoami", headers=auth_headers)
    assert response.status_code == 200
    assert "id" in response.json()
```

`backend/tests/conftest.py`:
```python
import os

import pytest


@pytest.fixture
def auth_headers():
    """
    Real end-to-end auth requires a live Supabase user session token,
    ES256-signed by Supabase's own key and verified here via JWKS. Set
    SUPABASE_TEST_USER_TOKEN in the environment (obtained by signing in a
    real test user against the real Supabase project) before running
    integration tests that use this fixture.
    """
    token = os.environ["SUPABASE_TEST_USER_TOKEN"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 4: Write `backend/app/auth.py`**

```python
import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import settings

_jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"id": payload["sub"], "token": token}
```

`PyJWKClient` fetches and caches the JWKS lazily (only on first `get_signing_key_from_jwt` call), so module import and the missing/invalid-token tests never make a network call — only the real-token integration test does.

- [ ] **Step 5: Write `backend/app/db.py`**

```python
from supabase import Client, create_client

from app.config import settings


def get_user_client(token: str) -> Client:
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return client
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: `test_missing_token_returns_401` and `test_invalid_token_returns_401` PASS. `test_valid_token_returns_user_id` SKIPPED until a real `SUPABASE_TEST_USER_TOKEN` is available (obtained by signing in a real test user via Supabase Auth and taking the session's `access_token`).

- [ ] **Step 7: Commit**

```bash
git add backend/app/auth.py backend/app/db.py backend/tests/conftest.py backend/tests/test_auth.py backend/requirements.txt
git commit -m "feat: JWKS-based auth dependency and per-request Supabase client"
```

---

### Task 6: Projects API

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/projects.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_projects.py`

**Interfaces:**
- Consumes: `app.auth.get_current_user`, `app.db.get_user_client` (Task 5).
- Produces: `app.models.ProjectCreate {name: str}`, `app.models.ProjectOut {id: str, name: str, created_at: datetime}`. Routes: `POST /projects`, `GET /projects`.

- [ ] **Step 1: Write `backend/app/models.py`**

```python
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: str
    name: str
    created_at: datetime
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_projects.py`:
```python
import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_project_requires_auth():
    response = client.post("/projects", json={"name": "Test Project"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_and_list_projects(auth_headers):
    create_response = client.post("/projects", json={"name": "Test Project"}, headers=auth_headers)
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "Test Project"

    list_response = client.get("/projects", headers=auth_headers)
    assert list_response.status_code == 200
    names = [p["name"] for p in list_response.json()]
    assert "Test Project" in names
```

`auth_headers` is already defined in `backend/tests/conftest.py` by Task 5 — do not redefine it here, this test just consumes it.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_projects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api'` (or similar import error on the not-yet-existing router).

- [ ] **Step 4: Write `backend/app/api/__init__.py`** (empty file)

- [ ] **Step 5: Write `backend/app/api/projects.py`**

```python
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("projects").insert({"name": body.name}).execute()
    return result.data[0]


@router.get("", response_model=list[ProjectOut])
def list_projects(user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("projects").select("*").order("created_at", desc=True).execute()
    return result.data
```

- [ ] **Step 6: Mount the router in `backend/app/main.py`**

Add near the top:
```python
from app.api import projects
```
Add after the `CORSMiddleware` block:
```python
app.include_router(projects.router)
```

- [ ] **Step 7: Run tests to verify the auth-required case passes**

Run: `cd backend && pytest tests/test_projects.py -v`
Expected: `test_create_project_requires_auth` PASSES. `test_create_and_list_projects` SKIPPED until a real Supabase project + `SUPABASE_TEST_USER_TOKEN` are available.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/api/__init__.py backend/app/api/projects.py backend/app/main.py backend/tests/test_projects.py
git commit -m "feat: Projects API"
```

---

### Task 7: Runs API

**Files:**
- Modify: `backend/app/models.py` (add run models)
- Create: `backend/app/api/runs.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_runs.py`

**Interfaces:**
- Consumes: `app.auth.get_current_user`, `app.db.get_user_client` (Task 5), `app.graph.agent_graph` (Task 3).
- Produces: `app.models.RunCreate {input: str}`, `app.models.RunEventOut {id, step_name, payload, created_at}`, `app.models.RunOut {id, status, output, events: list[RunEventOut]}`. Routes: `POST /projects/{project_id}/runs`, `GET /runs/{run_id}`.

- [ ] **Step 1: Add run models to `backend/app/models.py`**

Append:
```python
class RunCreate(BaseModel):
    input: str


class RunEventOut(BaseModel):
    id: str
    step_name: str
    payload: dict
    created_at: datetime


class RunOut(BaseModel):
    id: str
    status: str
    output: str | None
    events: list[RunEventOut]
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_runs.py`:
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
    response = client.post("/projects/some-id/runs", json={"input": "hello"})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost"
    or os.environ.get("GROQ_API_KEY", "test") == "test",
    reason="Real Supabase project and GROQ_API_KEY required for this integration test",
)
def test_create_run_executes_graph_and_records_events(auth_headers):
    project_response = client.post("/projects", json={"name": "Run Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    run_response = client.post(
        f"/projects/{project_id}/runs",
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_runs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.runs'`.

- [ ] **Step 4: Write `backend/app/api/runs.py`**

```python
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_user_client
from app.graph import agent_graph
from app.models import RunCreate, RunOut

router = APIRouter(tags=["runs"])


@router.post("/projects/{project_id}/runs", response_model=RunOut)
def create_run(project_id: str, body: RunCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])

    run = client.table("runs").insert(
        {"project_id": project_id, "status": "running", "input": body.input}
    ).execute().data[0]
    run_id = run["id"]

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "run_started", "payload": {"input": body.input}}
    ).execute()

    result = agent_graph.invoke({"input": body.input, "output": ""})

    client.table("run_events").insert(
        {"run_id": run_id, "step_name": "agent_responded", "payload": {"output": result["output"]}}
    ).execute()

    updated = client.table("runs").update(
        {"status": "completed", "output": result["output"]}
    ).eq("id", run_id).execute().data[0]

    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**updated, "events": events}


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    run = client.table("runs").select("*").eq("id", run_id).single().execute().data
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    events = client.table("run_events").select("*").eq("run_id", run_id).order("created_at").execute().data
    return {**run, "events": events}
```

- [ ] **Step 5: Mount the router in `backend/app/main.py`**

Add near the top:
```python
from app.api import runs
```
Add after `app.include_router(projects.router)`:
```python
app.include_router(runs.router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_runs.py -v`
Expected: `test_create_run_requires_auth` PASSES. `test_create_run_executes_graph_and_records_events` SKIPPED until real Supabase + Groq credentials are available; run it again once they are.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/app/api/runs.py backend/app/main.py backend/tests/test_runs.py
git commit -m "feat: Runs API executing the agent graph"
```

---

### Task 8: Backend Dockerfile and Compose service

**Files:**
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example` (repo root)

**Interfaces:**
- Produces: `backend` service reachable at `http://localhost:8000` under Compose.

- [ ] **Step 1: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
```

- [ ] **Step 3: Write `.env.example` at the repo root**

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
GROQ_API_KEY=
```

- [ ] **Step 4: Build and verify**

Run: `docker compose build backend`
Expected: image builds without error.

Once a real `.env` exists (copy `.env.example` to `.env` and fill in real values):
Run: `docker compose up backend` then in another terminal `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: backend Dockerfile and Compose service"
```

---

### Task 9: Frontend scaffold and Supabase client

**Files:**
- Create: `frontend/` (via `create-next-app`)
- Create: `frontend/lib/supabaseClient.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/.env.local.example`
- Create: `frontend/vitest.config.ts`
- Test: `frontend/lib/api.test.ts`

**Interfaces:**
- Produces: `supabase` (configured Supabase JS client), `createProject(name: string): Promise<Project>`, `listProjects(): Promise<Project[]>`, `createRun(projectId: string, input: string): Promise<Run>`, `getRun(runId: string): Promise<Run>`, where `Project = {id: string, name: string, created_at: string}`, `RunEvent = {id: string, step_name: string, payload: Record<string, unknown>, created_at: string}`, `Run = {id: string, status: string, output: string | null, events: RunEvent[]}`.

- [ ] **Step 1: Scaffold the Next.js app**

Run:
```bash
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"
cd frontend
npx shadcn@latest init -d
npx shadcn@latest add button input card
npm install @supabase/supabase-js
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Write `frontend/.env.local.example`**

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Write `frontend/lib/supabaseClient.ts`**

```typescript
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

- [ ] **Step 4: Write the failing test**

`frontend/lib/api.test.ts`:
```typescript
import { describe, expect, it, vi, beforeEach } from 'vitest'

vi.mock('./supabaseClient', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

describe('api client', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: '1', name: 'Test Project', created_at: '2026-01-01T00:00:00Z' }),
    }) as unknown as typeof fetch
  })

  it('createProject sends an authorized POST request', async () => {
    const { createProject } = await import('./api')
    const result = await createProject('Test Project')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
    expect(result.name).toBe('Test Project')
  })
})
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL — `./api` module doesn't exist yet.

- [ ] **Step 6: Write `frontend/lib/api.ts`**

```typescript
import { supabase } from './supabaseClient'

export type Project = { id: string; name: string; created_at: string }
export type RunEvent = { id: string; step_name: string; payload: Record<string, unknown>; created_at: string }
export type Run = { id: string; status: string; output: string | null; events: RunEvent[] }

const API_URL = process.env.NEXT_PUBLIC_API_URL!

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  return { Authorization: `Bearer ${data.session?.access_token}` }
}

export async function createProject(name: string): Promise<Project> {
  const res = await fetch(`${API_URL}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw new Error('Failed to create project')
  return res.json()
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_URL}/projects`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list projects')
  return res.json()
}

export async function createRun(projectId: string, input: string): Promise<Run> {
  const res = await fetch(`${API_URL}/projects/${projectId}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify({ input }),
  })
  if (!res.ok) throw new Error('Failed to create run')
  return res.json()
}

export async function getRun(runId: string): Promise<Run> {
  const res = await fetch(`${API_URL}/runs/${runId}`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to fetch run')
  return res.json()
}
```

- [ ] **Step 7: Write `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
  },
})
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend
git commit -m "feat: frontend scaffold with Supabase client and API wrapper"
```

---

### Task 10: Landing page and auth pages

**Files:**
- Modify: `frontend/app/page.tsx` (landing page)
- Create: `frontend/components/AuthForm.tsx`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/signup/page.tsx`
- Test: `frontend/components/AuthForm.test.tsx`

**Interfaces:**
- Consumes: `supabase` (Task 9).
- Produces: `<AuthForm mode="login" | "signup" onSuccess={() => void} />`.

- [ ] **Step 1: Write `frontend/app/page.tsx`**

```tsx
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const FEATURES = [
  { title: 'Multi-Agent Orchestration', description: 'Planner, Researcher, Executor and Verifier agents coordinated through a central runtime.' },
  { title: 'Advanced RAG', description: 'Hybrid retrieval, metadata filtering, citations, context compression.' },
  { title: 'Guardrails', description: 'Prompt injection detection, PII masking, schema validation and policy checks.' },
]

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-bold">AI Engineering Platform</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Reusable AI engineering capabilities for reliable AI applications.
      </p>
      <div className="mt-6 flex gap-3">
        <Button asChild>
          <Link href="/signup">Get started</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/login">Log in</Link>
        </Button>
      </div>
      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {FEATURES.map((feature) => (
          <Card key={feature.title}>
            <CardHeader>
              <CardTitle className="text-base">{feature.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{feature.description}</CardContent>
          </Card>
        ))}
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Write the failing test for AuthForm**

`frontend/components/AuthForm.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const signInWithPassword = vi.fn().mockResolvedValue({ error: null })

vi.mock('@/lib/supabaseClient', () => ({
  supabase: { auth: { signInWithPassword, signUp: vi.fn() } },
}))

describe('AuthForm', () => {
  it('calls signInWithPassword with entered credentials in login mode', async () => {
    const { default: AuthForm } = await import('./AuthForm')
    const onSuccess = vi.fn()
    render(<AuthForm mode="login" onSuccess={onSuccess} />)

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@example.com' } })
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'hunter2' } })
    fireEvent.click(screen.getByRole('button', { name: /log in/i }))

    await waitFor(() => expect(signInWithPassword).toHaveBeenCalledWith({ email: 'user@example.com', password: 'hunter2' }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalled())
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: FAIL — `./AuthForm` doesn't exist yet.

- [ ] **Step 4: Write `frontend/components/AuthForm.tsx`**

```tsx
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { supabase } from '@/lib/supabaseClient'

type Props = {
  mode: 'login' | 'signup'
  onSuccess: () => void
}

export default function AuthForm({ mode, onSuccess }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const { error } = mode === 'login'
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password })

    if (error) {
      setError(error.message)
      return
    }
    onSuccess()
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 max-w-sm">
      <label htmlFor="email">Email</label>
      <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      <label htmlFor="password">Password</label>
      <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit">{mode === 'login' ? 'Log in' : 'Sign up'}</Button>
    </form>
  )
}
```

- [ ] **Step 5: Write `frontend/app/login/page.tsx`**

```tsx
'use client'

import { useRouter } from 'next/navigation'
import AuthForm from '@/components/AuthForm'

export default function LoginPage() {
  const router = useRouter()
  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-bold mb-6">Log in</h1>
      <AuthForm mode="login" onSuccess={() => router.push('/dashboard')} />
    </main>
  )
}
```

- [ ] **Step 6: Write `frontend/app/signup/page.tsx`**

```tsx
'use client'

import { useRouter } from 'next/navigation'
import AuthForm from '@/components/AuthForm'

export default function SignupPage() {
  const router = useRouter()
  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-2xl font-bold mb-6">Sign up</h1>
      <AuthForm mode="signup" onSuccess={() => router.push('/dashboard')} />
    </main>
  )
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/AuthForm.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/app/page.tsx frontend/components/AuthForm.tsx frontend/components/AuthForm.test.tsx frontend/app/login/page.tsx frontend/app/signup/page.tsx
git commit -m "feat: landing page and login/signup"
```

---

### Task 11: Dashboard

**Files:**
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/components/ProjectList.tsx`
- Test: `frontend/components/ProjectList.test.tsx`

**Interfaces:**
- Consumes: `listProjects`, `createProject`, `Project` (Task 9).
- Produces: `<ProjectList projects={Project[]} onCreate={(name: string) => void} />`.

- [ ] **Step 1: Write the failing test**

`frontend/components/ProjectList.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ProjectList from './ProjectList'

describe('ProjectList', () => {
  it('renders project names and calls onCreate with the entered name', () => {
    const onCreate = vi.fn()
    render(
      <ProjectList
        projects={[{ id: '1', name: 'Alpha', created_at: '2026-01-01T00:00:00Z' }]}
        onCreate={onCreate}
      />
    )

    expect(screen.getByText('Alpha')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/new project name/i), { target: { value: 'Beta' } })
    fireEvent.click(screen.getByRole('button', { name: /create/i }))

    expect(onCreate).toHaveBeenCalledWith('Beta')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ProjectList.test.tsx`
Expected: FAIL — `./ProjectList` doesn't exist yet.

- [ ] **Step 3: Write `frontend/components/ProjectList.tsx`**

```tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { Project } from '@/lib/api'

type Props = {
  projects: Project[]
  onCreate: (name: string) => void
}

export default function ProjectList({ projects, onCreate }: Props) {
  const [name, setName] = useState('')

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-2">
        {projects.map((project) => (
          <li key={project.id}>
            <Link href={`/projects/${project.id}`} className="underline">
              {project.name}
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <label htmlFor="new-project-name" className="sr-only">New project name</label>
        <Input
          id="new-project-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name"
        />
        <Button
          onClick={() => {
            onCreate(name)
            setName('')
          }}
        >
          Create
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ProjectList.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write `frontend/app/dashboard/page.tsx`**

```tsx
'use client'

import { useEffect, useState } from 'react'
import { createProject, listProjects, type Project } from '@/lib/api'
import ProjectList from '@/components/ProjectList'

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]))
  }, [])

  async function handleCreate(name: string) {
    if (!name.trim()) return
    const project = await createProject(name)
    setProjects((prev) => [project, ...prev])
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <ProjectList projects={projects} onCreate={handleCreate} />
    </main>
  )
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/app/dashboard/page.tsx frontend/components/ProjectList.tsx frontend/components/ProjectList.test.tsx
git commit -m "feat: dashboard with project list and creation"
```

---

### Task 12: Project workspace — Chat/Run panel and timeline

**Files:**
- Create: `frontend/app/projects/[id]/page.tsx`
- Create: `frontend/components/WorkspaceNav.tsx`
- Create: `frontend/components/ChatPanel.tsx`
- Create: `frontend/components/Timeline.tsx`
- Test: `frontend/components/ChatPanel.test.tsx`
- Test: `frontend/components/WorkspaceNav.test.tsx`

**Interfaces:**
- Consumes: `createRun`, `Run`, `RunEvent` (Task 9).
- Produces: `<WorkspaceNav active="chat" />`, `<ChatPanel projectId={string} />`, `<Timeline events={RunEvent[]} />`.

- [ ] **Step 1: Write the failing WorkspaceNav test**

`frontend/components/WorkspaceNav.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import WorkspaceNav from './WorkspaceNav'

describe('WorkspaceNav', () => {
  it('renders Chat / Run as enabled and other tabs as disabled', () => {
    render(<WorkspaceNav active="chat" />)
    expect(screen.getByRole('link', { name: /chat \/ run/i })).toBeInTheDocument()
    expect(screen.getByText(/prompt manager/i).closest('[aria-disabled="true"]')).toBeTruthy()
    expect(screen.getByText(/knowledge hub/i).closest('[aria-disabled="true"]')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/WorkspaceNav.test.tsx`
Expected: FAIL — `./WorkspaceNav` doesn't exist yet.

- [ ] **Step 3: Write `frontend/components/WorkspaceNav.tsx`**

```tsx
import Link from 'next/link'

const DISABLED_TABS = [
  'Prompt Manager',
  'Knowledge Hub',
  'Tool Manager',
  'Memory Explorer',
  'Guardrails',
  'Evaluation',
  'Observability',
  'Cost Analytics',
  'Deployment',
  'Settings',
]

export default function WorkspaceNav({ active }: { active: 'chat' }) {
  return (
    <nav className="flex flex-col gap-1 w-48">
      <Link
        href="#"
        className={active === 'chat' ? 'font-semibold underline' : ''}
      >
        Chat / Run
      </Link>
      {DISABLED_TABS.map((tab) => (
        <span key={tab} aria-disabled="true" className="text-muted-foreground cursor-not-allowed">
          {tab}
        </span>
      ))}
    </nav>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/WorkspaceNav.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write `frontend/components/Timeline.tsx`**

```tsx
import type { RunEvent } from '@/lib/api'

export default function Timeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">No events yet.</p>
  }
  return (
    <ol className="flex flex-col gap-2">
      {events.map((event) => (
        <li key={event.id} className="text-sm border-l-2 pl-3">
          <span className="font-mono">{event.step_name}</span>
          <span className="text-muted-foreground"> — {new Date(event.created_at).toLocaleTimeString()}</span>
        </li>
      ))}
    </ol>
  )
}
```

- [ ] **Step 6: Write the failing ChatPanel test**

`frontend/components/ChatPanel.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const createRun = vi.fn().mockResolvedValue({
  id: 'run-1',
  status: 'completed',
  output: 'pong',
  events: [{ id: 'e1', step_name: 'run_started', payload: {}, created_at: '2026-01-01T00:00:00Z' }],
})

vi.mock('@/lib/api', () => ({ createRun }))

describe('ChatPanel', () => {
  it('sends input and displays the response and timeline', async () => {
    const { default: ChatPanel } = await import('./ChatPanel')
    render(<ChatPanel projectId="project-1" />)

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: 'ping' } })
    fireEvent.click(screen.getByRole('button', { name: /send/i }))

    await waitFor(() => expect(createRun).toHaveBeenCalledWith('project-1', 'ping'))
    await waitFor(() => expect(screen.getByText('pong')).toBeInTheDocument())
    expect(screen.getByText('run_started')).toBeInTheDocument()
  })
})
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ChatPanel.test.tsx`
Expected: FAIL — `./ChatPanel` doesn't exist yet.

- [ ] **Step 8: Write `frontend/components/ChatPanel.tsx`**

```tsx
'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createRun, type Run } from '@/lib/api'
import Timeline from './Timeline'

export default function ChatPanel({ projectId }: { projectId: string }) {
  const [message, setMessage] = useState('')
  const [run, setRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSend() {
    if (!message.trim()) return
    setLoading(true)
    try {
      const result = await createRun(projectId, message)
      setRun(result)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        <label htmlFor="chat-message" className="sr-only">Message</label>
        <Input id="chat-message" value={message} onChange={(e) => setMessage(e.target.value)} />
        <Button onClick={handleSend} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </Button>
      </div>
      {run && (
        <div className="flex flex-col gap-4">
          <p className="rounded border p-3">{run.output}</p>
          <Timeline events={run.events} />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ChatPanel.test.tsx`
Expected: PASS.

- [ ] **Step 10: Write `frontend/app/projects/[id]/page.tsx`**

```tsx
import WorkspaceNav from '@/components/WorkspaceNav'
import ChatPanel from '@/components/ChatPanel'

export default function ProjectWorkspacePage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16 flex gap-8">
      <WorkspaceNav active="chat" />
      <div className="flex-1">
        <h1 className="text-2xl font-bold mb-6">Chat / Run</h1>
        <ChatPanel projectId={params.id} />
      </div>
    </main>
  )
}
```

- [ ] **Step 11: Commit**

```bash
git add frontend/app/projects frontend/components/WorkspaceNav.tsx frontend/components/WorkspaceNav.test.tsx frontend/components/ChatPanel.tsx frontend/components/ChatPanel.test.tsx frontend/components/Timeline.tsx
git commit -m "feat: project workspace with chat/run panel and timeline"
```

---

### Task 13: Frontend Dockerfile and full Compose

**Files:**
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml` (add frontend service)
- Modify: `.env.example` (repo root — add three `NEXT_PUBLIC_` keys)

**Interfaces:**
- Produces: `frontend` service reachable at `http://localhost:3000` under Compose, talking to `backend` at `http://backend:8000` inside the Compose network (and `http://localhost:8000` from the host browser via `NEXT_PUBLIC_API_URL`).

**Next.js inlines `NEXT_PUBLIC_*` env vars at build time**, not container runtime, so Compose's `env_file:` (which only affects the running container) cannot supply them to `RUN npm run build` inside the image build. The Dockerfile and Compose file below use explicit `ARG`/`ENV` and `build.args` to solve this.

- [ ] **Step 1: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "start"]
```

- [ ] **Step 2: Update `docker-compose.yml`**

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env

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
```

Compose auto-loads the root `.env` for `${...}` substitution in the compose file itself (separate from `env_file:`), so the root `.env` needs the three `NEXT_PUBLIC_` keys too.

- [ ] **Step 3: Add the three `NEXT_PUBLIC_` keys to `.env.example` at the repo root**

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
GROQ_API_KEY=

NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 4: Build and verify**

Run: `docker compose build`
Expected: both images build without error once the real root `.env` has all six keys populated.

Run: `docker compose up`
Expected: `http://localhost:3000` loads the landing page, `http://localhost:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: frontend Dockerfile and full Compose stack"
```

---

### Task 14: Golden-path E2E test and Commands doc

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/golden-path.spec.ts`
- Modify: `CLAUDE.md` (fill in the "Commands" section)

**Interfaces:**
- Consumes: the full running stack (`docker compose up`), a real Supabase project, and a real Groq key.

- [ ] **Step 1: Install Playwright**

Run: `cd frontend && npm init playwright@latest -- --quiet --browser=chromium`

- [ ] **Step 2: Write `frontend/playwright.config.ts`**

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:3000',
  },
})
```

- [ ] **Step 3: Write the golden-path test**

`frontend/e2e/golden-path.spec.ts`:
```typescript
import { test, expect } from '@playwright/test'

test('signup, create project, run a message, see the response and timeline', async ({ page }) => {
  const email = `test-${Date.now()}@example.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Golden Path Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /golden path project/i }).click()

  await page.getByLabel(/message/i).fill("Say the word 'pong' and nothing else.")
  await page.getByRole('button', { name: /send/i }).click()

  await expect(page.getByText(/pong/i)).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('run_started')).toBeVisible()
  await expect(page.getByText('agent_responded')).toBeVisible()
})
```

- [ ] **Step 4: Run the test against the real stack**

This requires `docker compose up` running with real Supabase and Groq credentials, and that Supabase Auth has email confirmation disabled for test signups (or the test account pre-confirmed) so `signUp` logs the user in immediately.

Run: `cd frontend && npx playwright test`
Expected: PASS — 1 passed. This is the Phase 0 exit criteria from the design spec; do not consider Phase 0 done until this passes for real.

- [ ] **Step 5: Fill in the Commands section of `CLAUDE.md`**

Replace the "Not yet defined..." paragraph under `## Commands` with:

```markdown
Backend (from `backend/`):
- Install: `pip install -r requirements.txt`
- Run: `uvicorn app.main:app --reload`
- Test: `pytest -v`
- Single test: `pytest tests/test_runs.py::test_create_run_requires_auth -v`

Frontend (from `frontend/`):
- Install: `npm install`
- Run: `npm run dev`
- Unit tests: `npx vitest run`
- Single unit test: `npx vitest run components/ChatPanel.test.tsx`
- E2E (needs the full stack running via `docker compose up` first): `npx playwright test`

Full stack: `docker compose up` (from repo root, after copying `.env.example` to `.env` and filling in real values).
```

- [ ] **Step 6: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e/golden-path.spec.ts frontend/package.json CLAUDE.md
git commit -m "test: golden-path E2E test and documented commands"
```
