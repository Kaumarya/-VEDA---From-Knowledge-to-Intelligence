"""
VEDA Deterministic Corpus Splitter (Phase 4 — Training Corpus Architecture)

Implements leakage-aware, deterministic Train/Validation/Test splitting partitioned
at the Document boundary using a cryptographic hash bucket function.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Tuple

from foundation.corpus.schemas import DatasetSplit


class DeterministicSplitter:
    """
    Partitions documents and records into Train, Validation, and Test splits.

    Guarantees:
    1. Zero Data Leakage: All segments from the same document receive the same split.
    2. Determinism: Same document ID and seed always yield the same split.
    3. Reproducibility across operating systems and platforms.
    """

    VERSION = "0.1.0"
    DEFAULT_SEED = "VEDA_CORPUS_SEED_v0.1"

    def __init__(
        self,
        seed: str = DEFAULT_SEED,
        train_ratio: float = 0.90,
        val_ratio: float = 0.05,
        test_ratio: float = 0.05,
    ) -> None:
        total = train_ratio + val_ratio + test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Split ratios must sum to 1.0, got train={train_ratio}, val={val_ratio}, test={test_ratio} (sum={total})"
            )
        self.seed = seed
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

        # Precompute bucket boundaries out of 1000
        self._train_cutoff = int(round(train_ratio * 1000))
        self._val_cutoff = self._train_cutoff + int(round(val_ratio * 1000))

    def assign_document_split(self, document_id: str, group_id: Optional[str] = None) -> DatasetSplit:
        """
        Deterministically maps a document_id or group_id to a DatasetSplit.
        If group_id is provided, all documents within the same group (e.g. chapters of
        the same book, editions, translations, or near-duplicates) are guaranteed
        to be placed in the identical split partition, preventing train/test leakage.
        """
        effective_key = group_id if group_id else document_id
        key = f"{self.seed}::{effective_key}".encode("utf-8")
        hash_hex = hashlib.sha256(key).hexdigest()
        bucket = int(hash_hex[:8], 16) % 1000

        if bucket < self._train_cutoff:
            return DatasetSplit.TRAIN
        elif bucket < self._val_cutoff:
            return DatasetSplit.VALIDATION
        else:
            return DatasetSplit.TEST

    def get_split_stats_distribution(self, document_ids: list[str]) -> Dict[str, int]:
        """Calculates split distribution across a set of document IDs."""
        counts = {"train": 0, "validation": 0, "test": 0}
        for doc_id in document_ids:
            split = self.assign_document_split(doc_id)
            counts[split.value] += 1
        return counts
