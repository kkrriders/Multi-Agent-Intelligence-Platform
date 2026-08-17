# Phase 1, Sub-project 1: Tool Calling + Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Register a REST tool, invoke it directly via API (no LLM/agent involved yet), and see the result â€” the same "prove the capability stands alone" discipline Phase 0 used for the whole request lifecycle. Simultaneously, establish the "Signal & Trace" visual design system and apply it across all existing pages plus this sub-project's new Tool Manager panel, so later sub-projects inherit a working design system instead of needing their own pass.

**Architecture:** A `tools` table (RLS-scoped like `projects`/`runs`) stores tool configs. A single adapter function (`rest_adapter.invoke`) executes REST-type tools with SSRF guards. Three new endpoints (create/list/invoke) sit alongside Phase 0's projects/runs routes â€” nothing here touches the LangGraph agent graph. On the frontend, design tokens move from shadcn's default light theme into a dark "Signal & Trace" palette by overwriting the existing semantic CSS variables (`--background`, `--primary`, etc.) rather than inventing a parallel token system â€” every shadcn component (`Button`, `Input`, `Card`) picks up the new look automatically. A new `SignalTrace` component (the pipeline-as-oscilloscope-trace) is shared between the landing page hero (demo/looping) and the workspace `Timeline` (real, data-driven) â€” literally the same object in both places, per the design spec's signature-element requirement. The workspace gains real tab-switching (Chat/Run vs. Tool Manager) via a new client component that owns the active-tab state.

**Tech Stack:** Same as Phase 0 (Python/FastAPI/Supabase backend, Next.js/shadcn/Tailwind v4 frontend). No new backend dependencies (uses `httpx`, already present). No new frontend dependencies (fonts via `next/font/google`, already used for the existing Geist fonts being replaced).

## Global Constraints

- Groq remains the only LLM provider; this sub-project doesn't touch the LLM/graph layer at all.
- Authorization is RLS-only â€” the new `tools` table uses the exact same owner-via-`project_id`-join policy pattern as `runs`/`run_events`. No application-level permission checks.
- Tool adapter interface is one function signature: `invoke(config: dict, input: dict) -> dict`. Only the `rest` type is implemented. Do not add SQL/Python/GitHub adapters, a class hierarchy, or a plugin registry beyond a plain `{type: function}` dict â€” a second adapter type will tell us if more structure is needed.
- Do not wire tool invocation into the LangGraph agent graph or the LLM's reasoning in any way â€” that's the Multi-Agent Orchestration sub-project, deliberately last in the sequence.
- No Qdrant, Memory, or RAG work of any kind.
- Design tokens live in one place (`frontend/app/globals.css`'s `:root` block) as CSS custom properties. Components use Tailwind utility classes that resolve to those tokens (`bg-card`, `text-phosphor`, `border-grid`, `text-muted-foreground`, etc.) â€” never a hardcoded hex value or an arbitrary-value utility like `bg-[#1B1F26]` in a `.tsx` file.
- Any animation (the `SignalTrace` pulse) must check `prefers-reduced-motion` and skip animating if set.
- No new environment variables â€” tool configs are stored in the database, not `.env`.

---

### Task 1: Tools table migration and RLS policy

**Files:**
- Create: `backend/migrations/0002_tools.sql`

**Interfaces:**
- Produces: table `tools(id, project_id, name, type, config, permissions, created_at)` with an owner-scoped RLS policy identical in shape to `runs`'.

- [x] **Step 1: Write the migration**

`backend/migrations/0002_tools.sql`:
```sql
create table tools (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    name text not null,
    type text not null,
    config jsonb not null default '{}'::jsonb,
    permissions jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

alter table tools enable row level security;

create policy "owner can access own tools" on tools
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
```

- [x] **Step 2: Apply the migration**

In the Supabase project's SQL Editor, paste and run the contents of `backend/migrations/0002_tools.sql`. This is a manual step for the human operator â€” pause here and ask if Supabase access isn't available.

- [x] **Step 3: Verify**

In the Supabase SQL Editor, run:
```sql
select relname, relrowsecurity from pg_class where relname = 'tools';
```
Expected: one row, `relrowsecurity` is `true`.

---

### Task 2: REST tool adapter with SSRF guard

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/rest_adapter.py`
- Test: `backend/tests/test_rest_adapter.py`

**Interfaces:**
- Produces: `app.tools.rest_adapter.invoke(config: dict, input: dict) -> dict` (returns `{"status": int, "body": str}`), `app.tools.rest_adapter.ToolConfigError` (raised on invalid/unsafe config).

- [x] **Step 1: Write the failing tests**

`backend/tests/test_rest_adapter.py`:
```python
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.tools.rest_adapter import ToolConfigError, invoke


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):
        pass


@pytest.fixture
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()


def test_invoke_get_returns_status_and_body(echo_server):
    result = invoke({"url": echo_server, "method": "GET"}, {})
    assert result["status"] == 200
    assert result["body"] == "ok"


def test_invoke_rejects_non_http_scheme():
    with pytest.raises(ToolConfigError):
        invoke({"url": "file:///etc/passwd", "method": "GET"}, {})


def test_invoke_rejects_private_network_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://10.1.2.3/", "method": "GET"}, {})


def test_invoke_rejects_cloud_metadata_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://169.254.169.254/", "method": "GET"}, {})


