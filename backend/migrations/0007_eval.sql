create table eval_datasets (
    id          uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects(id) on delete cascade,
    name        text not null,
    created_at  timestamptz not null default now(),
    unique (project_id, name)
);

create table eval_items (
    id          uuid primary key default gen_random_uuid(),
    dataset_id  uuid not null references eval_datasets(id) on delete cascade,
    input       text not null,
    expected    text not null,
    created_at  timestamptz not null default now()
);

create table eval_runs (
    id                 uuid primary key default gen_random_uuid(),
    dataset_id         uuid not null references eval_datasets(id) on delete cascade,
    item_count         int not null,
    accuracy           double precision not null,
    hallucination_rate double precision not null,
    mean_score         double precision not null,
    created_at         timestamptz not null default now()
);

create table eval_results (
    id           uuid primary key default gen_random_uuid(),
    eval_run_id  uuid not null references eval_runs(id) on delete cascade,
    item_id      uuid not null references eval_items(id) on delete cascade,
    output       text not null,
    score        double precision not null,
    hallucinated boolean not null,
    reason       text not null default ''
);

alter table eval_datasets enable row level security;
alter table eval_items    enable row level security;
alter table eval_runs     enable row level security;
alter table eval_results  enable row level security;

create policy "owner can access own eval_datasets" on eval_datasets
    using      (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own eval_items" on eval_items
    using      (dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid())))
    with check (dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid())));

create policy "owner can access own eval_runs" on eval_runs
    using      (dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid())))
    with check (dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid())));

create policy "owner can access own eval_results" on eval_results
    using      (eval_run_id in (select id from eval_runs where dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid()))))
    with check (eval_run_id in (select id from eval_runs where dataset_id in (select id from eval_datasets
                               where project_id in (select id from projects where owner_id = auth.uid()))));
