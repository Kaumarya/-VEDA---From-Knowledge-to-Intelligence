"""
VEDA Foundation — Word Subsystem (Phase 2 — Word Foundation v0.1)
"""

from foundation.words.analyzer import WordAnalyzer
from foundation.words.schemas import (
    WordCandidateValidation,
    WordLexicalData,
    WordSchema,
)
from foundation.words.word import Word

__all__ = [
    "Word",
    "WordAnalyzer",
    "WordCandidateValidation",
    "WordLexicalData",
    "WordSchema",
]
