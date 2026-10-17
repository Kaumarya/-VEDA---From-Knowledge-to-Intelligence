"""
VEDA Corpus Manifest & Fingerprint Engine (Phase 4 — Training Corpus Architecture)

Builds, serializes, and validates the machine-readable corpus manifest (manifest.json)
and computes the canonical logical dataset fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from foundation.corpus.schemas import CorpusRecord, CorpusSource


@dataclass
class CorpusManifest:
    """Authoritative machine-readable manifest describing a sealed corpus release."""
    corpus_name: str
    corpus_version: str
    schema_version: str
    created_at: str
    pipeline_version: str
    split_seed: str
    policies: Dict[str, str]
    sources: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    artifacts: Dict[str, str]

    @property
    def content_fingerprint(self) -> str:
        return self.artifacts.get("content_fingerprint", self.artifacts.get("logical_fingerprint", ""))

    @property
    def manifest_fingerprint(self) -> str:
        return self.artifacts.get("manifest_fingerprint", "")

    @property
    def logical_fingerprint(self) -> str:
        return self.artifacts.get("logical_fingerprint", "")

    @property
    def total_documents(self) -> int:
        return self.statistics.get("total_documents", 0)

    @property
    def retained_documents(self) -> int:
        return self.statistics.get("retained_documents", 0)

    @property
    def rejected_documents(self) -> int:
        return self.statistics.get("rejected_documents", 0)

    @property
    def total_records_processed(self) -> int:
        return self.statistics.get("total_records_processed", 0)

    @property
    def retained_records(self) -> int:
        return self.statistics.get("retained_records", 0)

    @property
    def rejected_records(self) -> int:
        return self.statistics.get("rejected_records", 0)

    @property
    def duplicate_records(self) -> int:
        return self.statistics.get("duplicate_records", 0)

    @property
    def rejection_reasons(self) -> Dict[str, int]:
        return self.statistics.get("rejection_breakdown", {})

    @property
    def split_record_counts(self) -> Dict[str, int]:
        return self.statistics.get("split_counts", {})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorpusManifest:
        return cls(**data)

    @classmethod
    def from_file(cls, path: Path) -> CorpusManifest:
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def compute_content_fingerprint(records: List[CorpusRecord]) -> str:
    """Computes the canonical content fingerprint from an iterable of CorpusRecord objects."""
    if not records:
        return hashlib.sha256(b"EMPTY_CORPUS").hexdigest()
    record_digests = []
    for r in records:
        item_key = f"{r.record_id}::{r.normalized_text}::{r.split}".encode("utf-8")
        digest = hashlib.sha256(item_key).hexdigest()
        record_digests.append(f"{r.record_id}:{digest}")
    hasher = hashlib.sha256()
    for item in sorted(record_digests):
        hasher.update(item.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def compute_manifest_fingerprint(config: Dict[str, Any]) -> str:
    """Computes the canonical manifest configuration fingerprint from a configuration dictionary.

    Excludes non-deterministic or volatile fields like created_at, hostname, pid, or output paths.
    """
    excluded_keys = {"created_at", "hostname", "pid", "process_id", "temp_dir", "output_dir", "path"}
    filtered_config = {k: v for k, v in config.items() if k not in excluded_keys}
    canonical_json = json.dumps(filtered_config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ManifestBuilder:
    """
    Constructs and computes canonical metrics and logical fingerprints for CorpusManifest.
    """

    VERSION = "0.1.0"
    SCHEMA_VERSION = "0.1.0"

    def __init__(
        self,
        corpus_name: str,
        corpus_version: str = "0.1.0",
        split_seed: str = "VEDA_CORPUS_SEED_v0.1",
        train_ratio: float = 0.90,
        val_ratio: float = 0.05,
        test_ratio: float = 0.05,
        policy_versions: Optional[Dict[str, str]] = None,
    ) -> None:
        self.corpus_name = corpus_name
        self.corpus_version = corpus_version
        self.split_seed = split_seed
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.policy_versions = dict(policy_versions) if policy_versions else {
            "normalization_version": "0.1.0",
            "filtering_version": "0.1.0",
            "deduplication_version": "0.1.0",
            "segmentation_version": "0.1.0",
            "split_version": "0.1.0",
            "grouping_version": "0.1.0",
            "grouping_algorithm": "deterministic_group_hash_v1",
        }

        self._record_digests: List[str] = []
        self._sources: List[Dict[str, Any]] = []

        # Statistical counters
        self.total_documents = 0
        self.retained_documents = 0
        self.rejected_documents = 0
        self.total_records_processed = 0
        self.retained_records = 0
        self.rejected_records = 0
        self.duplicate_records = 0
        self.rejection_breakdown: Dict[str, int] = {}
        self.duplicate_breakdown: Dict[str, int] = {
            "exact_duplicates": 0,
            "normalized_duplicates": 0,
            "document_duplicates": 0,
        }
        self.split_counts: Dict[str, int] = {"train": 0, "validation": 0, "test": 0}
        self.character_counts: Dict[str, int] = {
            "total_raw_characters": 0,
            "total_normalized_characters": 0,
            "train_characters": 0,
            "validation_characters": 0,
            "test_characters": 0,
        }
        self.approx_word_counts: Dict[str, int] = {
            "total_words": 0,
            "train_words": 0,
            "validation_words": 0,
            "test_words": 0,
        }

    def register_source(self, source: CorpusSource, document_count: int) -> None:
        """Registers a data source and its processed document count."""
        self._sources.append({
            "source_id": source.source_id,
            "version": source.version,
            "license": source.license,
            "licensing_status": source.licensing_status.value,
            "source_hash": source.source_hash,
            "document_count": document_count,
        })
        self.total_documents += document_count

    def observe_record(self, record: CorpusRecord) -> None:
        """Accumulates metrics and logical fingerprint digest for an accepted record."""
        self.total_records_processed += 1
        self.retained_records += 1

        split = record.split
        self.split_counts[split] = self.split_counts.get(split, 0) + 1

        # Character counts
        self.character_counts["total_raw_characters"] += record.raw_char_count
        self.character_counts["total_normalized_characters"] += record.normalized_char_count
        split_char_key = f"{split}_characters"
        self.character_counts[split_char_key] = self.character_counts.get(split_char_key, 0) + record.normalized_char_count

        # Word counts
        words = record.approx_word_count
        self.approx_word_counts["total_words"] += words
        split_word_key = f"{split}_words"
        self.approx_word_counts[split_word_key] = self.approx_word_counts.get(split_word_key, 0) + words

        # Logical digest: hash(record_id :: normalized_text :: split)
        item_key = f"{record.record_id}::{record.normalized_text}::{record.split}".encode("utf-8")
        digest = hashlib.sha256(item_key).hexdigest()
        self._record_digests.append(f"{record.record_id}:{digest}")

    def observe_rejection(self, reason: str) -> None:
        """Tracks a non-duplicate rejected record (failed quality/language/governance)."""
        self.total_records_processed += 1
        self.rejected_records += 1
        self.rejection_breakdown[reason] = self.rejection_breakdown.get(reason, 0) + 1

    def observe_duplicate(self, dup_type: str = "record") -> None:
        """Tracks a duplicate record (exact or normalized duplicate)."""
        self.total_records_processed += 1
        self.duplicate_records += 1
        self.rejection_breakdown["DUPLICATE"] = self.rejection_breakdown.get("DUPLICATE", 0) + 1

    def observe_duplicates(self, exact: int, normalized: int, document: int) -> None:
        """Sets duplicate breakdowns."""
        self.duplicate_breakdown["exact_duplicates"] = exact
        self.duplicate_breakdown["normalized_duplicates"] = normalized
        self.duplicate_breakdown["document_duplicates"] = document

    def compute_content_fingerprint(self) -> str:
        """
        Computes the canonical content fingerprint.
        Deterministic: sorts record digests by record_id.
        """
        if not self._record_digests:
            return hashlib.sha256(b"EMPTY_CORPUS").hexdigest()

        sorted_digests = sorted(self._record_digests)
        hasher = hashlib.sha256()
        for item in sorted_digests:
            hasher.update(item.encode("utf-8"))
            hasher.update(b"\n")
        return hasher.hexdigest()

    def compute_logical_fingerprint(self) -> str:
        """Backwards-compatible alias for compute_content_fingerprint."""
        return self.compute_content_fingerprint()

    def compute_manifest_fingerprint(
        self,
        content_fingerprint: str,
        file_checksums: Dict[str, str],
    ) -> str:
        """
        Computes the canonical manifest configuration fingerprint.
        Identifies provenance, sources, versions, seed, and split configuration.
        Strictly excludes volatile runtime variables (created_at, host, pid, paths).
        """
        canonical_config = {
            "corpus_name": self.corpus_name,
            "corpus_version": self.corpus_version,
            "schema_version": self.SCHEMA_VERSION,
            "pipeline_version": self.VERSION,
            "split_seed": self.split_seed,
            "split_config": {
                "train_ratio": self.train_ratio,
                "val_ratio": self.val_ratio,
                "test_ratio": self.test_ratio,
            },
            "policies": dict(sorted(self.policy_versions.items())),
            "sources": sorted(
                [
                    {
                        "source_id": s["source_id"],
                        "version": s["version"],
                        "source_hash": s["source_hash"],
                        "license": s["license"],
                        "licensing_status": s["licensing_status"],
                    }
                    for s in self._sources
                ],
                key=lambda x: x["source_id"],
            ),
            "content_fingerprint": content_fingerprint,
            "artifact_hashes": {
                "train": file_checksums.get("train", ""),
                "validation": file_checksums.get("validation", ""),
                "test": file_checksums.get("test", ""),
                "rejections": file_checksums.get("rejections", ""),
            },
        }
        canonical_bytes = json.dumps(canonical_config, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    def build(self, file_checksums: Dict[str, str]) -> CorpusManifest:
        """Constructs the finalized CorpusManifest instance."""
        content_fp = self.compute_content_fingerprint()
        manifest_fp = self.compute_manifest_fingerprint(content_fp, file_checksums)

        artifacts: Dict[str, str] = {
            "train_file": "train.jsonl",
            "train_sha256": file_checksums.get("train", ""),
            "validation_file": "validation.jsonl",
            "validation_sha256": file_checksums.get("validation", ""),
            "test_file": "test.jsonl",
            "test_sha256": file_checksums.get("test", ""),
            "rejections_file": "rejections.jsonl",
            "rejections_sha256": file_checksums.get("rejections", ""),
            "content_fingerprint": content_fp,
            "manifest_fingerprint": manifest_fp,
            "logical_fingerprint": content_fp,  # Backwards compatibility
        }

        # Conservation law assertions
        assert self.total_documents == self.retained_documents + self.rejected_documents, (
            f"Document conservation violation: total={self.total_documents} != "
            f"retained={self.retained_documents} + rejected={self.rejected_documents}"
        )
        assert self.total_records_processed == (
            self.retained_records + self.rejected_records + self.duplicate_records
        ), (
            f"Record conservation violation: processed={self.total_records_processed} != "
            f"retained={self.retained_records} + rejected={self.rejected_records} + duplicate={self.duplicate_records}"
        )

        manifest = CorpusManifest(
            corpus_name=self.corpus_name,
            corpus_version=self.corpus_version,
            schema_version=self.SCHEMA_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            pipeline_version=self.VERSION,
            split_seed=self.split_seed,
            policies=dict(sorted(self.policy_versions.items())),
            sources=list(self._sources),
            statistics={
                "total_documents": self.total_documents,
                "retained_documents": self.retained_documents,
                "rejected_documents": self.rejected_documents,
                "total_records_processed": self.total_records_processed,
                "retained_records": self.retained_records,
                "rejected_records": self.rejected_records,
                "duplicate_records": self.duplicate_records,
                "rejection_breakdown": dict(self.rejection_breakdown),
                "duplicate_breakdown": dict(self.duplicate_breakdown),
                "split_counts": dict(self.split_counts),
                "character_counts": dict(self.character_counts),
                "approx_word_counts": dict(self.approx_word_counts),
            },
            artifacts=artifacts,
        )
        return manifest
