"""
VEDA Word Analyzer (Phase 2 — Word Foundation v0.1)

Provides validation, normalization, decomposition, and character-ID roundtrip
conversions for English words.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from foundation.characters.registry import CharacterRegistry
from foundation.words.schemas import WordCandidateValidation
from foundation.words.word import Word


class WordAnalyzer:
    """
    Core analysis and validation engine for the VEDA Word Foundation.

    Connects words to the underlying Character Registry for character ID conversion
    and validates plain English word candidates.
    """

    def __init__(
        self,
        registry: Optional[CharacterRegistry] = None,
        lexicon: Optional[Any] = None,
    ) -> None:
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

        self._lexicon = lexicon

    @staticmethod
    def _categorize_non_ascii(text: str) -> str:
        """Categorizes non-ASCII strings into Latin accented, non-Latin script, or emoji/symbol."""
        if all(unicodedata.category(c).startswith("L") for c in text):
            is_latin = all("LATIN" in unicodedata.name(c, "").upper() for c in text)
            return "latin_accented" if is_latin else "non_latin_script"
        if any(unicodedata.category(c).startswith(("S", "C")) for c in text):
            return "symbol_or_emoji"
        return "non_ascii_other"

    @property
    def registry(self) -> CharacterRegistry:
        """Returns the connected CharacterRegistry."""
        return self._registry

    @property
    def lexicon(self) -> Optional[Any]:
        """Returns the connected Lexicon, if any."""
        return self._lexicon

    def set_lexicon(self, lexicon: Any) -> None:
        """Attaches a Lexicon instance to the analyzer."""
        self._lexicon = lexicon

    def is_dictionary_word(self, word: Union[str, Word]) -> bool:
        """
        Returns True if the word is found in the attached Lexicon.
        Returns False if no lexicon is attached or word is not found.
        """
        if self._lexicon is None:
            return False
        return self._lexicon.has_word(word)

    def lookup_dictionary(self, word: Union[str, Word]) -> Optional[Any]:
        """Looks up the lexical entry in the attached Lexicon."""
        if self._lexicon is None:
            return None
        return self._lexicon.get(word)

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
        - Explicitly distinguishes candidate validity from character representability.
        """
        if not isinstance(text, str):
            raise TypeError(f"validate_candidate expects str, got {type(text).__name__}")

        trimmed = text.strip()
        if not trimmed:
            return WordCandidateValidation(
                is_valid=False,
                reason="EMPTY",
                details="Input is empty or contains only whitespace.",
                is_ascii=True,
                is_representable=False,
                unsupported_characters=[],
                orthographic_category="empty",
                language_scope="en",
            )

        # Check for internal whitespace
        if any(c.isspace() for c in trimmed):
            unsupported = [c for c in trimmed.lower() if not self._registry.contains_char(c)]
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_WHITESPACE",
                details="Input contains whitespace delimiters; not a single word candidate.",
                is_ascii=trimmed.isascii(),
                is_representable=(len(unsupported) == 0),
                unsupported_characters=unsupported,
                orthographic_category="whitespace",
                language_scope="en",
            )

        # Check for digits
        if any(c.isdigit() for c in trimmed):
            unsupported = [c for c in trimmed.lower() if not self._registry.contains_char(c)]
            digit_cat = "numeric" if trimmed.isdigit() else "contains_digits"
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_DIGITS",
                details="Input contains numeric digits; not an alphabetic English word.",
                is_ascii=trimmed.isascii(),
                is_representable=(len(unsupported) == 0),
                unsupported_characters=unsupported,
                orthographic_category=digit_cat,
                language_scope="en",
            )

        # Check for non-ASCII characters or emojis
        if not trimmed.isascii():
            non_ascii_cat = self._categorize_non_ascii(trimmed)
            unsupported = [c for c in trimmed.lower() if not self._registry.contains_char(c)]
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_NON_ENGLISH_CHARS",
                details="Input contains non-ASCII characters or symbols.",
                is_ascii=False,
                is_representable=(len(unsupported) == 0),
                unsupported_characters=unsupported,
                orthographic_category=non_ascii_cat,
                language_scope="en",
            )

        # Check for punctuation / non-alpha
        if not trimmed.isalpha():
            punct_cat = (
                "hyphenated"
                if "-" in trimmed
                else ("apostrophe_contraction" if ("'" in trimmed or "’" in trimmed) else "contains_punctuation")
            )
            unsupported = [c for c in trimmed.lower() if not self._registry.contains_char(c)]
            return WordCandidateValidation(
                is_valid=False,
                reason="CONTAINS_PUNCTUATION",
                details="Input contains punctuation or non-alphabetic symbols.",
                is_ascii=trimmed.isascii(),
                is_representable=(len(unsupported) == 0),
                unsupported_characters=unsupported,
                orthographic_category=punct_cat,
                language_scope="en",
            )

        # Valid v0.1 plain English candidate
        unsupported = [c for c in trimmed.lower() if not self._registry.contains_char(c)]
        return WordCandidateValidation(
            is_valid=True,
            reason="VALID",
            details="Valid plain English word candidate.",
            is_ascii=True,
            is_representable=(len(unsupported) == 0),
            unsupported_characters=unsupported,
            orthographic_category="plain_ascii",
            language_scope="en",
        )

    def check_character_support(
        self, word_or_text: Union[str, Word]
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates whether all characters in the word are representable
        by the connected Character Registry.

        Returns:
            Tuple of (is_fully_supported: bool, unsupported_characters: List[str])
        """
        text = (
            word_or_text.normalized
            if isinstance(word_or_text, Word)
            else self.normalize_word(word_or_text)
        )
        unsupported = [ch for ch in text if not self._registry.contains_char(ch)]
        return (len(unsupported) == 0, unsupported)

    def analyze_orthography(self, text: str) -> Dict[str, Any]:
        """
        Performs a full orthographic decomposition separating language classification,
        orthographic candidate validity, and character registry representability.
        """
        if not isinstance(text, str):
            raise TypeError(f"analyze_orthography expects str, got {type(text).__name__}")

        validation = self.validate_candidate(text)
        norm = self.normalize_word(text)
        is_dict = self.is_dictionary_word(norm)

        return {
            "surface_form": text,
            "normalized": norm,
            "is_v01_candidate": validation.is_valid,
            "validation_reason": validation.reason,
            "details": validation.details,
            "is_ascii": validation.is_ascii,
            "orthographic_category": validation.orthographic_category,
            "is_representable": validation.is_representable,
            "unsupported_characters": validation.unsupported_characters,
            "is_dictionary_word": is_dict,
            "language_scope": validation.language_scope,
        }


    def is_word_candidate(self, text: str) -> bool:
        """Returns True if the string is a valid plain English word candidate, False otherwise."""
        return self.validate_candidate(text).is_valid

    def create_word(self, text: str) -> Word:
        """
        Constructs a Word instance, validating character presence in registry.
        Preserves original surface form while normalizing lexical identity.
        If a lexicon is attached and contains the word, automatically populates its lexical data.
        """
        norm = self.normalize_word(text)
        lexical_data = None
        if self._lexicon is not None and self._lexicon.has_word(norm):
            entry = self._lexicon.get(norm)
            if entry is not None:
                lexical_data = entry.to_word_lexical_data()

        return Word(
            text=text,
            registry=self._registry,
            normalized=norm,
            lexical=lexical_data,
        )

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
