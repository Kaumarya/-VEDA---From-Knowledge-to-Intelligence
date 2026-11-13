"""
VEDA Candidate Database Subsystem — Typed Candidate Repository
Phase 4.14.2
"""

import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.models import (
    CandidateSubmission,
    CandidateSourceRecord,
    ProcessingDecisionRecord,
    DuplicateRelationshipRecord,
)
from foundation.candidates.state_machine import CandidateLifecycleStateMachine
from foundation.candidates.exceptions import (
    ValidationError,
    EmptySubmissionError,
    DuplicateSubmissionError,
    CandidateDatabaseError,
)
from foundation.corpus.normalization import TextNormalizer


class CandidateRepository:
    """
    Central typed repository interface for all candidate submissions, sources,
    decisions, relationships, and lifecycle state management.
    """

    def __init__(self, connection: CandidateDatabaseConnection, normalizer: Optional[TextNormalizer] = None):
        self.conn = connection
        self.normalizer = normalizer or TextNormalizer()

    def submit_candidate(
        self,
        original_text: str,
        source_id: str,
        source_document_id: str,
        pipeline_version: str = "v0.4.14",
        candidate_id: Optional[str] = None,
        raw_bytes: Optional[bytes] = None,
    ) -> CandidateSubmission:
        """
        Validates, normalizes, hashes, and persists a raw candidate submission.
        Guarantees verbatim original text preservation, optional raw-bytes preservation, and deterministic hashing.
        """
        if original_text is None or not original_text.strip():
            raise EmptySubmissionError("Candidate submission text must not be empty or whitespace-only.")

        raw_byte_sha256 = None
        if raw_bytes is not None:
            raw_byte_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            try:
                decoded = raw_bytes.decode("utf-8")
                if decoded != original_text:
                    raise ValidationError("Supplied raw_bytes decoded with UTF-8 does not match original_text.")
            except UnicodeDecodeError as e:
                raise ValidationError(f"raw_bytes could not be decoded as UTF-8: {e}") from e

        # 1. Deterministic Normalization
        norm_result = self.normalizer.normalize(original_text)
        normalized_text = norm_result.normalized_text

        # 2. Cryptographic Content Hashing (SHA-256)
        raw_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
        norm_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

        # 3. Candidate ID Generation
        cand_id = candidate_id or f"urn:uuid:{uuid.uuid4()}"

        # 4. Length and count computations
        raw_char_count = len(original_text)
        norm_char_count = len(normalized_text)
        approx_word_count = len(normalized_text.split())

        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn.transaction() as c:
            # Check source existence
            src_row = c.execute("SELECT source_id FROM candidate_sources WHERE source_id = ?;", (source_id,)).fetchone()
            if not src_row:
                raise ValidationError(f"Referenced source_id '{source_id}' does not exist in candidate_sources cache.")

            # Check for existing identical normalized candidate from this source
            existing_master = c.execute(
                """
                SELECT candidate_id FROM candidate_submissions 
                WHERE normalized_content_hash = ? AND source_id = ? AND is_canonical = 1
                LIMIT 1;
                """,
                (norm_hash, source_id),
            ).fetchone()

            is_canonical = 1 if existing_master is None else 0
            canonical_cand_id = None if existing_master is None else existing_master["candidate_id"]

            c.execute(
                """
                INSERT INTO candidate_submissions (
                    candidate_id, source_id, source_document_id, original_text, normalized_text,
                    raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count,
                    approx_word_count, processing_status, is_canonical, canonical_candidate_id,
                    pipeline_version, raw_bytes, raw_byte_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECEIVED', ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    cand_id,
                    source_id,
                    source_document_id,
                    original_text,
                    normalized_text,
                    raw_hash,
                    norm_hash,
                    raw_char_count,
                    norm_char_count,
                    approx_word_count,
                    is_canonical,
                    canonical_cand_id,
                    pipeline_version,
                    raw_bytes,
                    raw_byte_sha256,
                    now_iso,
                    now_iso,
                ),
            )

        return CandidateSubmission(
            candidate_id=cand_id,
            source_id=source_id,
            source_document_id=source_document_id,
            original_text=original_text,
            normalized_text=normalized_text,
            raw_content_hash=raw_hash,
            normalized_content_hash=norm_hash,
            raw_char_count=raw_char_count,
            normalized_char_count=norm_char_count,
            approx_word_count=approx_word_count,
            processing_status="RECEIVED",
            is_canonical=bool(is_canonical),
            canonical_candidate_id=canonical_cand_id,
            pipeline_version=pipeline_version,
            raw_bytes=raw_bytes,
            raw_byte_sha256=raw_byte_sha256,
            created_at=now_iso,
            updated_at=now_iso,
        )

    def _row_to_candidate(self, row: sqlite3.Row) -> CandidateSubmission:
        keys = row.keys()
        return CandidateSubmission(
            candidate_id=row["candidate_id"],
            source_id=row["source_id"],
            source_document_id=row["source_document_id"],
            original_text=row["original_text"],
            normalized_text=row["normalized_text"],
            raw_content_hash=row["raw_content_hash"],
            normalized_content_hash=row["normalized_content_hash"],
            raw_char_count=row["raw_char_count"],
            normalized_char_count=row["normalized_char_count"],
            approx_word_count=row["approx_word_count"],
            processing_status=row["processing_status"],
            is_canonical=bool(row["is_canonical"]),
            canonical_candidate_id=row["canonical_candidate_id"],
            pipeline_version=row["pipeline_version"],
            raw_bytes=row["raw_bytes"] if "raw_bytes" in keys else None,
            raw_byte_sha256=row["raw_byte_sha256"] if "raw_byte_sha256" in keys else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_candidate(self, candidate_id: str) -> Optional[CandidateSubmission]:
        """Retrieves a candidate by ID."""
        row = self.conn.fetchone("SELECT * FROM candidate_submissions WHERE candidate_id = ?;", (candidate_id,))
        if not row:
            return None
        return self._row_to_candidate(row)

    def get_by_raw_hash(self, raw_content_hash: str) -> List[CandidateSubmission]:
        """Retrieves all candidates matching a raw content hash."""
        rows = self.conn.fetchall("SELECT * FROM candidate_submissions WHERE raw_content_hash = ?;", (raw_content_hash,))
        return [self._row_to_candidate(r) for r in rows]

    def get_by_normalized_hash(self, normalized_content_hash: str) -> List[CandidateSubmission]:
        """Retrieves all candidates matching a normalized content hash."""
        rows = self.conn.fetchall("SELECT * FROM candidate_submissions WHERE normalized_content_hash = ?;", (normalized_content_hash,))
        return [self._row_to_candidate(r) for r in rows]

    def list_by_status(self, status: str, limit: int = 100, offset: int = 0) -> List[CandidateSubmission]:
        """Lists candidates in a given lifecycle status."""
        rows = self.conn.fetchall(
            "SELECT * FROM candidate_submissions WHERE processing_status = ? ORDER BY created_at ASC LIMIT ? OFFSET ?;",
            (status, limit, offset),
        )
        return [self._row_to_candidate(r) for r in rows]

    def update_status(
        self,
        candidate_id: str,
        new_status: str,
        actor_role: Optional[str] = None,
        is_human: bool = False,
        is_timeout_action: bool = False,
        reason: str = "",
    ) -> None:
        """
        Transitions candidate lifecycle status subject to state machine invariants.
        """
        cand = self.get_candidate(candidate_id)
        if not cand:
            raise ValidationError(f"Candidate '{candidate_id}' not found.")

        # State machine validation
        CandidateLifecycleStateMachine.validate_transition(
            from_state=cand.processing_status,
            to_state=new_status,
            actor_role=actor_role,
            is_human=is_human,
            is_timeout_action=is_timeout_action,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                "UPDATE candidate_submissions SET processing_status = ?, updated_at = ? WHERE candidate_id = ?;",
                (new_status, now_iso, candidate_id),
            )

    def record_processing_decision(self, record: ProcessingDecisionRecord) -> int:
        """Appends a versioned processing decision."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            cur = c.execute(
                """
                INSERT INTO processing_decisions (
                    candidate_id, stage_name, pipeline_version, decision_outcome,
                    quality_score, language_confidence, failed_metric, diagnostic_evidence_json, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.candidate_id,
                    record.stage_name,
                    record.pipeline_version,
                    record.decision_outcome,
                    record.quality_score,
                    record.language_confidence,
                    record.failed_metric,
                    record.diagnostic_evidence_json,
                    now_iso,
                ),
            )
            return cur.lastrowid

    def get_processing_decisions(self, candidate_id: str) -> List[ProcessingDecisionRecord]:
        """Retrieves decision history for a candidate."""
        rows = self.conn.fetchall(
            "SELECT * FROM processing_decisions WHERE candidate_id = ? ORDER BY evaluated_at ASC, decision_id ASC;",
            (candidate_id,),
        )
        return [
            ProcessingDecisionRecord(
                decision_id=r["decision_id"],
                candidate_id=r["candidate_id"],
                stage_name=r["stage_name"],
                pipeline_version=r["pipeline_version"],
                decision_outcome=r["decision_outcome"],
                quality_score=r["quality_score"],
                language_confidence=r["language_confidence"],
                failed_metric=r["failed_metric"],
                diagnostic_evidence_json=r["diagnostic_evidence_json"],
                evaluated_at=r["evaluated_at"],
            )
            for r in rows
        ]

    def record_duplicate_relationship(self, record: DuplicateRelationshipRecord) -> int:
        """Records a duplicate relationship between two candidates."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            cur = c.execute(
                """
                INSERT INTO duplicate_relationships (
                    candidate_id, related_candidate_id, relationship_type, detector_version,
                    similarity_score, is_safe_to_merge, conflict_reason, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    record.candidate_id,
                    record.related_candidate_id,
                    record.relationship_type,
                    record.detector_version,
                    record.similarity_score,
                    1 if record.is_safe_to_merge else 0,
                    record.conflict_reason,
                    now_iso,
                ),
            )
            return cur.lastrowid

    def get_duplicate_relationships(self, candidate_id: str) -> List[DuplicateRelationshipRecord]:
        """Retrieves all duplicate relationships involving a candidate."""
        rows = self.conn.fetchall(
            "SELECT * FROM duplicate_relationships WHERE candidate_id = ? OR related_candidate_id = ?;",
            (candidate_id, candidate_id),
        )
        return [
            DuplicateRelationshipRecord(
                relationship_id=r["relationship_id"],
                candidate_id=r["candidate_id"],
                related_candidate_id=r["related_candidate_id"],
                relationship_type=r["relationship_type"],
                detector_version=r["detector_version"],
                similarity_score=r["similarity_score"],
                is_safe_to_merge=bool(r["is_safe_to_merge"]),
                conflict_reason=r["conflict_reason"],
                detected_at=r["detected_at"],
            )
            for r in rows
        ]

    def upsert_source(self, record: CandidateSourceRecord) -> None:
        """Caches a verified source record from SourceRegistry into candidate_sources."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO candidate_sources (
                    source_id, name, version, licensing_status, license_name,
                    training_permitted_status, commercial_permitted, artifact_sha256,
                    registry_entry_sha256, approval_expiration_date, attribution, sync_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    name = excluded.name,
                    version = excluded.version,
                    licensing_status = excluded.licensing_status,
                    license_name = excluded.license_name,
                    training_permitted_status = excluded.training_permitted_status,
                    commercial_permitted = excluded.commercial_permitted,
                    artifact_sha256 = excluded.artifact_sha256,
                    registry_entry_sha256 = excluded.registry_entry_sha256,
                    approval_expiration_date = excluded.approval_expiration_date,
                    attribution = excluded.attribution,
                    sync_timestamp = excluded.sync_timestamp;
                """,
                (
                    record.source_id,
                    record.name,
                    record.version,
                    record.licensing_status,
                    record.license_name,
                    record.training_permitted_status,
                    1 if record.commercial_permitted else 0,
                    record.artifact_sha256,
                    record.registry_entry_sha256,
                    record.approval_expiration_date,
                    record.attribution,
                    now_iso,
                ),
            )

    def get_source(self, source_id: str) -> Optional[CandidateSourceRecord]:
        """Retrieves a cached source record."""
        row = self.conn.fetchone("SELECT * FROM candidate_sources WHERE source_id = ?;", (source_id,))
        if not row:
            return None
        return CandidateSourceRecord(
            source_id=row["source_id"],
            name=row["name"],
            version=row["version"],
            licensing_status=row["licensing_status"],
            license_name=row["license_name"],
            training_permitted_status=row["training_permitted_status"],
            commercial_permitted=bool(row["commercial_permitted"]),
            artifact_sha256=row["artifact_sha256"],
            registry_entry_sha256=row["registry_entry_sha256"],
            approval_expiration_date=row["approval_expiration_date"],
            attribution=row["attribution"],
            sync_timestamp=row["sync_timestamp"],
        )

    def create_quarantine_case(
        self,
        candidate_id: str,
        reason: str = "MANUAL_HUMAN_QUARANTINE",
        category: str = "SAFETY",
        evidence_json: str = "{}",
        assigned_reviewer_id: Optional[str] = None,
        assigned_role: str = "ROLE_SAFETY_OFFICER",
        pipeline_version: str = "v0.4.14",
    ):
        """Creates a quarantine case in quarantine_cases and sets candidate status to QUARANTINED."""
        from datetime import timedelta
        case_id = f"urn:uuid:{uuid.uuid4()}"
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        review_due_iso = (now_utc + timedelta(days=30)).isoformat()

        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO quarantine_cases (
                    case_id, candidate_id, quarantine_reason, quarantine_category,
                    diagnostic_evidence_json, pipeline_version, quarantined_at, review_due_at,
                    assigned_reviewer_id, assigned_role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (case_id, candidate_id, reason, category, evidence_json, pipeline_version, now_iso, review_due_iso, assigned_reviewer_id, assigned_role),
            )
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'QUARANTINED', updated_at = ? WHERE candidate_id = ?;",
                (now_iso, candidate_id),
            )
        from foundation.candidates.models import QuarantineCaseRecord
        row = self.conn.fetchone("SELECT * FROM quarantine_cases WHERE case_id = ?;", (case_id,))
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

