"""
VEDA Candidate Database Subsystem — Configuration
Phase 4.14.2
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from foundation.candidates.exceptions import ConfigurationError


DEFAULT_CANDIDATE_DB_PATH = Path("data/candidates/veda_candidates.sqlite")
FORBIDDEN_LEXICON_PATH = Path("data/lexicon/veda_lexicon_v0.1.sqlite")


@dataclass(frozen=True)
class CandidateDatabaseConfig:
    """Configuration for Candidate SQLite database connection and runtime parameters."""
    db_path: Path = DEFAULT_CANDIDATE_DB_PATH
    timeout_seconds: float = 30.0
    wal_mode: bool = True
    synchronous: str = "NORMAL"  # Recommended for WAL mode
    foreign_keys: bool = True
    is_test_mode: bool = False
    max_batch_size: int = 1000

    def __post_init__(self) -> None:
        # Validate that candidate database is never configured at lexicon path
        resolved_db = self.db_path.resolve()
        resolved_lex = FORBIDDEN_LEXICON_PATH.resolve()
        if resolved_db == resolved_lex:
            raise ConfigurationError(
                f"SAFETY VIOLATION: Candidate database path cannot be the production lexicon ({FORBIDDEN_LEXICON_PATH})."
            )
        if "data/lexicon" in str(self.db_path).replace("\\", "/"):
            raise ConfigurationError(
                f"SAFETY VIOLATION: Candidate database cannot reside inside data/lexicon directory: {self.db_path}"
            )
        if self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive.")
        if self.synchronous not in ("OFF", "NORMAL", "FULL", "EXTRA"):
            raise ConfigurationError(f"Invalid synchronous setting: {self.synchronous}")

    def ensure_parent_dir(self) -> None:
        """Ensures that the parent directory for the database file exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default_production(cls) -> "CandidateDatabaseConfig":
        """Factory for the default production candidate database configuration."""
        return cls()

    @classmethod
    def for_testing(cls, test_dir: Path, db_name: str = "test_candidates.sqlite") -> "CandidateDatabaseConfig":
        """Factory for an isolated, safe test database in a temporary directory."""
        test_path = test_dir / db_name
        return cls(
            db_path=test_path,
            timeout_seconds=10.0,
            wal_mode=False,  # In-memory/temp files test cleanly in DELETE/OFF mode
            synchronous="OFF",  # Fast execution in isolated tests
            foreign_keys=True,
            is_test_mode=True,
        )

