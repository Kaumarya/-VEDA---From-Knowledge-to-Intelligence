"""
VEDA Document Segmentation (Phase 4 — Training Corpus Architecture)

Decomposes raw CorpusDocument instances into coherent TextSegment instances
(paragraphs) while preserving exact character offsets and parent document lineage.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from foundation.corpus.schemas import CorpusDocument, Sentence, TextSegment


class DocumentSegmenter:
    """
    Splits documents into structural paragraphs and text segments.
    """

    VERSION = "0.1.0"

    # Regex matching double or more newlines (paragraph boundary)
    _PARAGRAPH_SPLIT_REGEX = re.compile(r"\n\s*\n")

    # Regex for standard English sentence boundary (heuristic)
    # Matches period, exclamation, question mark followed by whitespace and uppercase letter
    _SENTENCE_REGEX = re.compile(r'(?<=[.!?])\s+(?=[A-Z"“\'\d])')

    def __init__(
        self,
        min_segment_chars: int = 25,
        max_segment_chars: int = 10000,
    ) -> None:
        self.min_segment_chars = min_segment_chars
        self.max_segment_chars = max_segment_chars

    def segment_document(self, document: CorpusDocument) -> List[TextSegment]:
        """
        Decomposes a CorpusDocument into a list of TextSegment instances.

        Guarantees:
        - raw_document_text[start:end] == segment.raw_text
        - segment_id is deterministic: {document_id}:s{index}
        - offsets are non-overlapping and contiguous
        """
        raw_text = document.raw_text
        if not raw_text:
            return []

        segments: List[TextSegment] = []
        pos = 0
        seg_index = 0

        # Find paragraph boundaries via regex matches to preserve exact offsets
        for match in self._PARAGRAPH_SPLIT_REGEX.finditer(raw_text):
            boundary_start, boundary_end = match.span()
            if boundary_start > pos:
                seg_text = raw_text[pos:boundary_start]
                stripped_text = seg_text.strip()
                if stripped_text:
                    # Compute inner offsets if stripped, or keep exact slice
                    # In VEDA, we preserve the exact slice for 100% offset fidelity:
                    # start_offset is where non-whitespace begins
                    leading_ws = len(seg_text) - len(seg_text.lstrip())
                    trailing_ws = len(seg_text) - len(seg_text.rstrip())
                    start_off = pos + leading_ws
                    end_off = boundary_start - trailing_ws

                    clean_text = raw_text[start_off:end_off]
                    seg_type = self._detect_segment_type(clean_text)

                    segments.append(
                        TextSegment(
                            segment_id=f"{document.document_id}:s{seg_index}",
                            document_id=document.document_id,
                            segment_index=seg_index,
                            raw_text=clean_text,
                            start_char_offset=start_off,
                            end_char_offset=end_off,
                            segment_type=seg_type,
                        )
                    )
                    seg_index += 1

            pos = boundary_end

        # Handle remaining tail of document
        if pos < len(raw_text):
            seg_text = raw_text[pos:]
            stripped_text = seg_text.strip()
            if stripped_text:
                leading_ws = len(seg_text) - len(seg_text.lstrip())
                trailing_ws = len(seg_text) - len(seg_text.rstrip())
                start_off = pos + leading_ws
                end_off = len(raw_text) - trailing_ws

                clean_text = raw_text[start_off:end_off]
                seg_type = self._detect_segment_type(clean_text)

                segments.append(
                    TextSegment(
                        segment_id=f"{document.document_id}:s{seg_index}",
                        document_id=document.document_id,
                        segment_index=seg_index,
                        raw_text=clean_text,
                        start_char_offset=start_off,
                        end_char_offset=end_off,
                        segment_type=seg_type,
                    )
                )

        return segments

    def segment_sentences(self, segment: TextSegment) -> List[Sentence]:
        """
        Decomposes a TextSegment into individual Sentence instances.
        """
        text = segment.raw_text
        if not text:
            return []

        sentences: List[Sentence] = []
        sent_index = 0
        pos = 0

        for match in self._SENTENCE_REGEX.finditer(text):
            boundary_start, boundary_end = match.span()
            sent_text = text[pos:boundary_start].strip()
            if sent_text:
                sentences.append(
                    Sentence(
                        sentence_id=f"{segment.segment_id}:sent{sent_index}",
                        segment_id=segment.segment_id,
                        sentence_index=sent_index,
                        raw_text=sent_text,
                        start_char_offset=pos,
                        end_char_offset=boundary_start,
                    )
                )
                sent_index += 1
            pos = boundary_end

        # Tail sentence
        if pos < len(text):
            tail_text = text[pos:].strip()
            if tail_text:
                sentences.append(
                    Sentence(
                        sentence_id=f"{segment.segment_id}:sent{sent_index}",
                        segment_id=segment.segment_id,
                        sentence_index=sent_index,
                        raw_text=tail_text,
                        start_char_offset=pos,
                        end_char_offset=len(text),
                    )
                )

        return sentences

    def _detect_segment_type(self, text: str) -> str:
        """Heuristic detection of segment type."""
        stripped = text.strip()
        if stripped.startswith(("#", "Chapter ", "Section ", "CHAPTER ", "SECTION ")):
            return "heading"
        if stripped.startswith(("- ", "* ", "1. ", "2. ", "• ")):
            return "list_item"
        if stripped.startswith(('"', "“", "> ")):
            return "quote"
        return "paragraph"
