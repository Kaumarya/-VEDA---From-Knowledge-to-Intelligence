"""
VEDA Deduplication Engine (Phase 4 — Training Corpus Architecture)

Implements the multi-tiered deduplication framework defined in docs/corpus_split_policy.md.
Maintains exact distinction between raw exact duplicates, normalized duplicates,
and document collisions, while tracking deduplication statistics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from foundation.corpus.schemas import CorpusDocument


@dataclass
class DeduplicationStats:
    """Detailed statistics tracked by the deduplication engine."""
    documents_seen: int = 0
    document_duplicates: int = 0
    records_seen: int = 0
    exact_duplicates: int = 0
    normalized_duplicates: int = 0
    retained_records: int = 0

    @property
    def total_duplicates(self) -> int:
        return self.exact_duplicates + self.normalized_duplicates

    def to_dict(self) -> Dict[str, int]:
        return {
            "documents_seen": self.documents_seen,
            "document_duplicates": self.document_duplicates,
            "records_seen": self.records_seen,
            "exact_duplicates": self.exact_duplicates,
            "normalized_duplicates": self.normalized_duplicates,
            "retained_records": self.retained_records,
            "total_duplicates": self.total_duplicates,
        }


class DeduplicationEngine:
    """
    Multi-tiered deduplication tracker and filter.
    """

    VERSION = "0.1.0"

    def __init__(self) -> None:
        self.stats = DeduplicationStats()
        # Hashes of raw documents seen: doc_hash -> canonical document_id
        self._doc_hashes: Dict[str, str] = {}
        # Hashes of raw text: raw_sha256 -> canonical record_id
        self._raw_hashes: Dict[str, str] = {}
        # Hashes of normalized text: norm_sha256 -> canonical record_id
        self._norm_hashes: Dict[str, str] = {}
        # Map of canonical_record_id -> list of contributing source/record provenance entries
        self._contributors: Dict[str, List[Dict[str, Any]]] = {}

    def check_and_register_document(self, document: CorpusDocument) -> Tuple[bool, Optional[str]]:
        """
        Checks if a document is a duplicate of a previously seen document.
        Returns (is_duplicate, canonical_doc_id).
        """
        self.stats.documents_seen += 1
        doc_hash = document.document_hash

        if doc_hash in self._doc_hashes:
            self.stats.document_duplicates += 1
            return True, self._doc_hashes[doc_hash]

        self._doc_hashes[doc_hash] = document.document_id
        return False, None

    def check_and_register_record(
        self,
        record_id: str,
        raw_text: str,
        normalized_text: str,
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        attribution: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluates a candidate record for exact or normalized duplication.
        Preserves provenance of contributing sources even when duplicate records are dropped.

        Returns:
            Tuple[is_duplicate, duplicate_of_id, dup_type]
            where dup_type is 'exact', 'normalized', or None.
        """
        self.stats.records_seen += 1

        raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        norm_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

        contributor_entry = {
            "record_id": record_id,
            "source_id": source_id,
            "document_id": document_id,
            "attribution": attribution,
        }

        # Check exact raw duplicate first
        if raw_hash in self._raw_hashes:
            canonical_id = self._raw_hashes[raw_hash]
            self.stats.exact_duplicates += 1
            contributor_entry["dup_type"] = "exact"
            self._contributors.setdefault(canonical_id, []).append(contributor_entry)
            return True, canonical_id, "exact"

        # Check normalized duplicate
        if norm_hash in self._norm_hashes:
            canonical_id = self._norm_hashes[norm_hash]
            self.stats.normalized_duplicates += 1
            contributor_entry["dup_type"] = "normalized"
            self._contributors.setdefault(canonical_id, []).append(contributor_entry)
            return True, canonical_id, "normalized"

        # New unique record
        self._raw_hashes[raw_hash] = record_id
        self._norm_hashes[norm_hash] = record_id
        self.stats.retained_records += 1
        contributor_entry["dup_type"] = "canonical"
        self._contributors[record_id] = [contributor_entry]
        return False, None, None

    def get_contributors(self, canonical_record_id: str) -> List[Dict[str, Any]]:
        """Returns all contributing records, sources, and attributions for a canonical record."""
        return list(self._contributors.get(canonical_record_id, []))

    def reset(self) -> None:
        """Resets engine state for a clean pipeline run."""
        self.stats = DeduplicationStats()
        self._doc_hashes.clear()
        self._raw_hashes.clear()
        self._norm_hashes.clear()
        self._contributors.clear()
