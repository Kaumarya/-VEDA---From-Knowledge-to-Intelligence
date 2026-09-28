"""
VEDA Character Registry Module (Phase 1 — English Character Foundation)

This module provides data structures and loader utilities for the VEDA Character Registry.
The registry maintains the canonical English-oriented character inventory,
special tokens, and associated Unicode metadata from first principles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set


@dataclass(frozen=True)
class SpecialTokenEntry:
    """Represents a special token within the VEDA tokenization architecture."""
    id: int
    token: str
    purpose: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class CharacterEntry:
    """Represents a registered character with its Unicode and linguistic metadata."""
    id: int
    character: str
    unicode_codepoint: str
    unicode_name: str
    unicode_category: str
    type: str
    case: Optional[str]
    normalization: str
    language_scope: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "character": self.character,
            "unicode_codepoint": self.unicode_codepoint,
            "unicode_name": self.unicode_name,
            "unicode_category": self.unicode_category,
            "type": self.type,
            "case": self.case,
            "normalization": self.normalization,
            "language_scope": self.language_scope,
        }


class CharacterRegistry:
    """
    In-memory representation of the VEDA Character Registry.

    Loads and validates the character definitions and special tokens
    defined in veda_characters_v0.1.json.
    """

    def __init__(
        self,
        project: str,
        component: str,
        version: str,
        language_scope: str,
        description: str,
        design_note: str,
        special_tokens: Sequence[SpecialTokenEntry],
        characters: Sequence[CharacterEntry],
    ) -> None:
        self.project = project
        self.component = component
        self.version = version
        self.language_scope = language_scope
        self.description = description
        self.design_note = design_note

        self._special_tokens: List[SpecialTokenEntry] = list(special_tokens)
        self._characters: List[CharacterEntry] = list(characters)

        # Lookup structures
        self._char_by_char: Dict[str, CharacterEntry] = {
            entry.character: entry for entry in self._characters
        }
        self._char_by_id: Dict[int, CharacterEntry] = {
            entry.id: entry for entry in self._characters
        }
        self._special_by_token: Dict[str, SpecialTokenEntry] = {
            entry.token: entry for entry in self._special_tokens
        }
        self._special_by_id: Dict[int, SpecialTokenEntry] = {
            entry.id: entry for entry in self._special_tokens
        }

        # Validation
        self.validate()

    @classmethod
    def from_json_file(cls, path: str | Path) -> CharacterRegistry:
        """Loads and parses the Character Registry from a JSON file."""
        file_path = Path(path).resolve()
        if not file_path.is_file():
            raise FileNotFoundError(f"Character registry file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CharacterRegistry:
        """Constructs the registry from a parsed JSON dictionary."""
        special_tokens = [
            SpecialTokenEntry(
                id=item["id"],
                token=item["token"],
                purpose=item["purpose"],
            )
            for item in data.get("special_tokens", [])
        ]

        characters = [
            CharacterEntry(
                id=item["id"],
                character=item["character"],
                unicode_codepoint=item["unicode_codepoint"],
                unicode_name=item["unicode_name"],
                unicode_category=item["unicode_category"],
                type=item["type"],
                case=item.get("case"),
                normalization=item.get("normalization", item["character"]),
                language_scope=item.get("language_scope", "en"),
            )
            for item in data.get("characters", [])
        ]

        return cls(
            project=data.get("project", "VEDA"),
            component=data.get("component", "Character Registry"),
            version=data.get("version", "0.1.0"),
            language_scope=data.get("language_scope", "English"),
            description=data.get("description", ""),
            design_note=data.get("design_note", ""),
            special_tokens=special_tokens,
            characters=characters,
        )

    def validate(self) -> None:
        """
        Validates internal registry integrity:
        - Character entries must be single Unicode characters.
        - Characters must be strictly unique.
        - Special tokens must be strictly unique.
        - Special token names must not collide with characters.
        - Character IDs must be unique and contiguous from 0 to N-1.
        """
        if len(self._characters) != len(self._char_by_char):
            duplicates = [
                c.character for c in self._characters if self._characters.count(c) > 1
            ]
            raise ValueError(f"Duplicate characters found in registry: {set(duplicates)}")

        if len(self._characters) != len(self._char_by_id):
            duplicate_ids = [
                c.id for c in self._characters if [x.id for x in self._characters].count(c.id) > 1
            ]
            raise ValueError(f"Duplicate character IDs found in registry: {set(duplicate_ids)}")

        expected_char_ids = list(range(len(self._characters)))
        actual_char_ids = sorted(self._char_by_id.keys())
        if actual_char_ids != expected_char_ids:
            raise ValueError(
                f"Character IDs are not contiguous 0..N-1. Found {actual_char_ids[:5]}...{actual_char_ids[-5:]}"
            )

        for entry in self._characters:
            if len(entry.character) != 1:
                raise ValueError(
                    f"Character entry must be single Unicode character: id={entry.id}, repr={repr(entry.character)}"
                )

        special_token_names = set(self._special_by_token.keys())
        if len(special_token_names) != len(self._special_tokens):
            raise ValueError("Duplicate special tokens detected in registry.")

        # Ensure no overlap between special token strings and single characters
        registered_chars = set(self._char_by_char.keys())
        collision = special_token_names.intersection(registered_chars)
        if collision:
            raise ValueError(f"Collision between special token and character: {collision}")

    # Properties & Accessors
    @property
    def character_count(self) -> int:
        """Total number of registered characters."""
        return len(self._characters)

    @property
    def special_token_count(self) -> int:
        """Total number of registered special tokens."""
        return len(self._special_tokens)

    @property
    def characters(self) -> List[CharacterEntry]:
        """Returns a copy of all character entries."""
        return list(self._characters)

    @property
    def special_tokens(self) -> List[SpecialTokenEntry]:
        """Returns a copy of all special token entries."""
        return list(self._special_tokens)

    def contains_char(self, char: str) -> bool:
        """Checks if a character is part of this registry."""
        return char in self._char_by_char

    def get_character(self, char: str) -> Optional[CharacterEntry]:
        """Retrieves a CharacterEntry by character string."""
        return self._char_by_char.get(char)

    def get_character_by_id(self, char_id: int) -> Optional[CharacterEntry]:
        """Retrieves a CharacterEntry by character ID."""
        return self._char_by_id.get(char_id)

    def get_special_token(self, token: str) -> Optional[SpecialTokenEntry]:
        """Retrieves a SpecialTokenEntry by token string."""
        return self._special_by_token.get(token)

    def __len__(self) -> int:
        return len(self._characters)

    def __contains__(self, char: str) -> bool:
        return self.contains_char(char)

    def __repr__(self) -> str:
        return (
            f"CharacterRegistry(version={self.version!r}, "
            f"characters={len(self._characters)}, "
            f"special_tokens={len(self._special_tokens)})"
        )
