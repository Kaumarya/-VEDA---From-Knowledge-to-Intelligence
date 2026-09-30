"""
VEDA Lexical Foundation Demonstration Program (Phase 3)

Demonstrates streaming Wiktionary ingestion, lexical aggregation,
POS filtering, word sense inspection, and integration with the Character Registry.

Usage:
    python scripts/lexicon_demo.py
    python scripts/lexicon_demo.py --word "dictionary"
    python scripts/lexicon_demo.py --interactive
    python scripts/lexicon_demo.py --file "veda_sample.jsonl"
"""

import argparse
import sys
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
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.lexicon import Lexicon
from foundation.lexicon.schemas import LexicalEntry
from foundation.words.analyzer import WordAnalyzer


def display_entry(entry: LexicalEntry, analyzer: WordAnalyzer) -> None:
    """Prints a detailed view of a LexicalEntry formatted for the console."""
    print("=" * 60)
    print(f" WORD: {entry.word.upper()} (canonical: '{entry.normalized}')")
    print("=" * 60)
    print(f"Language:            {entry.language} (English)")
    print(f"Parts of Speech:     {', '.join(entry.parts_of_speech) if entry.parts_of_speech else 'N/A'}")
    print(f"Primary POS:         {entry.primary_pos or 'N/A'}")

    if entry.pronunciations:
        print(f"Pronunciation (IPA): {', '.join(entry.pronunciations[:3])}")

    # Morphological & Character integration
    word_obj = entry.to_word(registry=analyzer.registry)
    print(f"Length:              {word_obj.length} characters")
    print(f"Characters:          {' '.join(word_obj.characters)}")
    try:
        print(f"Character IDs:       {word_obj.character_ids}")
    except ValueError as e:
        print(f"Character IDs:       Error ({e})")

    if entry.forms:
        print(f"Inflected Forms:     {', '.join(entry.forms[:5])}")

    if entry.synonyms:
        print(f"Synonyms:            {', '.join(entry.synonyms[:5])}")

    if entry.antonyms:
        print(f"Antonyms:            {', '.join(entry.antonyms[:5])}")

    print("\n--- Definitions by Part of Speech ---")
    for pos, defs in entry.definitions_by_pos.items():
        print(f"[{pos.upper()}] ({len(defs)} definitions):")
        for i, d in enumerate(defs[:3], 1):
            print(f"  {i}. {d}")
        if len(defs) > 3:
            print(f"  ... and {len(defs) - 3} more definition(s)")

    print()


def run_showcase(lexicon: Lexicon, analyzer: WordAnalyzer) -> None:
    """Runs the primary educational showcase."""
    print("=" * 60)
    print("        VEDA ENGLISH LEXICAL FOUNDATION v0.1")
    print("       (Phase 3 — Wiktionary Streaming Ingestion)")
    print("=" * 60)
    print()

    print(lexicon.stats.summary_text())
    print()

    summary = lexicon.summary()
    print("Lexicon Summary:")
    print(f"  Total Indexed Words:     {summary['total_words']}")
    print(f"  Total Definitions:       {summary['total_definitions']}")
    print(f"  Avg Definitions/Word:    {summary['avg_definitions_per_word']}")
    print("  POS Distribution:")
    for pos, count in summary["pos_distribution"].items():
        print(f"    - {pos:10s}: {count} word(s)")
    print()

    print("-" * 60)
    print(" Detailed Word Inspections:")
    print("-" * 60)
    for word_norm in lexicon.words():
        entry = lexicon[word_norm]
        display_entry(entry, analyzer)


def run_interactive(lexicon: Lexicon, analyzer: WordAnalyzer) -> None:
    """Interactive dictionary lookup loop."""
    print("\n" + "=" * 60)
    print(" VEDA LEXICON — INTERACTIVE LOOKUP")
    print(f" Vocabulary: {len(lexicon)} words indexed from Wiktionary.")
    print(" Type a word to query its definition, POS, and character decomposition.")
    print(" Type ':words' to list all words. Type ':quit' to exit.")
    print("=" * 60 + "\n")

    while True:
        try:
            query = input("VEDA-Lexicon> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if query in (":quit", ":exit", "q"):
            break
        if query == ":words":
            print(f"Available words ({len(lexicon)}): {', '.join(lexicon.words())}\n")
            continue
        if not query:
            continue

        entry = lexicon.get(query)
        if entry is None:
            # Check candidate status
            val = analyzer.validate_candidate(query)
            if val.is_valid:
                print(f"'{query}' is a valid English candidate, but is NOT in this demo lexicon sample.")
            else:
                print(f"'{query}' is NOT a valid plain English candidate ({val.reason}).")
            print()
        else:
            display_entry(entry, analyzer)


def main() -> None:
    parser = argparse.ArgumentParser(description="VEDA Lexical Foundation Demonstration")
    parser.add_argument("--word", "-w", type=str, help="Specific word to inspect")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive lookup REPL")
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="veda_sample.jsonl",
        help="Path to JSONL dataset (default: veda_sample.jsonl)",
    )
    args = parser.parse_args()

    registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
    analyzer = WordAnalyzer(registry=registry)

    # Check for pre-existing serialized lexicon or extract dynamically
    lexicon_cache = Path("data/lexicon/veda_lexicon_v0.1.json")
    dataset_file = Path(args.file)

    if dataset_file.is_file():
        extractor = WiktionaryExtractor(analyzer=analyzer)
        lexicon = extractor.extract_lexicon(dataset_file)
    elif lexicon_cache.is_file():
        lexicon = Lexicon.from_json_file(lexicon_cache, registry=registry)
    else:
        print(f"Error: Neither dataset '{args.file}' nor cached lexicon found.")
        sys.exit(1)

    analyzer.set_lexicon(lexicon)

    if args.interactive:
        run_interactive(lexicon, analyzer)
    elif args.word is not None:
        entry = lexicon.get(args.word)
        if entry is None:
            print(f"Word '{args.word}' not found in lexicon.")
        else:
            display_entry(entry, analyzer)
    else:
        run_showcase(lexicon, analyzer)


if __name__ == "__main__":
    main()
