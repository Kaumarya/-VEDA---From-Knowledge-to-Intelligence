"""
VEDA Word Foundation Demonstration Program (Phase 2)

Demonstrates word representation, normalization, validation,
and character-ID roundtrip conversions from first principles.

Usage:
    python scripts/word_demo.py
    python scripts/word_demo.py --word "Apple"
    python scripts/word_demo.py --interactive
"""

import argparse
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

from foundation.words.analyzer import WordAnalyzer


def inspect_word(analyzer: WordAnalyzer, text: str) -> None:
    """Inspects a word input, printing its normalized form, characters, IDs, and candidate status."""
    print("-" * 64)
    print(f"{'Input:':<22} {text!r}")

    validation = analyzer.validate_candidate(text)
    norm = analyzer.normalize_word(text)

    if validation.is_valid:
        word = analyzer.create_word(text)
        if word.original != word.normalized:
            print(f"{'Original:':<22} {word.original}")
        print(f"{'Normalized:':<22} {word.normalized}")
        print(f"{'Characters:':<22} {' '.join(word.characters)}")
        print(f"{'Length:':<22} {word.length}")
        char_ids = word.character_ids
        print(f"{'Character IDs:':<22} {char_ids}")
        reconstructed = analyzer.decode_word(char_ids)
        print(f"{'Reverse Decoded:':<22} {reconstructed.normalized}")
        print(f"{'Word Candidate:':<22} YES (Valid plain English word candidate)")
        print(f"{'Orthography:':<22} {validation.orthographic_category}")
        print(f"{'Registry Support:':<22} YES (All characters representable)")
    else:
        if norm and norm != text:
            print(f"{'Normalized:':<22} {norm}")
        print(f"{'Word Candidate:':<22} NO / INVALID PLAIN WORD")
        print(f"{'Rejection Reason:':<22} {validation.reason}")
        if validation.details:
            print(f"{'Details:':<22} {validation.details}")
        print(f"{'Orthography:':<22} {validation.orthographic_category}")
        reg_status = (
            "YES (All characters representable)"
            if validation.is_representable
            else f"NO (Unsupported chars: {validation.unsupported_characters})"
        )
        print(f"{'Registry Support:':<22} {reg_status}")


def run_demo(analyzer: WordAnalyzer) -> None:
    """Runs the primary test cases specified in the Master Prompt."""
    print("=" * 64)
    print("               VEDA WORD FOUNDATION v0.1")
    print("=" * 64)

    demo_inputs = [
        "apple",
        "Apple",
        "hello!",
        "123",
        "computer",
        "veda",
        "café",
        "hello😊",
    ]

    for item in demo_inputs:
        inspect_word(analyzer, item)
    print("-" * 64 + "\n")



def run_interactive(analyzer: WordAnalyzer) -> None:
    """Interactive loop to test arbitrary word candidate inputs."""
    print("\n" + "=" * 50)
    print(" VEDA WORD FOUNDATION — INTERACTIVE REPL")
    print(" Type any word or string to analyze candidate status.")
    print(" Type ':quit' or ':exit' to quit.")
    print("=" * 50 + "\n")

    while True:
        try:
            val = input("VEDA-Word> ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if val.strip() in (":quit", ":exit"):
            break
        if not val.strip():
            continue

        inspect_word(analyzer, val)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="VEDA Word Foundation Demonstration")
    parser.add_argument("--word", "-w", type=str, help="Single word/string to inspect")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive REPL mode")
    args = parser.parse_args()

    analyzer = WordAnalyzer()

    if args.interactive:
        run_interactive(analyzer)
    elif args.word is not None:
        inspect_word(analyzer, args.word)
    else:
        run_demo(analyzer)


if __name__ == "__main__":
    main()
