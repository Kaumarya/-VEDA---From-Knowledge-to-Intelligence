"""
Focused Adversarial Tests for Export Gate Content-Hash Binding & Source Registry Integrity
Phase 4.14.2.1.2 — Issue 1 & Issue 7
"""

import json
import os
import hashlib
from pathlib import Path
from dataclasses import replace
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.candidates.signatures import Ed25519SignatureService, compute_payload_hash
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import ExportEligibilityError, GovernancePreflightError
from foundation.corpus.sources import SourceRegistry, CorpusSource, LicensingStatus


@pytest.fixture
def export_gate_env(tmp_path: Path):
    """Sets up an isolated database and authoritative source registry environment."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    reg_path = tmp_path / "source_registry.json"

    source_id = "src_export_harden_01"
    art_hash = "3" * 64
    auth_source = CorpusSource(
        source_id=source_id,
        name="Export Hardening Source",
        source_type="corpus",
        version="1.0.0",
        url_or_path="https://veda.internal/sources/harden01",
        acquisition_date="2026-01-01",
        source_hash=art_hash,
        artifact_sha256=art_hash,
        license="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        training_permitted_status="EXPLICITLY_PERMITTED",
        commercial_permitted=True,
        attribution="VEDA Hardening",
        approval_expiration_date="2099-12-31",
        evidence_checksum="4" * 64,
        license_evidence_sha256="4" * 64,
        evidence_retrieval_date="2026-01-01",
        reviewer_identity="curator_harden",
        review_date="2026-01-01",
        re_review_triggers="Annual audit",
        work_level_scope="Corpus",
    )
    registry = SourceRegistry([auth_source])
    registry.to_json(reg_path)

    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        approvals = ApprovalService(db, repo, reviewers)
        export_service = ExportEligibilityService(db, repo, source_registry_path=reg_path)
        authenticator = LocalSecureAuthenticator()

        # Seed source in DB
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
                registry_entry_sha256="4" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        curator = reviewers.create_reviewer("curator_harden", "Harden Curator", "curator@harden.internal")
        reviewers.assign_role(curator.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")

        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        key_record = reviewers.register_public_key(curator.reviewer_id, pub_hex, is_test_key=False)
        reviewers.activate_public_key(key_record.public_key_id, actor_id="admin")

        auth_session = authenticator.create_session(curator.reviewer_id)
        reviewers.record_authentication_event(auth_session)

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "approvals": approvals,
            "export_service": export_service,
            "curator": curator,
            "key": key_record,
            "priv_pem": priv_pem,
            "pub_hex": pub_hex,
            "session": auth_session,
            "source_id": source_id,
            "reg_path": reg_path,
            "art_hash": art_hash,
        }


def create_approved_candidate(env, text="The primary hypothesis was thoroughly confirmed by empirical evidence."):
    repo = env["repo"]
    approvals = env["approvals"]
    cand = repo.submit_candidate(
        original_text=text,
        source_id=env["source_id"],
        source_document_id="doc_tamper_001",
    )
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")
    approvals.approve_candidate(
        candidate_id=cand.candidate_id,
        reviewer_id=env["curator"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["key"].public_key_id,
        auth_event_id=env["session"].auth_event_id,
        decision_reason="Fully verified candidate content.",
        private_key_pem=env["priv_pem"],
    )
    return cand


def test_legitimate_approved_candidate_passes_export_gate(export_gate_env):
    env = export_gate_env
    cand = create_approved_candidate(env)
    assert env["export_service"].check_candidate_eligibility(cand.candidate_id) is True


def test_tamper_normalized_text_only_rejected(export_gate_env):
    """If normalized_text is altered directly in candidate_submissions, export gate must reject."""
    env = export_gate_env
    cand = create_approved_candidate(env)
    db = env["db"]

    with db.transaction() as c:
        c.execute(
            "UPDATE candidate_submissions SET normalized_text = 'Tampered text.' WHERE candidate_id = ?;",
            (cand.candidate_id,),
        )

    with pytest.raises(ExportEligibilityError, match="tampering detected"):
        env["export_service"].check_candidate_eligibility(cand.candidate_id)


def test_tamper_normalized_hash_only_rejected(export_gate_env):
    """If normalized_content_hash is altered directly in SQLite, export gate must reject."""
    env = export_gate_env
    cand = create_approved_candidate(env)
    db = env["db"]

    bogus_hash = "f" * 64
    with db.transaction() as c:
        c.execute(
            "UPDATE candidate_submissions SET normalized_content_hash = ? WHERE candidate_id = ?;",
            (bogus_hash, cand.candidate_id),
        )

    with pytest.raises(ExportEligibilityError, match="tampering detected"):
        env["export_service"].check_candidate_eligibility(cand.candidate_id)


def test_tamper_both_text_and_hash_rejected_by_payload_coupling(export_gate_env):
    """
    If an attacker alters BOTH normalized_text and normalized_content_hash in SQLite
    so they match each other, export gate must reject because hash does not match signed payload!
    """
    env = export_gate_env
    cand = create_approved_candidate(env)
    db = env["db"]

    new_text = "Completely swapped malicious sentence replacing the approved text."
    new_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

    with db.transaction() as c:
        c.execute(
            "UPDATE candidate_submissions SET normalized_text = ?, normalized_content_hash = ? WHERE candidate_id = ?;",
            (new_text, new_hash, cand.candidate_id),
        )

    with pytest.raises(ExportEligibilityError, match="decoupling detected"):
        env["export_service"].check_candidate_eligibility(cand.candidate_id)


def test_tamper_original_raw_text_rejected(export_gate_env):
    """If original_text is altered while raw_content_hash is bound, export gate must reject."""
    env = export_gate_env
    cand = create_approved_candidate(env)
    db = env["db"]

    with db.transaction() as c:
        c.execute(
            "UPDATE candidate_submissions SET original_text = 'Altered original prose.' WHERE candidate_id = ?;",
            (cand.candidate_id,),
        )

    with pytest.raises(ExportEligibilityError, match="raw content tampering detected"):
        env["export_service"].check_candidate_eligibility(cand.candidate_id)


def test_source_artifact_mismatch_against_signed_payload_rejected(export_gate_env):
    """If authoritative source artifact hash changes after approval, export gate must reject."""
    env = export_gate_env
    cand = create_approved_candidate(env)

    # Change artifact hash in authoritative source registry
    reg = SourceRegistry.load_from_json(env["reg_path"])
    updated_sources = [replace(reg.sources[0], artifact_sha256="9" * 64)]
    SourceRegistry(updated_sources).to_json(env["reg_path"])

    with pytest.raises(GovernancePreflightError):
        env["export_service"].check_candidate_eligibility(cand.candidate_id)


def test_source_registry_content_hash_cache_detects_same_mtime_spoofing(export_gate_env):
    """
    Attacker edits source registry but restores st_mtime.
    ExportEligibilityService must detect content hash mismatch and reload.
    """
    env = export_gate_env
    export_svc = env["export_service"]
    reg_path = env["reg_path"]

    # Initial load populates cache
    reg1 = export_svc._get_authoritative_registry()
    assert reg1.sources[0].licensing_status == LicensingStatus.VERIFIED_PERMITTED

    # Record mtime
    orig_mtime = reg_path.stat().st_mtime

    # Attacker alters file to revoke permission
    reg = SourceRegistry.load_from_json(reg_path)
    updated_sources = [replace(reg.sources[0], licensing_status=LicensingStatus.EXCLUDED)]
    SourceRegistry(updated_sources).to_json(reg_path)

    # Attacker restores previous mtime via os.utime
    os.utime(reg_path, (orig_mtime, orig_mtime))

    # Verification: export service must detect SHA-256 change despite same mtime
    reg2 = export_svc._get_authoritative_registry()
    assert reg2.sources[0].licensing_status == LicensingStatus.EXCLUDED


def test_source_registry_malformed_json_raises_governance_preflight(export_gate_env):
    """Malformed JSON in source registry raises controlled GovernancePreflightError, not unhandled JSONDecodeError."""
    env = export_gate_env
    export_svc = env["export_service"]
    reg_path = env["reg_path"]

    reg_path.write_text("{malformed: json", encoding="utf-8")

    with pytest.raises(GovernancePreflightError, match="Failed to parse source registry"):
        export_svc._get_authoritative_registry()
