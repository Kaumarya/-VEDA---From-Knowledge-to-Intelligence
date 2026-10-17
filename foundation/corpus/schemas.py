"""
VEDA Corpus Schemas & Data Contracts (Phase 4 — Training Corpus Architecture)

Defines structured schema dataclasses representing the six conceptual layers:
Corpus, Source, Document, TextSegment, Sentence, and CorpusRecord, along with
Provenance, Rejection Tracking, and Governance contracts.
"""

from __future__ import annotations

import enum
import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class LicensingStatus(str, enum.Enum):
    """Authoritative data governance licensing status for training sources."""
    VERIFIED_PERMITTED = "VERIFIED PERMITTED"
    REQUIRES_REVIEW = "REQUIRES REVIEW"
    UNKNOWN = "UNKNOWN"
    EXCLUDED = "EXCLUDED"

    @classmethod
    def _missing_(cls, value: object) -> Optional[LicensingStatus]:
        if isinstance(value, str):
            normalized = value.replace("_", " ").strip().upper()
            for member in cls:
                if member.value == normalized or member.name == value.strip().upper():
                    return member
        return None


class RejectionReason(str, enum.Enum):
    """Controlled taxonomy of quality, language, and structural rejection reasons."""
    EMPTY_TEXT = "EMPTY_TEXT"
    TOO_SHORT_CHARS = "TOO_SHORT_CHARS"
    TOO_SHORT_WORDS = "TOO_SHORT_WORDS"
    TOO_LONG_CHARS = "TOO_LONG_CHARS"
    LOW_ALPHA_RATIO = "LOW_ALPHA_RATIO"
    HIGH_SYMBOL_RATIO = "HIGH_SYMBOL_RATIO"
    HIGH_UNREGISTERED_RATIO = "HIGH_UNREGISTERED_RATIO"
    REPEATED_CHARS = "REPEATED_CHARS"
    REPEATED_WORDS = "REPEATED_WORDS"
    NO_ENGLISH_STOPWORDS = "NO_ENGLISH_STOPWORDS"
    BOILERPLATE_CONTENT = "BOILERPLATE_CONTENT"
    NON_ENGLISH_SCRIPT = "NON_ENGLISH_SCRIPT"
    GOVERNANCE_BLOCKED = "GOVERNANCE_BLOCKED"
    DUPLICATE = "DUPLICATE"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"


