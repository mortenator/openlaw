-- Migration 010: Create agent_memory_logs table + user_crons unique constraint
-- Stores per-user agent configuration files (SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md, AGENTS.md)
-- Generated during onboarding and updatable by the user from the Agent Config page.

create table if not exists public.agent_memory_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.users(id) on delete cascade not null,
  memory_key text not null,
  memory_val jsonb not null default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique (user_id, memory_key)
);

create index if not exists idx_agent_memory_logs_user_id
  on public.agent_memory_logs(user_id);

-- Enable RLS
alter table public.agent_memory_logs enable row level security;

create policy "users can manage their own memory logs"
  on public.agent_memory_logs for all
  using (auth.uid() = user_id);

-- Auto-update updated_at on row changes
do $$
begin
  if exists (select 1 from pg_proc where proname = 'update_updated_at_column') then
    create trigger trg_agent_memory_logs_updated_at
      before update on public.agent_memory_logs
      for each row execute function update_updated_at_column();
  end if;
end;
$$;


-- Add unique constraint on user_crons (user_id, job_type) so that
-- _provision_default_crons can upsert idempotently on retry.
-- Wrapped in a DO block because ADD CONSTRAINT IF NOT EXISTS is not valid
-- SQL syntax in PostgreSQL — the existence check must be done manually.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'user_crons_user_id_job_type_key'
      and conrelid = 'public.user_crons'::regclass
  ) then
    alter table public.user_crons
      add constraint user_crons_user_id_job_type_key unique (user_id, job_type);
  end if;
end;
$$;
