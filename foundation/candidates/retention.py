"""
VEDA Candidate Database Subsystem — Legally Governed Retention Management
Phase 4.14.2
"""

from datetime import datetime, timezone
from typing import Optional, List
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.models import RetentionDecisionRecord
from foundation.candidates.exceptions import RetentionError, ValidationError


class RetentionManager:
    """
    Manages evidence-based, legally governed data retention decisions.
    Preserves audit hashes permanently while supporting lawful raw text redactions and holds.
    """

    def __init__(self, connection: CandidateDatabaseConnection):
        self.conn = connection

    def record_decision(
        self,
        candidate_id: str,
        decision_type: str,
        legal_basis: str,
        governance_notes: str,
        authorized_by: str,
        review_deadline: Optional[str] = None,
    ) -> RetentionDecisionRecord:
        """Records an auditable legal retention decision."""
        valid_types = {
            "RETAIN_AUDIT_EVIDENCE",
            "RESTRICT_ACCESS_DISPUTE",
            "REDACT_RAW_TEXT_MANDATE",
            "EXPUNGE_LEGAL_ORDER",
        }
        if decision_type not in valid_types:
            raise ValidationError(f"Invalid retention decision_type: {decision_type}")

        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            cur = c.execute(
                """
                INSERT INTO retention_decisions (
                    candidate_id, decision_type, legal_basis, governance_notes, authorized_by, enacted_at, review_deadline
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (candidate_id, decision_type, legal_basis, governance_notes, authorized_by, now_iso, review_deadline),
            )
            dec_id = cur.lastrowid

        return RetentionDecisionRecord(
            decision_id=dec_id,
            candidate_id=candidate_id,
            decision_type=decision_type,
            legal_basis=legal_basis,
            governance_notes=governance_notes,
            authorized_by=authorized_by,
            enacted_at=now_iso,
            review_deadline=review_deadline,
        )

    def has_active_restriction(self, candidate_id: str) -> bool:
        """Returns True if candidate is under an active legal dispute or redaction order."""
        row = self.conn.fetchone(
            """
            SELECT 1 FROM retention_decisions
            WHERE candidate_id = ?
              AND decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
            LIMIT 1;
            """,
            (candidate_id,),
        )
        return row is not None

    def redact_raw_text(self, candidate_id: str, authorized_by: str, legal_basis: str) -> None:
        """
        Redacts raw original text from candidate_submissions due to a verified legal mandate.
        Preserves cryptographic content hashes and provenance for permanent non-repudiation.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            # 1. Record the retention decision
            c.execute(
                """
                INSERT INTO retention_decisions (candidate_id, decision_type, legal_basis, governance_notes, authorized_by, enacted_at)
                VALUES (?, 'REDACT_RAW_TEXT_MANDATE', ?, 'Raw verbatim text redacted under legal compliance order', ?, ?);
                """,
                (candidate_id, legal_basis, authorized_by, now_iso),
            )
            # 2. Mask verbatim text in candidate_submissions while preserving hashes
            c.execute(
                """
                UPDATE candidate_submissions 
                SET original_text = '[REDACTED UNDER LEGAL ORDER]',
                    normalized_text = '[REDACTED UNDER LEGAL ORDER]',
                    raw_bytes = NULL,
                    updated_at = ?
                WHERE candidate_id = ?;
                """,
                (now_iso, candidate_id),
            )

    def expunge_under_legal_order(self, candidate_id: str, authorized_by: str, legal_basis: str) -> None:
        """
        Expunges raw text and raw bytes under court order or statutory mandate.
        Masks verbatim text and nulls raw_bytes, while preserving cryptographic
        content hashes and provenance for permanent audit non-repudiation.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            # 1. Record the retention decision
            c.execute(
                """
                INSERT INTO retention_decisions (candidate_id, decision_type, legal_basis, governance_notes, authorized_by, enacted_at)
                VALUES (?, 'EXPUNGE_LEGAL_ORDER', ?, 'Verbatim text expunged under court/statutory compliance order', ?, ?);
                """,
                (candidate_id, legal_basis, authorized_by, now_iso),
            )
            # 2. Mask verbatim text in candidate_submissions while preserving hashes
            c.execute(
                """
                UPDATE candidate_submissions 
                SET original_text = '[EXPUNGED UNDER COURT ORDER]',
                    normalized_text = '[EXPUNGED UNDER COURT ORDER]',
                    raw_bytes = NULL,
                    updated_at = ?
                WHERE candidate_id = ?;
                """,
                (now_iso, candidate_id),
            )

