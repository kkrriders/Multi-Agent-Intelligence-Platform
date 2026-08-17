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
