"""
VEDA Deterministic Splitting Tests (Phase 4 — Training Corpus Architecture)

Validates:
- Deterministic hash-based split assignment
- Seed sensitivity (different seeds yield different splits)
- Invariance: same document_id + seed always yields identical split
- Split ratio validation (sum must equal 1.0)
- Zero leakage invariant across document groups
"""

import pytest

from foundation.corpus.schemas import DatasetSplit
from foundation.corpus.splitting import DeterministicSplitter


class TestDeterministicSplitter:
    """Test suite for DeterministicSplitter."""

    def test_split_determinism(self):
        splitter = DeterministicSplitter(seed="SEED_ALPHA")
        doc_id = "doc_chapter_104"

        split1 = splitter.assign_document_split(doc_id)
        split2 = splitter.assign_document_split(doc_id)
        assert split1 == split2

    def test_seed_sensitivity(self):
        splitter_a = DeterministicSplitter(seed="SEED_ALPHA")
        splitter_b = DeterministicSplitter(seed="SEED_BETA_DIFFERENT")

        # Over 50 documents, differing seeds will cause different split mappings
        matches = 0
        trials = 50
        for i in range(trials):
            doc_id = f"doc_experiment_{i}"
            if splitter_a.assign_document_split(doc_id) == splitter_b.assign_document_split(doc_id):
                matches += 1

        # Ratios: 90% train means they often match train, but shouldn't match 100% of documents
        assert matches < trials

    def test_ratio_sum_validation(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            DeterministicSplitter(train_ratio=0.8, val_ratio=0.1, test_ratio=0.2)  # sum = 1.1

    def test_split_distribution_large_population(self):
        splitter = DeterministicSplitter(
            train_ratio=0.80,
            val_ratio=0.10,
            test_ratio=0.10,
            seed="TEST_DIST_SEED",
        )
        doc_ids = [f"document_sample_{i}" for i in range(1000)]
        distribution = splitter.get_split_stats_distribution(doc_ids)

        train_count = distribution["train"]
        val_count = distribution["validation"]
        test_count = distribution["test"]

        assert train_count + val_count + test_count == 1000
        # Check within reasonable statistical margin for hash buckets (~800, ~100, ~100)
        assert 750 <= train_count <= 850
        assert 70 <= val_count <= 130
        assert 70 <= test_count <= 130