def test_invoke_rejects_private_ipv6_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://[fd00::1]/", "method": "GET"}, {})


def test_invoke_rejects_link_local_ipv6_address():
    with pytest.raises(ToolConfigError):
        invoke({"url": "http://[fe80::1]/", "method": "GET"}, {})
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_rest_adapter.py -v`
Expected: FAIL â€” `app.tools` module doesn't exist yet.

- [x] **Step 3: Write `backend/app/tools/__init__.py`** (empty file)

- [x] **Step 4: Write `backend/app/tools/rest_adapter.py`**

```python
import ipaddress
import socket
from urllib.parse import urlparse

import httpx


class ToolConfigError(Exception):
    pass


def _guard_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ToolConfigError(f"Unsupported scheme: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ToolConfigError("Missing host in URL")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ToolConfigError(f"Could not resolve host: {host}") from exc
    # ponytail: blocks the real SSRF targets (internal networks, cloud metadata
    # endpoint) but allows loopback so a tool can target a locally-run service.
    # Every resolved address is checked, not just the first: a host can carry
    # both an IPv4 A record and an IPv6 AAAA record, and the HTTP client may
    # connect via either â€” validating only gethostbyname's IPv4 result would
    # let a public A record mask a private AAAA record on the same domain.
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_loopback:
            continue
        if addr.is_private or addr.is_link_local or addr.is_reserved:
            raise ToolConfigError(f"Refusing to call private/internal address: {host}")


def invoke(config: dict, input: dict) -> dict:
    url = config["url"]
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})

    _guard_url(url)

    response = httpx.request(
        method,
        url,
        headers=headers,
        json=input if method in ("POST", "PUT", "PATCH") else None,
        params=input if method == "GET" else None,
        timeout=10.0,
    )
    return {"status": response.status_code, "body": response.text}
```

- [x] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_rest_adapter.py -v`
Expected: 6 passed. None of these tests need real network beyond the local test server and literal IP addresses (including the two IPv6 literals) â€” no external dependency, no skip needed. The guard validates every address `getaddrinfo` returns for the host (not just the first/IPv4 one), since a domain can carry both an A and an AAAA record and the HTTP client may connect via either.

- [x] **Step 6: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all prior Phase 0 tests still pass/skip as before, plus these 4 new passes.

---

### Task 3: Tools API

**Files:**
- Modify: `backend/app/models.py` (add tool models)
- Create: `backend/app/api/tools.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `app.auth.get_current_user`, `app.db.get_user_client` (Phase 0), `app.tools.rest_adapter.invoke`/`ToolConfigError` (Task 2), `auth_headers` pytest fixture (already exists in `backend/tests/conftest.py` from Phase 0 â€” do not redefine it).
- Produces: `app.models.ToolCreate {name: str, type: str, config: dict, permissions: dict = {}}`, `app.models.ToolOut {id, name, type, config, permissions, created_at}`, `app.models.ToolInvokeResult {status: int, body: str}`. Routes: `POST /projects/{project_id}/tools`, `GET /projects/{project_id}/tools`, `POST /tools/{tool_id}/invoke`.

- [x] **Step 1: Add tool models to `backend/app/models.py`**

Append to the existing file:
```python
class ToolCreate(BaseModel):
    name: str
    type: str
    config: dict
    permissions: dict = {}


class ToolOut(BaseModel):
    id: str
    name: str
    type: str
    config: dict
    permissions: dict
    created_at: datetime


class ToolInvokeResult(BaseModel):
    status: int
    body: str
```

- [x] **Step 2: Write the failing test**

`backend/tests/test_tools.py`:
```python
import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_tool_requires_auth():
    response = client.post("/projects/some-id/tools", json={"name": "Echo", "type": "rest", "config": {}})
    assert response.status_code in (401, 422)


