"""
VEDA Unified CLI Entrypoint ("From Knowledge to Intelligence")

Usage:
    python veda.py lexicon build-sample
    python veda.py lexicon build [--batch-size 25000] [--max-lines <N>]
    python veda.py lexicon lookup <word> [--pos <pos>]
    python veda.py lexicon stats
    python veda.py lexicon verify
    python veda.py lexicon benchmark
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("VEDA — From Knowledge to Intelligence")
        print("\nUsage:")
        print("    python veda.py lexicon <command> [options]")
        print("\nCommands:")
        print("    lexicon build-sample   Build sample SQLite lexicon database")
        print("    lexicon build          Ingest full Wiktextract dataset into SQLite")
        print("    lexicon lookup <word>  Look up a word in the database")
        print("    lexicon stats          Display database metadata and ingestion stats")
        print("    lexicon verify         Run SQLite PRAGMA integrity verification")
        print("    lexicon benchmark      Run query latency and memory benchmarks")
        sys.exit(0)

    subcommand = sys.argv[1]

    if subcommand == "lexicon":
        # Forward arguments to lexicon_cli.py
        from scripts.lexicon_cli import main as lexicon_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        lexicon_main()
    else:
        print(f"Unknown command: {subcommand}. Try: 'python veda.py lexicon --help'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
