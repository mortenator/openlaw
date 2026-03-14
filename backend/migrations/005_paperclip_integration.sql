-- Migration: 005_paperclip_integration.sql
-- Renames 'companies' (BD target firms) to 'tracked_firms' to avoid collision
-- with Paperclip's own 'companies' concept (tenant orgs).
-- Also adds paperclip_company_id and paperclip_agent_id to users.
--
-- ⚠️  RLS POLICIES: Verify no RLS policies reference 'companies' before running:
--   SELECT * FROM pg_policies WHERE tablename = 'companies';
--   SELECT * FROM pg_policies WHERE qual LIKE '%companies%' OR with_check LIKE '%companies%';
--
-- ⚠️  MANUAL ROLLBACK (if needed — run each statement individually):
--   ALTER TABLE tracked_firms RENAME TO companies;
--   ALTER INDEX IF EXISTS idx_tracked_firms_user_id_created RENAME TO idx_companies_user_id_created;
--   ALTER INDEX IF EXISTS idx_tracked_firms_domain RENAME TO idx_companies_domain;
--   ALTER INDEX IF EXISTS idx_tracked_firms_watchlist RENAME TO idx_companies_watchlist;
--   ALTER TABLE contacts RENAME CONSTRAINT contacts_tracked_firm_id_fkey TO contacts_company_id_fkey;
--   ALTER TABLE signals RENAME CONSTRAINT signals_tracked_firm_id_fkey TO signals_company_id_fkey;
--   ALTER TABLE users DROP COLUMN IF EXISTS paperclip_company_id;
--   ALTER TABLE users DROP COLUMN IF EXISTS paperclip_agent_id;

BEGIN;

-- ── 1. Rename companies → tracked_firms ────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'companies'
    ) THEN
        ALTER TABLE companies RENAME TO tracked_firms;
    END IF;
END;
$$;

-- ── 2. Rename indexes ───────────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_companies_user_id_created') THEN
        ALTER INDEX idx_companies_user_id_created RENAME TO idx_tracked_firms_user_id_created;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_companies_domain') THEN
        ALTER INDEX idx_companies_domain RENAME TO idx_tracked_firms_domain;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_companies_watchlist') THEN
        ALTER INDEX idx_companies_watchlist RENAME TO idx_tracked_firms_watchlist;
    END IF;
END;
$$;

-- ── 3. Rename updated_at trigger ────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trg_companies_updated_at'
          AND event_object_table = 'tracked_firms'
    ) THEN
        ALTER TRIGGER trg_companies_updated_at ON tracked_firms
            RENAME TO trg_tracked_firms_updated_at;
    END IF;
END;
$$;

-- ── 4. Rename FK constraints ────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'contacts_company_id_fkey'
          AND table_name = 'contacts'
    ) THEN
        ALTER TABLE contacts
            RENAME CONSTRAINT contacts_company_id_fkey
            TO contacts_tracked_firm_id_fkey;
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'signals_company_id_fkey'
          AND table_name = 'signals'
    ) THEN
        ALTER TABLE signals
            RENAME CONSTRAINT signals_company_id_fkey
            TO signals_tracked_firm_id_fkey;
    END IF;
END;
$$;

-- ── 5. Add Paperclip columns to users ───────────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS paperclip_company_id UUID,
    ADD COLUMN IF NOT EXISTS paperclip_agent_id   UUID;

CREATE INDEX IF NOT EXISTS idx_users_paperclip_company_id
    ON users(paperclip_company_id);

CREATE INDEX IF NOT EXISTS idx_users_paperclip_agent_id
    ON users(paperclip_agent_id);

-- ── 6. Ensure tracked_firms has an updated_at trigger ───────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'trg_tracked_firms_updated_at'
          AND event_object_table = 'tracked_firms'
    ) THEN
        EXECUTE '
            CREATE TRIGGER trg_tracked_firms_updated_at
            BEFORE UPDATE ON tracked_firms
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        ';
    END IF;
END;
$$;

COMMIT;
