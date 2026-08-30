
create table deploy_targets (
    id         uuid primary key default gen_random_uuid(),
    name       text not null,
    registry   text not null default 'ghcr.io',
    image_repo text not null,                 -- e.g. "owner/ai-platform"
    config     jsonb not null default '{}'::jsonb,  -- env-var set for the operator; NOT production secrets
    created_by uuid not null default auth.uid() references auth.users(id),
    created_at timestamptz not null default now(),
    unique (created_by, name)
);

create table deployments (
    id         uuid primary key default gen_random_uuid(),
    target_id  uuid references deploy_targets(id) on delete set null,
    image_tag  text not null,
    git_sha    text,
    components text[] not null default '{backend,frontend}',
    status     text not null default 'running' check (status in ('running', 'succeeded', 'failed')),
    log        text not null default '',
    created_by uuid not null default auth.uid() references auth.users(id),
    created_at timestamptz not null default now()
);

create index deployments_created_by_created_at_idx on deployments (created_by, created_at desc);

alter table deploy_targets enable row level security;
alter table deployments    enable row level security;

create policy "owner can access own deploy_targets" on deploy_targets
    for all
    using      (created_by = auth.uid())
    with check (created_by = auth.uid());

create policy "owner can access own deployments" on deployments
    for all
    using      (created_by = auth.uid())
    with check (created_by = auth.uid());
