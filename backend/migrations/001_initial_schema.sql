-- OpenLaw: Initial Schema
-- Migration: 001_initial_schema.sql
-- Run against your Supabase project via the SQL editor or psql

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    firm            TEXT,
    practice_area   TEXT[] NOT NULL DEFAULT '{}',
    comms_channel   TEXT NOT NULL DEFAULT 'email',
    timezone        TEXT NOT NULL DEFAULT 'UTC',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ── Agent Config ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_configs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scan_frequency          TEXT NOT NULL DEFAULT 'weekly',
    outreach_tone           TEXT NOT NULL DEFAULT 'professional',
    max_weekly_outreach     INT  NOT NULL DEFAULT 5,
    focus_keywords          TEXT[] NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_configs_user_id ON agent_configs(user_id);

-- ── Agent Memory Logs ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_memory_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_key  TEXT NOT NULL,
    memory_val  JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_user_id_created ON agent_memory_logs(user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_memory_user_key ON agent_memory_logs(user_id, memory_key);

-- ── Companies ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS companies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    domain      TEXT,
    industry    TEXT,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_companies_user_id_created ON companies(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);

-- ── Contacts ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS contacts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id          UUID REFERENCES companies(id) ON DELETE SET NULL,
    name                TEXT NOT NULL,
    email               TEXT,
    phone               TEXT,
    role                TEXT,
    tier                INT  NOT NULL DEFAULT 2 CHECK (tier IN (1, 2, 3)),
    tags                TEXT[] NOT NULL DEFAULT '{}',
    notes               TEXT,
    last_contacted_at   TIMESTAMPTZ,
    health_score        INT  NOT NULL DEFAULT 100 CHECK (health_score BETWEEN 0 AND 100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_user_id_created  ON contacts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_user_id_health   ON contacts(user_id, health_score);
CREATE INDEX IF NOT EXISTS idx_contacts_company_id       ON contacts(company_id);

-- ── Signals ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS signals (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id       UUID REFERENCES contacts(id) ON DELETE SET NULL,
    company_id       UUID REFERENCES companies(id) ON DELETE SET NULL,
    source           TEXT NOT NULL,
    headline         TEXT NOT NULL,
    url              TEXT,
    summary          TEXT,
    relevance_score  FLOAT,
    raw_data         JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_user_id_created   ON signals(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_contact_id        ON signals(contact_id);
CREATE INDEX IF NOT EXISTS idx_signals_company_id        ON signals(company_id);

-- ── Outreach Suggestions ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS outreach_suggestions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_id   UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    signal_id    UUID REFERENCES signals(id) ON DELETE SET NULL,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    edited_body  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'sent', 'dismissed')),
    scheduled_at TIMESTAMPTZ,
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_user_id_created ON outreach_suggestions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_status          ON outreach_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_outreach_contact_id      ON outreach_suggestions(contact_id);

-- ── User Crons ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_crons (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    cron_expression   TEXT NOT NULL,
    job_type          TEXT NOT NULL,
    config            JSONB NOT NULL DEFAULT '{}',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at       TIMESTAMPTZ,
    next_run_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_crons_user_id ON user_crons(user_id);
CREATE INDEX IF NOT EXISTS idx_user_crons_active  ON user_crons(is_active, next_run_at);

-- ── Deliveries ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS deliveries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delivery_type   TEXT NOT NULL,
    channel         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'failed')),
    payload         JSONB,
    error_message   TEXT,
    delivered_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deliveries_user_id_created ON deliveries(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deliveries_status          ON deliveries(status);

-- ── Auto-update updated_at trigger ─────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'agent_configs', 'agent_memory_logs', 'companies',
        'contacts', 'outreach_suggestions', 'user_crons'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
            t, t
        );
    END LOOP;
END;
$$;
