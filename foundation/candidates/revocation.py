"""
VEDA Candidate Database Subsystem — Approval Revocation & Batch Impact Tracking
Phase 4.14.2
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
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
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    KeyRevokedError,
    ValidationError,
)


class RevocationManager:
    """
    Manages explicit revocation of previously approved candidates.
    Immediately invalidates export eligibility and tracks impacted export batches.
    """

    def __init__(self, connection: CandidateDatabaseConnection, repository: CandidateRepository, reviewer_service: ReviewerService):
        self.conn = connection
        self.repo = repository
        self.reviewers = reviewer_service

    def revoke_approval(
        self,
        candidate_id: str,
        reviewer_id: str,
        reviewer_role: str,
        public_key_id: str,
        auth_event_id: str,
        revocation_reason: str,
        private_key_pem: Optional[bytes] = None,
        provided_signature_hex: Optional[str] = None,
        pipeline_version: str = "v0.4.14",
    ) -> ApprovalHistoryRecord:
        """
        Executes formal revocation of candidate approval with Ed25519 signature.
        Transitions candidate status to REVOKED and records in approval_history.
        """
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise ValidationError(f"Candidate '{candidate_id}' not found.")
        if cand.processing_status not in ("APPROVED", "EXPORT_PENDING", "EXPORTED"):
            raise ValidationError(f"Candidate status is '{cand.processing_status}'; cannot revoke unapproved candidate.")

        # Reviewer checks
        rev = self.reviewers.get_reviewer(reviewer_id)
        if not rev or rev.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' not active.")
        if not self.reviewers.has_role(reviewer_id, reviewer_role):
            raise ReviewerUnauthorizedError(f"Reviewer '{reviewer_id}' lacks role '{reviewer_role}'.")

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
            decision="REVOKED",
            decision_reason=revocation_reason,
            decision_timestamp=now_iso,
            normalized_content_hash=cand.normalized_content_hash,
            source_id=cand.source_id,
            source_artifact_sha256=artifact_hash,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            pipeline_version=pipeline_version,
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
            # 1. approval_history
            c.execute(
                """
                INSERT INTO approval_history (
                    candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
                    old_status, new_status, decision_reason, canonical_payload_json,
                    canonical_payload_sha256, signature_ed25519, payload_schema_version, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'REVOKED', ?, ?, ?, ?, ?, 'VERIFIED_VALID', ?);
                """,
                (
                    candidate_id,
                    decision_id,
                    reviewer_id,
                    reviewer_role,
                    public_key_id,
                    auth_event_id,
                    old_status,
                    revocation_reason,
                    canonical_json_str,
                    payload_hash,
                    signature_hex,
                    "1.0",
                    now_iso,
                ),
            )
            # 2. candidate_submissions update
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'REVOKED', updated_at = ? WHERE candidate_id = ?;",
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
            new_status="REVOKED",
            decision_reason=revocation_reason,
            canonical_payload_json=canonical_json_str,
            canonical_payload_sha256=payload_hash,
            signature_ed25519=signature_hex,
            payload_schema_version="1.0",
            verification_status="VERIFIED_VALID",
            created_at=now_iso,
        )

    def get_affected_batches(self, candidate_id: str) -> List[str]:
        """Returns list of export batch_ids that include this candidate."""
        rows = self.conn.fetchall("SELECT DISTINCT batch_id FROM export_batch_items WHERE candidate_id = ?;", (candidate_id,))
        return [r["batch_id"] for r in rows]
