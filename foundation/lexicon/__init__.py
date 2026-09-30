"""
VEDA English Lexical Foundation (Phase 3)

Provides English lexical models, Wiktionary streaming ingestion,
and dictionary indexing from first principles.
"""

from foundation.lexicon.audit import DatasetAuditor, DatasetAuditReport
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.lexicon import Lexicon
from foundation.lexicon.schemas import (
    ExtractionStats,
    LexicalEntry,
    LexicalSense,
    LexiconMetadata,
)
from foundation.lexicon.storage import SqliteLexicon, SqliteLexiconBuilder

__all__ = [
    "Lexicon",
    "WiktionaryExtractor",
    "LexicalEntry",
    "LexicalSense",
    "LexiconMetadata",
    "ExtractionStats",
    "DatasetAuditor",
    "DatasetAuditReport",
    "SqliteLexicon",
    "SqliteLexiconBuilder",
]


