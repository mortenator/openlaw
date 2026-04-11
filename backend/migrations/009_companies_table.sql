-- Migration 009: create tracked_firms table if it is still missing after the schema rename

create table if not exists public.tracked_firms (
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

alter table public.tracked_firms enable row level security;

do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'tracked_firms'
      and policyname = 'users can manage their own tracked firms'
  ) then
    create policy "users can manage their own tracked firms"
      on public.tracked_firms for all using (auth.uid() = user_id);
  end if;
end
$$;
