-- Migration 009: create companies table (was missing from initial deployment)
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/nyrzxkxfbrpxygvuywlr/sql/new

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade not null,
  name text not null,
  industry text,
  size text,
  is_watchlist boolean default false,
  tags text[] default '{}',
  last_news_fetched_at timestamptz,
  created_at timestamptz default now(),
  unique (user_id, name)
);

alter table public.companies enable row level security;

create policy "users can manage their own companies"
  on public.companies for all using (auth.uid() = user_id);

-- Backfill watchlist companies from tracked_firms (Phase 5 onboarding data)
insert into public.companies (id, user_id, name, is_watchlist, created_at)
select id, user_id, name, true, created_at
from public.tracked_firms
on conflict (user_id, name) do nothing;
