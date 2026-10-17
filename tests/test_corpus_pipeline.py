"""
VEDA Corpus Pipeline Integration, Golden Fixture, Determinism & Recovery Tests
(Phase 4 — Training Corpus Architecture)

Validates:
- Golden Corpus Fixture execution with difficult edge cases (Phase 4S)
- Zero data leakage: document-level split containment (Phase 4L)
- Determinism: identical logical fingerprint across independent runs (Phase 4T)
- Idempotency: repeated runs produce identical records and counts (Phase 4U)
- Failure Recovery: atomic rollback, cleanup of .tmp files, manifest integrity (Phase 4V)
- Machine-readable manifest verification (Phase 4P)
"""

import json
import shutil
from pathlib import Path

import pytest

from foundation.corpus.manifest import CorpusManifest
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
)
from foundation.corpus.storage import CorpusReader


@pytest.fixture
def golden_sources_and_docs():
    """Loads immutable golden corpus fixtures."""
    fixtures_dir = Path("data/corpus/fixtures")
    sources_path = fixtures_dir / "golden_sources.json"
    docs_path = fixtures_dir / "golden_documents.json"

    with open(sources_path, "r", encoding="utf-8") as f:
        raw_sources = json.load(f)
        sources = [CorpusSource.from_dict(s) for s in raw_sources]

    with open(docs_path, "r", encoding="utf-8") as f:
        raw_docs = json.load(f)
        docs = [CorpusDocument.from_dict(d) for d in raw_docs]

    return sources, docs


