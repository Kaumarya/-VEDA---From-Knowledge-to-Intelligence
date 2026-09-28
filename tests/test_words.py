"""
Unit Tests for VEDA Word Foundation v0.1 (Phase 2)

Tests:
1. Controlled vocabulary (apple, banana, cat, computer, language, learning, machine, knowledge, intelligence, veda).
2. Edge cases: 'A', 'I', 'x', 'hello', 'world'.
3. Normalization policy (lowercasing, whitespace trimming).
4. Character decomposition and length calculation.
5. Plain English word candidate validation (positive candidates and negative cases: digits, punctuation, whitespace, non-ASCII/emojis).
6. Word to Character ID conversion and reverse reconstruction.
7. Critical roundtrip test: decode_word(encode_word(word)) == normalized_word.
8. Case insensitivity and lexical identity (Apple == apple == APPLE).
9. Schema export and serialization.
"""

import unittest
from pathlib import Path

from foundation.characters.registry import CharacterRegistry
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word


class TestWordFoundationV01(unittest.TestCase):
    """Test suite for VEDA Word Foundation v0.1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(cls.registry)

        cls.sample_vocab = [
            "apple",
            "banana",
            "cat",
            "computer",
            "language",
            "learning",
            "machine",
            "knowledge",
            "intelligence",
            "veda",
        ]

    # --- 1. CONTROLLED VOCABULARY TESTS ---

    def test_sample_vocabulary_creation_and_properties(self) -> None:
        """Verifies creation and core properties for the primary sample vocabulary."""
        for text in self.sample_vocab:
            word = self.analyzer.create_word(text)
            self.assertEqual(word.normalized, text)
            self.assertEqual(word.length, len(text))
            self.assertEqual(word.characters, list(text))
            self.assertTrue(word.is_alphabetic())
            self.assertTrue(self.analyzer.is_word_candidate(text))

    def test_single_letter_and_edge_case_words(self) -> None:
        """Verifies valid single-letter words and edge cases ('A', 'I', 'x', 'hello', 'world')."""
        edge_cases = ["A", "I", "x", "hello", "world"]
        for ec in edge_cases:
            word = self.analyzer.create_word(ec)
            self.assertEqual(word.normalized, ec.lower())
            self.assertEqual(word.original, ec)
            self.assertTrue(self.analyzer.is_word_candidate(ec))

    # --- 2. NORMALIZATION POLICY TESTS ---

    def test_normalization_policy(self) -> None:
        """Verifies whitespace stripping and lowercase normalization."""
        cases = [
            ("apple", "apple"),
            ("Apple", "apple"),
            ("APPLE", "apple"),
            ("  machine  ", "machine"),
            ("\tlearning\n", "learning"),
            ("VeDa", "veda"),
        ]
        for raw, expected in cases:
            norm = self.analyzer.normalize_word(raw)
            self.assertEqual(norm, expected)

            word = self.analyzer.create_word(raw)
            self.assertEqual(word.normalized, expected)
            self.assertEqual(word.original, raw)

    # --- 3. WORD CANDIDATE VALIDATION TESTS ---

    def test_word_candidate_validation_positive(self) -> None:
        """Verifies valid alphabetic English words are accepted."""
        valid_words = [
            "apple",
            "banana",
            "cat",
            "computer",
            "language",
            "learning",
            "machine",
            "knowledge",
            "intelligence",
            "veda",
            "A",
            "I",
            "x",
        ]
        for w in valid_words:
            val = self.analyzer.validate_candidate(w)
            self.assertTrue(val.is_valid, f"Expected {w!r} to be valid, got {val}")
            self.assertEqual(val.reason, "VALID")
            self.assertTrue(self.analyzer.is_word_candidate(w))

    def test_word_candidate_validation_negative(self) -> None:
        """Verifies rejection of digits, punctuation, whitespace, and non-English symbols."""
        # Empty and pure whitespace
        for empty_case in ("", "   ", "\t\n"):
            val = self.analyzer.validate_candidate(empty_case)
            self.assertFalse(val.is_valid)
            self.assertEqual(val.reason, "EMPTY")

        # Containing digits
        for digit_case in ("123", "word2", "4you", "1"):
            val = self.analyzer.validate_candidate(digit_case)
            self.assertFalse(val.is_valid)
            self.assertEqual(val.reason, "CONTAINS_DIGITS")

        # Containing punctuation
        for punct_case in ("hello!", "cat.", "what?", "apple-pie", "don't"):
            val = self.analyzer.validate_candidate(punct_case)
            self.assertFalse(val.is_valid)
            self.assertEqual(val.reason, "CONTAINS_PUNCTUATION")

        # Multi-word whitespace delimited
        val_ws = self.analyzer.validate_candidate("apple banana")
        self.assertFalse(val_ws.is_valid)
        self.assertEqual(val_ws.reason, "CONTAINS_WHITESPACE")

        # Non-ASCII / Emojis
        for non_ascii in ("hello😊", "café", "नमस्ते", "☃"):
            val = self.analyzer.validate_candidate(non_ascii)
            self.assertFalse(val.is_valid)
            self.assertEqual(val.reason, "CONTAINS_NON_ENGLISH_CHARS")

    # --- 4. CHARACTER ID CONVERSION & REVERSE DECODE ---

    def test_character_ids_conversion(self) -> None:
        """Verifies conversion from word to character IDs."""
        word = self.analyzer.create_word("cat")
        char_ids = word.character_ids
        self.assertEqual(len(char_ids), 3)

        # Look up expected IDs from registry
        expected_ids = [
            self.registry.get_character("c").id,
            self.registry.get_character("a").id,
            self.registry.get_character("t").id,
        ]
        self.assertEqual(char_ids, expected_ids)

    def test_critical_roundtrip_conversion(self) -> None:
        """
        CRITICAL TEST:
        decode_word(encode_word(word)) == normalized_word
        """
        all_test_words = self.sample_vocab + ["Apple", "VEDA", "machine", "A", "I"]
        for raw in all_test_words:
            # Step 1: Word to character IDs
            char_ids = self.analyzer.encode_word(raw)
            self.assertIsInstance(char_ids, list)
            self.assertTrue(all(isinstance(i, int) for i in char_ids))

            # Step 2: Character IDs back to Word
            reconstructed_word = self.analyzer.decode_word(char_ids)

            # Step 3: Verification
            expected_normalized = self.analyzer.normalize_word(raw)
            self.assertEqual(
                reconstructed_word.normalized,
                expected_normalized,
                f"Roundtrip failed for {raw!r}: {char_ids} -> {reconstructed_word.normalized!r}",
            )
            self.assertEqual(reconstructed_word, expected_normalized)

    # --- 5. WORD IDENTITY & EQUALITY ---

    def test_word_identity_equality_and_hashing(self) -> None:
        """Verifies that 'Apple', 'apple', and 'APPLE' share the same lexical identity."""
        w_lower = Word("apple")
        w_title = Word("Apple")
        w_upper = Word("APPLE")

        # Lexical equality
        self.assertEqual(w_lower, w_title)
        self.assertEqual(w_title, w_upper)
        self.assertEqual(w_lower, "apple")

        # Hashing / Set deduplication
        vocab_set = {w_lower, w_title, w_upper}
        self.assertEqual(len(vocab_set), 1)

        # Surface form distinction preserved
        self.assertEqual(w_lower.original, "apple")
        self.assertEqual(w_title.original, "Apple")
        self.assertEqual(w_upper.original, "APPLE")
        self.assertFalse(w_lower.exact_match(w_title))

    # --- 6. SCHEMA AND SERIALIZATION ---

    def test_word_schema_serialization(self) -> None:
        """Verifies to_dict() output against the required Word Schema."""
        word = self.analyzer.create_word("apple")
        data = word.to_dict()

        self.assertEqual(data["word"], "apple")
        self.assertEqual(data["normalized"], "apple")
        self.assertEqual(data["language"], "en")
        self.assertEqual(data["characters"], ["a", "p", "p", "l", "e"])
        self.assertEqual(len(data["character_ids"]), 5)
        self.assertEqual(data["length"], 5)
        self.assertIn("lexical", data)
        self.assertIn("definitions", data["lexical"])
        self.assertIn("sources", data)

    def test_type_validation(self) -> None:
        """Verifies type checking on Word and WordAnalyzer."""
        with self.assertRaises(TypeError):
            Word(123)  # type: ignore

        with self.assertRaises(TypeError):
            self.analyzer.normalize_word(None)  # type: ignore

        with self.assertRaises(TypeError):
            self.analyzer.validate_candidate(42)  # type: ignore


if __name__ == "__main__":
    unittest.main()
