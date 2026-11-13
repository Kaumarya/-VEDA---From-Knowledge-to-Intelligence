"""
Tests for Quarantine Lifecycle Invariants, SLA Escalation, and Non-Mutation Contracts
Phase 4.14.2.1 — Issue 6
"""

from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.models import CandidateSourceRecord


@pytest.fixture
def inv_env(tmp_path: Path):
    """Sets up an environment with a quarantined candidate."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        quarantine = QuarantineManager(db, repo, reviewers)

        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_inv_01",
                name="Invariant Test Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="4" * 64,
                registry_entry_sha256="5" * 64,
            )
        )

        cand = repo.submit_candidate("Quarantined text for SLA testing.", "src_inv_01", "doc_inv_01")
        repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
        repo.update_status(cand.candidate_id, "QUARANTINED")
        case = repo.create_quarantine_case(
            cand.candidate_id,
            reason="LANGUAGE_FILTER_AMBIGUOUS",
            category="LANGUAGE",
            evidence_json='{"dialect":"archaic"}',
            assigned_role="ROLE_DOMAIN_CURATOR",
        )

        yield {
            "config": config,
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "quarantine": quarantine,
            "cand": cand,
            "case": case,
        }


def test_quarantine_sla_progression_strictly_non_mutating(inv_env):
    """
    Verify that advancing SLA through 7, 14, 21, 30 (ESCALATED_30_DAYS), and 60+ (CRITICAL_60_DAYS)
    updates monitoring timestamps and escalation levels but strictly leaves processing_status as QUARANTINED.
    """
    env = inv_env
    quarantine = env["quarantine"]
    repo = env["repo"]
    cand_id = env["cand"].candidate_id
    case_id = env["case"].case_id

    # 1. Day 7 Reminder
    lvl7 = quarantine.check_and_escalate_sla(case_id, age_days=7)
    assert lvl7 == "STANDARD"
    c7 = repo.get_candidate(cand_id)
    assert c7.processing_status == "QUARANTINED"
    assert quarantine.get_case(case_id).last_reminder_at is not None

    # 2. Day 14 Reminder
    lvl14 = quarantine.check_and_escalate_sla(case_id, age_days=14)
    assert lvl14 == "STANDARD"
    c14 = repo.get_candidate(cand_id)
    assert c14.processing_status == "QUARANTINED"

    # 3. Day 21 Reminder
    lvl21 = quarantine.check_and_escalate_sla(case_id, age_days=21)
    assert lvl21 == "STANDARD"
    c21 = repo.get_candidate(cand_id)
    assert c21.processing_status == "QUARANTINED"

    # 4. Day 30 Escalation
    lvl30 = quarantine.check_and_escalate_sla(case_id, age_days=30)
    assert lvl30 == "ESCALATED_30_DAYS"
    case30 = quarantine.get_case(case_id)
    assert case30.escalation_level == "ESCALATED_30_DAYS"
    assert case30.escalated_at is not None
    # Candidate status MUST NEVER change
    c30 = repo.get_candidate(cand_id)
    assert c30.processing_status == "QUARANTINED"

    # 5. Day 60+ Critical Backlog Escalation
    lvl60 = quarantine.check_and_escalate_sla(case_id, age_days=65)
    assert lvl60 == "CRITICAL_60_DAYS"
    case60 = quarantine.get_case(case_id)
    assert case60.escalation_level == "CRITICAL_60_DAYS"
    # Candidate status MUST NEVER change
    c60 = repo.get_candidate(cand_id)
    assert c60.processing_status == "QUARANTINED"


def test_quarantine_reboot_and_reprocessing_never_auto_resolves(inv_env):
    """
    Verify that application restart or re-processing never auto-resolves quarantine.
    """
    env = inv_env
    config = env["config"]
    cand_id = env["cand"].candidate_id
    case_id = env["case"].case_id

    # Simulate restart by reconnecting
    with CandidateDatabaseConnection(config) as new_db:
        new_repo = CandidateRepository(new_db)
        new_quarantine = QuarantineManager(new_db, new_repo, ReviewerService(new_db))

        cand = new_repo.get_candidate(cand_id)
        assert cand.processing_status == "QUARANTINED"

        case = new_quarantine.get_case(case_id)
        assert case.resolution_decision_id is None
        assert case.resolved_at is None


def test_trigger_blocks_direct_sql_unauthorized_quarantine_exit(inv_env):
    """
    Verify that trigger trig_abort_unauthorized_quarantine_exit prevents modifying
    candidate status away from QUARANTINED without an explicit human resolution record.
    """
    env = inv_env
    db = env["db"]
    cand_id = env["cand"].candidate_id

    # Attempt direct SQL update of processing_status while quarantine case is unresolved
    with pytest.raises(Exception, match="SECURITY VIOLATION: Candidate cannot exit QUARANTINED"):
        db.execute(
            "UPDATE candidate_submissions SET processing_status = 'APPROVAL_PENDING' WHERE candidate_id = ?;",
            (cand_id,),
        )
