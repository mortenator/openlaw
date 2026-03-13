-- Migration: 003_add_company_watchlist.sql
-- Adds is_watchlist column to companies table

ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_watchlist BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_companies_watchlist ON companies(user_id, is_watchlist);
