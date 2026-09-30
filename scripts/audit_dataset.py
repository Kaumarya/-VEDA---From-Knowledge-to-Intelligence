"""
VEDA Dataset Audit CLI (Phase 3 — Lexicon Readiness & Unicode Profiling)

Usage:
    python scripts/audit_dataset.py
    python scripts/audit_dataset.py --file veda_sample.jsonl
    python scripts/audit_dataset.py --file raw-wiktextract-data.jsonl --max-lines 50000
    python scripts/audit_dataset.py --file veda_sample.jsonl --output data/audit_sample.json
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

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.audit import DatasetAuditor
from foundation.words.analyzer import WordAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VEDA Dataset Audit — Empirical Quality, Unicode, and Memory Profiling"
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="veda_sample.jsonl",
        help="Target JSONL dataset file (default: veda_sample.jsonl)",
    )
    parser.add_argument(
        "--max-lines",
        "-n",
        type=int,
        default=None,
        help="Optional line limit for sampling large datasets",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional JSON file path to save structured audit report",
    )

    args = parser.parse_args()

    registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
    analyzer = WordAnalyzer(registry=registry)
    auditor = DatasetAuditor(registry=registry, analyzer=analyzer)

    target_path = Path(args.file)
    if not target_path.is_file():
        print(f"Error: Target file not found: {target_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting VEDA Dataset Audit on: {target_path} (max_lines={args.max_lines})...")
    report = auditor.audit_file(target_path, max_lines=args.max_lines)

    print("\n" + report.summary_text() + "\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Report saved to: {out_path}")


if __name__ == "__main__":
    main()
