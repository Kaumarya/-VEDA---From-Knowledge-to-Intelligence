"""
VEDA SQLite Storage Benchmark CLI (Phase 3)

Usage:
    python scripts/benchmark_storage.py
    python scripts/benchmark_storage.py --db data/lexicon/veda_lexicon_sample.sqlite
    python scripts/benchmark_storage.py --db data/lexicon/veda_lexicon_v0.1.sqlite --iterations 10000
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from foundation.lexicon.benchmarks import StorageBenchmarkRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VEDA SQLite Lexicon Benchmark — Latency Distributions & Memory Profiling"
    )
    parser.add_argument(
        "--db",
        "-d",
        type=str,
        default="data/lexicon/veda_lexicon_sample.sqlite",
        help="Path to SQLite lexicon database file (default: data/lexicon/veda_lexicon_sample.sqlite)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=5000,
        help="Number of query iterations per pattern (default: 5000)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional JSON file path to save structured benchmark report",
    )

    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Running benchmarks on {db_path} ({args.iterations:,} iterations per test)...")
    report = StorageBenchmarkRunner.benchmark_database(db_path, iterations=args.iterations)

    print("\n" + report.summary_text() + "\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Report saved to: {out_path}")


if __name__ == "__main__":
    main()
