"""
Tests for Governance, Reviewer Authentication, Signatures, Quarantine & Retention
Phase 4.14.2 — Stage 4
"""

import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.signatures import Ed25519SignatureService, canonicalize_json
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.retention import RetentionManager
from foundation.candidates.revocation import RevocationManager
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import (
    ReviewerUnauthorizedError,
    ReviewerInactiveError,
    KeyRevokedError,
    InvalidSignatureError,
    QuarantineTimeoutMutationError,
    ValidationError,
)


@pytest.fixture
def governance_env(tmp_path: Path):
    """Sets up a complete governance and reviewer environment with active keys and sources."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        authenticator = LocalSecureAuthenticator()
        approvals = ApprovalService(db, repo, reviewers)
        quarantine = QuarantineManager(db, repo, reviewers)
        retention = RetentionManager(db)
        revocation = RevocationManager(db, repo, reviewers)

        # 1. Seed valid source
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="SRC_CORPUS_01",
                name="Validated Corpus Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC-BY-4.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="a" * 64,
                registry_entry_sha256="b" * 64,
            )
        )

        # 2. Register human reviewer with DOMAIN_CURATOR role
        curator = reviewers.create_reviewer("curator_jane", "Jane Doe", "jane@veda.internal")
        reviewers.assign_role(curator.reviewer_id, "ROLE_DOMAIN_CURATOR", assigned_by="admin")

        # 3. Generate and activate production key pair for curator
        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        key_record = reviewers.register_public_key(curator.reviewer_id, pub_hex, is_test_key=False)
        reviewers.activate_public_key(key_record.public_key_id, actor_id="admin")

        # 4. Create active auth session
        auth_session = authenticator.create_session(curator.reviewer_id)
        reviewers.record_authentication_event(auth_session)

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "approvals": approvals,
            "quarantine": quarantine,
            "retention": retention,
            "revocation": revocation,
            "curator": curator,
            "priv_pem": priv_pem,
            "pub_hex": pub_hex,
            "key_record": key_record,
            "auth_session": auth_session,
        }


def advance_to_approval_pending(repo: CandidateRepository, candidate_id: str) -> None:
    """Helper to step candidate through lifecycle to APPROVAL_PENDING."""
    repo.update_status(candidate_id, "PROCESSING_PASSED")
    repo.update_status(candidate_id, "APPROVAL_PENDING")


def test_valid_approval_signature_passes(governance_env):
    """Verify that an authorized human reviewer creates a valid approval with Ed25519 signature."""
    env = governance_env
    repo = env["repo"]
    approvals = env["approvals"]

    cand = repo.submit_candidate(
        "Natural expository English prose demonstrates proper vocabulary and register.",
        "SRC_CORPUS_01",
        "doc_01",
    )
    advance_to_approval_pending(repo, cand.candidate_id)

    approval_rec = approvals.approve_candidate(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key_record"].public_key_id,
        auth_event_id=env["auth_session"].auth_event_id,
        decision_reason="Expository prose adheres to corpus standards.",
        private_key_pem=env["priv_pem"],
    )

    assert approval_rec.new_status == "APPROVED"
    assert approval_rec.verification_status == "VERIFIED_VALID"
    assert len(approval_rec.signature_ed25519) == 128
    assert len(approval_rec.canonical_payload_sha256) == 64

    # Verify candidate status updated
    updated_cand = repo.get_candidate(cand.candidate_id)
    assert updated_cand.processing_status == "APPROVED"


def test_invalid_signature_bytes_fails(governance_env):
    """Verify corrupted signature is rejected with InvalidSignatureError."""
    env = governance_env
    repo = env["repo"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("Another valid sentence.", "SRC_CORPUS_01", "doc_02")
    advance_to_approval_pending(repo, cand.candidate_id)

    # Pass corrupt signature
    corrupt_sig = "0" * 128
    with pytest.raises(InvalidSignatureError):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["curator"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["key_record"].public_key_id,
            auth_event_id=env["auth_session"].auth_event_id,
            decision_reason="Should fail",
            provided_signature_hex=corrupt_sig,
        )


def test_altered_candidate_hash_breaks_verification(governance_env):
    """Verify that signing a payload with an altered candidate hash is detected."""
    env = governance_env
    # Build payload with tampered hash
    payload = Ed25519SignatureService.build_canonical_approval_payload(
        candidate_id="cand_1",
        decision_id="dec_1",
        decision="APPROVED",
        decision_reason="Tampered hash test",
        decision_timestamp="2026-11-13T12:00:00Z",
        normalized_content_hash="f" * 64,  # Tampered hash
        source_id="SRC_CORPUS_01",
        source_artifact_sha256="a" * 64,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
    )
    canonical_bytes = canonicalize_json(payload)
    sig_hex = Ed25519SignatureService.sign(env["priv_pem"], canonical_bytes)

    # Now verify against legitimate payload with different hash
    legit_payload = dict(payload)
    legit_payload["normalized_content_hash"] = "e" * 64
    legit_bytes = canonicalize_json(legit_payload)

    with pytest.raises(InvalidSignatureError):
        Ed25519SignatureService.verify(env["pub_hex"], legit_bytes, sig_hex)


def test_unauthorized_role_rejected(governance_env):
    """Verify reviewer without required role cannot approve."""
    env = governance_env
    repo = env["repo"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("English sentence.", "SRC_CORPUS_01", "doc_03")
    advance_to_approval_pending(repo, cand.candidate_id)

    # Curator only has DOMAIN_CURATOR, not LEGAL_COMPLIANCE_AUDITOR
    with pytest.raises(ReviewerUnauthorizedError):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["curator"].reviewer_id,
            reviewer_role="LEGAL_COMPLIANCE_AUDITOR",
            public_key_id=env["key_record"].public_key_id,
            auth_event_id=env["auth_session"].auth_event_id,
            decision_reason="Should fail",
            private_key_pem=env["priv_pem"],
        )


def test_inactive_reviewer_rejected(governance_env):
    """Verify suspended reviewer cannot approve candidates."""
    env = governance_env
    repo = env["repo"]
    reviewers = env["reviewers"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("English sentence.", "SRC_CORPUS_01", "doc_04")
    advance_to_approval_pending(repo, cand.candidate_id)

    # Suspend reviewer
    reviewers.set_account_status(env["curator"].reviewer_id, "SUSPENDED")

    with pytest.raises(ReviewerInactiveError):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["curator"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["key_record"].public_key_id,
            auth_event_id=env["auth_session"].auth_event_id,
            decision_reason="Should fail",
            private_key_pem=env["priv_pem"],
        )


def test_revoked_key_rejected(governance_env):
    """Verify revoked public key cannot be used for signing."""
    env = governance_env
    repo = env["repo"]
    reviewers = env["reviewers"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("English sentence.", "SRC_CORPUS_01", "doc_05")
    advance_to_approval_pending(repo, cand.candidate_id)

    # Revoke key
    reviewers.revoke_public_key(env["key_record"].public_key_id, actor_id="admin", reason="Test revocation")

    with pytest.raises(KeyRevokedError):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["curator"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["key_record"].public_key_id,
            auth_event_id=env["auth_session"].auth_event_id,
            decision_reason="Should fail",
            private_key_pem=env["priv_pem"],
        )


def test_quarantine_reminder_and_escalation_non_mutating(governance_env):
    """
    Verify sending reminders and 30-day escalation updates metadata only.
    Candidate status MUST remain QUARANTINED.
    """
    env = governance_env
    repo = env["repo"]
    quarantine = env["quarantine"]

    cand = repo.submit_candidate("Quarantined text.", "SRC_CORPUS_01", "doc_06")
    # Route to quarantine
    case_id = "case_001"
    repo.update_status(cand.candidate_id, "QUARANTINED", is_human=True)

    env["db"].execute(
        """
        INSERT INTO quarantine_cases (
            case_id, candidate_id, quarantine_reason, quarantine_category, diagnostic_evidence_json,
            pipeline_version, review_due_at, assigned_role
        ) VALUES (?, ?, 'LANGUAGE_FILTER_AMBIGUOUS', 'LANGUAGE', '{}', 'v0.4.14', '2099-01-01', 'ROLE_DOMAIN_CURATOR');
        """,
        (case_id, cand.candidate_id),
    )

    # 1. Send reminder
    quarantine.send_reminder(case_id)
    c1 = repo.get_candidate(cand.candidate_id)
    assert c1.processing_status == "QUARANTINED"
    case1 = quarantine.get_case(case_id)
    assert case1.last_reminder_at is not None

    # 2. Escalate after 30 days
    quarantine.escalate_case(case_id, "ESCALATED_30_DAYS")
    c2 = repo.get_candidate(cand.candidate_id)
    assert c2.processing_status == "QUARANTINED"
    case2 = quarantine.get_case(case_id)
    assert case2.escalated_at is not None
    assert case2.escalation_level == "ESCALATED_30_DAYS"


def test_quarantine_human_resolution_release_to_pending(governance_env):
    """Verify human reviewer resolves quarantine case, releasing candidate to APPROVAL_PENDING."""
    env = governance_env
    repo = env["repo"]
    quarantine = env["quarantine"]

    cand = repo.submit_candidate("Quarantined text.", "SRC_CORPUS_01", "doc_07")
    repo.update_status(cand.candidate_id, "QUARANTINED", is_human=True)

    case_id = "case_002"
    env["db"].execute(
        """
        INSERT INTO quarantine_cases (
            case_id, candidate_id, quarantine_reason, quarantine_category, diagnostic_evidence_json,
            pipeline_version, review_due_at, assigned_role
        ) VALUES (?, ?, 'LANGUAGE_FILTER_AMBIGUOUS', 'LANGUAGE', '{}', 'v0.4.14', '2099-01-01', 'ROLE_DOMAIN_CURATOR');
        """,
        (case_id, cand.candidate_id),
    )

    # Human curator resolves quarantine
    resolved_case = quarantine.resolve_quarantine(
        case_id=case_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key_record"].public_key_id,
        auth_event_id=env["auth_session"].auth_event_id,
        resolution_action="RELEASED_TO_PENDING",
        resolution_reason="Confirmed valid formal expository English.",
        private_key_pem=env["priv_pem"],
    )

    assert resolved_case.resolution_decision_id is not None
    assert resolved_case.resolved_at is not None

    cand_after = repo.get_candidate(cand.candidate_id)
    assert cand_after.processing_status == "APPROVAL_PENDING"


def test_retention_redaction_masks_text_preserves_hashes(governance_env):
    """Verify legal retention redaction masks raw text while preserving non-repudiation hashes."""
    env = governance_env
    repo = env["repo"]
    retention = env["retention"]

    cand = repo.submit_candidate("Sensitive confidential text under GDPR request.", "SRC_CORPUS_01", "doc_08")
    original_raw_hash = cand.raw_content_hash
    original_norm_hash = cand.normalized_content_hash

    # Execute lawful redaction
    retention.redact_raw_text(cand.candidate_id, authorized_by="legal_counsel", legal_basis="GDPR Art. 17")

    updated = repo.get_candidate(cand.candidate_id)
    assert "[REDACTED UNDER LEGAL ORDER]" in updated.original_text
    # Hashes MUST remain unchanged for audit non-repudiation
    assert updated.raw_content_hash == original_raw_hash
    assert updated.normalized_content_hash == original_norm_hash


def test_revocation_invalidates_approval(governance_env):
    """Verify revocation transitions candidate status to REVOKED with signed record."""
    env = governance_env
    repo = env["repo"]
    approvals = env["approvals"]
    revocation = env["revocation"]

    cand = repo.submit_candidate("Initially approved sentence.", "SRC_CORPUS_01", "doc_09")
    advance_to_approval_pending(repo, cand.candidate_id)

    # Approve
    approvals.approve_candidate(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key_record"].public_key_id,
        auth_event_id=env["auth_session"].auth_event_id,
        decision_reason="Approved",
        private_key_pem=env["priv_pem"],
    )
    assert repo.get_candidate(cand.candidate_id).processing_status == "APPROVED"

    # Revoke
    revocation.revoke_approval(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key_record"].public_key_id,
        auth_event_id=env["auth_session"].auth_event_id,
        revocation_reason="Source copyright challenged post-approval",
        private_key_pem=env["priv_pem"],
    )

    assert repo.get_candidate(cand.candidate_id).processing_status == "REVOKED"
