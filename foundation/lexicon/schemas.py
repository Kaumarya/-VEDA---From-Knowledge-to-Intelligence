"""
VEDA Lexicon Schemas (Phase 3 — English Lexical Foundation v0.1)

Defines data structures representing word senses, aggregated lexical entries,
lexicon metadata, and streaming extraction statistics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from foundation.characters.registry import CharacterRegistry
from foundation.words.schemas import WordLexicalData
from foundation.words.word import Word


@dataclass
class LexicalSense:
    """Represents a specific meaning or sense of a word under a given part of speech."""
    pos: str
    glosses: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pos": self.pos,
            "glosses": list(self.glosses),
            "tags": list(self.tags),
            "examples": list(self.examples),
            "categories": list(self.categories),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LexicalSense:
        return cls(
            pos=data.get("pos", "unknown"),
            glosses=list(data.get("glosses", [])),
            tags=list(data.get("tags", [])),
            examples=list(data.get("examples", [])),
            categories=list(data.get("categories", [])),
        )


@dataclass
class LexicalEntry:
    """
    Consolidated dictionary entry for an English word.

    Aggregates multiple senses, parts of speech, pronunciations,
    inflections, synonyms, and antonyms from authoritative sources (Wiktionary).
    """
    word: str
    normalized: str
    language: str = "en"
    parts_of_speech: List[str] = field(default_factory=list)
    primary_pos: Optional[str] = None
    definitions: List[str] = field(default_factory=list)
    definitions_by_pos: Dict[str, List[str]] = field(default_factory=dict)
    senses: List[LexicalSense] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    pronunciations: List[str] = field(default_factory=list)  # IPA transcriptions
    forms: List[str] = field(default_factory=list)          # Inflected forms
    etymology: Optional[str] = None
    sources: List[str] = field(default_factory=lambda: ["Wiktionary"])
    provenance: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.primary_pos is None and self.parts_of_speech:
            self.primary_pos = self.parts_of_speech[0]
        elif self.primary_pos and self.primary_pos not in self.parts_of_speech:
            self.parts_of_speech.insert(0, self.primary_pos)

    def add_sense(self, sense: LexicalSense) -> None:
        """Adds a sense and updates pos, definitions, and definitions_by_pos."""
        self.senses.append(sense)
        if sense.pos and sense.pos not in self.parts_of_speech:
            self.parts_of_speech.append(sense.pos)
            if self.primary_pos is None:
                self.primary_pos = sense.pos

        if sense.pos not in self.definitions_by_pos:
            self.definitions_by_pos[sense.pos] = []

        for g in sense.glosses:
            if g not in self.definitions:
                self.definitions.append(g)
            if g not in self.definitions_by_pos[sense.pos]:
                self.definitions_by_pos[sense.pos].append(g)

    def merge(self, other: LexicalEntry) -> None:
        """Merges another LexicalEntry for the same word."""
        if self.normalized != other.normalized:
            raise ValueError(
                f"Cannot merge mismatched words: {self.normalized!r} vs {other.normalized!r}"
            )

        for pos in other.parts_of_speech:
            if pos not in self.parts_of_speech:
                self.parts_of_speech.append(pos)

        for pos, defs in other.definitions_by_pos.items():
            if pos not in self.definitions_by_pos:
                self.definitions_by_pos[pos] = []
            for d in defs:
                if d not in self.definitions_by_pos[pos]:
                    self.definitions_by_pos[pos].append(d)

        for d in other.definitions:
            if d not in self.definitions:
                self.definitions.append(d)

        for s in other.senses:
            if s not in self.senses:
                self.senses.append(s)

        for syn in other.synonyms:
            if syn not in self.synonyms:
                self.synonyms.append(syn)

        for ant in other.antonyms:
            if ant not in self.antonyms:
                self.antonyms.append(ant)

        for pron in other.pronunciations:
            if pron not in self.pronunciations:
                self.pronunciations.append(pron)

        for form in other.forms:
            if form not in self.forms:
                self.forms.append(form)

        for src in other.sources:
            if src not in self.sources:
                self.sources.append(src)

        if not self.etymology and other.etymology:
            self.etymology = other.etymology

        if not self.provenance and other.provenance:
            self.provenance = dict(other.provenance)

    def is_representable(self, registry: Optional[CharacterRegistry] = None) -> bool:
        """
        Checks whether all characters in the entry are representable
        in the VEDA Character Registry.
        """
        if registry is None:
            registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        return all(registry.contains_char(ch) for ch in self.normalized)

    def unsupported_characters(self, registry: Optional[CharacterRegistry] = None) -> List[str]:
        """
        Returns any characters in the entry that are not supported by the Character Registry.
        """
        if registry is None:
            registry = CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        return [ch for ch in self.normalized if not registry.contains_char(ch)]

    def to_word_lexical_data(self) -> WordLexicalData:
        """Converts into a WordLexicalData dataclass for Word integration."""
        return WordLexicalData(
            part_of_speech=self.primary_pos,
            parts_of_speech=list(self.parts_of_speech),
            definitions=list(self.definitions),
            definitions_by_pos={k: list(v) for k, v in self.definitions_by_pos.items()},
            synonyms=list(self.synonyms),
            antonyms=list(self.antonyms),
            pronunciations=list(self.pronunciations),
            etymology=self.etymology,
        )

    def to_word(self, registry: Optional[CharacterRegistry] = None) -> Word:
        """Converts this lexical entry into a rich Word instance."""
        return Word(
            text=self.word,
            registry=registry,
            normalized=self.normalized,
            language=self.language,
            lexical=self.to_word_lexical_data(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the LexicalEntry to a JSON-compatible dictionary."""
        d: Dict[str, Any] = {
            "word": self.word,
            "normalized": self.normalized,
            "language": self.language,
            "parts_of_speech": list(self.parts_of_speech),
            "primary_pos": self.primary_pos,
            "definitions": list(self.definitions),
            "definitions_by_pos": {k: list(v) for k, v in self.definitions_by_pos.items()},
            "senses": [s.to_dict() for s in self.senses],
            "synonyms": list(self.synonyms),
            "antonyms": list(self.antonyms),
            "pronunciations": list(self.pronunciations),
            "forms": list(self.forms),
            "etymology": self.etymology,
            "sources": list(self.sources),
        }
        if self.provenance is not None:
            d["provenance"] = dict(self.provenance)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LexicalEntry:
        """Deserializes a dictionary into a LexicalEntry instance."""
        senses = [LexicalSense.from_dict(s) for s in data.get("senses", [])]
        return cls(
            word=data["word"],
            normalized=data.get("normalized", data["word"].strip().lower()),
            language=data.get("language", "en"),
            parts_of_speech=list(data.get("parts_of_speech", [])),
            primary_pos=data.get("primary_pos"),
            definitions=list(data.get("definitions", [])),
            definitions_by_pos={
                k: list(v) for k, v in data.get("definitions_by_pos", {}).items()
            },
            senses=senses,
            synonyms=list(data.get("synonyms", [])),
            antonyms=list(data.get("antonyms", [])),
            pronunciations=list(data.get("pronunciations", [])),
            forms=list(data.get("forms", [])),
            etymology=data.get("etymology"),
            sources=list(data.get("sources", ["Wiktionary"])),
            provenance=data.get("provenance"),
        )


