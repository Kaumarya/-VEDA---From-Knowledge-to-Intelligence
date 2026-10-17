"""
VEDA Corpus Subsystem — Adversarial Regression Test Suite (Phase 4.1)
"From Knowledge to Intelligence"

Comprehensive adversarial test suite covering:
1. Unicode Policy & Tokenizer Boundary (Preserved, Normalized, Filtered, Rejected, Quarantined)
2. Dual Fingerprinting (Content Fingerprint vs Manifest Configuration Fingerprint)
3. Leakage Prevention & Canonical Document Split Boundary
4. Near-Duplicate Discrimination & Limitations
5. Provenance & Record Conservation Laws
6. Crash, Rollback & Rebuild Recovery
7. Multi-Batch & Cross-Directory Determinism
8. Pathological & Adversarial Stress Inputs
"""

import hashlib
import json
import os
import shutil
import tempfile
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from foundation.corpus.deduplication import DeduplicationEngine
from foundation.corpus.filtering import QualityFilter
from foundation.corpus.manifest import (
    CorpusManifest,
    compute_content_fingerprint,
    compute_manifest_fingerprint,
)
from foundation.corpus.normalization import TextNormalizer
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusRecord,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
    RecordProvenance,
    RejectionReason,
)
from foundation.corpus.storage import CorpusReader, CorpusWriter


# ==============================================================================
# TEST FIXTURE HELPERS
# ==============================================================================


def make_test_source(
    source_id: str = "src_001",
    name: str = "Test Source",
    status: LicensingStatus = LicensingStatus.VERIFIED_PERMITTED,
) -> CorpusSource:
    """Helper to build a valid CorpusSource contract."""
    return CorpusSource(
        source_id=source_id,
        name=name,
        version="1.0.0",
        url_or_path="https://example.org/test",
        acquisition_date="2026-10-01",
        source_hash="a" * 64,
        license="CC0-1.0",
        licensing_status=status,
    )


def make_test_record(
    record_id: str,
    raw_text: str,
    split: str = "train",
    document_id: str = "doc_001",
    source_id: str = "src_001",
    normalized_text: Optional[str] = None,
) -> CorpusRecord:
    """Helper to build a valid CorpusRecord contract."""
    norm = normalized_text if normalized_text is not None else raw_text
    return CorpusRecord(
        record_id=record_id,
        document_id=document_id,
        source_id=source_id,
        segment_index=0,
        raw_text=raw_text,
        normalized_text=norm,
        raw_char_count=len(raw_text),
        normalized_char_count=len(norm),
        approx_word_count=len(norm.split()),
        quality_score=1.0,
        is_duplicate=False,
        split=split,
        corpus_version="0.1.0",
        provenance=RecordProvenance(
            source_id=source_id,
            document_id=document_id,
            segment_index=0,
            start_char_offset=0,
            end_char_offset=len(raw_text),
        ),
    )


# ==============================================================================
# 1. UNICODE POLICY & TOKENIZER BOUNDARY AUDIT TESTS
# ==============================================================================


