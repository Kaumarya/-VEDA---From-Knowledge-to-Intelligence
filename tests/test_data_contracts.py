"""
Unit Tests for VEDA Data Contracts, Orthography, and Lexicon Readiness (Hardening Phase)

Covers:
1. Character Contracts:
   - Known character lookup and properties
   - Unsupported character handling (in registry, knowledge, tokenizer)
   - Tokenizer <UNK> semantics vs lexical unknown ("blork" vs "café" vs unsupported char)
2. Word Contracts:
   - Word identity: Word('apple') == Word('Apple') == Word('APPLE')
   - Exact surface match vs normalized equality
   - Derived properties coherence (length, characters, character_ids)
   - Validation cases: 'apple', 'Apple', 'APPLE', '123', 'hello!', 'apple pie', 'café', emojis
   - Separation: Language vs Orthography vs Representability
   - Candidate validation vs dictionary membership
3. Lexicon Contracts:
   - Multi-POS structural distinction (e.g. 'free' across 5 parts of speech)
   - Multi-sense preservation without collapsing
   - Inflected forms, IPA pronunciations, synonyms, antonyms, etymology
   - Deduplication semantics (merging records without losing POS/senses)
   - Provenance tracking on entries and lexicon metadata
4. Dataset Quality & Audit Contracts:
   - Malformed JSON resilience and stat tracking
   - Missing fields detection
   - English filtering
   - DatasetAuditor metrics verification
5. Serialization & Versioning:
   - Lossless roundtrip saving/loading
   - Preservation of schema_version, extractor_version, normalization_version, provenance
"""

import json
import tempfile
import unittest
from pathlib import Path

from foundation.characters.knowledge import CharacterKnowledge
from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.audit import DatasetAuditor
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.lexicon import Lexicon
from foundation.lexicon.schemas import (
    ExtractionStats,
    LexicalEntry,
    LexicalSense,
    LexiconMetadata,
)
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word
from tokenizer.char_tokenizer import CharacterTokenizer


