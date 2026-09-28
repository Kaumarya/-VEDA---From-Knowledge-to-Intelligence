"""
VEDA Foundation — Character Subsystem
"""

from foundation.characters.knowledge import CharacterKnowledge
from foundation.characters.knowledge_builder import CharacterKnowledgeBuilder
from foundation.characters.registry import (
    CharacterEntry,
    CharacterRegistry,
    SpecialTokenEntry,
)
from foundation.characters.schemas import (
    CharacterClassification,
    CharacterIdentity,
    CharacterKnowledgeEntry,
    CharacterLanguage,
    CharacterLinguistic,
    CharacterRelationships,
)

__all__ = [
    "CharacterEntry",
    "CharacterRegistry",
    "SpecialTokenEntry",
    "CharacterKnowledge",
    "CharacterKnowledgeBuilder",
    "CharacterIdentity",
    "CharacterClassification",
    "CharacterRelationships",
    "CharacterLanguage",
    "CharacterLinguistic",
    "CharacterKnowledgeEntry",
]