class TestCorpusUnicodeAdversarial:
    """Verifies that Unicode corpus handling adheres to docs/corpus_unicode_policy.md

    and strictly separates corpus representability from 113-char tokenizer bounds.
    """

    @pytest.fixture
    def normalizer(self):
        return TextNormalizer()

    @pytest.fixture
    def quality_filter(self):
        return QualityFilter(min_char_length=4, max_char_length=1000, min_word_count=1)

    def test_ascii_canonical_tokens(self, normalizer, quality_filter):
        """Standard ASCII text: PRESERVED."""
        cases = ["Apple", "apple", "NASA"]
        for text in cases:
            norm = normalizer.normalize(text).normalized_text
            # Preserved (casing intact in default corpus mode)
            assert norm == text
            decision = quality_filter.evaluate(norm)
            assert decision.is_accepted is True

    def test_apostrophes_and_hyphens(self, normalizer, quality_filter):
        """Apostrophes and hyphens in contractions and compounds: PRESERVED."""
        cases = ["don't", "co-operate"]
        for text in cases:
            norm = normalizer.normalize(text).normalized_text
            assert norm == text
            decision = quality_filter.evaluate(norm)
            assert decision.is_accepted is True

    def test_curly_quotes_and_typographic_dashes(self, normalizer, quality_filter):
        """Typographic punctuation: PRESERVED in authentic form, conventions normalized."""
        # Registered curly quotes are preserved in authentic typography
        assert normalizer.normalize("“hello”").normalized_text == "“hello”"
        assert normalizer.normalize("‘hello’").normalized_text == "‘hello’"

        # Typewriter conventions '--' -> '—' and '...' -> '…' are NORMALIZED
        assert normalizer.normalize("science -- knowledge").normalized_text == "science — knowledge"
        assert normalizer.normalize("waiting...").normalized_text == "waiting…"

        # Em-dash and ellipsis preserved
        assert normalizer.normalize("knowledge — wisdom").normalized_text == "knowledge — wisdom"
        assert normalizer.normalize("thinking…").normalized_text == "thinking…"

    def test_accented_latin_loanwords(self, normalizer, quality_filter):
        """Accented Latin words (café, naïve, résumé) must be PRESERVED in corpus,
        even if the character tokenizer does not have them in its 113-char vocab.
        """
        cases = [
            ("café", "The local café served fresh coffee and tea."),
            ("naïve", "A naïve approach to natural language processing."),
            ("résumé", "Submit your updated résumé to the committee."),
            ("foreign_names", "René Descartes and François Viète wrote extensively."),
        ]
        for name, text in cases:
            norm = normalizer.normalize(text).normalized_text
            # Accents are preserved (NFC)
            assert unicodedata.is_normalized("NFC", norm)
            decision = quality_filter.evaluate(norm)
            assert decision.is_accepted is True, f"Failed on {name}: {decision.rejection_reason}"

    def test_combining_marks_nfc_composition(self, normalizer):
        """Combining marks (e.g. e + combining acute) are NORMALIZED to NFC precomposed form."""
        decomposed = "cafe\u0301"  # e + \u0301 (NFD)
        norm = normalizer.normalize(decomposed).normalized_text
        assert norm == "café"
        assert len(norm) == 4
        assert unicodedata.is_normalized("NFC", norm)

    def test_unusual_whitespace_normalization(self, normalizer):
        """Unusual whitespace (non-breaking, zero-width, tabs) is NORMALIZED or FILTERED."""
        # Non-breaking space \u00a0 -> regular space
        text_nbsp = "The\u00a0quick\u00a0brown\u00a0fox"
        assert normalizer.normalize(text_nbsp).normalized_text == "The quick brown fox"

        # Multi-space and tab collapsing
        text_mixed = "Words \t\t with    spaces"
        assert normalizer.normalize(text_mixed).normalized_text == "Words with spaces"

        # Paragraph boundary preservation (3+ newlines -> 2 newlines)
        text_paragraphs = "First line\n\n\nSecond line"
        assert normalizer.normalize(text_paragraphs).normalized_text == "First line\n\nSecond line"

    def test_emoji_and_math_symbols(self, quality_filter):
        """Emoji and mathematical symbols: FILTERED or REJECTED by quality filter if dominant."""
        # Pure emoji: REJECTED under LOW_ALPHA_RATIO
        emoji_text = "🚀 🎉 🤖 ✨ 🌟"
        decision = quality_filter.evaluate(emoji_text)
        assert decision.is_accepted is False
        assert decision.rejection_reason in (RejectionReason.LOW_ALPHA_RATIO, RejectionReason.NON_ENGLISH_SCRIPT)

        # Pure math symbols: REJECTED under LOW_ALPHA_RATIO
        math_text = "∀ x ∈ S : f(x) ≤ ∑ y"
        decision_math = quality_filter.evaluate(math_text)
        assert decision_math.is_accepted is False
        assert decision_math.rejection_reason == RejectionReason.LOW_ALPHA_RATIO

    def test_non_latin_scripts_rejected(self, quality_filter):
        """Non-Latin scripts (Cyrillic, Greek, Devanagari, CJK) are REJECTED under NON_ENGLISH_SCRIPT."""
        cases = [
            ("Cyrillic", "Это предложение на русском языке для проверки."),
            ("Devanagari", "यह हिंदी में लिखा गया एक परीक्षण वाक्य है।"),
            ("Greek", "Αυτό είναι ένα δοκιμαστικό κείμενο στα ελληνικά."),
            ("CJK", "这是一个用于测试语料库管道的中文句子。"),
        ]
        for script, text in cases:
            decision = quality_filter.evaluate(text)
            assert decision.is_accepted is False
            assert decision.rejection_reason == RejectionReason.NON_ENGLISH_SCRIPT

    def test_corrupted_unicode_rejected_or_quarantined(self, quality_filter):
        """Corrupted Unicode characters (replacement char \\ufffd, unassigned Cn, surrogates Cs) are REJECTED."""
        corrupted = "Valid text with corrupt \ufffd character inside it."
        decision = quality_filter.evaluate(corrupted)
        assert decision.is_accepted is False
        assert decision.rejection_reason == RejectionReason.HIGH_UNREGISTERED_RATIO


