"""
VEDA Candidate Database Subsystem — Strongly Typed Domain Models
Phase 4.14.2
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass(frozen=True)
class CandidateSubmission:
    candidate_id: str
    source_id: str
    source_document_id: str
    original_text: str
    normalized_text: str
    raw_content_hash: str
    normalized_content_hash: str
    raw_char_count: int
    normalized_char_count: int
    approx_word_count: int
    processing_status: str = "RECEIVED"
    is_canonical: bool = True
    canonical_candidate_id: Optional[str] = None
    pipeline_version: str = "v0.4.14"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class CandidateSourceRecord:
    source_id: str
    name: str
    version: str
    licensing_status: str
    license_name: str
    training_permitted_status: str
    commercial_permitted: bool
    artifact_sha256: str
    registry_entry_sha256: str
    approval_expiration_date: Optional[str] = None
    attribution: Optional[str] = None
    sync_timestamp: Optional[str] = None


@dataclass(frozen=True)
class ProcessingDecisionRecord:
    candidate_id: str
    stage_name: str
    pipeline_version: str
    decision_outcome: str  # PASS, FAIL, QUARANTINE, MERGE
    quality_score: Optional[float] = None
    language_confidence: Optional[float] = None
    failed_metric: Optional[str] = None
    diagnostic_evidence_json: Optional[str] = None
    decision_id: Optional[int] = None
    evaluated_at: Optional[str] = None


@dataclass(frozen=True)
class DuplicateRelationshipRecord:
    candidate_id: str
    related_candidate_id: str
    relationship_type: str  # EXACT_RAW, EXACT_NORMALIZED, NEAR_DUPLICATE, SEMANTIC_CONFLICT
    detector_version: str
    similarity_score: float
    is_safe_to_merge: bool = True
    conflict_reason: Optional[str] = None
    relationship_id: Optional[int] = None
    detected_at: Optional[str] = None


@dataclass(frozen=True)
class ReviewerAccountRecord:
    reviewer_id: str
    username: str
    full_name: str
    email: str
    account_status: str = "ACTIVE"  # ACTIVE, SUSPENDED, INACTIVE, OFFBOARDED
    idp_subject_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class ReviewerRoleRecord:
    role_id: str
    role_name: str
    description: str
    can_approve_corpus: bool = True
    created_at: Optional[str] = None


@dataclass(frozen=True)
class ReviewerPublicKeyRecord:
    public_key_id: str
    reviewer_id: str
    public_key_hex: str
    algorithm: str = "Ed25519"
    key_status: str = "PENDING_ACTIVATION"  # PENDING_ACTIVATION, ACTIVE, ROTATED_RETIRED, REVOKED_COMPROMISED, REVOKED_ADMIN
    is_test_key: bool = False
    activated_at: Optional[str] = None
    valid_until: Optional[str] = None
    revoked_at: Optional[str] = None
    revocation_reason: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class AuthenticationEventRecord:
    auth_event_id: str
    reviewer_id: str
    auth_method: str
    client_host: str
    auth_status: str
    session_expires_at: str
    created_at: Optional[str] = None


@dataclass(frozen=True)
class ApprovalHistoryRecord:
    candidate_id: str
    decision_id: str
    reviewer_id: str
    reviewer_role: str
    public_key_id: str
    auth_event_id: str
    old_status: str
    new_status: str
    decision_reason: str
    canonical_payload_json: str
    canonical_payload_sha256: str
    signature_ed25519: str
    payload_schema_version: str = "1.0"
    verification_status: str = "VERIFIED_VALID"
    history_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class QuarantineCaseRecord:
    case_id: str
    candidate_id: str
    quarantine_reason: str
    quarantine_category: str
    diagnostic_evidence_json: str
    pipeline_version: str
    review_due_at: str
    assigned_role: str
    quarantined_at: Optional[str] = None
    last_reminder_at: Optional[str] = None
    escalated_at: Optional[str] = None
    escalation_level: str = "STANDARD"
    assigned_reviewer_id: Optional[str] = None
    resolution_decision_id: Optional[str] = None
    resolution_evidence_reference: Optional[str] = None
    resolved_at: Optional[str] = None


@dataclass(frozen=True)
class RetentionDecisionRecord:
    candidate_id: str
    decision_type: str
    legal_basis: str
    governance_notes: str
    authorized_by: str
    decision_id: Optional[int] = None
    enacted_at: Optional[str] = None
    review_deadline: Optional[str] = None


@dataclass(frozen=True)
class ExportBatchRecord:
    batch_id: str
    corpus_version: str
    target_split: str
    record_count: int = 0
    export_status: str = "PREPARING"
    manifest_sha256: Optional[str] = None
    output_path: Optional[str] = None
    created_at: Optional[str] = None
    committed_at: Optional[str] = None

