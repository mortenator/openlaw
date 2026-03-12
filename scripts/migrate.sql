-- OpenLaw complete schema migration
-- Run this against your Supabase project SQL editor

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── profiles ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  name        TEXT,
  firm        TEXT,
  practice_area TEXT[],
  comms_channel TEXT DEFAULT 'email',
  timezone    TEXT DEFAULT 'UTC',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── agent_configs ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.agent_configs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  file_name   TEXT NOT NULL,
  content     TEXT NOT NULL DEFAULT '',
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, file_name)
);

-- ── companies ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.companies (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  industry     TEXT,
  tags         TEXT[] DEFAULT '{}',
  is_watchlist BOOLEAN DEFAULT FALSE,
  domain       TEXT,
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── contacts ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.contacts (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id        UUID REFERENCES public.companies(id) ON DELETE SET NULL,
  name              TEXT NOT NULL,
  role              TEXT,
  email             TEXT,
  phone             TEXT,
  tier              INT NOT NULL DEFAULT 2 CHECK (tier IN (1, 2, 3)),
  last_contacted_at TIMESTAMPTZ,
  health_score      REAL DEFAULT 0 CHECK (health_score >= 0 AND health_score <= 100),
  notes             TEXT,
  tags              TEXT[] DEFAULT '{}',
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── signals ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.signals (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  company_id  UUID REFERENCES public.companies(id) ON DELETE CASCADE,
  type        TEXT NOT NULL DEFAULT 'general_news',
  headline    TEXT NOT NULL,
  source_url  TEXT,
  summary     TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── outreach_suggestions ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.outreach_suggestions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  contact_id    UUID NOT NULL REFERENCES public.contacts(id) ON DELETE CASCADE,
  signal_id     UUID REFERENCES public.signals(id) ON DELETE SET NULL,
  subject       TEXT,
  draft_message TEXT,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'dismissed', 'sent')),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── user_crons ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.user_crons (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  schedule    TEXT NOT NULL,
  job_type    TEXT NOT NULL,
  is_enabled  BOOLEAN DEFAULT TRUE,
  last_run_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── deliveries ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.deliveries (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  type         TEXT NOT NULL,
  subject      TEXT,
  content_html TEXT,
  status       TEXT NOT NULL DEFAULT 'sent',
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Row Level Security ───────────────────────────────────────────────────────

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.profiles
  FOR ALL USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

ALTER TABLE public.agent_configs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.agent_configs
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.companies
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.contacts
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.signals
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.outreach_suggestions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.outreach_suggestions
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.user_crons ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.user_crons
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

ALTER TABLE public.deliveries ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON public.deliveries
  FOR ALL USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_contacts_user_health ON public.contacts(user_id, health_score);
CREATE INDEX IF NOT EXISTS idx_contacts_user_tier ON public.contacts(user_id, tier);
CREATE INDEX IF NOT EXISTS idx_signals_user_created ON public.signals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_suggestions_user_status ON public.outreach_suggestions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_companies_user_watchlist ON public.companies(user_id, is_watchlist);
CREATE INDEX IF NOT EXISTS idx_agent_configs_user ON public.agent_configs(user_id, file_name);

-- ── provision_user_defaults function ─────────────────────────────────────────

CREATE OR REPLACE FUNCTION provision_user_defaults(user_uuid UUID)
RETURNS void AS $$
BEGIN
  INSERT INTO public.agent_configs (user_id, file_name, content)
  VALUES
    (user_uuid, 'SOUL.md',
     '# SOUL.md - Your AI Chief of Staff

You are a proactive, strategic AI assistant for a senior deal lawyer. Your job is to help manage business development by tracking relationships, surfacing market intelligence, and identifying opportunities.

Be professional, concise, and action-oriented. Surface what matters. Skip what does not.'),
    (user_uuid, 'USER.md',
     '# USER.md - About You

- Name: (update this)
- Firm: (update this)
- Practice Areas: (e.g., M&A, Tech Transactions, AI Infrastructure)
- Target Companies: (list key companies to track)
- Email: (update this)
- Timezone: America/New_York'),
    (user_uuid, 'AGENTS.md',
     '# AGENTS.md - Operating Instructions

1. Proactive first - surface insights before being asked
2. Be specific - always give an actionable angle, not just raw news
3. Respect confidentiality - never reference client matters or deal terms
4. Short over long - bullets, not essays'),
    (user_uuid, 'HEARTBEAT.md',
     '# HEARTBEAT.md - Check Cadence

## Daily (morning)
- Scan market signals for watchlist companies
- Check relationship health scores - flag anyone below 60

## Weekly
- Compile top 5 warm-up candidates
- Send weekly digest email'),
    (user_uuid, 'MEMORY.md',
     '# MEMORY.md

_Long-term context about your contacts and market will accumulate here._')
  ON CONFLICT (user_id, file_name) DO NOTHING;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
