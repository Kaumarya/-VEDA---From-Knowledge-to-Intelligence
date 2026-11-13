"""
Tests for Reviewer Role Taxonomy, Granular Permissions, and RBAC Authorization
Phase 4.14.2.1 — Issue 2
"""

import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.exceptions import (
    ReviewerNotFoundError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    RolePermissionError,
)


@pytest.fixture
def rbac_env(tmp_path: Path):
    """Sets up a migrated database with ReviewerService."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()
        reviewers = ReviewerService(db)
        yield {"db": db, "reviewers": reviewers}


def test_canonical_roles_seeded_in_database(rbac_env):
    """Verify that all five canonical reviewer roles are seeded and active."""
    db = rbac_env["db"]
    rows = db.fetchall("SELECT role_name FROM reviewer_roles ORDER BY role_name;")
    role_names = {r["role_name"] for r in rows}

    expected_roles = {
        "LEGAL_COMPLIANCE_AUDITOR",
        "DOMAIN_CURATOR",
        "SAFETY_COMPLIANCE_OFFICER",
        "CHIEF_DATA_OFFICER",
        "AUDIT_OBSERVER",
    }
    assert expected_roles.issubset(role_names)


def test_granular_permissions_matrix(rbac_env):
    """Verify that role permissions strictly match the governance matrix."""
    reviewers = rbac_env["reviewers"]

    # 1. DOMAIN_CURATOR: can approve and reject, but cannot manage keys or admin accounts
    curator = reviewers.create_reviewer("curator_test", "Curator Test", "curator@veda.internal")
    reviewers.assign_role(curator.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")

    assert reviewers.check_permission(curator.reviewer_id, "can_approve_candidates") is True
    assert reviewers.check_permission(curator.reviewer_id, "can_reject_candidates") is True
    assert reviewers.check_permission(curator.reviewer_id, "can_manage_keys") is False
    assert reviewers.check_permission(curator.reviewer_id, "can_administer_accounts") is False
    assert reviewers.check_permission(curator.reviewer_id, "can_issue_retention") is False

    # 2. LEGAL_COMPLIANCE_AUDITOR: can issue retention and participate in dual approval, but cannot approve ordinary candidates
    auditor = reviewers.create_reviewer("auditor_test", "Auditor Test", "auditor@veda.internal")
    reviewers.assign_role(auditor.reviewer_id, "LEGAL_COMPLIANCE_AUDITOR", assigned_by="admin")

    assert reviewers.check_permission(auditor.reviewer_id, "can_issue_retention") is True
    assert reviewers.check_permission(auditor.reviewer_id, "can_participate_dual_appr") is True
    assert reviewers.check_permission(auditor.reviewer_id, "can_approve_candidates") is False

    # 3. CHIEF_DATA_OFFICER: executive authority with all permissions
    cdo = reviewers.create_reviewer("cdo_test", "CDO Test", "cdo@veda.internal")
    reviewers.assign_role(cdo.reviewer_id, "CHIEF_DATA_OFFICER", assigned_by="admin")

    assert reviewers.check_permission(cdo.reviewer_id, "can_approve_candidates") is True
    assert reviewers.check_permission(cdo.reviewer_id, "can_administer_accounts") is True
    assert reviewers.check_permission(cdo.reviewer_id, "can_manage_keys") is True
    assert reviewers.check_permission(cdo.reviewer_id, "can_issue_retention") is True

    # 4. AUDIT_OBSERVER: read-only inspection only
    observer = reviewers.create_reviewer("observer_test", "Observer Test", "observer@veda.internal")
    reviewers.assign_role(observer.reviewer_id, "AUDIT_OBSERVER", assigned_by="admin")

    assert reviewers.check_permission(observer.reviewer_id, "can_inspect_audit") is True
    assert reviewers.check_permission(observer.reviewer_id, "can_approve_candidates") is False
    assert reviewers.check_permission(observer.reviewer_id, "can_reject_candidates") is False
    assert reviewers.check_permission(observer.reviewer_id, "can_resolve_quarantine") is False


def test_assert_permission_raises_role_permission_error(rbac_env):
    """Verify that assert_permission fails closed with RolePermissionError."""
    reviewers = rbac_env["reviewers"]
    rev = reviewers.create_reviewer("auditor_alice", "Alice Auditor", "alice@veda.internal")
    reviewers.assign_role(rev.reviewer_id, "ROLE_LEGAL_AUDITOR", assigned_by="admin")

    # Auditor cannot approve ordinary candidates
    with pytest.raises(RolePermissionError, match="lacks required permission 'can_approve_candidates'"):
        reviewers.assert_permission(rev.reviewer_id, "can_approve_candidates")

    # Auditor can issue retention decisions
    reviewers.assert_permission(rev.reviewer_id, "can_issue_retention")


def test_inactive_reviewer_fails_permission_checks(rbac_env):
    """Verify that inactive/suspended reviewers possess zero active permissions."""
    reviewers = rbac_env["reviewers"]
    cdo = reviewers.create_reviewer("cdo_inactive", "Inactive CDO", "inactive@veda.internal")
    reviewers.assign_role(cdo.reviewer_id, "CHIEF_DATA_OFFICER", assigned_by="admin")

    # While ACTIVE, possesses permissions
    assert reviewers.check_permission(cdo.reviewer_id, "can_approve_candidates") is True

    # Deactivate account
    reviewers.set_account_status(cdo.reviewer_id, "SUSPENDED")
    assert reviewers.check_permission(cdo.reviewer_id, "can_approve_candidates") is False

    with pytest.raises(ReviewerInactiveError, match="not active"):
        reviewers.assert_permission(cdo.reviewer_id, "can_approve_candidates")


def test_role_assignment_and_revocation(rbac_env):
    """Verify that assign_role and revoke_role dynamically modify active permissions."""
    reviewers = rbac_env["reviewers"]
    user = reviewers.create_reviewer("user_dynamic", "Dynamic User", "dyn@veda.internal")

    # Initially has no roles or approval permissions
    assert reviewers.check_permission(user.reviewer_id, "can_approve_candidates") is False

    # Assign DOMAIN_CURATOR by role_name
    reviewers.assign_role(user.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")
    assert reviewers.check_permission(user.reviewer_id, "can_approve_candidates") is True

    # Revoke DOMAIN_CURATOR
    reviewers.revoke_role(user.reviewer_id, "DOMAIN_CURATOR")
    assert reviewers.check_permission(user.reviewer_id, "can_approve_candidates") is False

