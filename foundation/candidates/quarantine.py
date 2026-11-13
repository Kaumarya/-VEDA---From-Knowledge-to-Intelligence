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
from foundation.candidates.models import (
    QuarantineCaseRecord,
    ApprovalHistoryRecord,
    QuarantineDualApprovalRecord,
)
from foundation.candidates.exceptions import (
    QuarantineError,
    QuarantineTimeoutMutationError,
    UnauthorizedQuarantineResolutionError,
    ReviewerUnauthorizedError,
    ReviewerInactiveError,
    RolePermissionError,
    KeyRevokedError,
    KeyExpiredError,
    KeyNotFoundError,
    ValidationError,
    DualApprovalRequiredError,
    InvalidDualApprovalError,
)
from foundation.candidates.key_custody import ReviewerKeyProvider


class QuarantineManager:
    """
    Manages quarantine lifecycle, monitoring reminders, non-mutating escalations,
    and cryptographically verified human resolutions.
    """

    def __init__(
        self,
        connection: CandidateDatabaseConnection,
        repository: CandidateRepository,
        reviewer_service: ReviewerService,
        enforce_identity_assurance: bool = False,
    ):
        self.conn = connection
        self.repo = repository
        self.reviewers = reviewer_service
        self.enforce_identity_assurance = enforce_identity_assurance

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

    def check_and_escalate_sla(self, case_id: str, age_days: int) -> str:
        """
        Evaluates SLA aging for open quarantine cases according to governance policy.
        - 7, 14, 21 days: records monitoring reminder.
        - 30 days: marks ESCALATED_30_DAYS.
        - 60+ days: marks CRITICAL_60_DAYS.
        Strictly NON-MUTATING on candidate_submissions.processing_status.
        """
        case = self.get_case(case_id)
        if not case:
            raise ValidationError(f"Quarantine case '{case_id}' not found.")
        if case.resolution_decision_id is not None:
            return case.escalation_level or "RESOLVED"

        now_iso = datetime.now(timezone.utc).isoformat()
        new_level = case.escalation_level

        if age_days >= 60:
            new_level = "CRITICAL_60_DAYS"
            with self.conn.transaction() as c:
                c.execute(
                    "UPDATE quarantine_cases SET escalated_at = ?, escalation_level = ?, last_reminder_at = ? WHERE case_id = ?;",
                    (now_iso, new_level, now_iso, case_id),
                )
        elif age_days >= 30:
            new_level = "ESCALATED_30_DAYS"
            with self.conn.transaction() as c:
                c.execute(
                    "UPDATE quarantine_cases SET escalated_at = ?, escalation_level = ?, last_reminder_at = ? WHERE case_id = ?;",
                    (now_iso, new_level, now_iso, case_id),
                )
        elif age_days >= 7:
            with self.conn.transaction() as c:
                c.execute("UPDATE quarantine_cases SET last_reminder_at = ? WHERE case_id = ?;", (now_iso, case_id))

        return new_level or "NORMAL"

    def get_dual_approval(self, case_id: str) -> Optional[QuarantineDualApprovalRecord]:
        """Retrieves a quarantine dual approval ledger record."""
        row = self.conn.fetchone("SELECT * FROM quarantine_dual_approvals WHERE case_id = ?;", (case_id,))
        if not row:
            return None
        return QuarantineDualApprovalRecord(
            case_id=row["case_id"],
            candidate_id=row["candidate_id"],
            first_decision_id=row["first_decision_id"],
            first_reviewer_id=row["first_reviewer_id"],
            first_reviewer_role=row["first_reviewer_role"],
            first_auth_event_id=row["first_auth_event_id"],
            first_public_key_id=row["first_public_key_id"],
            first_signature=row["first_signature"],
            first_approved_at=row["first_approved_at"],
            second_decision_id=row["second_decision_id"],
            second_reviewer_id=row["second_reviewer_id"],
            second_reviewer_role=row["second_reviewer_role"],
            second_auth_event_id=row["second_auth_event_id"],
            second_public_key_id=row["second_public_key_id"],
            second_signature=row["second_signature"],
            second_approved_at=row["second_approved_at"],
            dual_status=row["dual_status"],
            bound_candidate_hash=row["bound_candidate_hash"],
            bound_artifact_hash=row["bound_artifact_hash"],
            policy_version=row["policy_version"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def initiate_quarantine_dual_approval(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        decision_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        key_provider: Optional[ReviewerKeyProvider] = None,
        pipeline_version: str = "v0.4.14",
        enforce_identity_assurance: Optional[bool] = None,
    ) -> QuarantineDualApprovalRecord:
        """
        Initiates the first leg of the Two-Person Dual Approval Protocol for a quarantined candidate.
        Validates the first reviewer, records their signed approval in the dual ledger, and leaves
        the candidate strictly in QUARANTINED status until Leg 2 is completed by an independent reviewer.
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

        self.reviewers.assert_permission(reviewer_id, "can_participate_dual_appr")

        # Session validation for Leg 1
        self.reviewers.validate_session(auth_event_id, reviewer_id, "INITIATE_QUARANTINE_DUAL_APPROVAL")

        # Key checks
        key = self.reviewers.get_public_key(public_key_id)
        if not key or key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError("Public key not active.")
        if key.reviewer_id != reviewer_id:
            raise KeyNotFoundError(f"Public key '{public_key_id}' does not belong to reviewer '{reviewer_id}'.")

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

        existing_dual = self.get_dual_approval(case_id)
        if existing_dual:
            if existing_dual.dual_status == "FIRST_LEG_APPROVED":
                raise ValidationError(f"Dual approval already initiated for case '{case_id}'.")
            if existing_dual.dual_status == "COMPLETED":
                raise ValidationError(f"Dual approval already completed for case '{case_id}'.")

        decision_id = f"urn:uuid:{uuid.uuid4()}"
        payload_dict = Ed25519SignatureService.build_canonical_approval_payload(
            candidate_id=cand.candidate_id,
            decision_id=decision_id,
            decision="DUAL_APPROVAL_LEG_1",
            decision_reason=decision_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=artifact_hash,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
            quarantine_case_id=case_id,
            canonicalization_version="RFC8785_V2",
        )
        canonical_bytes = canonicalize_json(payload_dict, version="RFC8785_V2")

        if key_provider:
            signature_hex = key_provider.sign_payload(reviewer_id, public_key_id, canonical_bytes)
        elif private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either key_provider, private_key_pem, or provided_signature_hex must be supplied.")

        Ed25519SignatureService.verify(key.public_key_hex, canonical_bytes, signature_hex)

        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO quarantine_dual_approvals (
                    case_id, candidate_id, first_decision_id, first_reviewer_id, first_reviewer_role,
                    first_auth_event_id, first_public_key_id, first_signature, first_approved_at,
                    dual_status, bound_candidate_hash, bound_artifact_hash, policy_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'FIRST_LEG_APPROVED', ?, ?, ?, ?);
                """,
                (
                    case_id,
                    cand.candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    auth_event_id,
                    public_key_id,
                    signature_hex,
                    now_iso,
                    cand.normalized_content_hash,
                    artifact_hash,
                    pipeline_version,
                    now_iso,
                ),
            )

        return self.get_dual_approval(case_id)

    def complete_quarantine_dual_approval(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        decision_reason: str,
        evidence_reference: str = "",
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        key_provider: Optional[ReviewerKeyProvider] = None,
        pipeline_version: str = "v0.4.14",
        enforce_identity_assurance: Optional[bool] = None,
    ) -> QuarantineDualApprovalRecord:
        """
        Completes the second leg of the Two-Person Dual Approval Protocol for a quarantined candidate.
        Enforces that the second approver is an independent human identity with separate authentication,
        verifies that candidate content has not been tampered with, and commits the candidate to APPROVED.
        """
        case = self.get_case(case_id)
        if not case:
            raise ValidationError(f"Quarantine case '{case_id}' not found.")
        if case.resolution_decision_id is not None:
            raise ValidationError(f"Quarantine case '{case_id}' is already resolved.")

        dual = self.get_dual_approval(case_id)
        if not dual or dual.dual_status != "FIRST_LEG_APPROVED":
            raise ValidationError(f"First leg of dual approval must be completed before second leg for case '{case_id}'.")

        # Two-person rule enforcement
        if reviewer_id == dual.first_reviewer_id:
            raise InvalidDualApprovalError(
                f"Two-person rule violation: Second reviewer '{reviewer_id}' cannot be identical to first reviewer."
            )

        first_rev = self.reviewers.get_reviewer(dual.first_reviewer_id)
        second_rev = self.reviewers.get_reviewer(reviewer_id)
        if not second_rev or second_rev.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Second reviewer '{reviewer_id}' not active.")

        if first_rev and second_rev.email and first_rev.email == second_rev.email:
            raise InvalidDualApprovalError(
                f"Two-person rule violation: Second reviewer shares email '{second_rev.email}' with first reviewer."
            )

        if auth_event_id == dual.first_auth_event_id:
            raise InvalidDualApprovalError(
                "Two-person rule violation: Second reviewer must have an independent authentication event."
            )

        # Human Identity Assurance (Part 11)
        should_enforce_id = self.enforce_identity_assurance if enforce_identity_assurance is None else enforce_identity_assurance
        if first_rev and second_rev:
            if first_rev.idp_subject_id and second_rev.idp_subject_id:
                if first_rev.idp_subject_id == second_rev.idp_subject_id:
                    raise InvalidDualApprovalError(
                        f"Two-person human identity violation: Both reviewer accounts map to the same "
                        f"organizational IdP subject identifier '{first_rev.idp_subject_id}'."
                    )
            elif should_enforce_id:
                raise InvalidDualApprovalError(
                    "Production dual approval blocked: Organizational identity provider assurance is "
                    "NOT IMPLEMENTED or reviewers lack verified idp_subject_id."
                )

        if not self.reviewers.has_role(reviewer_id, reviewer_role):
            raise ReviewerUnauthorizedError(f"Second reviewer '{reviewer_id}' lacks role '{reviewer_role}'.")

        self.reviewers.assert_permission(reviewer_id, "can_participate_dual_appr")

        # Session validation for Leg 2
        self.reviewers.validate_session(auth_event_id, reviewer_id, "COMPLETE_QUARANTINE_DUAL_APPROVAL")

        # Key checks
        key = self.reviewers.get_public_key(public_key_id)
        if not key or key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError("Public key not active.")
        if key.reviewer_id != reviewer_id:
            raise KeyNotFoundError(f"Public key '{public_key_id}' does not belong to reviewer '{reviewer_id}'.")

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        if key.activated_at and now_iso < key.activated_at:
            raise KeyExpiredError("Signing timestamp is prior to key activation.")
        if key.valid_until and now_iso > key.valid_until:
            raise KeyExpiredError(f"Key '{public_key_id}' has expired/rotated on {key.valid_until}.")
        if key.revoked_at and now_iso >= key.revoked_at:
            raise KeyRevokedError(f"Key '{public_key_id}' was revoked on {key.revoked_at}.")

        cand = self.repo.get_candidate(case.candidate_id)
        if not cand or cand.processing_status != "QUARANTINED":
            raise ValidationError(f"Candidate '{case.candidate_id}' is not in QUARANTINED status.")

        src = self.repo.get_source(cand.source_id)
        if not src:
            raise InvalidDualApprovalError(f"Source '{cand.source_id}' not found in candidate source cache.")
        if src.licensing_status != "VERIFIED PERMITTED" or src.training_permitted_status != "EXPLICITLY_PERMITTED":
            raise InvalidDualApprovalError(
                f"Source '{cand.source_id}' licensing or training permission was revoked between approval legs "
                f"(licensing: {src.licensing_status}, training: {src.training_permitted_status}). Candidate remains QUARANTINED."
            )
        artifact_hash = src.artifact_sha256 if src else "0" * 64

        # Hash integrity checks against first leg bindings
        if cand.normalized_content_hash != dual.bound_candidate_hash:
            raise InvalidDualApprovalError(
                "Candidate normalized content hash has changed since first leg approval."
            )
        if artifact_hash != dual.bound_artifact_hash:
            raise InvalidDualApprovalError(
                "Source artifact hash has changed since first leg approval."
            )

        # Build canonical payload for Leg 2 (final approval)
        decision_id = f"urn:uuid:{uuid.uuid4()}"
        payload_dict = Ed25519SignatureService.build_canonical_approval_payload(
            candidate_id=cand.candidate_id,
            decision_id=decision_id,
            decision="APPROVED",
            decision_reason=decision_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=artifact_hash,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
            quarantine_case_id=case_id,
            canonicalization_version="RFC8785_V2",
        )
        canonical_bytes = canonicalize_json(payload_dict, version="RFC8785_V2")
        payload_hash = compute_payload_hash(canonical_bytes)
        canonical_json_str = canonical_bytes.decode("utf-8")

        if key_provider:
            signature_hex = key_provider.sign_payload(reviewer_id, public_key_id, canonical_bytes)
        elif private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either key_provider, private_key_pem, or provided_signature_hex must be supplied.")

        Ed25519SignatureService.verify(key.public_key_hex, canonical_bytes, signature_hex)

        # Atomic commit
        with self.conn.transaction() as c:
            # 1. approval_history entry
            c.execute(
                """
                INSERT INTO approval_history (
                    candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                    old_status, new_status, decision_reason, canonical_payload_json,
                    canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'QUARANTINED', 'APPROVED', ?, ?, ?, ?, '1.0', 'VERIFIED_VALID', ?);
                """,
                (
                    cand.candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    public_key_id,
                    auth_event_id,
                    decision_reason,
                    canonical_json_str,
                    payload_hash,
                    signature_hex,
                    now_iso,
                ),
            )
            # 2. Update quarantine_cases to resolved
            c.execute(
                """
                UPDATE quarantine_cases 
                SET resolution_decision_id = ?, resolution_evidence_reference = ?, resolved_at = ?
                WHERE case_id = ?;
                """,
                (decision_id, evidence_reference, now_iso, case_id),
            )
            # 3. Update quarantine_dual_approvals to COMPLETED
            c.execute(
                """
                UPDATE quarantine_dual_approvals
                SET second_decision_id = ?, second_reviewer_id = ?, second_reviewer_role = ?,
                    second_auth_event_id = ?, second_public_key_id = ?, second_signature = ?,
                    second_approved_at = ?, dual_status = 'COMPLETED', completed_at = ?
                WHERE case_id = ?;
                """,
                (
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    auth_event_id,
                    public_key_id,
                    signature_hex,
                    now_iso,
                    now_iso,
                    case_id,
                ),
            )
            # 4. Update candidate status to APPROVED
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'APPROVED', updated_at = ? WHERE candidate_id = ?;",
                (now_iso, cand.candidate_id),
            )

        return self.get_dual_approval(case_id)

    def resolve_quarantine(
        self,
        case_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        resolution_action: str,  # RELEASED_TO_PENDING, REJECTED (APPROVED requires dual approval protocol)
        resolution_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        key_provider: Optional[ReviewerKeyProvider] = None,
        evidence_reference: str = "",
        pipeline_version: str = "v0.4.14",
    ) -> QuarantineCaseRecord:
        """
        Executes explicit, cryptographically signed human resolution of a quarantine case.
        Permitted actions: RELEASED_TO_PENDING, REJECTED.
        Resolution directly to APPROVED requires the Two-Person Dual Approval Protocol.
        Fails closed on missing authorization or invalid signature.
        """
        if resolution_action == "APPROVED":
            raise DualApprovalRequiredError(
                "Direct single-reviewer approval of quarantined candidate is forbidden. "
                "Quarantine approval strictly requires the two-person dual approval protocol "
                "(initiate_quarantine_dual_approval and complete_quarantine_dual_approval)."
            )

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

        # Map resolution action and verify granular permissions
        if resolution_action == "RELEASED_TO_PENDING":
            self.reviewers.assert_permission(reviewer_id, "can_resolve_quarantine")
            new_status = "APPROVAL_PENDING"
            decision_outcome = "RELEASED_TO_PENDING"
        elif resolution_action == "REJECTED":
            self.reviewers.assert_permission(reviewer_id, "can_reject_candidates")
            new_status = "REJECTED"
            decision_outcome = "REJECTED"
        else:
            raise ValidationError(f"Invalid quarantine resolution action: {resolution_action}")

        # Key checks
        key = self.reviewers.get_public_key(public_key_id)
        if not key or key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError("Public key not active.")
        if key.reviewer_id != reviewer_id:
            raise KeyNotFoundError(f"Public key '{public_key_id}' does not belong to reviewer '{reviewer_id}'.")

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
            canonicalization_version="RFC8785_V2",
        )
        canonical_bytes = canonicalize_json(payload_dict, version="RFC8785_V2")
        payload_hash = compute_payload_hash(canonical_bytes)
        canonical_json_str = canonical_bytes.decode("utf-8")

        # Sign or verify signature
        if key_provider:
            signature_hex = key_provider.sign_payload(reviewer_id, public_key_id, canonical_bytes)
        elif private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either key_provider, private_key_pem, or provided_signature_hex must be supplied.")

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

