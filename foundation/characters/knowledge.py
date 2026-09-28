"""
VEDA Character Knowledge Base (Phase 1 — Character Knowledge Layer v0.1)

Provides a high-level symbolic knowledge interface for querying linguistic,
typographical, and Unicode properties of characters from first principles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from foundation.characters.knowledge_builder import CharacterKnowledgeBuilder
from foundation.characters.registry import CharacterRegistry
from foundation.characters.schemas import CharacterKnowledgeEntry


class CharacterKnowledge:
    """
    Symbolic knowledge layer for characters in the VEDA project.

    Answers: 'What is this character?'
    Distinguishes letters, digits, punctuation, whitespace, symbols, and unknowns.
    """

    DEFAULT_KNOWLEDGE_JSON = Path("data/characters/veda_character_knowledge_v0.1.json")

    def __init__(
        self,
        registry: Optional[Union[CharacterRegistry, str, Path]] = None,
    ) -> None:
        """Initializes the knowledge base by connecting to the Character Registry."""
        if registry is None:
            self._registry = self._load_default_registry()
        elif isinstance(registry, (str, Path)):
            self._registry = CharacterRegistry.from_json_file(registry)
        elif isinstance(registry, CharacterRegistry):
            self._registry = registry
        else:
            raise TypeError(f"Invalid registry type: {type(registry).__name__}")

        # In-memory knowledge store indexed by character
        self._entries: Dict[str, CharacterKnowledgeEntry] = {}
        self._build_knowledge_base()

    def _load_default_registry(self) -> CharacterRegistry:
        """Finds and loads the default character registry."""
        candidates = [
            Path("data/characters/veda_characters_v0.1.json"),
            Path("veda_characters_v0.1.json"),
            Path(__file__).resolve().parent.parent.parent / "data" / "characters" / "veda_characters_v0.1.json",
            Path(__file__).resolve().parent.parent.parent / "veda_characters_v0.1.json",
        ]
        for path in candidates:
            if path.is_file():
                return CharacterRegistry.from_json_file(path)
        raise FileNotFoundError("Could not find veda_characters_v0.1.json in workspace.")

    def _build_knowledge_base(self) -> None:
        """Populates the knowledge base from the active registry entries."""
        for char_entry in self._registry.characters:
            knowledge_entry = CharacterKnowledgeBuilder.build_entry(
                char=char_entry.character,
                registry_entry=char_entry,
            )
            self._entries[char_entry.character] = knowledge_entry

    @property
    def registry(self) -> CharacterRegistry:
        """Returns the underlying CharacterRegistry."""
        return self._registry

    @property
    def known_characters_count(self) -> int:
        """Number of characters registered in the knowledge base."""
        return len(self._entries)

    def get(self, character: str) -> CharacterKnowledgeEntry:
        """
        Retrieves knowledge for any single character.
        If the character is outside the registry, dynamically builds a safe 'unknown' entry.
        Never crashes on unlisted characters.
        """
        if not isinstance(character, str) or len(character) != 1:
            raise ValueError(f"get() requires a single-character string, got {character!r}")

        if character in self._entries:
            return self._entries[character]

        # Dynamic fallback for out-of-registry characters (e.g. '☃', emojis)
        return CharacterKnowledgeBuilder.build_entry(character, registry_entry=None)

    def is_known(self, character: str) -> bool:
        """Checks if a character is part of the registered English character knowledge base."""
        return character in self._entries

    def is_letter(self, character: str) -> bool:
        """Checks if the character is an English alphabet letter."""
        entry = self.get(character)
        return entry.classification.type == "letter"

    def is_digit(self, character: str) -> bool:
        """Checks if the character is a digit (0-9)."""
        entry = self.get(character)
        return entry.classification.type == "digit"

    def is_punctuation(self, character: str) -> bool:
        """Checks if the character is punctuation."""
        entry = self.get(character)
        return entry.classification.type == "punctuation"

    def is_whitespace(self, character: str) -> bool:
        """Checks if the character is whitespace."""
        entry = self.get(character)
        return entry.classification.type == "whitespace"

    def is_symbol(self, character: str) -> bool:
        """Checks if the character is a symbol (currency, math, typographic)."""
        entry = self.get(character)
        return entry.classification.type == "symbol"

    def get_uppercase(self, character: str) -> Optional[str]:
        """Returns the uppercase equivalent for letters, or None for non-letters."""
        entry = self.get(character)
        return entry.relationships.uppercase

    def get_lowercase(self, character: str) -> Optional[str]:
        """Returns the lowercase equivalent for letters, or None for non-letters."""
        entry = self.get(character)
        return entry.relationships.lowercase

    def get_alphabet_position(self, character: str) -> Optional[int]:
        """Returns 1..26 for English letters (A=1..Z=26, a=1..z=26), None for non-letters."""
        entry = self.get(character)
        return entry.classification.alphabet_position

    def get_unicode_info(self, character: str) -> Dict[str, str]:
        """Returns Unicode codepoint, name, and general category."""
        entry = self.get(character)
        return {
            "codepoint": entry.identity.unicode_codepoint,
            "name": entry.identity.unicode_name,
            "category": entry.identity.unicode_category,
        }

    def get_examples(self, character: str) -> List[str]:
        """Returns curated example English words for a character."""
        entry = self.get(character)
        return list(entry.examples)

    def to_dict(self) -> Dict[str, Any]:
        """Exports the complete knowledge base to a dictionary representation."""
        return {
            "project": "VEDA",
            "component": "Character Knowledge Base",
            "version": "0.1.0",
            "language_scope": "English",
            "description": "Structured symbolic knowledge layer for English characters.",
            "character_count": len(self._entries),
            "characters": [entry.to_dict() for entry in self._entries.values()],
        }

    def save_to_json(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Saves the structured character knowledge dataset to a JSON file."""
        target_path = Path(path) if path else self.DEFAULT_KNOWLEDGE_JSON
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return target_path

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, character: str) -> bool:
        return self.is_known(character)

    def __repr__(self) -> str:
        return f"CharacterKnowledge(known_characters={len(self._entries)}, language='English')"
