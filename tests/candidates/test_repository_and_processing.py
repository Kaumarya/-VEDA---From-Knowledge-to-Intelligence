"""
Tests for Candidate Repository, Lifecycle State Machine & Processing Integration
Phase 4.14.2 — Stage 3
"""

import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.processing import CandidateProcessor
from foundation.candidates.models import CandidateSourceRecord, ProcessingDecisionRecord
from foundation.candidates.exceptions import (
    EmptySubmissionError,
    ValidationError,
    InvalidStateTransitionError,
)


@pytest.fixture
def repo_and_db(tmp_path: Path):
    """Provides an initialized test repository with seed source."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()
        repo = CandidateRepository(db)

        # Seed valid source
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="SRC_GUTENBERG",
                name="Project Gutenberg",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="Public Domain",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="1" * 64,
                registry_entry_sha256="2" * 64,
            )
        )
        yield repo, db


def test_submission_rejects_empty_and_whitespace(repo_and_db):
    """Verify empty or whitespace-only submissions are rejected with EmptySubmissionError."""
    repo, _ = repo_and_db
    with pytest.raises(EmptySubmissionError):
        repo.submit_candidate("", "SRC_GUTENBERG", "doc_1")

    with pytest.raises(EmptySubmissionError):
        repo.submit_candidate("   \n\t  ", "SRC_GUTENBERG", "doc_1")


def test_submission_preserves_original_and_normalizes_deterministically(repo_and_db):
    """Verify original text is preserved verbatim while normalized text and hashes are computed."""
    repo, _ = repo_and_db
    raw_text = "This   is  a   “test”   sentence with   irregular  spaces."
    cand = repo.submit_candidate(raw_text, "SRC_GUTENBERG", "doc_1")

    assert cand.original_text == raw_text
    assert cand.normalized_text != raw_text
    assert "   " not in cand.normalized_text  # Irregular spaces normalized
    assert len(cand.raw_content_hash) == 64
    assert len(cand.normalized_content_hash) == 64
    assert cand.processing_status == "RECEIVED"
    assert cand.is_canonical is True


def test_duplicate_submission_canonical_tracking(repo_and_db):
    """Verify second identical submission from same source is marked non-canonical duplicate."""
    repo, _ = repo_and_db
    text = "The quick brown fox jumps over the lazy dog."
    cand1 = repo.submit_candidate(text, "SRC_GUTENBERG", "doc_1")
    cand2 = repo.submit_candidate(text, "SRC_GUTENBERG", "doc_2")

    assert cand1.is_canonical is True
    assert cand1.canonical_candidate_id is None

    assert cand2.is_canonical is False
    assert cand2.canonical_candidate_id == cand1.candidate_id


def test_state_machine_illegal_transition_rejected(repo_and_db):
    """Verify state machine rejects illegal state transitions."""
    repo, _ = repo_and_db
    cand = repo.submit_candidate("Valid English sentence for testing.", "SRC_GUTENBERG", "doc_1")

    # Direct transition from RECEIVED to EXPORTED is illegal
    with pytest.raises(InvalidStateTransitionError):
        repo.update_status(cand.candidate_id, "EXPORTED")

    # Direct transition from RECEIVED to APPROVED without human authorization is illegal
    with pytest.raises(InvalidStateTransitionError):
        repo.update_status(cand.candidate_id, "APPROVED", is_human=False)


def test_automated_processing_pipeline_to_approval_pending(repo_and_db):
    """
    Verify automated pipeline processes valid English sentence to APPROVAL_PENDING.
    Must NEVER automatically set status to APPROVED.
    """
    repo, _ = repo_and_db
    processor = CandidateProcessor(repo)

    cand = repo.submit_candidate(
        "The development of artificial intelligence requires careful attention to the language that is used in the training corpus.",
        "SRC_GUTENBERG",
        "doc_10",
    )

    processed = processor.process_candidate(cand.candidate_id)
    assert processed.processing_status == "APPROVAL_PENDING"
    assert processed.processing_status != "APPROVED"

    decisions = repo.get_processing_decisions(cand.candidate_id)
    assert len(decisions) >= 2
    outcomes = [d.decision_outcome for d in decisions]
    assert "PASS" in outcomes


def test_automated_processing_quarantines_safety_conflict(repo_and_db):
    """
    Verify that a near-duplicate with polarity conflict is routed to QUARANTINED.
    """
    repo, db = repo_and_db
    processor = CandidateProcessor(repo)

    # 1. First submit and process a base sentence
    cand1 = repo.submit_candidate("The proposed treaty was accepted by all participating nations in the summit.", "SRC_GUTENBERG", "doc_1")
    processor.process_candidate(cand1.candidate_id)

    # 2. Submit a contradictory sentence (negation / polarity inversion)
    cand2 = repo.submit_candidate("The proposed treaty was not accepted by all participating nations in the summit.", "SRC_GUTENBERG", "doc_2")
    processed2 = processor.process_candidate(cand2.candidate_id)

    # Must be quarantined due to semantic safety conflict
    assert processed2.processing_status == "QUARANTINED"

    # Verify quarantine_cases record
    row = db.fetchone("SELECT * FROM quarantine_cases WHERE candidate_id = ?;", (cand2.candidate_id,))
    assert row is not None
    assert row["quarantine_reason"] == "SEMANTIC_SAFETY_CONFLICT"
    assert row["quarantine_category"] == "SAFETY"
    assert row["resolution_decision_id"] is None
