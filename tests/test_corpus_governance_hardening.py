"""
VEDA Corpus Governance & Ingestion Gate Hardening Test Suite (Phase 4.2.1)

Adversarial verification of:
1. Stale or superseded approval fails closed
2. Missing license evidence fails strict audit
3. Tampered registry metadata detected and blocked
4. Strict direct API invocation fails closed on unapproved sources
5. Related-work grouping guarantees identical split across seeds
6. Cross-source deduplication preserves contributing provenance & attribution
7. Preflight storage check aborts execution before writing files
8. MinHash/LSH near-duplicate candidate detection & hard negative separation
9. Conservation laws across complex multi-source corpus
10. Configuration mutations alter manifest fingerprint deterministically
"""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from foundation.corpus.budget import PreflightStorageChecker, ResourceBudgetExceededError
from foundation.corpus.deduplication import DeduplicationEngine
from foundation.corpus.manifest import compute_content_fingerprint, compute_manifest_fingerprint
from foundation.corpus.near_deduplication import (
    MinHashLSHCandidateDetector,
    build_default_labeled_test_set,
    evaluate_near_duplicate_strategy,
)
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusRecord,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
    RecordProvenance,
    RejectionReason,
)
from foundation.corpus.sources import (
    GovernanceGateError,
    SourceRegistry,
    StaleApprovalError,
    UnapprovedSourceError,
)
from foundation.corpus.splitting import DeterministicSplitter


