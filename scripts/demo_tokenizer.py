"""
VEDA Character Tokenizer v0.1 — Interactive & Batch Testing Tool

Usage:
    # 1. Run demonstration with pre-configured diverse inputs:
    python scripts/demo_tokenizer.py

    # 2. Test a specific input from command line:
    python scripts/demo_tokenizer.py --text "Hello VEDA! 2026"

    # 3. Interactive REPL mode:
    python scripts/demo_tokenizer.py --interactive
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path so imports work from any cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tokenizer.char_tokenizer import CharacterTokenizer


# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


def format_char(ch: str) -> str:
    """Returns a readable representation of whitespace and special characters."""
    if ch == " ":
        return "' ' (SPACE)"
    elif ch == "\t":
        return r"'\t' (TAB)"
    elif ch == "\n":
        return r"'\n' (NEWLINE)"
    else:
        # Use repr to be safely displayable in any terminal encoding
        return repr(ch)


def inspect_input(tokenizer: CharacterTokenizer, text: str, show_breakdown: bool = True) -> None:
    """Encodes, decodes, and displays full diagnostic information for an input string."""
    print("=" * 70)
    print(f"INPUT TEXT (len={len(text)} chars):")
    print(f"  {repr(text)}")
    print("-" * 70)

    # Encode without special tokens
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    print(f"TOKEN IDs ({len(token_ids)} tokens):")
    print(f"  {token_ids}")

    # Encode with special tokens (<BOS> and <EOS>)
    seq_ids = tokenizer.encode(text, add_special_tokens=True)
    print(f"WITH BOUNDARY TOKENS (<BOS>...<EOS>):")
    print(f"  {seq_ids}")

    # Decode
    decoded = tokenizer.decode(token_ids)
    is_roundtrip_exact = (decoded == text)
    print("-" * 70)
    print(f"DECODED TEXT:")
    print(f"  {repr(decoded)}")
    status_label = "[OK] EXACT MATCH" if is_roundtrip_exact else "[DIFF] REPLACED WITH <UNK>"
    print(f"ROUNDTRIP MATCH: {status_label}")

    # Character breakdown table
    if show_breakdown and text:
        print("-" * 70)
        print(f"{'Pos':<5} {'Char':<16} {'Codepoint':<12} {'Token ID':<10} {'Status':<10}")
        print("-" * 70)
        for idx, ch in enumerate(text):
            tid = tokenizer.token_to_id(ch)
            if tid is not None:
                cp = f"U+{ord(ch):04X}"
                status = "KNOWN"
            else:
                tid = tokenizer.unk_token_id
                cp = f"U+{ord(ch):04X}"
                status = "<UNK>"
            print(f"{idx:<5} {format_char(ch):<16} {cp:<12} {tid:<10} {status:<10}")
    print("=" * 70 + "\n")


def run_demo_suite(tokenizer: CharacterTokenizer) -> None:
    """Runs a diverse suite of representative test inputs."""
    samples = [
        ("Standard English Sentence", "The quick brown fox jumps over the lazy dog."),
        ("VEDA Mission Statement", "VEDA: From Knowledge to Intelligence."),
        ("Whitespace & Punctuation", "Hello, World!\tHow are you today?\nFine, thank you!"),
        ("Extended Typography & Currencies", "“VEDA” — $100, £80, €90, ¥1000… 100% genuine!"),
        ("Case Sensitivity Distinction", "abc ABC aBc AbC"),
        ("Repeated Characters", "Sooooo coooool!!!!!!! 11111"),
        ("Out-of-Vocabulary Characters (Emojis & Non-English)", "Hello 🤖! Welcome to VEDA 🚀 (नमस्ते)"),
        ("Empty String Edge Case", ""),
    ]

    print("\n" + "#" * 70)
    print("# VEDA CHARACTER TOKENIZER v0.1 — TEST RUNNER")
    print(f"# Active Vocabulary Size: {tokenizer.vocab_size} tokens")
    print(f"# Special Tokens: {tokenizer.special_tokens}")
    print("#" * 70 + "\n")

    for title, text in samples:
        print(f">>> TEST CASE: {title}")
        inspect_input(tokenizer, text, show_breakdown=(len(text) <= 50))


def run_interactive_repl(tokenizer: CharacterTokenizer) -> None:
    """Interactive command-line loop for testing arbitrary user inputs."""
    print("\n" + "=" * 70)
    print(" VEDA CHARACTER TOKENIZER v0.1 — INTERACTIVE REPL")
    print(" Type any text and press Enter to inspect its tokenization.")
    print(" Type ':quit' or ':exit' or press Ctrl+C to stop.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("VEDA-Tokenize> ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive mode.")
            break

        if user_input.strip() in (":quit", ":exit"):
            print("Goodbye.")
            break

        # Allow escaped characters like \n and \t if typed explicitly
        processed_input = user_input.encode("utf-8").decode("unicode_escape")
        inspect_input(tokenizer, processed_input, show_breakdown=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test VEDA Character Tokenizer v0.1")
    parser.add_argument("--text", type=str, help="Single string to tokenize and inspect")
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive REPL mode")
    args = parser.parse_args()

    tokenizer = CharacterTokenizer()

    if args.interactive:
        run_interactive_repl(tokenizer)
    elif args.text is not None:
        inspect_input(tokenizer, args.text, show_breakdown=True)
    else:
        run_demo_suite(tokenizer)


if __name__ == "__main__":
    main()
