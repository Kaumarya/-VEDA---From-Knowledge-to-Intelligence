"""
VEDA Text Normalizer (Phase 4 — Training Corpus Architecture)

Implements the text normalization policy defined in docs/corpus_normalization_policy.md.
Executes deterministic, auditable transformations while preserving authentic capitalization,
registered typography, and linguistic structures.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class NormalizationResult:
    """Result of normalizing a raw text segment."""
    raw_text: str
    normalized_text: str
    is_modified: bool
    applied_transforms: List[str] = field(default_factory=list)


class TextNormalizer:
    """
    Deterministic, policy-driven text normalizer for VEDA training corpus.
    """

    VERSION = "0.1.0"

    # Control chars to strip: 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F
    _CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

    # HTML tags regex
    _HTML_TAG_REGEX = re.compile(r"<[^>]+>")

    # Ellipsis regex: 3 or more dots
    _ELLIPSIS_REGEX = re.compile(r"\.{3,}")

    # Double/triple hyphens in typography (Gutenberg dash convention: '--' -> '—')
    _DASH_CONVENTION_REGEX = re.compile(r"(?<=\S)--(?=\S)|(?<=\s)--(?=\s)|---")

    def __init__(
        self,
        strip_html: bool = True,
        standardize_dashes: bool = True,
        standardize_ellipsis: bool = True,
        collapse_whitespace: bool = True,
    ) -> None:
        self.strip_html = strip_html
        self.standardize_dashes = standardize_dashes
        self.standardize_ellipsis = standardize_ellipsis
        self.collapse_whitespace = collapse_whitespace

    def normalize(self, text: str) -> NormalizationResult:
        """
        Normalizes raw text in accordance with VEDA Corpus Normalization Policy.

        Guarantees:
        1. Original casing is strictly preserved.
        2. Unicode is normalized to NFC.
        3. Linebreaks are normalized to '\\n'.
        4. Control characters and null bytes are removed.
        5. Registered typographical characters (‘’, “”, –, —, …) are preserved.
        """
        if not isinstance(text, str):
            raise TypeError(f"TextNormalizer.normalize expects a string, got {type(text).__name__}")

        if not text:
            return NormalizationResult(raw_text=text, normalized_text="", is_modified=False)

        current = text
        applied: List[str] = []

        # 1. HTML Entity Decoding
        decoded = html.unescape(current)
        if decoded != current:
            applied.append("html_unescape")
            current = decoded

        # 2. HTML Tag Stripping (if enabled)
        if self.strip_html and "<" in current and ">" in current:
            stripped = self._HTML_TAG_REGEX.sub("", current)
            if stripped != current:
                applied.append("html_tag_strip")
                current = stripped

        # 3. Unicode Canonical Normalization (NFC)
        nfc = unicodedata.normalize("NFC", current)
        if nfc != current:
            applied.append("unicode_nfc")
            current = nfc

        # 4. Line Ending Standardization (\r\n and \r -> \n)
        if "\r" in current:
            crlf_normalized = current.replace("\r\n", "\n").replace("\r", "\n")
            if crlf_normalized != current:
                applied.append("newline_standardize")
                current = crlf_normalized

        # 5. Control Character and Null Byte Removal
        cleaned_ctrl = self._CONTROL_CHAR_REGEX.sub("", current)
        if cleaned_ctrl != current:
            applied.append("strip_control_chars")
            current = cleaned_ctrl

        # 6. Typographical Standardization
        # Standardize 3+ dots to registered ellipsis glyph '…' (U+2026)
        if self.standardize_ellipsis and "..." in current:
            ellipsis_text = self._ELLIPSIS_REGEX.sub("…", current)
            if ellipsis_text != current:
                applied.append("standardize_ellipsis")
                current = ellipsis_text

        # Standardize typewriter '--' or '---' to em-dash '—' (U+2014)
        if self.standardize_dashes and "--" in current:
            dashed = self._DASH_CONVENTION_REGEX.sub("—", current)
            if dashed != current:
                applied.append("standardize_dashes")
                current = dashed

        # 7. Horizontal & Vertical Whitespace Consolidation
        if self.collapse_whitespace:
            # Replace non-breaking spaces & tabs with standard space
            ws_cleaned = current.replace("\u00a0", " ").replace("\t", " ")

            # Collapse horizontal multiple spaces to a single space
            ws_cleaned = re.sub(r"[ ]{2,}", " ", ws_cleaned)

            # Collapse 3 or more consecutive newlines to exactly 2 newlines (preserve paragraph)
            ws_cleaned = re.sub(r"\n{3,}", "\n\n", ws_cleaned)

            if ws_cleaned != current:
                applied.append("whitespace_collapse")
                current = ws_cleaned

        # 8. Boundary Trimming (strip leading & trailing whitespace)
        trimmed = current.strip()
        if trimmed != current:
            applied.append("boundary_trim")
            current = trimmed

        is_modified = current != text
        return NormalizationResult(
            raw_text=text,
            normalized_text=current,
            is_modified=is_modified,
            applied_transforms=applied,
        )
