-- Migration: 006_trigger_summary.sql
-- Adds trigger_summary column to outreach_suggestions for human-readable surfacing reason

ALTER TABLE outreach_suggestions ADD COLUMN IF NOT EXISTS trigger_summary TEXT;
