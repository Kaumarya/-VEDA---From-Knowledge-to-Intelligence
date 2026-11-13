"""
Tests for Migration 005 Design, Role Separation Matrix, and Legal Expungement on Isolated Database Copies
Phase 4.14.2.1.2 — Issue 8 & Issue 9
"""

import sqlite3
import shutil
from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.exceptions import ReviewerUnauthorizedError, RolePermissionError


MIGRATION_005_PROPOSED_SQL = """
-- Migration 005: Role Separation of Duties & Legal Expungement Support

-- 1. Update reviewer role permissions to enforce Separation of Duties (SoD)
UPDATE reviewer_role_permissions
SET can_approve_candidates = 0,
    can_resolve_quarantine = 0,
    can_participate_dual_appr = 0
WHERE role_name = 'CHIEF_DATA_OFFICER';

UPDATE reviewer_role_permissions
SET can_resolve_quarantine = 0
WHERE role_name = 'DOMAIN_CURATOR';

-- 2. Add is_expunged column to candidate_submissions for lawful court-mandated redactions
ALTER TABLE candidate_submissions ADD COLUMN is_expunged INTEGER NOT NULL DEFAULT 0;

-- 3. Audit ledger for legal expungement court orders
CREATE TABLE IF NOT EXISTS legal_expungement_orders (
    expungement_id          TEXT PRIMARY KEY,
    candidate_id            TEXT NOT NULL,
    court_order_ref         TEXT NOT NULL,
    authorized_by           TEXT NOT NULL,
    executed_at             TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT
);

-- 4. Update export view to exclude expunged candidates unconditionally
DROP VIEW IF EXISTS v_export_eligible_candidates;

CREATE VIEW v_export_eligible_candidates AS
SELECT
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution,
    ah.decision_id AS approval_decision_id,
    ah.reviewer_id AS approved_by_reviewer_id,
    ra.full_name AS reviewer_full_name,
    ah.signature_ed25519 AS approval_signature,
    ah.canonical_payload_sha256 AS payload_hash
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
JOIN approval_history ah ON c.candidate_id = ah.candidate_id
JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
WHERE c.processing_status = 'APPROVED'
  AND c.processing_status != 'QUARANTINED'
  AND c.is_canonical = 1
  AND c.is_expunged = 0
  AND s.licensing_status = 'VERIFIED PERMITTED'
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'
  AND s.artifact_sha256 != 'NOT_VERIFIED'
  AND (s.approval_expiration_date IS NULL
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND ah.new_status = 'APPROVED'
  AND ah.verification_status = 'VERIFIED_VALID'
  AND ra.account_status = 'ACTIVE'
  AND k.is_test_key = 0
  AND k.key_status IN ('ACTIVE', 'ROTATED_RETIRED')
  AND ah.created_at >= k.activated_at
  AND (k.valid_until IS NULL OR ah.created_at <= k.valid_until)
  AND (k.revoked_at IS NULL OR ah.created_at < k.revoked_at)
  AND NOT EXISTS (
      SELECT 1 FROM quarantine_cases qc
      WHERE qc.candidate_id = c.candidate_id
        AND qc.resolution_decision_id IS NULL
  )
  AND NOT EXISTS (
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (
      SELECT 1 FROM retention_decisions rd
      WHERE rd.candidate_id = c.candidate_id
        AND rd.decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
  );
"""


@pytest.fixture
def migration_copy_env(tmp_path: Path):
    """Sets up an isolated copy of the candidate database to test Migration 005 safely."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()
        yield {"db": db, "config": config, "tmp_path": tmp_path}


def test_migration_005_applies_cleanly_on_database_copy(migration_copy_env):
    """Verifies that the proposed Migration 005 executes cleanly and establishes SoD."""
    env = migration_copy_env
    db = env["db"]

    # Execute proposed Migration 005 in a transaction
    with db.transaction() as c:
        c.executescript(MIGRATION_005_PROPOSED_SQL)

    # 1. Verify PRAGMA quick_check
    qc = db.fetchone("PRAGMA quick_check;")
    assert qc[0] == "ok"

    # 2. Verify foreign keys
    fk = db.fetchall("PRAGMA foreign_key_check;")
    assert len(fk) == 0

    # 3. Verify CDO has can_approve_candidates = 0 (Separation of Duties enforced)
    cdo_perms = db.fetchone(
        "SELECT * FROM reviewer_role_permissions WHERE role_name = 'CHIEF_DATA_OFFICER';"
    )
    assert cdo_perms["can_approve_candidates"] == 0
    assert cdo_perms["can_resolve_quarantine"] == 0
    assert cdo_perms["can_participate_dual_appr"] == 0
    assert cdo_perms["can_administer_accounts"] == 1
    assert cdo_perms["can_manage_keys"] == 1

    # 4. Verify candidate_submissions has is_expunged column
    cols = [r["name"] for r in db.fetchall("PRAGMA table_info(candidate_submissions);")]
    assert "is_expunged" in cols


def test_cdo_approval_prevented_under_separation_of_duties(migration_copy_env):
    """Verifies that under Migration 005 permissions, CDO cannot approve candidates."""
    env = migration_copy_env
    db = env["db"]

    with db.transaction() as c:
        c.executescript(MIGRATION_005_PROPOSED_SQL)

    repo = CandidateRepository(db)
    reviewers = ReviewerService(db)

    # Create CDO account
    cdo = reviewers.create_reviewer("cdo_exec", "Chief Data Officer", "cdo@veda.internal")
    reviewers.assign_role(cdo.reviewer_id, "CHIEF_DATA_OFFICER", assigned_by="admin")

    # Asserting permission can_approve_candidates must raise RolePermissionError
    assert reviewers.check_permission(cdo.reviewer_id, "can_approve_candidates") is False
    with pytest.raises(RolePermissionError):
        reviewers.assert_permission(cdo.reviewer_id, "can_approve_candidates")


def test_migration_005_transactional_rollback_on_failure(migration_copy_env):
    """Verifies that an error during migration cleanly rolls back without corrupting the DB."""
    env = migration_copy_env
    db = env["db"]

    failing_script = """
    BEGIN IMMEDIATE;
    UPDATE reviewer_role_permissions SET can_approve_candidates = 0 WHERE role_name = 'CHIEF_DATA_OFFICER';
    CREATE TABLE canary_table_should_rollback (id INT);
    SYNTAX ERROR TRIGGERING ROLLBACK;
    COMMIT;
    """

    raw_conn = db._raw_conn
    with pytest.raises(sqlite3.OperationalError):
        try:
            raw_conn.executescript(failing_script)
        finally:
            if raw_conn.in_transaction:
                raw_conn.execute("ROLLBACK;")

    # Canary table must not exist
    table = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='canary_table_should_rollback';")
    assert table is None

    # CDO permissions must remain unchanged (can_approve_candidates = 1 before migration)
    cdo_perms = db.fetchone("SELECT can_approve_candidates FROM reviewer_role_permissions WHERE role_name = 'CHIEF_DATA_OFFICER';")
    assert cdo_perms["can_approve_candidates"] == 1
