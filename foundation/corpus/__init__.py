"""
VEDA Corpus Architecture & Pipeline (Phase 4 — Training Corpus Architecture)

Provides contracts, normalization, quality filtering, segmentation, deduplication,
deterministic splitting, and storage for the VEDA training corpus.
"""

from foundation.corpus.deduplication import DeduplicationEngine, DeduplicationStats
from foundation.corpus.filtering import FilterDecision, QualityFilter, QualityMetrics
from foundation.corpus.manifest import CorpusManifest, ManifestBuilder
from foundation.corpus.normalization import NormalizationResult, TextNormalizer
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusRecord,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
    RecordProvenance,
    RejectionReason,
    RejectionRecord,
    Sentence,
    TextSegment,
)
from foundation.corpus.segmentation import DocumentSegmenter
from foundation.corpus.sources import SourceRegistry
from foundation.corpus.splitting import DeterministicSplitter
from foundation.corpus.storage import CorpusReader, CorpusWriter

__all__ = [
    "CorpusSource",
    "SourceRegistry",
    "CorpusDocument",
    "TextSegment",
    "Sentence",
    "RecordProvenance",
    "CorpusRecord",
    "RejectionRecord",
    "LicensingStatus",
    "RejectionReason",
    "DatasetSplit",
    "TextNormalizer",
    "NormalizationResult",
    "QualityFilter",
    "QualityMetrics",
    "FilterDecision",
    "DocumentSegmenter",
    "DeduplicationEngine",
    "DeduplicationStats",
    "DeterministicSplitter",
    "CorpusWriter",
    "CorpusReader",
    "CorpusManifest",
    "ManifestBuilder",
    "CorpusPipeline",
]
