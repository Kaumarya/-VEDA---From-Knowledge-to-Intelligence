"""
VEDA Candidate Database Subsystem — Quarantine Case Management & Human Resolution
Phase 4.14.2
Enforces non-mutating escalations and 100% human resolution with Ed25519 signatures.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.signatures import (
    canonicalize_json,
    compute_payload_hash,
    Ed25519SignatureService,
)
from foundation.candidates.models import QuarantineCaseRecord, ApprovalHistoryRecord
from foundation.candidates.exceptions import (
    QuarantineError,
    QuarantineTimeoutMutationError,
    UnauthorizedQuarantineResolutionError,
    ReviewerUnauthorizedError,
    ReviewerInactiveError,
    KeyRevokedError,
    KeyExpiredError,
    ValidationError,
)


class QuarantineManager:
    """
    Manages quarantine lifecycle, monitoring reminders, non-mutating escalations,
    and cryptographically verified human resolutions.
    """

    def __init__(self, connection: CandidateDatabaseConnection, repository: CandidateRepository, reviewer_service: ReviewerService):
        self.conn = connection
        self.repo = repository
        self.reviewers = reviewer_service

    def get_case(self, case_id: str) -> Optional[QuarantineCaseRecord]:
        """Retrieves a quarantine case by case_id."""
        row = self.conn.fetchone("SELECT * FROM quarantine_cases WHERE case_id = ?;", (case_id,))
        if not row:
            return None
        return QuarantineCaseRecord(
            case_id=row["case_id"],
            candidate_id=row["candidate_id"],
            quarantine_reason=row["quarantine_reason"],
            quarantine_category=row["quarantine_category"],
            diagnostic_evidence_json=row["diagnostic_evidence_json"],
            pipeline_version=row["pipeline_version"],
            quarantined_at=row["quarantined_at"],
            review_due_at=row["review_due_at"],
            last_reminder_at=row["last_reminder_at"],
            escalated_at=row["escalated_at"],
            escalation_level=row["escalation_level"],
            assigned_reviewer_id=row["assigned_reviewer_id"],
            assigned_role=row["assigned_role"],
            resolution_decision_id=row["resolution_decision_id"],
            resolution_evidence_reference=row["resolution_evidence_reference"],
            resolved_at=row["resolved_at"],
        )

    def get_case_for_candidate(self, candidate_id: str) -> Optional[QuarantineCaseRecord]:
        """Retrieves the active quarantine case for a candidate."""
        row = self.conn.fetchone("SELECT * FROM quarantine_cases WHERE candidate_id = ? ORDER BY quarantined_at DESC LIMIT 1;", (candidate_id,))
        if not row:
            return None
        return self.get_case(row["case_id"])

    def list_open_cases(self) -> List[QuarantineCaseRecord]:
        """Lists all unresolved quarantine cases."""
        rows = self.conn.fetchall("SELECT case_id FROM quarantine_cases WHERE resolution_decision_id IS NULL ORDER BY review_due_at ASC;")
        return [self.get_case(r["case_id"]) for r in rows if r["case_id"]]

    def send_reminder(self, case_id: str) -> None:
        """
        Records a reminder timestamp. Strictly NON-MUTATING on candidate status.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute("UPDATE quarantine_cases SET last_reminder_at = ? WHERE case_id = ?;", (now_iso, case_id))

    def escalate_case(self, case_id: str, level: str = "ESCALATED_30_DAYS") -> None:
        """
        Flags case as escalated after 30 days. Strictly NON-MUTATING on candidate status.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                "UPDATE quarantine_cases SET escalated_at = ?, escalation_level = ? WHERE case_id = ?;",
                (now_iso, level, case_id),
            )

    def resolve_quarantine(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        resolution_action: str,  # RELEASED_TO_PENDING, REJECTED, APPROVED
        resolution_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        evidence_reference: str = "",
        pipeline_version: str = "v0.4.14",
    ) -> QuarantineCaseRecord:
        """
        Executes explicit, cryptographically signed human resolution of a quarantine case.
        Permitted actions: RELEASED_TO_PENDING, REJECTED, APPROVED.
        Fails closed on missing authorization or invalid signature.
        """
        case = self.get_case(case_id)
        if not case:
            raise ValidationError(f"Quarantine case '{case_id}' not found.")
        if case.resolution_decision_id is not None:
            raise ValidationError(f"Quarantine case '{case_id}' is already resolved.")

        cand = self.repo.get_candidate(case.candidate_id)
        if not cand or cand.processing_status != "QUARANTINED":
            raise ValidationError(f"Candidate '{case.candidate_id}' is not in QUARANTINED status.")

        # Reviewer checks
        rev = self.reviewers.get_reviewer(reviewer_id)
        if not rev or rev.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' not active.")

        if not self.reviewers.has_role(reviewer_id, reviewer_role):
            raise ReviewerUnauthorizedError(f"Reviewer '{reviewer_id}' lacks role '{reviewer_role}'.")

        # Key checks
        key = self.reviewers.get_public_key(public_key_id)
        if not key or key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError("Public key not active.")

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        if key.activated_at and now_iso < key.activated_at:
            raise KeyExpiredError("Signing timestamp is prior to key activation.")
        if key.valid_until and now_iso > key.valid_until:
            raise KeyExpiredError(f"Key '{public_key_id}' has expired/rotated on {key.valid_until}.")
        if key.revoked_at and now_iso >= key.revoked_at:
            raise KeyRevokedError(f"Key '{public_key_id}' was revoked on {key.revoked_at}.")

        src = self.repo.get_source(cand.source_id)
        artifact_hash = src.artifact_sha256 if src else "0" * 64

        # Map resolution action to new status
        if resolution_action == "RELEASED_TO_PENDING":
            new_status = "APPROVAL_PENDING"
            decision_outcome = "RELEASED_TO_PENDING"
        elif resolution_action == "REJECTED":
            new_status = "REJECTED"
            decision_outcome = "REJECTED"
        elif resolution_action == "APPROVED":
            new_status = "APPROVED"
            decision_outcome = "APPROVED"
        else:
            raise ValidationError(f"Invalid quarantine resolution action: {resolution_action}")

        # Build canonical payload with quarantine_case_id binding
        decision_id = f"urn:uuid:{uuid.uuid4()}"
        payload_dict = Ed25519SignatureService.build_canonical_approval_payload(
            candidate_id=cand.candidate_id,
            decision_id=decision_id,
            decision=decision_outcome,
            decision_reason=resolution_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=artifact_hash,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
            quarantine_case_id=case_id,
        )
        canonical_bytes = canonicalize_json(payload_dict)
        payload_hash = compute_payload_hash(canonical_bytes)
        canonical_json_str = canonical_bytes.decode("utf-8")

        # Sign or verify signature
        if private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either private_key_pem or provided_signature_hex must be supplied.")

        Ed25519SignatureService.verify(key.public_key_hex, canonical_bytes, signature_hex)

        # Atomic commit: approval_history -> quarantine_cases -> candidate_submissions
        with self.conn.transaction() as c:
            # 1. approval_history
            c.execute(
                """
                INSERT INTO approval_history (
                    candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                    old_status, new_status, decision_reason, canonical_payload_json,
                    canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'QUARANTINED', ?, ?, ?, ?, ?, '1.0', 'VERIFIED_VALID', ?);
                """,
                (
                    cand.candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    public_key_id,
                    auth_event_id,
                    new_status,
                    resolution_reason,
                    canonical_json_str,
                    payload_hash,
                    signature_hex,
                    now_iso,
                ),
            )
            # 2. quarantine_cases resolution
            c.execute(
                """
                UPDATE quarantine_cases 
                SET resolution_decision_id = ?, resolution_evidence_reference = ?, resolved_at = ?
                WHERE case_id = ?;
                """,
                (decision_id, evidence_reference, now_iso, case_id),
            )
            # 3. candidate_submissions update (triggers verify approval_history & resolved quarantine_case)
            c.execute(
                "UPDATE candidate_submissions SET processing_status = ?, updated_at = ? WHERE candidate_id = ?;",
                (new_status, now_iso, cand.candidate_id),
            )

        return self.get_case(case_id)