class TestCorpusPipelineGoldenAndIntegrity:
    """Golden fixture and end-to-end pipeline verification."""

    def test_golden_fixture_pipeline_run(self, tmp_path, golden_sources_and_docs):
        sources, docs = golden_sources_and_docs
        pipeline = CorpusPipeline(
            corpus_name="veda_golden_test",
            corpus_version="0.1.0",
        )

        manifest = pipeline.process_corpus(
            sources=sources,
            documents=docs,
            output_dir=tmp_path,
        )

        # 1. Manifest file existence & structure
        manifest_file = tmp_path / "manifest.json"
        assert manifest_file.exists()
        loaded_manifest = CorpusManifest.from_file(manifest_file)
        assert loaded_manifest.corpus_name == "veda_golden_test"
        assert len(loaded_manifest.artifacts["logical_fingerprint"]) == 64

        # 2. Check split files exist
        train_file = tmp_path / "train.jsonl"
        val_file = tmp_path / "validation.jsonl"
        test_file = tmp_path / "test.jsonl"
        rejections_file = tmp_path / "rejections.jsonl"

        assert train_file.exists()
        assert val_file.exists()
        assert test_file.exists()
        assert rejections_file.exists()

        # 3. Governance gate: doc_13_governance_excluded must be in rejections under GOVERNANCE_BLOCKED
        rejections = list(CorpusReader.read_rejections(rejections_file))
        gov_blocked = [r for r in rejections if r["rejection_reason"] == "GOVERNANCE_BLOCKED"]
        assert len(gov_blocked) >= 1
        assert any("doc_13_governance_excluded" in r["document_id"] for r in gov_blocked)

        # 4. Document Deduplication: doc_06_exact_duplicate_of_01 must be rejected under DUPLICATE
        doc_dups = [r for r in rejections if r["rejection_reason"] == "DUPLICATE" and "doc_dup" in r["record_id"]]
        assert len(doc_dups) >= 1
        assert any("doc_06" in r["document_id"] for r in doc_dups)

        # 5. Corrupted records properly rejected
        short_rejections = [r for r in rejections if r["rejection_reason"] == "TOO_SHORT_CHARS"]
        assert any("doc_08_very_short" in r["document_id"] for r in short_rejections)

        nonlatin_rejections = [r for r in rejections if r["rejection_reason"] == "NON_ENGLISH_SCRIPT"]
        assert any("doc_09_multilingual_nonlatin" in r["document_id"] for r in nonlatin_rejections)

        # 6. Accepted records verification
        train_records = list(CorpusReader.read_records(train_file))
        val_records = list(CorpusReader.read_records(val_file))
        test_records = list(CorpusReader.read_records(test_file))
        all_accepted = train_records + val_records + test_records

        assert len(all_accepted) > 0
        for rec in all_accepted:
            # Check contract invariants
            assert rec.raw_char_count == len(rec.raw_text)
            assert rec.normalized_char_count == len(rec.normalized_text)
            assert rec.quality_score >= 0.50
            assert rec.is_duplicate is False

    def test_data_leakage_prevention(self, tmp_path, golden_sources_and_docs):
        """Verifies that all segments from a single document belong strictly to the same split."""
        sources, docs = golden_sources_and_docs
        pipeline = CorpusPipeline()
        pipeline.process_corpus(sources, docs, tmp_path)

        train_records = list(CorpusReader.read_records(tmp_path / "train.jsonl"))
        val_records = list(CorpusReader.read_records(tmp_path / "validation.jsonl"))
        test_records = list(CorpusReader.read_records(tmp_path / "test.jsonl"))

        train_doc_ids = {r.document_id for r in train_records}
        val_doc_ids = {r.document_id for r in val_records}
        test_doc_ids = {r.document_id for r in test_records}

        # Zero intersection across document IDs
        assert train_doc_ids.isdisjoint(val_doc_ids)
        assert train_doc_ids.isdisjoint(test_doc_ids)
        assert val_doc_ids.isdisjoint(test_doc_ids)

    def test_determinism_across_runs(self, tmp_path, golden_sources_and_docs):
        """Verifies that running the same fixture multiple times yields bitwise identical logical fingerprints."""
        sources, docs = golden_sources_and_docs

        run1_dir = tmp_path / "run1"
        run2_dir = tmp_path / "run2"

        pipeline = CorpusPipeline(split_seed="VEDA_DETERMINISM_TEST_SEED")

        manifest1 = pipeline.process_corpus(sources, docs, run1_dir)
        manifest2 = pipeline.process_corpus(sources, docs, run2_dir)

        # Logical dataset fingerprint must match 100%
        fp1 = manifest1.artifacts["logical_fingerprint"]
        fp2 = manifest2.artifacts["logical_fingerprint"]
        assert fp1 == fp2

        # Check statistical counts identical
        assert manifest1.statistics == manifest2.statistics

        # Check records match
        records1 = list(CorpusReader.read_records(run1_dir / "train.jsonl"))
        records2 = list(CorpusReader.read_records(run2_dir / "train.jsonl"))
        assert len(records1) == len(records2)
        for r1, r2 in zip(records1, records2):
            assert r1.record_id == r2.record_id
            assert r1.normalized_text == r2.normalized_text
            assert r1.quality_score == r2.quality_score

    def test_idempotency_invariance(self, tmp_path, golden_sources_and_docs):
        """Rebuilding into the same directory overwrites cleanly without duplication."""
        sources, docs = golden_sources_and_docs
        pipeline = CorpusPipeline()

        manifest_a = pipeline.process_corpus(sources, docs, tmp_path)
        count_a = manifest_a.statistics["retained_records"]

        # Run again in the same directory
        manifest_b = pipeline.process_corpus(sources, docs, tmp_path)
        count_b = manifest_b.statistics["retained_records"]

        assert count_a == count_b
        assert manifest_a.artifacts["logical_fingerprint"] == manifest_b.artifacts["logical_fingerprint"]

    def test_failure_recovery_and_cleanup(self, tmp_path, golden_sources_and_docs):
        """Verifies that an error midway rolls back, cleans up .tmp files, and does NOT publish manifest."""
        sources, docs = golden_sources_and_docs

        # Introduce a corrupted document referencing a non-existent source
        bad_doc = CorpusDocument(
            document_id="bad_doc_corrupted",
            source_id="non_existent_source_id_xyz",
            raw_text="This document references an uncataloged source.",
        )
        invalid_docs = docs + [bad_doc]

        pipeline = CorpusPipeline()

        with pytest.raises(RuntimeError, match="references unknown source_id"):
            pipeline.process_corpus(sources, invalid_docs, tmp_path)

        # Verify that manifest was NOT published
        assert not (tmp_path / "manifest.json").exists()

        # Verify that temporary files were cleaned up
        for tmp_file in tmp_path.glob("*.tmp"):
            pytest.fail(f"Found orphaned temporary file: {tmp_file}")
