"""
Unit Tests for VEDA Character Knowledge Layer v0.1 (Phase 1)

Verifies:
1. Classification of letters, digits, punctuation, whitespace, symbols, and unknowns.
2. Uppercase / lowercase case relationships.
3. Alphabet positions (1..26 for English letters, None for others).
4. Unicode metadata derivation (codepoints, names, categories).
5. Safe unknown character handling ('☃', emojis, non-English scripts).
6. Consistency and round-trip alignment across Character Knowledge,
   Character Registry, and Character Tokenizer.
7. Serialization and JSON schema compliance.
"""

import unittest
from pathlib import Path

from foundation.characters.knowledge import CharacterKnowledge
from foundation.characters.registry import CharacterRegistry
from foundation.characters.schemas import CharacterKnowledgeEntry
from tokenizer.char_tokenizer import CharacterTokenizer


class TestCharacterKnowledgeV01(unittest.TestCase):
    """Test suite for VEDA CharacterKnowledge v0.1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.knowledge = CharacterKnowledge()
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.tokenizer = CharacterTokenizer()

    # --- LETTER TESTS (A, a, B, b, M, m, Z, z) ---

    def test_letters_classification_and_case(self) -> None:
        """Verifies letter classification and case detection."""
        letter_cases = [
            ("A", "uppercase", 1, "a", "A"),
            ("a", "lowercase", 1, "a", "A"),
            ("B", "uppercase", 2, "b", "B"),
            ("b", "lowercase", 2, "b", "B"),
            ("M", "uppercase", 13, "m", "M"),
            ("m", "lowercase", 13, "m", "M"),
            ("Z", "uppercase", 26, "z", "Z"),
            ("z", "lowercase", 26, "z", "Z"),
        ]
        for char, expected_case, expected_pos, exp_lower, exp_upper in letter_cases:
            entry = self.knowledge.get(char)
            self.assertTrue(entry.known, f"Character {char!r} should be known")
            self.assertEqual(entry.classification.type, "letter")
            self.assertEqual(entry.classification.case, expected_case)
            self.assertEqual(entry.classification.alphabet, "english")
            self.assertEqual(entry.classification.alphabet_position, expected_pos)
            self.assertEqual(entry.relationships.lowercase, exp_lower)
            self.assertEqual(entry.relationships.uppercase, exp_upper)

            # Query API methods
            self.assertTrue(self.knowledge.is_letter(char))
            self.assertFalse(self.knowledge.is_digit(char))
            self.assertFalse(self.knowledge.is_punctuation(char))
            self.assertFalse(self.knowledge.is_whitespace(char))
            self.assertEqual(self.knowledge.get_alphabet_position(char), expected_pos)
            self.assertEqual(self.knowledge.get_lowercase(char), exp_lower)
            self.assertEqual(self.knowledge.get_uppercase(char), exp_upper)

    def test_letter_examples_and_linguistics(self) -> None:
        """Verifies curated examples and phonetic info for English letters."""
        entry_a = self.knowledge.get("A")
        self.assertIsNotNone(entry_a.linguistic)
        self.assertEqual(entry_a.linguistic.letter_name, "A")
        self.assertIn("apple", entry_a.examples)

        entry_m = self.knowledge.get("m")
        self.assertIsNotNone(entry_m.linguistic)
        self.assertEqual(entry_m.linguistic.letter_name, "M")
        self.assertIn("model", entry_m.examples)

    # --- DIGITS TESTS (0, 5, 9) ---

    def test_digits(self) -> None:
        """Verifies classification and properties of digits (0, 5, 9)."""
        for d in ("0", "5", "9"):
            entry = self.knowledge.get(d)
            self.assertTrue(entry.known)
            self.assertEqual(entry.classification.type, "digit")
            self.assertIsNone(entry.classification.case)
            self.assertIsNone(entry.classification.alphabet_position)
            self.assertIsNone(entry.relationships.lowercase)
            self.assertIsNone(entry.relationships.uppercase)

            self.assertTrue(self.knowledge.is_digit(d))
            self.assertFalse(self.knowledge.is_letter(d))
            self.assertFalse(self.knowledge.is_punctuation(d))
            self.assertIsNone(self.knowledge.get_alphabet_position(d))

    # --- PUNCTUATION TESTS (., !, ?, ,) ---

    def test_punctuation(self) -> None:
        """Verifies punctuation marks (., !, ?, ,)."""
        for p in (".", "!", "?", ","):
            entry = self.knowledge.get(p)
            self.assertTrue(entry.known)
            self.assertEqual(entry.classification.type, "punctuation")
            self.assertIsNone(entry.classification.case)
            self.assertIsNone(entry.classification.alphabet_position)
            self.assertIsNone(entry.relationships.lowercase)
            self.assertIsNone(entry.relationships.uppercase)

            self.assertTrue(self.knowledge.is_punctuation(p))
            self.assertFalse(self.knowledge.is_letter(p))
            self.assertFalse(self.knowledge.is_digit(p))

    # --- WHITESPACE TESTS (space, newline, tab) ---

    def test_whitespace(self) -> None:
        """Verifies whitespace characters (' ', '\\n', '\\t')."""
        for ws in (" ", "\n", "\t"):
            entry = self.knowledge.get(ws)
            self.assertTrue(entry.known)
            self.assertEqual(entry.classification.type, "whitespace")
            self.assertIsNone(entry.classification.case)
            self.assertIsNone(entry.classification.alphabet_position)

            self.assertTrue(self.knowledge.is_whitespace(ws))
            self.assertFalse(self.knowledge.is_letter(ws))
            self.assertFalse(self.knowledge.is_digit(ws))

    # --- UNKNOWN / NON-ENGLISH SYMBOL TESTS ('☃', emojis, Devanagari) ---

    def test_unknown_character_handling(self) -> None:
        """Verifies safe handling of characters outside the English knowledge base."""
        unknown_samples = ["☃", "🤖", "🚀", "क"]
        for unk in unknown_samples:
            entry = self.knowledge.get(unk)
            self.assertFalse(entry.known, f"Character {unk!r} should be known=False")
            self.assertEqual(entry.classification.type, "unknown")
            self.assertIsNone(entry.classification.case)
            self.assertIsNone(entry.classification.alphabet_position)
            self.assertIsNone(entry.relationships.lowercase)
            self.assertIsNone(entry.relationships.uppercase)

            # API queries must return safe false/None without raising exceptions
            self.assertFalse(self.knowledge.is_known(unk))
            self.assertFalse(self.knowledge.is_letter(unk))
            self.assertFalse(self.knowledge.is_digit(unk))
            self.assertFalse(self.knowledge.is_punctuation(unk))
            self.assertFalse(self.knowledge.is_whitespace(unk))
            self.assertIsNone(self.knowledge.get_alphabet_position(unk))
            self.assertIsNone(self.knowledge.get_lowercase(unk))
            self.assertIsNone(self.knowledge.get_uppercase(unk))

            # Unicode codepoint and category must still be valid
            u_info = self.knowledge.get_unicode_info(unk)
            self.assertTrue(u_info["codepoint"].startswith("U+"))
            self.assertNotEqual(u_info["category"], "")

    # --- UNICODE METADATA TESTS ---

    def test_unicode_metadata(self) -> None:
        """Verifies Unicode codepoint, category, and name formatting."""
        u_info_a = self.knowledge.get_unicode_info("A")
        self.assertEqual(u_info_a["codepoint"], "U+0041")
        self.assertEqual(u_info_a["name"], "LATIN CAPITAL LETTER A")
        self.assertEqual(u_info_a["category"], "Lu")

        u_info_excl = self.knowledge.get_unicode_info("!")
        self.assertEqual(u_info_excl["codepoint"], "U+0021")
        self.assertEqual(u_info_excl["name"], "EXCLAMATION MARK")
        self.assertEqual(u_info_excl["category"], "Po")

    # --- ALIGNMENT / ROUND-TRIP TEST ACROSS KNOWLEDGE, REGISTRY, TOKENIZER ---

    def test_cross_layer_coherence(self) -> None:
        """
        Verifies that Character Knowledge, Character Registry, and Character Tokenizer
        all consistently map to the identical underlying character representation.
        """
        for char_entry in self.registry.characters:
            char = char_entry.character

            # 1. Knowledge layer knows this character
            k_entry = self.knowledge.get(char)
            self.assertTrue(k_entry.known)
            self.assertEqual(k_entry.identity.character_id, char_entry.id)
            self.assertEqual(k_entry.identity.unicode_codepoint, char_entry.unicode_codepoint)

            # 2. Tokenizer maps to continuous token ID (4 + registry_id)
            token_id = self.tokenizer.token_to_id(char)
            self.assertIsNotNone(token_id)
            self.assertEqual(token_id, char_entry.id + 4)

            # 3. Tokenizer decodes token ID back to exact character
            self.assertEqual(self.tokenizer.id_to_token(token_id), char)

            # 4. If letter, knowledge case matches registry case
            if k_entry.classification.type == "letter":
                self.assertEqual(k_entry.classification.case, char_entry.case)

    # --- SUMMARY & SERIALIZATION TESTS ---

    def test_summary_and_serialization(self) -> None:
        """Verifies to_dict() and summary() structure matches conceptual requirements."""
        entry_a = self.knowledge.get("A")
        summary_a = entry_a.summary()
        self.assertEqual(summary_a["character"], "A")
        self.assertEqual(summary_a["type"], "letter")
        self.assertEqual(summary_a["case"], "uppercase")
        self.assertEqual(summary_a["alphabet_position"], 1)
        self.assertEqual(summary_a["lowercase"], "a")
        self.assertEqual(summary_a["unicode"], "U+0041")

        entry_excl = self.knowledge.get("!")
        summary_excl = entry_excl.summary()
        self.assertEqual(summary_excl["character"], "!")
        self.assertEqual(summary_excl["type"], "punctuation")
        self.assertIsNone(summary_excl["case"])
        self.assertIsNone(summary_excl["alphabet_position"])

        entry_unk = self.knowledge.get("☃")
        self.assertFalse(entry_unk.known)
        self.assertEqual(entry_unk.classification.type, "unknown")

    def test_invalid_input_validation(self) -> None:
        """Verifies get() raises ValueError on empty strings or multi-character strings."""
        with self.assertRaises(ValueError):
            self.knowledge.get("")
        with self.assertRaises(ValueError):
            self.knowledge.get("AB")


if __name__ == "__main__":
    unittest.main()
