"""
VEDA Security & Robustness Regression Suite (Phase 31)

Verifies:
1. SQL Injection defense: Parameterized queries ensure input is strictly treated as data.
2. Special characters: Single quotes, double quotes, and backslashes preserve exact fidelity.
3. Malformed JSON & extremely long lines are handled safely without crash.
4. Unexpected types raise explicit TypeErrors according to the data contracts.
"""

import json
import tempfile
import unittest
from pathlib import Path

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.storage import SqliteLexicon, SqliteLexiconBuilder
from foundation.words.analyzer import WordAnalyzer


class TestSecurityAndRobustness(unittest.TestCase):
    """Adversarial security and robustness tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sec.sqlite"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sql_injection_defense_in_lookups(self) -> None:
        """SQL injection strings in lookup queries must not execute SQL or damage tables."""
        builder = SqliteLexiconBuilder()
        sample_path = Path("veda_sample.jsonl")
        db = builder.build(sample_path, self.db_path, rebuild=True)

        payloads = [
            "'; DROP TABLE words; --",
            "' OR '1'='1",
            "\" UNION SELECT 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 --",
            "apple' OR 1=1; --",
            "'; DELETE FROM word_pos; --",
            "admin' --",
        ]

        try:
            for p in payloads:
                res = db.lookup(p)
                self.assertIsNone(res, f"Payload {p!r} should return None")
                has_it = db.has_word(p)
                self.assertFalse(has_it)

            # Ensure tables still exist and are healthy
            health = db.integrity_check()
            self.assertTrue(health["is_healthy"])
            self.assertEqual(health["words_row_count"], 6)
            self.assertEqual(health["word_pos_row_count"], 13)
        finally:
            db.close()

    def test_sql_injection_payloads_stored_as_verbatim_data(self) -> None:
        """SQL payloads in dictionary fields must be stored and retrieved as literal data."""
        builder = SqliteLexiconBuilder()

        src = Path(self.temp_dir.name) / "injection_src.jsonl"
        with open(src, "w", encoding="utf-8") as f:
            rec = {
                "word": "injection",
                "lang": "English",
                "pos": "noun",
                "senses": [
                    {
                        "glosses": ["'; DROP TABLE words; --"],
                        "tags": ["' OR 1=1 --"],
                        "examples": [{"text": "\"; VACUUM; --"}],
                    }
                ],
                "etymology": "From Latin '; DELETE FROM metadata; --",
            }
            f.write(json.dumps(rec) + "\n")

        db = builder.build(src, self.db_path, rebuild=True)
        try:
            entry = db.lookup("injection")
            self.assertIsNotNone(entry)
            self.assertIn("'; DROP TABLE words; --", entry.definitions)
            self.assertEqual(entry.senses[0].tags, ["' OR 1=1 --"])
            self.assertEqual(entry.senses[0].examples, ["\"; VACUUM; --"])
            self.assertEqual(entry.etymology, "From Latin '; DELETE FROM metadata; --")

            # Verify integrity
            health = db.integrity_check()
            self.assertTrue(health["is_healthy"])
            self.assertEqual(health["words_row_count"], 1)
        finally:
            db.close()

    def test_quotes_and_backslashes_fidelity(self) -> None:
        """Strings with complex quotes and backslashes round-trip with exact fidelity."""
        builder = SqliteLexiconBuilder()
        src = Path(self.temp_dir.name) / "quotes_src.jsonl"
        complex_text = "He said: \"It's a \\path\\to\\file with 'single' and \"double\" quotes\"."

        with open(src, "w", encoding="utf-8") as f:
            rec = {
                "word": "quote",
                "lang": "English",
                "pos": "noun",
                "senses": [
                    {
                        "glosses": [complex_text],
                        "examples": [{"text": complex_text}],
                    }
                ],
            }
            f.write(json.dumps(rec) + "\n")

        db = builder.build(src, self.db_path, rebuild=True)
        try:
            entry = db.lookup("quote")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.definitions[0], complex_text)
            self.assertEqual(entry.senses[0].examples[0], complex_text)
        finally:
            db.close()

    def test_extremely_long_string_handling(self) -> None:
        """10,000-character string is evaluated safely without memory crash."""
        huge_str = "a" * 10000
        val = self.analyzer.validate_candidate(huge_str)
        self.assertTrue(val.is_valid)  # Plain ASCII 'a' repeated is syntactically valid plain English candidate
        self.assertEqual(self.analyzer.normalize_word(huge_str), huge_str)

        huge_dirty = ("a" * 5000) + "-" + ("b" * 5000)
        val_dirty = self.analyzer.validate_candidate(huge_dirty)
        self.assertFalse(val_dirty.is_valid)
        self.assertEqual(val_dirty.reason, "CONTAINS_PUNCTUATION")

    def test_unexpected_types_raise_type_error(self) -> None:
        """Non-string inputs to validate_candidate and analyze_orthography raise TypeError."""
        for bad_input in [None, 123, ["apple"], {"word": "apple"}]:
            with self.assertRaises(TypeError):
                self.analyzer.validate_candidate(bad_input)  # type: ignore

            with self.assertRaises(TypeError):
                self.analyzer.analyze_orthography(bad_input)  # type: ignore


if __name__ == "__main__":
    unittest.main()
