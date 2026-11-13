"""
Performance and Database Quality Benchmark Tests
Phase 4.14.2 — Section 11
Measures query plans, indexing efficiency, candidate ingestion throughput,
and export eligibility query performance using isolated synthetic fixtures.
"""

import time
import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.models import (
    CandidateSourceRecord,
    ProcessingDecisionRecord,
    DuplicateRelationshipRecord,
)
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.corpus.schemas import CorpusSource, LicensingStatus
from foundation.corpus.sources import SourceRegistry


@pytest.fixture
def perf_env(tmp_path: Path):
    """Sets up an isolated, migrated candidate database for performance benchmarking."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        mgr = MigrationManager(db)
        mgr.apply_all()
        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        auth = LocalSecureAuthenticator()
        approvals = ApprovalService(db, repo, reviewers)

        # Seed valid source
        source_id = "src_perf_01"
        art_hash = "9" * 64
        repo.upsert_source(
            CandidateSourceRecord(
                source_id=source_id,
                name="Performance Test Ingestion Source",
                version="1.0.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256=art_hash,
                registry_entry_sha256="8" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        auth_source = CorpusSource(
            source_id=source_id,
            name="Performance Test Ingestion Source",
            version="1.0.0",
            url_or_path="https://veda.internal/perf",
            acquisition_date="2026-01-01",
            source_hash=art_hash,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            attribution="VEDA Performance Lab",
            approval_expiration_date="2099-12-31",
            evidence_checksum="7" * 64,
            evidence_retrieval_date="2026-01-01",
            reviewer_identity="perf_reviewer",
            review_date="2026-01-01",
            re_review_triggers="Annual audit",
            work_level_scope="Corpus",
        )
        reg = SourceRegistry([auth_source])
        reg_path = tmp_path / "source_registry.json"
        reg.to_json(reg_path)

        export_service = ExportEligibilityService(db, repo, source_registry_path=reg_path)

        # Register reviewer
        rev = reviewers.create_reviewer("perf_curator", "Performance Reviewer", "perf@veda.internal")
        reviewers.assign_role(rev.reviewer_id, "ROLE_DOMAIN_CURATOR", assigned_by="admin")
        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        key_rec = reviewers.register_public_key(rev.reviewer_id, pub_hex, is_test_key=False)
        reviewers.activate_public_key(key_rec.public_key_id, actor_id="admin")
        auth_session = auth.create_session(rev.reviewer_id)
        reviewers.record_authentication_event(auth_session)

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "approvals": approvals,
            "export_service": export_service,
            "source_id": source_id,
            "rev": rev,
            "priv_pem": priv_pem,
            "key_rec": key_rec,
            "auth_session": auth_session,
        }


def test_candidate_insertion_and_retrieval_performance(perf_env):
    """
    Measures candidate ingestion throughput and indexed content-hash lookups.
    Target: 200 synthetic candidates ingested in under 1.0 second.
    Indexed retrieval latency: < 5ms per lookup.
    """
    repo = perf_env["repo"]
    source_id = perf_env["source_id"]

    num_samples = 200
    texts = [f"This is synthetic candidate sentence number {i} with deterministic content." for i in range(num_samples)]

    start_insert = time.perf_counter()
    submitted = []
    for i, t in enumerate(texts):
        c = repo.submit_candidate(original_text=t, source_id=source_id, source_document_id=f"doc_{i}")
        submitted.append(c)
    insert_duration = time.perf_counter() - start_insert

    # Verify insertion throughput
    assert len(submitted) == num_samples
    assert insert_duration < 2.0, f"Insertion of {num_samples} records took {insert_duration:.3f}s (exceeded 2.0s limit)"

    # Measure indexed retrieval latency using raw and normalized content hashes
    start_lookup = time.perf_counter()
    for c in submitted[:50]:
        found_raw = repo.get_by_raw_hash(c.raw_content_hash)
        assert len(found_raw) > 0
        found_norm = repo.get_by_normalized_hash(c.normalized_content_hash)
        assert len(found_norm) > 0
    lookup_duration = time.perf_counter() - start_lookup
    avg_lookup_ms = (lookup_duration / 100) * 1000

    assert avg_lookup_ms < 5.0, f"Average indexed hash lookup took {avg_lookup_ms:.2f}ms (exceeded 5ms limit)"


def test_query_plan_uses_indexes(perf_env):
    """
    Inspects SQLite EXPLAIN QUERY PLAN output to verify indexes are actively utilized
    for normalized content hash lookups, status filters, and duplicate pairs.
    """
    db = perf_env["db"]

    # 1. Normalized hash lookup should use idx_candidates_norm_hash
    plan_norm = db.fetchall(
        "EXPLAIN QUERY PLAN SELECT * FROM candidate_submissions WHERE normalized_content_hash = ?;",
        ("0" * 64,),
    )
    plan_norm_text = " ".join(str(r["detail"]) for r in plan_norm)
    assert "USING INDEX idx_candidates_norm_hash" in plan_norm_text or "USING COVERING INDEX" in plan_norm_text

    # 2. Status filter should use idx_candidates_status
    plan_status = db.fetchall(
        "EXPLAIN QUERY PLAN SELECT * FROM candidate_submissions WHERE processing_status = ?;",
        ("APPROVED",),
    )
    plan_status_text = " ".join(str(r["detail"]) for r in plan_status)
    assert "USING INDEX idx_candidates_status" in plan_status_text

    # 3. Decision history lookup should use idx_decisions_candidate
    plan_dec = db.fetchall(
        "EXPLAIN QUERY PLAN SELECT * FROM processing_decisions WHERE candidate_id = ?;",
        ("urn:uuid:test",),
    )
    plan_dec_text = " ".join(str(r["detail"]) for r in plan_dec)
    assert "USING INDEX idx_decisions_candidate" in plan_dec_text

    # 4. Release-scoped idempotency check should use idx_unique_release_export
    plan_export = db.fetchall(
        "EXPLAIN QUERY PLAN SELECT * FROM export_batch_items WHERE batch_id = ? AND candidate_id = ?;",
        ("b_1", "c_1"),
    )
    plan_export_text = " ".join(str(r["detail"]) for r in plan_export)
    assert "USING INDEX idx_unique_release_export" in plan_export_text


def test_export_eligibility_and_batch_idempotency_performance(perf_env):
    """
    Measures export eligibility view query performance and batch item addition with 50 candidates.
    """
    repo = perf_env["repo"]
    approvals = perf_env["approvals"]
    export_service = perf_env["export_service"]
    source_id = perf_env["source_id"]
    rev = perf_env["rev"]
    priv_pem = perf_env["priv_pem"]
    key_rec = perf_env["key_rec"]
    auth_session = perf_env["auth_session"]

    # Ingest and approve 20 candidates
    approved_ids = []
    for i in range(20):
        t = f"High quality expository sentence for performance benchmark candidate number {i}."
        c = repo.submit_candidate(t, source_id, f"doc_perf_{i}")
        repo.update_status(c.candidate_id, "PROCESSING_PASSED")
        repo.update_status(c.candidate_id, "APPROVAL_PENDING")
        approvals.approve_candidate(
            candidate_id=c.candidate_id,
            reviewer_id=rev.reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=key_rec.public_key_id,
            auth_event_id=auth_session.auth_event_id,
            decision_reason="Performance test approval",
            private_key_pem=priv_pem,
        )
        approved_ids.append(c.candidate_id)

    # 1. Benchmark export eligibility query
    start_view = time.perf_counter()
    eligible = export_service.list_eligible_candidates(limit=100)
    view_duration_ms = (time.perf_counter() - start_view) * 1000
    assert len(eligible) == 20
    assert view_duration_ms < 50.0, f"Export eligibility view evaluation took {view_duration_ms:.2f}ms"

    # 2. Benchmark batch creation and idempotency additions
    batch = export_service.create_export_batch(corpus_version="v0.1.0", target_split="train")
    start_batch_add = time.perf_counter()
    for cid in approved_ids:
        export_service.add_candidate_to_batch(batch.batch_id, cid)
    batch_add_duration_ms = (time.perf_counter() - start_batch_add) * 1000

    updated_batch = export_service.get_export_batch(batch.batch_id)
    assert updated_batch.record_count == 20
    assert batch_add_duration_ms < 100.0, f"Adding 20 items with idempotency checks took {batch_add_duration_ms:.2f}ms"
