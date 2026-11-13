"""
Tests for Centralized Export Eligibility & Release-Scoped Export Batches
Phase 4.14.2 — Stage 5
Enforces 18-point fail-closed predicate, authoritative SourceRegistry preflight, and idempotency.
"""

import sqlite3
import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.retention import RetentionManager
from foundation.candidates.revocation import RevocationManager
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.candidates.models import CandidateSourceRecord, DuplicateRelationshipRecord
from foundation.candidates.exceptions import (
    ExportEligibilityError,
    GovernancePreflightError,
    DuplicateExportError,
    ValidationError,
)
from foundation.corpus.schemas import CorpusSource, LicensingStatus
from foundation.corpus.sources import SourceRegistry


@pytest.fixture
def export_env(tmp_path: Path):
    """Sets up an isolated database and authoritative source registry environment for export testing."""
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

        # 1. Authoritative Source Registry
        source_id = "src_export_test_01"
        art_hash = "a" * 64
        auth_source = CorpusSource(
            source_id=source_id,
            name="Official Test Ingestion Source",
            source_type="corpus",
            version="1.0.0",
            url_or_path="https://veda.internal/sources/test01",
            acquisition_date="2026-01-01",
            source_hash=art_hash,
            artifact_sha256=art_hash,
            license="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            attribution="VEDA Testing Foundation",
            approval_expiration_date="2099-12-31",
            evidence_checksum="b" * 64,
            license_evidence_sha256="b" * 64,
            evidence_retrieval_date="2026-01-01",
            reviewer_identity="curator_jane",
            review_date="2026-01-01",
            re_review_triggers="Annual audit",
            work_level_scope="Corpus",
        )
        reg = SourceRegistry([auth_source])
        registry_path = tmp_path / "source_registry.json"
        reg.to_json(registry_path)

        # 2. Seed database source cache matching authoritative registry
        repo.upsert_source(
            CandidateSourceRecord(
                source_id=source_id,
                name=auth_source.name,
                version=auth_source.version,
                licensing_status="VERIFIED PERMITTED",
                license_name=auth_source.license,
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256=art_hash,
                registry_entry_sha256="c" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        # 3. Register human reviewer with ROLE_DOMAIN_CURATOR
        curator = reviewers.create_reviewer("curator_jane", "Jane Doe", "jane@veda.internal")
        reviewers.assign_role(curator.reviewer_id, "ROLE_DOMAIN_CURATOR", assigned_by="admin")

        # 4. Generate and activate production key pair (is_test_key=False)
        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        key_record = reviewers.register_public_key(curator.reviewer_id, pub_hex, is_test_key=False)
        reviewers.activate_public_key(key_record.public_key_id, actor_id="admin")

        # 5. Create active auth session
        auth_session = authenticator.create_session(curator.reviewer_id)
        reviewers.record_authentication_event(auth_session)

        # 6. Initialize ExportEligibilityService
        export_service = ExportEligibilityService(
            connection=db,
            repository=repo,
            source_registry_path=registry_path,
        )

        yield {
            "tmp_path": tmp_path,
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "authenticator": authenticator,
            "approvals": approvals,
            "quarantine": quarantine,
            "retention": retention,
            "revocation": revocation,
            "export_service": export_service,
            "curator": curator,
            "priv_pem": priv_pem,
            "pub_hex": pub_hex,
            "key_record": key_record,
            "auth_session": auth_session,
            "source_id": source_id,
            "registry_path": registry_path,
            "auth_source": auth_source,
        }


def advance_and_approve(env, text: str = "A valid sentence for training corpus export.") -> str:
    """Helper to submit, advance to APPROVAL_PENDING, and sign human approval."""
    repo = env["repo"]
    approvals = env["approvals"]
    cand = repo.submit_candidate(
        original_text=text,
        source_id=env["source_id"],
        source_document_id="doc_001",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")
    approvals.approve_candidate(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key_record"].public_key_id,
        auth_event_id=env["auth_session"].auth_event_id,
        decision_reason="Passed human export review",
        private_key_pem=env["priv_pem"],
    )
    return cand.candidate_id


def test_fully_eligible_candidate_passes_view_and_check(export_env):
    """Verify that an approved, signed, canonical candidate passes 18-point view and preflight."""
    cand_id = advance_and_approve(export_env)
    export_service = export_env["export_service"]

    # 1. Direct eligibility check
    assert export_service.check_candidate_eligibility(cand_id, verify_source=True) is True

    # 2. Listed in view query
    eligible = export_service.list_eligible_candidates()
    assert len(eligible) == 1
    assert eligible[0]["candidate_id"] == cand_id
    assert eligible[0]["approval_signature"] is not None


def test_ineligible_unapproved_candidate_rejected(export_env):
    """Verify that a candidate in APPROVAL_PENDING (unapproved) is rejected by export eligibility."""
    repo = export_env["repo"]
    cand = repo.submit_candidate(
        original_text="Sentence pending approval.",
        source_id=export_env["source_id"],
        source_document_id="doc_001",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="must be 'APPROVED'"):
        export_service.check_candidate_eligibility(cand.candidate_id)

    assert len(export_service.list_eligible_candidates()) == 0


def test_test_key_signed_candidate_rejected_from_approval_and_export(export_env):
    """Verify that approvals signed with test keys are rejected at trigger level and excluded by view."""
    repo = export_env["repo"]
    reviewers = export_env["reviewers"]
    approvals = export_env["approvals"]
    curator = export_env["curator"]

    # Register a key marked is_test_key=True
    priv_test_pem, pub_test_hex = Ed25519SignatureService.generate_key_pair()
    test_key = reviewers.register_public_key(curator.reviewer_id, pub_test_hex, is_test_key=True)
    reviewers.activate_public_key(test_key.public_key_id, actor_id="admin")

    cand = repo.submit_candidate(
        original_text="Text to be tested with test key.",
        source_id=export_env["source_id"],
        source_document_id="doc_001",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    # Attempting to approve with test key fails closed (trigger trig_enforce_signed_approval_mutation)
    with pytest.raises(sqlite3.IntegrityError, match="SECURITY VIOLATION"):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=curator.reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=test_key.public_key_id,
            auth_event_id=export_env["auth_session"].auth_event_id,
            decision_reason="Attempt approval with test key",
            private_key_pem=priv_test_pem,
        )


def test_non_canonical_duplicate_candidate_rejected(export_env):
    """Verify that a non-canonical duplicate is rejected from export eligibility."""
    repo = export_env["repo"]
    cand1_id = advance_and_approve(export_env, text="Canonical version of the text.")

    # Second submission with same text -> marked is_canonical=False
    cand2 = repo.submit_candidate(
        original_text="Canonical version of the text.",
        source_id=export_env["source_id"],
        source_document_id="doc_002",
    )
    assert cand2.is_canonical is False

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="non-canonical duplicate"):
        export_service.check_candidate_eligibility(cand2.candidate_id)


def test_unresolved_quarantine_candidate_rejected(export_env):
    """Verify that an active quarantine case blocks export eligibility."""
    cand_id = advance_and_approve(export_env, text="Quarantined test sentence.")
    
    # Open quarantine case
    export_env["db"].execute(
        """
        INSERT INTO quarantine_cases (
            case_id, candidate_id, quarantine_reason, quarantine_category, diagnostic_evidence_json,
            pipeline_version, review_due_at, assigned_role
        ) VALUES ('case_export_q', ?, 'SEMANTIC_SAFETY_CONFLICT', 'SAFETY', '{}', '1.0.0', '2099-01-01', 'ROLE_DOMAIN_CURATOR');
        """,
        (cand_id,),
    )

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="unresolved quarantine case"):
        export_service.check_candidate_eligibility(cand_id)


def test_semantic_conflict_duplicate_rejected(export_env):
    """Verify that a candidate involved in an unsafe semantic conflict is excluded from export."""
    cand1_id = advance_and_approve(export_env, text="First statement in conflict.")
    cand2 = export_env["repo"].submit_candidate(
        original_text="Second conflicting statement.",
        source_id=export_env["source_id"],
        source_document_id="doc_002",
    )

    # Insert unsafe duplicate relationship
    export_env["repo"].record_duplicate_relationship(
        DuplicateRelationshipRecord(
            candidate_id=cand1_id,
            related_candidate_id=cand2.candidate_id,
            relationship_type="SEMANTIC_CONFLICT",
            detector_version="1.0.0",
            similarity_score=0.95,
            is_safe_to_merge=False,
            conflict_reason="NEGATION_INVERSION",
        )
    )

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="failed export eligibility predicate"):
        export_service.check_candidate_eligibility(cand1_id)


