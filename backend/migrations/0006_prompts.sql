create table prompt_templates (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    name        text not null,
    created_at  timestamptz not null default now(),
    unique (project_id, name)
);

create table prompt_template_versions (
    id          uuid primary key default gen_random_uuid(),
    template_id uuid not null references prompt_templates(id) on delete cascade,
    version     int not null,
    body        text not null,
    created_at  timestamptz not null default now(),
    unique (template_id, version)
);

alter table prompt_templates          enable row level security;
alter table prompt_template_versions  enable row level security;

create policy "owner can access own prompt_templates" on prompt_templates
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own prompt_template_versions" on prompt_template_versions
    using      (template_id in (select id from prompt_templates
                                where project_id in (select id from projects where owner_id = auth.uid())))
    with check (template_id in (select id from prompt_templates
                                where project_id in (select id from projects where owner_id = auth.uid())));
