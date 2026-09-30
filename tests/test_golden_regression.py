"""
VEDA Golden Regression Suite (Phase 3 & 4)

Contains immutable golden test fixtures representing the established VEDA v0.1 contract.
Evaluates:
- CharacterRegistry representability & unsupported character isolation
- Word identity, case normalization, and exact matching
- WordAnalyzer candidate validation and categorization
- Production Lexicon lookup, POS retention, sense structure, and provenance
"""

import unittest
from pathlib import Path
from typing import Dict, List, Optional

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.storage import SqliteLexicon
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word


PROD_DB = Path("data/lexicon/veda_lexicon_v0.1.sqlite")
SAMPLE_DB = Path("data/lexicon/veda_lexicon_sample.sqlite")


class TestGoldenRegression(unittest.TestCase):
    """Immutable golden regression tests for VEDA v0.1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)
        cls.db_path = PROD_DB if PROD_DB.is_file() else SAMPLE_DB
        cls.db = SqliteLexicon(cls.db_path, read_only=True, registry=cls.registry)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "db") and cls.db:
            cls.db.close()

    # --- 1. GOLDEN LEXICAL ENTRIES ---

    def test_golden_free(self) -> None:
        """Golden contract verification for multi-POS word 'free'."""
        entry = self.db.lookup("free")
        self.assertIsNotNone(entry, "'free' must exist in lexicon")
        self.assertEqual(entry.normalized, "free")
        self.assertEqual(entry.word, "free")
        self.assertEqual(entry.language, "en")

        # Multi-POS
        self.assertIn("adj", entry.parts_of_speech)
        self.assertIn("verb", entry.parts_of_speech)
        self.assertIn("noun", entry.parts_of_speech)

        # Definitions by POS
        self.assertIn("adj", entry.definitions_by_pos)
        self.assertIn("verb", entry.definitions_by_pos)
        self.assertGreater(len(entry.definitions_by_pos["adj"]), 0)
        self.assertGreater(len(entry.definitions_by_pos["verb"]), 0)

        # Granular senses
        self.assertGreater(len(entry.senses), 5)
        has_examples = any(len(s.examples) > 0 for s in entry.senses)
        self.assertTrue(has_examples, "'free' senses must preserve examples")

        # Inflections and Pronunciations
        self.assertTrue(any("freer" in f for f in entry.forms))
        self.assertTrue(any("frees" in f for f in entry.forms))
        self.assertGreater(len(entry.pronunciations), 0)

        # Provenance
        self.assertIsNotNone(entry.provenance)
        self.assertEqual(entry.provenance.get("source_dataset"), "Wiktionary (Wiktextract)")

    def test_golden_dictionary(self) -> None:
        """Golden contract verification for 'dictionary'."""
        entry = self.db.lookup("dictionary")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.normalized, "dictionary")
        self.assertIn("noun", entry.parts_of_speech)
        self.assertGreater(len(entry.definitions), 0)

    def test_golden_run(self) -> None:
        """Golden contract verification for 'run'."""
        entry = self.db.lookup("run")
        self.assertIsNotNone(entry)
        self.assertIn("verb", entry.parts_of_speech)
        self.assertIn("noun", entry.parts_of_speech)

    def test_golden_apple(self) -> None:
        """Golden contract verification for 'apple'."""
        entry = self.db.lookup("apple")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.normalized, "apple")
        self.assertIn("noun", entry.parts_of_speech)

    def test_golden_encyclopedia_and_variant(self) -> None:
        """Golden contract verification for 'encyclopedia' and 'encyclopaedia'."""
        if self.db_path == PROD_DB:
            e1 = self.db.lookup("encyclopedia")
            e2 = self.db.lookup("encyclopaedia")
            self.assertIsNotNone(e1)
            self.assertIsNotNone(e2)
            self.assertEqual(e1.normalized, "encyclopedia")
            self.assertEqual(e2.normalized, "encyclopaedia")
            self.assertIn("noun", e1.parts_of_speech)
            self.assertIn("noun", e2.parts_of_speech)

    def test_golden_thesaurus_and_portmanteau(self) -> None:
        """Golden contract verification for 'thesaurus' and 'portmanteau'."""
        t = self.db.lookup("thesaurus")
        p = self.db.lookup("portmanteau")
        self.assertIsNotNone(t)
        self.assertIsNotNone(p)
        self.assertIn("noun", t.parts_of_speech)
        self.assertIn("noun", p.parts_of_speech)

    # --- 2. CASE INVARIANCE & SURFACE MATCHING ---

    def test_golden_case_invariance(self) -> None:
        """apple == Apple == APPLE under normalized lookup; distinct under surface lookup."""
        e_lower = self.db.lookup("apple")
        e_title = self.db.lookup("Apple")
        e_upper = self.db.lookup("APPLE")

        self.assertIsNotNone(e_lower)
        self.assertEqual(e_lower, e_title)
        self.assertEqual(e_title, e_upper)

        # Word objects
        w1 = Word("apple", registry=self.registry)
        w2 = Word("Apple", registry=self.registry)
        w3 = Word("APPLE", registry=self.registry)

        self.assertEqual(w1, w2)
        self.assertEqual(w2, w3)
        self.assertEqual(hash(w1), hash(w2))
        self.assertTrue(w1.exact_match(Word("apple", registry=self.registry)))
        self.assertFalse(w1.exact_match(w2))

    # --- 3. REJECTION & ORTHOGRAPHY CATEGORIES ---

    def test_golden_invalid_and_edge_cases(self) -> None:
        """Exhaustively verifies non-candidates and their rejection reasons."""
        # Empty string
        val_empty = self.analyzer.validate_candidate("")
        self.assertFalse(val_empty.is_valid)
        self.assertEqual(val_empty.reason, "EMPTY")

        # Whitespace
        val_ws = self.analyzer.validate_candidate("   ")
        self.assertFalse(val_ws.is_valid)

        # Multiword expression
        val_mw = self.analyzer.validate_candidate("apple pie")
        self.assertFalse(val_mw.is_valid)
        self.assertEqual(val_mw.reason, "CONTAINS_WHITESPACE")
        self.assertFalse(self.db.has_word("apple pie"))

        # Hyphenated compound
        val_hyphen = self.analyzer.validate_candidate("state-of-the-art")
        self.assertFalse(val_hyphen.is_valid)
        self.assertEqual(val_hyphen.reason, "CONTAINS_PUNCTUATION")
        self.assertFalse(self.db.has_word("state-of-the-art"))

        # Contraction
        val_contr = self.analyzer.validate_candidate("don't")
        self.assertFalse(val_contr.is_valid)
        self.assertEqual(val_contr.reason, "CONTAINS_PUNCTUATION")
        self.assertFalse(self.db.has_word("don't"))

        # Digits & alphanumeric
        val_num = self.analyzer.validate_candidate("123")
        self.assertFalse(val_num.is_valid)
        self.assertEqual(val_num.reason, "CONTAINS_DIGITS")

        val_alnum = self.analyzer.validate_candidate("mp3")
        self.assertFalse(val_alnum.is_valid)
        self.assertEqual(val_alnum.reason, "CONTAINS_DIGITS")

        # Accented characters (unrepresentable in v0.1 registry)
        val_cafe = self.analyzer.validate_candidate("café")
        self.assertFalse(val_cafe.is_valid)
        self.assertEqual(val_cafe.reason, "CONTAINS_NON_ENGLISH_CHARS")
        self.assertFalse(val_cafe.is_representable)
        self.assertEqual(val_cafe.unsupported_characters, ["é"])
        self.assertFalse(self.db.has_word("café"))

        val_naive = self.analyzer.validate_candidate("naïve")
        self.assertFalse(val_naive.is_valid)
        self.assertFalse(val_naive.is_representable)
        self.assertEqual(val_naive.unsupported_characters, ["ï"])

        # Emoji
        val_emoji = self.analyzer.validate_candidate("hello😊")
        self.assertFalse(val_emoji.is_valid)
        self.assertFalse(val_emoji.is_representable)
        self.assertEqual(val_emoji.unsupported_characters, ["😊"])

        # Mixed ASCII / non-ASCII
        val_facade = self.analyzer.validate_candidate("façade")
        self.assertFalse(val_facade.is_valid)
        self.assertFalse(val_facade.is_representable)
        self.assertEqual(val_facade.unsupported_characters, ["ç"])


if __name__ == "__main__":
    unittest.main()
