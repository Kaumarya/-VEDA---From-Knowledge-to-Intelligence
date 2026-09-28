"""
Tests for VEDA Character Tokenizer v0.1 (Phase 1 — English Character Foundation)

Covers all 10 required foundational tests and edge cases:
1. Encode a normal English sentence.
2. Decode the encoded result.
3. Verify: decode(encode(text)) == text
4. Test spaces.
5. Test punctuation.
6. Test newline.
7. Test unknown characters.
8. Test empty strings.
9. Test repeated characters.
10. Test mixed uppercase/lowercase.
"""

import unittest
from pathlib import Path

from tokenizer.char_tokenizer import CharacterTokenizer


class TestCharacterTokenizerV01(unittest.TestCase):
    """Test suite for VEDA CharacterTokenizer v0.1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tokenizer = CharacterTokenizer()

    # --- 10 REQUIRED TESTS SPECIFIED IN MASTER PROMPT ---

    def test_01_encode_normal_sentence(self) -> None:
        """1. Encode a normal English sentence."""
        sentence = "The quick brown fox jumps over the lazy dog."
        token_ids = self.tokenizer.encode(sentence)

        # Must return a list of integers
        self.assertIsInstance(token_ids, list)
        self.assertEqual(len(token_ids), len(sentence))
        self.assertTrue(all(isinstance(t, int) for t in token_ids))
        # Ensure all IDs are within vocabulary bounds
        self.assertTrue(all(0 <= t < self.tokenizer.vocab_size for t in token_ids))

    def test_02_decode_encoded_result(self) -> None:
        """2. Decode the encoded result."""
        sentence = "VEDA is built from first principles."
        token_ids = self.tokenizer.encode(sentence)
        decoded = self.tokenizer.decode(token_ids)

        self.assertIsInstance(decoded, str)
        self.assertEqual(decoded, sentence)

    def test_03_roundtrip_equality(self) -> None:
        """3. Verify: decode(encode(text)) == text."""
        test_sentences = [
            "Hello VEDA!",
            "From Knowledge to Intelligence.",
            "Character tokenization is deterministic and lossless.",
            "All registered English characters round-trip exactly.",
        ]
        for text in test_sentences:
            encoded = self.tokenizer.encode(text)
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(
                decoded,
                text,
                f"Round-trip failed for: {text!r} -> {encoded} -> {decoded!r}",
            )

    def test_04_spaces(self) -> None:
        """4. Test spaces (single, multiple, leading, trailing, internal)."""
        space_cases = [
            " ",
            "   ",
            "  leading spaces",
            "trailing spaces  ",
            "multiple   internal   spaces",
            " \t words with space and tab \t ",
        ]
        for text in space_cases:
            encoded = self.tokenizer.encode(text)
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(decoded, text, f"Space test failed for: {text!r}")

    def test_05_punctuation(self) -> None:
        """5. Test punctuation (ASCII and typography in registry)."""
        punct_cases = [
            ".,!?;:-_()[]{}\"'/\\@#$%^&*+=<>~",
            "Single 'quote' and double \"quote\".",
            "Hyphen-word, en–dash, and em—dash.",
            "Ellipsis is supported… right?",
            "Symbols: $100, £50, €75, ¥1000, 100°, ©2026, VEDA®.",
        ]
        for text in punct_cases:
            encoded = self.tokenizer.encode(text)
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(decoded, text, f"Punctuation test failed for: {text!r}")

    def test_06_newline(self) -> None:
        """6. Test newline (\\n, multiple newlines, multiline paragraphs)."""
        newline_cases = [
            "\n",
            "\n\n\n",
            "Line one\nLine two",
            "First line.\n\nSecond paragraph.\nThird line.\n",
        ]
        for text in newline_cases:
            encoded = self.tokenizer.encode(text)
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(decoded, text, f"Newline test failed for: {text!r}")

    def test_07_unknown_characters(self) -> None:
        """7. Test unknown characters (characters outside registry map to <UNK>)."""
        # Emojis and characters outside registry
        text_with_unknown = "Hello 🤖 World 🚀"
        encoded = self.tokenizer.encode(text_with_unknown)

        # Verify <UNK> id is present at the positions of the emojis
        unk_id = self.tokenizer.unk_token_id
        self.assertIn(unk_id, encoded)
        self.assertEqual(encoded.count(unk_id), 2)

        # Decoding by default replaces unknown IDs with "<UNK>"
        decoded = self.tokenizer.decode(encoded)
        self.assertEqual(decoded, "Hello <UNK> World <UNK>")

        # Decoding with skip_special_tokens=True omits <UNK>
        decoded_skip = self.tokenizer.decode(encoded, skip_special_tokens=True)
        self.assertEqual(decoded_skip, "Hello  World ")

    def test_08_empty_strings(self) -> None:
        """8. Test empty strings."""
        empty_text = ""
        encoded = self.tokenizer.encode(empty_text)
        self.assertEqual(encoded, [])

        decoded = self.tokenizer.decode([])
        self.assertEqual(decoded, "")

        # Roundtrip
        self.assertEqual(self.tokenizer.decode(self.tokenizer.encode("")), "")

    def test_09_repeated_characters(self) -> None:
        """9. Test repeated characters."""
        single_repeat_cases = [
            "aaaaaaa",
            "ZZZZZZZZZZ",
            "..........",
            "!!!!!!!!!!",
            "   ",
            "\n\n\n\n",
            "1111111111",
        ]
        for text in single_repeat_cases:
            encoded = self.tokenizer.encode(text)
            self.assertEqual(len(encoded), len(text))
            self.assertEqual(len(set(encoded)), 1)
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(decoded, text)

        # Multi-run repeated characters
        multi_run_cases = [
            "!!!!!?????",
            "aaabbbccc",
            "   \t\t\t   ",
        ]
        for text in multi_run_cases:
            encoded = self.tokenizer.encode(text)
            self.assertEqual(len(encoded), len(text))
            decoded = self.tokenizer.decode(encoded)
            self.assertEqual(decoded, text)

    def test_10_mixed_case(self) -> None:
        """10. Test mixed uppercase/lowercase."""
        mixed_text = "VeDa: FrOm KnOwLeDgE tO iNtElLiGeNcE"
        encoded = self.tokenizer.encode(mixed_text)
        decoded = self.tokenizer.decode(encoded)
        self.assertEqual(decoded, mixed_text)

        # Verify that uppercase and lowercase produce distinct IDs
        upper_ids = self.tokenizer.encode("VEDA")
        lower_ids = self.tokenizer.encode("veda")
        self.assertNotEqual(upper_ids, lower_ids)
        for u_id, l_id in zip(upper_ids, lower_ids):
            self.assertNotEqual(u_id, l_id)

    # --- ADDITIONAL ARCHITECTURAL & EDGE CASE TESTS ---

    def test_vocabulary_size_and_contiguity(self) -> None:
        """Verifies vocabulary size is 117 (4 special tokens + 113 characters) and contiguous."""
        self.assertEqual(self.tokenizer.vocab_size, 117)
        vocab = self.tokenizer.get_vocab()
        self.assertEqual(len(vocab), 117)
        ids = sorted(vocab.values())
        self.assertEqual(ids, list(range(117)))

    def test_special_tokens_properties(self) -> None:
        """Verifies canonical IDs and tokens for special tokens."""
        self.assertEqual(self.tokenizer.pad_token, "<PAD>")
        self.assertEqual(self.tokenizer.pad_token_id, 0)
        self.assertEqual(self.tokenizer.unk_token, "<UNK>")
        self.assertEqual(self.tokenizer.unk_token_id, 1)
        self.assertEqual(self.tokenizer.bos_token, "<BOS>")
        self.assertEqual(self.tokenizer.bos_token_id, 2)
        self.assertEqual(self.tokenizer.eos_token, "<EOS>")
        self.assertEqual(self.tokenizer.eos_token_id, 3)

    def test_add_special_tokens_flag(self) -> None:
        """Verifies BOS and EOS boundary token insertion during encode."""
        text = "Hello"
        encoded_raw = self.tokenizer.encode(text, add_special_tokens=False)
        encoded_seq = self.tokenizer.encode(text, add_special_tokens=True)

        self.assertEqual(encoded_seq[0], self.tokenizer.bos_token_id)
        self.assertEqual(encoded_seq[-1], self.tokenizer.eos_token_id)
        self.assertEqual(encoded_seq[1:-1], encoded_raw)

        # Decoding with skip_special_tokens=True recovers the original text
        decoded_clean = self.tokenizer.decode(encoded_seq, skip_special_tokens=True)
        self.assertEqual(decoded_clean, text)

        # Decoding without skip_special_tokens includes <BOS> and <EOS>
        decoded_full = self.tokenizer.decode(encoded_seq, skip_special_tokens=False)
        self.assertEqual(decoded_full, f"<BOS>{text}<EOS>")

    def test_invalid_token_id_error_handling(self) -> None:
        """Verifies decode error handling modes ('strict', 'replace', 'ignore')."""
        invalid_id = 999  # Out of range (0..116)

        # Strict mode raises ValueError
        with self.assertRaises(ValueError):
            self.tokenizer.decode([invalid_id], errors="strict")

        # Replace mode inserts <UNK>
        self.assertEqual(self.tokenizer.decode([invalid_id], errors="replace"), "<UNK>")

        # Ignore mode drops invalid ID
        self.assertEqual(self.tokenizer.decode([invalid_id], errors="ignore"), "")

    def test_type_validation(self) -> None:
        """Verifies that non-string and non-sequence inputs raise TypeError."""
        with self.assertRaises(TypeError):
            self.tokenizer.encode(12345)  # type: ignore

        with self.assertRaises(TypeError):
            self.tokenizer.decode([1, "invalid_id", 3])  # type: ignore

    def test_tokenize_method(self) -> None:
        """Verifies that tokenize() produces character token strings."""
        tokens = self.tokenizer.tokenize("Hi 🤖")
        self.assertEqual(tokens, ["H", "i", " ", "<UNK>"])


if __name__ == "__main__":
    unittest.main()
