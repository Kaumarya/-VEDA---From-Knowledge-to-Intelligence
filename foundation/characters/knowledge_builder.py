"""
VEDA Character Knowledge Builder (Phase 1 — Character Knowledge Layer v0.1)

Responsible for constructing structured, verified character knowledge entries
from the Character Registry and Python's Unicode subsystem.
"""

from __future__ import annotations

import unicodedata
from typing import Dict, List, Optional, Tuple

from foundation.characters.registry import CharacterEntry, CharacterRegistry
from foundation.characters.schemas import (
    CharacterClassification,
    CharacterIdentity,
    CharacterKnowledgeEntry,
    CharacterLanguage,
    CharacterLinguistic,
    CharacterRelationships,
)

# Curated English letter phonetic and linguistic metadata
ENGLISH_LETTER_METADATA: Dict[str, Tuple[str, str, List[str]]] = {
    "A": ("A", "/eɪ/", ["apple", "animal", "artificial"]),
    "B": ("B", "/biː/", ["book", "binary", "build"]),
    "C": ("C", "/siː/", ["computer", "character", "code"]),
    "D": ("D", "/diː/", ["data", "design", "dictionary"]),
    "E": ("E", "/iː/", ["english", "embedding", "engine"]),
    "F": ("F", "/ɛf/", ["foundation", "first", "forward"]),
    "G": ("G", "/dʒiː/", ["gradient", "grammar", "generation"]),
    "H": ("H", "/eɪtʃ/", ["hello", "history", "hierarchy"]),
    "I": ("I", "/aɪ/", ["intelligence", "inference", "iteration"]),
    "J": ("J", "/dʒeɪ/", ["json", "join", "journey"]),
    "K": ("K", "/keɪ/", ["knowledge", "kernel", "key"]),
    "L": ("L", "/ɛl/", ["language", "layer", "lexicon"]),
    "M": ("M", "/ɛm/", ["model", "matrix", "masking"]),
    "N": ("N", "/ɛn/", ["neural", "network", "normalization"]),
    "O": ("O", "/oʊ/", ["optimizer", "output", "order"]),
    "P": ("P", "/piː/", ["principle", "pipeline", "pretraining"]),
    "Q": ("Q", "/kjuː/", ["query", "quality", "question"]),
    "R": ("R", "/ɑːr/", ["registry", "retrieval", "residual"]),
    "S": ("S", "/ɛs/", ["sequence", "structure", "symbol"]),
    "T": ("T", "/tiː/", ["transformer", "tokenizer", "tensor"]),
    "U": ("U", "/juː/", ["unicode", "unknown", "unit"]),
    "V": ("V", "/viː/", ["veda", "vocabulary", "vector"]),
    "W": ("W", "/ˈdʌbəl.juː/", ["weight", "word", "whitespace"]),
    "X": ("X", "/ɛks/", ["example", "index", "extract"]),
    "Y": ("Y", "/waɪ/", ["yield", "yaml", "year"]),
    "Z": ("Z", "/zɛd/", ["zero", "zone", "zip"]),
}