@dataclass
class ExtractionStats:
    """Statistics tracking streaming ingestion metrics, data quality, and performance."""
    total_lines_read: int = 0
    english_records: int = 0
    non_english_skipped: int = 0
    valid_candidates: int = 0
    invalid_candidates_skipped: int = 0
    unique_words_aggregated: int = 0
    elapsed_seconds: float = 0.0
    # Data quality & rejection statistics
    malformed_json_records: int = 0
    missing_word_records: int = 0
    missing_pos_records: int = 0
    missing_lang_records: int = 0
    duplicate_records: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_text(self) -> str:
        rate = (
            (self.total_lines_read / self.elapsed_seconds)
            if self.elapsed_seconds > 0
            else 0.0
        )
        return (
            f"Extraction Stats:\n"
            f"  Lines Read:              {self.total_lines_read:,}\n"
            f"  English Records:         {self.english_records:,}\n"
            f"  Non-English Skipped:     {self.non_english_skipped:,}\n"
            f"  Valid Candidates:        {self.valid_candidates:,}\n"
            f"  Invalid Candidates Skip: {self.invalid_candidates_skipped:,}\n"
            f"  Unique Words Aggregated: {self.unique_words_aggregated:,}\n"
            f"  Duplicate Records:       {self.duplicate_records:,}\n"
            f"  Malformed JSON Skipped:  {self.malformed_json_records:,}\n"
            f"  Elapsed Time:            {self.elapsed_seconds:.4f}s ({rate:,.1f} lines/sec)"
        )


@dataclass
class LexiconMetadata:
    """Header and audit metadata for the serialized VEDA Lexicon."""
    project: str = "VEDA"
    component: str = "Lexical Foundation"
    version: str = "0.1.0"
    schema_version: str = "0.1.0"
    extractor_version: str = "0.1.0"
    normalization_version: str = "0.1.0"
    language_scope: str = "English"
    word_count: int = 0
    pos_distribution: Dict[str, int] = field(default_factory=dict)
    sources: List[str] = field(default_factory=lambda: ["Wiktionary (Wiktextract)"])
    source_dataset: str = "Wiktionary (Wiktextract)"
    created_at: Optional[str] = None
    processing_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LexiconMetadata:
        return cls(
            project=data.get("project", "VEDA"),
            component=data.get("component", "Lexical Foundation"),
            version=data.get("version", "0.1.0"),
            schema_version=data.get("schema_version", data.get("version", "0.1.0")),
            extractor_version=data.get("extractor_version", "0.1.0"),
            normalization_version=data.get("normalization_version", "0.1.0"),
            language_scope=data.get("language_scope", "English"),
            word_count=data.get("word_count", 0),
            pos_distribution=dict(data.get("pos_distribution", {})),
            sources=list(data.get("sources", ["Wiktionary (Wiktextract)"])),
            source_dataset=data.get("source_dataset", "Wiktionary (Wiktextract)"),
            created_at=data.get("created_at"),
            processing_config=dict(data.get("processing_config", {})),
        )

