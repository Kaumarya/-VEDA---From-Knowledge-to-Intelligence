"""
VEDA Lexicon Repository (Phase 3 — English Lexical Foundation v0.1)

Provides fast in-memory indexing, POS filtering, dictionary lookup,
and persistence for the English Lexical Foundation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.schemas import ExtractionStats, LexicalEntry, LexiconMetadata
from foundation.words.word import Word


class Lexicon:
    """
    In-memory English Lexicon containing validated words with structured definitions,
    parts of speech, pronunciations, inflections, and semantic relations.
    """

    def __init__(
        self,
        entries: Optional[Iterable[LexicalEntry]] = None,
        metadata: Optional[LexiconMetadata] = None,
        stats: Optional[ExtractionStats] = None,
        registry: Optional[CharacterRegistry] = None,
    ) -> None:
        self._entries: Dict[str, LexicalEntry] = {}
        self._stats: ExtractionStats = stats or ExtractionStats()
        self._registry: Optional[CharacterRegistry] = registry

        if entries:
            for entry in entries:
                self.add_entry(entry)

        if metadata:
            self._metadata = metadata
        else:
            self._metadata = LexiconMetadata(
                word_count=len(self._entries),
                pos_distribution=self._compute_pos_distribution(),
            )

    @property
    def metadata(self) -> LexiconMetadata:
        """Returns the lexicon metadata."""
        return self._metadata

    @property
    def stats(self) -> ExtractionStats:
        """Returns the extraction statistics."""
        return self._stats

    def _compute_pos_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for entry in self._entries.values():
            for pos in entry.parts_of_speech:
                dist[pos] = dist.get(pos, 0) + 1
        return dist

    def add_entry(self, entry: LexicalEntry) -> None:
        """Adds or merges an entry into the lexicon."""
        norm = entry.normalized
        if norm in self._entries:
            self._entries[norm].merge(entry)
        else:
            self._entries[norm] = entry

    def get(
        self, word: Union[str, Word], default: Optional[LexicalEntry] = None
    ) -> Optional[LexicalEntry]:
        """Retrieves a LexicalEntry by word string or Word object."""
        key = word.normalized if isinstance(word, Word) else word.strip().lower()
        return self._entries.get(key, default)

    def has_word(self, word: Union[str, Word]) -> bool:
        """Checks if a word exists in the lexicon."""
        key = word.normalized if isinstance(word, Word) else word.strip().lower()
        return key in self._entries

    def to_word(self, word: Union[str, Word]) -> Optional[Word]:
        """Converts an entry to a rich Word object connected to the Character Registry."""
        entry = self.get(word)
        if entry is None:
            return None
        return entry.to_word(registry=self._registry)

    def filter_by_pos(self, pos: str) -> List[LexicalEntry]:
        """Returns all entries that can function as the specified part of speech."""
        pos_lower = pos.strip().lower()
        return [e for e in self._entries.values() if pos_lower in e.parts_of_speech]

    def words(self) -> List[str]:
        """Returns a sorted list of all canonical normalized words in the lexicon."""
        return sorted(self._entries.keys())

    def entries(self) -> List[LexicalEntry]:
        """Returns a list of all lexical entries."""
        return list(self._entries.values())

    def summary(self) -> Dict[str, Any]:
        """Returns a statistical summary of the lexicon."""
        pos_dist = self._compute_pos_distribution()
        total_defs = sum(len(e.definitions) for e in self._entries.values())
        return {
            "total_words": len(self._entries),
            "total_definitions": total_defs,
            "avg_definitions_per_word": (
                round(total_defs / len(self._entries), 2) if self._entries else 0.0
            ),
            "pos_distribution": pos_dist,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the lexicon to a structured dictionary."""
        d = self._metadata.to_dict()
        d["word_count"] = len(self._entries)
        d["pos_distribution"] = self._compute_pos_distribution()
        d["stats"] = self._stats.to_dict()
        d["words"] = [
            entry.to_dict() for entry in sorted(self._entries.values(), key=lambda e: e.normalized)
        ]
        return d

    def save_to_json(self, file_path: Union[str, Path], indent: int = 2) -> None:
        """Saves the lexicon to a JSON file."""
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        registry: Optional[CharacterRegistry] = None,
    ) -> Lexicon:
        """Deserializes a dictionary into a Lexicon instance."""
        import dataclasses

        entries = [LexicalEntry.from_dict(w) for w in data.get("words", [])]
        metadata = LexiconMetadata.from_dict(data)
        metadata.word_count = len(entries)
        stats_dict = data.get("stats", {})
        if stats_dict:
            stat_fields = {f.name for f in dataclasses.fields(ExtractionStats)}
            filtered_stats = {k: v for k, v in stats_dict.items() if k in stat_fields}
            stats = ExtractionStats(**filtered_stats)
        else:
            stats = ExtractionStats()
        return cls(entries=entries, metadata=metadata, stats=stats, registry=registry)


    @classmethod
    def from_json_file(
        cls,
        file_path: Union[str, Path],
        registry: Optional[CharacterRegistry] = None,
    ) -> Lexicon:
        """Loads a Lexicon from a JSON file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Lexicon file not found: {path}")

        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return cls.from_dict(data, registry=registry)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[LexicalEntry]:
        return iter(self._entries.values())

    def __contains__(self, word: Union[str, Word]) -> bool:
        return self.has_word(word)

    def __getitem__(self, word: Union[str, Word]) -> LexicalEntry:
        entry = self.get(word)
        if entry is None:
            norm = word.normalized if isinstance(word, Word) else str(word).strip().lower()
            raise KeyError(f"Word {norm!r} not found in Lexicon")
        return entry

    def __repr__(self) -> str:
        return f"Lexicon(words={len(self._entries)}, version={self._metadata.version!r})"
