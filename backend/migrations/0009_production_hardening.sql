-- Phase 3, Sub-project 3: Production Hardening
-- Per-project alert rules + an append-only alert_events log. Rate limiting
-- needs no table (a COUNT over the last 60s of the RLS-scoped runs table).

create table alert_rules (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    kind        text not null check (kind in ('error_rate', 'daily_spend', 'p95_latency')),
    threshold   numeric not null,          -- error_rate: 0..1 ; daily_spend: USD ; p95_latency: ms
    window_n    int not null default 20,   -- lookback run count (error_rate, p95_latency)
    webhook_url text,
    enabled     boolean not null default true,
    created_at  timestamptz not null default now(),
    unique (project_id, kind)
);

create table alert_events (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    rule_id     uuid references alert_rules(id) on delete set null,
    kind        text not null,
    observed    numeric not null,
    threshold   numeric not null,
    detail      jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index alert_events_project_id_created_at_idx on alert_events (project_id, created_at desc);

alter table alert_rules  enable row level security;
alter table alert_events enable row level security;

create policy "owner can access own alert_rules" on alert_rules
    for all
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own alert_events" on alert_events
    for all
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
