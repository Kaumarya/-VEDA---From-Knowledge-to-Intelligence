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
    """
    Represents the outcome of validating a string as an English word candidate.

    Separates:
    - is_valid: whether it satisfies VEDA v0.1 plain English word candidate constraints
    - reason: categorical validation outcome code (preserves backward compatibility)
    - details: human-readable explanation
    - is_ascii: whether the string contains exclusively ASCII codepoints
    - is_representable: whether all characters exist in the CharacterRegistry (if checked)
    - unsupported_characters: characters outside the CharacterRegistry
    - orthographic_category: detailed classification ('plain_ascii', 'latin_accented', 'hyphenated', etc.)
    - language_scope: language classification context (defaults to 'en')
    """
    is_valid: bool
    reason: str  # "VALID", "EMPTY", "CONTAINS_DIGITS", "CONTAINS_PUNCTUATION", "CONTAINS_WHITESPACE", "CONTAINS_NON_ENGLISH_CHARS"
    details: Optional[str] = None
    is_ascii: bool = True
    is_representable: Optional[bool] = None
    unsupported_characters: List[str] = field(default_factory=list)
    orthographic_category: str = "plain_ascii"
    language_scope: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "reason": self.reason,
            "details": self.details,
            "is_ascii": self.is_ascii,
            "is_representable": self.is_representable,
            "unsupported_characters": list(self.unsupported_characters),
            "orthographic_category": self.orthographic_category,
            "language_scope": self.language_scope,
        }



@dataclass
class WordLexicalData:
    """Represents lexical information for an English word (definitions, POS, relations, sounds)."""
    part_of_speech: Optional[str] = None
    parts_of_speech: List[str] = field(default_factory=list)
    definitions: List[str] = field(default_factory=list)
    definitions_by_pos: Dict[str, List[str]] = field(default_factory=dict)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    pronunciations: List[str] = field(default_factory=list)
    etymology: Optional[str] = None

    def __post_init__(self) -> None:
        # Sync primary part_of_speech and parts_of_speech list
        if self.part_of_speech and not self.parts_of_speech:
            self.parts_of_speech = [self.part_of_speech]
        elif self.parts_of_speech and not self.part_of_speech:
            self.part_of_speech = self.parts_of_speech[0]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "part_of_speech": self.part_of_speech,
            "definitions": list(self.definitions),
            "synonyms": list(self.synonyms),
            "antonyms": list(self.antonyms),
        }
        if self.parts_of_speech:
            d["parts_of_speech"] = list(self.parts_of_speech)
        if self.definitions_by_pos:
            d["definitions_by_pos"] = {k: list(v) for k, v in self.definitions_by_pos.items()}
        if self.pronunciations:
            d["pronunciations"] = list(self.pronunciations)
        if self.etymology:
            d["etymology"] = self.etymology
        return d


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
