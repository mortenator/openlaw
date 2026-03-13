create table if not exists onboarding_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade unique,
  step int default 0,
  answers jsonb default '{}',
  completed_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists onboarding_sessions_user_id_idx on onboarding_sessions(user_id);

alter table users add column if not exists first_name text;
alter table users add column if not exists last_name text;
alter table users add column if not exists role text;
alter table users add column if not exists deal_types text[] default '{}';
alter table users add column if not exists geography text;
alter table users add column if not exists client_types text;
alter table users add column if not exists delivery_email text;
alter table users add column if not exists delivery_schedule text default 'morning';
alter table users add column if not exists watchlist_companies text[] default '{}';
alter table users add column if not exists tracking_gap text;
alter table users add column if not exists relationship_flag text;
alter table users add column if not exists onboarding_complete boolean default false;
alter table users add column if not exists practice_area text[] default '{}';