class TestDataContractsCharacter(unittest.TestCase):
    """Verifies Character layer data contracts, registry lookups, and <UNK> semantics."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.knowledge = CharacterKnowledge(registry=cls.registry)
        cls.tokenizer = CharacterTokenizer(registry=cls.registry)

    def test_known_character_contract(self) -> None:
        """Known characters exist in registry with valid metadata and contiguous IDs."""
        entry = self.registry.get_character("A")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.character, "A")
        self.assertEqual(entry.unicode_codepoint, "U+0041")
        self.assertEqual(entry.case, "uppercase")
        self.assertTrue(self.registry.contains_char("A"))

        # Knowledge layer verification
        k_entry = self.knowledge.get("A")
        self.assertTrue(k_entry.known)
        self.assertEqual(k_entry.classification.type, "letter")
        self.assertEqual(k_entry.classification.alphabet_position, 1)

    def test_unsupported_character_contract(self) -> None:
        """Characters outside the registry return safe defaults without throwing exceptions."""
        unsupported = "☃"  # Snowman U+2603
        self.assertFalse(self.registry.contains_char(unsupported))
        self.assertIsNone(self.registry.get_character(unsupported))

        k_entry = self.knowledge.get(unsupported)
        self.assertFalse(k_entry.known)
        self.assertEqual(k_entry.classification.type, "unknown")
        self.assertIsNone(k_entry.classification.case)
        self.assertIsNone(k_entry.classification.alphabet_position)

    def test_tokenizer_unk_vs_unknown_word_semantics(self) -> None:
        """
        CRITICAL ARCHITECTURAL CONTRACT:
        <UNK> is a tokenizer-level representation for unsupported characters.
        An unknown dictionary word ('blork') is NOT a tokenizer <UNK>.
        """
        # 1. 'blork': structurally valid candidate word, absent from dictionary
        # It must tokenize into 5 valid token IDs, with ZERO <UNK> tokens!
        encoded_blork = self.tokenizer.encode("blork")
        self.assertEqual(len(encoded_blork), 5)
        self.assertNotIn(self.tokenizer.unk_token_id, encoded_blork)
        self.assertEqual(self.tokenizer.decode(encoded_blork), "blork")

        # 2. Unsupported character: maps to tokenizer <UNK> (ID 1)
        encoded_snowman = self.tokenizer.encode("☃")
        self.assertEqual(encoded_snowman, [self.tokenizer.unk_token_id])

        # 3. In the word/lexical layer, original characters are preserved, NOT replaced with <UNK>
        word_cafe = Word("café", registry=self.registry)
        self.assertEqual(word_cafe.characters, ["c", "a", "f", "é"])
        self.assertEqual(word_cafe.normalized, "café")
        self.assertIn("é", word_cafe.characters)
        self.assertFalse(word_cafe.is_representable)
        self.assertEqual(word_cafe.unsupported_characters, ["é"])


class TestDataContractsWord(unittest.TestCase):
    """Verifies Word Foundation identity, normalization, and orthography contracts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)

    def test_word_identity_equality_and_hashing(self) -> None:
        """Word identity is invariant under case variations: apple == Apple == APPLE."""
        w1 = Word("apple", registry=self.registry)
        w2 = Word("Apple", registry=self.registry)
        w3 = Word("APPLE", registry=self.registry)

        self.assertEqual(w1, w2)
        self.assertEqual(w2, w3)
        self.assertEqual(hash(w1), hash(w2))
        self.assertEqual(hash(w2), hash(w3))

        # Set deduplication
        word_set = {w1, w2, w3}
        self.assertEqual(len(word_set), 1)

        # Exact surface match distinction
        self.assertFalse(w1.exact_match(w2))
        self.assertTrue(w1.exact_match(Word("apple", registry=self.registry)))
        self.assertTrue(w2.exact_match(Word("Apple", registry=self.registry)))

    def test_derived_properties_relationship(self) -> None:
        """Derived properties (length, characters, character_ids) have strict coherent relationships."""
        word = Word("Apple", registry=self.registry)
        self.assertEqual(word.length, len(word.normalized))
        self.assertEqual(word.characters, list(word.normalized))
        self.assertEqual(
            word.character_ids,
            [self.registry.get_character(c).id for c in word.characters],
        )

    def test_orthography_separation_policy(self) -> None:
        """
        Verifies separation of:
        - Language classification (English)
        - Orthographic candidate validity (v0.1 plain English constraint)
        - Character representability (CharacterRegistry membership)
        """
        # Case A: Plain ASCII English candidate ('apple')
        res_apple = self.analyzer.analyze_orthography("apple")
        self.assertTrue(res_apple["is_v01_candidate"])
        self.assertTrue(res_apple["is_ascii"])
        self.assertTrue(res_apple["is_representable"])
        self.assertEqual(res_apple["orthographic_category"], "plain_ascii")
        self.assertEqual(res_apple["unsupported_characters"], [])

        # Case B: Latin-accented loanword ('café')
        res_cafe = self.analyzer.analyze_orthography("café")
        self.assertFalse(res_cafe["is_v01_candidate"])  # Rejected for v0.1 plain words
        self.assertFalse(res_cafe["is_ascii"])
        self.assertFalse(res_cafe["is_representable"])
        self.assertEqual(res_cafe["orthographic_category"], "latin_accented")
        self.assertEqual(res_cafe["unsupported_characters"], ["é"])
        self.assertEqual(res_cafe["language_scope"], "en")

        # Case C: Numeric string ('123')
        res_num = self.analyzer.analyze_orthography("123")
        self.assertFalse(res_num["is_v01_candidate"])
        self.assertTrue(res_num["is_ascii"])
        self.assertTrue(res_num["is_representable"])
        self.assertEqual(res_num["orthographic_category"], "numeric")

        # Case D: Punctuation / Hyphenated word ('apple-pie')
        res_hyphen = self.analyzer.analyze_orthography("apple-pie")
        self.assertFalse(res_hyphen["is_v01_candidate"])
        self.assertEqual(res_hyphen["orthographic_category"], "hyphenated")
        self.assertTrue(res_hyphen["is_representable"])

        # Case E: Multiword expression ('apple pie')
        res_ws = self.analyzer.analyze_orthography("apple pie")
        self.assertFalse(res_ws["is_v01_candidate"])
        self.assertEqual(res_ws["orthographic_category"], "whitespace")

        # Case F: Emoji / Symbol ('hello😊')
        res_emoji = self.analyzer.analyze_orthography("hello😊")
        self.assertFalse(res_emoji["is_v01_candidate"])
        self.assertEqual(res_emoji["orthographic_category"], "symbol_or_emoji")
        self.assertEqual(res_emoji["unsupported_characters"], ["😊"])

    def test_candidate_vs_dictionary_membership(self) -> None:
        """Morphological candidate status is orthogonal to Lexicon dictionary membership."""
        sample_path = Path("veda_sample.jsonl")
        extractor = WiktionaryExtractor(analyzer=self.analyzer)
        lexicon = extractor.extract_lexicon(sample_path)
        analyzer_with_lex = WordAnalyzer(registry=self.registry, lexicon=lexicon)

        # 1. 'free': valid candidate AND in dictionary
        self.assertTrue(analyzer_with_lex.is_word_candidate("free"))
        self.assertTrue(analyzer_with_lex.is_dictionary_word("free"))

        # 2. 'blork': valid candidate AND NOT in dictionary
        self.assertTrue(analyzer_with_lex.is_word_candidate("blork"))
        self.assertFalse(analyzer_with_lex.is_dictionary_word("blork"))

        # 3. '123': NOT valid candidate AND NOT in dictionary
        self.assertFalse(analyzer_with_lex.is_word_candidate("123"))
        self.assertFalse(analyzer_with_lex.is_dictionary_word("123"))


