"""
Tests for Candidate Database Initialization and Migration Framework
Phase 4.14.2 — Stage 1
"""

import sqlite3
import pytest
from pathlib import Path
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager, Migration
from foundation.candidates.exceptions import (
    ConfigurationError,
    DatabaseConnectionError,
    MigrationChecksumMismatchError,
    UnsupportedSchemaVersionError,
)


def test_config_forbidden_paths():
    """Verify that candidate database cannot be configured inside data/lexicon."""
    with pytest.raises(ConfigurationError, match="SAFETY VIOLATION"):
        CandidateDatabaseConfig(db_path=Path("data/lexicon/veda_lexicon_v0.1.sqlite"))

    with pytest.raises(ConfigurationError, match="SAFETY VIOLATION"):
        CandidateDatabaseConfig(db_path=Path("data/lexicon/candidates.sqlite"))


def test_database_initialization_and_parent_dir(tmp_path: Path):
    """Verify that parent directories are created automatically and connection succeeds."""
    nested_dir = tmp_path / "deeply" / "nested" / "candidates"
    config = CandidateDatabaseConfig.for_testing(nested_dir)
    assert not nested_dir.exists()

    with CandidateDatabaseConnection(config) as db:
        assert nested_dir.exists()
        assert config.db_path.exists()
        # Test basic query
        row = db.fetchone("SELECT 1 AS val;")
        assert row["val"] == 1


def test_foreign_keys_strictly_enforced(tmp_path: Path):
    """Verify that PRAGMA foreign_keys is strictly ON."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        row = db.fetchone("PRAGMA foreign_keys;")
        assert row[0] == 1


def test_migration_framework_apply_all(tmp_path: Path):
    """Verify that MigrationManager applies all pending migrations in order."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        assert manager.get_current_version() == 0

        applied_count = manager.apply_all()
        assert applied_count == 4
        assert manager.get_current_version() == 4

        # Applying again is idempotent and applies 0 migrations
        assert manager.apply_all() == 0

        # Verify applied records
        applied = manager.get_applied_migrations()
        assert len(applied) == 4
        assert [r["version"] for r in applied] == [1, 2, 3, 4]
        for r in applied:
            assert len(r["checksum"]) == 64
            assert r["applied_at"] is not None


def test_migration_checksum_tamper_detection(tmp_path: Path):
    """Verify that altering historical migration SQL triggers MigrationChecksumMismatchError."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        # Tamper with the checksum in schema_migrations
        db.execute("UPDATE schema_migrations SET checksum = 'tampered_hash_000000000000000000000000000000000000000000000000000' WHERE version = 1;")

        # Subsequent check should raise MigrationChecksumMismatchError
        with pytest.raises(MigrationChecksumMismatchError):
            manager.apply_all()


def test_unsupported_future_version_detection(tmp_path: Path):
    """Verify that future unsupported schema versions in DB trigger UnsupportedSchemaVersionError."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        # Insert a future schema version (e.g. version 99)
        db.execute(
            "INSERT INTO schema_migrations (version, name, applied_at, checksum, description) VALUES (99, 'future_99', '2099-01-01', 'hash', 'future');"
        )

        with pytest.raises(UnsupportedSchemaVersionError):
            manager.get_pending_migrations()


def test_interrupted_migration_rollback(tmp_path: Path):
    """Verify that a failing migration rolls back cleanly and doesn't partially commit."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.init_migrations_table()

        bad_migration = Migration(
            version=1,
            name="bad_migration",
            description="Intentionally invalid SQL",
            sql="CREATE TABLE test_good (id INT); INVALID SQL STATEMENT SYNTAX ERROR;",
        )

        with pytest.raises(Exception):
            manager.apply_migration(bad_migration)

        # Confirm rollback: test_good was not created and migration 1 was not recorded
        assert manager.get_current_version() == 0
        tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table' AND name='test_good';")
        assert len(tables) == 0


def test_production_and_test_database_isolation(tmp_path: Path):
    """Verify that test configuration is completely isolated from production default path."""
    prod_config = CandidateDatabaseConfig()
    test_config = CandidateDatabaseConfig.for_testing(tmp_path)

    assert prod_config.is_test_mode is False
    assert test_config.is_test_mode is True
    assert prod_config.db_path != test_config.db_path
    assert not str(test_config.db_path).startswith("data/candidates")

