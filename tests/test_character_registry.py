"""
Tests for VEDA Character Registry (Phase 1)
"""

import unittest
from pathlib import Path

from foundation.characters.registry import (
    CharacterEntry,
    CharacterRegistry,
    SpecialTokenEntry,
)


class TestCharacterRegistry(unittest.TestCase):
    """Verifies schema, integrity, and behavior of CharacterRegistry."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry_path = Path("veda_characters_v0.1.json").resolve()
        cls.registry = CharacterRegistry.from_json_file(cls.registry_path)

    def test_registry_metadata(self) -> None:
        """Verifies top-level metadata fields."""
        self.assertEqual(self.registry.project, "VEDA")
        self.assertEqual(self.registry.component, "Character Registry")
        self.assertEqual(self.registry.version, "0.1.0")
        self.assertEqual(self.registry.language_scope, "English")
        self.assertIn("English", self.registry.description)

    def test_special_tokens_count_and_content(self) -> None:
        """Verifies that special tokens match expected VEDA specifications."""
        self.assertEqual(self.registry.special_token_count, 4)
        tokens = [st.token for st in self.registry.special_tokens]
        self.assertEqual(tokens, ["<PAD>", "<UNK>", "<BOS>", "<EOS>"])

        # Check purposes
        pad_st = self.registry.get_special_token("<PAD>")
        self.assertIsNotNone(pad_st)
        self.assertEqual(pad_st.id, 0)
        self.assertEqual(pad_st.purpose, "padding")

        unk_st = self.registry.get_special_token("<UNK>")
        self.assertIsNotNone(unk_st)
        self.assertEqual(unk_st.id, 1)

        bos_st = self.registry.get_special_token("<BOS>")
        self.assertIsNotNone(bos_st)
        self.assertEqual(bos_st.id, 2)

        eos_st = self.registry.get_special_token("<EOS>")
        self.assertIsNotNone(eos_st)
        self.assertEqual(eos_st.id, 3)

    def test_character_count(self) -> None:
        """Verifies total registered characters count is exactly 113."""
        self.assertEqual(self.registry.character_count, 113)
        self.assertEqual(len(self.registry), 113)

    def test_character_ids_contiguous(self) -> None:
        """Verifies character IDs are contiguous from 0 to 112."""
        ids = [c.id for c in self.registry.characters]
        self.assertEqual(ids, list(range(113)))

    def test_characters_are_single_unicode_codepoints(self) -> None:
        """Verifies each character entry is a single Unicode character."""
        for entry in self.registry.characters:
            self.assertEqual(len(entry.character), 1)
            # Verify Unicode codepoint format (e.g. U+0020)
            self.assertTrue(entry.unicode_codepoint.startswith("U+"))
            codepoint_int = int(entry.unicode_codepoint[2:], 16)
            self.assertEqual(ord(entry.character), codepoint_int)

    def test_all_characters_unique(self) -> None:
        """Verifies there are no duplicate characters in the registry."""
        chars = [c.character for c in self.registry.characters]
        self.assertEqual(len(chars), len(set(chars)))

    def test_essential_character_classes(self) -> None:
        """Verifies presence of uppercase, lowercase, digits, whitespace, and punctuation."""
        # Whitespace
        self.assertTrue(self.registry.contains_char(" "))
        self.assertTrue(self.registry.contains_char("\n"))
        self.assertTrue(self.registry.contains_char("\t"))

        # Digits
        for d in "0123456789":
            self.assertTrue(self.registry.contains_char(d), f"Digit {d} missing")

        # Uppercase letters
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.assertTrue(self.registry.contains_char(c), f"Uppercase {c} missing")
            entry = self.registry.get_character(c)
            self.assertEqual(entry.case, "uppercase")

        # Lowercase letters
        for c in "abcdefghijklmnopqrstuvwxyz":
            self.assertTrue(self.registry.contains_char(c), f"Lowercase {c} missing")
            entry = self.registry.get_character(c)
            self.assertEqual(entry.case, "lowercase")

        # Core English punctuation
        for p in ".,!?;:'\"-()[]":
            self.assertTrue(self.registry.contains_char(p), f"Punctuation {p} missing")

    def test_lookup_methods(self) -> None:
        """Verifies character and special token lookup methods."""
        entry = self.registry.get_character("A")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.unicode_name, "LATIN CAPITAL LETTER A")
        self.assertEqual(entry.unicode_codepoint, "U+0041")
        self.assertEqual(entry.type, "letter")

        by_id = self.registry.get_character_by_id(entry.id)
        self.assertEqual(by_id, entry)

        self.assertIsNone(self.registry.get_character("🚀"))
        self.assertIsNone(self.registry.get_special_token("<NON_EXISTENT>"))


if __name__ == "__main__":
    unittest.main()
