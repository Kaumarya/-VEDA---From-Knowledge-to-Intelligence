"""
VEDA Candidate Database Subsystem — Database Connection Factory
Phase 4.14.2
"""

import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional, Any, List, Tuple
from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.exceptions import DatabaseConnectionError


class CandidateDatabaseConnection:
    """
    Manages safe, parameterized SQLite connections to the VEDA Candidate Database.
    Guarantees foreign key enforcement, WAL mode, timeouts, and transaction isolation.
    """

    def __init__(self, config: CandidateDatabaseConfig):
        self.config = config
        self._raw_conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Establishes, configures, and verifies a SQLite connection."""
        try:
            self.config.ensure_parent_dir()
            # Explicit timeout in seconds
            conn = sqlite3.connect(
                str(self.config.db_path),
                timeout=self.config.timeout_seconds,
                isolation_level=None,  # Autocommit mode; explicit transactions managed manually
            )
            conn.row_factory = sqlite3.Row

            # 1. Mandatory Foreign Key Enforcement
            conn.execute("PRAGMA foreign_keys = ON;")
            cur = conn.execute("PRAGMA foreign_keys;")
            fk_status = cur.fetchone()[0]
            if fk_status != 1:
                conn.close()
                raise DatabaseConnectionError("CRITICAL: Failed to enable SQLite foreign_keys constraint.")

            # 2. Busy Timeout in milliseconds
            busy_timeout_ms = int(self.config.timeout_seconds * 1000)
            conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")

            # 3. Journal Mode
            if self.config.wal_mode:
                conn.execute("PRAGMA journal_mode = WAL;")

            # 4. Synchronous Durability
            conn.execute(f"PRAGMA synchronous = {self.config.synchronous};")

            self._raw_conn = conn
            return conn

        except Exception as e:
            if isinstance(e, DatabaseConnectionError):
                raise
            raise DatabaseConnectionError(f"Failed to connect to candidate database at {self.config.db_path}: {e}") from e

    def close(self) -> None:
        """Safely closes the connection if open."""
        if self._raw_conn is not None:
            try:
                self._raw_conn.close()
            except Exception:
                pass
            finally:
                self._raw_conn = None

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for an atomic database transaction.
        Begins transaction explicitly, commits on clean exit, rolls back on error.
        """
        conn = self._raw_conn if self._raw_conn is not None else self.connect()
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE;")
        try:
            yield conn
            if conn.in_transaction:
                conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                try:
                    conn.execute("ROLLBACK;")
                except Exception:
                    pass
            raise

    def execute(self, sql: str, params: Tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Executes a parameterized SQL statement."""
        if self._raw_conn is None:
            self.connect()
        assert self._raw_conn is not None
        return self._raw_conn.execute(sql, params)

    def fetchone(self, sql: str, params: Tuple[Any, ...] = ()) -> Optional[sqlite3.Row]:
        """Fetches a single row from a parameterized query."""
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        """Fetches all rows from a parameterized query."""
        cur = self.execute(sql, params)
        return cur.fetchall()

    def __enter__(self) -> "CandidateDatabaseConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