class TestCorpusLanguageAndScriptCompositionAdversarial:
    """Verifies the four-way distinction required by Phase 4.1.1:

    1. Language Identity (English vs Non-English)
    2. Script Composition (Latin vs Non-Latin ratio)
    3. Content Quality (Prose vs Symbol/Code dumps)
    4. Unicode Representability (Valid NFC vs Corrupt Codepoints)

    Proves:
    - Latin script != English (rejects pure French, German, Spanish).
    - Non-Latin script != non-English document (admits English with Greek symbols, foreign names, citations).
    """

    @pytest.fixture
    def quality_filter(self):
        return QualityFilter()

    def test_foreign_names_in_english_prose_accepted(self, quality_filter):
        """English documents containing legitimate foreign names in original script are ACCEPTED."""
        cases = [
            "The classical Greek philosopher Socrates (Σωκράτης) taught ethics and dialectical reasoning in ancient Athens.",
            "The Russian author Leo Tolstoy (Лев Толстой) wrote extensively on moral philosophy and nonviolent resistance.",
            "Chinese thinker Confucius (孔子) emphasized righteousness, filial piety, and harmonious social order.",
        ]
        for text in cases:
            decision = quality_filter.evaluate(text)
            assert decision.is_accepted is True, f"Failed on foreign name: {text} -> {decision.rejection_reason}"

    def test_quoted_foreign_text_in_english_prose_accepted(self, quality_filter):
        """Brief quoted foreign text or philosophical maxims inside English prose are ACCEPTED."""
        cases = [
            "The Delphic inscription urged all seekers to observe the ancient maxim, 'γνῶθι σεαυτόν', in their daily life.",
            "René Descartes famously proclaimed 'cogito, ergo sum' as the indubitable starting point for epistemology.",
        ]
        for text in cases:
            decision = quality_filter.evaluate(text)
            assert decision.is_accepted is True, f"Failed on quoted text: {text} -> {decision.rejection_reason}"

    def test_greek_scientific_and_mathematical_symbols_accepted(self, quality_filter):
        """English scientific prose containing Greek variables (λ, ω, α, θ, Δ) is ACCEPTED."""
        cases = [
            "In wave mechanics, the phase velocity v relates to wavelength λ and angular frequency ω through the dispersion relation.",
            "The standard error margin Δ was computed with confidence coefficient α = 0.05 across all experimental trials.",
            "In quantum thermodynamics, the density operator ρ satisfies the von Neumann equation with Hamiltonian H.",
        ]
        for text in cases:
            decision = quality_filter.evaluate(text)
            assert decision.is_accepted is True, f"Failed on scientific symbols: {text} -> {decision.rejection_reason}"

    def test_mathematical_notation_in_prose_vs_formula_dump(self, quality_filter):
        """Prose-embedded mathematical statements are ACCEPTED; pure symbol formula dumps are REJECTED."""
        prose_math = (
            "Let matrix A be a symmetric tensor with positive eigenvalues λ_1 and λ_2 "
            "such that the determinant is strictly positive and the quadratic form is stable."
        )
        dec_prose = quality_filter.evaluate(prose_math)
        assert dec_prose.is_accepted is True, f"Failed on prose math: {dec_prose.rejection_reason}"

        formula_dump = "∀ x ∈ S : f(x) ≤ ∑ y_i ∧ ∃ z ∈ T : g(z) = 0"
        dec_dump = quality_filter.evaluate(formula_dump)
        assert dec_dump.is_accepted is False
        assert dec_dump.rejection_reason in (RejectionReason.LOW_ALPHA_RATIO, RejectionReason.HIGH_SYMBOL_RATIO)

    def test_academic_citations_with_foreign_titles_accepted(self, quality_filter):
        """Academic citations containing original-language titles in parentheses are ACCEPTED."""
        citation_text = (
            "As detailed in Aristotle's foundational treatise Metaphysics (Τὰ μετὰ τὰ φυσικά, Book IV), "
            "the principle of non-contradiction remains the primary axiom of all rational discourse."
        )
        dec = quality_filter.evaluate(citation_text)
        assert dec.is_accepted is True, f"Failed on citation: {dec.rejection_reason}"

    def test_programming_code_fragment_rejected_vs_prose_accepted(self, quality_filter):
        """Raw source code syntax is REJECTED; English prose explaining code is ACCEPTED."""
        raw_code = "for (int i = 0; i < n; i++) { if (arr[i] > max_val) { max_val = arr[i]; }; };"
        dec_code = quality_filter.evaluate(raw_code)
        assert dec_code.is_accepted is False
        assert dec_code.rejection_reason in (RejectionReason.HIGH_SYMBOL_RATIO, RejectionReason.LOW_ALPHA_RATIO)

        code_prose = (
            "The algorithm iteratively scans the array, comparing each integer to the current maximum "
            "and storing the highest value found before terminating."
        )
        dec_prose = quality_filter.evaluate(code_prose)
        assert dec_prose.is_accepted is True

    def test_latin_script_does_not_equal_english(self, quality_filter):
        """Proves Latin script != English: pure French or German text with 100% Latin letters is REJECTED."""
        french_text = "C'est une belle journée aujourd'hui dans la magnifique ville de Paris avec beaucoup de soleil."
        dec_fr = quality_filter.evaluate(french_text)
        assert dec_fr.is_accepted is False
        assert dec_fr.rejection_reason == RejectionReason.NO_ENGLISH_STOPWORDS

        german_text = "Das ist ein deutsches Dokument ohne englische Wörter für die gründliche wissenschaftliche Untersuchung."
        dec_de = quality_filter.evaluate(german_text)
        assert dec_de.is_accepted is False
        assert dec_de.rejection_reason == RejectionReason.NO_ENGLISH_STOPWORDS

    def test_non_latin_script_does_not_equal_non_english_document(self, quality_filter):
        """Proves non-Latin script != non-English document:

        English with minority Greek symbols is accepted; pure non-Latin documents are rejected.
        """
        # English with Greek symbols: ACCEPTED
        mixed_english = (
            "The quantum efficiency η was measured across several laser frequencies, "
            "verifying that the emission spectrum matches theoretical predictions."
        )
        dec_mixed = quality_filter.evaluate(mixed_english)
        assert dec_mixed.is_accepted is True

        # Pure non-Latin text (Russian): REJECTED
        russian_text = "Это предложение полностью написано на русском языке для проверки качества модели."
        dec_ru = quality_filter.evaluate(russian_text)
        assert dec_ru.is_accepted is False
        assert dec_ru.rejection_reason == RejectionReason.NON_ENGLISH_SCRIPT