def test_invoke_tool_requires_auth():
    response = client.post("/tools/some-id/invoke", json={})
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_create_list_and_invoke_tool(auth_headers):
    project_response = client.post("/projects", json={"name": "Tool Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/tools",
        json={"name": "Echo", "type": "rest", "config": {"url": "https://httpbin.org/get", "method": "GET"}},
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    tool = create_response.json()

    list_response = client.get(f"/projects/{project_id}/tools", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(t["id"] == tool["id"] for t in list_response.json())

    invoke_response = client.post(f"/tools/{tool['id']}/invoke", json={}, headers=auth_headers)
    assert invoke_response.status_code == 200
    assert invoke_response.json()["status"] == 200
```

- [x] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tools.py -v`
Expected: FAIL â€” `app.api.tools` module doesn't exist yet.

- [x] **Step 4: Write `backend/app/api/tools.py`**

```python
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_user_client
from app.models import ToolCreate, ToolInvokeResult, ToolOut
from app.tools.rest_adapter import ToolConfigError
from app.tools.rest_adapter import invoke as rest_invoke

router = APIRouter(tags=["tools"])

ADAPTERS = {"rest": rest_invoke}


@router.post("/projects/{project_id}/tools", response_model=ToolOut)
def create_tool(project_id: str, body: ToolCreate, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = client.table("tools").insert({
        "project_id": project_id,
        "name": body.name,
        "type": body.type,
        "config": body.config,
        "permissions": body.permissions,
    }).execute()
    return result.data[0]


@router.get("/projects/{project_id}/tools", response_model=list[ToolOut])
def list_tools(project_id: str, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    result = (
        client.table("tools")
        .select("*")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.post("/tools/{tool_id}/invoke", response_model=ToolInvokeResult)
def invoke_tool(tool_id: str, input: dict, user: dict = Depends(get_current_user)):
    client = get_user_client(user["token"])
    tool = client.table("tools").select("*").eq("id", tool_id).single().execute().data
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    adapter = ADAPTERS.get(tool["type"])
    if adapter is None:
        raise HTTPException(status_code=400, detail=f"Unsupported tool type: {tool['type']}")

    try:
        return adapter(tool["config"], input)
    except ToolConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [x] **Step 5: Mount the router in `backend/app/main.py`**

Add near the top (alongside the existing `from app.api import projects` / `from app.api import runs`):
```python
from app.api import tools
```
Add after the existing `app.include_router(runs.router)`:
```python
app.include_router(tools.router)
```

- [x] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_tools.py -v`
Expected: both auth-required tests PASS. The integration test SKIPS â€” no real Supabase project wired into this environment's shell yet; that is correct, not a failure.

- [x] **Step 7: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all prior tests still pass/skip as before, plus this task's tests.

---

### Task 4: Design tokens â€” Signal & Trace palette and type

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Produces: Tailwind utility classes `bg-background`, `text-foreground`, `bg-card`, `bg-primary`, `text-phosphor`, `bg-signal-cool`, `border-grid`, `font-heading` (Space Grotesk), `font-sans` (IBM Plex Sans, body default), `font-mono` (IBM Plex Mono) â€” all resolving to the new palette. Every existing shadcn component (`Button`, `Input`, `Card`) picks these up automatically since they already reference the semantic token names being redefined here.

**Read `frontend/app/globals.css` and `frontend/app/layout.tsx` first** â€” this task overwrites specific blocks in files that already exist from Phase 0 (Task 9's `create-next-app` + shadcn scaffold), it doesn't create new files. The exact current content is shown below for reference; if it has drifted, adapt these edits to match the real current structure rather than blindly overwriting.

- [x] **Step 1: Replace `frontend/app/layout.tsx`'s font loaders**

Current file uses `Geist`/`Geist_Mono` from `next/font/google`. Replace with:

```tsx
import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "AI Engineering Platform",
  description: "Reusable AI engineering capabilities for reliable AI applications.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
```

Keep the `metadata` export and overall `RootLayout` structure exactly as shown (the title/description were already fixed in Phase 0's final review â€” don't regress them) â€” only the font imports/variables change.

- [x] **Step 2: Rewrite `frontend/app/globals.css`'s `@theme inline` and `:root` blocks**

The file currently has `@import` lines, a `@custom-variant dark` line, an `@theme inline` block, a `:root` block, a `.dark` block, and an `@layer base` block (in that order). Keep the `@import`/`@custom-variant` lines and the `@layer base` block exactly as they are. Replace the `@theme inline` block, replace the `:root` block, and **delete the `.dark` block entirely** (it's dead code â€” no theme-toggle mechanism exists anywhere in this app, so `.dark` is never applied; keeping stale values that can never be reached just invites confusion later).

Replace `@theme inline` with:
```css
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --font-sans: var(--font-plex-sans);
  --font-mono: var(--font-plex-mono);
  --font-heading: var(--font-space-grotesk);
  --color-sidebar-ring: var(--sidebar-ring);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar: var(--sidebar);
  --color-chart-5: var(--chart-5);
  --color-chart-4: var(--chart-4);
  --color-chart-3: var(--chart-3);
  --color-chart-2: var(--chart-2);
  --color-chart-1: var(--chart-1);
  --color-ring: var(--ring);
  --color-input: var(--input);
  --color-border: var(--border);
  --color-destructive: var(--destructive);
  --color-accent-foreground: var(--accent-foreground);
  --color-accent: var(--accent);
  --color-muted-foreground: var(--muted-foreground);
  --color-muted: var(--muted);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-secondary: var(--secondary);
  --color-primary-foreground: var(--primary-foreground);
  --color-primary: var(--primary);
  --color-popover-foreground: var(--popover-foreground);
  --color-popover: var(--popover);
  --color-card-foreground: var(--card-foreground);
  --color-card: var(--card);
  --color-phosphor: var(--phosphor);
  --color-signal-cool: var(--signal-cool);
  --color-grid: var(--grid);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
  --radius-2xl: calc(var(--radius) * 1.8);
  --radius-3xl: calc(var(--radius) * 2.2);
  --radius-4xl: calc(var(--radius) * 2.6);
}
```

Replace `:root` with:
```css
:root {
  --background: #12151A;
  --foreground: #E7E9EC;
  --card: #1B1F26;
  --card-foreground: #E7E9EC;
  --popover: #1B1F26;
  --popover-foreground: #E7E9EC;
  --primary: #FFB454;
  --primary-foreground: #12151A;
  --secondary: #20242B;
  --secondary-foreground: #E7E9EC;
  --muted: #191D24;
  --muted-foreground: #8B92A0;
  --accent: #1B2530;
  --accent-foreground: #E7E9EC;
  --destructive: #FF6B6B;
  --border: #262B33;
  --input: #262B33;
  --ring: #FFB454;
  --chart-1: #FFB454;
  --chart-2: #7DD3FC;
  --chart-3: #FF6B6B;
  --chart-4: #8B92A0;
  --chart-5: #E7E9EC;
  --radius: 0.375rem;
  --sidebar: #1B1F26;
  --sidebar-foreground: #E7E9EC;
  --sidebar-primary: #FFB454;
  --sidebar-primary-foreground: #12151A;
  --sidebar-accent: #1B2530;
  --sidebar-accent-foreground: #E7E9EC;
  --sidebar-border: #262B33;
  --sidebar-ring: #FFB454;
  --phosphor: #FFB454;
  --signal-cool: #7DD3FC;
  --grid: #262B33;
}
```

- [x] **Step 3: Verify the app still builds**

Run: `cd frontend && npx next build`
Expected: clean build, all 6 routes compile (same route count as Phase 0 â€” this task only changes tokens/fonts, not routes). Visually the app is now dark-themed by default; no visual QA beyond a successful build is required for this task specifically â€” later tasks build the pages that actually showcase the new palette.

- [x] **Step 4: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all 5 existing tests still pass â€” none of them assert on colors/fonts, so this should be unaffected.

---

### Task 5: SignalTrace component

**Files:**
- Create: `frontend/components/SignalTrace.tsx`
- Test: `frontend/components/SignalTrace.test.tsx`

**Interfaces:**
- Produces: `SignalTrace({ stages: TraceStage[], loop?: boolean })`, `TraceStage = { id: string, label: string, state: 'pending' | 'active' | 'done', detail?: string }` (exported type). This is the signature element used by both Task 6 (landing hero, `loop=true`, fixed demo stages) and Task 7 (workspace `Timeline`, `loop` unset/false, real `run_events`-derived stages).

- [x] **Step 1: Write the failing test**

`frontend/components/SignalTrace.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import SignalTrace from './SignalTrace'

describe('SignalTrace', () => {
  it('renders a labeled node for every stage', () => {
    render(
      <SignalTrace
        stages={[
          { id: '1', label: 'Guardrails', state: 'done' },
          { id: '2', label: 'Agent', state: 'active' },
          { id: '3', label: 'Response', state: 'pending' },
        ]}
      />
    )
    expect(screen.getByText('Guardrails')).toBeInTheDocument()
    expect(screen.getByText('Agent')).toBeInTheDocument()
    expect(screen.getByText('Response')).toBeInTheDocument()
  })

  it('renders an optional detail line under a stage label', () => {
    render(
      <SignalTrace
        stages={[{ id: '1', label: 'run_started', state: 'active', detail: '10:00:00 AM' }]}
      />
    )
    expect(screen.getByText('10:00:00 AM')).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/SignalTrace.test.tsx`
Expected: FAIL â€” `./SignalTrace` doesn't exist yet.

- [x] **Step 3: Write `frontend/components/SignalTrace.tsx`**

```tsx
'use client'

import { useEffect, useState } from 'react'

export type TraceStage = {
  id: string
  label: string
  state: 'pending' | 'active' | 'done'
  detail?: string
}

type Props = {
  stages: TraceStage[]
  loop?: boolean
}

export default function SignalTrace({ stages, loop = false }: Props) {
  const [cycleIndex, setCycleIndex] = useState(0)

  useEffect(() => {
    if (!loop || stages.length === 0) return
    if (
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return
    }
    const interval = setInterval(() => {
      setCycleIndex((i) => (i + 1) % stages.length)
    }, 1200)
    return () => clearInterval(interval)
  }, [loop, stages.length])

  return (
    <div className="flex items-center gap-0" role="list" aria-label="Execution trace">
      {stages.map((stage, index) => {
        const isActive = loop ? index === cycleIndex : stage.state === 'active'
        const isDone = loop ? index < cycleIndex : stage.state === 'done'
        return (
          <div key={stage.id} className="flex items-center" role="listitem">
            <div className="flex flex-col items-center gap-2">
              <div
                className={`h-3 w-3 rounded-full border transition-colors duration-300 ${
                  isActive
                    ? 'bg-phosphor border-phosphor'
                    : isDone
                      ? 'bg-signal-cool border-signal-cool'
                      : 'bg-transparent border-grid'
                }`}
              />
              <span className="font-mono text-xs text-muted-foreground whitespace-nowrap">
                {stage.label}
              </span>
              {stage.detail && (
                <span className="font-mono text-[10px] text-muted-foreground whitespace-nowrap">
                  {stage.detail}
                </span>
              )}
            </div>
            {index < stages.length - 1 && (
              <div
                className={`h-px w-12 sm:w-20 transition-colors duration-300 ${
                  isDone || isActive ? 'bg-signal-cool' : 'bg-grid'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/SignalTrace.test.tsx`
Expected: PASS (2 tests).

---

### Task 6: Landing page retrofit

**Files:**
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `SignalTrace` (Task 5), `buttonVariants` from `@/components/ui/button` (already in use since Phase 0's final review fix).

- [x] **Step 1: Rewrite `frontend/app/page.tsx`**

```tsx
import Link from 'next/link'
import { buttonVariants } from '@/components/ui/button'
import SignalTrace from '@/components/SignalTrace'

const PIPELINE_STAGES = [
  { id: 'guardrails', label: 'Guardrails', state: 'pending' as const },
  { id: 'orchestrator', label: 'Orchestrator', state: 'pending' as const },
  { id: 'agent', label: 'Agent', state: 'pending' as const },
  { id: 'gateway', label: 'Gateway', state: 'pending' as const },
  { id: 'response', label: 'Response', state: 'pending' as const },
]

const READOUTS = [
  {
    label: 'ORCHESTRATION',
    reading: 'Planner, Researcher, Executor and Verifier, coordinated through one runtime.',
  },
  {
    label: 'RETRIEVAL',
    reading: 'Hybrid search, metadata filtering, citations on every response.',
  },
  {
    label: 'GUARDRAILS',
    reading: 'Prompt injection detection, PII masking, policy checks on every run.',
  },
]

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="font-heading text-4xl font-bold">AI Engineering Platform</h1>
      <p className="mt-4 text-lg text-muted-foreground">
        Reusable AI engineering capabilities for reliable AI applications.
      </p>
      <div className="mt-6 flex gap-3">
        <Link href="/signup" className={buttonVariants()}>
          Get started
        </Link>
        <Link href="/login" className={buttonVariants({ variant: 'outline' })}>
          Log in
        </Link>
      </div>

      <div className="mt-16 overflow-x-auto rounded-md border border-grid bg-card p-8">
        <SignalTrace stages={PIPELINE_STAGES} loop />
      </div>

      <div className="mt-12 grid gap-4 sm:grid-cols-3">
        {READOUTS.map((item) => (
          <div key={item.label} className="rounded-md border border-grid bg-card p-4">
            <p className="font-mono text-xs tracking-wide text-phosphor">{item.label}</p>
            <p className="mt-2 text-sm text-muted-foreground">{item.reading}</p>
          </div>
        ))}
      </div>
    </main>
  )
}
```

- [x] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: all existing tests still pass â€” no test file targets `app/page.tsx` directly.

- [x] **Step 3: Run a full build**

Run: `cd frontend && npx next build`
Expected: clean build, 6 routes.

---

### Task 7: Timeline retrofit (uses SignalTrace)

**Files:**
- Modify: `frontend/components/Timeline.tsx`

**Interfaces:**
- Consumes: `SignalTrace`, `TraceStage` (Task 5), `RunEvent` from `@/lib/api` (Phase 0).
- Produces: same `Timeline({ events: RunEvent[] })` signature as Phase 0 â€” `ChatPanel.tsx` and its test are unaffected by this task and are not modified.

**Why this replaces the plain bulleted list, not just adds to it:** Phase 0's `Timeline` rendered each event's `step_name` as its own list item. If this task's `SignalTrace`-based version also kept that list, `run_started`/`agent_responded` would each appear on the page twice (once as a trace node label, once as a list item), which breaks `ChatPanel.test.tsx`'s `screen.getByText('run_started')` (that query throws if more than one match exists) and would do the same to the golden-path E2E test's equivalent assertions. The fix is structural, not cosmetic: each event's `step_name` must render in exactly one place. Put the timestamp into `SignalTrace`'s per-stage `detail` line (Task 5 already supports this) instead of a separate list.

- [x] **Step 1: Rewrite `frontend/components/Timeline.tsx`**

```tsx
import type { RunEvent } from '@/lib/api'
import SignalTrace, { type TraceStage } from './SignalTrace'

export default function Timeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">No events yet.</p>
  }

  const stages: TraceStage[] = events.map((event, index) => ({
    id: event.id,
    label: event.step_name,
    state: index === events.length - 1 ? 'active' : 'done',
    detail: new Date(event.created_at).toLocaleTimeString(),
  }))

  return (
    <div className="overflow-x-auto rounded-md border border-grid bg-card p-4">
      <SignalTrace stages={stages} />
    </div>
  )
}
```

- [x] **Step 2: Run the full frontend test suite and confirm no regressions**

Run: `cd frontend && npx vitest run`
Expected: all tests pass, INCLUDING `ChatPanel.test.tsx`'s `expect(screen.getByText('run_started')).toBeInTheDocument()` â€” this is the specific assertion this task's design must not break. If it fails with a "multiple elements found" error, the `detail`/label split above was not applied correctly; fix `Timeline.tsx`, don't touch the test.

- [x] **Step 3: Run a full build**

Run: `cd frontend && npx next build`
Expected: clean build, 6 routes.

---

### Task 8: `lib/api.ts` â€” Tool client functions

**Files:**
- Modify: `frontend/lib/api.ts`
- Test: `frontend/lib/api.test.ts` (modify â€” add new test cases to the existing file, don't replace it)

**Interfaces:**
- Consumes: `authHeaders()`, `API_URL` (already defined in the existing file from Phase 0).
- Produces: `Tool = { id: string, name: string, type: string, config: Record<string, unknown>, permissions: Record<string, unknown>, created_at: string }`, `ToolInvokeResult = { status: number, body: string }`, `listTools(projectId: string): Promise<Tool[]>`, `createTool(projectId: string, tool: { name: string, type: string, config: Record<string, unknown> }): Promise<Tool>`, `invokeTool(toolId: string, input: Record<string, unknown>): Promise<ToolInvokeResult>`.

- [x] **Step 1: Add the failing tests to the existing `frontend/lib/api.test.ts`**

Append (inside the existing `describe('api client', ...)` block, alongside the existing `createProject` test â€” reuse the same `beforeEach`/mock setup already in the file):

```tsx
  it('listTools sends an authorized GET request', async () => {
    const { listTools } = await import('./api')
    await listTools('project-1')

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/tools'),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })

  it('createTool sends an authorized POST request with the tool payload', async () => {
    const { createTool } = await import('./api')
    await createTool('project-1', { name: 'Echo', type: 'rest', config: { url: 'https://example.com' } })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/projects/project-1/tools'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({ name: 'Echo', type: 'rest', config: { url: 'https://example.com' } }),
      })
    )
  })

  it('invokeTool sends an authorized POST request to the invoke endpoint', async () => {
    const { invokeTool } = await import('./api')
    await invokeTool('tool-1', { foo: 'bar' })

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/tools/tool-1/invoke'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        body: JSON.stringify({ foo: 'bar' }),
      })
    )
  })
