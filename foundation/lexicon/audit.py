"""
VEDA Dataset Audit Module (Phase 3 — English Lexical Foundation v0.1)

Provides comprehensive inspection, character distribution profiling,
orthographic validation, memory tracking, and storage estimation for
Wiktextract and derived VEDA datasets.
"""

from __future__ import annotations

import json
import os
import time
import tracemalloc
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from foundation.characters.registry import CharacterRegistry
from foundation.words.analyzer import WordAnalyzer


@dataclass
class DatasetAuditReport:
    """Consolidated audit report containing empirical dataset measurements."""
    input_file: str
    file_size_bytes: int
    total_lines_read: int
    english_records: int
    non_english_records: int
    malformed_json_records: int
    missing_fields: Dict[str, int]
    valid_candidates: int
    rejected_candidates: int
    rejection_reasons: Dict[str, int]
    unique_normalized_words: int
    duplicate_records: int
    pos_distribution: Dict[str, int]
    definitions_count: int
    avg_definitions_per_word: float
    max_definitions_in_word: int
    examples_count: int
    forms_count: int
    pronunciations_count: int
    synonyms_count: int
    antonyms_count: int
    etymology_count: int
    unicode_stats: Dict[str, Any]
    unsupported_chars_freq: Dict[str, int]
    length_stats: Dict[str, Any]
    performance: Dict[str, Any]
    storage_projections: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_text(self) -> str:
        """Formats the audit metrics into an aligned, human-readable terminal report."""
        sep = "=" * 70
        sub_sep = "-" * 70
        lines: List[str] = [
            sep,
            "                   VEDA DATASET AUDIT REPORT",
            sep,
            f"{'Target File:':<30} {self.input_file}",
            f"{'File Size:':<30} {self.file_size_bytes:,} bytes ({self.file_size_bytes / (1024*1024):.2f} MB)",
            f"{'Total Lines Read:':<30} {self.total_lines_read:,}",
            f"{'English Records:':<30} {self.english_records:,}",
            f"{'Non-English Filtered:':<30} {self.non_english_records:,}",
            f"{'Malformed JSON Records:':<30} {self.malformed_json_records:,}",
            sub_sep,
            "1. WORD CANDIDATE VALIDATION (v0.1 Plain English Policy)",
            f"{'Valid v0.1 Candidates:':<30} {self.valid_candidates:,}",
            f"{'Rejected Candidates:':<30} {self.rejected_candidates:,}",
            f"{'Unique Normalized Words:':<30} {self.unique_normalized_words:,}",
            f"{'Duplicate / Repeated Records:':<30} {self.duplicate_records:,}",
        ]

        if self.rejection_reasons:
            lines.append("  Rejection Breakdown:")
            for reason, cnt in sorted(self.rejection_reasons.items(), key=lambda x: -x[1]):
                lines.append(f"    - {reason:<26} {cnt:,}")

        lines.extend([
            sub_sep,
            "2. UNICODE & ORTHOGRAPHY CHARACTERISTICS",
            f"{'ASCII-Only Words:':<30} {self.unicode_stats.get('ascii_words', 0):,}",
            f"{'Non-ASCII Latin Words:':<30} {self.unicode_stats.get('latin_accented_words', 0):,}",
            f"{'Combining Marks:':<30} {self.unicode_stats.get('combining_mark_words', 0):,}",
            f"{'Hyphenated Words:':<30} {self.unicode_stats.get('hyphenated_words', 0):,}",
            f"{'Apostrophe Words:':<30} {self.unicode_stats.get('apostrophe_words', 0):,}",
            f"{'Punctuation Words:':<30} {self.unicode_stats.get('other_punctuation_words', 0):,}",
            f"{'Non-Latin Scripts:':<30} {self.unicode_stats.get('non_latin_script_words', 0):,}",
            f"{'Symbols & Emojis:':<30} {self.unicode_stats.get('symbol_or_emoji_words', 0):,}",
            f"{'Registry-Representable:':<30} {self.unicode_stats.get('representable_words', 0):,}",
            f"{'Unrepresentable Words:':<30} {self.unicode_stats.get('unrepresentable_words', 0):,}",
        ])

        if self.unsupported_chars_freq:
            lines.append("  Unsupported Characters Encountered:")
            for char, freq in sorted(self.unsupported_chars_freq.items(), key=lambda x: -x[1])[:10]:
                code = f"U+{ord(char):04X}"
                name = unicodedata.name(char, "UNKNOWN")
                lines.append(f"    - {char!r:<5} {code} ({name}): {freq:,} occurrences")

        lines.extend([
            sub_sep,
            "3. LEXICAL CONTENT STATISTICS",
            f"{'Total Definitions:':<30} {self.definitions_count:,}",
            f"{'Avg Definitions / Word:':<30} {self.avg_definitions_per_word:.2f}",
            f"{'Max Definitions in a Word:':<30} {self.max_definitions_in_word:,}",
            f"{'Example Sentences:':<30} {self.examples_count:,}",
            f"{'Inflected Forms:':<30} {self.forms_count:,}",
            f"{'Pronunciations (IPA):':<30} {self.pronunciations_count:,}",
            f"{'Synonyms Extracted:':<30} {self.synonyms_count:,}",
            f"{'Antonyms Extracted:':<30} {self.antonyms_count:,}",
            f"{'Etymologies Extracted:':<30} {self.etymology_count:,}",
        ])

        if self.pos_distribution:
            lines.append("  Parts of Speech Breakdown:")
            for pos, count in sorted(self.pos_distribution.items(), key=lambda x: -x[1])[:8]:
                lines.append(f"    - {pos:<15} {count:,}")

        lines.extend([
            sub_sep,
            "4. WORD LENGTH DISTRIBUTION",
            f"{'Min Length:':<30} {self.length_stats.get('min_length', 0)}",
            f"{'Max Length:':<30} {self.length_stats.get('max_length', 0)}",
            f"{'Average Length:':<30} {self.length_stats.get('avg_length', 0.0):.2f}",
            "  Length Buckets:",
        ])
        for bucket, cnt in self.length_stats.get("buckets", {}).items():
            lines.append(f"    - {bucket:<15} {cnt:,}")

        lines.extend([
            sub_sep,
            "5. PERFORMANCE & MEMORY METRICS",
            f"{'Elapsed Time:':<30} {self.performance.get('elapsed_seconds', 0.0):.4f}s",
            f"{'Throughput:':<30} {self.performance.get('lines_per_sec', 0.0):,.1f} lines/sec",
            f"{'Peak Tracemalloc Memory:':<30} {self.performance.get('peak_memory_mb', 0.0):.2f} MB",
            sub_sep,
            "6. ESTIMATED SERIALIZED STORAGE",
            f"{'JSON (Monolithic):':<30} ~{self.storage_projections.get('json_mb', 0.0):.3f} MB",
            f"{'JSONL (Streaming Lines):':<30} ~{self.storage_projections.get('jsonl_mb', 0.0):.3f} MB",
            f"{'SQLite (Indexed DB):':<30} ~{self.storage_projections.get('sqlite_mb', 0.0):.3f} MB",
            sep,
        ])

        return "\n".join(lines)


