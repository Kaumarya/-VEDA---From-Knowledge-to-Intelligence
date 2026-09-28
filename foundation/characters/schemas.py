"""
VEDA Character Knowledge Schemas (Phase 1 — Character Knowledge Layer v0.1)

Defines structured schema dataclasses representing linguistic, Unicode,
and relational knowledge about characters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CharacterIdentity:
    """Identity and encoding information for a character."""
    unicode_codepoint: str
    unicode_name: str
    unicode_category: str
    character_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterClassification:
    """Linguistic and typographical classification of a character."""
    type: str  # letter, digit, punctuation, whitespace, symbol, unknown
    case: Optional[str] = None  # uppercase, lowercase, None
    alphabet: Optional[str] = None  # english, None
    alphabet_position: Optional[int] = None  # 1..26 for English letters, None otherwise

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterRelationships:
    """Case relationships and equivalences for a character."""
    lowercase: Optional[str] = None
    uppercase: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterLanguage:
    """Language scope for character knowledge."""
    language: str = "English"
    language_code: str = "en"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CharacterLinguistic:
    """Linguistic and phonetic information."""
    letter_name: Optional[str] = None
    pronunciation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CharacterKnowledgeEntry:
    """
    Complete structured knowledge representation for a single character.
    Answers: 'What is this character?'
    """
    character: str
    known: bool
    identity: CharacterIdentity
    classification: CharacterClassification
    relationships: CharacterRelationships
    language: Optional[CharacterLanguage] = None
    linguistic: Optional[CharacterLinguistic] = None
    examples: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=lambda: ["VEDA foundational data"])

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the full knowledge entry into a standard dictionary."""
        data: Dict[str, Any] = {
            "character": self.character,
            "known": self.known,
            "identity": self.identity.to_dict(),
            "classification": self.classification.to_dict(),
            "relationships": self.relationships.to_dict(),
        }
        if self.language is not None:
            data["language"] = self.language.to_dict()
        if self.linguistic is not None:
            data["linguistic"] = self.linguistic.to_dict()
        data["examples"] = list(self.examples)
        data["sources"] = list(self.sources)
        return data

    def summary(self) -> Dict[str, Any]:
        """Returns a concise summary dictionary for quick inspection."""
        res: Dict[str, Any] = {
            "character": self.character,
            "type": self.classification.type,
            "case": self.classification.case,
            "alphabet_position": self.classification.alphabet_position,
        }
        if self.classification.type == "letter":
            if self.classification.case == "uppercase":
                res["lowercase"] = self.relationships.lowercase
            elif self.classification.case == "lowercase":
                res["uppercase"] = self.relationships.uppercase
            else:
                res["lowercase"] = self.relationships.lowercase
                res["uppercase"] = self.relationships.uppercase
        res["unicode"] = self.identity.unicode_codepoint
        return res
