-- Migration: 005_paperclip_integration.sql
-- Renames 'companies' (BD target firms) to 'tracked_firms' to avoid collision
-- with Paperclip's own 'companies' concept (tenant orgs).
-- Also adds paperclip_company_id and paperclip_agent_id to users.
--
-- ⚠️  RLS POLICIES: If any RLS policies reference the 'companies' table on other
-- tables, verify them manually after running this migration. Table rename in
-- Postgres updates FK references but does NOT update policy names or USING/WITH CHECK
-- clauses on sibling tables. Run: SELECT * FROM pg_policies WHERE tablename = 'companies';
-- before applying to confirm there are none.
--
-- ⚠️  IRREVERSIBLE in normal flow. Manual rollback if needed:
--   ALTER TABLE tracked_firms RENAME TO companies;
--   ALTER INDEX idx_tracked_firms_user_id_created RENAME TO idx_companies_user_id_created;
--   ALTER INDEX idx_tracked_firms_domain RENAME TO idx_companies_domain;
--   ALTER INDEX idx_tracked_firms_watchlist RENAME TO idx_companies_watchlist;
--   ALTER TABLE users DROP COLUMN IF EXISTS paperclip_company_id;
--   ALTER TABLE users DROP COLUMN IF EXISTS paperclip_agent_id;

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

-- Rename primary indexes (safe: IF EXISTS via DO block)
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

-- Rename the updated_at trigger on the renamed table
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

-- ── 2. Update contacts FK to point at tracked_firms ─────────────────────────
-- PostgreSQL automatically follows the table rename for existing FKs,
-- but the constraint may still be named 'contacts_company_id_fkey'.
-- Rename it for clarity.

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

-- ── 3. Update signals FK constraint name (if it references companies) ───────

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

-- ── 4. Add Paperclip columns to users ───────────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS paperclip_company_id UUID,
    ADD COLUMN IF NOT EXISTS paperclip_agent_id   UUID;

CREATE INDEX IF NOT EXISTS idx_users_paperclip_company_id
    ON users(paperclip_company_id);

CREATE INDEX IF NOT EXISTS idx_users_paperclip_agent_id
    ON users(paperclip_agent_id);

-- ── 5. Re-register auto-update trigger for tracked_firms ────────────────────
-- The trigger function already exists (from migration 001).
-- Create the trigger on tracked_firms if it doesn't already exist
-- (handles case where rename above moved the trigger).

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
