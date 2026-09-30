"""
VEDA Lexicon Storage CLI (Phase 3 — SQLite Persistence)

Provides command-line commands for:
- Building sample or full SQLite lexicon databases
- Looking up words with POS filtering and morphological inspection
- Inspecting database metadata and ingestion audit statistics
- Verifying database integrity (PRAGMA integrity_check and foreign keys)
- Benchmarking query latency distributions and process memory

Usage:
    python scripts/lexicon_cli.py build-sample
    python scripts/lexicon_cli.py build [--source <path>] [--batch-size 25000] [--max-lines <N>]
    python scripts/lexicon_cli.py lookup <word> [--pos <pos>] [--exact-surface] [--db <path>]
    python scripts/lexicon_cli.py stats [--db <path>]
    python scripts/lexicon_cli.py verify [--db <path>]
    python scripts/lexicon_cli.py benchmark [--db <path>] [--iterations <N>]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

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
from foundation.lexicon.benchmarks import StorageBenchmarkRunner
from foundation.lexicon.schemas import LexicalEntry
from foundation.lexicon.storage import SqliteLexicon, SqliteLexiconBuilder
from foundation.words.analyzer import WordAnalyzer


DEFAULT_SAMPLE_SOURCE = PROJECT_ROOT / "veda_sample.jsonl"
DEFAULT_SAMPLE_DB = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_sample.sqlite"
DEFAULT_FULL_SOURCE = PROJECT_ROOT / "raw-wiktextract-data.jsonl"
DEFAULT_FULL_DB = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_v0.1.sqlite"


def get_default_db() -> Path:
    """Returns production DB if it exists, otherwise sample DB."""
    if DEFAULT_FULL_DB.is_file():
        return DEFAULT_FULL_DB
    return DEFAULT_SAMPLE_DB


def cmd_build_sample(args: argparse.Namespace) -> None:
    source_path = Path(args.source) if args.source else DEFAULT_SAMPLE_SOURCE
    db_path = Path(args.output) if args.output else DEFAULT_SAMPLE_DB

    if not source_path.is_file():
        print(f"Error: Sample source file not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print(" VEDA LEXICON — BUILD SAMPLE DATABASE")
    print("=" * 65)
    print(f"Source file:   {source_path}")
    print(f"Target DB:     {db_path}")
    print(f"Batch size:    {args.batch_size}")
    print(f"Rebuild mode:  {args.rebuild}")
    print()

    builder = SqliteLexiconBuilder()
    start_time = time.perf_counter()

    db = builder.build(
        source_file=source_path,
        db_path=db_path,
        batch_size=args.batch_size,
        max_lines=args.max_lines,
        rebuild=args.rebuild,
    )
    elapsed = time.perf_counter() - start_time
    count = db.count()
    health = db.integrity_check()
    db.close()

    db_size_bytes = db_path.stat().st_size
    print("-" * 65)
    print(f"Build complete in {elapsed:.3f}s")
    print(f"Total Unique Words: {count:,}")
    print(f"Database Size:      {db_size_bytes / 1024:.1f} KB ({db_size_bytes:,} bytes)")
    print(f"Integrity Check:    {'PASSED (ok)' if health['is_healthy'] else 'FAILED'}")
    print("=" * 65)


def cmd_build(args: argparse.Namespace) -> None:
    source_path = Path(args.source) if args.source else DEFAULT_FULL_SOURCE
    db_path = Path(args.output) if args.output else DEFAULT_FULL_DB

    if not source_path.is_file():
        print(f"Error: Source dataset not found: {source_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print(" VEDA LEXICON — FULL PRODUCTION INGESTION")
    print("=" * 65)
    print(f"Source:        {source_path} ({source_path.stat().st_size / (1024**3):.2f} GB)")
    print(f"Target DB:     {db_path}")
    print(f"Batch size:    {args.batch_size:,} records")
    print(f"Max lines:     {args.max_lines if args.max_lines else 'Unlimited'}")
    print(f"Validation:    {'Enabled (v0.1 ASCII Plain English)' if not args.no_validate else 'Disabled'}")
    print(f"Rebuild:       {args.rebuild}")
    print("-" * 65)

    builder = SqliteLexiconBuilder()

    last_report_time = [time.perf_counter()]

    def on_progress(p: dict) -> None:
        now = time.perf_counter()
        if now - last_report_time[0] >= 5.0 or p["total_lines_read"] % 100000 == 0:
            last_report_time[0] = now
            print(
                f"[{p['elapsed_seconds']:7.1f}s] Lines: {p['total_lines_read']:,} | "
                f"English: {p['english_records']:,} | "
                f"Valid: {p['valid_candidates']:,} | "
                f"Rate: {p['rate']:,.0f} lines/sec"
            )

    start_time = time.perf_counter()
    db = builder.build(
        source_file=source_path,
        db_path=db_path,
        batch_size=args.batch_size,
        max_lines=args.max_lines,
        validate_candidates=not args.no_validate,
        rebuild=args.rebuild,
        progress_callback=on_progress,
        report_every=args.report_every,
    )
    total_elapsed = time.perf_counter() - start_time
    total_words = db.count()
    health = db.integrity_check()
    latest_stats = db.get_latest_ingestion_stats()
    db.close()

    db_size = db_path.stat().st_size
    print("=" * 65)
    print(" INGESTION COMPLETE")
    print("=" * 65)
    print(f"Total Elapsed Time:    {total_elapsed:.2f} seconds ({total_elapsed / 60:.2f} minutes)")
    print(f"Total Unique Words:    {total_words:,}")
    print(f"Database Size:         {db_size / (1024**2):.2f} MB ({db_size:,} bytes)")
    print(f"Integrity Status:      {'HEALTHY (ok)' if health['is_healthy'] else 'CORRUPT'}")
    if latest_stats:
        print(f"Total Lines Processed: {latest_stats['total_lines_read']:,}")
        print(f"English Records:       {latest_stats['english_records']:,}")
        print(f"Valid Candidates:      {latest_stats['valid_candidates']:,}")
        print(f"Rejections Tracked:    {latest_stats['invalid_candidates_skipped']:,}")
        print(f"Duplicate Merges:      {latest_stats['duplicate_records']:,}")
        print(f"Throughput:            {latest_stats['throughput_lines_sec']:,.0f} lines/sec")
        if latest_stats.get("peak_memory_mb"):
            print(f"Peak Memory (RSS):     {latest_stats['peak_memory_mb']:.2f} MB")
    print("=" * 65)


def display_entry(entry: LexicalEntry, analyzer: WordAnalyzer) -> None:
    print("=" * 65)
    print(f" WORD: {entry.word.upper()} (canonical: '{entry.normalized}')")
    print("=" * 65)
    print(f"Language:            {entry.language} (English)")
    print(f"Parts of Speech:     {', '.join(entry.parts_of_speech) if entry.parts_of_speech else 'N/A'}")
    print(f"Primary POS:         {entry.primary_pos or 'N/A'}")

    if entry.pronunciations:
        print(f"Pronunciation (IPA): {', '.join(entry.pronunciations[:3])}")

    word_obj = entry.to_word(registry=analyzer.registry)
    print(f"Length:              {word_obj.length} characters")
    print(f"Characters:          {' '.join(word_obj.characters)}")
    try:
        print(f"Character IDs:       {word_obj.character_ids}")
    except ValueError as e:
        print(f"Character IDs:       Error ({e})")

    if entry.forms:
        print(f"Inflected Forms:     {', '.join(entry.forms[:8])}")
    if entry.synonyms:
        print(f"Synonyms:            {', '.join(entry.synonyms[:6])}")
    if entry.antonyms:
        print(f"Antonyms:            {', '.join(entry.antonyms[:6])}")
    if entry.etymology:
        print(f"Etymology:           {entry.etymology[:120]}{'...' if len(entry.etymology) > 120 else ''}")

    print("\n--- Definitions by Part of Speech ---")
    for pos, defs in entry.definitions_by_pos.items():
        print(f"[{pos.upper()}] ({len(defs)} definitions):")
        for i, d in enumerate(defs[:4], 1):
            print(f"  {i}. {d}")
        if len(defs) > 4:
            print(f"  ... and {len(defs) - 4} more definition(s)")

    if entry.senses:
        examples_list = []
        for s in entry.senses:
            for ex in s.examples:
                if ex and ex not in examples_list:
                    examples_list.append(ex)
        if examples_list:
            print("\n--- Usage Examples ---")
            for i, ex in enumerate(examples_list[:3], 1):
                print(f"  * \"{ex}\"")

    if entry.provenance:
        print(f"\nProvenance:          {entry.provenance.get('source_dataset', 'Wiktionary')} (v{entry.provenance.get('extractor_version', '0.1.0')})")
    print("=" * 65)


def cmd_lookup(args: argparse.Namespace) -> None:
    db_path = Path(args.db) if args.db else get_default_db()
    if not db_path.is_file():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
    analyzer = WordAnalyzer(registry=registry)

    with SqliteLexicon(db_path, read_only=True, registry=registry) as db:
        entry = db.lookup(args.word, pos=args.pos, exact_surface=args.exact_surface)

        if entry is None:
            pos_msg = f" with POS '{args.pos}'" if args.pos else ""
            surface_msg = " (exact surface match)" if args.exact_surface else ""
            print(f"Word '{args.word}'{pos_msg}{surface_msg} was not found in {db_path.name}.")
            sys.exit(1)

        if args.json:
            print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))
        else:
            display_entry(entry, analyzer)


def cmd_stats(args: argparse.Namespace) -> None:
    db_path = Path(args.db) if args.db else get_default_db()
    if not db_path.is_file():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    with SqliteLexicon(db_path, read_only=True) as db:
        meta = db.get_metadata()
        health = db.integrity_check()
        latest_stats = db.get_latest_ingestion_stats()

    db_size = db_path.stat().st_size
    print("=" * 65)
    print(f" VEDA LEXICON DATABASE STATISTICS: {db_path.name}")
    print("=" * 65)
    print(f"Database Path:        {db_path}")
    print(f"Database File Size:   {db_size / (1024**2):.2f} MB ({db_size:,} bytes)")
    print(f"Schema Version:       {meta.schema_version}")
    print(f"Extractor Version:    {meta.extractor_version}")
    print(f"Language Scope:       {meta.language_scope}")
    print(f"Source Dataset:       {meta.source_dataset or 'Unknown'}")
    print(f"Total Unique Words:   {meta.word_count:,}")
    print(f"Words Table Rows:     {health['words_row_count']:,}")
    print(f"POS Index Rows:       {health['word_pos_row_count']:,}")
    print(f"Senses Table Rows:    {health['senses_row_count']:,}")
    print(f"Integrity Status:     {'OK (PRAGMA integrity_check passed)' if health['is_healthy'] else 'CORRUPT'}")

    print("\n--- Part-of-Speech Distribution ---")
    sorted_pos = sorted(meta.pos_distribution.items(), key=lambda kv: kv[1], reverse=True)
    for pos, count in sorted_pos[:15]:
        pct = (count / meta.word_count * 100.0) if meta.word_count > 0 else 0.0
        print(f"  {pos:15s}: {count:8,} words ({pct:5.1f}%)")
    if len(sorted_pos) > 15:
        print(f"  ... and {len(sorted_pos) - 15} more parts of speech")

    if latest_stats:
        print("\n--- Latest Ingestion Audit Record ---")
        print(f"Source File:          {latest_stats['source_file']}")
        print(f"Total Lines Read:     {latest_stats['total_lines_read']:,}")
        print(f"English Records:      {latest_stats['english_records']:,}")
        print(f"Valid Candidates:     {latest_stats['valid_candidates']:,}")
        print(f"Invalid Skipped:      {latest_stats['invalid_candidates_skipped']:,}")
        print(f"Duplicate Merges:     {latest_stats['duplicate_records']:,}")
        print(f"Malformed Records:    {latest_stats['malformed_json_records']:,}")
        print(f"Throughput:           {latest_stats['throughput_lines_sec']:,.0f} lines/sec")
        print(f"Elapsed Time:         {latest_stats['elapsed_seconds']:.2f}s")
        if latest_stats.get("peak_memory_mb"):
            print(f"Peak Process Memory:  {latest_stats['peak_memory_mb']:.2f} MB")
        print(f"Completed At:         {latest_stats['completed_at']}")
        if latest_stats.get("rejection_reasons"):
            print("  Top Rejection Reasons:")
            reasons = sorted(latest_stats["rejection_reasons"].items(), key=lambda x: x[1], reverse=True)
            for r, c in reasons[:5]:
                print(f"    - {r}: {c:,}")
    print("=" * 65)


def cmd_verify(args: argparse.Namespace) -> None:
    db_path = Path(args.db) if args.db else get_default_db()
    if not db_path.is_file():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print(f" RUNNING INTEGRITY VERIFICATION: {db_path.name}")
    print("=" * 65)

    with SqliteLexicon(db_path, read_only=True) as db:
        health = db.integrity_check()

    print(f"PRAGMA integrity_check:        {', '.join(health['sqlite_integrity_check'])}")
    print(f"Foreign Key Violations:        {len(health['foreign_key_violations'])}")
    print(f"Words Table Row Count:         {health['words_row_count']:,}")
    print(f"Word-POS Relational Rows:      {health['word_pos_row_count']:,}")
    print(f"Distinct Words in POS Index:   {health['distinct_normalized_words_in_pos']:,}")
    print(f"Senses Table Row Count:        {health['senses_row_count']:,}")

    if health["is_healthy"]:
        print("\nRESULT: [PASS] Database integrity is 100% verified.")
    else:
        print("\nRESULT: [FAIL] Database contains integrity violations!")
        sys.exit(1)
    print("=" * 65)


def cmd_benchmark(args: argparse.Namespace) -> None:
    db_path = Path(args.db) if args.db else get_default_db()
    if not db_path.is_file():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Running benchmarks on {db_path} ({args.iterations:,} iterations per pattern)...")
    report = StorageBenchmarkRunner.benchmark_database(db_path, iterations=args.iterations)
    print("\n" + report.summary_text() + "\n")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"Benchmark results saved to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="veda lexicon",
        description="VEDA Lexicon Storage CLI — Management, Ingestion, Lookups & Benchmarking",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: build-sample
    p_build_sample = subparsers.add_parser("build-sample", help="Build sample database from veda_sample.jsonl")
    p_build_sample.add_argument("--source", "-s", type=str, default=None, help="Path to sample JSONL")
    p_build_sample.add_argument("--output", "-o", type=str, default=None, help="Target SQLite path")
    p_build_sample.add_argument("--batch-size", "-b", type=int, default=1000, help="Transaction batch size")
    p_build_sample.add_argument("--max-lines", "-n", type=int, default=None, help="Maximum lines to process")
    p_build_sample.add_argument("--rebuild", action="store_true", default=True, help="Force rebuild (default: True)")

    # Subcommand: build
    p_build = subparsers.add_parser("build", help="Ingest full dataset into production SQLite database")
    p_build.add_argument("--source", "-s", type=str, default=None, help="Path to raw JSONL dataset")
    p_build.add_argument("--output", "-o", type=str, default=None, help="Target SQLite path")
    p_build.add_argument("--batch-size", "-b", type=int, default=25000, help="Transaction batch size (default: 25,000)")
    p_build.add_argument("--max-lines", "-n", type=int, default=None, help="Maximum lines to process")
    p_build.add_argument("--no-validate", action="store_true", default=False, help="Disable v0.1 word candidate validation")
    p_build.add_argument("--rebuild", action="store_true", default=True, help="Force clean rebuild (default: True)")
    p_build.add_argument("--report-every", type=int, default=25000, help="Progress callback frequency in lines")

    # Subcommand: lookup
    p_lookup = subparsers.add_parser("lookup", help="Look up a word in the lexicon")
    p_lookup.add_argument("word", type=str, help="Word to query")
    p_lookup.add_argument("--pos", "-p", type=str, default=None, help="Filter by part of speech (e.g. noun, verb)")
    p_lookup.add_argument("--exact-surface", action="store_true", default=False, help="Require exact surface case match")
    p_lookup.add_argument("--db", "-d", type=str, default=None, help="Path to SQLite database")
    p_lookup.add_argument("--json", action="store_true", default=False, help="Output raw JSON")

    # Subcommand: stats
    p_stats = subparsers.add_parser("stats", help="Inspect database statistics and ingestion audit")
    p_stats.add_argument("--db", "-d", type=str, default=None, help="Path to SQLite database")

    # Subcommand: verify
    p_verify = subparsers.add_parser("verify", help="Run database integrity check and validation")
    p_verify.add_argument("--db", "-d", type=str, default=None, help="Path to SQLite database")

    # Subcommand: benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run storage latency and memory benchmarks")
    p_bench.add_argument("--db", "-d", type=str, default=None, help="Path to SQLite database")
    p_bench.add_argument("--iterations", "-n", type=int, default=5000, help="Iterations per test (default: 5000)")
    p_bench.add_argument("--output", "-o", type=str, default=None, help="Save JSON report to path")

    args = parser.parse_args()

    if args.command == "build-sample":
        cmd_build_sample(args)
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "lookup":
        cmd_lookup(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
