-- OpenLaw: Seed Data — Brian Hamilton (Customer #0)
-- Migration: 002_seed_brian.sql
--
-- Run AFTER 001_initial_schema.sql
-- Brian's real email and firm name will be filled in during onboarding.

INSERT INTO users (
    name,
    email,
    firm,
    practice_area,
    comms_channel,
    timezone
) VALUES (
    'Brian Hamilton',
    'brian@placeholder.com',      -- TODO: replace with real email at onboarding
    'TBD',                         -- TODO: replace with firm name at onboarding
    ARRAY['M&A', 'tech transactions', 'AI infrastructure'],
    'email',
    'America/New_York'
)
ON CONFLICT (email) DO NOTHING;

-- Insert default agent config for Brian
INSERT INTO agent_configs (user_id, scan_frequency, outreach_tone, max_weekly_outreach, focus_keywords)
SELECT
    id,
    'weekly',
    'professional',
    5,
    ARRAY['M&A', 'AI infrastructure', 'tech transactions', 'venture capital', 'private equity']
FROM users
WHERE email = 'brian@placeholder.com'
ON CONFLICT DO NOTHING;

-- NOTE: Run contact CSV import separately after onboarding call with Brian.
-- Use the POST /users/{id}/contacts endpoint or a bulk import script.
