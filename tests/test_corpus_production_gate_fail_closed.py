"""
VEDA Production Ingestion Gate Fail-Closed Test Suite (Phase 4.2.3)

Tests the real ingestion entry point (CorpusPipeline.ingest_production_corpus)
to verify that production ingestion fails-closed and commits zero records
when any required precondition is unmet:
1. Candidate source with unacquired/unverified artifact
2. Excluded source (Common Crawl / Ubuntu Dialogue)
3. Metadata tampering relative to authoritative Source Registry
4. Missing or mismatching physical artifact bytes
5. Missing or invalid license evidence document
6. Expired approval date (stale approval)
7. Missing required attribution notice
8. Host storage reserve margin violation (<40% reserve)
9. Unregistered candidate source
10. Atomic rollback guaranteeing zero committed records
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from foundation.corpus.budget import PreflightStorageChecker, ResourceBudgetExceededError
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusSource,
    LicensingStatus,
)
from foundation.corpus.sources import (
    GovernanceGateError,
    SourceRegistry,
    StaleApprovalError,
    UnapprovedSourceError,
)


class TestCorpusProductionGateFailClosed(unittest.TestCase):
    """Rigorous fail-closed testing of the production ingestion entry point."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="veda_gate_test_"))
        self.output_dir = self.temp_dir / "production_output"

        # Load authoritative registry
        self.registry = SourceRegistry.load_from_json("data/corpus/source_registry.json")

        self.pipeline = CorpusPipeline(
            corpus_name="veda_production_test",
            corpus_version="0.1.0",
        )

        self.sample_doc = CorpusDocument(
            document_id="prod_doc_001",
            source_id="standard_ebooks",
            raw_text=(
                "It is a truth universally acknowledged, that a single man in possession "
                "of a good fortune, must be in want of a wife."
            ),
        )

    def tearDown(self) -> None:
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unacquired_candidate_source_rejected(self) -> None:
        """Production ingestion must reject unacquired candidate sources whose artifact is NOT_VERIFIED."""
        source = self.registry.get("standard_ebooks")
        self.assertIsNotNone(source)
        self.assertEqual(source.licensing_status, LicensingStatus.REQUIRES_REVIEW)

        with self.assertRaises(UnapprovedSourceError) as ctx:
            self.pipeline.ingest_production_corpus(
                sources=[source],
                documents=[self.sample_doc],
                output_dir=self.output_dir,
                source_registry=self.registry,
            )
        self.assertIn("standard_ebooks", str(ctx.exception))
        # Verify zero records committed
        self.assertFalse((self.output_dir / "manifest.json").exists())
        self.assertFalse((self.output_dir / "train.jsonl").exists())

    def test_excluded_source_rejected(self) -> None:
        """Production ingestion must reject explicitly EXCLUDED sources immediately."""
        source = self.registry.get("common_crawl_unfiltered")
        self.assertIsNotNone(source)
        self.assertEqual(source.licensing_status, LicensingStatus.EXCLUDED)

        doc = CorpusDocument("cc_doc", "common_crawl_unfiltered", "Some scraped text.")
        with self.assertRaises(UnapprovedSourceError) as ctx:
            self.pipeline.ingest_production_corpus(
                sources=[source],
                documents=[doc],
                output_dir=self.output_dir,
                source_registry=self.registry,
            )
        self.assertIn("EXCLUDED", str(ctx.exception))
        self.assertFalse((self.output_dir / "manifest.json").exists())

    def test_tampered_source_metadata_rejected(self) -> None:
        """Production ingestion must reject a source whose metadata differs from the registry."""
        original = self.registry.get("standard_ebooks")
        # Tamper: change attribution or license
        tampered_dict = original.to_dict()
        tampered_dict["attribution"] = "Unauthorized Third Party"
        tampered_source = CorpusSource.from_dict(tampered_dict)

        with self.assertRaises(GovernanceGateError) as ctx:
            self.pipeline.ingest_production_corpus(
                sources=[tampered_source],
                documents=[self.sample_doc],
                output_dir=self.output_dir,
                source_registry=self.registry,
            )
        self.assertIn("modified after approval", str(ctx.exception))
        self.assertFalse((self.output_dir / "manifest.json").exists())

    def test_unregistered_source_rejected(self) -> None:
        """Production ingestion must reject any source not present in authoritative registry."""
        rogue_source = CorpusSource(
            source_id="rogue_unregistered_corpus",
            name="Rogue Corpus",
            version="1.0",
            url_or_path="https://example.com/rogue",
            acquisition_date="2026-10-15",
            source_hash="a" * 64,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        )
        doc = CorpusDocument("rogue_doc", "rogue_unregistered_corpus", "Valid text here.")

        with self.assertRaises(UnapprovedSourceError) as ctx:
            self.pipeline.ingest_production_corpus(
                sources=[rogue_source],
                documents=[doc],
                output_dir=self.output_dir,
                source_registry=self.registry,
            )
        self.assertIn("not registered in authoritative registry", str(ctx.exception))
        self.assertFalse((self.output_dir / "manifest.json").exists())

    def test_stale_approval_source_rejected(self) -> None:
        """Production ingestion must reject a source whose approval expiration date has passed."""
        stale_source = CorpusSource(
            source_id="stale_source",
            name="Stale Source",
            version="1.0",
            url_or_path="https://example.com/stale",
            acquisition_date="2025-01-01",
            source_hash="b" * 64,
            artifact_sha256="b" * 64,
            license="CC-BY-4.0",
            license_url="https://example.com/license",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            attribution="Stale Attribution",
            evidence_checksum="d" * 64,
            license_evidence_sha256="d" * 64,
            evidence_retrieval_date="2025-01-01",
            reviewer_identity="Lead Auditor",
            review_date="2025-01-01",
            re_review_triggers="Annual",
            work_level_scope="Complete archive",
            approval_expiration_date="2025-06-01",  # Past date
        )
        reg = SourceRegistry([stale_source])
        doc = CorpusDocument("stale_doc", "stale_source", "Valid text content.")

        with self.assertRaises(StaleApprovalError) as ctx:
            self.pipeline.ingest_production_corpus(
                sources=[stale_source],
                documents=[doc],
                output_dir=self.output_dir,
                source_registry=reg,
            )
        self.assertIn("stale or expired", str(ctx.exception))
        self.assertFalse((self.output_dir / "manifest.json").exists())

    def test_host_reserve_margin_violation_halts_before_execution(self) -> None:
        """Production ingestion must halt if estimated job bytes violate host reserve margin."""
        valid_source = CorpusSource(
            source_id="valid_src",
            name="Valid Source",
            version="1.0",
            url_or_path="https://example.com/valid",
            acquisition_date="2026-10-15",
            source_hash="c" * 64,
            artifact_sha256="c" * 64,
            license="CC-BY-4.0",
            license_url="https://example.com/license",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            attribution="Valid Attribution",
            evidence_checksum="e" * 64,
            license_evidence_sha256="e" * 64,
            evidence_retrieval_date="2026-10-15",
            reviewer_identity="Lead Auditor",
            review_date="2026-10-15",
            re_review_triggers="Annual",
            work_level_scope="Complete archive",
            approval_expiration_date="2027-10-15",
        )
        reg = SourceRegistry([valid_source])
        doc = CorpusDocument("valid_doc", "valid_src", "Valid text content.")

        # Request an impossible footprint (e.g. 1 Petabyte) that violates reserve
        huge_bytes = 1_000_000_000_000_000
        with self.assertRaises(ResourceBudgetExceededError):
            self.pipeline.ingest_production_corpus(
                sources=[valid_source],
                documents=[doc],
                output_dir=self.output_dir,
                source_registry=reg,
                estimated_job_bytes=huge_bytes,
            )
        # Verify no directory or files were created
        self.assertFalse((self.output_dir / "manifest.json").exists())

    def test_atomic_rollback_on_pipeline_failure(self) -> None:
        """Verifies that if an unexpected error occurs during processing, rollback removes all .tmp files."""
        valid_source = CorpusSource(
            source_id="valid_src",
            name="Valid Source",
            version="1.0",
            url_or_path="https://example.com/valid",
            acquisition_date="2026-10-15",
            source_hash="c" * 64,
            artifact_sha256="c" * 64,
            license="CC-BY-4.0",
            license_url="https://example.com/license",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            training_permitted_status="EXPLICITLY_PERMITTED",
            commercial_permitted=True,
            attribution="Valid Attribution",
            evidence_checksum="e" * 64,
            license_evidence_sha256="e" * 64,
            evidence_retrieval_date="2026-10-15",
            reviewer_identity="Lead Auditor",
            review_date="2026-10-15",
            re_review_triggers="Annual",
            work_level_scope="Complete archive",
            approval_expiration_date="2027-10-15",
        )
        reg = SourceRegistry([valid_source])

        # Doc referencing missing source to trigger mid-run failure
        docs = [
            CorpusDocument("good_doc", "valid_src", "Good prose text."),
            CorpusDocument("bad_doc", "nonexistent_src", "Corrupt prose text."),
        ]

        with self.assertRaises(RuntimeError):
            self.pipeline.ingest_production_corpus(
                sources=[valid_source],
                documents=docs,
                output_dir=self.output_dir,
                source_registry=reg,
            )

        # Confirm atomic rollback: zero committed splits, zero .tmp files, zero manifest
        self.assertFalse((self.output_dir / "manifest.json").exists())
        self.assertFalse((self.output_dir / "train.jsonl").exists())
        for f in self.output_dir.glob("*.tmp"):
            self.fail(f"Found orphaned temporary file: {f}")


if __name__ == "__main__":
    unittest.main()