def test_retention_dispute_blocks_export(export_env):
    """Verify that a legal retention dispute blocks export eligibility."""
    cand_id = advance_and_approve(export_env, text="Sentence under dispute.")
    retention = export_env["retention"]

    retention.record_decision(
        candidate_id=cand_id,
        decision_type="RESTRICT_ACCESS_DISPUTE",
        legal_basis="DMCA Notice 123",
        governance_notes="Access restricted pending resolution",
        authorized_by="legal_counsel_01",
    )

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="failed export eligibility predicate"):
        export_service.check_candidate_eligibility(cand_id)


def test_revocation_invalidates_export_eligibility(export_env):
    """Verify that revoking an approved candidate makes it ineligible for export."""
    cand_id = advance_and_approve(export_env, text="Sentence to be revoked.")
    revocation = export_env["revocation"]

    revocation.revoke_approval(
        candidate_id=cand_id,
        reviewer_id=export_env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=export_env["key_record"].public_key_id,
        auth_event_id=export_env["auth_session"].auth_event_id,
        revocation_reason="New safety violation detected post-approval",
        private_key_pem=export_env["priv_pem"],
    )

    export_service = export_env["export_service"]
    with pytest.raises(ExportEligibilityError, match="must be 'APPROVED'"):
        export_service.check_candidate_eligibility(cand_id)


