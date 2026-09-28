"""
VEDA Character Knowledge Demonstration Program (Phase 1)

Demonstrates structured symbolic character knowledge for:
- English letters (A, m, etc.)
- Punctuation (!)
- Digits (7)
- Non-English / Out-of-vocabulary characters (☃)

Usage:
    python scripts/character_demo.py
    python scripts/character_demo.py --char "A"
    python scripts/character_demo.py --interactive
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

from foundation.characters.knowledge import CharacterKnowledge
from foundation.characters.schemas import CharacterKnowledgeEntry


def print_character_card(entry: CharacterKnowledgeEntry) -> None:
    """Prints a clean, human-readable card for a character knowledge entry."""
    print("-" * 42)
    # Character display (repr-safe for non-ASCII)
    ch_display = entry.character if ord(entry.character) < 128 else f"{entry.character} ({entry.identity.unicode_codepoint})"
    print(f"Character: {ch_display}")

    if not entry.known:
        print("Known: False")
        print("Type: Unknown (Outside English Character System)")
        print(f"Unicode: {entry.identity.unicode_codepoint}")
        print(f"Unicode Name: {entry.identity.unicode_name}")
        return

    # Known character attributes
    char_type = entry.classification.type.capitalize()
    print(f"Type: {char_type}")

    if entry.classification.type == "letter":
        if entry.classification.case:
            print(f"Case: {entry.classification.case.capitalize()}")
        if entry.classification.alphabet_position is not None:
            print(f"Alphabet Position: {entry.classification.alphabet_position}")

        # Opposite case equivalent
        if entry.classification.case == "uppercase" and entry.relationships.lowercase:
            print(f"Lowercase: {entry.relationships.lowercase}")
        elif entry.classification.case == "lowercase" and entry.relationships.uppercase:
            print(f"Uppercase: {entry.relationships.uppercase}")

        if entry.linguistic and entry.linguistic.pronunciation:
            print(f"Pronunciation: {entry.linguistic.pronunciation}")
        if entry.examples:
            print(f"Example Words: {', '.join(entry.examples)}")

    print(f"Unicode: {entry.identity.unicode_codepoint}")
    print(f"Unicode Name: {entry.identity.unicode_name}")


def run_demo(knowledge: CharacterKnowledge) -> None:
    """Runs the primary demonstration required by the Master Specification."""
    print("=" * 42)
    print("      VEDA CHARACTER KNOWLEDGE v0.1")
    print("=" * 42)

    demo_chars = ["A", "m", "!", "7", "☃"]
    for ch in demo_chars:
        entry = knowledge.get(ch)
        print_character_card(entry)
    print("-" * 42 + "\n")


def run_interactive(knowledge: CharacterKnowledge) -> None:
    """Interactive loop to inspect character knowledge."""
    print("\n" + "=" * 50)
    print(" VEDA CHARACTER KNOWLEDGE — INTERACTIVE REPL")
    print(" Enter any character to inspect what VEDA knows about it.")
    print(" Type ':quit' or ':exit' to quit.")
    print("=" * 50 + "\n")

    while True:
        try:
            val = input("VEDA-CharKnowledge> ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if val.strip() in (":quit", ":exit"):
            break
        if not val:
            continue

        for ch in val:
            entry = knowledge.get(ch)
            print_character_card(entry)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="VEDA Character Knowledge Demonstration")
    parser.add_argument("--char", "-c", type=str, help="Single character to inspect")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive REPL mode")
    args = parser.parse_args()

    knowledge = CharacterKnowledge()

    if args.interactive:
        run_interactive(knowledge)
    elif args.char:
        for ch in args.char:
            entry = knowledge.get(ch)
            print_character_card(entry)
    else:
        run_demo(knowledge)


if __name__ == "__main__":
    main()
