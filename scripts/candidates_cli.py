"""
VEDA Unified CLI — Candidate Subsystem Commands
Phase 4.14.2
Usage:
    python veda.py candidate status
    python veda.py candidate init
    python veda.py candidate migrate
    python veda.py candidate version
    python veda.py candidate verify
    python veda.py candidate benchmark
"""

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager, ALL_MIGRATIONS
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.models import CandidateSourceRecord


def cmd_status() -> int:
    """Inspects candidate database status and statistics."""
    config = CandidateDatabaseConfig.default_production()
    db_path = config.db_path

    print("VEDA Candidate Database Subsystem Status")
    print("=" * 45)
    print(f"Target Database: {db_path}")

    if not db_path.exists():
        print("Status: NOT INITIALIZED")
        print("Database file does not exist on disk.")
        print("Run 'python veda.py candidate init' to explicitly initialize.")
        return 0

    size_kb = db_path.stat().st_size / 1024
    print(f"Status: INITIALIZED ({size_kb:.1f} KB)")

    with CandidateDatabaseConnection(config) as db:
        # Check foreign keys and journal mode
        fk_on = db.fetchone("PRAGMA foreign_keys;")
        journal = db.fetchone("PRAGMA journal_mode;")
        print(f"Foreign Keys Enforced: {'YES' if fk_on and fk_on[0] == 1 else 'NO'}")
        print(f"Journal Mode: {journal[0].upper() if journal else 'UNKNOWN'}")

        # Schema version
        mgr = MigrationManager(db)
        version = mgr.get_current_version()
        applied = mgr.get_applied_migrations()
        print(f"Applied Schema Version: {version} ({len(applied)} migrations)")

        # Candidate counts
        try:
            total_cand = db.fetchone("SELECT COUNT(*) FROM candidate_submissions;")[0]
            canonical = db.fetchone("SELECT COUNT(*) FROM candidate_submissions WHERE is_canonical = 1;")[0]
            print(f"\nCandidates:")
            print(f"  Total Submissions: {total_cand}")
            print(f"  Canonical: {canonical}")
            print(f"  Duplicates: {total_cand - canonical}")

            # Status breakdown
            rows = db.fetchall(
                "SELECT processing_status, COUNT(*) as cnt FROM candidate_submissions GROUP BY processing_status ORDER BY cnt DESC;"
            )
            if rows:
                print("  Status Breakdown:")
                for r in rows:
                    print(f"    - {r['processing_status']}: {r['cnt']}")

            # Quarantine
            open_q = db.fetchone("SELECT COUNT(*) FROM quarantine_cases WHERE resolution_decision_id IS NULL;")[0]
            print(f"\nQuarantine Queue:")
            print(f"  Active Unresolved Cases: {open_q}")

            # Reviewers
            revs = db.fetchone("SELECT COUNT(*) FROM reviewer_accounts;")[0]
            keys = db.fetchone("SELECT COUNT(*) FROM reviewer_public_keys;")[0]
            print(f"\nGovernance:")
            print(f"  Registered Reviewers: {revs}")
            print(f"  Registered Public Keys: {keys}")

            # Export Batches
            batches = db.fetchone("SELECT COUNT(*) FROM export_batches;")[0]
            print(f"  Export Batches: {batches}")
        except Exception as e:
            print(f"\nNotice: Tables not fully queried ({e})")

    return 0


def cmd_init() -> int:
    """Explicitly initializes a new candidate database and applies all migrations."""
    config = CandidateDatabaseConfig.default_production()
    db_path = config.db_path

    print(f"Initializing VEDA Candidate Database at {db_path}...")
    with CandidateDatabaseConnection(config) as db:
        mgr = MigrationManager(db)
        current = mgr.get_current_version()
        if current >= len(ALL_MIGRATIONS):
            print(f"Candidate database is already at current schema version {current}.")
            return 0

        count = mgr.apply_all()
        applied = mgr.get_applied_migrations()
        print(f"Successfully initialized candidate database! Applied {count} migrations:")
        for m in applied:
            print(f"  - Version {m['version']:03d} ({m['name']}) [SHA-256: {m['checksum'][:16]}...]")

    return 0


def cmd_migrate() -> int:
    """Applies any pending migrations."""
    config = CandidateDatabaseConfig.default_production()
    with CandidateDatabaseConnection(config) as db:
        mgr = MigrationManager(db)
        count = mgr.apply_all()
        if count == 0:
            print(f"Database schema is up to date (version {mgr.get_current_version()}).")
        else:
            applied = mgr.get_applied_migrations()
            print(f"Applied {count} pending migrations:")
            for m in applied:
                print(f"  - Version {m['version']:03d} ({m['name']})")
    return 0


def cmd_version() -> int:
    """Displays applied migrations and checksums."""
    config = CandidateDatabaseConfig.default_production()
    if not config.db_path.exists():
        print(f"Candidate database does not exist at {config.db_path}.")
        return 1

    with CandidateDatabaseConnection(config) as db:
        mgr = MigrationManager(db)
        applied = mgr.get_applied_migrations()
        print("Applied Candidate Database Migrations:")
        print("-" * 65)
        for m in applied:
            print(f"Version: {m['version']:03d} | Name: {m['name']:<25} | Applied: {m['applied_at']}")
            print(f"Checksum: {m['checksum']}")
            print("-" * 65)
    return 0


