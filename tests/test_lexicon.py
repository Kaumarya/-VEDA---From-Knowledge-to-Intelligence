"""
Unit Tests for VEDA Lexical Foundation (Phase 3)

Tests:
1. Streaming line and JSON record reading (O(1) memory safety).
2. Language filtering (English vs foreign records).
3. Plain English word candidate validation during extraction.
4. Multi-POS and multi-sense aggregation (e.g., 'free', 'dictionary', 'portmanteau').
5. Semantic relation extraction (synonyms, antonyms, definitions by POS).
6. Pronunciation (IPA) and inflected form extraction.
7. Lexicon querying, POS filtering, and dictionary containment.
8. Word Foundation & Character Registry integration (round-trip character IDs).
9. JSON persistence serialization and round-trip fidelity.
10. Streaming Word generator (stream_words).
"""

import json
import tempfile
import unittest
from pathlib import Path

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.lexicon import Lexicon
from foundation.lexicon.schemas import LexicalEntry, LexicalSense
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word


class TestLexicalFoundation(unittest.TestCase):
    """Test suite for VEDA English Lexical Foundation v0.1."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)
        cls.extractor = WiktionaryExtractor(analyzer=cls.analyzer)
        cls.sample_path = Path("veda_sample.jsonl")

    # --- 1. STREAMING RECORD PARSING TESTS ---

    def test_stream_raw_lines_and_records(self) -> None:
        """Verifies streaming generator reads lines and records line-by-line."""
        lines = list(self.extractor.stream_raw_lines(self.sample_path, max_lines=5))
        self.assertEqual(len(lines), 5)
        for line in lines:
            self.assertIsInstance(line, str)
            self.assertTrue(len(line) > 0)

        records = list(self.extractor.stream_raw_records(self.sample_path, max_lines=3))
        self.assertEqual(len(records), 3)
        for r in records:
            self.assertIsInstance(r, dict)
            self.assertIn("word", r)
            self.assertIn("lang", r)

    # --- 2. LANGUAGE FILTERING TESTS ---

    def test_language_filtering(self) -> None:
        """Verifies English entries are kept while Galician, German, Latin, etc. are filtered."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        stats = lexicon.stats

        self.assertEqual(stats.total_lines_read, 20)
        self.assertEqual(stats.english_records, 13)
        self.assertEqual(stats.non_english_skipped, 7)

        # Non-English words must NOT be in the aggregated lexicon
        self.assertNotIn("frei", lexicon)  # German
        self.assertIn("free", lexicon)      # English
        self.assertIn("dictionary", lexicon)

    # --- 3. MULTI-POS AND MULTI-SENSE AGGREGATION ---

    def test_multi_pos_aggregation_free(self) -> None:
        """Verifies 'free' aggregates 5 parts of speech (adj, adv, verb, noun, num)."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        free_entry = lexicon["free"]

        self.assertEqual(free_entry.word, "free")
        self.assertEqual(free_entry.normalized, "free")

        expected_pos = {"adj", "adv", "verb", "noun", "num"}
        self.assertTrue(expected_pos.issubset(set(free_entry.parts_of_speech)))

        # Definitions grouped by POS
        self.assertIn("adj", free_entry.definitions_by_pos)
        self.assertIn("verb", free_entry.definitions_by_pos)
        self.assertIn("noun", free_entry.definitions_by_pos)
        self.assertTrue(len(free_entry.definitions) >= 30)

        # Primary POS defaults to first encountered
        self.assertEqual(free_entry.primary_pos, "adj")

    def test_multi_pos_aggregation_dictionary_and_portmanteau(self) -> None:
        """Verifies multi-POS words like 'dictionary' (noun, verb) and 'portmanteau' (noun, adj, verb)."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)

        dict_entry = lexicon["dictionary"]
        self.assertIn("noun", dict_entry.parts_of_speech)
        self.assertIn("verb", dict_entry.parts_of_speech)
        self.assertTrue(len(dict_entry.definitions_by_pos["noun"]) >= 5)
        self.assertTrue(len(dict_entry.definitions_by_pos["verb"]) >= 2)

        port_entry = lexicon["portmanteau"]
        self.assertIn("noun", port_entry.parts_of_speech)
        self.assertIn("adj", port_entry.parts_of_speech)
        self.assertIn("verb", port_entry.parts_of_speech)

    # --- 4. SEMANTIC RELATIONS, FORMS, AND PRONUNCIATIONS ---

    def test_synonyms_antonyms_and_pronunciations(self) -> None:
        """Verifies extraction of IPA transcriptions, inflected forms, synonyms, and antonyms."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)

        # Dictionary IPA pronunciations
        dict_entry = lexicon["dictionary"]
        self.assertTrue(len(dict_entry.pronunciations) > 0)
        self.assertTrue(any("dɪk" in ipa for ipa in dict_entry.pronunciations))
        self.assertIn("dictionaries", dict_entry.forms)

        # Free synonyms & antonyms
        free_entry = lexicon["free"]
        self.assertTrue(len(free_entry.synonyms) > 0)
        self.assertTrue(len(free_entry.antonyms) > 0)
        self.assertIn("unconstrained", free_entry.synonyms)
        self.assertIn("constrained", free_entry.antonyms)

    # --- 5. CANDIDATE VALIDATION DURING EXTRACTION ---

    def test_candidate_validation_filter(self) -> None:
        """Verifies non-word candidates are skipped during extraction if validate_candidates=True."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".jsonl") as f:
            f.write(json.dumps({"word": "apple", "lang": "English", "pos": "noun", "senses": []}) + "\n")
            f.write(json.dumps({"word": "apple pie", "lang": "English", "pos": "noun", "senses": []}) + "\n")  # whitespace
            f.write(json.dumps({"word": "123", "lang": "English", "pos": "noun", "senses": []}) + "\n")        # digits
            f.write(json.dumps({"word": "café", "lang": "English", "pos": "noun", "senses": []}) + "\n")       # non-ascii
            f.write(json.dumps({"word": "good!", "lang": "English", "pos": "noun", "senses": []}) + "\n")      # punctuation
            temp_path = Path(f.name)

        try:
            lexicon = self.extractor.extract_lexicon(temp_path, validate_candidates=True)
            self.assertEqual(len(lexicon), 1)
            self.assertIn("apple", lexicon)
            self.assertEqual(lexicon.stats.invalid_candidates_skipped, 4)
            self.assertEqual(lexicon.stats.valid_candidates, 1)
        finally:
            if temp_path.is_file():
                temp_path.unlink()

    # --- 6. LEXICON CONTAINER QUERYING & FILTERING ---

    def test_lexicon_container_methods(self) -> None:
        """Verifies container methods: len, in, get, filter_by_pos, summary."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)

        self.assertEqual(len(lexicon), 6)
        self.assertTrue("free" in lexicon)
        self.assertTrue("DICTIONARY" in lexicon)  # case-insensitive check
        self.assertFalse("banana" in lexicon)

        # POS Filtering
        verbs = lexicon.filter_by_pos("verb")
        verb_words = [v.normalized for v in verbs]
        self.assertIn("dictionary", verb_words)
        self.assertIn("free", verb_words)
        self.assertIn("portmanteau", verb_words)
        self.assertNotIn("thesaurus", verb_words)

        # Summary dict
        summary = lexicon.summary()
        self.assertEqual(summary["total_words"], 6)
        self.assertGreater(summary["total_definitions"], 50)
        self.assertIn("noun", summary["pos_distribution"])
        self.assertIn("verb", summary["pos_distribution"])

    # --- 7. WORD FOUNDATION & CHARACTER REGISTRY INTEGRATION ---

    def test_word_foundation_integration(self) -> None:
        """Verifies lexicon.to_word() connects directly to Word and CharacterRegistry."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        word_obj = lexicon.to_word("dictionary")

        self.assertIsInstance(word_obj, Word)
        self.assertEqual(word_obj.normalized, "dictionary")
        self.assertEqual(word_obj.characters, ["d", "i", "c", "t", "i", "o", "n", "a", "r", "y"])
        self.assertEqual(len(word_obj.character_ids), 10)

        # Roundtrip invariant: decode_word(encode_word(w)) == normalized_w
        char_ids = self.analyzer.encode_word(word_obj)
        reconstructed = self.analyzer.decode_word(char_ids)
        self.assertEqual(reconstructed.normalized, "dictionary")

        # Lexical data attached to Word
        self.assertIsNotNone(word_obj.lexical)
        self.assertEqual(word_obj.lexical.part_of_speech, "noun")
        self.assertIn("verb", word_obj.lexical.parts_of_speech)
        self.assertTrue(len(word_obj.lexical.definitions) >= 5)

    def test_analyzer_dictionary_lookup(self) -> None:
        """Verifies WordAnalyzer can query an attached Lexicon."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        analyzer_with_lex = WordAnalyzer(registry=self.registry, lexicon=lexicon)

        # Both word candidate and dictionary word
        self.assertTrue(analyzer_with_lex.is_word_candidate("free"))
        self.assertTrue(analyzer_with_lex.is_dictionary_word("free"))

        # Valid word candidate, but not in sample dictionary
        self.assertTrue(analyzer_with_lex.is_word_candidate("banana"))
        self.assertFalse(analyzer_with_lex.is_dictionary_word("banana"))

        # Invalid plain word candidate
        self.assertFalse(analyzer_with_lex.is_word_candidate("123"))
        self.assertFalse(analyzer_with_lex.is_dictionary_word("123"))

        # Auto-populates lexical data via create_word
        word_auto = analyzer_with_lex.create_word("free")
        self.assertIsNotNone(word_auto.lexical.part_of_speech)
        self.assertIn("verb", word_auto.lexical.parts_of_speech)

    # --- 8. SERIALIZATION AND ROUNDTRIP FIDELITY ---

    def test_json_serialization_roundtrip(self) -> None:
        """Verifies Lexicon serialization to JSON and lossless deserialization."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            temp_path = Path(f.name)

        try:
            lexicon.save_to_json(temp_path)
            self.assertTrue(temp_path.is_file())

            reloaded = Lexicon.from_json_file(temp_path, registry=self.registry)
            self.assertEqual(len(reloaded), len(lexicon))
            self.assertEqual(reloaded.words(), lexicon.words())

            # Detailed word comparison
            for w in lexicon.words():
                orig = lexicon[w]
                reld = reloaded[w]
                self.assertEqual(orig.normalized, reld.normalized)
                self.assertEqual(orig.parts_of_speech, reld.parts_of_speech)
                self.assertEqual(orig.primary_pos, reld.primary_pos)
                self.assertEqual(orig.definitions, reld.definitions)
                self.assertEqual(orig.synonyms, reld.synonyms)
                self.assertEqual(orig.antonyms, reld.antonyms)
                self.assertEqual(orig.pronunciations, reld.pronunciations)
        finally:
            if temp_path.is_file():
                temp_path.unlink()

    # --- 9. STREAMING WORD GENERATOR ---

    def test_stream_words_generator(self) -> None:
        """Verifies stream_words yields Word objects directly from the raw file."""
        words = list(self.extractor.stream_words(self.sample_path, max_lines=10))
        self.assertTrue(len(words) > 0)
        for w in words:
            self.assertIsInstance(w, Word)
            self.assertTrue(w.is_alphabetic())
            self.assertIsNotNone(w.character_ids)


if __name__ == "__main__":
    unittest.main()
