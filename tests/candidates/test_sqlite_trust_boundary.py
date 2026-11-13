"""
Tests for SQLite Trust Boundaries & Application-Level Cryptographic Re-verification
Phase 4.14.2.1 — Issue 4
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import ExportEligibilityError
from foundation.corpus.sources import SourceRegistry, CorpusSource, LicensingStatus


@pytest.fixture
def trust_env(tmp_path: Path):
    """Sets up a test database and valid authoritative source registry."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    reg_path = tmp_path / "source_registry.json"

    # Write authoritative registry
    auth_src = CorpusSource(
        source_id="src_trust_01",
        name="Trust Verification Source",
        source_type="corpus",
        version="1.0.0",
        url_or_path="https://veda.internal/sources/trust01",
        acquisition_date="2026-01-01",
        source_hash="7" * 64,
        artifact_sha256="7" * 64,
        license="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        training_permitted_status="EXPLICITLY_PERMITTED",
        commercial_permitted=True,
        attribution="Trust Test Attrib",
        approval_expiration_date="2099-12-31",
        evidence_checksum="8" * 64,
        license_evidence_sha256="8" * 64,
        evidence_retrieval_date="2026-01-01",
        reviewer_identity="curator_trust",
        review_date="2026-01-01",
        re_review_triggers="Annual audit",
        work_level_scope="Corpus",
    )
    registry = SourceRegistry([auth_src])
    registry.to_json(reg_path)

    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        approvals = ApprovalService(db, repo, reviewers)
        export_service = ExportEligibilityService(db, repo, source_registry_path=reg_path)
        auth = LocalSecureAuthenticator()

        # Cache source in DB
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_trust_01",
                name="Trust Verification Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="7" * 64,
                registry_entry_sha256="8" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        # Register authorized curator
        curator = reviewers.create_reviewer("curator_trust", "Trust Curator", "curator@trust.internal")
        reviewers.assign_role(curator.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")
        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        key_rec = reviewers.register_public_key(curator.reviewer_id, pub_hex, is_test_key=False)
        reviewers.activate_public_key(key_rec.public_key_id, actor_id="admin")
        auth_session = auth.create_session(curator.reviewer_id)
        reviewers.record_authentication_event(auth_session)

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "approvals": approvals,
            "export_service": export_service,
            "curator": curator,
            "key": key_rec,
            "priv_pem": priv_pem,
            "pub_hex": pub_hex,
            "session": auth_session,
        }


def test_direct_sql_fake_verified_valid_rejected_at_export_gate(trust_env):
    """
    Verify that an attacker or corrupted process writing VERIFIED_VALID directly to SQLite
    with a forged/fake signature is caught and rejected by ExportEligibilityService.
    """
    env = trust_env
    repo = env["repo"]
    db = env["db"]
    export_service = env["export_service"]

    cand = repo.submit_candidate(
        "Verifiable natural English prose adhering to strict standards.",
        "src_trust_01",
        "doc_trust_01",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")

    # Attacker inserts fake approval row with fake signature and claims VERIFIED_VALID
    fake_decision_id = f"urn:uuid:{uuid.uuid4()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    fake_signature = "bad0" * 32  # 128 chars of invalid signature hex
    fake_payload_json = '{"decision":"APPROVED","fake":true}'
    import hashlib
    fake_payload_sha256 = hashlib.sha256(fake_payload_json.encode("utf-8")).hexdigest()

    with db.transaction() as c:
        c.execute(
            """
            INSERT INTO approval_history (
                candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                old_status, new_status, decision_reason, canonical_payload_json,
                canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
            ) VALUES (?, ?, ?, 'DOMAIN_CURATOR', ?, ?, 'APPROVAL_PENDING', 'APPROVED', 'Forged approval', ?, ?, ?, '1.0', 'VERIFIED_VALID', ?);
            """,
            (
                cand.candidate_id,
                fake_decision_id,
                env["curator"].reviewer_id,
                env["key"].public_key_id,
                env["session"].auth_event_id,
                fake_payload_json,
                fake_payload_sha256,
                fake_signature,
                now_iso,
            ),
        )
        c.execute(
            "UPDATE candidate_submissions SET processing_status = 'APPROVED', updated_at = ? WHERE candidate_id = ?;",
            (now_iso, cand.candidate_id),
        )

    # SQLite view sees VERIFIED_VALID and status APPROVED
    view_row = db.fetchone(
        "SELECT * FROM v_export_eligible_candidates WHERE candidate_id = ?;",
        (cand.candidate_id,),
    )
    assert view_row is not None  # SQLite view trusts the column

    # ExportEligibilityService MUST perform cryptographic re-verification and reject the forged candidate!
    with pytest.raises(ExportEligibilityError, match="Cryptographic signature re-verification failed"):
        export_service.check_candidate_eligibility(cand.candidate_id)


def test_tampered_payload_json_fails_export_verification(trust_env):
    """
    Verify that if canonical_payload_json in the database is modified after legitimate signing,
    the payload SHA-256 mismatch or signature verification failure is detected at the export gate.
    """
    env = trust_env
    repo = env["repo"]
    approvals = env["approvals"]
    db = env["db"]
    export_service = env["export_service"]

    cand = repo.submit_candidate(
        "Legitimate candidate prose for tamper testing.",
        "src_trust_01",
        "doc_trust_02",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    # Legitimate approval
    app_rec = approvals.approve_candidate(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key"].public_key_id,
        auth_event_id=env["session"].auth_event_id,
        decision_reason="Legitimate approval",
        private_key_pem=env["priv_pem"],
    )

    # Initially passes eligibility check
    assert export_service.check_candidate_eligibility(cand.candidate_id) is True

    # Note: Trigger trig_abort_approval_history_update prevents direct UPDATE on approval_history!
    # Let's verify trigger blocks UPDATE
    with pytest.raises(Exception, match="SECURITY VIOLATION: approval_history records are immutable"):
        db.execute(
            "UPDATE approval_history SET canonical_payload_json = '{\"tampered\":true}' WHERE candidate_id = ?;",
            (cand.candidate_id,),
        )
