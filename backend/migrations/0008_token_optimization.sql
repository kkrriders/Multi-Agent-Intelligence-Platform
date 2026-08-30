-- Phase 3, Sub-project 1: Token Optimization
-- Per-call token/cost capture, whole-run response cache, and history-summary
-- storage. Consumed by Cost Analytics (SP2) and Production Hardening (SP3).

alter table runs add column prompt_tokens     int;
alter table runs add column completion_tokens int;
alter table runs add column cost_usd          numeric(12, 6);
alter table runs add column cache_hit         boolean not null default false;

create table run_llm_calls (
    id                uuid primary key default gen_random_uuid(),
    run_id            uuid not null references runs(id) on delete cascade,
    node              text not null,
    model             text not null,
    prompt_tokens     int not null default 0,
    completion_tokens int not null default 0,
    cost_usd          numeric(12, 6) not null default 0,
    created_at        timestamptz not null default now()
);

create index run_llm_calls_run_id_idx on run_llm_calls (run_id);

create table response_cache (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    cache_key   text not null,
    output      text not null,
    hit_count   int not null default 0,
    created_at  timestamptz not null default now(),
    last_hit_at timestamptz,
    unique (project_id, cache_key)
);

alter table conversations add column history_summary       text;
alter table conversations add column summary_through_run_id uuid;

alter table run_llm_calls  enable row level security;
alter table response_cache enable row level security;

create policy "owner can access own run_llm_calls" on run_llm_calls
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

create policy "owner can access own response_cache" on response_cache
    for all
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
