"""
VEDA Document Segmentation Tests (Phase 4 — Training Corpus Architecture)

Validates:
- Paragraph boundary identification via double newlines (\n\n)
- Character offset fidelity: raw_text[start:end] == segment.raw_text
- Heading, list, quote, and paragraph semantic type classification
- Sentence boundary segmentation
"""

from foundation.corpus.schemas import CorpusDocument
from foundation.corpus.segmentation import DocumentSegmenter


class TestDocumentSegmenter:
    """Test suite for DocumentSegmenter."""

    def setup_method(self):
        self.segmenter = DocumentSegmenter()

    def test_paragraph_segmentation_offsets_and_content(self):
        raw_doc_text = (
            "This is the first paragraph with complete English sentences.\n\n"
            "This is the second paragraph exploring empirical observations.\n\n"
            "Finally, the third paragraph concludes the brief exposition."
        )
        doc = CorpusDocument(
            document_id="doc_seg_01",
            source_id="test_src",
            raw_text=raw_doc_text,
        )

        segments = self.segmenter.segment_document(doc)
        assert len(segments) == 3

        for i, seg in enumerate(segments):
            assert seg.segment_index == i
            assert seg.document_id == "doc_seg_01"
            # Invariant: offset slice matches segment text
            sliced_text = raw_doc_text[seg.start_char_offset:seg.end_char_offset]
            assert sliced_text == seg.raw_text

        assert "first paragraph" in segments[0].raw_text
        assert "second paragraph" in segments[1].raw_text
        assert "third paragraph" in segments[2].raw_text

    def test_segment_type_classification(self):
        doc = CorpusDocument(
            document_id="doc_types",
            source_id="test_src",
            raw_text=(
                "# Chapter 1: Foundations\n\n"
                "- Item 1 in list\n\n"
                "“Quoted speech here,” said the author.\n\n"
                "Regular narrative prose paragraph."
            ),
        )
        segments = self.segmenter.segment_document(doc)
        assert len(segments) == 4
        assert segments[0].segment_type == "heading"
        assert segments[1].segment_type == "list_item"
        assert segments[2].segment_type == "quote"
        assert segments[3].segment_type == "paragraph"

    def test_sentence_segmentation(self):
        doc = CorpusDocument(
            document_id="doc_sents",
            source_id="test_src",
            raw_text="Dr. Watson arrived early. The game was afoot! Did you see the clue?",
        )
        segments = self.segmenter.segment_document(doc)
        assert len(segments) == 1

        sentences = self.segmenter.segment_sentences(segments[0])
        assert len(sentences) >= 2
        for sent in sentences:
            assert sent.segment_id == segments[0].segment_id
            assert len(sent.raw_text) > 0

    def test_empty_document_produces_empty_segments(self):
        doc = CorpusDocument(document_id="empty_doc", source_id="src1", raw_text="")
        assert self.segmenter.segment_document(doc) == []
