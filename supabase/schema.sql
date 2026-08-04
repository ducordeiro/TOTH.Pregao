-- TOTH Propostas: schema idempotente para Supabase/PostgreSQL.
-- Execute no SQL Editor de um projeto Supabase novo ou homologado.
create extension if not exists pgcrypto;

create table if not exists public.kanban_columns (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (length(name) between 1 and 80), position integer not null check (position > 0),
  color text not null default '#E8F1FB', created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(user_id,name), unique(user_id,position));
create table if not exists public.proposals (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  column_id uuid not null references public.kanban_columns(id) on delete restrict, portal text not null,
  position_number integer check(position_number is null or position_number > 0),
  modality text not null default '', agency_name text not null default '', notice_number text not null default '',
  uasg text not null default '', pncp_control_number text not null default '', opening_date date, opening_time time,
  critical_deadline timestamptz, internal_identifier text not null default '', title text not null,
  object_description text not null default '', phase_status text not null default '',
  priority text not null default 'normal' check(priority in ('critica','alta','normal','baixa')),
  pending_documents text not null default '', estimated_value numeric(18,2), responsible text not null default '',
  next_review_at timestamptz, notes text not null default '', source_link text not null default '',
  source_last_checked_at timestamptz, source_last_updated_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(user_id,portal,title,notice_number,uasg));
create table if not exists public.proposal_stage_history (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  proposal_id uuid not null references public.proposals(id) on delete cascade,
  from_column_id uuid references public.kanban_columns(id) on delete set null,
  to_column_id uuid not null references public.kanban_columns(id) on delete restrict, moved_at timestamptz not null default now());
create table if not exists public.proposal_reviews (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,proposal_id uuid not null references public.proposals(id) on delete cascade,reviewed_at timestamptz not null default now(),notes text not null default '');
create table if not exists public.proposal_documents (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,proposal_id uuid not null references public.proposals(id) on delete cascade,name text not null,status text not null default 'pendente',created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table if not exists public.proposal_links (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,proposal_id uuid not null references public.proposals(id) on delete cascade,label text not null,url text not null check(url ~ '^https?://'),created_at timestamptz not null default now());
create table if not exists public.agenda_records (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,proposal_id uuid references public.proposals(id) on delete set null,title text not null,due_at timestamptz,status text not null default 'pendente',created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table if not exists public.readings (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,proposal_id uuid references public.proposals(id) on delete cascade,source text not null,payload jsonb not null default '{}'::jsonb,read_at timestamptz not null default now());
create table if not exists public.sync_log (id uuid primary key default gen_random_uuid(),user_id uuid not null references auth.users(id) on delete cascade,direction text not null,action text not null,status text not null,summary jsonb not null default '{}'::jsonb,created_at timestamptz not null default now());

do $$ declare t text; begin
  foreach t in array array['kanban_columns','proposals','proposal_stage_history','proposal_reviews','proposal_documents','proposal_links','agenda_records','readings','sync_log'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('drop policy if exists user_owns_rows on public.%I',t);
    execute format('create policy user_owns_rows on public.%I for all using (auth.uid() = user_id) with check (auth.uid() = user_id)',t);
  end loop;
end $$;

create or replace function public.seed_default_kanban_columns() returns void language plpgsql security invoker as $$
declare names text[] := array['BLL','BNC','ComprasBR','Licitações-e','Licitanet','Licita PP','Licitar Digital','NovoBBMNet','Portal de Compras Públicas','Portal de Compras RS','SISLOG']; n text; i integer:=0;
begin foreach n in array names loop i:=i+1; insert into public.kanban_columns(user_id,name,position) values(auth.uid(),n,i) on conflict(user_id,name) do nothing; end loop; end $$;