class DatasetSplit(str, enum.Enum):
    """Dataset partition assignment."""
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True)
class CorpusSource:
    """
    Authoritative origin contract for an external archive or dataset.
    Answers: 'Where did this data originate and are we legally permitted to train on it?'
    """
    source_id: str
    name: str
    version: str
    url_or_path: str
    acquisition_date: str
    source_hash: str
    license: str
    licensing_status: LicensingStatus
    language: str = "en"
    source_type: str = "book"  # book, encyclopedia, essay, educational, news, synthetic
    attribution: Optional[str] = None
    description: Optional[str] = None
    # Phase 4.2 Extended Governance Attributes
    publisher: Optional[str] = None
    license_url: Optional[str] = None
    attribution_requirements: Optional[str] = None
    redistribution_requirements: Optional[str] = None
    commercial_permitted: Optional[bool] = None
    training_permitted_status: Optional[str] = None  # EXPLICITLY_PERMITTED, PROHIBITED, UNCLEAR
    privacy_considerations: Optional[str] = None
    expected_size_mb: Optional[float] = None
    format: Optional[str] = None  # jsonl, epub, txt, xml
    approx_doc_count: Optional[int] = None
    checksum_procedure: Optional[str] = None
    reviewer_notes: Optional[str] = None
    unresolved_questions: Optional[str] = None
    # Phase 4.2.1 Work-Level Governance & Auditable Evidence
    # Phase 4.2.1 Work-Level Governance & Auditable Evidence
    work_level_scope: Optional[str] = None
    jurisdiction_limitations: Optional[str] = None
    modification_conditions: Optional[str] = None
    access_api_terms: Optional[str] = None
    mixed_license_risks: Optional[str] = None
    evidence_retrieval_date: Optional[str] = None
    evidence_checksum: Optional[str] = None
    reviewer_identity: Optional[str] = None
    review_date: Optional[str] = None
    re_review_triggers: Optional[str] = None
    approval_expiration_date: Optional[str] = None
    # Phase 4.2.2 Accuracy & Evidence-Integrity Fields
    artifact_sha256: Optional[str] = None
    license_evidence_sha256: Optional[str] = None
    registry_entry_sha256: Optional[str] = None

    # Canonical empty-file SHA-256 constant
    EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z0-9_.-]+$", self.source_id):
            raise ValueError(f"Invalid source_id {self.source_id!r}: must match ^[a-z0-9_.-]+$")
        if not self.name or not self.version:
            raise ValueError("source name and version must be non-empty")
        if not isinstance(self.licensing_status, LicensingStatus):
            # Allow string coercion if valid enum value
            resolved = LicensingStatus(self.licensing_status)
            object.__setattr__(self, "licensing_status", resolved)

        # Synchronize artifact_sha256 with source_hash
        eff_artifact_sha256 = self.artifact_sha256 or self.source_hash
        object.__setattr__(self, "artifact_sha256", eff_artifact_sha256)
        object.__setattr__(self, "source_hash", eff_artifact_sha256)

        # Synchronize license_evidence_sha256 with evidence_checksum
        eff_evidence_sha256 = self.license_evidence_sha256 or self.evidence_checksum
        object.__setattr__(self, "license_evidence_sha256", eff_evidence_sha256)
        object.__setattr__(self, "evidence_checksum", eff_evidence_sha256)

        # Validate artifact_sha256 / source_hash
        if self.artifact_sha256 == "NOT_VERIFIED":
            pass  # Explicitly unacquired artifact
        else:
            if len(self.artifact_sha256) != 64 or not all(c in "0123456789abcdef" for c in self.artifact_sha256.lower()):
                raise ValueError(f"source_hash must be a valid 64-char hex SHA-256 string, got {self.artifact_sha256!r}")
            # Reject empty-artifact SHA-256 placeholder where a nonempty artifact is required
            if self.artifact_sha256.lower() == self.EMPTY_FILE_SHA256:
                if (self.expected_size_mb is not None and self.expected_size_mb > 0) or (self.format and self.format != "empty"):
                    raise ValueError("Empty-artifact SHA-256 placeholder detected for non-empty source artifact")

        # Validate license_evidence_sha256 / evidence_checksum
        if self.license_evidence_sha256 is not None:
            if self.license_evidence_sha256 == "NOT_VERIFIED":
                pass
            else:
                if len(self.license_evidence_sha256) != 64 or not all(c in "0123456789abcdef" for c in self.license_evidence_sha256.lower()):
                    raise ValueError(f"evidence_checksum must be a valid 64-char hex SHA-256 string, got {self.license_evidence_sha256!r}")

    @property
    def is_approval_stale(self) -> bool:
        """Returns True if the approval expiration date has passed."""
        if not self.approval_expiration_date:
            return False
        try:
            # Parse ISO date (e.g. '2026-10-15' or with time)
            exp_str = self.approval_expiration_date
            if "T" in exp_str:
                exp = datetime.fromisoformat(exp_str)
            else:
                exp = datetime.strptime(exp_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return now > exp
        except Exception:
            return True

    @property
    def is_permitted_for_training(self) -> bool:
        """Data governance check: only VERIFIED PERMITTED sources with active non-stale approval and verified artifact may enter training splits."""
        if self.licensing_status != LicensingStatus.VERIFIED_PERMITTED:
            return False
        if self.is_approval_stale:
            return False
        if self.artifact_sha256 == "NOT_VERIFIED":
            return False
        return True

    def verify_artifact_bytes(self, file_path: Union[str, Path]) -> bool:
        """
        Verifies that the physical file bytes match the declared artifact_sha256.
        Raises FileNotFoundError if file is missing.
        Raises ValueError if artifact_sha256 is 'NOT_VERIFIED' or if checksum mismatches.
        """
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"Artifact file not found: {p}")
        if self.artifact_sha256 == "NOT_VERIFIED":
            raise ValueError(f"Source {self.source_id!r} artifact is NOT_VERIFIED; cannot verify file bytes")
        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        if actual_hash.lower() != self.artifact_sha256.lower():
            raise ValueError(
                f"Artifact checksum mismatch for {self.source_id}: "
                f"declared {self.artifact_sha256}, actual {actual_hash}"
            )
        return True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["licensing_status"] = self.licensing_status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorpusSource:
        status_val = data["licensing_status"]
        status = LicensingStatus(status_val) if not isinstance(status_val, LicensingStatus) else status_val
        return cls(
            source_id=data["source_id"],
            name=data["name"],
            version=data["version"],
            url_or_path=data["url_or_path"],
            acquisition_date=data["acquisition_date"],
            source_hash=data.get("artifact_sha256") or data["source_hash"],
            license=data["license"],
            licensing_status=status,
            language=data.get("language", "en"),
            source_type=data.get("source_type", "book"),
            attribution=data.get("attribution"),
            description=data.get("description"),
            publisher=data.get("publisher"),
            license_url=data.get("license_url"),
            attribution_requirements=data.get("attribution_requirements"),
            redistribution_requirements=data.get("redistribution_requirements"),
            commercial_permitted=data.get("commercial_permitted"),
            training_permitted_status=data.get("training_permitted_status"),
            privacy_considerations=data.get("privacy_considerations"),
            expected_size_mb=data.get("expected_size_mb"),
            format=data.get("format"),
            approx_doc_count=data.get("approx_doc_count"),
            checksum_procedure=data.get("checksum_procedure"),
            reviewer_notes=data.get("reviewer_notes"),
            unresolved_questions=data.get("unresolved_questions"),
            work_level_scope=data.get("work_level_scope"),
            jurisdiction_limitations=data.get("jurisdiction_limitations"),
            modification_conditions=data.get("modification_conditions"),
            access_api_terms=data.get("access_api_terms"),
            mixed_license_risks=data.get("mixed_license_risks"),
            evidence_retrieval_date=data.get("evidence_retrieval_date"),
            evidence_checksum=data.get("license_evidence_sha256") or data.get("evidence_checksum"),
            reviewer_identity=data.get("reviewer_identity"),
            review_date=data.get("review_date"),
            re_review_triggers=data.get("re_review_triggers"),
            approval_expiration_date=data.get("approval_expiration_date"),
            artifact_sha256=data.get("artifact_sha256") or data.get("source_hash"),
            license_evidence_sha256=data.get("license_evidence_sha256") or data.get("evidence_checksum"),
            registry_entry_sha256=data.get("registry_entry_sha256"),
        )



