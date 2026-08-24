create table documents (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    filename text not null,
    mime_type text not null,
    storage_path text not null,
    status text not null default 'pending',
    error text,
    created_at timestamptz not null default now()
);

create table document_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    project_id uuid not null references projects(id) on delete cascade,
    chunk_index int not null,
    content text not null,
    content_tsv tsvector generated always as (to_tsvector('english', content)) stored,
    created_at timestamptz not null default now()
);

create index document_chunks_tsv_idx on document_chunks using gin (content_tsv);

alter table documents enable row level security;
alter table document_chunks enable row level security;


create policy "owner can access own documents" on documents
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

create policy "owner can access own document chunks" on document_chunks
    for all
    using (project_id in (select id from projects where owner_id = auth.uid()))
    with check (project_id in (select id from projects where owner_id = auth.uid()));

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do nothing;

create policy "owner can access own document files" on storage.objects
    for all
    using (
        bucket_id = 'documents'
        and (storage.foldername(name))[1]::uuid in (select id from projects where owner_id = auth.uid())
    )
    with check (
        bucket_id = 'documents'
        and (storage.foldername(name))[1]::uuid in (select id from projects where owner_id = auth.uid())
    );
