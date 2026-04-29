-- Supabase/PostgreSQL schema for KAS app
-- Run in Supabase SQL Editor

create table if not exists public.users (
    id bigserial primary key,
    name text not null,
    email text not null unique,
    password text not null,
    role text not null check (role in ('admin', 'employee', 'client')),
    created_at text not null
);

create table if not exists public.workers (
    id bigserial primary key,
    username text not null unique,
    password_hash text not null,
    created_at text not null
);

create table if not exists public.jobs (
    id bigserial primary key,
    name text not null,
    location text not null,
    due_date text,
    service_type text,
    other_service_details text,
    description text not null,
    status text not null default 'Lead',
    client_name text,
    proposal_amount double precision,
    proposal_sent_date text,
    decision_date text,
    rejection_reason text,
    invoice_amount double precision,
    payment_status text not null default 'Not Paid',
    assigned_to bigint references public.users(id) on delete set null,
    client_id bigint references public.users(id) on delete set null,
    created_at text not null
);

create table if not exists public.updates (
    id bigserial primary key,
    job_id bigint not null references public.jobs(id) on delete cascade,
    notes text,
    image_path text,
    receipt_path text,
    client_visible boolean not null default false,
    update_group text,
    user_id bigint references public.users(id) on delete set null,
    author_role text,
    timestamp text not null
);

create table if not exists public.job_tasks (
    id bigserial primary key,
    job_id bigint not null references public.jobs(id) on delete cascade,
    service_type text,
    title text not null,
    status text not null default 'Not Started',
    sort_order integer default 0,
    created_at text not null,
    updated_at text
);

create index if not exists idx_jobs_assigned_to on public.jobs(assigned_to);
create index if not exists idx_jobs_client_id on public.jobs(client_id);
create index if not exists idx_jobs_status on public.jobs(status);
create index if not exists idx_updates_job_id on public.updates(job_id);
create index if not exists idx_updates_timestamp on public.updates(timestamp desc);
create index if not exists idx_job_tasks_job_id on public.job_tasks(job_id);
