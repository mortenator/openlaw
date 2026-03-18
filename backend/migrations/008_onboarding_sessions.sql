-- Migration 008: Add is_complete boolean to onboarding_sessions
-- The completed_at column exists from migration 004; is_complete provides
-- a simpler boolean check for the step-based onboarding flow.

alter table onboarding_sessions
  add column if not exists is_complete boolean default false;

-- Backfill: any session that already has completed_at should be marked complete
update onboarding_sessions
  set is_complete = true
  where completed_at is not null and is_complete = false;
