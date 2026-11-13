"""
VEDA Candidate Database Subsystem
Phase 4.14.2 — Complete Candidate Database Architecture
Provides candidate text ingestion, deterministic normalization, processing pipeline integration,
cryptographic reviewer governance (Ed25519/RFC 8785), human approval workflows, non-mutating quarantine,
legal retention holds, and fail-closed export eligibility gating.
"""

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager, Migration
from foundation.candidates.models import (
    CandidateSubmission,
    CandidateSourceRecord,
    ProcessingDecisionRecord,
    DuplicateRelationshipRecord,
    ReviewerAccountRecord,
    ReviewerRoleRecord,
    ReviewerPublicKeyRecord,
    AuthenticationEventRecord,
    ApprovalHistoryRecord,
    QuarantineCaseRecord,
    RetentionDecisionRecord,
    ExportBatchRecord,
)
from foundation.candidates.state_machine import (
    CandidateLifecycleStateMachine,
    VALID_LIFECYCLE_STATES,
    PERMITTED_TRANSITIONS,
)
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.processing import CandidateProcessor
from foundation.candidates.signatures import (
    Ed25519SignatureService,
    canonicalize_json,
    compute_payload_hash,
)
from foundation.candidates.authentication import (
    IReviewerAuthenticator,
    LocalSecureAuthenticator,
)
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.retention import RetentionManager
from foundation.candidates.revocation import RevocationManager
from foundation.candidates.export_eligibility import ExportEligibilityService
from foundation.candidates.exceptions import (
    CandidateDatabaseError,
    DatabaseConnectionError,
    ConfigurationError,
    MigrationError,
    MigrationChecksumMismatchError,
    UnsupportedSchemaVersionError,
    ValidationError,
    EmptySubmissionError,
    DuplicateSubmissionError,
    InvalidStateTransitionError,
    ReviewerError,
    ReviewerNotFoundError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    AuthenticationError,
    CryptographicError,
    InvalidSignatureError,
    KeyNotFoundError,
    KeyRevokedError,
    KeyExpiredError,
    QuarantineError,
    QuarantineTimeoutMutationError,
    UnauthorizedQuarantineResolutionError,
    ExportEligibilityError,
    GovernancePreflightError,
    DuplicateExportError,
    RetentionError,
    ContentRedactedError,
)

__all__ = [
    # Config & Connection
    "CandidateDatabaseConfig",
    "CandidateDatabaseConnection",
    # Migrations
    "MigrationManager",
    "Migration",
    # Models
    "CandidateSubmission",
    "CandidateSourceRecord",
    "ProcessingDecisionRecord",
    "DuplicateRelationshipRecord",
    "ReviewerAccountRecord",
    "ReviewerRoleRecord",
    "ReviewerPublicKeyRecord",
    "AuthenticationEventRecord",
    "ApprovalHistoryRecord",
    "QuarantineCaseRecord",
    "RetentionDecisionRecord",
    "ExportBatchRecord",
    # State Machine
    "CandidateLifecycleStateMachine",
    "VALID_LIFECYCLE_STATES",
    "PERMITTED_TRANSITIONS",
    # Repository & Processing
    "CandidateRepository",
    "CandidateProcessor",
    # Signatures & Auth
    "Ed25519SignatureService",
    "canonicalize_json",
    "compute_payload_hash",
    "IReviewerAuthenticator",
    "LocalSecureAuthenticator",
    # Services
    "ReviewerService",
    "ApprovalService",
    "QuarantineManager",
    "RetentionManager",
    "RevocationManager",
    "ExportEligibilityService",
    # Exceptions
    "CandidateDatabaseError",
    "DatabaseConnectionError",
    "ConfigurationError",
    "MigrationError",
    "MigrationChecksumMismatchError",
    "UnsupportedSchemaVersionError",
    "ValidationError",
    "EmptySubmissionError",
    "DuplicateSubmissionError",
    "InvalidStateTransitionError",
    "ReviewerError",
    "ReviewerNotFoundError",
    "ReviewerInactiveError",
    "ReviewerUnauthorizedError",
    "AuthenticationError",
    "CryptographicError",
    "InvalidSignatureError",
    "KeyNotFoundError",
    "KeyRevokedError",
    "KeyExpiredError",
    "QuarantineError",
    "QuarantineTimeoutMutationError",
    "UnauthorizedQuarantineResolutionError",
    "ExportEligibilityError",
    "GovernancePreflightError",
    "DuplicateExportError",
    "RetentionError",
    "ContentRedactedError",
]