def test_source_governance_preflight_checks(export_env):
    """Verify authoritative SourceRegistry preflight catches unregistered, unpermitted, or tampered sources."""
    cand_id = advance_and_approve(export_env)
    export_service = export_env["export_service"]
    registry_path = export_env["registry_path"]
    auth_source = export_env["auth_source"]

    # 1. Normal preflight passes
    export_service.verify_source_governance_preflight(export_env["source_id"])

    # 2. Source missing in authoritative registry
    empty_reg = SourceRegistry([])
    empty_reg.to_json(registry_path)
    export_service._cached_registry = None  # Clear cache
    with pytest.raises(GovernancePreflightError, match="does not exist in authoritative SourceRegistry"):
        export_service.verify_source_governance_preflight(export_env["source_id"])

    # 3. Source licensing not VERIFIED_PERMITTED in authoritative registry
    dict_copy = auth_source.to_dict()
    dict_copy["licensing_status"] = LicensingStatus.REQUIRES_REVIEW
    unpermitted_source = CorpusSource.from_dict(dict_copy)
    SourceRegistry([unpermitted_source]).to_json(registry_path)
    export_service._cached_registry = None
    with pytest.raises(GovernancePreflightError, match="must be VERIFIED PERMITTED"):
        export_service.verify_source_governance_preflight(export_env["source_id"])

    # 4. Artifact SHA-256 mismatch between DB cache and registry
    dict_copy2 = auth_source.to_dict()
    dict_copy2["artifact_sha256"] = "f" * 64
    dict_copy2["source_hash"] = "f" * 64
    tampered_source = CorpusSource.from_dict(dict_copy2)
    SourceRegistry([tampered_source]).to_json(registry_path)
    export_service._cached_registry = None
    with pytest.raises(GovernancePreflightError, match="SHA-256 mismatch"):
        export_service.verify_source_governance_preflight(export_env["source_id"])


