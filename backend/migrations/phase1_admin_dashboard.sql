-- =============================================================================
-- Phase 1 Migration: Admin Dashboard RBAC & Analytics Foundations
-- Project: SabiLens  |  Target: GCP Cloud SQL PostgreSQL 15
-- Updated: 2026-04-29 (v6 — idempotent, safe to re-run)
-- Run order: Step 1 → 2 → 3 → 4 → 5
-- =============================================================================


-- =============================================================================
-- STEP 1: nafdac_access_requests
-- State machine for the NAFDAC "Further Breakdown" approval workflow.
-- Statuses: pending → approved | rejected; approved → revoked
-- =============================================================================

CREATE TABLE IF NOT EXISTS nafdac_access_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by_id     UUID NOT NULL REFERENCES users(id),
    jurisdiction        VARCHAR(100) NOT NULL,   -- copied from user.state at request time
    breakdown_type      VARCHAR(50)  NOT NULL,   -- brand_breakdown | quantity_breakdown | company_breakdown
    justification       TEXT NOT NULL,
    filter_category     VARCHAR(100),
    filter_date_from    DATE,
    filter_date_to      DATE,
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending',
    reviewed_by_id      UUID REFERENCES users(id),
    review_notes        TEXT,
    approved_at         TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,             -- super admin sets TTL on approval
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_nafdac_access_status
        CHECK (status IN ('pending', 'approved', 'rejected', 'revoked'))
);

-- One pending OR approved request per breakdown type per user at a time.
-- DB-level guard: returns 409 before app logic runs.
CREATE UNIQUE INDEX IF NOT EXISTS uix_nafdac_access_one_active
    ON nafdac_access_requests (requested_by_id, breakdown_type)
    WHERE status IN ('pending', 'approved');

-- General status filter (used on super admin queue view)
CREATE INDEX IF NOT EXISTS idx_nafdac_access_status
    ON nafdac_access_requests (status);

-- Reviewer lookup
CREATE INDEX IF NOT EXISTS idx_nafdac_access_reviewer
    ON nafdac_access_requests (reviewed_by_id)
    WHERE reviewed_by_id IS NOT NULL;

-- Hot path: loaded on every admin request to populate TenantContext._approved set
CREATE INDEX IF NOT EXISTS idx_nafdac_access_active
    ON nafdac_access_requests (requested_by_id, breakdown_type)
    WHERE status = 'approved';


-- =============================================================================
-- STEP 2: Extend analytics_daily with per-company and per-state scope axes
-- (company_id IS NULL, state IS NULL) = platform-wide aggregate  ← existing rows
-- company_id = X                       = that company's daily shard
-- state      = Y                       = that state's daily shard
-- =============================================================================

ALTER TABLE analytics_daily
    ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS state      VARCHAR(100) DEFAULT NULL;

-- Drop the old plain-date unique constraint if it exists.
-- SQLAlchemy's unique=True creates a named CONSTRAINT (not a bare index), so
-- DROP INDEX fails with "constraint requires it" — use ALTER TABLE DROP CONSTRAINT.
-- Dropping the constraint also drops the backing index automatically.
ALTER TABLE analytics_daily DROP CONSTRAINT IF EXISTS analytics_daily_date_key;

-- New composite unique index scopes uniqueness to (date, company_id, state)
CREATE UNIQUE INDEX IF NOT EXISTS uix_analytics_daily_scope
    ON analytics_daily (date, COALESCE(company_id::text, ''), COALESCE(state, ''));


-- =============================================================================
-- STEP 3: Scan table indexes for RBAC query performance
-- Every admin dashboard query passes through TenantContext filters on these columns.
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_scans_company_id
    ON scans (company_id);

CREATE INDEX IF NOT EXISTS idx_scans_state_status
    ON scans (scan_location_state, status);

CREATE INDEX IF NOT EXISTS idx_scans_state_created
    ON scans (scan_location_state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_scans_company_state
    ON scans (company_id, scan_location_state, status);


-- =============================================================================
-- STEP 4: admin_reports — subcategory slug column (v6 addition)
-- Stores the human-readable nafdac_chunks.json slug alongside the UUID
-- so report summaries can display category names without a join.
-- =============================================================================

ALTER TABLE admin_reports
    ADD COLUMN IF NOT EXISTS filter_subcategory_slug VARCHAR(100);


-- =============================================================================
-- STEP 5: Verification queries
-- Run these after the migration to confirm everything applied correctly.
-- Expected: each query should return 1 row with exists = true.
-- =============================================================================

SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'nafdac_access_requests'
) AS nafdac_access_requests_exists;

SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'analytics_daily' AND column_name = 'company_id'
) AS analytics_daily_company_id_exists;

SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'analytics_daily' AND column_name = 'state'
) AS analytics_daily_state_exists;

SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'admin_reports' AND column_name = 'filter_subcategory_slug'
) AS admin_reports_slug_exists;

SELECT indexname, tablename
FROM pg_indexes
WHERE tablename IN ('scans', 'nafdac_access_requests', 'analytics_daily')
  AND indexname IN (
      'idx_scans_company_id',
      'idx_scans_state_status',
      'idx_scans_state_created',
      'idx_scans_company_state',
      'uix_nafdac_access_one_active',
      'idx_nafdac_access_status',
      'idx_nafdac_access_active',
      'uix_analytics_daily_scope'
  )
ORDER BY tablename, indexname;