class DatasetAuditor:
    """
    Streaming analyzer that profiles raw dataset quality, character composition,
    and storage requirements without loading the full file into memory.
    """

    def __init__(
        self,
        registry: Optional[CharacterRegistry] = None,
        analyzer: Optional[WordAnalyzer] = None,
    ) -> None:
        self.registry = registry or CharacterRegistry.from_json_file("veda_characters_v0.1.json")
        self.analyzer = analyzer or WordAnalyzer(registry=self.registry)

    def audit_file(
        self,
        file_path: Union[str, Path],
        max_lines: Optional[int] = None,
    ) -> DatasetAuditReport:
        """
        Executes a complete streaming audit of a JSONL dataset file.
        """
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        file_size = path.stat().st_size

        # Performance and memory tracking
        tracemalloc.start()
        start_time = time.perf_counter()

        total_lines = 0
        english_records = 0
        non_english_records = 0
        malformed_json_records = 0
        missing_fields: Dict[str, int] = {
            "missing_word": 0,
            "missing_lang": 0,
            "missing_pos": 0,
            "empty_senses": 0,
        }

        valid_candidates = 0
        rejected_candidates = 0
        rejection_reasons: Dict[str, int] = {}

        seen_words: Set[str] = set()
        duplicate_records = 0

        pos_dist: Dict[str, int] = {}
        total_definitions = 0
        max_defs_in_word = 0
        examples_count = 0
        forms_count = 0
        pronunciations_count = 0
        synonyms_count = 0
        antonyms_count = 0
        etymology_count = 0

        # Unicode categorization
        ascii_words = 0
        latin_accented_words = 0
        combining_mark_words = 0
        hyphenated_words = 0
        apostrophe_words = 0
        other_punct_words = 0
        non_latin_script_words = 0
        symbol_or_emoji_words = 0
        representable_words = 0
        unrepresentable_words = 0
        unsupported_chars_freq: Dict[str, int] = {}

        lengths: List[int] = []

        # Sample serialization accumulator for storage projection
        sample_serialized_bytes_json = 0
        sample_serialized_count = 0

        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue

                total_lines += 1

                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    malformed_json_records += 1
                    continue

                if not isinstance(record, dict):
                    malformed_json_records += 1
                    continue

                # Missing field audits
                raw_word = str(record.get("word", "")).strip()
                if not raw_word:
                    missing_fields["missing_word"] += 1

                lang = record.get("lang")
                lang_code = record.get("lang_code")
                if not lang and not lang_code:
                    missing_fields["missing_lang"] += 1

                pos = record.get("pos")
                if not pos:
                    missing_fields["missing_pos"] += 1

                senses = record.get("senses", [])
                if not senses:
                    missing_fields["empty_senses"] += 1

                # Language filtering
                is_eng = (lang == "English" or lang_code == "en")
                if not is_eng:
                    non_english_records += 1
                    continue

                english_records += 1

                # Word candidate validation (v0.1 orthography)
                val = self.analyzer.validate_candidate(raw_word)
                norm_word = self.analyzer.normalize_word(raw_word)

                if val.is_valid:
                    valid_candidates += 1
                else:
                    rejected_candidates += 1
                    rejection_reasons[val.reason] = rejection_reasons.get(val.reason, 0) + 1

                # Duplicate tracking
                if norm_word in seen_words:
                    duplicate_records += 1
                else:
                    seen_words.add(norm_word)

                # Length tracking
                word_len = len(norm_word)
                lengths.append(word_len)

                # Unicode profiling
                if raw_word.isascii():
                    ascii_words += 1
                else:
                    # Check if combining marks present
                    if any(unicodedata.combining(c) for c in raw_word):
                        combining_mark_words += 1
                    if any(unicodedata.category(c).startswith("L") for c in raw_word):
                        if all("LATIN" in unicodedata.name(c, "").upper() for c in raw_word if unicodedata.category(c).startswith("L")):
                            latin_accented_words += 1
                        else:
                            non_latin_script_words += 1
                    elif any(unicodedata.category(c).startswith(("S", "C")) for c in raw_word):
                        symbol_or_emoji_words += 1

                if "-" in raw_word:
                    hyphenated_words += 1
                if "'" in raw_word or "’" in raw_word:
                    apostrophe_words += 1
                if any(c in "!?,.;:()[]{}\"/\\" for c in raw_word):
                    other_punct_words += 1

                # Registry support profiling
                is_rep, unsupp = self.analyzer.check_character_support(norm_word)
                if is_rep:
                    representable_words += 1
                else:
                    unrepresentable_words += 1
                    for uc in unsupp:
                        unsupported_chars_freq[uc] = unsupported_chars_freq.get(uc, 0) + 1

                # Lexical content metrics
                pos_str = str(pos or "unknown").strip().lower()
                pos_dist[pos_str] = pos_dist.get(pos_str, 0) + 1

                word_defs = 0
                for s in senses:
                    if isinstance(s, dict):
                        glosses = s.get("glosses", [])
                        word_defs += len(glosses)
                        examples = s.get("examples", [])
                        examples_count += len(examples)
                        synonyms_count += len(s.get("synonyms", []))
                        antonyms_count += len(s.get("antonyms", []))

                total_definitions += word_defs
                if word_defs > max_defs_in_word:
                    max_defs_in_word = word_defs

                # Top-level collections
                synonyms_count += len(record.get("synonyms", []))
                antonyms_count += len(record.get("antonyms", []))
                pronunciations_count += len(record.get("sounds", []))
                forms_count += len(record.get("forms", []))
                if record.get("etymology_text"):
                    etymology_count += 1

                # Sample serialization size tracking (first 50 records)
                if sample_serialized_count < 50:
                    entry = self.analyzer.create_word(raw_word).to_dict()
                    sample_serialized_bytes_json += len(json.dumps(entry, ensure_ascii=False).encode("utf-8"))
                    sample_serialized_count += 1

                if max_lines is not None and total_lines >= max_lines:
                    break

        elapsed = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        unique_count = len(seen_words)
        avg_defs = (total_definitions / unique_count) if unique_count > 0 else 0.0

        # Word length buckets
        length_buckets: Dict[str, int] = {
            "<= 3 chars": sum(1 for l in lengths if l <= 3),
            "4 - 6 chars": sum(1 for l in lengths if 4 <= l <= 6),
            "7 - 10 chars": sum(1 for l in lengths if 7 <= l <= 10),
            "11 - 15 chars": sum(1 for l in lengths if 11 <= l <= 15),
            "> 15 chars": sum(1 for l in lengths if l > 15),
        }
        length_stats = {
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "avg_length": (sum(lengths) / len(lengths)) if lengths else 0.0,
            "buckets": length_buckets,
        }

        unicode_stats = {
            "ascii_words": ascii_words,
            "latin_accented_words": latin_accented_words,
            "combining_mark_words": combining_mark_words,
            "hyphenated_words": hyphenated_words,
            "apostrophe_words": apostrophe_words,
            "other_punctuation_words": other_punct_words,
            "non_latin_script_words": non_latin_script_words,
            "symbol_or_emoji_words": symbol_or_emoji_words,
            "representable_words": representable_words,
            "unrepresentable_words": unrepresentable_words,
        }

        # Projected storage calculation
        avg_entry_bytes = (
            (sample_serialized_bytes_json / sample_serialized_count)
            if sample_serialized_count > 0
            else 350
        )
        projected_json_mb = (unique_count * avg_entry_bytes * 1.15) / (1024 * 1024)
        projected_jsonl_mb = (unique_count * avg_entry_bytes) / (1024 * 1024)
        projected_sqlite_mb = (unique_count * avg_entry_bytes * 1.35) / (1024 * 1024)

        storage_projections = {
            "json_mb": round(projected_json_mb, 4),
            "jsonl_mb": round(projected_jsonl_mb, 4),
            "sqlite_mb": round(projected_sqlite_mb, 4),
            "avg_entry_bytes": round(avg_entry_bytes, 1),
        }

        performance = {
            "elapsed_seconds": round(elapsed, 4),
            "lines_per_sec": round((total_lines / elapsed) if elapsed > 0 else 0.0, 1),
            "records_per_sec": round((english_records / elapsed) if elapsed > 0 else 0.0, 1),
            "peak_memory_mb": round(peak_mem / (1024 * 1024), 3),
        }

        return DatasetAuditReport(
            input_file=str(path),
            file_size_bytes=file_size,
            total_lines_read=total_lines,
            english_records=english_records,
            non_english_records=non_english_records,
            malformed_json_records=malformed_json_records,
            missing_fields=missing_fields,
            valid_candidates=valid_candidates,
            rejected_candidates=rejected_candidates,
            rejection_reasons=rejection_reasons,
            unique_normalized_words=unique_count,
            duplicate_records=duplicate_records,
            pos_distribution=pos_dist,
            definitions_count=total_definitions,
            avg_definitions_per_word=avg_defs,
            max_definitions_in_word=max_defs_in_word,
            examples_count=examples_count,
            forms_count=forms_count,
            pronunciations_count=pronunciations_count,
            synonyms_count=synonyms_count,
            antonyms_count=antonyms_count,
            etymology_count=etymology_count,
            unicode_stats=unicode_stats,
            unsupported_chars_freq=unsupported_chars_freq,
            length_stats=length_stats,
            performance=performance,
            storage_projections=storage_projections,
        )
