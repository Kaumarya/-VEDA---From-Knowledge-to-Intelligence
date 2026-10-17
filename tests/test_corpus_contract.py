"""
VEDA Corpus Data Contract & Schema Tests (Phase 4 — Training Corpus Architecture)

Validates schema constraints, field types, nullability, validation logic,
round-trip serialization, and governance gates across all six conceptual layers.
"""

import pytest

from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusRecord,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
    RecordProvenance,
    RejectionReason,
    RejectionRecord,
    Sentence,
    TextSegment,
)


class TestCorpusSourceContract:
    """Tests for CorpusSource data model and governance rules."""

    def test_valid_source_creation(self):
        source = CorpusSource(
            source_id="gutenberg_essays",
            name="Project Gutenberg Essays",
            version="2026.09",
            url_or_path="https://gutenberg.org/essays.zip",
            acquisition_date="2026-09-30",
            source_hash="a" * 64,
            license="Public Domain",
            licensing_status=LicensingStatus.VERIFIED_PERMITTED,
        )
        assert source.source_id == "gutenberg_essays"
        assert source.is_permitted_for_training is True

        # Round-trip serialization
        data = source.to_dict()
        reconstructed = CorpusSource.from_dict(data)
        assert reconstructed == source

    def test_source_id_validation(self):
        with pytest.raises(ValueError, match="Invalid source_id"):
            CorpusSource(
                source_id="Invalid Source ID!",
                name="Bad Source",
                version="1.0",
                url_or_path="/path",
                acquisition_date="2026-01-01",
                source_hash="a" * 64,
                license="MIT",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

    def test_source_hash_validation(self):
        with pytest.raises(ValueError, match="source_hash must be a valid 64-char hex"):
            CorpusSource(
                source_id="bad_hash_source",
                name="Bad Hash",
                version="1.0",
                url_or_path="/path",
                acquisition_date="2026-01-01",
                source_hash="not_a_sha256_hash",
                license="MIT",
                licensing_status=LicensingStatus.VERIFIED_PERMITTED,
            )

    def test_licensing_governance_gate(self):
        source_unknown = CorpusSource(
            source_id="unknown_src",
            name="Unknown License",
            version="1.0",
            url_or_path="/path",
            acquisition_date="2026-01-01",
            source_hash="b" * 64,
            license="Custom",
            licensing_status=LicensingStatus.UNKNOWN,
        )
        assert source_unknown.is_permitted_for_training is False

        source_excluded = CorpusSource(
            source_id="excluded_src",
            name="Proprietary",
            version="1.0",
            url_or_path="/path",
            acquisition_date="2026-01-01",
            source_hash="c" * 64,
            license="Proprietary",
            licensing_status=LicensingStatus.EXCLUDED,
        )
        assert source_excluded.is_permitted_for_training is False


class TestCorpusDocumentContract:
    """Tests for CorpusDocument schema and cryptographic hashing."""

    def test_document_creation_and_hash(self):
        text = "This is a clean English paragraph for document testing."
        doc = CorpusDocument(
            document_id="doc_test_01",
            source_id="gutenberg_essays",
            raw_text=text,
            title="Test Doc",
            author="Author",
        )
        assert doc.raw_char_count == len(text)
        assert len(doc.document_hash) == 64

        data = doc.to_dict()
        reconstructed = CorpusDocument.from_dict(data)
        assert reconstructed.document_id == doc.document_id
        assert reconstructed.raw_char_count == doc.raw_char_count
        assert reconstructed.document_hash == doc.document_hash

    def test_empty_document_id_rejected(self):
        with pytest.raises(ValueError, match="document_id must not be empty"):
            CorpusDocument(document_id="", source_id="src1", raw_text="Valid text")


class TestTextSegmentAndSentenceContract:
    """Tests for structural segmentation layers."""

    def test_text_segment_valid_offsets(self):
        seg = TextSegment(
            segment_id="doc1:s0",
            document_id="doc1",
            segment_index=0,
            raw_text="Sample segment.",
            start_char_offset=0,
            end_char_offset=15,
            segment_type="paragraph",
        )
        assert seg.segment_id == "doc1:s0"
        assert seg.to_dict()["end_char_offset"] == 15

    def test_text_segment_invalid_offsets(self):
        with pytest.raises(ValueError, match="Invalid offsets"):
            TextSegment(
                segment_id="doc1:s0",
                document_id="doc1",
                segment_index=0,
                raw_text="Sample",
                start_char_offset=20,
                end_char_offset=10,  # end < start
            )

    def test_sentence_contract(self):
        sent = Sentence(
            sentence_id="doc1:s0:sent0",
            segment_id="doc1:s0",
            sentence_index=0,
            raw_text="Sample sentence.",
            start_char_offset=0,
            end_char_offset=16,
        )
        assert sent.to_dict()["raw_text"] == "Sample sentence."


class TestCorpusRecordContract:
    """Tests for canonical CorpusRecord contract rules."""

    def test_valid_corpus_record(self):
        prov = RecordProvenance(
            source_id="src1",
            document_id="doc1",
            segment_index=0,
            start_char_offset=0,
            end_char_offset=27,
        )
        record = CorpusRecord(
            record_id="rec_001",
            document_id="doc1",
            source_id="src1",
            segment_index=0,
            raw_text="A quick brown fox jumps.",
            normalized_text="A quick brown fox jumps.",
            raw_char_count=24,
            normalized_char_count=24,
            approx_word_count=5,
            quality_score=0.95,
            is_duplicate=False,
            split="train",
            corpus_version="0.1.0",
            provenance=prov,
        )
        assert record.record_id == "rec_001"

        data = record.to_dict()
        reconstructed = CorpusRecord.from_dict(data)
        assert reconstructed.record_id == record.record_id
        assert reconstructed.raw_char_count == record.raw_char_count
        assert reconstructed.split == record.split
        assert reconstructed.provenance.source_id == "src1"

    def test_length_mismatch_validation(self):
        prov = RecordProvenance("src1", "doc1", 0, 0, 10)
        with pytest.raises(ValueError, match="raw_char_count"):
            CorpusRecord(
                record_id="rec_002",
                document_id="doc1",
                source_id="src1",
                segment_index=0,
                raw_text="Hello",
                normalized_text="Hello",
                raw_char_count=999,  # Deliberate mismatch
                normalized_char_count=5,
                approx_word_count=1,
                quality_score=0.9,
                is_duplicate=False,
                split="train",
                corpus_version="0.1.0",
                provenance=prov,
            )

    def test_invalid_split_name(self):
        prov = RecordProvenance("src1", "doc1", 0, 0, 5)
        with pytest.raises(ValueError, match="Invalid split"):
            CorpusRecord(
                record_id="rec_003",
                document_id="doc1",
                source_id="src1",
                segment_index=0,
                raw_text="Hello",
                normalized_text="Hello",
                raw_char_count=5,
                normalized_char_count=5,
                approx_word_count=1,
                quality_score=0.9,
                is_duplicate=False,
                split="invalid_split",
                corpus_version="0.1.0",
                provenance=prov,
            )

    def test_duplicate_record_contract(self):
        prov = RecordProvenance("src1", "doc1", 0, 0, 5)
        # Duplicate without duplicate_of_id must fail
        with pytest.raises(ValueError, match="duplicate_of_id must be populated"):
            CorpusRecord(
                record_id="rec_004",
                document_id="doc1",
                source_id="src1",
                segment_index=0,
                raw_text="Hello",
                normalized_text="Hello",
                raw_char_count=5,
                normalized_char_count=5,
                approx_word_count=1,
                quality_score=0.9,
                is_duplicate=True,
                duplicate_of_id=None,
                split="train",
                corpus_version="0.1.0",
                provenance=prov,
            )


class TestRejectionRecordContract:
    """Tests for RejectionRecord ledger tracking."""

    def test_rejection_record_serialization(self):
        rej = RejectionRecord(
            record_id="doc1:s0",
            document_id="doc1",
            source_id="src1",
            rejection_reason=RejectionReason.TOO_SHORT_CHARS,
            rejection_stage="filtering",
            raw_text_sample="Hi.",
            metric_name="char_length",
            metric_value=3.0,
            threshold_value=25.0,
        )
        d = rej.to_dict()
        assert d["rejection_reason"] == "TOO_SHORT_CHARS"
        assert d["metric_name"] == "char_length"
        assert d["threshold_value"] == 25.0