class CharacterKnowledgeBuilder:
    """Builder utility for creating CharacterKnowledgeEntry objects."""

    @staticmethod
    def get_alphabet_position(char: str) -> Optional[int]:
        """Returns 1..26 for English letters (A-Z / a-z), None for all other characters."""
        if len(char) == 1 and char.isalpha() and char.isascii():
            return ord(char.upper()) - ord("A") + 1
        return None

    @staticmethod
    def determine_type(char: str, registry_entry: Optional[CharacterEntry] = None) -> str:
        """
        Determines the character classification type:
        letter, digit, punctuation, whitespace, symbol, or unknown.
        """
        if len(char) != 1:
            return "unknown"

        # Letters
        if char.isalpha() and char.isascii():
            return "letter"

        # Digits
        if char.isdigit() and char.isascii():
            return "digit"

        # Whitespace
        if char.isspace():
            return "whitespace"

        # Check registry entry classification if available
        if registry_entry is not None:
            if registry_entry.type == "punctuation":
                return "punctuation"
            elif registry_entry.type == "symbol":
                return "symbol"
            elif registry_entry.type == "whitespace":
                return "whitespace"
            elif registry_entry.type == "number":
                return "digit"

        # Fallback to Unicode category inspection
        cat = unicodedata.category(char)
        if cat.startswith("P"):
            return "punctuation"
        if cat.startswith("S"):
            return "symbol"
        if cat.startswith("Z") or cat.startswith("C"):
            if char in ("\t", "\n", "\r", " "):
                return "whitespace"

        return "unknown"

    @classmethod
    def build_entry(
        cls,
        char: str,
        registry_entry: Optional[CharacterEntry] = None,
    ) -> CharacterKnowledgeEntry:
        """
        Builds a comprehensive CharacterKnowledgeEntry for any single character.
        If registry_entry is provided, associates the character ID from the registry.
        Safely handles unknown characters (e.g. non-ASCII or out-of-registry symbols).
        """
        if len(char) != 1:
            raise ValueError(f"build_entry expects a single character string, got {char!r}")

        is_registered = registry_entry is not None
        char_id = registry_entry.id if registry_entry is not None else None

        # Unicode metadata derived programmatically
        codepoint = f"U+{ord(char):04X}"
        try:
            uni_name = unicodedata.name(char)
        except ValueError:
            uni_name = registry_entry.unicode_name if registry_entry else "UNKNOWN"
        uni_cat = unicodedata.category(char)

        identity = CharacterIdentity(
            unicode_codepoint=codepoint,
            unicode_name=uni_name,
            unicode_category=uni_cat,
            character_id=char_id,
        )

        char_type = cls.determine_type(char, registry_entry)

        if not is_registered:
            # Unregistered / Out of English character scope
            classification_type = "unknown"
            case = None
            alphabet = None
            alphabet_position = None
            relationships = CharacterRelationships(lowercase=None, uppercase=None)
            language = None
            linguistic = None
            examples = []
            known = False
            sources = [f"Unicode Standard {unicodedata.unidata_version}"]
        elif char_type == "letter":
            classification_type = "letter"
            is_upper = char.isupper()
            case = "uppercase" if is_upper else "lowercase"
            alphabet = "english"
            alphabet_position = cls.get_alphabet_position(char)

            relationships = CharacterRelationships(
                lowercase=char.lower(),
                uppercase=char.upper(),
            )
            language = CharacterLanguage(language="English", language_code="en")

            # Look up linguistic info
            base_upper = char.upper()
            letter_info = ENGLISH_LETTER_METADATA.get(base_upper)
            if letter_info:
                letter_name, pronunciation, examples = letter_info
                linguistic = CharacterLinguistic(
                    letter_name=letter_name,
                    pronunciation=pronunciation,
                )
            else:
                linguistic = CharacterLinguistic(letter_name=base_upper)
                examples = []

            known = True
            sources = [
                "VEDA foundational data",
                f"Unicode Standard {unicodedata.unidata_version}",
            ]

        elif char_type in ("digit", "punctuation", "whitespace", "symbol") and is_registered:
            classification_type = char_type
            case = None
            alphabet = None
            alphabet_position = None
            relationships = CharacterRelationships(lowercase=None, uppercase=None)
            language = CharacterLanguage(language="English", language_code="en")
            linguistic = None
            examples = []
            known = True
            sources = [
                "VEDA foundational data",
                f"Unicode Standard {unicodedata.unidata_version}",
            ]

        else:
            classification_type = "unknown"
            case = None
            alphabet = None
            alphabet_position = None
            relationships = CharacterRelationships(lowercase=None, uppercase=None)
            language = None
            linguistic = None
            examples = []
            known = False
            sources = [f"Unicode Standard {unicodedata.unidata_version}"]

        classification = CharacterClassification(
            type=classification_type,
            case=case,
            alphabet=alphabet,
            alphabet_position=alphabet_position,
        )

        return CharacterKnowledgeEntry(
            character=char,
            known=known,
            identity=identity,
            classification=classification,
            relationships=relationships,
            language=language,
            linguistic=linguistic,
            examples=examples,
            sources=sources,
        )
