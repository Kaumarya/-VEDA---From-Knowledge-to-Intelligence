"""
VEDA Wiktionary Streaming Extractor (Phase 3 — English Lexical Foundation v0.1)

Provides memory-safe streaming extraction and aggregation of Wiktionary/Wiktextract
datasets from first principles.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from foundation.lexicon.lexicon import Lexicon
from foundation.lexicon.schemas import ExtractionStats, LexicalEntry, LexicalSense
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word


class WiktionaryExtractor:
    """
    Streaming input parser and lexical aggregator for Wiktionary/Wiktextract JSONL datasets.

    Principles & Memory Contract:
    - Streaming Input Parser: reads line-by-line in O(1) buffer memory.
    - Aggregation Memory: In-memory dictionary aggregation scales as O(V), where V is the
      number of unique normalized English words. It does not load the raw dataset into memory.
    - Strict English filtering: filters non-English records.
    - Word candidate validation: utilizes WordAnalyzer to ensure pure plain English candidates.
    - Lossless Aggregation: consolidates multiple parts-of-speech and senses for identical words.
    - Provenance Preservation: attaches source dataset and version metadata.
    """


    def __init__(self, analyzer: Optional[WordAnalyzer] = None) -> None:
        self.analyzer = analyzer or WordAnalyzer()

    def stream_raw_lines(
        self,
        file_path: Union[str, Path],
        max_lines: Optional[int] = None,
    ) -> Iterator[str]:
        """
        Streams raw lines from a file using UTF-8 with BOM tolerance (utf-8-sig).
        Yields non-empty stripped lines.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        lines_read = 0
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                yield stripped
                lines_read += 1
                if max_lines is not None and lines_read >= max_lines:
                    break

    def stream_raw_records(
        self,
        file_path: Union[str, Path],
        max_lines: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Streams parsed JSON records line-by-line.
        """
        for line in self.stream_raw_lines(file_path, max_lines=max_lines):
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    yield record
            except json.JSONDecodeError:
                continue

    @staticmethod
    def is_english(record: Dict[str, Any]) -> bool:
        """Determines whether a Wiktextract record is English."""
        lang = record.get("lang")
        lang_code = record.get("lang_code")
        return lang == "English" or lang_code == "en"

    @staticmethod
    def _clean_text(s: str) -> str:
        """
        Repairs accidental double-encoded UTF-8 (mojibake) if present.
        E.g., when UTF-8 bytes were interpreted as cp1252/latin-1 and re-encoded.
        """
        if not isinstance(s, str):
            return s
        try:
            if any(ord(c) > 127 for c in s):
                return s.encode("cp1252").decode("utf-8")
        except Exception:
            pass
        return s

    def parse_record(self, record: Dict[str, Any]) -> LexicalEntry:
        """
        Parses a single Wiktextract JSON record into an unaggregated LexicalEntry.
        """
        raw_word = str(record.get("word", "")).strip()
        norm_word = self.analyzer.normalize_word(raw_word)
        pos = str(record.get("pos", "unknown")).strip().lower()

        # Parse senses
        senses: List[LexicalSense] = []
        definitions: List[str] = []
        synonyms: List[str] = []
        antonyms: List[str] = []

        for s in record.get("senses", []):
            if not isinstance(s, dict):
                continue

            glosses = [
                self._clean_text(g.strip())
                for g in s.get("glosses", [])
                if isinstance(g, str) and g.strip()
            ]
            tags = [t.strip() for t in s.get("tags", []) if isinstance(t, str) and t.strip()]
            examples = [
                self._clean_text(ex.get("text", "").strip())
                for ex in s.get("examples", [])
                if isinstance(ex, dict) and ex.get("text")
            ]
            categories = [
                c.strip()
                for c in s.get("categories", [])
                if isinstance(c, str) and c.strip()
            ]

            if glosses:
                senses.append(
                    LexicalSense(
                        pos=pos,
                        glosses=glosses,
                        tags=tags,
                        examples=examples,
                        categories=categories,
                    )
                )
                for g in glosses:
                    if g not in definitions:
                        definitions.append(g)

            # Sense-level synonyms/antonyms
            for syn in s.get("synonyms", []):
                syn_word = syn.get("word") if isinstance(syn, dict) else str(syn)
                if syn_word and syn_word not in synonyms:
                    synonyms.append(self._clean_text(syn_word.strip()))

            for ant in s.get("antonyms", []):
                ant_word = ant.get("word") if isinstance(ant, dict) else str(ant)
                if ant_word and ant_word not in antonyms:
                    antonyms.append(self._clean_text(ant_word.strip()))

        # Top-level synonyms
        for syn in record.get("synonyms", []):
            syn_word = syn.get("word") if isinstance(syn, dict) else str(syn)
            if syn_word and syn_word not in synonyms:
                synonyms.append(self._clean_text(syn_word.strip()))

        # Top-level antonyms
        for ant in record.get("antonyms", []):
            ant_word = ant.get("word") if isinstance(ant, dict) else str(ant)
            if ant_word and ant_word not in antonyms:
                antonyms.append(self._clean_text(ant_word.strip()))

        # Pronunciations (IPA)
        pronunciations: List[str] = []
        for sound in record.get("sounds", []):
            if isinstance(sound, dict):
                ipa = sound.get("ipa")
                if ipa and isinstance(ipa, str) and ipa.strip():
                    cleaned_ipa = self._clean_text(ipa.strip())
                    if cleaned_ipa not in pronunciations:
                        pronunciations.append(cleaned_ipa)

        # Forms (inflections)
        forms: List[str] = []
        for form_entry in record.get("forms", []):
            if isinstance(form_entry, dict):
                f_val = form_entry.get("form")
                if f_val and isinstance(f_val, str) and f_val.strip() and f_val.strip() not in forms:
                    forms.append(f_val.strip())

        # Etymology
        etymology = record.get("etymology_text") or record.get("etymology")
        if isinstance(etymology, str):
            etymology = self._clean_text(etymology.strip()) or None
        else:
            etymology = None

        definitions_by_pos = {pos: list(definitions)} if definitions else {}

        provenance = {
            "source_dataset": "Wiktionary (Wiktextract)",
            "extractor_version": "0.1.0",
            "source_lang": record.get("lang", "English"),
            "source_lang_code": record.get("lang_code", "en"),
        }

        return LexicalEntry(
            word=raw_word,
            normalized=norm_word,
            language="en",
            parts_of_speech=[pos] if pos != "unknown" else [],
            primary_pos=pos if pos != "unknown" else None,
            definitions=definitions,
            definitions_by_pos=definitions_by_pos,
            senses=senses,
            synonyms=synonyms,
            antonyms=antonyms,
            pronunciations=pronunciations,
            forms=forms,
            etymology=etymology,
            sources=["Wiktionary"],
            provenance=provenance,
        )

    def extract_lexicon(
        self,
        file_path: Union[str, Path],
        max_lines: Optional[int] = None,
        validate_candidates: bool = True,
        progress_callback: Optional[Callable[[ExtractionStats], None]] = None,
        report_every: int = 5000,
    ) -> Lexicon:
        """
        Streaming pipeline that aggregates multi-record Wiktionary entries into a Lexicon.

        Memory Usage:
        - Streamed line-by-line from disk.
        - Memory consumption is strictly proportional to the number of distinct English words.
        """
        import datetime
        from foundation.lexicon.schemas import LexiconMetadata

        start_time = time.perf_counter()
        stats = ExtractionStats()
        aggregation: Dict[str, LexicalEntry] = {}

        for line in self.stream_raw_lines(file_path, max_lines=max_lines):
            stats.total_lines_read += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                stats.malformed_json_records += 1
                continue

            if not isinstance(record, dict):
                stats.malformed_json_records += 1
                continue

            # Step 1: English Language Filter
            if not self.is_english(record):
                stats.non_english_skipped += 1
                continue

            stats.english_records += 1

            raw_word = str(record.get("word", "")).strip()
            if not raw_word:
                stats.missing_word_records += 1
                continue

            # Step 2: Word Candidate Validation
            if validate_candidates:
                val = self.analyzer.validate_candidate(raw_word)
                if not val.is_valid:
                    stats.invalid_candidates_skipped += 1
                    continue

            stats.valid_candidates += 1

            # Step 3: Parse Record
            entry = self.parse_record(record)
            norm = entry.normalized

            # Step 4: Multi-POS / Multi-sense Aggregation
            if norm in aggregation:
                stats.duplicate_records += 1
                aggregation[norm].merge(entry)
            else:
                aggregation[norm] = entry

            # Periodic progress reporting
            if (
                progress_callback is not None
                and stats.total_lines_read % report_every == 0
            ):
                stats.elapsed_seconds = time.perf_counter() - start_time
                stats.unique_words_aggregated = len(aggregation)
                progress_callback(stats)

        stats.elapsed_seconds = time.perf_counter() - start_time
        stats.unique_words_aggregated = len(aggregation)

        metadata = LexiconMetadata(
            project="VEDA",
            component="Lexical Foundation",
            version="0.1.0",
            schema_version="0.1.0",
            extractor_version="0.1.0",
            normalization_version="0.1.0",
            language_scope="English",
            word_count=len(aggregation),
            pos_distribution={},
            sources=["Wiktionary (Wiktextract)"],
            source_dataset=str(file_path),
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            processing_config={
                "max_lines": max_lines,
                "validate_candidates": validate_candidates,
            },
        )

        return Lexicon(
            entries=aggregation.values(),
            metadata=metadata,
            stats=stats,
            registry=self.analyzer.registry,
        )


    def stream_words(
        self,
        file_path: Union[str, Path],
        max_lines: Optional[int] = None,
        validate_candidates: bool = True,
    ) -> Iterator[Word]:
        """
        Yields Word instances directly from the streaming Wiktextract file.
        Useful for continuous corpus streaming without intermediate lexicon persistence.
        """
        for record in self.stream_raw_records(file_path, max_lines=max_lines):
            if not self.is_english(record):
                continue

            raw_word = str(record.get("word", "")).strip()
            if validate_candidates and not self.analyzer.is_word_candidate(raw_word):
                continue

            entry = self.parse_record(record)
            yield entry.to_word(registry=self.analyzer.registry)
