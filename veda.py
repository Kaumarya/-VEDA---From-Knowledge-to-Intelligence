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

# Python 3.14 Standardization Guidance Notice
if sys.version_info < (3, 14):
    sys.stderr.write(
        f"VEDA Notice: Project is standardized on Python 3.14+. Active interpreter: Python {sys.version.split()[0]}. "
        f"Please execute commands using the dedicated .venv environment (.\\.venv\\Scripts\\python.exe).\n"
    )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "help"):
        print("VEDA — From Knowledge to Intelligence")
        print("\nUsage:")
        print("    python veda.py <subsystem> <command> [options]")
        print("\nCommands:")
        print("    lexicon <command>      Interact with the SQLite production lexicon")
        print("    corpus <command>       Interact with the training corpus pipeline")
        print("    candidate <command>    Interact with the candidate database subsystem")
        print("\nLexicon subcommands: build-sample, build, lookup, stats, verify, benchmark")
        print("Corpus subcommands: sources, pilot, build-golden, inspect-manifest, verify")
        print("Candidate subcommands: status, init, migrate, version, verify, benchmark, backup")
        sys.exit(0)

    subcommand = sys.argv[1]

    if subcommand == "lexicon":
        # Forward arguments to lexicon_cli.py
        from scripts.lexicon_cli import main as lexicon_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        lexicon_main()
    elif subcommand == "corpus":
        # Forward arguments to corpus_cli.py
        from scripts.corpus_cli import main as corpus_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        corpus_main()
    elif subcommand == "candidate":
        # Forward arguments to candidates_cli.py
        from scripts.candidates_cli import main as candidate_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        candidate_main()
    else:
        print(f"Unknown command: {subcommand}. Try: 'python veda.py --help'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
