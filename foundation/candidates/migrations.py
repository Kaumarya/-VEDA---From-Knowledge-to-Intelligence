"""
VEDA Candidate Database Subsystem — Versioned Migration Engine
Phase 4.14.2
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.exceptions import (
    MigrationError,
    MigrationChecksumMismatchError,
    UnsupportedSchemaVersionError,
)
from foundation.candidates.schema import (
    MIGRATION_001_CORE,
    MIGRATION_002_REVIEWER_SECURITY,
    MIGRATION_003_APPROVALS_QUARANTINE_EXPORT,
)


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    description: str
    sql: str

    @property
    def checksum(self) -> str:
        """Computes deterministic SHA-256 checksum over migration SQL."""
        return hashlib.sha256(self.sql.strip().encode("utf-8")).hexdigest()


# Deterministic ordered registry of migrations
ALL_MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        name="001_core_schema",
        description="Core ingestion tables: migrations, candidate sources, submissions, decisions, duplicate relationships",
        sql=MIGRATION_001_CORE,
    ),
    Migration(
        version=2,
        name="002_reviewer_security",
        description="Reviewer identity: accounts, RBAC roles, public keys, authentication and key lifecycle events",
        sql=MIGRATION_002_REVIEWER_SECURITY,
    ),
    Migration(
        version=3,
        name="003_approvals_quarantine_export",
        description="Governance: approval history, quarantine cases, retention decisions, export batches, triggers and views",
        sql=MIGRATION_003_APPROVALS_QUARANTINE_EXPORT,
    ),
]


class MigrationManager:
    """Manages transactional, checksummed, versioned migrations for the candidate SQLite database."""

    def __init__(self, connection: CandidateDatabaseConnection, migrations: Optional[List[Migration]] = None):
        self.conn = connection
        self.migrations = sorted(migrations or ALL_MIGRATIONS, key=lambda m: m.version)

    def init_migrations_table(self) -> None:
        """Ensures the schema_migrations table exists."""
        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version             INTEGER PRIMARY KEY,
            name                TEXT NOT NULL,
            applied_at          TEXT NOT NULL,
            checksum            TEXT NOT NULL,
            description         TEXT NOT NULL
        );
        """
        with self.conn.transaction() as c:
            c.executescript(sql)

    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Returns all applied migrations ordered by version."""
        self.init_migrations_table()
        rows = self.conn.fetchall("SELECT version, name, applied_at, checksum, description FROM schema_migrations ORDER BY version ASC;")
        return [dict(r) for r in rows]

    def get_current_version(self) -> int:
        """Returns the current applied schema version, or 0 if uninitialized."""
        applied = self.get_applied_migrations()
        return applied[-1]["version"] if applied else 0

    def verify_historical_migrations(self) -> None:
        """
        Verifies that previously applied migrations match current code definitions.
        Detects altered historical checksums and unsupported future versions.
        """
        applied = self.get_applied_migrations()
        max_registered = max([m.version for m in self.migrations], default=0)

        migration_by_version = {m.version: m for m in self.migrations}

        for record in applied:
            v = record["version"]
            if v > max_registered:
                raise UnsupportedSchemaVersionError(
                    f"Database has future schema version {v}, but latest supported version is {max_registered}."
                )
            expected = migration_by_version.get(v)
            if expected is None:
                raise MigrationError(f"Database contains recorded migration version {v} not present in migration registry.")
            if record["checksum"] != expected.checksum:
                raise MigrationChecksumMismatchError(
                    f"Checksum mismatch for migration {v} ({expected.name}). Recorded: {record['checksum'][:8]}..., Expected: {expected.checksum[:8]}... Historical migrations must not be altered."
                )

    def get_pending_migrations(self) -> List[Migration]:
        """Returns migrations that have not yet been applied."""
        self.verify_historical_migrations()
        current_version = self.get_current_version()
        return [m for m in self.migrations if m.version > current_version]

    def apply_migration(self, migration: Migration) -> None:
        """Applies a single migration transactionally and records its execution."""
        applied_at = datetime.now(timezone.utc).isoformat()
        # Wrap DDL and audit registration in atomic transaction
        escaped_desc = migration.description.replace("'", "''")
        script = f"""
        BEGIN IMMEDIATE;
        {migration.sql}
        INSERT INTO schema_migrations (version, name, applied_at, checksum, description)
        VALUES ({migration.version}, '{migration.name}', '{applied_at}', '{migration.checksum}', '{escaped_desc}');
        COMMIT;
        """
        conn = self.conn._raw_conn if self.conn._raw_conn is not None else self.conn.connect()
        try:
            conn.executescript(script)
        except Exception:
            if conn.in_transaction:
                try:
                    conn.execute("ROLLBACK;")
                except Exception:
                    pass
            raise

    def apply_all(self) -> int:
        """
        Verifies history and applies all pending migrations in strict version order.
        Returns the number of migrations applied.
        """
        self.init_migrations_table()
        self.verify_historical_migrations()
        pending = self.get_pending_migrations()
        applied_count = 0
        for migration in pending:
            self.apply_migration(migration)
            applied_count += 1
        return applied_count
