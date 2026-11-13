"""
VEDA Candidate Database Subsystem — Domain Exceptions
Phase 4.14.2
"""

class CandidateDatabaseError(Exception):
    """Base exception for all candidate database errors."""
    pass


# Connection and Configuration Exceptions
class DatabaseConnectionError(CandidateDatabaseError):
    """Raised when connecting to or configuring the SQLite database fails."""
    pass


class ConfigurationError(CandidateDatabaseError):
    """Raised when candidate database configuration is invalid."""
    pass


# Migration Exceptions
class MigrationError(CandidateDatabaseError):
    """Base exception for migration failures."""
    pass


class MigrationChecksumMismatchError(MigrationError):
    """Raised when an already-applied migration has an altered checksum."""
    pass


class UnsupportedSchemaVersionError(MigrationError):
    """Raised when the database has a future schema version unsupported by this code."""
    pass


# Validation & Ingestion Exceptions
class ValidationError(CandidateDatabaseError):
    """Raised when submitted candidate text or metadata fails validation."""
    pass


class EmptySubmissionError(ValidationError):
    """Raised when submitted text is empty or whitespace-only."""
    pass


class DuplicateSubmissionError(CandidateDatabaseError):
    """Raised when an identical candidate is submitted where uniqueness is required."""
    pass


# State Machine Exceptions
class InvalidStateTransitionError(CandidateDatabaseError):
    """Raised when an illegal candidate lifecycle transition is attempted."""
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        msg = f"Invalid state transition: {from_state} -> {to_state}."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


# Reviewer & Governance Exceptions
class ReviewerError(CandidateDatabaseError):
    """Base exception for reviewer management errors."""
    pass


class ReviewerNotFoundError(ReviewerError):
    """Raised when a specified reviewer does not exist."""
    pass


class ReviewerInactiveError(ReviewerError):
    """Raised when an inactive, suspended, or offboarded reviewer attempts an action."""
    pass


class ReviewerUnauthorizedError(ReviewerError):
    """Raised when a reviewer lacks the required role for an approval or resolution."""
    pass


class AuthenticationError(CandidateDatabaseError):
    """Raised when reviewer authentication fails."""
    pass


# Cryptography & Signature Exceptions
class CryptographicError(CandidateDatabaseError):
    """Base exception for cryptographic signature errors."""
    pass


class InvalidSignatureError(CryptographicError):
    """Raised when Ed25519 signature verification fails."""
    pass


class KeyNotFoundError(CryptographicError):
    """Raised when a referenced public or private key is not found."""
    pass


class KeyRevokedError(CryptographicError):
    """Raised when an operation attempts to use a revoked signing key."""
    pass


class KeyExpiredError(CryptographicError):
    """Raised when an operation attempts to use a key outside its validity window."""
    pass


# Quarantine Exceptions
class QuarantineError(CandidateDatabaseError):
    """Base exception for quarantine management errors."""
    pass


class QuarantineTimeoutMutationError(QuarantineError):
    """Raised when a timeout or background job attempts to mutate a quarantined candidate's status."""
    pass


class UnauthorizedQuarantineResolutionError(QuarantineError):
    """Raised when quarantine resolution lacks required human authorization or signature."""
    pass


# Export Exceptions
class ExportEligibilityError(CandidateDatabaseError):
    """Raised when a candidate fails the export eligibility predicate."""
    pass


class GovernancePreflightError(ExportEligibilityError):
    """Raised when source governance or license preflight fails."""
    pass


class DuplicateExportError(ExportEligibilityError):
    """Raised when attempting to export an already-exported candidate into the same release split."""
    pass


# Retention Exceptions
class RetentionError(CandidateDatabaseError):
    """Base exception for legal retention errors."""
    pass


class ContentRedactedError(RetentionError):
    """Raised when attempting to read text that has been legally redacted or expunged."""
    pass