```

- [x] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: FAIL â€” `listTools`/`createTool`/`invokeTool` don't exist yet.

- [x] **Step 3: Append to `frontend/lib/api.ts`**

```typescript
export type Tool = {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  permissions: Record<string, unknown>
  created_at: string
}

export type ToolInvokeResult = { status: number; body: string }

export async function listTools(projectId: string): Promise<Tool[]> {
  const res = await fetch(`${API_URL}/projects/${projectId}/tools`, { headers: await authHeaders() })
  if (!res.ok) throw new Error('Failed to list tools')
  return res.json()
}

export async function createTool(
  projectId: string,
  tool: { name: string; type: string; config: Record<string, unknown> }
): Promise<Tool> {
  const res = await fetch(`${API_URL}/projects/${projectId}/tools`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(tool),
  })
  if (!res.ok) throw new Error('Failed to create tool')
  return res.json()
}

export async function invokeTool(toolId: string, input: Record<string, unknown>): Promise<ToolInvokeResult> {
  const res = await fetch(`${API_URL}/tools/${toolId}/invoke`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error('Failed to invoke tool')
  return res.json()
}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api.test.ts`
Expected: all tests in the file pass (existing `createProject` test plus the 3 new ones).

---

### Task 9: WorkspaceNav â€” enable the Tool Manager tab

**Files:**
- Modify: `frontend/components/WorkspaceNav.tsx`
- Modify: `frontend/components/WorkspaceNav.test.tsx` (rewrite â€” the component's prop shape and interaction model change in this task)

**Interfaces:**
- Produces: `WorkspaceTab = 'chat' | 'tools'` (exported type), `WorkspaceNav({ active: WorkspaceTab, onSelect: (tab: WorkspaceTab) => void })`. This replaces Phase 0's `WorkspaceNav({ active: 'chat' })` (no callback, non-functional `href="#"` link) â€” Task 10 (`ToolManagerPanel`) and Task 11 (`ProjectWorkspace`) depend on this new signature.

**Why the test changes, not just the component:** Phase 0's test asserted `screen.getByRole('link', { name: /chat \/ run/i })` because "Chat / Run" was an `<a href="#">`. It becomes a `<button>` in this task (real click-driven tab switching needs a click handler, not a dead link), so the existing test's role query would fail against the new markup â€” this is an intentional, necessary update to match the new interaction model, not a workaround.

- [x] **Step 1: Write the failing test**

Replace `frontend/components/WorkspaceNav.test.tsx` entirely with:
```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import WorkspaceNav from './WorkspaceNav'

describe('WorkspaceNav', () => {
  it('renders Chat/Run and Tool Manager as clickable, other tabs as disabled', () => {
    const onSelect = vi.fn()
    render(<WorkspaceNav active="chat" onSelect={onSelect} />)

    expect(screen.getByRole('button', { name: /chat \/ run/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /tool manager/i })).toBeInTheDocument()
    expect(screen.getByText(/prompt manager/i).closest('[aria-disabled="true"]')).toBeTruthy()
    expect(screen.getByText(/knowledge hub/i).closest('[aria-disabled="true"]')).toBeTruthy()
  })

  it('calls onSelect with the clicked tab', () => {
    const onSelect = vi.fn()
    render(<WorkspaceNav active="chat" onSelect={onSelect} />)

    fireEvent.click(screen.getByRole('button', { name: /tool manager/i }))
    expect(onSelect).toHaveBeenCalledWith('tools')
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/WorkspaceNav.test.tsx`
Expected: FAIL â€” current component doesn't accept `onSelect` and renders a link, not buttons.

- [x] **Step 3: Rewrite `frontend/components/WorkspaceNav.tsx`**

```tsx
'use client'

const DISABLED_TABS = [
  'Prompt Manager',
  'Knowledge Hub',
  'Memory Explorer',
  'Guardrails',
  'Evaluation',
  'Observability',
  'Cost Analytics',
  'Deployment',
  'Settings',
]

export type WorkspaceTab = 'chat' | 'tools'

type Props = {
  active: WorkspaceTab
  onSelect: (tab: WorkspaceTab) => void
}

export default function WorkspaceNav({ active, onSelect }: Props) {
  return (
    <nav className="flex flex-col gap-1 w-48">
      <button
        type="button"
        onClick={() => onSelect('chat')}
        className={`text-left ${active === 'chat' ? 'font-semibold text-phosphor' : ''}`}
      >
        Chat / Run
      </button>
      <button
        type="button"
        onClick={() => onSelect('tools')}
        className={`text-left ${active === 'tools' ? 'font-semibold text-phosphor' : ''}`}
      >
        Tool Manager
      </button>
      {DISABLED_TABS.map((tab) => (
        <span key={tab} aria-disabled="true" className="text-muted-foreground cursor-not-allowed">
          {tab}
        </span>
      ))}
    </nav>
  )
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/WorkspaceNav.test.tsx`
Expected: PASS (2 tests).

---

### Task 10: ToolManagerPanel

**Files:**
- Create: `frontend/components/ToolManagerPanel.tsx`
- Test: `frontend/components/ToolManagerPanel.test.tsx`

**Interfaces:**
- Consumes: `listTools`, `createTool`, `invokeTool`, `Tool` (Task 8).
- Produces: `<ToolManagerPanel projectId={string} />`.

- [x] **Step 1: Write the failing test**

`frontend/components/ToolManagerPanel.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const listTools = vi.fn().mockResolvedValue([])
const createTool = vi.fn().mockResolvedValue({
  id: 't1',
  name: 'Echo',
  type: 'rest',
  config: {},
  permissions: {},
  created_at: '2026-01-01T00:00:00Z',
})
const invokeTool = vi.fn().mockResolvedValue({ status: 200, body: 'ok' })

vi.mock('@/lib/api', () => ({ listTools, createTool, invokeTool }))

describe('ToolManagerPanel', () => {
  it('registers a tool and shows it in the list', async () => {
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(listTools).toHaveBeenCalledWith('project-1'))

    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: 'Echo' } })
    fireEvent.change(screen.getByLabelText(/^url$/i), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /register tool/i }))

    await waitFor(() =>
      expect(createTool).toHaveBeenCalledWith('project-1', {
        name: 'Echo',
        type: 'rest',
        config: { url: 'https://example.com', method: 'GET' },
      })
    )
    await waitFor(() => expect(screen.getByText('Echo')).toBeInTheDocument())
  })

  it('tests a tool via the invoke endpoint', async () => {
    listTools.mockResolvedValueOnce([
      { id: 't1', name: 'Echo', type: 'rest', config: {}, permissions: {}, created_at: '2026-01-01T00:00:00Z' },
    ])
    const { default: ToolManagerPanel } = await import('./ToolManagerPanel')
    render(<ToolManagerPanel projectId="project-1" />)

    await waitFor(() => expect(screen.getByText('Echo')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /test/i }))

    await waitFor(() => expect(invokeTool).toHaveBeenCalledWith('t1', {}))
    await waitFor(() => expect(screen.getByText('200')).toBeInTheDocument())
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ToolManagerPanel.test.tsx`
Expected: FAIL â€” `./ToolManagerPanel` doesn't exist yet.

- [x] **Step 3: Write `frontend/components/ToolManagerPanel.tsx`**

```tsx
'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createTool, invokeTool, listTools, type Tool } from '@/lib/api'

export default function ToolManagerPanel({ projectId }: { projectId: string }) {
  const [tools, setTools] = useState<Tool[]>([])
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, string>>({})

  useEffect(() => {
    listTools(projectId)
      .then(setTools)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load tools'))
  }, [projectId])

  async function handleRegister() {
    if (!name.trim() || !url.trim()) return
    setError(null)
    try {
      const tool = await createTool(projectId, { name, type: 'rest', config: { url, method: 'GET' } })
      setTools((prev) => [tool, ...prev])
      setName('')
      setUrl('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to register tool')
    }
  }

  async function handleTest(tool: Tool) {
    try {
      const result = await invokeTool(tool.id, {})
      setResults((prev) => ({ ...prev, [tool.id]: `${result.status}` }))
    } catch {
      setResults((prev) => ({ ...prev, [tool.id]: 'error' }))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <ul className="flex flex-col gap-2">
        {tools.map((tool) => (
          <li
            key={tool.id}
            className="flex items-center justify-between gap-4 rounded-md border border-grid bg-card p-3"
          >
            <div>
              <p className="font-mono text-sm">{tool.name}</p>
              <p className="text-xs text-muted-foreground">{tool.type}</p>
            </div>
            <div className="flex items-center gap-3">
              {results[tool.id] && (
                <span className="font-mono text-xs text-muted-foreground">{results[tool.id]}</span>
              )}
              <Button variant="outline" size="sm" onClick={() => handleTest(tool)}>
                Test
              </Button>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-col gap-2 rounded-md border border-grid bg-card p-4">
        <label htmlFor="tool-name" className="text-sm font-medium">
          Name
        </label>
        <Input id="tool-name" value={name} onChange={(e) => setName(e.target.value)} />
        <label htmlFor="tool-url" className="text-sm font-medium">
          URL
        </label>
        <Input id="tool-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." />
        <Button className="mt-2 self-start" onClick={handleRegister}>
          Register tool
        </Button>
      </div>
    </div>
  )
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ToolManagerPanel.test.tsx`
Expected: PASS (2 tests).

---

### Task 11: ProjectWorkspace composition and page restructure

**Files:**
- Create: `frontend/components/ProjectWorkspace.tsx`
- Test: `frontend/components/ProjectWorkspace.test.tsx`
- Modify: `frontend/app/projects/[id]/page.tsx`

**Interfaces:**
- Consumes: `WorkspaceNav`, `WorkspaceTab` (Task 9), `ChatPanel` (Phase 0, unmodified), `ToolManagerPanel` (Task 10).
- Produces: `<ProjectWorkspace projectId={string} />` â€” owns which tab is active; the page component becomes a thin async wrapper that just resolves `params` and renders this.

- [x] **Step 1: Write the failing test**

`frontend/components/ProjectWorkspace.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('./ChatPanel', () => ({ default: () => <div>chat-panel</div> }))
vi.mock('./ToolManagerPanel', () => ({ default: () => <div>tool-panel</div> }))

describe('ProjectWorkspace', () => {
  it('switches between Chat/Run and Tool Manager panels', async () => {
    const { default: ProjectWorkspace } = await import('./ProjectWorkspace')
    render(<ProjectWorkspace projectId="p1" />)

    expect(screen.getByText('chat-panel')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /tool manager/i }))
    expect(screen.getByText('tool-panel')).toBeInTheDocument()
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run components/ProjectWorkspace.test.tsx`
Expected: FAIL â€” `./ProjectWorkspace` doesn't exist yet.

- [x] **Step 3: Write `frontend/components/ProjectWorkspace.tsx`**

```tsx
'use client'

import { useState } from 'react'
import WorkspaceNav, { type WorkspaceTab } from './WorkspaceNav'
import ChatPanel from './ChatPanel'
import ToolManagerPanel from './ToolManagerPanel'

export default function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<WorkspaceTab>('chat')

  return (
    <div className="flex gap-8">
      <WorkspaceNav active={tab} onSelect={setTab} />
      <div className="flex-1">
        {tab === 'chat' && (
          <>
            <h1 className="font-heading text-2xl font-bold mb-6">Chat / Run</h1>
            <ChatPanel projectId={projectId} />
          </>
        )}
        {tab === 'tools' && (
          <>
            <h1 className="font-heading text-2xl font-bold mb-6">Tool Manager</h1>
            <ToolManagerPanel projectId={projectId} />
          </>
        )}
      </div>
    </div>
  )
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run components/ProjectWorkspace.test.tsx`
Expected: PASS.

- [x] **Step 5: Rewrite `frontend/app/projects/[id]/page.tsx`**

Read the current file first â€” it awaits `params` as a `Promise<{ id: string }>` (Next.js 16 convention, established in Phase 0 Task 12). Preserve that pattern:

```tsx
import ProjectWorkspace from '@/components/ProjectWorkspace'

export default async function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <ProjectWorkspace projectId={id} />
    </main>
  )
}
```

- [x] **Step 6: Run the full frontend suite and a full build**

Run: `cd frontend && npx vitest run`
Expected: all tests pass (existing 5 from Phase 0's final state, plus this sub-project's new ones).

Run: `cd frontend && npx next build`
Expected: clean build, 6 routes, no type errors.

---

### Task 12: E2E test â€” register and invoke a tool

**Files:**
- Create: `frontend/e2e/tool-calling.spec.ts`

**Interfaces:**
- Consumes: the full running stack (`docker compose up`), a real Supabase project with Task 1's migration applied, and email-confirmation-free signup (same live-stack requirements as Phase 0's `golden-path.spec.ts`).

**Same caveat as Phase 0's E2E task: this cannot be run to a green result without the live stack + real credentials. Write and verify selectors carefully; do not attempt to fake a live run.**

- [x] **Step 1: Write the test**

`frontend/e2e/tool-calling.spec.ts`:
```typescript
import { test, expect } from '@playwright/test'

test('register a tool, invoke it, and see the result', async ({ page }) => {
  const email = `test-tools-${Date.now()}@example.com`

  await page.goto('/signup')
  await page.getByLabel(/email/i).fill(email)
  await page.getByLabel(/password/i).fill('hunter2-hunter2')
  await page.getByRole('button', { name: /sign up/i }).click()

  await page.waitForURL('**/dashboard')

  await page.getByLabel(/new project name/i).fill('Tool Test Project')
  await page.getByRole('button', { name: /create/i }).click()
  await page.getByRole('link', { name: /tool test project/i }).click()

  await page.getByRole('button', { name: /tool manager/i }).click()

  await page.getByLabel(/^name$/i).fill('Public Echo')
  await page.getByLabel(/^url$/i).fill('https://httpbin.org/get')
  await page.getByRole('button', { name: /register tool/i }).click()

  await expect(page.getByText('Public Echo')).toBeVisible()

  await page.getByRole('button', { name: /test/i }).click()
  await expect(page.getByText('200')).toBeVisible({ timeout: 15000 })
})
```

- [x] **Step 2: Verify without a live server**

Run: `cd frontend && npx playwright test --list`
Expected: both `golden-path.spec.ts` and `tool-calling.spec.ts` are discovered (2 tests total).

Cross-check every selector in the new test against the real component source from this plan (`ToolManagerPanel.tsx`'s "Name"/"URL" labels and "Register tool"/"Test" button text, `WorkspaceNav.tsx`'s "Tool Manager" button, `ProjectList.tsx`'s project-name link pattern reused from Phase 0). Report any mismatch precisely rather than fixing it by changing an earlier task's file.