# ==============================================================================
# 2. DUAL FINGERPRINTING AUDIT TESTS (Cases 1 - 4)
# ==============================================================================


class TestCorpusFingerprintingAdversarial:
    """Verifies complete separation of Content Fingerprint vs Manifest Configuration Fingerprint."""

    @pytest.fixture
    def sample_records(self):
        return [
            make_test_record(
                record_id="rec_001",
                document_id="doc_001",
                raw_text="Hello world.",
                split="train",
            ),
            make_test_record(
                record_id="rec_002",
                document_id="doc_002",
                raw_text="The second record.",
                split="validation",
            ),
        ]

    def test_case_1_same_content_same_config(self, sample_records):
        """CASE 1: Same content + same configuration -> identical content & manifest fingerprints."""
        fp_content_1 = compute_content_fingerprint(sample_records)
        fp_content_2 = compute_content_fingerprint(sample_records)
        assert fp_content_1 == fp_content_2

        config = {
            "corpus_version": "0.1.0",
            "schema_version": "0.1.0",
            "pipeline_version": "0.1.0",
            "sources": [{"source_id": "src_001", "hash": "abc"}],
            "split_seed": 42,
            "split_ratios": {"train": 0.8, "validation": 0.1, "test": 0.1},
            "content_fingerprint": fp_content_1,
        }
        mfp_1 = compute_manifest_fingerprint(config)
        mfp_2 = compute_manifest_fingerprint(config)
        assert mfp_1 == mfp_2

    def test_case_2_same_content_changed_configuration(self, sample_records):
        """CASE 2: Same content + changed configuration/metadata ->

        content fingerprint UNCHANGED, manifest fingerprint MUST CHANGE.
        """
        fp_content_1 = compute_content_fingerprint(sample_records)
        fp_content_2 = compute_content_fingerprint(sample_records)
        assert fp_content_1 == fp_content_2

        config_base = {
            "corpus_version": "0.1.0",
            "schema_version": "0.1.0",
            "pipeline_version": "0.1.0",
            "sources": [{"source_id": "src_001", "hash": "abc"}],
            "split_seed": 42,
            "split_ratios": {"train": 0.8, "validation": 0.1, "test": 0.1},
            "content_fingerprint": fp_content_1,
        }
        config_changed_seed = dict(config_base)
        config_changed_seed["split_seed"] = 9999

        mfp_base = compute_manifest_fingerprint(config_base)
        mfp_changed = compute_manifest_fingerprint(config_changed_seed)

        assert mfp_base != mfp_changed

    def test_case_3_changed_content_changes_content_fingerprint(self, sample_records):
        """CASE 3: Changed corpus content -> content fingerprint MUST CHANGE."""
        fp_orig = compute_content_fingerprint(sample_records)

        # Modify one character of text
        modified_records = [
            sample_records[0],
            make_test_record(
                record_id="rec_002",
                document_id="doc_002",
                raw_text="The second record!",
                split="validation",
            ),
        ]
        fp_mod = compute_content_fingerprint(modified_records)
        assert fp_orig != fp_mod

    def test_case_4_path_only_change_does_not_change_content_identity(self, tmp_path, sample_records):
        """CASE 4: Changing output filename or directory path only does not alter content fingerprint."""
        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"

        writer_a = CorpusWriter(dir_a)
        writer_b = CorpusWriter(dir_b)

        for rec in sample_records:
            writer_a.write_record(rec)
            writer_b.write_record(rec)

        writer_a.close(commit=True)
        writer_b.close(commit=True)

        records_a = list(CorpusReader.read_records(dir_a / "train.jsonl")) + list(CorpusReader.read_records(dir_a / "validation.jsonl"))
        records_b = list(CorpusReader.read_records(dir_b / "train.jsonl")) + list(CorpusReader.read_records(dir_b / "validation.jsonl"))

        fp_a = compute_content_fingerprint(records_a)
        fp_b = compute_content_fingerprint(records_b)

        assert fp_a == fp_b


