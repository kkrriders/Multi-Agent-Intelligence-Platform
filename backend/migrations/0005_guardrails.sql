create table guardrail_policies (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    kind        text not null check (kind in ('input_constraint', 'output_constraint')),
    enabled     boolean not null default true,
    config      jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    unique (project_id, kind)
);

create table guardrail_events (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid not null references runs(id) on delete cascade,
    project_id  uuid not null references projects(id) on delete cascade,
    phase       text not null check (phase in ('pre', 'post')),
    kind        text not null,
    outcome     text not null check (outcome in ('pass', 'blocked', 'masked', 'warned')),
    detail      jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

alter table guardrail_policies enable row level security;
alter table guardrail_events   enable row level security;

create policy "owner can access own guardrail_policies" on guardrail_policies
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own guardrail_events" on guardrail_events
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));
