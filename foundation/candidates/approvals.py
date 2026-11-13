"""
VEDA Candidate Database Subsystem — Human Approval & Cryptographic Audit Service
Phase 4.14.2
Enforces 100% human approval, Ed25519 digital signatures, and fail-closed audit logging.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.signatures import (
    canonicalize_json,
    compute_payload_hash,
    Ed25519SignatureService,
)
from foundation.candidates.models import ApprovalHistoryRecord
from foundation.candidates.exceptions import (
    ReviewerNotFoundError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    KeyNotFoundError,
    KeyRevokedError,
    KeyExpiredError,
    InvalidSignatureError,
    ValidationError,
)


class ApprovalService:
    """
    Authoritative service executing human approvals and rejections.
    Enforces all 12 approval prerequisites, canonical payload binding,
    Ed25519 signature verification, and atomic commit to approval_history.
    """

    def __init__(self, connection: CandidateDatabaseConnection, repository: CandidateRepository, reviewer_service: ReviewerService):
        self.conn = connection
        self.repo = repository
        self.reviewers = reviewer_service

    def approve_candidate(
        self,
        candidate_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        decision_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        pipeline_version: str = "v0.4.14",
        policy_schema_version: str = "1.0",
        allow_quarantine_dual_approval: bool = False,
    ) -> ApprovalHistoryRecord:
        """
        Executes explicit, authenticated human approval with Ed25519 signature.
        Fails closed on any governance, authorization, or cryptographic defect.
        """
        # 1. Candidate Preconditions
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise ValidationError(f"Candidate '{candidate_id}' not found.")

        if cand.processing_status != "APPROVAL_PENDING":
            if not (allow_quarantine_dual_approval and cand.processing_status == "QUARANTINED"):
                raise ValidationError(
                    f"Candidate is in status '{cand.processing_status}'; must be 'APPROVAL_PENDING' for human approval."
                )

        # 2. Reviewer Identity Preconditions
        reviewer = self.reviewers.get_reviewer(reviewer_id)
        if not reviewer:
            raise ReviewerNotFoundError(f"Reviewer '{reviewer_id}' not found.")
        if reviewer.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' account is {reviewer.account_status}; cannot approve.")

        # 3. Role Authorization
        if not self.reviewers.has_role(reviewer_id, reviewer_role):
            raise ReviewerUnauthorizedError(
                f"Reviewer '{reviewer_id}' is not assigned the required role '{reviewer_role}'."
            )

        # Check role permission in DB
        role_row = self.conn.fetchone("SELECT can_approve_corpus FROM reviewer_roles WHERE role_name = ?;", (reviewer_role,))
        if not role_row or role_row["can_approve_corpus"] != 1:
            raise ReviewerUnauthorizedError(f"Role '{reviewer_role}' has no authority to grant corpus approval.")

        # 4. Public Key Validity Preconditions
        key = self.reviewers.get_public_key(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Public key '{public_key_id}' not found.")
        if key.reviewer_id != reviewer_id:
            raise KeyNotFoundError(f"Public key '{public_key_id}' belongs to a different reviewer.")
        if key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError(f"Public key '{public_key_id}' is {key.key_status}; cannot be used for approval.")

        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()

        if key.activated_at and now_iso < key.activated_at:
            raise KeyExpiredError("Signing timestamp is prior to key activation.")
        if key.valid_until and now_iso > key.valid_until:
            raise KeyExpiredError(f"Key '{public_key_id}' has expired/rotated on {key.valid_until}.")
        if key.revoked_at and now_iso >= key.revoked_at:
            raise KeyRevokedError(f"Key '{public_key_id}' was revoked on {key.revoked_at}.")

        # 5. Source Governance Preconditions
        src = self.repo.get_source(cand.source_id)
        if not src:
            raise ValidationError(f"Source '{cand.source_id}' not found.")
        if src.licensing_status != "VERIFIED PERMITTED" or src.training_permitted_status != "EXPLICITLY_PERMITTED":
            raise ValidationError(
                f"Source '{cand.source_id}' does not have verified training permission (licensing: {src.licensing_status}, training: {src.training_permitted_status})."
            )

        # 6. Safety Conflict Check (No unresolved conflicts)
        conflicts = self.conn.fetchall(
            """
            SELECT * FROM duplicate_relationships
            WHERE (candidate_id = ? OR related_candidate_id = ?) AND is_safe_to_merge = 0;
            """,
            (candidate_id, candidate_id),
        )
        if conflicts:
            raise ValidationError(f"Candidate '{candidate_id}' has active unmerged safety conflicts.")

        # 7. Unresolved Quarantine Check
        if not allow_quarantine_dual_approval:
            q_case = self.conn.fetchone(
                "SELECT * FROM quarantine_cases WHERE candidate_id = ? AND resolution_decision_id IS NULL;",
                (candidate_id,),
            )
            if q_case:
                raise ValidationError(f"Candidate '{candidate_id}' has an unresolved quarantine case ({q_case['case_id']}).")

        # 8. Build Canonical Approval Payload
        decision_id = f"urn:uuid:{uuid.uuid4()}"
        payload_dict = Ed25519SignatureService.build_canonical_approval_payload(
            candidate_id=candidate_id,
            decision_id=decision_id,
            decision="APPROVED",
            decision_reason=decision_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=src.artifact_sha256,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
            payload_schema_version=policy_schema_version,
        )
        canonical_bytes = canonicalize_json(payload_dict)
        payload_hash = compute_payload_hash(canonical_bytes)
        canonical_json_str = canonical_bytes.decode("utf-8")

        # 9. Sign or Verify Signature
        if private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either private_key_pem or provided_signature_hex must be supplied.")

        # Mathematical Ed25519 verification against registered public key
        Ed25519SignatureService.verify(key.public_key_hex, canonical_bytes, signature_hex)

        # 10. Atomic Transaction Commit
        old_status = cand.processing_status
        with self.conn.transaction() as c:
            # First insert approval_history row
            c.execute(
                """
                INSERT INTO approval_history (
                    candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                    old_status, new_status, decision_reason, canonical_payload_json,
                    canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'APPROVED', ?, ?, ?, ?, ?, 'VERIFIED_VALID', ?);
                """,
                (
                    candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    public_key_id,
                    auth_event_id,
                    old_status,
                    decision_reason,
                    canonical_json_str,
                    payload_hash,
                    signature_hex,
                    policy_schema_version,
                    now_iso,
                ),
            )
            # Then mutate candidate_submissions (trigger trig_enforce_signed_approval_mutation checks approval_history)
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'APPROVED', updated_at = ? WHERE candidate_id = ?;",
                (now_iso, candidate_id),
            )

        return ApprovalHistoryRecord(
            candidate_id=candidate_id,
            decision_id=decision_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            public_key_id=public_key_id,
            auth_event_id=auth_event_id,
            old_status=old_status,
            new_status="APPROVED",
            decision_reason=decision_reason,
            canonical_payload_json=canonical_json_str,
            canonical_payload_sha256=payload_hash,
            signature_ed25519=signature_hex,
            payload_schema_version=policy_schema_version,
            verification_status="VERIFIED_VALID",
            created_at=now_iso,
        )

    def reject_candidate(
        self,
        candidate_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        decision_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        pipeline_version: str = "v0.4.14",
        policy_schema_version: str = "1.0",
    ) -> ApprovalHistoryRecord:
        """
        Executes explicit human rejection of a candidate with signed audit record.
        """
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise ValidationError(f"Candidate '{candidate_id}' not found.")

        reviewer = self.reviewers.get_reviewer(reviewer_id)
        if not reviewer or reviewer.account_status != "ACTIVE":
            raise ReviewerInactiveError("Reviewer not active.")

        if not self.reviewers.has_role(reviewer_id, reviewer_role):
            raise ReviewerUnauthorizedError("Reviewer lacks role.")

        key = self.reviewers.get_public_key(public_key_id)
        if not key or key.key_status not in ("ACTIVE", "ROTATED_RETIRED"):
            raise KeyRevokedError("Public key not active.")

        src = self.repo.get_source(cand.source_id)
        artifact_hash = src.artifact_sha256 if src else "0" * 64

        now_iso = datetime.now(timezone.utc).isoformat()
        decision_id = f"urn:uuid:{uuid.uuid4()}"

        payload_dict = Ed25519SignatureService.build_canonical_approval_payload(
            candidate_id=candidate_id,
            decision_id=decision_id,
            decision="REJECTED",
            decision_reason=decision_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=artifact_hash,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
            payload_schema_version=policy_schema_version,
        )
        canonical_bytes = canonicalize_json(payload_dict)
        payload_hash = compute_payload_hash(canonical_bytes)
        canonical_json_str = canonical_bytes.decode("utf-8")

        if private_key_pem:
            signature_hex = Ed25519SignatureService.sign(private_key_pem, canonical_bytes)
        elif provided_signature_hex:
            signature_hex = provided_signature_hex.lower()
        else:
            raise ValidationError("Either private_key_pem or provided_signature_hex must be supplied.")

        Ed25519SignatureService.verify(key.public_key_hex, canonical_bytes, signature_hex)

        old_status = cand.processing_status
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO approval_history (
                    candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                    old_status, new_status, decision_reason, canonical_payload_json,
                    canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'REJECTED', ?, ?, ?, ?, ?, 'VERIFIED_VALID', ?);
                """,
                (
                    candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    public_key_id,
                    auth_event_id,
                    old_status,
                    decision_reason,
                    canonical_json_str,
                    payload_hash,
                    signature_hex,
                    policy_schema_version,
                    now_iso,
                ),
            )
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'REJECTED', updated_at = ? WHERE candidate_id = ?;",
                (now_iso, candidate_id),
            )

        return ApprovalHistoryRecord(
            candidate_id=candidate_id,
            decision_id=decision_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            public_key_id=public_key_id,
            auth_event_id=auth_event_id,
            old_status=old_status,
            new_status="REJECTED",
            decision_reason=decision_reason,
            canonical_payload_json=canonical_json_str,
            canonical_payload_sha256=payload_hash,
            signature_ed25519=signature_hex,
            payload_schema_version=policy_schema_version,
            verification_status="VERIFIED_VALID",
            created_at=now_iso,
        )