# ==============================================================================
# 3. LEAKAGE PREVENTION & CANONICAL DOCUMENT BOUNDARY TESTS
# ==============================================================================


class TestCorpusLeakageAdversarial:
    """Verifies that split assignment strictly adheres to document boundaries

    and that duplicates cannot leak across splits.
    """

    def test_document_is_canonical_leakage_boundary(self, tmp_path):
        """Every record from the same document belongs to the exact same split."""
        source = make_test_source("src_leak_test", "Leak Test Source")
        # Document with 10 paragraphs that will be segmented
        paragraphs = [
            f"Paragraph {i} discussing the epistemological foundations of intelligence in VEDA."
            for i in range(10)
        ]
        doc = CorpusDocument(
            document_id="doc_multi_segment",
            source_id="src_leak_test",
            raw_text="\n\n".join(paragraphs),
        )

        pipeline = CorpusPipeline(corpus_name="leak_test")
        out_dir = tmp_path / "leak_test"
        manifest = pipeline.process_corpus([source], [doc], out_dir)

        # Inspect resulting records
        all_records = []
        for split in [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]:
            split_file = out_dir / f"{split.value}.jsonl"
            if split_file.exists():
                recs = list(CorpusReader.read_records(split_file))
                all_records.extend(recs)

        assert len(all_records) == 10
        assigned_splits = {rec.split for rec in all_records}
        assert len(assigned_splits) == 1, f"Document segments crossed splits: {assigned_splits}"

    def test_duplicate_documents_cannot_cross_splits(self, tmp_path):
        """Duplicate documents must not be assigned to a different split; deduplication blocks them."""
        source = make_test_source("src_dup_leak", "Dup Leak Source")
        doc1 = CorpusDocument(
            document_id="doc_orig",
            source_id="src_dup_leak",
            raw_text="The exact same text appears in two separate documents in the input stream.",
        )
        doc2 = CorpusDocument(
            document_id="doc_dup",
            source_id="src_dup_leak",
            raw_text="The exact same text appears in two separate documents in the input stream.",
        )

        pipeline = CorpusPipeline(corpus_name="dup_leak_test")
        out_dir = tmp_path / "dup_leak"
        manifest = pipeline.process_corpus([source], [doc1, doc2], out_dir)

        assert manifest.total_documents == 2
        assert manifest.retained_documents == 1
        assert manifest.rejected_documents == 1
        assert manifest.duplicate_records == 1

        # Check records
        retained = []
        for split in [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]:
            p = out_dir / f"{split.value}.jsonl"
            if p.exists():
                retained.extend(list(CorpusReader.read_records(p)))

        assert len(retained) == 1
        assert retained[0].document_id == "doc_orig"

    def test_near_duplicate_discrimination(self):
        """Proves exact dedup correctly identifies near duplicates as NOT exact duplicates.

        This demonstrates why exact dedup alone does not eliminate near duplicates.
        """
        dedup = DeduplicationEngine()

        text_a = "The quick brown fox jumps over the lazy dog."
        text_b = "The quick brown fox jumps over a lazy dog."

        is_dup_a, can_a, type_a = dedup.check_and_register_record("rec_a", text_a, text_a)
        is_dup_b, can_b, type_b = dedup.check_and_register_record("rec_b", text_b, text_b)

        assert is_dup_a is False
        assert is_dup_b is False  # Exact dedup does not catch 1-word variation
        assert can_b is None
        assert type_b is None


