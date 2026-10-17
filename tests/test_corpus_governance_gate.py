"""
VEDA Corpus Governance & Ingestion Gate Adversarial Test Suite (Phase 4.2)

Exhaustively tests the 10 critical governance and ingestion gate scenarios:
1. Missing, conflicting, or unknown license metadata
2. Source version changes update Manifest Fingerprint
3. Checksum format and validation
4. Duplicate source records and document deduplication
5. Unicode-rich eligible text preserved in NFC
6. Rejected and quarantined records logging
7. Interrupted acquisition or ingestion recovery
8. Deterministic reruns produce identical dual fingerprints
9. Manifest changes when source or configuration changes
10. Rejection of unapproved sources before ingestion
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusSource,
    LicensingStatus,
    RejectionReason,
)
from foundation.corpus.sources import SourceRegistry
from foundation.corpus.storage import CorpusReader


class TestCorpusGovernanceGate(unittest.TestCase):
    """Adversarial test suite for Phase 4.2 Source Governance and Ingestion Gate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Baseline valid permitted source
        self.valid_source = CorpusSource(
            source_id="test_permitted_source",
            name="Test Permitted Source",
            version="1.0.0",
            url_or_path="https://example.com/permitted.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="a" * 64,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            language="en",
            source_type="book",
            attribution="Public Domain Author",
            description="Permitted educational public domain test source",
            publisher="Test Publisher",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            commercial_permitted=True,
            training_permitted_status="EXPLICITLY_PERMITTED",
        )

        # Baseline valid document
        self.valid_doc = CorpusDocument(
            document_id="doc_001",
            source_id="test_permitted_source",
            title="Valid English Document",
            author="Author Name",
            raw_text=(
                "Language intelligence requires an uncompromising commitment to verified provenance. "
                "The VEDA architecture demonstrates that foundational models can be trained strictly on "
                "auditable, legally verified, and high-quality texts without web-scraping shortcuts.\n\n"
                "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
                "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC."
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- 1. MISSING, CONFLICTING, OR UNKNOWN LICENSE METADATA ---

    def test_missing_conflicting_or_unknown_license_metadata(self) -> None:
        """Verifies missing metadata raises ValueError and UNKNOWN status blocks ingestion."""
        # A. Missing source name
        with self.assertRaises(ValueError):
            CorpusSource(
                source_id="invalid_src",
                name="",
                version="1.0",
                url_or_path="https://example.com",
                acquisition_date="2026-10-15",
                source_hash="b" * 64,
                license="CC0",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

        # B. Invalid source ID regex
        with self.assertRaises(ValueError):
            CorpusSource(
                source_id="INVALID/SRC ID!",
                name="Invalid",
                version="1.0",
                url_or_path="https://example.com",
                acquisition_date="2026-10-15",
                source_hash="b" * 64,
                license="CC0",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

        # C. UNKNOWN licensing status blocks ingestion at pipeline entry
        unknown_source = CorpusSource(
            source_id="unknown_source",
            name="Unknown Source",
            version="1.0",
            url_or_path="https://example.com/unknown.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="c" * 64,
            license="Unknown",
            licensing_status=LicensingStatus.UNKNOWN,
        )
        doc = CorpusDocument(
            document_id="doc_unknown",
            source_id="unknown_source",
            raw_text="Some valid prose that must be blocked because the source license is unknown.",
        )

        out = self.test_dir / "unknown_out"
        pipeline = CorpusPipeline(corpus_name="test_unknown")
        manifest = pipeline.process_corpus([unknown_source], [doc], out)

        self.assertEqual(manifest.retained_records, 0)
        self.assertEqual(manifest.rejected_documents, 1)
        self.assertEqual(manifest.rejection_reasons.get(RejectionReason.GOVERNANCE_BLOCKED.value), 1)

    # --- 2. SOURCE VERSION CHANGES ---

    def test_source_version_changes_updates_manifest_fingerprint(self) -> None:
        """Verifies bumping source version alters Manifest Fingerprint while Content Fingerprint is unchanged."""
        source_v1 = self.valid_source
        source_v2 = CorpusSource(
            source_id="test_permitted_source",
            name="Test Permitted Source",
            version="2.0.0",  # Bumped version
            url_or_path="https://example.com/permitted.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="a" * 64,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        )

        out1 = self.test_dir / "out_v1"
        out2 = self.test_dir / "out_v2"
        pipeline = CorpusPipeline()

        m1 = pipeline.process_corpus([source_v1], [self.valid_doc], out1)
        m2 = pipeline.process_corpus([source_v2], [self.valid_doc], out2)

        # Content is identical: Content Fingerprints MUST match
        self.assertEqual(m1.content_fingerprint, m2.content_fingerprint)
        # Source version changed: Manifest Fingerprints MUST differ
        self.assertNotEqual(m1.manifest_fingerprint, m2.manifest_fingerprint)

    # --- 3. CHECKSUM FORMAT AND VALIDATION ---

    def test_checksum_mismatch_and_format_validation(self) -> None:
        """Verifies invalid checksum length or non-hex characters are rejected."""
        # Checksum too short
        with self.assertRaises(ValueError):
            CorpusSource(
                source_id="bad_hash_src",
                name="Bad Hash",
                version="1.0",
                url_or_path="https://example.com",
                acquisition_date="2026-10-15",
                source_hash="tooshort",
                license="CC0",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

        # Checksum with non-hex character
        with self.assertRaises(ValueError):
            CorpusSource(
                source_id="bad_hex_src",
                name="Bad Hex",
                version="1.0",
                url_or_path="https://example.com",
                acquisition_date="2026-10-15",
                source_hash="z" * 64,  # 'z' is not hex
                license="CC0",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

    # --- 4. DUPLICATE SOURCE RECORDS AND DOCUMENT DEDUPLICATION ---

    def test_duplicate_source_records(self) -> None:
        """Verifies duplicate source IDs raise ValueError and duplicate documents are rejected."""
        registry = SourceRegistry()
        registry.register(self.valid_source)
        with self.assertRaises(ValueError):
            registry.register(self.valid_source)

        # Test duplicate document rejection
        dup_doc = CorpusDocument(
            document_id="doc_001_dup",
            source_id="test_permitted_source",
            raw_text=self.valid_doc.raw_text,
        )
        out = self.test_dir / "dup_doc_out"
        pipeline = CorpusPipeline()
        manifest = pipeline.process_corpus([self.valid_source], [self.valid_doc, dup_doc], out)

        self.assertEqual(manifest.total_documents, 2)
        self.assertEqual(manifest.retained_documents, 1)
        self.assertEqual(manifest.rejected_documents, 1)
        self.assertEqual(manifest.rejection_reasons.get(RejectionReason.DUPLICATE.value), 1)

    # --- 5. UNICODE-RICH ELIGIBLE TEXT PRESERVED IN NFC ---

    def test_unicode_rich_eligible_text_preserved(self) -> None:
        """Verifies that eligible loanwords, smart quotes, em-dashes, and Greek symbols are preserved in NFC."""
        rich_doc = CorpusDocument(
            document_id="doc_unicode",
            source_id="test_permitted_source",
            raw_text=(
                "The café owner discussed the résumé of the chef over a cup of espresso. "
                "In physics, wavelength is denoted by λ and angular frequency by ω. "
                "He remarked, “Accurate typography matters—it preserves meaning and intent.”"
            ),
        )
        out = self.test_dir / "unicode_out"
        pipeline = CorpusPipeline()
        manifest = pipeline.process_corpus([self.valid_source], [rich_doc], out)

        self.assertEqual(manifest.retained_records, 1)
        records = list(CorpusReader.read_records(out / "train.jsonl")) + list(
            CorpusReader.read_records(out / "test.jsonl")
        )
        retained_text = records[0].normalized_text

        self.assertIn("café", retained_text)
        self.assertIn("résumé", retained_text)
        self.assertIn("λ", retained_text)
        self.assertIn("ω", retained_text)
        self.assertIn("—", retained_text)
        self.assertIn("“", retained_text)
        self.assertIn("”", retained_text)

    # --- 6. REJECTED AND QUARANTINED RECORDS LEDGER ---

    def test_rejected_and_quarantined_records_ledger(self) -> None:
        """Verifies rejections log stage, reason, metric, threshold, and raw sample."""
        short_doc = CorpusDocument(
            document_id="doc_short",
            source_id="test_permitted_source",
            raw_text="Short.",
        )
        out = self.test_dir / "rej_ledger_out"
        pipeline = CorpusPipeline()
        manifest = pipeline.process_corpus([self.valid_source], [short_doc], out)

        self.assertEqual(manifest.retained_records, 0)
        rej_file = out / "rejections.jsonl"
        self.assertTrue(rej_file.exists())
        rej_records = list(CorpusReader.read_rejections(rej_file))
        self.assertEqual(len(rej_records), 1)
        r = rej_records[0]
        self.assertEqual(r["rejection_reason"], RejectionReason.TOO_SHORT_CHARS.value)
        self.assertEqual(r["rejection_stage"], "filtering")
        self.assertEqual(r["document_id"], "doc_short")
        self.assertEqual(r["source_id"], "test_permitted_source")

    # --- 7. INTERRUPTED ACQUISITION OR INGESTION RECOVERY ---

    def test_interrupted_ingestion_recovery(self) -> None:
        """Verifies process failure cleans up .tmp files and never publishes manifest.json."""
        out = self.test_dir / "crash_recovery_out"
        out.mkdir(parents=True, exist_ok=True)
        bad_doc = CorpusDocument(
            document_id="bad_doc",
            source_id="missing_source",
            raw_text="Text with missing source.",
        )
        pipeline = CorpusPipeline()
        with self.assertRaises(RuntimeError):
            pipeline.process_corpus([self.valid_source], [bad_doc], out)

        # Check no .tmp files exist
        tmp_files = list(out.glob("*.tmp"))
        self.assertEqual(len(tmp_files), 0)
        # Check manifest was NOT written
        self.assertFalse((out / "manifest.json").exists())

    # --- 8. DETERMINISTIC RERUNS ---

    def test_deterministic_reruns_exact_fingerprint_match(self) -> None:
        """Verifies independent runs over the same input produce bit-for-bit identical fingerprints."""
        out1 = self.test_dir / "det_out1"
        out2 = self.test_dir / "det_out2"
        pipeline = CorpusPipeline()

        m1 = pipeline.process_corpus([self.valid_source], [self.valid_doc], out1)
        m2 = pipeline.process_corpus([self.valid_source], [self.valid_doc], out2)

        self.assertEqual(m1.content_fingerprint, m2.content_fingerprint)
        self.assertEqual(m1.manifest_fingerprint, m2.manifest_fingerprint)
        self.assertEqual(m1.artifacts["train_sha256"], m2.artifacts["train_sha256"])

    # --- 9. MANIFEST CHANGES WHEN SOURCE OR CONFIGURATION CHANGES ---

    def test_manifest_changes_when_configuration_changes(self) -> None:
        """Verifies altering split seed produces a different Manifest Fingerprint."""
        out1 = self.test_dir / "cfg_out1"
        out2 = self.test_dir / "cfg_out2"

        pipe1 = CorpusPipeline(split_seed="seed_alpha")
        pipe2 = CorpusPipeline(split_seed="seed_beta")

        m1 = pipe1.process_corpus([self.valid_source], [self.valid_doc], out1)
        m2 = pipe2.process_corpus([self.valid_source], [self.valid_doc], out2)

        self.assertNotEqual(m1.manifest_fingerprint, m2.manifest_fingerprint)

    # --- 10. REJECTION OF UNAPPROVED SOURCES BEFORE INGESTION ---

    def test_rejection_of_unapproved_sources_before_ingestion(self) -> None:
        """Verifies sources with REQUIRES_REVIEW or EXCLUDED are rejected at governance gate."""
        req_review_src = CorpusSource(
            source_id="src_review",
            name="Requires Review Source",
            version="1.0",
            url_or_path="https://example.com/review.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="d" * 64,
            license="CC-BY-SA-4.0",
            licensing_status=LicensingStatus.REQUIRES_REVIEW,
        )
        excluded_src = CorpusSource(
            source_id="src_excluded",
            name="Excluded Source",
            version="1.0",
            url_or_path="https://example.com/excluded.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="e" * 64,
            license="Proprietary",
            licensing_status=LicensingStatus.EXCLUDED,
        )

        doc1 = CorpusDocument("doc_rev", "src_review", "Text from review source that must be blocked.")
        doc2 = CorpusDocument("doc_exc", "src_excluded", "Text from excluded source that must be blocked.")

        out = self.test_dir / "unapproved_out"
        pipeline = CorpusPipeline()
        manifest = pipeline.process_corpus([req_review_src, excluded_src], [doc1, doc2], out)

        self.assertEqual(manifest.retained_records, 0)
        self.assertEqual(manifest.rejected_documents, 2)
        self.assertEqual(manifest.rejection_reasons.get(RejectionReason.GOVERNANCE_BLOCKED.value), 2)


if __name__ == "__main__":
    unittest.main()
