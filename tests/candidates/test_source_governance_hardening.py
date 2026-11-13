"""
Tests for Authoritative Source Governance, Registry Staleness & Preflight Hardening
Phase 4.14.2.1 — Issue 5
"""

import time
from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import GovernancePreflightError
from foundation.corpus.sources import SourceRegistry, CorpusSource, LicensingStatus


def build_test_source(
    source_id: str,
    licensing_status: LicensingStatus = LicensingStatus.VERIFIED_PERMITTED,
    expiration_date: str = "2099-12-31",
    artifact_hash: str = "1" * 64,
) -> CorpusSource:
    return CorpusSource(
        source_id=source_id,
        name=f"Source {source_id}",
        source_type="corpus",
        version="1.0.0",
        url_or_path=f"https://veda.internal/{source_id}",
        acquisition_date="2026-01-01",
        source_hash=artifact_hash,
        artifact_sha256=artifact_hash,
        license="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        licensing_status=licensing_status,
        training_permitted_status="EXPLICITLY_PERMITTED",
        commercial_permitted=True,
        attribution="Governance Hardening Test",
        approval_expiration_date=expiration_date,
        evidence_checksum="2" * 64,
        license_evidence_sha256="2" * 64,
        evidence_retrieval_date="2026-01-01",
        reviewer_identity="curator_test",
        review_date="2026-01-01",
        re_review_triggers="Annual review",
        work_level_scope="Corpus",
    )


@pytest.fixture
def gov_env(tmp_path: Path):
    """Sets up an isolated database and authoritative source registry environment."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    reg_path = tmp_path / "source_registry.json"

    initial_source = build_test_source("src_gov_01")
    reg = SourceRegistry([initial_source])
    reg.to_json(reg_path)

    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        export_service = ExportEligibilityService(db, repo, source_registry_path=reg_path)

        # Cache in DB
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_gov_01",
                name=initial_source.name,
                version=initial_source.version,
                licensing_status="VERIFIED PERMITTED",
                license_name="CC-BY-4.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="1" * 64,
                registry_entry_sha256="2" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        yield {
            "db": db,
            "repo": repo,
            "export_service": export_service,
            "reg_path": reg_path,
        }


def test_source_governance_valid_source_passes(gov_env):
    """Verify that a compliant, non-expired source passes preflight verification."""
    export_service = gov_env["export_service"]
    export_service.verify_source_governance_preflight("src_gov_01")


def test_source_governance_missing_in_registry_raises(gov_env):
    """Verify that a source absent from authoritative registry raises GovernancePreflightError."""
    export_service = gov_env["export_service"]
    with pytest.raises(GovernancePreflightError, match="does not exist in authoritative SourceRegistry"):
        export_service.verify_source_governance_preflight("src_non_existent")


def test_source_governance_expired_source_raises(gov_env):
    """Verify that an expired source approval raises GovernancePreflightError."""
    export_service = gov_env["export_service"]
    reg_path = gov_env["reg_path"]
    repo = gov_env["repo"]

    # Create expired source
    expired_source = build_test_source("src_expired", expiration_date="2020-01-01")
    reg = SourceRegistry([expired_source])
    reg.to_json(reg_path)

    repo.upsert_source(
        CandidateSourceRecord(
            source_id="src_expired",
            name=expired_source.name,
            version=expired_source.version,
            licensing_status="VERIFIED PERMITTED",
            license_name="CC-BY-4.0",
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            artifact_sha256="1" * 64,
            registry_entry_sha256="2" * 64,
            approval_expiration_date="2020-01-01",
        )
    )

    with pytest.raises(GovernancePreflightError, match="approval expired on 2020-01-01"):
        export_service.verify_source_governance_preflight("src_expired")


def test_source_governance_staleness_and_cache_reload(gov_env):
    """Verify that modifying the source_registry.json on disk triggers cache invalidation."""
    export_service = gov_env["export_service"]
    reg_path = gov_env["reg_path"]

    # Initial check passes
    export_service.verify_source_governance_preflight("src_gov_01")

    # Update source on disk to REQUIRES_REVIEW licensing
    time.sleep(0.05)  # Ensure mtime changes
    modified_source = build_test_source("src_gov_01", licensing_status=LicensingStatus.REQUIRES_REVIEW)
    reg = SourceRegistry([modified_source])
    reg.to_json(reg_path)

    # Next call should reload the file and detect the licensing downgrade
    with pytest.raises(GovernancePreflightError, match="must be VERIFIED PERMITTED"):
        export_service.verify_source_governance_preflight("src_gov_01")


def test_source_governance_hash_mismatch_detected(gov_env):
    """Verify that artifact SHA-256 discrepancy between DB cache and registry is rejected."""
    export_service = gov_env["export_service"]
    repo = gov_env["repo"]

    # Corrupt DB cache artifact hash
    repo.upsert_source(
        CandidateSourceRecord(
            source_id="src_gov_01",
            name="Source src_gov_01",
            version="1.0.0",
            licensing_status="VERIFIED PERMITTED",
            license_name="CC-BY-4.0",
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            artifact_sha256="9" * 64,  # Mismatched hash
            registry_entry_sha256="2" * 64,
            approval_expiration_date="2099-12-31",
        )
    )

    with pytest.raises(GovernancePreflightError, match="artifact SHA-256 mismatch"):
        export_service.verify_source_governance_preflight("src_gov_01")