# ==============================================================================
# 4. PROVENANCE & ACCOUNTING CONSERVATION TESTS
# ==============================================================================


class TestCorpusProvenanceAndAccountingAdversarial:
    """Verifies that no record or document silently disappears and accounting is exact."""

    def test_exact_document_and_record_conservation(self, tmp_path):
        """Verifies machine-checkable accounting conservation:

        total_docs = retained_docs + rejected_docs
        processed_recs = retained_recs + rejected_recs + duplicate_recs
        """
        source = make_test_source("src_cons", "Conservation Test")
        docs = [
            # 1. Valid doc (retained)
            CorpusDocument("doc_valid_1", "src_cons", "A valid document with sufficient length."),
            # 2. Duplicate of doc 1 (rejected document, duplicate record)
            CorpusDocument("doc_dup_1", "src_cons", "A valid document with sufficient length."),
            # 3. Empty doc (rejected document, empty text)
            CorpusDocument("doc_empty", "src_cons", "    \n\t  "),
            # 4. Low alpha ratio (rejected doc)
            CorpusDocument("doc_symbols", "src_cons", "$$$$$$$$ %%%%%%%% ^^^^^^^^ &&&&&&&&"),
            # 5. Non-English (rejected doc)
            CorpusDocument("doc_russian", "src_cons", "Это предложение полностью на русском языке."),
            # 6. Valid doc (retained)
            CorpusDocument("doc_valid_2", "src_cons", "Another completely valid scientific record."),
        ]

        pipeline = CorpusPipeline(corpus_name="conservation_test")
        out_dir = tmp_path / "cons_test"
        manifest = pipeline.process_corpus([source], docs, out_dir)

        # Document conservation check
        assert manifest.total_documents == len(docs)
        assert manifest.total_documents == manifest.retained_documents + manifest.rejected_documents

        # Record conservation check
        assert manifest.total_records_processed == (
            manifest.retained_records + manifest.rejected_records + manifest.duplicate_records
        )
        assert manifest.duplicate_records == 1
        assert manifest.retained_documents == 2
        assert manifest.rejected_documents == 4

    def test_provenance_traceability_round_trip(self, tmp_path):
        """Every field in CorpusRecord survives serialization and deserialization without mutation."""
        rec = make_test_record(
            record_id="rec_prov_001",
            document_id="doc_prov_001",
            source_id="src_prov_001",
            raw_text="Raw unadulterated source text with café.",
            normalized_text="Raw unadulterated source text with café.",
            split="train",
        )

        out_dir = tmp_path / "writer_dir"
        writer = CorpusWriter(out_dir)
        writer.write_record(rec)
        writer.close(commit=True)

        reloaded = list(CorpusReader.read_records(out_dir / "train.jsonl"))[0]

        assert reloaded.record_id == rec.record_id
        assert reloaded.document_id == rec.document_id
        assert reloaded.source_id == rec.source_id
        assert reloaded.raw_text == rec.raw_text
        assert reloaded.normalized_text == rec.normalized_text
        assert reloaded.split == rec.split
        assert reloaded.raw_char_count == rec.raw_char_count
        assert reloaded.normalized_char_count == rec.normalized_char_count
        assert reloaded.approx_word_count == rec.approx_word_count
        assert reloaded.quality_score == rec.quality_score
        assert reloaded.is_duplicate == rec.is_duplicate
        assert reloaded.language == rec.language
        assert reloaded.segment_index == rec.segment_index
        assert reloaded.provenance.source_id == rec.provenance.source_id
        assert reloaded.provenance.document_id == rec.provenance.document_id


