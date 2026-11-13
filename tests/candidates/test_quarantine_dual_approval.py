"""
Tests for Two-Person Quarantine Dual-Approval Protocol
Phase 4.14.2.1 — Issue 3
"""

import pytest
from pathlib import Path
from dataclasses import replace
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import (
    DualApprovalRequiredError,
    InvalidDualApprovalError,
    ValidationError,
)


@pytest.fixture
def dual_env(tmp_path: Path):
    """Sets up an environment with two distinct human reviewers and a quarantined candidate."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        quarantine = QuarantineManager(db, repo, reviewers)
        auth = LocalSecureAuthenticator()

        # Seed valid source
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_dual",
                name="Dual Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="d" * 64,
                registry_entry_sha256="e" * 64,
            )
        )

        # Reviewer 1: SAFETY_COMPLIANCE_OFFICER
        rev1 = reviewers.create_reviewer("safety_officer_sam", "Sam Safety", "sam@veda.internal")
        reviewers.assign_role(rev1.reviewer_id, "SAFETY_COMPLIANCE_OFFICER", assigned_by="admin")
        priv1_pem, pub1_hex = Ed25519SignatureService.generate_key_pair()
        key1 = reviewers.register_public_key(rev1.reviewer_id, pub1_hex, is_test_key=False)
        reviewers.activate_public_key(key1.public_key_id, actor_id="admin")
        session1 = auth.create_session(rev1.reviewer_id)
        reviewers.record_authentication_event(session1)

        # Reviewer 2: LEGAL_COMPLIANCE_AUDITOR
        rev2 = reviewers.create_reviewer("legal_auditor_laura", "Laura Legal", "laura@veda.internal")
        reviewers.assign_role(rev2.reviewer_id, "LEGAL_COMPLIANCE_AUDITOR", assigned_by="admin")
        priv2_pem, pub2_hex = Ed25519SignatureService.generate_key_pair()
        key2 = reviewers.register_public_key(rev2.reviewer_id, pub2_hex, is_test_key=False)
        reviewers.activate_public_key(key2.public_key_id, actor_id="admin")
        session2 = auth.create_session(rev2.reviewer_id)
        reviewers.record_authentication_event(session2)

        # Ingest candidate and quarantine it
        cand = repo.submit_candidate("Quarantined sensitive prose for dual review.", "src_dual", "doc_dual_01")
        repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
        repo.update_status(cand.candidate_id, "QUARANTINED")
        case = repo.create_quarantine_case(
            cand.candidate_id,
            reason="SEMANTIC_SAFETY_CONFLICT",
            category="SAFETY",
            evidence_json='{"confidence":0.78}',
            assigned_reviewer_id=rev1.reviewer_id,
            assigned_role="ROLE_SAFETY_OFFICER",
        )

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "quarantine": quarantine,
            "case": case,
            "cand": cand,
            "rev1": rev1,
            "key1": key1,
            "priv1": priv1_pem,
            "session1": session1,
            "rev2": rev2,
            "key2": key2,
            "priv2": priv2_pem,
            "session2": session2,
        }


def test_single_reviewer_direct_approval_forbidden(dual_env):
    """Verify that calling resolve_quarantine with action 'APPROVED' raises DualApprovalRequiredError."""
    env = dual_env
    quarantine = env["quarantine"]

    with pytest.raises(DualApprovalRequiredError, match="Direct single-reviewer approval of quarantined candidate is forbidden"):
        quarantine.resolve_quarantine(
            case_id=env["case"].case_id,
            reviewer_id=env["rev1"].reviewer_id,
            reviewer_role="SAFETY_COMPLIANCE_OFFICER",
            public_key_id=env["key1"].public_key_id,
            auth_event_id=env["session1"].auth_event_id,
            resolution_action="APPROVED",
            resolution_reason="Single reviewer attempting direct approval",
            private_key_pem=env["priv1"],
        )


def test_two_person_dual_approval_workflow_success(dual_env):
    """
    Verify complete 2-person dual approval:
    1. First reviewer initiates Leg 1 -> status remains QUARANTINED.
    2. Second distinct reviewer completes Leg 2 -> status transitions to APPROVED.
    """
    env = dual_env
    quarantine = env["quarantine"]
    repo = env["repo"]
    case_id = env["case"].case_id
    cand_id = env["cand"].candidate_id

    # 1. Leg 1 by Reviewer 1 (Sam)
    leg1 = quarantine.initiate_quarantine_dual_approval(
        case_id=case_id,
        reviewer_id=env["rev1"].reviewer_id,
        reviewer_role="SAFETY_COMPLIANCE_OFFICER",
        public_key_id=env["key1"].public_key_id,
        auth_event_id=env["session1"].auth_event_id,
        decision_reason="Reviewed linguistic safety; context confirmed benign.",
        private_key_pem=env["priv1"],
    )

    assert leg1.dual_status == "FIRST_LEG_APPROVED"
    assert leg1.first_reviewer_id == env["rev1"].reviewer_id
    assert leg1.second_reviewer_id is None

    # Candidate remains strictly QUARANTINED
    cand_after_leg1 = repo.get_candidate(cand_id)
    assert cand_after_leg1.processing_status == "QUARANTINED"

    # Quarantine case remains unresolved
    case_after_leg1 = quarantine.get_case(case_id)
    assert case_after_leg1.resolution_decision_id is None

    # 2. Leg 2 by Reviewer 2 (Laura)
    leg2 = quarantine.complete_quarantine_dual_approval(
        case_id=case_id,
        reviewer_id=env["rev2"].reviewer_id,
        reviewer_role="LEGAL_COMPLIANCE_AUDITOR",
        public_key_id=env["key2"].public_key_id,
        auth_event_id=env["session2"].auth_event_id,
        decision_reason="Second independent sign-off confirming dialect compliance.",
        evidence_reference="DOC-REF-992",
        private_key_pem=env["priv2"],
    )

    assert leg2.dual_status == "COMPLETED"
    assert leg2.second_reviewer_id == env["rev2"].reviewer_id
    assert leg2.completed_at is not None

    # Candidate is now officially APPROVED
    cand_after_leg2 = repo.get_candidate(cand_id)
    assert cand_after_leg2.processing_status == "APPROVED"

    # Quarantine case is resolved
    case_after_leg2 = quarantine.get_case(case_id)
    assert case_after_leg2.resolution_decision_id is not None
    assert case_after_leg2.resolution_evidence_reference == "DOC-REF-992"


def test_two_person_rule_rejects_same_reviewer(dual_env):
    """Verify that attempting to complete Leg 2 with the same reviewer raises InvalidDualApprovalError."""
    env = dual_env
    quarantine = env["quarantine"]
    case_id = env["case"].case_id

    # Leg 1 by Rev 1
    quarantine.initiate_quarantine_dual_approval(
        case_id=case_id,
        reviewer_id=env["rev1"].reviewer_id,
        reviewer_role="SAFETY_COMPLIANCE_OFFICER",
        public_key_id=env["key1"].public_key_id,
        auth_event_id=env["session1"].auth_event_id,
        decision_reason="Leg 1 approval",
        private_key_pem=env["priv1"],
    )

    # Attempt Leg 2 with SAME Rev 1
    with pytest.raises(InvalidDualApprovalError, match="cannot be identical to first reviewer"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case_id,
            reviewer_id=env["rev1"].reviewer_id,
            reviewer_role="SAFETY_COMPLIANCE_OFFICER",
            public_key_id=env["key1"].public_key_id,
            auth_event_id=env["session1"].auth_event_id,
            decision_reason="Leg 2 attempt by same reviewer",
            private_key_pem=env["priv1"],
        )


def test_two_person_rule_rejects_shared_email(dual_env, monkeypatch):
    """Verify that a second reviewer sharing the same email is rejected to prevent alias circumvention."""
    env = dual_env
    quarantine = env["quarantine"]
    case_id = env["case"].case_id

    # Leg 1 by Rev 1 (sam@veda.internal)
    quarantine.initiate_quarantine_dual_approval(
        case_id=case_id,
        reviewer_id=env["rev1"].reviewer_id,
        reviewer_role="SAFETY_COMPLIANCE_OFFICER",
        public_key_id=env["key1"].public_key_id,
        auth_event_id=env["session1"].auth_event_id,
        decision_reason="Leg 1 approval",
        private_key_pem=env["priv1"],
    )

    # Reviewer 2 is laura@veda.internal. If reviewer 2's email matches reviewer 1's email:
    orig_get_reviewer = quarantine.reviewers.get_reviewer
    def mock_get_reviewer(rid):
        rec = orig_get_reviewer(rid)
        if rec and rid == env["rev2"].reviewer_id:
            return replace(rec, email="sam@veda.internal")
        return rec

    monkeypatch.setattr(quarantine.reviewers, "get_reviewer", mock_get_reviewer)

    # Attempt Leg 2 with shared email
    with pytest.raises(InvalidDualApprovalError, match="shares email"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case_id,
            reviewer_id=env["rev2"].reviewer_id,
            reviewer_role="LEGAL_COMPLIANCE_AUDITOR",
            public_key_id=env["key2"].public_key_id,
            auth_event_id=env["session2"].auth_event_id,
            decision_reason="Attempt by alias",
            private_key_pem=env["priv2"],
        )


def test_dual_approval_detects_content_tampering_between_legs(dual_env):
    """Verify that if candidate content is modified after Leg 1, Leg 2 fails closed."""
    env = dual_env
    quarantine = env["quarantine"]
    db = env["db"]
    case_id = env["case"].case_id
    cand_id = env["cand"].candidate_id

    # Leg 1
    quarantine.initiate_quarantine_dual_approval(
        case_id=case_id,
        reviewer_id=env["rev1"].reviewer_id,
        reviewer_role="SAFETY_COMPLIANCE_OFFICER",
        public_key_id=env["key1"].public_key_id,
        auth_event_id=env["session1"].auth_event_id,
        decision_reason="Leg 1 approval",
        private_key_pem=env["priv1"],
    )

    # Tamper with candidate normalized_content_hash directly in DB (must be valid 64-char hex)
    tampered_hash = "f" * 64
    db.execute(
        "UPDATE candidate_submissions SET normalized_content_hash = ? WHERE candidate_id = ?;",
        (tampered_hash, cand_id),
    )

    # Leg 2 should detect hash mismatch and reject
    with pytest.raises(InvalidDualApprovalError, match="Candidate normalized content hash has changed"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case_id,
            reviewer_id=env["rev2"].reviewer_id,
            reviewer_role="LEGAL_COMPLIANCE_AUDITOR",
            public_key_id=env["key2"].public_key_id,
            auth_event_id=env["session2"].auth_event_id,
            decision_reason="Leg 2 approval on tampered content",
            private_key_pem=env["priv2"],
        )
