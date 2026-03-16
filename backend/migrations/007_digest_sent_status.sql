-- Migration: 007_digest_sent_status.sql
-- Add 'digest_sent' as a valid status for outreach_suggestions
-- Required for weekly digest to mark suggestions after sending

ALTER TABLE outreach_suggestions
  DROP CONSTRAINT IF EXISTS outreach_suggestions_status_check;

ALTER TABLE outreach_suggestions
  ADD CONSTRAINT outreach_suggestions_status_check
  CHECK (status IN ('pending', 'approved', 'sent', 'dismissed', 'digest_sent'));