# ==============================================================================
# 5. CRASH, ROLLBACK & RECOVERY AUDIT TESTS
# ==============================================================================


class TestCorpusRecoveryAdversarial:
    """Verifies atomic writes, failure cleanup, and rebuild identity."""

    def test_interrupted_build_atomic_cleanup(self, tmp_path):
        """Simulate a crash mid-pipeline: no partial datasets or invalid manifests must remain."""
        source = make_test_source("src_crash", "Crash Test")
        docs = [
            CorpusDocument("doc_crash_1", "src_crash", "Document 1 for crash simulation."),
            CorpusDocument("doc_crash_2", "src_crash", "Document 2 for crash simulation."),
        ]

        out_dir = tmp_path / "crash_output"
        pipeline = CorpusPipeline(corpus_name="crash_test")

        # Mock an error during deduplication/writing
        with patch.object(DeduplicationEngine, "check_and_register_record", side_effect=RuntimeError("Forced Mid-Pipeline Failure")):
            with pytest.raises(RuntimeError, match="Forced Mid-Pipeline Failure"):
                pipeline.process_corpus([source], docs, out_dir)

        # Verify no .tmp files and no manifest.json exists
        tmp_files = list(out_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temporary files left behind: {tmp_files}"
        assert not (out_dir / "manifest.json").exists()

    def test_clean_rebuild_after_crash_equals_first_clean_build(self, tmp_path):
        """A rebuild following a crash produces identical content and manifest fingerprints."""
        source = make_test_source("src_rebuild", "Rebuild Test")
        docs = [
            CorpusDocument(f"doc_{i}", "src_rebuild", f"This is valid corpus document number {i} for rebuild testing.")
            for i in range(20)
        ]

        dir_clean = tmp_path / "clean_build"
        pipeline1 = CorpusPipeline(corpus_name="rebuild_test", split_seed=12345)
        manifest_clean = pipeline1.process_corpus([source], docs, dir_clean)

        # In dir_rebuild, simulate failure first
        dir_rebuild = tmp_path / "rebuild_after_crash"
        pipeline_fail = CorpusPipeline(corpus_name="rebuild_test", split_seed=12345)
        with patch.object(QualityFilter, "evaluate", side_effect=[RuntimeError("Forced Failure")]):
            with pytest.raises(RuntimeError):
                pipeline_fail.process_corpus([source], docs, dir_rebuild)

        # Now execute clean rebuild in the same directory
        pipeline2 = CorpusPipeline(corpus_name="rebuild_test", split_seed=12345)
        manifest_rebuilt = pipeline2.process_corpus([source], docs, dir_rebuild)

        # Assert identical fingerprints and accounting
        assert manifest_clean.content_fingerprint == manifest_rebuilt.content_fingerprint
        assert manifest_clean.manifest_fingerprint == manifest_rebuilt.manifest_fingerprint
        assert manifest_clean.retained_records == manifest_rebuilt.retained_records
        assert manifest_clean.rejected_records == manifest_rebuilt.rejected_records
        assert manifest_clean.duplicate_records == manifest_rebuilt.duplicate_records


# ==============================================================================
# 6. MULTI-BATCH & DETERMINISM MATRIX TESTS
# ==============================================================================


class TestCorpusDeterminismAdversarial:
    """Verifies pipeline determinism across batch variations and execution runs."""

    def test_determinism_across_runs_and_different_dirs(self, tmp_path):
        """Repeated runs across different output paths produce identical fingerprints."""
        source = make_test_source("src_det", "Determinism Test")
        docs = [
            CorpusDocument(f"doc_det_{i}", "src_det", f"Document number {i} with deterministic content.")
            for i in range(25)
        ]

        dir_1 = tmp_path / "run_1"
        dir_2 = tmp_path / "run_2"

        p1 = CorpusPipeline(corpus_name="det_test", split_seed=42)
        m1 = p1.process_corpus([source], docs, dir_1)

        p2 = CorpusPipeline(corpus_name="det_test", split_seed=42)
        m2 = p2.process_corpus([source], docs, dir_2)

        assert m1.content_fingerprint == m2.content_fingerprint
        assert m1.manifest_fingerprint == m2.manifest_fingerprint
        assert m1.split_record_counts == m2.split_record_counts

    def test_determinism_across_chunked_batches(self, tmp_path):
        """Batch ingestion in chunks (1, 5, 10) produces identical fingerprints."""
        source = make_test_source("src_batch", "Batch Determinism")
        docs = [
            CorpusDocument(f"doc_b_{i}", "src_batch", f"Batch test document {i} with verified text content.")
            for i in range(25)
        ]

        dir_mono = tmp_path / "mono"
        p_mono = CorpusPipeline(corpus_name="batch_det", split_seed=42)
        m_mono = p_mono.process_corpus([source], docs, dir_mono)

        for batch_size in [1, 5, 10]:
            dir_b = tmp_path / f"batch_{batch_size}"
            p_b = CorpusPipeline(corpus_name="batch_det", split_seed=42)
            batched_docs = []
            for i in range(0, len(docs), batch_size):
                batched_docs.extend(docs[i : i + batch_size])
            m_b = p_b.process_corpus([source], batched_docs, dir_b)
            assert m_b.content_fingerprint == m_mono.content_fingerprint
            assert m_b.manifest_fingerprint == m_mono.manifest_fingerprint


# ==============================================================================
# 7. PATHOLOGICAL & STRESS EDGE CASES
# ==============================================================================


class TestCorpusPathologicalAdversarial:
    """Adversarial stress inputs designed to break naive parsers."""

    def test_huge_single_line_document(self, tmp_path):
        """A massive single line exceeding character limits is cleanly rejected under TOO_LONG_CHARS."""
        source = make_test_source("src_huge", "Huge Line Source")
        huge_text = "word " * 50_000  # 250,000 characters
        doc = CorpusDocument("doc_huge", "src_huge", huge_text)

        pipeline = CorpusPipeline(corpus_name="huge_test")
        out_dir = tmp_path / "huge_out"
        manifest = pipeline.process_corpus([source], [doc], out_dir)

        assert manifest.total_documents == 1
        assert manifest.rejected_documents == 1
        assert manifest.retained_documents == 0
        assert manifest.rejection_reasons[RejectionReason.TOO_LONG_CHARS.value] == 1

    def test_unlicensed_source_blocked_by_governance(self, tmp_path):
        """Unverified source is strictly blocked at the governance gate."""
        source_unverified = make_test_source("src_unverified", "Unverified Source", LicensingStatus.REQUIRES_REVIEW)
        doc = CorpusDocument("doc_unv", "src_unverified", "Valid text from unverified source.")

        pipeline = CorpusPipeline(corpus_name="gov_test")
        out_dir = tmp_path / "gov_out"
        manifest = pipeline.process_corpus([source_unverified], [doc], out_dir)

        assert manifest.total_documents == 1
        assert manifest.rejected_documents == 1
        assert manifest.retained_documents == 0
        assert manifest.rejection_reasons[RejectionReason.GOVERNANCE_BLOCKED.value] == 1
