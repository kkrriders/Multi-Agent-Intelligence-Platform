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
