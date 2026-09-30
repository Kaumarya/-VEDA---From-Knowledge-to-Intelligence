"""
VEDA Production Lexicon Verification & Edge Case Audit (Phase 3)

Validates:
1. SQLite PRAGMA integrity check and foreign-key referential integrity
2. Single-POS entries (e.g. 'thesaurus', 'apple')
3. Multi-POS entries (e.g. 'free', 'run', 'set')
4. Multi-sense entries with granular glosses, tags, and usage examples
5. Case-insensitivity via normalization (apple == Apple == APPLE)
6. Exact surface form filtering
7. Missing word handling
8. Rejection policy enforcement (multiword, hyphenated, diacritics, numbers not present)
9. Lexical attributes: IPA pronunciations, inflected forms, synonyms, antonyms, etymology
10. Morphological & Character integration (Word object reconstruction & CharacterRegistry IDs)
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

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
from foundation.lexicon.storage import SqliteLexicon
from foundation.words.word import Word


DEFAULT_DB = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_v0.1.sqlite"


def run_verification(db_path: Path) -> Dict[str, Any]:
    print("=" * 70)
    print(f" VEDA PRODUCTION LEXICON VERIFICATION: {db_path.name}")
    print("=" * 70)

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
    results = {"passed": 0, "failed": 0, "checks": []}

    def check(name: str, condition: bool, details: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        if condition:
            results["passed"] += 1
        else:
            results["failed"] += 1
        print(f"[{status}] {name} {('- ' + details) if details else ''}")
        results["checks"].append({"name": name, "status": status, "details": details})

    with SqliteLexicon(db_path, read_only=True, registry=registry) as db:
        meta = db.get_metadata()
        health = db.integrity_check()
        latest_stats = db.get_latest_ingestion_stats()

        print("\n--- 1. DATABASE INTEGRITY & SCHEMA ---")
        check(
            "PRAGMA integrity_check",
            health["sqlite_integrity_check"] == ["ok"],
            f"Result: {health['sqlite_integrity_check']}",
        )
        check(
            "Foreign Key Integrity",
            len(health["foreign_key_violations"]) == 0,
            f"Violations: {len(health['foreign_key_violations'])}",
        )
        check(
            "Words Table Non-Empty",
            health["words_row_count"] > 1000,
            f"Total unique words: {health['words_row_count']:,}",
        )
        check(
            "Relational POS Index Consistency",
            health["distinct_normalized_words_in_pos"] == health["words_row_count"],
            f"Distinct words in POS index: {health['distinct_normalized_words_in_pos']:,}",
        )
        check(
            "Granular Senses Present",
            health["senses_row_count"] >= health["words_row_count"],
            f"Total sense rows: {health['senses_row_count']:,}",
        )

        print("\n--- 2. SINGLE-POS & COMMON NOUNS ---")
        apple = db.lookup("apple")
        check("Lookup 'apple'", apple is not None)
        if apple:
            check("'apple' primary POS is noun", apple.primary_pos == "noun", f"POS: {apple.parts_of_speech}")
            check("'apple' has definitions", len(apple.definitions) > 0, f"Count: {len(apple.definitions)}")

        thesaurus = db.lookup("thesaurus")
        check("Lookup 'thesaurus'", thesaurus is not None)
        if thesaurus:
            check("'thesaurus' has POS 'noun'", "noun" in thesaurus.parts_of_speech)

        print("\n--- 3. MULTI-POS AGGREGATION ---")
        free = db.lookup("free")
        check("Lookup 'free'", free is not None)
        if free:
            check(
                "'free' multi-POS preserved",
                len(free.parts_of_speech) >= 3,
                f"Parts of speech: {free.parts_of_speech}",
            )
            check("'free' has adj definitions", len(free.definitions_by_pos.get("adj", [])) > 0)
            check("'free' has verb definitions", len(free.definitions_by_pos.get("verb", [])) > 0)

        run_entry = db.lookup("run")
        check("Lookup 'run'", run_entry is not None)
        if run_entry:
            check(
                "'run' has both noun and verb",
                "noun" in run_entry.parts_of_speech and "verb" in run_entry.parts_of_speech,
                f"POS: {run_entry.parts_of_speech}",
            )

        print("\n--- 4. MULTI-SENSE & USAGE EXAMPLES ---")
        if free:
            check("'free' multiple senses", len(free.senses) > 5, f"Sense count: {len(free.senses)}")
            has_examples = any(len(s.examples) > 0 for s in free.senses)
            check("'free' retains examples", has_examples)
            has_tags = any(len(s.tags) > 0 for s in free.senses)
            check("'free' retains grammatical tags", has_tags)

        print("\n--- 5. NORMALIZATION & CASE VARIATIONS ---")
        check("Normalized query 'APPLE'", db.lookup("APPLE") is not None)
        check("Normalized query 'Apple'", db.lookup("Apple") is not None)
        check("Normalized query 'aPple'", db.lookup("aPple") is not None)
        check(
            "Equivalence across cases",
            db.lookup("apple") == db.lookup("APPLE") == db.lookup("Apple"),
        )
        check(
            "Exact surface match distinction",
            db.lookup("apple", exact_surface=True) is not None
            and (db.lookup("APPLE", exact_surface=True) is None or db.lookup("APPLE", exact_surface=True).word == "APPLE"),
        )

        print("\n--- 6. POS FILTERING ---")
        check("Filter 'free' pos='verb'", db.lookup("free", pos="verb") is not None)
        check("Filter 'free' pos='adj'", db.lookup("free", pos="adj") is not None)
        check("Filter 'free' invalid POS", db.lookup("free", pos="conjunction") is None)

        print("\n--- 7. REJECTION POLICY ENFORCEMENT ---")
        check("Exclude multiword 'apple pie'", not db.has_word("apple pie"))
        check("Exclude hyphenated 'apple-pie'", not db.has_word("apple-pie"))
        check("Exclude contraction 'don't'", not db.has_word("don't"))
        check("Exclude accented 'café'", not db.has_word("café"))
        check("Exclude numeric '123'", not db.has_word("123"))
        check("Exclude symbol 'hello😊'", not db.has_word("hello😊"))

        print("\n--- 8. LEXICAL ATTRIBUTES & RICHNESS ---")
        words_with_ipa = [w for w in ["apple", "free", "run", "water", "time"] if db.lookup(w) and db.lookup(w).pronunciations]
        check("IPA transcriptions preserved", len(words_with_ipa) > 0, f"Found IPA for: {words_with_ipa}")

        words_with_forms = [w for w in ["apple", "free", "run", "take", "give"] if db.lookup(w) and db.lookup(w).forms]
        check("Inflected forms preserved", len(words_with_forms) > 0, f"Found forms for: {words_with_forms}")

        words_with_relations = [w for w in ["free", "good", "fast", "big"] if db.lookup(w) and (db.lookup(w).synonyms or db.lookup(w).antonyms)]
        check("Synonyms/Antonyms preserved", len(words_with_relations) > 0, f"Found relations for: {words_with_relations}")

        words_with_etymology = [w for w in ["free", "apple", "mother", "water"] if db.lookup(w) and db.lookup(w).etymology]
        check("Etymology preserved", len(words_with_etymology) > 0, f"Found etymology for: {words_with_etymology}")

        print("\n--- 9. CHARACTER & WORD INTEGRATION ---")
        free_word = db.to_word("free")
        check("Reconstruct Word instance", isinstance(free_word, Word))
        if free_word:
            check("Word length matches", free_word.length == 4)
            check("Word characters match", free_word.characters == ["f", "r", "e", "e"])
            check("Character IDs contiguous & valid", free_word.character_ids == [72, 84, 71, 71])
            check("Word lexical attached", free_word.lexical is not None)

        print("\n--- 10. PROVENANCE & METADATA ---")
        check("Metadata schema_version", meta.schema_version == "0.1.0")
        check("Metadata extractor_version", meta.extractor_version == "0.1.0")
        check("Metadata language_scope", meta.language_scope == "English")
        check("Metadata source_dataset", "wiktextract" in str(meta.source_dataset).lower() or "wiktionary" in str(meta.source_dataset).lower())
        check("Ingestion audit stats present", latest_stats is not None)

    print("\n" + "=" * 70)
    print(f"VERIFICATION SUMMARY: {results['passed']} PASSED, {results['failed']} FAILED")
    print("=" * 70)
    return results


if __name__ == "__main__":
    db_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    res = run_verification(db_file)
    if res["failed"] > 0:
        sys.exit(1)