def test_export_batch_lifecycle_and_release_idempotency(export_env):
    """Verify export batch lifecycle and release-scoped idempotency."""
    export_service = export_env["export_service"]
    cand1_id = advance_and_approve(export_env, text="Candidate one for batch.")
    cand2_id = advance_and_approve(export_env, text="Candidate two for batch.")

    # 1. Create batch
    batch1 = export_service.create_export_batch(corpus_version="v0.1.0", target_split="train")
    assert batch1.export_status == "PREPARING"
    assert batch1.record_count == 0

    # 2. Add candidates to batch
    export_service.add_candidate_to_batch(batch1.batch_id, cand1_id)
    export_service.add_candidate_to_batch(batch1.batch_id, cand2_id)

    updated_batch1 = export_service.get_export_batch(batch1.batch_id)
    assert updated_batch1.record_count == 2

    # 3. Idempotency: cannot add cand1_id to the same batch again
    with pytest.raises(DuplicateExportError, match="already exported to release 'v0.1.0' split 'train'"):
        export_service.add_candidate_to_batch(batch1.batch_id, cand1_id)

    # 4. Idempotency: cannot add cand1_id to ANOTHER batch for the SAME release and split
    batch2 = export_service.create_export_batch(corpus_version="v0.1.0", target_split="train")
    with pytest.raises(DuplicateExportError, match="already exported to release 'v0.1.0' split 'train'"):
        export_service.add_candidate_to_batch(batch2.batch_id, cand1_id)

    # 5. Adding to DIFFERENT split in same release is permitted
    dev_batch = export_service.create_export_batch(corpus_version="v0.1.0", target_split="dev")
    export_service.add_candidate_to_batch(dev_batch.batch_id, cand1_id)
    assert export_service.get_export_batch(dev_batch.batch_id).record_count == 1

    # 6. Adding to DIFFERENT release version is permitted
    v2_batch = export_service.create_export_batch(corpus_version="v0.2.0", target_split="train")
    export_service.add_candidate_to_batch(v2_batch.batch_id, cand1_id)
    assert export_service.get_export_batch(v2_batch.batch_id).record_count == 1

    # 7. Commit batch
    committed = export_service.commit_export_batch(
        batch_id=batch1.batch_id,
        manifest_sha256="m" * 64,
        output_path="data/corpus/train_v0.1.0.jsonl",
    )
    assert committed.export_status == "COMMITTED"
    assert committed.manifest_sha256 == "m" * 64
    assert committed.committed_at is not None

    # 8. Cannot add items to committed batch
    with pytest.raises(ValidationError, match="cannot add items"):
        export_service.add_candidate_to_batch(batch1.batch_id, cand1_id)


def test_export_batch_crash_recovery(export_env):
    """Verify that a failed export batch allows candidate to be recovered and re-exported."""
    export_service = export_env["export_service"]
    cand_id = advance_and_approve(export_env, text="Candidate for crash recovery test.")

    batch = export_service.create_export_batch(corpus_version="v0.1.0", target_split="train")
    export_service.add_candidate_to_batch(batch.batch_id, cand_id)

    # Simulate failure during batch processing
    export_service.fail_export_batch(batch.batch_id)
    failed_batch = export_service.get_export_batch(batch.batch_id)
    assert failed_batch.export_status == "FAILED"

    # Because prior batch failed, candidate can now be exported to a new batch for that split
    recovery_batch = export_service.create_export_batch(corpus_version="v0.1.0", target_split="train")
    export_service.add_candidate_to_batch(recovery_batch.batch_id, cand_id)
    assert export_service.get_export_batch(recovery_batch.batch_id).record_count == 1
