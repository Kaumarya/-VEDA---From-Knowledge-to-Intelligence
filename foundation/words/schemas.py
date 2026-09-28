"""
VEDA Word Schemas (Phase 2 — Word Foundation v0.1)

Defines data structures representing word schemas, validation results,
and lexical placeholders for the VEDA Word Foundation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WordCandidateValidation:
    """Represents the outcome of validating a string as an English word candidate."""
    is_valid: bool
    reason: str  # "VALID", "EMPTY", "CONTAINS_DIGITS", "CONTAINS_PUNCTUATION", "CONTAINS_WHITESPACE", "CONTAINS_NON_ENGLISH_CHARS"
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WordLexicalData:
    """Placeholder for future Phase 3 Lexicon data (definitions, POS, relations)."""
    part_of_speech: Optional[str] = None
    definitions: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_of_speech": self.part_of_speech,
            "definitions": list(self.definitions),
            "synonyms": list(self.synonyms),
            "antonyms": list(self.antonyms),
        }


@dataclass
class WordSchema:
    """
    Complete structured serialized representation of an English word entry.
    Compatible with future Lexicon ingestion and vocabulary export.
    """
    word: str
    normalized: str
    language: str
    characters: List[str]
    character_ids: List[int]
    length: int
    lexical: WordLexicalData = field(default_factory=WordLexicalData)
    forms: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=lambda: ["VEDA foundational vocabulary"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "normalized": self.normalized,
            "language": self.language,
            "characters": list(self.characters),
            "character_ids": list(self.character_ids),
            "length": self.length,
            "lexical": self.lexical.to_dict(),
            "forms": list(self.forms),
            "sources": list(self.sources),
        }
