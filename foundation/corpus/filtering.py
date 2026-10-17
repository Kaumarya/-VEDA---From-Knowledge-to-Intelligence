"""
VEDA Corpus Quality & Language Filtering (Phase 4 — Training Corpus Architecture)

Implements the quality filtering and English language policy specified in
docs/corpus_quality_policy.md. Computes measurable metrics, enforces threshold
bounds, and assigns composite quality scores.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from foundation.characters.registry import CharacterRegistry
from foundation.corpus.schemas import RejectionReason


def load_default_registry() -> CharacterRegistry:
    """Finds and loads the default CharacterRegistry from canonical locations."""
    candidates = [
        Path("veda_characters_v0.1.json"),
        Path("data/characters/veda_characters_v0.1.json"),
        Path(__file__).resolve().parent.parent.parent / "veda_characters_v0.1.json",
        Path(__file__).resolve().parent.parent.parent / "data" / "characters" / "veda_characters_v0.1.json",
    ]
    for p in candidates:
        if p.is_file():
            return CharacterRegistry.from_json_file(p)
    raise FileNotFoundError("Could not find veda_characters_v0.1.json in default locations")


# Standard English function stopwords for structural syntactic verification
_COMMON_ENGLISH_STOPWORDS: Set[str] = {
    # Core Function Words
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    # Essential Closed-Class Auxiliaries, Prepositions & Pronouns
    "is", "are", "were", "been", "has", "had", "between", "while",
    "under", "through", "before", "after", "these", "those",
    "each", "other", "such", "both", "than", "could", "should", "must", "only",
    "against", "near", "during", "across", "without", "over", "within", "along",
    "among", "upon", "its", "because", "since", "inside", "via",
    "how", "where", "why", "toward", "towards", "throughout", "whether",
}

# Known boilerplate phrases
_BOILERPLATE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\ball rights reserved\b", re.IGNORECASE),
    re.compile(r"\bterms of (use|service)\b", re.IGNORECASE),
    re.compile(r"\bprivacy policy\b", re.IGNORECASE),
    re.compile(r"\bclick here to\b", re.IGNORECASE),
    re.compile(r"\bcookie policy\b", re.IGNORECASE),
    re.compile(r"\bsubscribe to our newsletter\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class QualityMetrics:
    """Calculated measurable metrics for a text segment."""
    char_length: int
    word_count: int
    alpha_ratio: float
    symbol_ratio: float
    unregistered_ratio: float
    max_char_run: int
    max_word_run: int
    stopword_count: int
    non_latin_count: int
    non_latin_ratio: float
    unique_word_ratio: float


@dataclass(frozen=True)
class FilterDecision:
    """Decision produced by the QualityFilter for a text segment."""
    is_accepted: bool
    quality_score: float
    rejection_reason: Optional[RejectionReason] = None
    failed_metric: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    metrics: Optional[QualityMetrics] = None


class QualityFilter:
    """
    Measurable quality and language filter suite.
    """

    VERSION = "0.1.0"

    def __init__(
        self,
        registry: Optional[CharacterRegistry] = None,
        min_char_length: int = 25,
        max_char_length: int = 15000,
        min_word_count: int = 4,
        min_alpha_ratio: float = 0.65,
        max_symbol_ratio: float = 0.20,
        max_unregistered_ratio: float = 0.05,
        max_char_repetition: int = 4,
        max_word_repetition: int = 3,
        min_stopwords_short_threshold: int = 8,
        min_stopwords_for_short_texts: int = 1,
        min_stopwords_for_long_texts: int = 2,
        long_text_word_threshold: int = 15,
        max_non_latin_count: int = 30,
        max_non_latin_ratio: float = 0.15,
    ) -> None:
        self.registry = registry
        self.min_char_length = min_char_length
        self.max_char_length = max_char_length
        self.min_word_count = min_word_count
        self.min_alpha_ratio = min_alpha_ratio
        self.max_symbol_ratio = max_symbol_ratio
        self.max_unregistered_ratio = max_unregistered_ratio
        self.max_char_repetition = max_char_repetition
        self.max_word_repetition = max_word_repetition
        self.min_stopwords_short_threshold = min_stopwords_short_threshold
        self.min_stopwords_for_short_texts = min_stopwords_for_short_texts
        self.min_stopwords_for_long_texts = min_stopwords_for_long_texts
        self.long_text_word_threshold = long_text_word_threshold
        self.max_non_latin_count = max_non_latin_count
        self.max_non_latin_ratio = max_non_latin_ratio

    def compute_metrics(self, text: str) -> QualityMetrics:
        """Computes all quality metrics for the input string."""
        if not isinstance(text, str):
            raise TypeError(f"QualityFilter.compute_metrics expects a string, got {type(text).__name__}")
        char_length = len(text)
        if char_length == 0:
            return QualityMetrics(
                char_length=0,
                word_count=0,
                alpha_ratio=0.0,
                symbol_ratio=0.0,
                unregistered_ratio=0.0,
                max_char_run=0,
                max_word_run=0,
                stopword_count=0,
                non_latin_count=0,
                non_latin_ratio=0.0,
                unique_word_ratio=0.0,
            )

        words = text.split()
        word_count = len(words)
        lower_words = [w.strip(".,!?:;\"'()[]{}—–-").lower() for w in words]
        clean_words = [w for w in lower_words if w]

        alpha_chars = sum(1 for c in text if c.isalpha())
        alpha_ratio = alpha_chars / char_length

        # Symbols / punctuation count (not alpha, not digit, not whitespace)
        symbol_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        symbol_ratio = symbol_chars / char_length

        # Unregistered / Corrupted Unicode check
        # If registry is explicitly provided by caller, check membership in registry.
        # Otherwise, follow Corpus Unicode Policy: count truly corrupted/unassigned/private-use codepoints.
        if self.registry is not None:
            unregistered_chars = sum(1 for c in text if not self.registry.contains_char(c))
        else:
            unregistered_chars = sum(
                1 for c in text if c == "\ufffd" or unicodedata.category(c) in ("Cn", "Co", "Cs")
            )
        unregistered_ratio = unregistered_chars / char_length

        # Non-Latin characters (scripts outside Latin)
        # Latin letters have Unicode names starting with 'LATIN '
        non_latin = 0
        for c in text:
            if c.isalpha():
                name = unicodedata.name(c, "")
                if not name.startswith("LATIN "):
                    non_latin += 1

        non_latin_ratio = (non_latin / alpha_chars) if alpha_chars > 0 else 0.0

        # Max consecutive identical characters
        max_char_run = 1
        current_run = 1
        for i in range(1, len(text)):
            if text[i] == text[i - 1]:
                current_run += 1
                if current_run > max_char_run:
                    max_char_run = current_run
            else:
                current_run = 1

        # Max consecutive identical words
        max_word_run = 1
        current_w_run = 1
        for i in range(1, len(lower_words)):
            if lower_words[i] and lower_words[i] == lower_words[i - 1]:
                current_w_run += 1
                if current_w_run > max_word_run:
                    max_word_run = current_w_run
            else:
                current_w_run = 1

        # Distinct stopwords
        stopword_count = sum(1 for w in set(clean_words) if w in _COMMON_ENGLISH_STOPWORDS)

        # Unique word ratio
        unique_word_ratio = len(set(clean_words)) / max(1, len(clean_words))

        return QualityMetrics(
            char_length=char_length,
            word_count=word_count,
            alpha_ratio=alpha_ratio,
            symbol_ratio=symbol_ratio,
            unregistered_ratio=unregistered_ratio,
            max_char_run=max_char_run,
            max_word_run=max_word_run,
            stopword_count=stopword_count,
            non_latin_count=non_latin,
            non_latin_ratio=non_latin_ratio,
            unique_word_ratio=unique_word_ratio,
        )

    def evaluate(self, normalized_text: str) -> FilterDecision:
        """
        Evaluates a normalized text segment against all quality filters.
        Returns a FilterDecision with pass/fail status and composite score.
        """
        metrics = self.compute_metrics(normalized_text)

        # 1. Empty Text check (empty string or whitespace-only text)
        if metrics.char_length == 0 or not normalized_text.strip():
            return FilterDecision(
                is_accepted=False,
                quality_score=0.0,
                rejection_reason=RejectionReason.EMPTY_TEXT,
                failed_metric="char_length",
                metric_value=0.0,
                threshold_value=float(self.min_char_length),
                metrics=metrics,
            )

        # 2. Min character length
        if metrics.char_length < self.min_char_length:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.1,
                rejection_reason=RejectionReason.TOO_SHORT_CHARS,
                failed_metric="char_length",
                metric_value=float(metrics.char_length),
                threshold_value=float(self.min_char_length),
                metrics=metrics,
            )

        # 3. Min word count
        if metrics.word_count < self.min_word_count:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.15,
                rejection_reason=RejectionReason.TOO_SHORT_WORDS,
                failed_metric="word_count",
                metric_value=float(metrics.word_count),
                threshold_value=float(self.min_word_count),
                metrics=metrics,
            )

        # 4. Max character length
        if metrics.char_length > self.max_char_length:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.2,
                rejection_reason=RejectionReason.TOO_LONG_CHARS,
                failed_metric="char_length",
                metric_value=float(metrics.char_length),
                threshold_value=float(self.max_char_length),
                metrics=metrics,
            )

        # 5. Non-Latin script dominance limit (Script Composition vs. Language Identity)
        # Rejects text where non-Latin scripts dominate (e.g. Cyrillic, Hindi, Greek, CJK).
        # Allows legitimate minority inclusions (Greek scientific symbols, foreign names, citations)
        # provided the document remains predominantly Latin script (non_latin_ratio <= max_non_latin_ratio)
        # and total non-Latin letters do not exceed absolute threshold (max_non_latin_count).
        if metrics.non_latin_count > 0:
            if metrics.non_latin_ratio > self.max_non_latin_ratio or metrics.non_latin_count > self.max_non_latin_count:
                return FilterDecision(
                    is_accepted=False,
                    quality_score=0.1,
                    rejection_reason=RejectionReason.NON_ENGLISH_SCRIPT,
                    failed_metric="non_latin_ratio",
                    metric_value=metrics.non_latin_ratio,
                    threshold_value=self.max_non_latin_ratio,
                    metrics=metrics,
                )

        # 6. Alphabetic character ratio
        if metrics.alpha_ratio < self.min_alpha_ratio:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.25,
                rejection_reason=RejectionReason.LOW_ALPHA_RATIO,
                failed_metric="alpha_ratio",
                metric_value=metrics.alpha_ratio,
                threshold_value=self.min_alpha_ratio,
                metrics=metrics,
            )

        # 7. Symbol and punctuation ratio
        if metrics.symbol_ratio > self.max_symbol_ratio:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.25,
                rejection_reason=RejectionReason.HIGH_SYMBOL_RATIO,
                failed_metric="symbol_ratio",
                metric_value=metrics.symbol_ratio,
                threshold_value=self.max_symbol_ratio,
                metrics=metrics,
            )

        # 8. Unregistered / Corrupted character ratio
        if "\ufffd" in normalized_text or any(unicodedata.category(c) in ("Cn", "Cs") for c in normalized_text):
            return FilterDecision(
                is_accepted=False,
                quality_score=0.1,
                rejection_reason=RejectionReason.HIGH_UNREGISTERED_RATIO,
                failed_metric="corrupted_unicode",
                metric_value=metrics.unregistered_ratio,
                threshold_value=0.0,
                metrics=metrics,
            )

        if metrics.unregistered_ratio > self.max_unregistered_ratio:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.2,
                rejection_reason=RejectionReason.HIGH_UNREGISTERED_RATIO,
                failed_metric="unregistered_ratio",
                metric_value=metrics.unregistered_ratio,
                threshold_value=self.max_unregistered_ratio,
                metrics=metrics,
            )

        # 9. Character repetition run
        if metrics.max_char_run > self.max_char_repetition:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.2,
                rejection_reason=RejectionReason.REPEATED_CHARS,
                failed_metric="max_char_run",
                metric_value=float(metrics.max_char_run),
                threshold_value=float(self.max_char_repetition),
                metrics=metrics,
            )

        # 10. Word repetition run
        if metrics.max_word_run > self.max_word_repetition:
            return FilterDecision(
                is_accepted=False,
                quality_score=0.2,
                rejection_reason=RejectionReason.REPEATED_WORDS,
                failed_metric="max_word_run",
                metric_value=float(metrics.max_word_run),
                threshold_value=float(self.max_word_repetition),
                metrics=metrics,
            )

        # 11. Common English stopwords for syntactic verification
        # Distinguishes genuine English prose from Latin-script foreign languages (French, German, Spanish)
        # as well as non-syntactic word lists and jargon dumps.
        if metrics.word_count >= self.min_stopwords_short_threshold:
            required_stopwords = (
                self.min_stopwords_for_long_texts
                if metrics.word_count >= self.long_text_word_threshold
                else self.min_stopwords_for_short_texts
            )
            if metrics.stopword_count < required_stopwords:
                # Phase 4.13 Remediation:
                # Single-sentence technical and scientific English prose (15-24 words) frequently connects
                # domain-specific compound nouns using a single distinct function word (e.g., 'to', 'and', 'across')
                # or multiple occurrences of a single stopword.
                # If the segment has at least 1 stopword, high alphabetic cleanliness (alpha_ratio >= 0.75),
                # pure Latin script (non_latin_ratio == 0.0), and word_count < 25, do not reject solely on
                # distinct stopword count; allow it to pass to the language audit gate (classify_with_quarantine)
                # for cognate-aware verification.
                is_valid_technical_candidate = (
                    metrics.stopword_count >= 1
                    and metrics.alpha_ratio >= 0.75
                    and metrics.non_latin_ratio == 0.0
                    and metrics.word_count < 25
                )
                if not is_valid_technical_candidate:
                    return FilterDecision(
                        is_accepted=False,
                        quality_score=0.3,
                        rejection_reason=RejectionReason.NO_ENGLISH_STOPWORDS,
                        failed_metric="stopword_count",
                        metric_value=float(metrics.stopword_count),
                        threshold_value=float(required_stopwords),
                        metrics=metrics,
                    )

        # 12. Programming source code syntax detection
        if re.search(r"^\s*(def\s+\w+\s*\(|class\s+\w+\s*(\(|:)|import\s+\w+|from\s+\w+\s+import)\b", normalized_text, re.MULTILINE):
            return FilterDecision(
                is_accepted=False,
                quality_score=0.1,
                rejection_reason=RejectionReason.INVALID_STRUCTURE,
                failed_metric="code_syntax",
                metric_value=1.0,
                threshold_value=0.0,
                metrics=metrics,
            )

        # 13. Boilerplate matching
        for pattern in _BOILERPLATE_PATTERNS:
            if pattern.search(normalized_text):
                return FilterDecision(
                    is_accepted=False,
                    quality_score=0.2,
                    rejection_reason=RejectionReason.BOILERPLATE_CONTENT,
                    failed_metric="boilerplate_pattern",
                    metric_value=1.0,
                    threshold_value=0.0,
                    metrics=metrics,
                )

        # Passed all filters — calculate continuous quality score
        # Alpha score: 0.65 -> 0.85 maps to 0.7 -> 1.0
        s_alpha = min(1.0, max(0.5, metrics.alpha_ratio / 0.85))
        # Symbol penalty
        s_symbol = max(0.0, 1.0 - (metrics.symbol_ratio / self.max_symbol_ratio))
        # Diversity score
        s_diversity = min(1.0, metrics.unique_word_ratio * 1.2)
        # Length score (bell curve around 100 words)
        words = metrics.word_count
        s_length = 1.0 if (20 <= words <= 250) else (0.85 if words < 20 else 0.90)

        composite_score = (
            0.35 * s_alpha +
            0.25 * s_symbol +
            0.20 * s_diversity +
            0.20 * s_length
        )
        composite_score = min(1.0, max(0.0, composite_score))

        return FilterDecision(
            is_accepted=True,
            quality_score=composite_score,
            metrics=metrics,
        )
