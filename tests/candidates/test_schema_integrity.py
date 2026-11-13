"""
Tests for Complete Relational Database Schema Integrity & Triggers
Phase 4.14.2 — Stage 2
"""

import sqlite3
import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager


@pytest.fixture
def migrated_db(tmp_path: Path):
    """Provides a fresh, fully migrated test database connection."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()
        yield db


def test_schema_creates_all_16_tables_and_view(migrated_db: CandidateDatabaseConnection):
    """Verify all 16 architectural tables and views exist."""
    rows = migrated_db.fetchall("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view');")
    names = {r["name"] for r in rows}

    expected_tables = {
        "schema_migrations",
        "candidate_sources",
        "candidate_submissions",
        "processing_decisions",
        "duplicate_relationships",
        "reviewer_accounts",
        "reviewer_roles",
        "reviewer_account_roles",
        "reviewer_public_keys",
        "authentication_events",
        "key_lifecycle_events",
        "approval_history",
        "quarantine_cases",
        "retention_decisions",
        "export_batches",
        "export_batch_items",
    }
    for table in expected_tables:
        assert table in names, f"Expected table {table} was not created."

    assert "v_export_eligible_candidates" in names


def test_foreign_key_violation_rejected(migrated_db: CandidateDatabaseConnection):
    """Verify inserting candidate with non-existent source_id violates FK constraint."""
    with pytest.raises(sqlite3.IntegrityError):
        migrated_db.execute(
            """
            INSERT INTO candidate_submissions (
                candidate_id, source_id, source_document_id, original_text, normalized_text,
                raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count, approx_word_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "cand_001",
                "non_existent_source",
                "doc_1",
                "Hello text",
                "Hello text",
                "a" * 64,
                "a" * 64,
                10,
                10,
                2,
            ),
        )


def test_invalid_status_check_constraint(migrated_db: CandidateDatabaseConnection):
    """Verify that inserting an illegal candidate lifecycle status fails CHECK constraint."""
    # First insert a valid source
    migrated_db.execute(
        """
        INSERT INTO candidate_sources (
            source_id, name, version, licensing_status, license_name, training_permitted_status, artifact_sha256, registry_entry_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("SRC_01", "Test Source", "1.0", "VERIFIED PERMITTED", "CC0", "EXPLICITLY_PERMITTED", "b" * 64, "c" * 64),
    )

    with pytest.raises(sqlite3.IntegrityError):
        migrated_db.execute(
            """
            INSERT INTO candidate_submissions (
                candidate_id, source_id, source_document_id, original_text, normalized_text,
                raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count, approx_word_count,
                processing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "cand_002",
                "SRC_01",
                "doc_1",
                "Hello",
                "Hello",
                "a" * 64,
                "a" * 64,
                5,
                5,
                1,
                "INVALID_STATUS_FOOBAR",
            ),
        )