@dataclass
class CorpusDocument:
    """
    Coherent authorial unit (book, article, essay) from a single source.
    """
    document_id: str
    source_id: str
    raw_text: str
    title: Optional[str] = None
    author: Optional[str] = None
    group_id: Optional[str] = None  # Related-work grouping identifier to prevent train/test leakage
    raw_char_count: int = field(init=False)
    document_hash: str = field(init=False)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.document_id:
            raise ValueError("document_id must not be empty")
        if not self.source_id:
            raise ValueError("source_id must not be empty")
        if not isinstance(self.raw_text, str):
            raise TypeError("raw_text must be a string")
        if not self.group_id:
            meta_group = self.metadata.get("group_id") or self.metadata.get("work_id")
            self.group_id = str(meta_group) if meta_group else self.document_id
        self.raw_char_count = len(self.raw_text)
        self.document_hash = hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "author": self.author,
            "group_id": self.group_id,
            "raw_text": self.raw_text,
            "raw_char_count": self.raw_char_count,
            "document_hash": self.document_hash,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorpusDocument:
        doc = cls(
            document_id=data["document_id"],
            source_id=data["source_id"],
            raw_text=data["raw_text"],
            title=data.get("title"),
            author=data.get("author"),
            group_id=data.get("group_id"),
            metadata=dict(data.get("metadata", {})),
        )
        return doc