class TestCorpusGovernanceHardening(unittest.TestCase):
    """Adversarial hardening test suite for Phase 4.2.1."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

        # Baseline compliant permitted source
        self.compliant_source = CorpusSource(
            source_id="compliant_se_source",
            name="Compliant Standard Ebooks",
            version="2026.1",
            url_or_path="https://standardebooks.org/ebooks/test",
            acquisition_date="2026-10-15",
            source_hash="a" * 64,
            license="Public Domain / CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            language="en",
            source_type="book",
            attribution="Standard Ebooks Volunteer Association",
            description="Fully audited public domain literary text.",
            publisher="Standard Ebooks",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            commercial_permitted=True,
            training_permitted_status="EXPLICITLY_PERMITTED",
            work_level_scope="Complete work.",
            jurisdiction_limitations="US Public Domain (pre-1929).",
            evidence_retrieval_date="2026-10-15",
            evidence_checksum="e97d04b516dd46d0a662a9a0e1be68e5f4702cbcea4be03ccba7229569eb226d",
            reviewer_identity="VEDA Lead Auditor",
            review_date="2026-10-15",
            re_review_triggers="180-day cycle.",
            approval_expiration_date="2027-04-15",
        )

        self.valid_text = (
            "Language intelligence requires an uncompromising commitment to verified provenance. "
            "The VEDA architecture demonstrates that foundational models can be trained strictly on "
            "auditable, legally verified, and high-quality texts without web-scraping shortcuts."
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- 1. STALE / EXPIRED APPROVAL FAILS CLOSED ---

    def test_stale_approval_fails_closed(self) -> None:
        """Verifies that an expired approval is detected and fails closed."""
        expired_source = CorpusSource(
            source_id="expired_source",
            name="Expired Source",
            version="1.0.0",
            url_or_path="https://example.com/expired",
            acquisition_date="2025-01-01",
            source_hash="b" * 64,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            license_url="https://example.com/license",
            commercial_permitted=True,
            training_permitted_status="EXPLICITLY_PERMITTED",
            approval_expiration_date="2025-06-01",  # Past expiration date
        )

        self.assertTrue(expired_source.is_approval_stale)
        self.assertFalse(expired_source.is_permitted_for_training)

        reg = SourceRegistry([expired_source])
        with self.assertRaises(StaleApprovalError):
            reg.assert_permitted_admissible(expired_source)

    # --- 2. MISSING LICENSE EVIDENCE FAILS STRICT AUDIT ---

    def test_missing_license_evidence_fails_audit(self) -> None:
        """Verifies that missing evidence fields produce audit failures."""
        incomplete_source = CorpusSource(
            source_id="incomplete_source",
            name="Incomplete Source",
            version="1.0.0",
            url_or_path="https://example.com/incomplete",
            acquisition_date="2026-10-15",
            source_hash="c" * 64,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            license_url="https://example.com/license",
            commercial_permitted=True,
            training_permitted_status="EXPLICITLY_PERMITTED",
            # Missing evidence_checksum, evidence_retrieval_date, reviewer_identity, review_date
        )

        reg = SourceRegistry([incomplete_source])
        issues = reg.validate_source_governance(incomplete_source, strict_evidence=True)
        self.assertGreater(len(issues), 0)
        self.assertTrue(any("evidence_checksum" in iss for iss in issues))
        self.assertTrue(any("reviewer_identity" in iss for iss in issues))

        with self.assertRaises(GovernanceGateError):
            reg.assert_permitted_admissible(incomplete_source, strict_evidence=True)

    # --- 3. TAMPERED REGISTRY METADATA DETECTED ---

    def test_tampered_registry_metadata_detected(self) -> None:
        """Verifies that modifying source attributes after approval violates registry integrity."""
        reg = SourceRegistry([self.compliant_source])

        # Tampered copy attempting to alter URL
        tampered_source = CorpusSource.from_dict({
            **self.compliant_source.to_dict(),
            "url_or_path": "https://attacker.com/malicious_payload.tar.gz",
        })

        with self.assertRaises(GovernanceGateError) as ctx:
            reg.verify_source_integrity(tampered_source)
        self.assertIn("Registry integrity violation", str(ctx.exception))

    # --- 4. STRICT API INVOCATION FAILS CLOSED ---

    def test_strict_api_invocation_fails_closed(self) -> None:
        """Verifies direct pipeline API fails closed when strict_governance=True."""
        unapproved_source = CorpusSource(
            source_id="gated_review_source",
            name="Gated Review Source",
            version="1.0.0",
            url_or_path="https://example.com/gated",
            acquisition_date="2026-10-15",
            source_hash="d" * 64,
            license="CC-BY-SA-4.0",
            licensing_status=LicensingStatus.REQUIRES_REVIEW,
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
        )
        doc = CorpusDocument("doc_gated", "gated_review_source", self.valid_text)

        pipeline = CorpusPipeline(corpus_name="test_strict_gate")
        out_path = self.test_dir / "strict_gate_out"

        with self.assertRaises(UnapprovedSourceError):
            pipeline.process_corpus(
                [unapproved_source],
                [doc],
                out_path,
                strict_governance=True,
            )

    # --- 5. RELATED-WORK GROUPING PREVENTS SPLIT LEAKAGE ---

    def test_related_work_grouping_prevents_split_leakage(self) -> None:
        """Verifies that chapters and excerpts sharing group_id land in identical splits across 50 seeds."""
        for seed_idx in range(50):
            seed = f"VEDA_SEED_TEST_{seed_idx}"
            splitter = DeterministicSplitter(seed=seed, train_ratio=0.80, val_ratio=0.10, test_ratio=0.10)

            # Two different document IDs sharing the same group_id
            doc1_split = splitter.assign_document_split(
                document_id=f"moby_dick_ch_{seed_idx}",
                group_id="moby_dick_work_group",
            )
            doc2_split = splitter.assign_document_split(
                document_id=f"moby_dick_excerpt_{seed_idx}",
                group_id="moby_dick_work_group",
            )

            self.assertEqual(
                doc1_split,
                doc2_split,
                f"Related work grouping violated on seed {seed}: {doc1_split} != {doc2_split}",
            )

    # --- 6. CROSS-SOURCE DEDUPLICATION PRESERVES CONTRIBUTING SOURCES ---

    def test_cross_source_deduplication_preserves_all_contributing_sources(self) -> None:
        """Verifies deduplication records both contributing sources and attributions."""
        source_a = self.compliant_source
        source_b = CorpusSource(
            source_id="pg_mirror_source",
            name="Project Gutenberg Mirror",
            version="2026.09",
            url_or_path="https://gutenberg.org/ebooks/999",
            acquisition_date="2026-10-15",
            source_hash="e" * 64,
            license="Public Domain (US)",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            license_url="https://www.gutenberg.org/policy/license.html",
            attribution="Project Gutenberg Literary Archive Foundation",
            commercial_permitted=True,
            training_permitted_status="EXPLICITLY_PERMITTED",
        )

        doc_a = CorpusDocument("doc_a", source_a.source_id, self.valid_text)
        doc_b = CorpusDocument("doc_b", source_b.source_id, self.valid_text)

        engine = DeduplicationEngine()
        is_dup1, canon1, _ = engine.check_and_register_record(
            record_id="rec_001",
            raw_text=self.valid_text,
            normalized_text=self.valid_text,
            source_id=source_a.source_id,
            document_id=doc_a.document_id,
            attribution=source_a.attribution,
        )
        self.assertFalse(is_dup1)

        is_dup2, canon2, dup_type = engine.check_and_register_record(
            record_id="rec_002",
            raw_text=self.valid_text,
            normalized_text=self.valid_text,
            source_id=source_b.source_id,
            document_id=doc_b.document_id,
            attribution=source_b.attribution,
        )
        self.assertTrue(is_dup2)
        self.assertEqual(canon2, "rec_001")
        self.assertEqual(dup_type, "exact")

        contributors = engine.get_contributors("rec_001")
        self.assertEqual(len(contributors), 2)
        contributing_src_ids = [c["source_id"] for c in contributors]
        self.assertIn("compliant_se_source", contributing_src_ids)
        self.assertIn("pg_mirror_source", contributing_src_ids)

    # --- 7. PREFLIGHT DISK SPACE CHECKER ABORTS ---

    def test_preflight_disk_space_checker_aborts_on_insufficient_space(self) -> None:
        """Verifies PreflightStorageChecker halts before execution when space is insufficient."""
        checker = PreflightStorageChecker(minimum_reserve_bytes=20 * 1024 * 1024 * 1024)

        # Request impossibly large allocation: 50 Petabytes
        impossibly_large_bytes = 50 * 1024 * 1024 * 1024 * 1024 * 1024
        with self.assertRaises(ResourceBudgetExceededError) as ctx:
            checker.verify_disk_availability(
                target_path=self.test_dir,
                estimated_job_bytes=impossibly_large_bytes,
                enforce=True,
            )
        self.assertIn("Disk preflight check failed", str(ctx.exception))

    # --- 8. MINHASH / LSH EVALUATION ---

    def test_minhash_lsh_near_duplicate_evaluation(self) -> None:
        """Verifies MinHash/LSH evaluation achieves expected precision and recall."""
        eval_report = evaluate_near_duplicate_strategy(threshold=0.80)
        self.assertEqual(eval_report["precision"], 1.0)
        self.assertEqual(eval_report["recall"], 1.0)
        self.assertEqual(eval_report["false_positives"], 0)
        self.assertEqual(eval_report["false_negatives"], 0)
        self.assertGreater(eval_report["total_evaluated_pairs"], 0)

    # --- 9. CONSERVATION LAWS ACROSS COMPLEX MIXED CORPUS ---

    def test_conservation_laws_on_mixed_corpus(self) -> None:
        """Verifies strict conservation laws hold on a multi-source corpus."""
        src_permitted = self.compliant_source
        src_unapproved = CorpusSource(
            source_id="unapproved_src",
            name="Unapproved",
            version="1.0",
            url_or_path="https://example.com/unapproved",
            acquisition_date="2026-10-15",
            source_hash="f" * 64,
            license="All Rights Reserved",
            licensing_status=LicensingStatus.REQUIRES_REVIEW,
        )

        docs = [
            CorpusDocument("doc_ok_1", src_permitted.source_id, self.valid_text),
            CorpusDocument("doc_dup_exact", src_permitted.source_id, self.valid_text),
            CorpusDocument("doc_short", src_permitted.source_id, "Tiny snippet."),
            CorpusDocument("doc_blocked", src_unapproved.source_id, self.valid_text),
        ]

        out_path = self.test_dir / "conservation_out"
        pipeline = CorpusPipeline()
        manifest = pipeline.process_corpus([src_permitted, src_unapproved], docs, out_path)

        self.assertEqual(
            manifest.total_documents,
            manifest.retained_documents + manifest.rejected_documents,
        )
        self.assertEqual(
            manifest.total_records_processed,
            manifest.retained_records + manifest.rejected_records + manifest.duplicate_records,
        )

    # --- 10. MANIFEST FINGERPRINT CHANGES ON CONFIG MUTATION ---

    def test_manifest_fingerprint_changes_on_config_mutation(self) -> None:
        """Verifies manifest fingerprint is sensitive to policy and split configuration changes."""
        config1 = {
            "corpus_name": "test_corpus",
            "corpus_version": "0.1.0",
            "split_seed": "SEED_A",
            "policies": {
                "grouping_version": "0.1.0",
                "grouping_algorithm": "deterministic_group_hash_v1",
            },
        }
        config2 = {
            "corpus_name": "test_corpus",
            "corpus_version": "0.1.0",
            "split_seed": "SEED_B",  # Changed seed
            "policies": {
                "grouping_version": "0.1.0",
                "grouping_algorithm": "deterministic_group_hash_v1",
            },
        }
        config3 = {
            "corpus_name": "test_corpus",
            "corpus_version": "0.1.0",
            "split_seed": "SEED_A",
            "policies": {
                "grouping_version": "0.2.0",  # Changed grouping version
                "grouping_algorithm": "deterministic_group_hash_v2",
            },
        }

        fp1 = compute_manifest_fingerprint(config1)
        fp2 = compute_manifest_fingerprint(config2)
        fp3 = compute_manifest_fingerprint(config3)

        self.assertNotEqual(fp1, fp2)
        self.assertNotEqual(fp1, fp3)
        self.assertNotEqual(fp2, fp3)

    # --- 11. EMPTY-ARTIFACT PLACEHOLDER HASH REJECTED ---

    def test_empty_artifact_placeholder_hash_rejected_on_nonempty_source(self) -> None:
        """Verifies that the empty-string SHA-256 placeholder is rejected when nonempty content is required."""
        empty_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        with self.assertRaises(ValueError) as ctx:
            CorpusSource(
                source_id="fake_se_source",
                name="Fake Standard Ebooks",
                version="2026.1",
                url_or_path="https://standardebooks.org",
                acquisition_date="2026-10-15",
                source_hash=empty_sha256,
                license="Public Domain",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
                expected_size_mb=450.0,
                format="epub",
            )
        self.assertIn("Empty-artifact SHA-256 placeholder detected", str(ctx.exception))

    # --- 12. PHYSICAL FILE BYTES VERIFICATION ---

    def test_physical_file_bytes_verification_and_mismatch_rejection(self) -> None:
        """Verifies verify_artifact_bytes checks real file bytes and rejects mismatches."""
        test_file = self.test_dir / "real_artifact.txt"
        test_content = b"Authentic acquired source artifact bytes for testing."
        test_file.write_bytes(test_content)
        correct_sha256 = hashlib.sha256(test_content).hexdigest()

        src = CorpusSource(
            source_id="real_acquired_source",
            name="Real Source",
            version="1.0",
            url_or_path="https://example.com/real.tar.gz",
            acquisition_date="2026-10-15",
            source_hash=correct_sha256,
            license="CC0-1.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        )
        # Should verify cleanly against actual bytes
        self.assertTrue(src.verify_artifact_bytes(test_file))

        # Tamper with file
        tampered_file = self.test_dir / "tampered_artifact.txt"
        tampered_file.write_bytes(b"Tampered bytes!")
        with self.assertRaises(ValueError) as ctx:
            src.verify_artifact_bytes(tampered_file)
        self.assertIn("Artifact checksum mismatch", str(ctx.exception))

    # --- 13. NOT_VERIFIED ARTIFACT FAILS INGESTION GATE ---

    def test_not_verified_source_blocked_from_training(self) -> None:
        """Verifies that an unacquired source with artifact_sha256='NOT_VERIFIED' cannot enter training."""
        unverified_source = CorpusSource(
            source_id="unacquired_candidate",
            name="Unacquired Candidate Source",
            version="1.0",
            url_or_path="https://example.com/unacquired.tar.gz",
            acquisition_date="2026-10-15",
            source_hash="NOT_VERIFIED",
            license="CC-BY-4.0",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        )
        self.assertFalse(unverified_source.is_permitted_for_training)

        registry = SourceRegistry()
        registry.register(unverified_source)
        # assert_permitted_admissible must fail closed
        with self.assertRaises(GovernanceGateError) as ctx:
            registry.assert_permitted_admissible(unverified_source)
        self.assertIn("NOT_VERIFIED", str(ctx.exception))

    # --- 14. HOST SAFETY RESERVE MARGIN ENFORCEMENT ---

    def test_host_reserve_margin_enforcement(self) -> None:
        """Verifies verify_host_reserve_margin catches reserve margin violations."""
        checker = PreflightStorageChecker()
        # Enforce an impossibly high 99.9% reserve margin
        with self.assertRaises(ResourceBudgetExceededError) as ctx:
            checker.verify_host_reserve_margin(
                target_path=self.test_dir,
                min_reserve_percent=99.9,
                enforce=True,
            )
        self.assertIn("Host safety reserve violation", str(ctx.exception))