def test_trigger_aborts_approval_history_update_and_delete(migrated_db: CandidateDatabaseConnection):
    """Verify triggers prevent update or deletion of approval_history records."""
    # Seed reviewer account and role
    migrated_db.execute(
        "INSERT INTO reviewer_accounts (reviewer_id, username, full_name, email) VALUES (?, ?, ?, ?);",
        ("rev_1", "jdoe", "Jane Doe", "jdoe@veda.internal"),
    )
    migrated_db.execute(
        "INSERT INTO reviewer_public_keys (public_key_id, reviewer_id, public_key_hex, key_status) VALUES (?, ?, ?, ?);",
        ("key_1", "rev_1", "d" * 64, "ACTIVE"),
    )
    migrated_db.execute(
        "INSERT INTO authentication_events (auth_event_id, reviewer_id, auth_method, client_host, auth_status, session_expires_at) VALUES (?, ?, ?, ?, ?, ?);",
        ("auth_1", "rev_1", "LOCAL_PASSWORD_MFA", "localhost", "SUCCESS", "2099-01-01T00:00:00Z"),
    )
    # Seed source and candidate
    migrated_db.execute(
        """
        INSERT INTO candidate_sources (
            source_id, name, version, licensing_status, license_name, training_permitted_status, artifact_sha256, registry_entry_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("SRC_01", "Test Source", "1.0", "VERIFIED PERMITTED", "CC0", "EXPLICITLY_PERMITTED", "b" * 64, "c" * 64),
    )
    migrated_db.execute(
        """
        INSERT INTO candidate_submissions (
            candidate_id, source_id, source_document_id, original_text, normalized_text,
            raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count, approx_word_count, processing_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("cand_003", "SRC_01", "doc_1", "Text", "Text", "a" * 64, "a" * 64, 4, 4, 1, "APPROVAL_PENDING"),
    )
    # Insert approval_history record
    migrated_db.execute(
        """
        INSERT INTO approval_history (
            candidate_id, decision_id, reviewer_id, reviewer_role, public_key_id, auth_event_id,
            old_status, new_status, decision_reason, canonical_payload_json, canonical_payload_sha256, signature_ed25519
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            "cand_003",
            "dec_001",
            "rev_1",
            "DOMAIN_CURATOR",
            "key_1",
            "auth_1",
            "APPROVAL_PENDING",
            "APPROVED",
            "Valid expository prose",
            "{}",
            "e" * 64,
            "f" * 128,
        ),
    )

    # Attempt UPDATE on approval_history -> must fail with SECURITY VIOLATION trigger
    with pytest.raises(sqlite3.DatabaseError, match="approval_history records are immutable"):
        migrated_db.execute("UPDATE approval_history SET decision_reason = 'Hacked reason' WHERE decision_id = 'dec_001';")

    # Attempt DELETE on approval_history -> must fail with SECURITY VIOLATION trigger
    with pytest.raises(sqlite3.DatabaseError, match="approval_history records are permanent"):
        migrated_db.execute("DELETE FROM approval_history WHERE decision_id = 'dec_001';")


def test_trigger_prevents_public_key_mutation(migrated_db: CandidateDatabaseConnection):
    """Verify trigger prevents altering public key material once registered."""
    migrated_db.execute(
        "INSERT INTO reviewer_accounts (reviewer_id, username, full_name, email) VALUES (?, ?, ?, ?);",
        ("rev_2", "asmith", "Alice Smith", "asmith@veda.internal"),
    )
    migrated_db.execute(
        "INSERT INTO reviewer_public_keys (public_key_id, reviewer_id, public_key_hex, key_status) VALUES (?, ?, ?, ?);",
        ("key_2", "rev_2", "1" * 64, "ACTIVE"),
    )

    # Attempt to change public_key_hex
    with pytest.raises(sqlite3.DatabaseError, match="Public key material is cryptographically immutable"):
        migrated_db.execute("UPDATE reviewer_public_keys SET public_key_hex = ? WHERE public_key_id = ?;", ("2" * 64, "key_2"))


def test_trigger_blocks_approved_mutation_without_valid_human_record(migrated_db: CandidateDatabaseConnection):
    """Verify trigger trig_enforce_signed_approval_mutation prevents setting APPROVED directly."""
    migrated_db.execute(
        """
        INSERT INTO candidate_sources (
            source_id, name, version, licensing_status, license_name, training_permitted_status, artifact_sha256, registry_entry_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("SRC_02", "Test Source 2", "1.0", "VERIFIED PERMITTED", "CC0", "EXPLICITLY_PERMITTED", "b" * 64, "c" * 64),
    )
    migrated_db.execute(
        """
        INSERT INTO candidate_submissions (
            candidate_id, source_id, source_document_id, original_text, normalized_text,
            raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count, approx_word_count, processing_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("cand_004", "SRC_02", "doc_1", "Direct approve test", "Direct approve test", "a" * 64, "a" * 64, 19, 19, 3, "APPROVAL_PENDING"),
    )

    # Attempt to mutate status to APPROVED without an approval_history entry
    with pytest.raises(sqlite3.DatabaseError, match="Cannot mark candidate APPROVED without an authenticated, verified human Ed25519 approval event"):
        migrated_db.execute("UPDATE candidate_submissions SET processing_status = 'APPROVED' WHERE candidate_id = 'cand_004';")


def test_trigger_blocks_quarantine_exit_without_resolution_record(migrated_db: CandidateDatabaseConnection):
    """Verify candidate cannot exit QUARANTINED without a valid resolved quarantine_cases record."""
    migrated_db.execute(
        """
        INSERT INTO candidate_sources (
            source_id, name, version, licensing_status, license_name, training_permitted_status, artifact_sha256, registry_entry_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("SRC_03", "Test Source 3", "1.0", "VERIFIED PERMITTED", "CC0", "EXPLICITLY_PERMITTED", "b" * 64, "c" * 64),
    )
    migrated_db.execute(
        """
        INSERT INTO candidate_submissions (
            candidate_id, source_id, source_document_id, original_text, normalized_text,
            raw_content_hash, normalized_content_hash, raw_char_count, normalized_char_count, approx_word_count, processing_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        ("cand_005", "SRC_03", "doc_1", "Quarantined test", "Quarantined test", "a" * 64, "a" * 64, 16, 16, 2, "QUARANTINED"),
    )

    # Attempt to transition out of QUARANTINED to APPROVAL_PENDING without human resolution
    with pytest.raises(sqlite3.DatabaseError, match="Candidate cannot exit QUARANTINED without an authenticated human cryptographic resolution record"):
        migrated_db.execute("UPDATE candidate_submissions SET processing_status = 'APPROVAL_PENDING' WHERE candidate_id = 'cand_005';")

