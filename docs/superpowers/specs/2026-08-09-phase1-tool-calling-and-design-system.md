# Phase 1, Sub-project 1: Tool Calling + Frontend Design System

**Date:** 2026-08-09
**Status:** Approved for planning
**Builds on:** `2026-08-09-ai-engineering-platform-design.md` (master spec), Phase 0 (walking skeleton, complete)

## Scope

First Phase 1 sub-project, per the master spec's sequencing decision: **Tool Calling → Memory → RAG → Multi-Agent Orchestration**, dependency-first. This sub-project also establishes the frontend's visual design system (previously bare shadcn defaults) and applies it both to this sub-project's new UI and as a retrofit of Phase 0's existing pages, so no second design pass is needed later — later sub-projects just use the system already in place.

**Explicitly not in this sub-project:** SQL/Python/GitHub tool adapters (same interface, added later, one file each), wiring tool calls into the agent's reasoning loop (that's the Multi-Agent Orchestration sub-project — Groq's native tool-calling gets threaded in there, once there's a real multi-step agent to use it). This sub-project proves the Tool Calling capability stands on its own: register a tool, invoke it directly via API, see the result — the same "walking skeleton per capability" discipline Phase 0 used for the whole request lifecycle.

Qdrant is not added in this sub-project either — nothing here needs it. It arrives in the Memory sub-project (self-hosted via Docker, per user decision; Qdrant Cloud as the fallback if Docker hosting becomes a problem).

## Backend: Tool Calling

**Data model** (new Supabase migration, RLS-scoped like `projects`/`runs`):

```sql
create table tools (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    name text not null,
    type text not null,              -- 'rest' for now; 'sql'/'python'/'github' later, same column
    config jsonb not null default '{}'::jsonb,       -- adapter-specific: base_url, method, headers, auth
    permissions jsonb not null default '{}'::jsonb,  -- e.g. {"allow_write": false} — scope restriction, not user auth
    created_at timestamptz not null default now()
);
```
RLS: owner-only access via the same `project_id → projects.owner_id = auth.uid()` pattern Phase 0 established for `runs`/`run_events`. No new permission mechanism — this table just adds one more thing scoped by the existing pattern.

**Tool adapter interface** — one Python function type, not a class hierarchy (YAGNI: a second adapter type will tell us if we need more structure than a function signature):
```python
def invoke(config: dict, input: dict) -> dict: ...
```
`type` on the `tools` row selects which adapter function runs. This sub-project implements exactly one: `rest_adapter.invoke` — makes an HTTP request using `config` (method, url, headers) and `input` (body/params), returns `{status, body}`. No SQL/Python/GitHub adapters yet; adding one later is "write one more function matching this signature and register it," not a redesign.

**API:**
- `POST /projects/{project_id}/tools` — register a tool (name, type, config, permissions)
- `GET /projects/{project_id}/tools` — list a project's tools
- `POST /tools/{tool_id}/invoke` — call the tool directly with a JSON `input` body, returns the adapter's result. This is the "prove it works standalone" endpoint — no LLM/graph involved.

**Security note carried forward from Phase 0's auth review:** the REST adapter executes an outbound HTTP call using data one project's owner controls (their own tool config) — this is not a new trust boundary beyond what RLS already scopes (a user can only invoke tools on projects they own), but the adapter itself must not blindly follow redirects to internal/private network addresses (basic SSRF hygiene: reject non-http(s) schemes, don't allow the config to target `localhost`/private IP ranges). This is small and goes in the same task as the adapter, not deferred — unlike SQL/Python (which are deferred as whole adapters), this is a correctness requirement of the one adapter we ARE building now.

## Frontend: Design System ("Signal & Trace")

**Tokens** (as CSS custom properties / Tailwind theme extension, not hardcoded classNames scattered through components):

| Token | Value | Use |
|---|---|---|
| `--ink` | `#12151A` | page background |
| `--panel` | `#1B1F26` | card/surface background |
| `--grid` | `#262B33` | hairlines, borders, scope-graticule lines |
| `--phosphor` | `#FFB454` | primary accent — active signal, primary actions, focus rings |
| `--signal-cool` | `#7DD3FC` | idle/secondary state, links |
| `--alert` | `#FF6B6B` | guardrail violations, errors, destructive actions |
| `--foreground` | `#E7E9EC` | primary text |
| `--muted` | `#8B92A0` | secondary text |

**Type:** Space Grotesk (display, headlines only), IBM Plex Sans (body), IBM Plex Mono (data: trace IDs, timestamps, step names, token counts — functional, not decorative, since this product's own UI surfaces literal machine data).

**Signature element:** the request lifecycle rendered as an animated horizontal signal trace — nodes for each pipeline stage connected by a line, a pulse travels along it, each node lights `--phosphor` as it activates. This is literally the master spec's own architecture diagram, made real. It appears twice, as the *same component* in two contexts:
1. Landing page hero (static/looping demo version, illustrating the product)
2. Workspace `Timeline` component (real version, driven by actual `run_events` — replaces Phase 0's plain bulleted list with a proper trace/waveform-styled log using the mono type and phosphor/cool-signal coloring per event type)

**Retrofit scope (Phase 0 pages, minimal targeted changes, not a rewrite):**
- Landing (`app/page.tsx`): new hero with the signal-trace component; feature cards restyled as instrument-readout panels (mono label + reading) instead of generic icon-title-text cards
- Login/signup (`AuthForm.tsx` + pages): inherit new tokens via the shared shadcn `Button`/`Input` theme — no structural changes needed, colors/type flow through automatically once the Tailwind theme + `globals.css` tokens are updated
- Dashboard/workspace: inherit tokens the same way; `Timeline.tsx` gets the trace-log restyle described above
- `WorkspaceNav.tsx`: "Tool Manager" becomes the second enabled tab (alongside "Chat / Run") — the rest stay disabled

**New: Tool Manager panel**, as a tab within the existing project workspace (`app/projects/[id]/page.tsx`), matching the master spec's Frontend IA where Tool Manager is one of the Project Workspace's tabs, not a standalone route — same pattern as Chat/Run. Content: list of a project's tools (name, type, permissions, last invoke result), a form to register a new tool, and a "test" action that calls the invoke endpoint and shows status/latency inline — matching the master spec's "connected tools, permissions, health and latency" description.

## Testing

Same discipline as Phase 0: real Supabase/RLS for integration tests (skip without credentials, don't mock), unit tests for the REST adapter's request-building logic (pure function, no network needed) plus one credential-gated integration test hitting a real HTTP endpoint (e.g., a public httpbin-style echo endpoint) to prove the adapter actually works end to end. Frontend: Vitest component tests for the new Tool Manager UI and the restyled `Timeline`, Playwright extension to the existing golden-path test (or a new short E2E test) covering "register a tool, invoke it, see the result."

## Non-goals (explicit, so scope doesn't creep mid-build)

- No SQL/Python/GitHub adapters
- No tool invocation from within the agent graph/LLM reasoning
- No Qdrant, Memory, or RAG work
- No design changes beyond what's listed above — this is a system + retrofit, not a full redesign of every page's layout
