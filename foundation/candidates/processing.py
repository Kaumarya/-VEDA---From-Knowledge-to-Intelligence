"""
VEDA Candidate Database Subsystem — Processing & Foundation Integration
Phase 4.14.2
Reuses TextNormalizer, classify_with_quarantine, NearDuplicateDetector, and SemanticSafetyGuard.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.models import (
    CandidateSubmission,
    ProcessingDecisionRecord,
    DuplicateRelationshipRecord,
    QuarantineCaseRecord,
)
from foundation.corpus.normalization import TextNormalizer
from foundation.corpus.language_audit import classify_with_quarantine
from foundation.corpus.near_deduplication import NearDuplicateDetector


class CandidateProcessor:
    """
    Automated processing pipeline for candidate submissions.
    Applies normalization, quality filtering, language filtering, near-duplicate detection,
    and semantic safety conflict analysis.
    Maintains strict separation: automated processing NEVER grants production approval.
    """

    def __init__(
        self,
        repository: CandidateRepository,
        normalizer: Optional[TextNormalizer] = None,
        near_dedup_detector: Optional[NearDuplicateDetector] = None,
    ):
        self.repo = repository
        self.normalizer = normalizer or TextNormalizer()
        self.near_dedup_detector = near_dedup_detector or NearDuplicateDetector()

    def process_candidate(self, candidate_id: str, pipeline_version: str = "v0.4.14") -> CandidateSubmission:
        """
        Executes end-to-end automated processing on a candidate submission.
        Routes candidates to PROCESSING_PASSED -> APPROVAL_PENDING, QUARANTINED, or REJECTED.
        """
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise ValueError(f"Candidate '{candidate_id}' not found.")

        # Transition to PROCESSING
        self.repo.update_status(candidate_id, "PROCESSING")

        # 1. Language & Quality Audit via classify_with_quarantine
        audit_res = classify_with_quarantine(cand.normalized_text)
        outcome = audit_res.get("outcome", "REJECT")
        reason = audit_res.get("reason", "UNKNOWN")
        q_score = audit_res.get("quality_score")
        failed_metric = audit_res.get("failed_metric")

        evidence_json = json.dumps(audit_res)

        if outcome == "REJECT":
            self.repo.record_processing_decision(
                ProcessingDecisionRecord(
                    candidate_id=candidate_id,
                    stage_name="LANGUAGE_AND_QUALITY",
                    pipeline_version=pipeline_version,
                    decision_outcome="FAIL",
                    quality_score=q_score,
                    failed_metric=failed_metric or reason,
                    diagnostic_evidence_json=evidence_json,
                )
            )
            self.repo.update_status(candidate_id, "REJECTED")
            return self.repo.get_candidate(candidate_id)

        elif outcome == "QUARANTINE":
            self.repo.record_processing_decision(
                ProcessingDecisionRecord(
                    candidate_id=candidate_id,
                    stage_name="LANGUAGE_AND_QUALITY",
                    pipeline_version=pipeline_version,
                    decision_outcome="QUARANTINE",
                    quality_score=q_score,
                    failed_metric=failed_metric or reason,
                    diagnostic_evidence_json=evidence_json,
                )
            )
            self._route_to_quarantine(
                candidate_id=candidate_id,
                reason="LANGUAGE_FILTER_AMBIGUOUS",
                category="LANGUAGE",
                evidence_json=evidence_json,
                pipeline_version=pipeline_version,
                assigned_role="ROLE_DOMAIN_CURATOR",
            )
            return self.repo.get_candidate(candidate_id)

        else:
            # Passed Language and Quality
            self.repo.record_processing_decision(
                ProcessingDecisionRecord(
                    candidate_id=candidate_id,
                    stage_name="LANGUAGE_AND_QUALITY",
                    pipeline_version=pipeline_version,
                    decision_outcome="PASS",
                    quality_score=q_score,
                    diagnostic_evidence_json=evidence_json,
                )
            )

        # 2. Near-Duplicate & Semantic Safety Conflict Check
        # Compare against existing approved or pending candidates
        candidates_to_compare = self.repo.list_by_status("APPROVAL_PENDING", limit=200) + \
                                self.repo.list_by_status("APPROVED", limit=200)

        for other in candidates_to_compare:
            if other.candidate_id == cand.candidate_id:
                continue

            dup_res = self.near_dedup_detector.are_near_duplicates(cand.normalized_text, other.normalized_text)
            if dup_res.is_candidate:
                # If safety guard failed, this is a semantic conflict
                if not dup_res.safety_guard_passed:
                    conflict_reason = str(dup_res.safety_guard_violations or dup_res.conflict_type)
                    rel_type = "SEMANTIC_CONFLICT"
                    self.repo.record_duplicate_relationship(
                        DuplicateRelationshipRecord(
                            candidate_id=candidate_id,
                            related_candidate_id=other.candidate_id,
                            relationship_type=rel_type,
                            detector_version=pipeline_version,
                            similarity_score=dup_res.candidate_similarity,
                            is_safe_to_merge=False,
                            conflict_reason=conflict_reason,
                        )
                    )
                    safety_evidence = json.dumps({
                        "related_candidate_id": other.candidate_id,
                        "candidate_similarity": dup_res.candidate_similarity,
                        "conflict_type": dup_res.conflict_type,
                        "violations": str(dup_res.safety_guard_violations),
                    })
                    self.repo.record_processing_decision(
                        ProcessingDecisionRecord(
                            candidate_id=candidate_id,
                            stage_name="SEMANTIC_SAFETY",
                            pipeline_version=pipeline_version,
                            decision_outcome="QUARANTINE",
                            failed_metric=dup_res.conflict_type or "SAFETY_VIOLATION",
                            diagnostic_evidence_json=safety_evidence,
                        )
                    )
                    self._route_to_quarantine(
                        candidate_id=candidate_id,
                        reason="SEMANTIC_SAFETY_CONFLICT",
                        category="SAFETY",
                        evidence_json=safety_evidence,
                        pipeline_version=pipeline_version,
                        assigned_role="ROLE_SAFETY_OFFICER",
                    )
                    return self.repo.get_candidate(candidate_id)
                elif dup_res.is_duplicate:
                    self.repo.record_duplicate_relationship(
                        DuplicateRelationshipRecord(
                            candidate_id=candidate_id,
                            related_candidate_id=other.candidate_id,
                            relationship_type="NEAR_DUPLICATE",
                            detector_version=pipeline_version,
                            similarity_score=dup_res.candidate_similarity,
                            is_safe_to_merge=True,
                            conflict_reason=None,
                        )
                    )

        # 3. All automated checks passed: transition to PROCESSING_PASSED -> APPROVAL_PENDING
        self.repo.record_processing_decision(
            ProcessingDecisionRecord(
                candidate_id=candidate_id,
                stage_name="AUTOMATED_PIPELINE_COMPLETE",
                pipeline_version=pipeline_version,
                decision_outcome="PASS",
            )
        )
        self.repo.update_status(candidate_id, "PROCESSING_PASSED")
        self.repo.update_status(candidate_id, "APPROVAL_PENDING")

        return self.repo.get_candidate(candidate_id)

    def _route_to_quarantine(
        self,
        candidate_id: str,
        reason: str,
        category: str,
        evidence_json: str,
        pipeline_version: str,
        assigned_role: str,
    ) -> None:
        """Internal helper to transition candidate to QUARANTINED and record quarantine_cases entry."""
        case_id = f"urn:uuid:{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        review_due = (now + timedelta(days=30)).isoformat()
        now_iso = now.isoformat()

        with self.repo.conn.transaction() as c:
            # 1. Update candidate status
            c.execute(
                "UPDATE candidate_submissions SET processing_status = 'QUARANTINED', updated_at = ? WHERE candidate_id = ?;",
                (now_iso, candidate_id),
            )
            # 2. Insert quarantine case
            c.execute(
                """
                INSERT INTO quarantine_cases (
                    case_id, candidate_id, quarantine_reason, quarantine_category,
                    diagnostic_evidence_json, pipeline_version, quarantined_at, review_due_at,
                    escalation_level, assigned_role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'STANDARD', ?);
                """,
                (
                    case_id,
                    candidate_id,
                    reason,
                    category,
                    evidence_json,
                    pipeline_version,
                    now_iso,
                    review_due,
                    assigned_role,
                ),
            )
