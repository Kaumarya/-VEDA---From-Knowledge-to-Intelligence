"""
Unit Tests for VEDA Production SQLite Lexicon Storage (Phase 3)

Covers:
- SQLite schema initialization & table creation
- Exact normalized word lookup
- Case-normalized lookup (apple == Apple == APPLE)
- Exact surface lookup
- POS filtering (e.g. 'free' as 'verb' vs 'adj' vs missing POS)
- Lossless round-trip fidelity across all LexicalEntry attributes
- Multi-POS & multi-sense preservation in child tables
- Idempotent repeated ingestion
- Transaction rollback safety on simulated error
- PRAGMA integrity and foreign-key validation
- Metadata, versioning, and provenance inspection
- Missing word lookup and error handling
- Integration with Word Foundation and CharacterRegistry
"""

import json
import tempfile
import unittest
from pathlib import Path

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.schemas import LexicalEntry, LexicalSense, LexiconMetadata
from foundation.lexicon.storage import SqliteLexicon, SqliteLexiconBuilder
from foundation.words.word import Word


class TestSqliteLexiconStorage(unittest.TestCase):
    """Test suite for VEDA SQLite Production Lexicon Storage."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        cls.sample_path = Path("veda_sample.jsonl")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_lexicon.sqlite"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    # --- 1. SCHEMA & INITIALIZATION ---

    def test_schema_initialization_and_integrity(self) -> None:
        """Verifies tables and indices are created with PRAGMA integrity passing."""
        db = SqliteLexicon(self.db_path, read_only=False, registry=self.registry)
        self.assertTrue(self.db_path.is_file())

        health = db.integrity_check()
        self.assertTrue(health["is_healthy"])
        self.assertEqual(health["sqlite_integrity_check"], ["ok"])
        self.assertEqual(health["foreign_key_violations"], [])
        self.assertEqual(health["words_row_count"], 0)
        db.close()

    # --- 2. INGESTION, LOOKUP & NORMALIZATION ---

    def test_sample_build_and_lookups(self) -> None:
        """Builds sample database and tests exact and case-normalized lookups."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, batch_size=5, rebuild=True)

        self.assertEqual(len(db), 6)
        self.assertTrue("free" in db)
        self.assertTrue("dictionary" in db)

        # 1. Exact normalized lookup
        entry_free = db.lookup("free")
        self.assertIsNotNone(entry_free)
        self.assertEqual(entry_free.normalized, "free")
        self.assertEqual(entry_free.word, "free")

        # 2. Case-normalized lookup
        entry_upper = db.lookup("FREE")
        self.assertIsNotNone(entry_upper)
        self.assertEqual(entry_upper.normalized, "free")

        entry_title = db.lookup("Free")
        self.assertIsNotNone(entry_title)
        self.assertEqual(entry_title.normalized, "free")

        # 3. Surface lookup
        entry_surface = db.lookup("free", exact_surface=True)
        self.assertIsNotNone(entry_surface)
        self.assertIsNone(db.lookup("FREE", exact_surface=True))

        db.close()

    # --- 3. POS FILTERING ---

    def test_pos_filtering(self) -> None:
        """Verifies indexed POS filtering across single-word and batch queries."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        # Single word POS check
        self.assertIsNotNone(db.lookup("free", pos="adj"))
        self.assertIsNotNone(db.lookup("free", pos="verb"))
        self.assertIsNotNone(db.lookup("free", pos="noun"))
        self.assertIsNone(db.lookup("free", pos="conjunction"))

        # Batch filter by POS
        verbs = db.filter_by_pos("verb")
        verb_words = [v.normalized for v in verbs]
        self.assertIn("free", verb_words)
        self.assertIn("dictionary", verb_words)
        self.assertIn("portmanteau", verb_words)
        self.assertNotIn("thesaurus", verb_words)

        db.close()

    # --- 4. LOSSLESS ROUND-TRIP FIDELITY ---

    def test_lossless_roundtrip_fidelity(self) -> None:
        """Verifies exact attribute preservation between Extractor and SQLite."""
        extractor = WiktionaryExtractor()
        in_memory_lex = extractor.extract_lexicon(self.sample_path)

        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        self.assertEqual(len(db), len(in_memory_lex))

        for word_key in in_memory_lex.words():
            orig = in_memory_lex[word_key]
            reconstructed = db.lookup(word_key)
            self.assertIsNotNone(reconstructed)

            self.assertEqual(orig.word, reconstructed.word)
            self.assertEqual(orig.normalized, reconstructed.normalized)
            self.assertEqual(orig.language, reconstructed.language)
            self.assertEqual(orig.parts_of_speech, reconstructed.parts_of_speech)
            self.assertEqual(orig.primary_pos, reconstructed.primary_pos)
            self.assertEqual(orig.definitions, reconstructed.definitions)
            self.assertEqual(orig.definitions_by_pos, reconstructed.definitions_by_pos)
            self.assertEqual(orig.pronunciations, reconstructed.pronunciations)
            self.assertEqual(orig.forms, reconstructed.forms)
            self.assertEqual(orig.synonyms, reconstructed.synonyms)
            self.assertEqual(orig.antonyms, reconstructed.antonyms)
            self.assertEqual(orig.etymology, reconstructed.etymology)
            self.assertEqual(orig.provenance, reconstructed.provenance)
            self.assertEqual(len(orig.senses), len(reconstructed.senses))

        db.close()

    # --- 5. MULTI-POS & MULTI-SENSE PRESERVATION ---

    def test_multi_pos_and_multi_sense_preservation(self) -> None:
        """Verifies multi-POS words like 'free' keep distinct senses and child rows."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        free_entry = db["free"]
        self.assertGreaterEqual(len(free_entry.parts_of_speech), 5)
        self.assertIn("adj", free_entry.parts_of_speech)
        self.assertIn("verb", free_entry.parts_of_speech)
        self.assertIn("noun", free_entry.parts_of_speech)

        # Senses contain granular fields
        self.assertGreater(len(free_entry.senses), 10)
        has_examples = any(len(s.examples) > 0 for s in free_entry.senses)
        self.assertTrue(has_examples)

        health = db.integrity_check()
        self.assertEqual(health["words_row_count"], 6)
        self.assertEqual(health["distinct_normalized_words_in_pos"], 6)
        self.assertGreaterEqual(health["senses_row_count"], 50)

        db.close()

    # --- 6. IDEMPOTENT INGESTION ---

    def test_idempotent_ingestion(self) -> None:
        """Re-ingesting the same source dataset does not duplicate records or senses."""
        builder = SqliteLexiconBuilder()

        # Ingestion 1
        db1 = builder.build(self.sample_path, self.db_path, rebuild=True)
        count_1 = db1.count()
        chk_1 = db1.integrity_check()
        db1.close()

        # Ingestion 2 without rebuild
        db2 = builder.build(self.sample_path, self.db_path, rebuild=False)
        count_2 = db2.count()
        chk_2 = db2.integrity_check()
        db2.close()

        self.assertEqual(count_1, count_2)
        self.assertEqual(chk_1["words_row_count"], chk_2["words_row_count"])
        self.assertEqual(chk_1["word_pos_row_count"], chk_2["word_pos_row_count"])
        self.assertEqual(chk_1["senses_row_count"], chk_2["senses_row_count"])

    # --- 7. TRANSACTION ROLLBACK SAFETY ---

    def test_transaction_rollback_on_failure(self) -> None:
        """Simulated mid-ingestion failure cleans up temp files and leaves target intact."""
        builder = SqliteLexiconBuilder()

        # First build a valid database
        db_orig = builder.build(self.sample_path, self.db_path, rebuild=True)
        self.assertEqual(len(db_orig), 6)
        db_orig.close()

        # Attempt build with unreadable/corrupt source that raises exception
        corrupt_source = Path(self.temp_dir.name) / "corrupt.jsonl"
        with open(corrupt_source, "w", encoding="utf-8") as f:
            f.write('{"word": "apple", "lang": "English", "pos": "noun", "senses": []}\n')

        # Mock extractor to raise error on second line
        original_parse = builder.extractor.parse_record
        def faulty_parse(rec):
            raise RuntimeError("Simulated transaction crash!")

        builder.extractor.parse_record = faulty_parse

        with self.assertRaises(RuntimeError):
            builder.build(corrupt_source, self.db_path, rebuild=True)

        builder.extractor.parse_record = original_parse

        # Verify the original database is still intact and queryable
        db_verified = SqliteLexicon(self.db_path, read_only=True)
        self.assertEqual(len(db_verified), 6)
        db_verified.close()

    # --- 8. METADATA & PROVENANCE ---

    def test_metadata_and_provenance(self) -> None:
        """Verifies database metadata and entry-level provenance tracking."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        meta = db.get_metadata()
        self.assertEqual(meta.project, "VEDA")
        self.assertEqual(meta.component, "Production Lexicon")
        self.assertEqual(meta.schema_version, "0.1.0")
        self.assertEqual(meta.extractor_version, "0.1.0")
        self.assertEqual(meta.normalization_version, "0.1.0")
        self.assertEqual(meta.word_count, 6)
        self.assertIn("noun", meta.pos_distribution)

        stats = db.get_latest_ingestion_stats()
        self.assertIsNotNone(stats)
        self.assertEqual(stats["total_lines_read"], 20)
        self.assertEqual(stats["english_records"], 13)
        self.assertEqual(stats["unique_words_aggregated"], 6)

        db.close()

    # --- 9. MISSING WORD LOOKUPS ---

    def test_missing_word_lookups(self) -> None:
        """Verifies graceful handling of nonexistent words."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        self.assertIsNone(db.lookup("nonexistentword"))
        self.assertFalse(db.has_word("nonexistentword"))
        self.assertFalse("nonexistentword" in db)

        with self.assertRaises(KeyError):
            _ = db["nonexistentword"]

        db.close()

    # --- 10. WORD FOUNDATION INTEGRATION ---

    def test_word_foundation_integration(self) -> None:
        """Verifies db.to_word() reconstructs rich Word instances with CharacterRegistry IDs."""
        builder = SqliteLexiconBuilder()
        db = builder.build(self.sample_path, self.db_path, rebuild=True)

        word_obj = db.to_word("free")
        self.assertIsInstance(word_obj, Word)
        self.assertEqual(word_obj.normalized, "free")
        self.assertEqual(word_obj.characters, ["f", "r", "e", "e"])
        self.assertEqual(word_obj.character_ids, [72, 84, 71, 71])
        self.assertIsNotNone(word_obj.lexical)
        self.assertIn("verb", word_obj.lexical.parts_of_speech)

        db.close()

    # --- 11. GRANULAR ATTRIBUTES & DUPLICATE GLOSSES ---

    def test_multi_pos_multi_sense_granular_attributes(self) -> None:
        """Verifies duplicate glosses deduplicate while distinct examples, tags, forms, synonyms are preserved."""
        builder = SqliteLexiconBuilder()

        # Create custom records with duplicate glosses, distinct examples & tags
        custom_source = Path(self.temp_dir.name) / "custom.jsonl"
        with open(custom_source, "w", encoding="utf-8") as f:
            # First record for "run" (noun)
            r1 = {
                "word": "run",
                "lang": "English",
                "pos": "noun",
                "senses": [
                    {
                        "glosses": ["An act of running."],
                        "tags": ["countable"],
                        "examples": [{"text": "He went for a morning run."}],
                    }
                ],
                "forms": [{"form": "runs"}],
                "synonyms": [{"word": "jog"}],
            }
            # Second record for "run" (noun) with identical gloss but new example
            r2 = {
                "word": "run",
                "lang": "English",
                "pos": "noun",
                "senses": [
                    {
                        "glosses": ["An act of running."],
                        "tags": ["sport"],
                        "examples": [{"text": "A five-mile run."}],
                    }
                ],
                "forms": [{"form": "running"}],
                "antonyms": [{"word": "walk"}],
            }
            # Third record for "run" (verb)
            r3 = {
                "word": "run",
                "lang": "English",
                "pos": "verb",
                "senses": [
                    {
                        "glosses": ["To move swiftly on foot."],
                        "tags": ["intransitive"],
                        "examples": [{"text": "The dog ran fast."}],
                    },
                    {
                        "glosses": ["To operate or manage."],
                        "tags": ["transitive"],
                        "examples": [{"text": "She runs a business."}],
                    },
                ],
                "sounds": [{"ipa": "/rʌn/"}],
            }
            f.write(json.dumps(r1) + "\n" + json.dumps(r2) + "\n" + json.dumps(r3) + "\n")

        db = builder.build(custom_source, self.db_path, rebuild=True)
        try:
            entry = db.lookup("run")
            self.assertIsNotNone(entry)
            self.assertIn("noun", entry.parts_of_speech)
            self.assertIn("verb", entry.parts_of_speech)

            # Definitions deduplicate identical glosses
            self.assertEqual(len(entry.definitions_by_pos["noun"]), 1)
            self.assertEqual(entry.definitions_by_pos["noun"], ["An act of running."])
            self.assertEqual(len(entry.definitions_by_pos["verb"]), 2)

            # Senses contain distinct examples and tags
            noun_senses = [s for s in entry.senses if s.pos == "noun"]
            self.assertEqual(len(noun_senses), 2)
            all_noun_examples = [ex for s in noun_senses for ex in s.examples]
            self.assertIn("He went for a morning run.", all_noun_examples)
            self.assertIn("A five-mile run.", all_noun_examples)

            # Forms, synonyms, antonyms, pronunciations preserved
            self.assertIn("runs", entry.forms)
            self.assertIn("running", entry.forms)
            self.assertIn("jog", entry.synonyms)
            self.assertIn("walk", entry.antonyms)
            self.assertIn("/rʌn/", entry.pronunciations)

            # Provenance present
            self.assertIsNotNone(entry.provenance)
            self.assertEqual(entry.provenance["source_dataset"], "Wiktionary (Wiktextract)")
        finally:
            db.close()

    # --- 12. BATCH BOUNDARY CROSS-MERGING ---

    def test_batch_boundary_cross_merging(self) -> None:
        """Verifies records for the same word appearing in separate commit batches merge cleanly."""
        builder = SqliteLexiconBuilder()

        # Batch size 1 forces every line to be a separate commit batch
        custom_source = Path(self.temp_dir.name) / "batch_test.jsonl"
        with open(custom_source, "w", encoding="utf-8") as f:
            f.write(json.dumps({"word": "apple", "lang": "English", "pos": "noun", "senses": [{"glosses": ["A fruit."]}]}) + "\n")
            f.write(json.dumps({"word": "banana", "lang": "English", "pos": "noun", "senses": [{"glosses": ["A yellow fruit."]}]}) + "\n")
            f.write(json.dumps({"word": "apple", "lang": "English", "pos": "verb", "senses": [{"glosses": ["To harvest apples."]}]}) + "\n")

        db = builder.build(custom_source, self.db_path, batch_size=1, rebuild=True)
        try:
            self.assertEqual(len(db), 2)

            apple = db.lookup("apple")
            self.assertIsNotNone(apple)
            self.assertIn("noun", apple.parts_of_speech)
            self.assertIn("verb", apple.parts_of_speech)
            self.assertEqual(len(apple.senses), 2)

            chk = db.integrity_check()
            self.assertTrue(chk["is_healthy"])
            self.assertEqual(chk["words_row_count"], 2)
            self.assertEqual(chk["word_pos_row_count"], 3)  # apple:noun, apple:verb, banana:noun
            self.assertEqual(chk["senses_row_count"], 3)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