@dataclass(frozen=True)
class TextSegment:
    """
    Structural section or paragraph extracted from a parent Document.
    """
    segment_id: str
    document_id: str
    segment_index: int
    raw_text: str
    start_char_offset: int
    end_char_offset: int
    segment_type: str = "paragraph"  # paragraph, heading, list_item, quote, table_row

    def __post_init__(self) -> None:
        if self.start_char_offset < 0 or self.end_char_offset < self.start_char_offset:
            raise ValueError(
                f"Invalid offsets [{self.start_char_offset}:{self.end_char_offset}]"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sentence:
    """Single grammatical sentence within a segment."""
    sentence_id: str
    segment_id: str
    sentence_index: int
    raw_text: str
    start_char_offset: int
    end_char_offset: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecordProvenance:
    """End-to-end lineage tracing for a training record back to source."""
    source_id: str
    document_id: str
    segment_index: int
    start_char_offset: int
    end_char_offset: int
    normalizer_version: str = "0.1.0"
    filter_version: str = "0.1.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CorpusRecord:
    """
    The canonical atomic training record consumed by tokenizer and model.
    Preserves raw_text, normalized_text, provenance, quality score, and split.
    """
    record_id: str
    document_id: str
    source_id: str
    segment_index: int
    raw_text: str
    normalized_text: str
    raw_char_count: int
    normalized_char_count: int
    approx_word_count: int
    quality_score: float
    is_duplicate: bool
    split: str  # train, validation, test
    corpus_version: str
    provenance: RecordProvenance
    language: str = "en"
    duplicate_of_id: Optional[str] = None
    group_id: Optional[str] = None
    contributing_sources: List[str] = field(default_factory=list)
    attribution_notices: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must not be empty")
        if self.raw_char_count != len(self.raw_text):
            raise ValueError(f"raw_char_count {self.raw_char_count} != len(raw_text) {len(self.raw_text)}")
        if self.normalized_char_count != len(self.normalized_text):
            raise ValueError(
                f"normalized_char_count {self.normalized_char_count} != len(normalized_text) {len(self.normalized_text)}"
            )
        if self.split not in ("train", "validation", "test"):
            raise ValueError(f"Invalid split {self.split!r}: must be train, validation, or test")
        if self.is_duplicate and not self.duplicate_of_id:
            raise ValueError("duplicate_of_id must be populated if is_duplicate is True")
        if not self.contributing_sources:
            self.contributing_sources = [self.source_id]
        if not self.group_id:
            self.group_id = self.document_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "segment_index": self.segment_index,
            "language": self.language,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "raw_char_count": self.raw_char_count,
            "normalized_char_count": self.normalized_char_count,
            "approx_word_count": self.approx_word_count,
            "quality_score": round(self.quality_score, 4),
            "is_duplicate": self.is_duplicate,
            "duplicate_of_id": self.duplicate_of_id,
            "split": self.split,
            "corpus_version": self.corpus_version,
            "provenance": self.provenance.to_dict(),
            "group_id": self.group_id,
            "contributing_sources": list(self.contributing_sources),
            "attribution_notices": list(self.attribution_notices),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorpusRecord:
        prov_data = data["provenance"]
        provenance = RecordProvenance(**prov_data) if isinstance(prov_data, dict) else prov_data
        return cls(
            record_id=data["record_id"],
            document_id=data["document_id"],
            source_id=data["source_id"],
            segment_index=data["segment_index"],
            language=data.get("language", "en"),
            raw_text=data["raw_text"],
            normalized_text=data["normalized_text"],
            raw_char_count=data["raw_char_count"],
            normalized_char_count=data["normalized_char_count"],
            approx_word_count=data["approx_word_count"],
            quality_score=float(data["quality_score"]),
            is_duplicate=bool(data["is_duplicate"]),
            duplicate_of_id=data.get("duplicate_of_id"),
            split=data["split"],
            corpus_version=data["corpus_version"],
            provenance=provenance,
            group_id=data.get("group_id"),
            contributing_sources=list(data.get("contributing_sources", [data["source_id"]])),
            attribution_notices=list(data.get("attribution_notices", [])),
        )


@dataclass(frozen=True)
class RejectionRecord:
    """
    Structured ledger entry recording when and why text was rejected.
    Preserves provenance for auditing without polluting the training corpus.
    """
    record_id: str
    document_id: str
    source_id: str
    rejection_reason: RejectionReason
    rejection_stage: str  # governance, normalization, filtering, deduplication
    raw_text_sample: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "rejection_reason": self.rejection_reason.value if isinstance(self.rejection_reason, RejectionReason) else str(self.rejection_reason),
            "rejection_stage": self.rejection_stage,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold_value": self.threshold_value,
            "raw_text_sample": self.raw_text_sample[:100],
            "created_at": self.created_at,
        }
