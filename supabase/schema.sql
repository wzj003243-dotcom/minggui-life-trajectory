-- Reference schema. Do not expose research source data directly to public clients.
create schema if not exists research;

create table if not exists public.user_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  display_name text,
  birth_date date not null,
  birth_time time,
  birth_time_known boolean not null default false,
  birth_place_label text,
  birth_lat double precision,
  birth_lng double precision,
  created_at timestamptz not null default now()
);
alter table public.user_profiles enable row level security;
create policy "owners read profiles" on public.user_profiles for select to authenticated using ((select auth.uid()) = user_id);
create policy "owners insert profiles" on public.user_profiles for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "owners update profiles" on public.user_profiles for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update on public.user_profiles to authenticated;

create table if not exists public.prediction_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  profile_id uuid references public.user_profiles(id) on delete cascade,
  information_cutoff timestamptz not null,
  horizon_start date not null,
  horizon_end date not null,
  claim text not null,
  probability double precision not null check (probability between 0 and 1),
  validation_rule jsonb not null,
  evidence_snapshot jsonb not null,
  created_at timestamptz not null default now(),
  locked boolean not null default true
);
alter table public.prediction_ledger enable row level security;
create policy "owners read predictions" on public.prediction_ledger for select to authenticated using ((select auth.uid()) = user_id);
create policy "owners create predictions" on public.prediction_ledger for insert to authenticated with check ((select auth.uid()) = user_id);
grant select, insert on public.prediction_ledger to authenticated;

-- Source biographies, licenses, and model features belong in research schema and should be accessed server-side only.
create table if not exists research.people (
  id bigserial primary key,
  source text not null,
  source_person_id text not null,
  canonical_name text not null,
  birth_date date,
  birth_time time,
  birth_time_precision text,
  birth_place text,
  source_reliability text,
  metadata jsonb not null default '{}'::jsonb,
  unique(source, source_person_id)
);
create table if not exists research.life_events (
  id bigserial primary key,
  person_id bigint references research.people(id) on delete cascade,
  occurred_on date,
  date_precision text,
  age_years double precision,
  domain text not null,
  event_type text not null,
  description text,
  source_url text,
  confidence double precision check (confidence between 0 and 1),
  attributes jsonb not null default '{}'::jsonb
);
revoke all on schema research from anon, authenticated;
