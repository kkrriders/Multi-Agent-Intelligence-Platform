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