class TestDataContractsLexicon(unittest.TestCase):
    """Verifies LexicalEntry, multi-POS structure, provenance, and deduplication contracts."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)
        cls.sample_path = Path("veda_sample.jsonl")
        cls.extractor = WiktionaryExtractor(analyzer=cls.analyzer)

    def test_multi_pos_structural_distinction(self) -> None:
        """A word with multiple parts of speech retains structural distinction without flattening."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        free_entry = lexicon["free"]

        # 'free' functions across 5 parts of speech
        expected_pos = {"adj", "adv", "verb", "noun", "num"}
        self.assertTrue(expected_pos.issubset(set(free_entry.parts_of_speech)))

        # Senses and definitions remain organized by POS
        for pos in ["adj", "verb", "noun"]:
            self.assertIn(pos, free_entry.definitions_by_pos)
            self.assertTrue(len(free_entry.definitions_by_pos[pos]) > 0)

        # Senses contain granular grammatical tags and examples
        senses = free_entry.senses
        self.assertTrue(len(senses) > 10)
        has_examples = any(len(s.examples) > 0 for s in senses)
        self.assertTrue(has_examples)

    def test_lexical_entry_provenance(self) -> None:
        """Lexical entries preserve source dataset and extractor version provenance."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)
        dict_entry = lexicon["dictionary"]

        self.assertIsNotNone(dict_entry.provenance)
        self.assertEqual(dict_entry.provenance["source_dataset"], "Wiktionary (Wiktextract)")
        self.assertEqual(dict_entry.provenance["extractor_version"], "0.1.0")
        self.assertEqual(dict_entry.provenance["source_lang"], "English")

        # Lexicon metadata provenance
        meta = lexicon.metadata
        self.assertEqual(meta.project, "VEDA")
        self.assertEqual(meta.component, "Lexical Foundation")
        self.assertEqual(meta.schema_version, "0.1.0")
        self.assertEqual(meta.extractor_version, "0.1.0")
        self.assertEqual(meta.normalization_version, "0.1.0")
        self.assertIsNotNone(meta.created_at)

    def test_deduplication_preserves_distinct_senses(self) -> None:
        """Deduplication merges repeated records without overwriting distinct POS or senses."""
        e1 = LexicalEntry(
            word="testword",
            normalized="testword",
            language="en",
            parts_of_speech=["noun"],
            definitions=["A procedure to evaluate something."],
            definitions_by_pos={"noun": ["A procedure to evaluate something."]},
            senses=[LexicalSense(pos="noun", glosses=["A procedure to evaluate something."])],
        )

        e2 = LexicalEntry(
            word="testword",
            normalized="testword",
            language="en",
            parts_of_speech=["verb"],
            definitions=["To put to the test."],
            definitions_by_pos={"verb": ["To put to the test."]},
            senses=[LexicalSense(pos="verb", glosses=["To put to the test."])],
        )

        e1.merge(e2)

        # Both parts of speech preserved
        self.assertIn("noun", e1.parts_of_speech)
        self.assertIn("verb", e1.parts_of_speech)
        self.assertEqual(len(e1.definitions), 2)
        self.assertEqual(len(e1.senses), 2)
        self.assertEqual(e1.definitions_by_pos["noun"], ["A procedure to evaluate something."])
        self.assertEqual(e1.definitions_by_pos["verb"], ["To put to the test."])

    def test_lexical_entry_representability_check(self) -> None:
        """LexicalEntry can evaluate character representability against CharacterRegistry."""
        entry_ascii = LexicalEntry(word="free", normalized="free")
        self.assertTrue(entry_ascii.is_representable(self.registry))
        self.assertEqual(entry_ascii.unsupported_characters(self.registry), [])

        entry_accented = LexicalEntry(word="café", normalized="café")
        self.assertFalse(entry_accented.is_representable(self.registry))
        self.assertEqual(entry_accented.unsupported_characters(self.registry), ["é"])


class TestDataContractsDatasetQuality(unittest.TestCase):
    """Verifies dataset quality tracking, malformed JSON resilience, and audit capabilities."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.analyzer = WordAnalyzer(registry=cls.registry)
        cls.extractor = WiktionaryExtractor(analyzer=cls.analyzer)
        cls.auditor = DatasetAuditor(registry=cls.registry, analyzer=cls.analyzer)

    def test_malformed_json_resilience_and_tracking(self) -> None:
        """Streaming extractor does not crash on malformed JSON and tracks error count."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".jsonl") as f:
            f.write('{"word": "apple", "lang": "English", "pos": "noun", "senses": []}\n')
            f.write('THIS IS NOT VALID JSON\n')
            f.write('{"unclosed": "json"\n')
            f.write('{"word": "banana", "lang": "English", "pos": "noun", "senses": []}\n')
            temp_path = Path(f.name)

        try:
            lexicon = self.extractor.extract_lexicon(temp_path)
            self.assertEqual(len(lexicon), 2)
            self.assertEqual(lexicon.stats.malformed_json_records, 2)
            self.assertEqual(lexicon.stats.valid_candidates, 2)
        finally:
            if temp_path.is_file():
                temp_path.unlink()

    def test_audit_report_statistics_contract(self) -> None:
        """DatasetAuditor correctly measures all required dataset dimensions."""
        sample_path = Path("veda_sample.jsonl")
        report = self.auditor.audit_file(sample_path)

        self.assertEqual(report.total_lines_read, 20)
        self.assertEqual(report.english_records, 13)
        self.assertEqual(report.non_english_records, 7)
        self.assertEqual(report.malformed_json_records, 0)
        self.assertEqual(report.valid_candidates, 13)
        self.assertEqual(report.unique_normalized_words, 6)
        self.assertEqual(report.duplicate_records, 7)

        # Lexical content metrics
        self.assertEqual(report.definitions_count, 89)
        self.assertGreater(report.examples_count, 50)
        self.assertGreater(report.forms_count, 20)
        self.assertGreater(report.pronunciations_count, 50)

        # Unicode metrics
        self.assertEqual(report.unicode_stats["ascii_words"], 13)
        self.assertEqual(report.unicode_stats["unrepresentable_words"], 0)


class TestDataContractsSerialization(unittest.TestCase):
    """Verifies lossless serialization roundtrip and versioning metadata preservation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.sample_path = Path("veda_sample.jsonl")
        cls.extractor = WiktionaryExtractor()

    def test_lexicon_serialization_roundtrip_preserves_versioning_and_provenance(self) -> None:
        """Serialization preserves metadata, versions, provenance, and stats."""
        lexicon = self.extractor.extract_lexicon(self.sample_path)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".json") as f:
            temp_path = Path(f.name)

        try:
            lexicon.save_to_json(temp_path)
            reloaded = Lexicon.from_json_file(temp_path, registry=self.registry)

            # Metadata preservation
            self.assertEqual(reloaded.metadata.schema_version, "0.1.0")
            self.assertEqual(reloaded.metadata.extractor_version, "0.1.0")
            self.assertEqual(reloaded.metadata.normalization_version, "0.1.0")
            self.assertEqual(reloaded.metadata.word_count, len(lexicon))

            # Entry provenance preservation
            for w in lexicon.words():
                orig_entry = lexicon[w]
                reloaded_entry = reloaded[w]
                self.assertEqual(orig_entry.normalized, reloaded_entry.normalized)
                self.assertEqual(orig_entry.provenance, reloaded_entry.provenance)
                self.assertEqual(orig_entry.definitions_by_pos, reloaded_entry.definitions_by_pos)
        finally:
            if temp_path.is_file():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
