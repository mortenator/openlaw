-- Phase 6: Map outreach_suggestions to Paperclip issues for approval workflow.
-- Adds columns to track the Paperclip issue created when a user approves an
-- outreach suggestion, enabling a review/send flow instead of a local-only
-- status flip.

ALTER TABLE outreach_suggestions
  ADD COLUMN IF NOT EXISTS paperclip_issue_id TEXT,
  ADD COLUMN IF NOT EXISTS paperclip_issue_identifier TEXT,
  ADD COLUMN IF NOT EXISTS paperclip_issue_url TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_suggestions_paperclip_issue_id
  ON outreach_suggestions (paperclip_issue_id)
  WHERE paperclip_issue_id IS NOT NULL;
