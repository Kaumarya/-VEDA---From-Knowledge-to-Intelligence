"""
VEDA Word Representation (Phase 2 — Word Foundation v0.1)

Encapsulates an English word entry, bridging character-level representations
to word-level lexical entities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from foundation.characters.registry import CharacterRegistry
from foundation.words.schemas import WordLexicalData, WordSchema


class Word:
    """
    Represents an English word in the VEDA architecture.

    Maintains:
    - Original surface form (e.g., 'Apple')
    - Canonical normalized lexical form (e.g., 'apple')
    - Character decomposition derived via CharacterRegistry
    - Discrete character and token IDs
    """

    def __init__(
        self,
        text: str,
        registry: Optional[CharacterRegistry] = None,
        normalized: Optional[str] = None,
        language: str = "en",
        lexical: Optional[WordLexicalData] = None,
    ) -> None:
        if not isinstance(text, str):
            raise TypeError(f"Word expects string input, got {type(text).__name__}")

        self._original = text
        self._normalized = normalized if normalized is not None else text.strip().lower()
        self._language = language
        self._lexical = lexical or WordLexicalData()

        # Connect to character registry for character identity
        if registry is None:
            self._registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        else:
            self._registry = registry

    @property
    def original(self) -> str:
        """Original surface form as typed/extracted (e.g. 'Apple')."""
        return self._original

    @property
    def normalized(self) -> str:
        """Canonical normalized identity (e.g. 'apple')."""
        return self._normalized

    @property
    def word(self) -> str:
        """Alias for original surface form."""
        return self._original

    @property
    def language(self) -> str:
        """Language code (e.g. 'en')."""
        return self._language

    @property
    def characters(self) -> List[str]:
        """List of individual characters in the normalized word."""
        return list(self._normalized)

    @property
    def surface_characters(self) -> List[str]:
        """List of individual characters in the original surface word."""
        return list(self._original)

    @property
    def length(self) -> int:
        """Number of characters in the word."""
        return len(self._normalized)

    @property
    def character_ids(self) -> List[int]:
        """
        Converts the normalized word into character IDs from the Character Registry.
        Raises ValueError if any character is outside the registry.
        """
        ids: List[int] = []
        for ch in self._normalized:
            entry = self._registry.get_character(ch)
            if entry is None:
                raise ValueError(
                    f"Character {ch!r} in word {self._normalized!r} is not in Character Registry"
                )
            ids.append(entry.id)
        return ids

    @property
    def lexical(self) -> WordLexicalData:
        """Access lexical definitions, parts of speech, and relationships."""
        return self._lexical

    def is_alphabetic(self) -> bool:
        """Checks if the word consists purely of ASCII alphabetic letters."""
        return len(self._normalized) > 0 and self._normalized.isalpha() and self._normalized.isascii()

    def to_schema(self) -> WordSchema:
        """Converts to a WordSchema dataclass."""
        return WordSchema(
            word=self._original,
            normalized=self._normalized,
            language=self._language,
            characters=self.characters,
            character_ids=self.character_ids,
            length=self.length,
            lexical=self._lexical,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the word into the standard VEDA Word schema dictionary."""
        return self.to_schema().to_dict()

    def exact_match(self, other: Any) -> bool:
        """Checks if both surface form and normalized form match exactly."""
        if not isinstance(other, Word):
            return False
        return self._original == other._original and self._normalized == other._normalized

    def __len__(self) -> int:
        return self.length

    def __iter__(self):
        return iter(self.characters)

    def __eq__(self, other: Any) -> bool:
        """
        Word Identity: Two words are lexically identical if their normalized forms match.
        For instance, Word('Apple') == Word('apple') == Word('APPLE').
        """
        if isinstance(other, Word):
            return self._normalized == other._normalized
        if isinstance(other, str):
            return self._normalized == other.strip().lower()
        return False

    def __hash__(self) -> int:
        """Enables storing Words in sets/dicts based on canonical lexical identity."""
        return hash((self._normalized, self._language))

    def __repr__(self) -> str:
        if self._original != self._normalized:
            return f"Word({self._original!r} -> {self._normalized!r})"
        return f"Word({self._normalized!r})"

    def __str__(self) -> str:
        return self._normalized
