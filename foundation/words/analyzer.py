"""
VEDA Word Analyzer (Phase 2 — Word Foundation v0.1)

Provides validation, normalization, decomposition, and character-ID roundtrip
conversions for English words.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

from foundation.characters.registry import CharacterRegistry
from foundation.words.schemas import WordCandidateValidation
from foundation.words.word import Word


class WordAnalyzer:
    """
    Core analysis and validation engine for the VEDA Word Foundation.

    Connects words to the underlying Character Registry for character ID conversion
    and validates plain English word candidates.
    """

    def __init__(self, registry: Optional[CharacterRegistry] = None) -> None:
        if registry is None:
            # Look for default registry file
            for candidate in (
                Path("data/characters/veda_characters_v0.1.json"),
                Path("veda_characters_v0.1.json"),
            ):
                if candidate.is_file():
                    self._registry = CharacterRegistry.from_json_file(candidate)
                    break
            else:
                self._registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        else:
            self._registry = registry

    @property
    def registry(self) -> CharacterRegistry:
        """Returns the connected CharacterRegistry."""
        return self._registry

    def normalize_word(self, text: str) -> str:
        """
        Normalizes a word string according to VEDA v0.1 normalization policy:
        - Strips leading and trailing whitespace
        - Converts to lowercase
        """
        if not isinstance(text, str):
            raise TypeError(f"normalize_word expects str, got {type(text).__name__}")
        return text.strip().lower()

    def validate_candidate(self, text: str) -> WordCandidateValidation:
        """
        Evaluates whether a string qualifies as a valid plain English word candidate.

        Validation Policy for v0.1:
        - Non-empty
        - Purely ASCII alphabetic letters (A-Z, a-z)
        - Rejects numbers, punctuation, whitespace, and non-English/emoji characters.
        """
        if not isinstance(text, str):
            raise TypeError(f"validate_candidate expects str, got {type(text).__name__}")

        trimmed = text.strip()
        if not trimmed:
            return WordCandidateValidation(
                is_valid=False,
                reason="EMPTY",
                details="Input is empty or contains only whitespace.",
            )

        # Check for internal whitespace
        if any(c.isspace() for c in trimmed):
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_WHITESPACE",
                details="Input contains whitespace delimiters; not a single word candidate.",
            )

        # Check for digits
        if any(c.isdigit() for c in trimmed):
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_DIGITS",
                details="Input contains numeric digits; not an alphabetic English word.",
            )

        # Check for non-ASCII characters or emojis
        if not trimmed.isascii():
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_NON_ENGLISH_CHARS",
                details="Input contains non-ASCII characters or symbols.",
            )

        # Check for punctuation / non-alpha
        if not trimmed.isalpha():
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_PUNCTUATION",
                details="Input contains punctuation or non-alphabetic symbols.",
            )

        return WordCandidateValidation(
            is_valid=True,
            reason="VALID",
            details="Valid plain English word candidate.",
        )

    def is_word_candidate(self, text: str) -> bool:
        """Returns True if the string is a valid plain English word candidate, False otherwise."""
        return self.validate_candidate(text).is_valid

    def create_word(self, text: str) -> Word:
        """
        Constructs a Word instance, validating character presence in registry.
        Preserves original surface form while normalizing lexical identity.
        """
        norm = self.normalize_word(text)
        return Word(text=text, registry=self._registry, normalized=norm)

    def get_characters(self, word: Union[str, Word]) -> List[str]:
        """Returns the list of characters forming the normalized word."""
        if isinstance(word, Word):
            return word.characters
        return list(self.normalize_word(word))

    def get_length(self, word: Union[str, Word]) -> int:
        """Returns the character count of the normalized word."""
        if isinstance(word, Word):
            return word.length
        return len(self.normalize_word(word))

    def get_character_ids(self, word: Union[str, Word]) -> List[int]:
        """
        Converts a word into a sequence of integer character IDs from the Character Registry.
        """
        if isinstance(word, Word):
            return word.character_ids

        norm = self.normalize_word(word)
        ids: List[int] = []
        for ch in norm:
            entry = self._registry.get_character(ch)
            if entry is None:
                raise ValueError(f"Character {ch!r} in word {norm!r} is not in Character Registry")
            ids.append(entry.id)
        return ids

    def encode_word(self, word: Union[str, Word]) -> List[int]:
        """Alias for get_character_ids: converts word -> characters -> character IDs."""
        return self.get_character_ids(word)

    def decode_word(self, character_ids: Sequence[int]) -> Word:
        """
        Reconstructs a Word instance from a sequence of character IDs.
        character IDs -> characters -> Word
        """
        chars: List[str] = []
        for cid in character_ids:
            entry = self._registry.get_character_by_id(cid)
            if entry is None:
                raise ValueError(f"Character ID {cid} not found in Character Registry")
            chars.append(entry.character)

        reconstructed_text = "".join(chars)
        return self.create_word(reconstructed_text)
