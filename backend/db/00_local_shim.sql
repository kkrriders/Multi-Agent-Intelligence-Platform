-- Stand-ins for the Supabase objects migrations 0001-0010 reference.
create schema if not exists auth;

create table auth.users (
    id            uuid primary key default gen_random_uuid(),
    email         text not null unique,
    password_hash text not null,
    created_at    timestamptz not null default now()
);

-- Same contract as Supabase's auth.uid(): the calling user's id, or null.
create function auth.uid() returns uuid
    language sql stable
    as $$ select nullif(current_setting('app.user_id', true), '')::uuid $$;

create schema if not exists storage;

create table storage.buckets (
    id     text primary key,
    name   text not null,
    public boolean not null default false
);

-- Policy target only: file bytes live on disk (app/storage.py), not in this table.
create table storage.objects (
    bucket_id text not null,
    name      text not null
);
alter table storage.objects enable row level security;

create function storage.foldername(name text) returns text[]
    language sql immutable
    as $$ select (string_to_array(name, '/'))[1:cardinality(string_to_array(name, '/')) - 1] $$;
