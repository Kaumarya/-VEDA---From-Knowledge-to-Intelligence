"""
Tests for Candidate Database Backup, WAL Checkpointing, and Integrity Verification
Phase 4.14.2.1 — Issue 8
"""

import sqlite3
from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.models import CandidateSourceRecord


@pytest.fixture
def backup_env(tmp_path: Path):
    """Sets up an environment with active database content and migrations."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)

        # Seed data
        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_bk_01",
                name="Backup Test Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="5" * 64,
                registry_entry_sha256="6" * 64,
            )
        )
        for i in range(10):
            repo.submit_candidate(f"Candidate sentence number {i} for backup validation.", "src_bk_01", f"doc_{i}")

        reviewers.create_reviewer("backup_admin", "Backup Admin", "admin@backup.internal")

        yield {
            "config": config,
            "db": db,
            "tmp_path": tmp_path,
        }


def test_consistent_online_backup_and_restoration(backup_env):
    """
    Verify that CandidateDatabaseConnection.backup creates a clean, atomic snapshot
    using the SQLite Backup API with WAL checkpointing, verified by quick_check and foreign_key_check.
    """
    db = backup_env["db"]
    tmp_path = backup_env["tmp_path"]
    backup_file = tmp_path / "backups" / "test_backup.sqlite"

    # Create backup
    db.backup(backup_file)
    assert backup_file.exists()
    assert backup_file.stat().st_size > 50_000

    # Verify backup integrity directly using sqlite3
    conn = sqlite3.connect(str(backup_file))
    try:
        cur = conn.cursor()
        chk = cur.execute("PRAGMA quick_check;").fetchone()[0]
        assert chk == "ok"

        fk_violations = cur.execute("PRAGMA foreign_key_check;").fetchall()
        assert len(fk_violations) == 0

        # Verify content count in backup snapshot
        cand_count = cur.execute("SELECT COUNT(*) FROM candidate_submissions;").fetchone()[0]
        assert cand_count == 10

        rev_count = cur.execute("SELECT COUNT(*) FROM reviewer_accounts;").fetchone()[0]
        assert rev_count == 1
    finally:
        conn.close()


def test_backup_can_be_mounted_as_independent_candidate_db(backup_env):
    """
    Verify that the backup SQLite file can be configured and accessed as a first-class
    CandidateDatabaseConnection instance.
    """
    db = backup_env["db"]
    tmp_path = backup_env["tmp_path"]
    backup_file = tmp_path / "restored.sqlite"

    db.backup(backup_file)

    # Mount as new CandidateDatabaseConfig
    restored_config = CandidateDatabaseConfig(
        db_path=backup_file,
        timeout_seconds=5.0,
        is_test_mode=True,
    )

    with CandidateDatabaseConnection(restored_config) as restored_db:
        repo = CandidateRepository(restored_db)
        candidates = repo.list_by_status("RECEIVED", limit=50)
        assert len(candidates) == 10
        assert candidates[0].processing_status == "RECEIVED"