def cmd_verify() -> int:
    """Verifies relational database integrity, foreign keys, triggers, and views."""
    config = CandidateDatabaseConfig.default_production()
    if not config.db_path.exists():
        print(f"Database file does not exist at {config.db_path}.")
        return 1

    print("Running Candidate Database Integrity Verification...")
    with CandidateDatabaseConnection(config) as db:
        # 1. Integrity check
        integ = db.fetchone("PRAGMA integrity_check;")
        print(f"  SQLite Page Integrity: {integ[0]}")
        if integ[0] != "ok":
            print("ERROR: Database page corruption detected!", file=sys.stderr)
            return 1

        # 2. Foreign key check
        fk_violations = db.fetchall("PRAGMA foreign_key_check;")
        if fk_violations:
            print(f"ERROR: {len(fk_violations)} foreign key violations found!", file=sys.stderr)
            return 1
        print("  Foreign Key Constraints: OK (0 violations)")

        # 3. Verify all 16 tables
        tables = [
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
            "schema_migrations",
        ]
        db_tables = {r[0] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table';")}
        missing = [t for t in tables if t not in db_tables]
        if missing:
            print(f"ERROR: Missing required tables: {missing}", file=sys.stderr)
            return 1
        print(f"  Required Relational Tables: OK (all {len(tables)} verified)")

        # 4. Verify triggers
        triggers = {r[0] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='trigger';")}
        expected_triggers = [
            "trig_abort_approval_history_update",
            "trig_abort_approval_history_delete",
            "trig_abort_public_key_mutation",
            "trig_abort_decision_update",
            "trig_enforce_signed_approval_mutation",
            "trig_abort_unauthorized_quarantine_exit",
            "trig_prevent_escalation_status_tampering",
        ]
        missing_trig = [t for t in expected_triggers if t not in triggers]
        if missing_trig:
            print(f"ERROR: Missing triggers: {missing_trig}", file=sys.stderr)
            return 1
        print(f"  Database Security Triggers: OK (all {len(expected_triggers)} active)")

        # 5. Verify view
        views = {r[0] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='view';")}
        if "v_export_eligible_candidates" not in views:
            print("ERROR: Missing view v_export_eligible_candidates", file=sys.stderr)
            return 1
        print("  Export Eligibility View: OK (v_export_eligible_candidates active)")

    print("\nALL CANDIDATE DATABASE INTEGRITY CHECKS PASSED.")
    return 0


def cmd_benchmark() -> int:
    """Executes synthetic performance benchmark measuring ingestion, hashing, and lookups."""
    import tempfile
    print("Running Candidate Database Synthetic Performance Benchmark...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = CandidateDatabaseConfig.for_testing(Path(tmp_dir))
        with CandidateDatabaseConnection(config) as db:
            mgr = MigrationManager(db)
            mgr.apply_all()
            repo = CandidateRepository(db)

            # Seed source
            repo.upsert_source(
                CandidateSourceRecord(
                    source_id="src_bench",
                    name="Benchmark Synthetic Source",
                    version="1.0.0",
                    licensing_status="VERIFIED PERMITTED",
                    license_name="CC0-1.0",
                    training_permitted_status="EXPLICITLY_PERMITTED",
                    commercial_permitted=True,
                    artifact_sha256="1" * 64,
                    registry_entry_sha256="2" * 64,
                    approval_expiration_date="2099-12-31",
                )
            )

            # Ingest 250 records
            n = 250
            t0 = time.perf_counter()
            candidates = []
            for i in range(n):
                text = f"Synthetic candidate sentence number {i} for benchmarking indexing speed."
                c = repo.submit_candidate(text, "src_bench", f"doc_{i}")
                candidates.append(c)
            dur_insert = time.perf_counter() - t0
            throughput = n / dur_insert

            # Lookups
            t1 = time.perf_counter()
            for c in candidates:
                repo.get_by_raw_hash(c.raw_content_hash)
                repo.get_by_normalized_hash(c.normalized_content_hash)
            dur_lookup = time.perf_counter() - t1
            lookup_latency_us = (dur_lookup / (n * 2)) * 1_000_000

            print(f"  Ingestion Throughput: {throughput:.1f} candidates/sec ({n} records in {dur_insert:.3f}s)")
            print(f"  Indexed Lookup Latency: {lookup_latency_us:.1f} microseconds / query")
            print("Benchmark completed successfully.")
    return 0


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print("VEDA Candidate Database CLI")
        print("\nUsage:")
        print("    python veda.py candidate status")
        print("    python veda.py candidate init")
        print("    python veda.py candidate migrate")
        print("    python veda.py candidate version")
        print("    python veda.py candidate verify")
        print("    python veda.py candidate benchmark")
        sys.exit(0)

    sub = sys.argv[1]
    if sub == "status":
        sys.exit(cmd_status())
    elif sub == "init":
        sys.exit(cmd_init())
    elif sub == "migrate":
        sys.exit(cmd_migrate())
    elif sub == "version":
        sys.exit(cmd_version())
    elif sub == "verify":
        sys.exit(cmd_verify())
    elif sub == "benchmark":
        sys.exit(cmd_benchmark())
    else:
        print(f"Unknown candidate command: '{sub}'. Run 'python veda.py candidate --help'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
