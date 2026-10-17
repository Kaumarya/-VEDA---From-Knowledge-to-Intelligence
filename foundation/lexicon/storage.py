"""
VEDA Production Lexicon Storage (Phase 3 — SQLite Persistence)

Provides high-performance SQLite-backed persistence, O(log N) indexed B-tree lookups,
transaction-controlled streaming ingestion, lossless round-trip reconstruction,
and database integrity validation from first principles.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union

from foundation.characters.registry import CharacterRegistry
from foundation.lexicon.extractor import WiktionaryExtractor
from foundation.lexicon.schemas import (
    ExtractionStats,
    LexicalEntry,
    LexicalSense,
    LexiconMetadata,
)
from foundation.words.analyzer import WordAnalyzer
from foundation.words.word import Word


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Core metadata table
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Primary words table
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized TEXT UNIQUE NOT NULL,
    word TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    primary_pos TEXT,
    senses_count INTEGER NOT NULL DEFAULT 0,
    definitions_count INTEGER NOT NULL DEFAULT 0,
    forms_count INTEGER NOT NULL DEFAULT 0,
    pronunciations_count INTEGER NOT NULL DEFAULT 0,
    etymology TEXT,
    entry_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_words_normalized ON words (normalized);
CREATE INDEX IF NOT EXISTS idx_words_word ON words (word);
CREATE INDEX IF NOT EXISTS idx_words_primary_pos ON words (primary_pos);

-- Relational POS index table for fast multi-POS queries
CREATE TABLE IF NOT EXISTS word_pos (
    word_id INTEGER NOT NULL,
    normalized TEXT NOT NULL,
    pos TEXT NOT NULL,
    PRIMARY KEY (word_id, pos),
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_word_pos_pos_norm ON word_pos (pos, normalized);
CREATE INDEX IF NOT EXISTS idx_word_pos_norm ON word_pos (normalized);

-- Relational senses table for granular sense-level queries
CREATE TABLE IF NOT EXISTS senses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    normalized TEXT NOT NULL,
    pos TEXT NOT NULL,
    sense_index INTEGER NOT NULL,
    glosses_json TEXT NOT NULL,
    tags_json TEXT,
    examples_json TEXT,
    categories_json TEXT,
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_senses_word_pos ON senses (word_id, pos);
CREATE INDEX IF NOT EXISTS idx_senses_normalized ON senses (normalized);

-- Ingestion audit & rejection tracking table
CREATE TABLE IF NOT EXISTS ingestion_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    total_lines_read INTEGER NOT NULL,
    english_records INTEGER NOT NULL,
    non_english_skipped INTEGER NOT NULL,
    valid_candidates INTEGER NOT NULL,
    invalid_candidates_skipped INTEGER NOT NULL,
    unique_words_aggregated INTEGER NOT NULL,
    duplicate_records INTEGER NOT NULL,
    malformed_json_records INTEGER NOT NULL,
    missing_fields_json TEXT NOT NULL,
    rejection_reasons_json TEXT NOT NULL,
    elapsed_seconds REAL NOT NULL,
    throughput_lines_sec REAL NOT NULL,
    peak_memory_mb REAL,
    completed_at TEXT NOT NULL
);
"""


class SqliteLexicon:
    """
    SQLite-backed repository for the VEDA Lexicon.

    Features:
    - O(log N) indexed B-tree lookups by canonical normalized word.
    - Exact surface form queries and case-normalized lookups.
    - Indexed POS filtering across multi-POS words without full RAM loading.
    - Lossless reconstruction of LexicalEntry dataclasses.
    - True minimal RAM footprint: lookups do not hold the full dictionary in memory.
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        read_only: bool = True,
        registry: Optional[CharacterRegistry] = None,
    ) -> None:
        self.db_path = Path(db_path).resolve()
        if not self.db_path.is_file() and read_only:
            raise FileNotFoundError(f"SQLite lexicon database not found: {self.db_path}")

        self.read_only = read_only
        self._registry = registry
        self._analyzer: Optional[WordAnalyzer] = None

        uri = f"file:{self.db_path.as_posix()}?mode={'ro' if read_only else 'rwc'}"
        self.conn = sqlite3.connect(uri, uri=True, timeout=30.0)
        self.conn.row_factory = sqlite3.Row

        if not read_only:
            self.conn.executescript(SCHEMA_SQL)
            self.conn.commit()

    @property
    def registry(self) -> Optional[CharacterRegistry]:
        return self._registry

    @property
    def analyzer(self) -> WordAnalyzer:
        if self._analyzer is None:
            self._analyzer = WordAnalyzer(registry=self._registry, lexicon=self)
        return self._analyzer

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    def __enter__(self) -> SqliteLexicon:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def normalize_key(self, word: Union[str, Word]) -> str:
        """Derives the canonical normalized search key according to VEDA v0.1 policy."""
        if isinstance(word, Word):
            return word.normalized
        return word.strip().lower()

    def lookup(
        self,
        word: Union[str, Word],
        pos: Optional[str] = None,
        exact_surface: bool = False,
    ) -> Optional[LexicalEntry]:
        """
        Retrieves a LexicalEntry by word string or Word object.

        Args:
            word: Target word string or Word object.
            pos: Optional part of speech filter (e.g. 'noun', 'verb').
            exact_surface: If True, matches exact surface casing (e.g. 'Apple' vs 'apple').

        Returns:
            Reconstructed LexicalEntry or None if not found / doesn't match POS.
        """
        cursor = self.conn.cursor()

        if exact_surface:
            surface = word.original if isinstance(word, Word) else str(word).strip()
            cursor.execute("SELECT entry_json FROM words WHERE word = ? LIMIT 1", (surface,))
        else:
            norm = self.normalize_key(word)
            cursor.execute("SELECT entry_json FROM words WHERE normalized = ? LIMIT 1", (norm,))

        row = cursor.fetchone()
        if row is None:
            return None

        entry_data = json.loads(row["entry_json"])
        entry = LexicalEntry.from_dict(entry_data)

        if pos is not None:
            pos_clean = pos.strip().lower()
            if pos_clean not in entry.parts_of_speech:
                return None

        return entry

    def get(
        self,
        word: Union[str, Word],
        default: Optional[LexicalEntry] = None,
        pos: Optional[str] = None,
    ) -> Optional[LexicalEntry]:
        """Dictionary-like accessor returning a LexicalEntry or default."""
        res = self.lookup(word, pos=pos)
        return res if res is not None else default

    def has_word(self, word: Union[str, Word], pos: Optional[str] = None) -> bool:
        """
        Fast indexed existence check without deserializing full JSON payloads.
        """
        norm = self.normalize_key(word)
        cursor = self.conn.cursor()

        if pos is not None:
            pos_clean = pos.strip().lower()
            cursor.execute(
                "SELECT 1 FROM word_pos WHERE normalized = ? AND pos = ? LIMIT 1",
                (norm, pos_clean),
            )
        else:
            cursor.execute("SELECT 1 FROM words WHERE normalized = ? LIMIT 1", (norm,))

        return cursor.fetchone() is not None

    def to_word(self, word: Union[str, Word]) -> Optional[Word]:
        """
        Constructs a rich Word instance populated with LexicalEntry data,
        connected to the CharacterRegistry.
        """
        entry = self.lookup(word)
        if entry is None:
            return None
        return entry.to_word(registry=self._registry)

    def filter_by_pos(
        self,
        pos: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[LexicalEntry]:
        """
        Queries all entries matching a specified part of speech using the indexed word_pos table.
        """
        pos_clean = pos.strip().lower()
        query = """
            SELECT w.entry_json
            FROM words w
            JOIN word_pos wp ON w.id = wp.word_id
            WHERE wp.pos = ?
            ORDER BY w.normalized ASC
        """
        params: List[Any] = [pos_clean]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(query, params)

        results: List[LexicalEntry] = []
        for row in cursor.fetchall():
            entry_dict = json.loads(row["entry_json"])
            results.append(LexicalEntry.from_dict(entry_dict))
        return results

    def words(self, limit: Optional[int] = None, offset: int = 0) -> List[str]:
        """Returns sorted canonical normalized word keys."""
        query = "SELECT normalized FROM words ORDER BY normalized ASC"
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [row["normalized"] for row in cursor.fetchall()]

    def count(self) -> int:
        """Returns the total number of unique normalized words in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM words")
        row = cursor.fetchone()
        return int(row["total"]) if row else 0

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, word: Union[str, Word]) -> bool:
        return self.has_word(word)

    def __getitem__(self, word: Union[str, Word]) -> LexicalEntry:
        res = self.lookup(word)
        if res is None:
            norm = self.normalize_key(word)
            raise KeyError(f"Word {norm!r} not found in SQLite Lexicon")
        return res

    def get_metadata(self) -> LexiconMetadata:
        """Extracts LexiconMetadata from the metadata table."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM metadata")
        meta_dict: Dict[str, Any] = {}
        for row in cursor.fetchall():
            k = row["key"]
            val_str = row["value"]
            try:
                meta_dict[k] = json.loads(val_str)
            except Exception:
                meta_dict[k] = val_str

        # Derive live counts
        word_count = self.count()
        pos_dist: Dict[str, int] = {}
        cursor.execute("SELECT pos, COUNT(*) as c FROM word_pos GROUP BY pos")
        for row in cursor.fetchall():
            pos_dist[row["pos"]] = int(row["c"])

        return LexiconMetadata(
            project=meta_dict.get("project", "VEDA"),
            component=meta_dict.get("component", "Lexical Foundation"),
            version=meta_dict.get("version", "0.1.0"),
            schema_version=meta_dict.get("schema_version", "0.1.0"),
            extractor_version=meta_dict.get("extractor_version", "0.1.0"),
            normalization_version=meta_dict.get("normalization_version", "0.1.0"),
            language_scope=meta_dict.get("language_scope", "English"),
            word_count=word_count,
            pos_distribution=pos_dist,
            sources=meta_dict.get("sources", ["Wiktionary (Wiktextract)"]),
            source_dataset=meta_dict.get("source_dataset", "Wiktionary (Wiktextract)"),
            created_at=meta_dict.get("created_at"),
            processing_config=meta_dict.get("processing_config", {}),
        )

    def get_latest_ingestion_stats(self) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent ingestion stats record."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ingestion_stats ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            return None

        return {
            "source_file": row["source_file"],
            "total_lines_read": row["total_lines_read"],
            "english_records": row["english_records"],
            "non_english_skipped": row["non_english_skipped"],
            "valid_candidates": row["valid_candidates"],
            "invalid_candidates_skipped": row["invalid_candidates_skipped"],
            "unique_words_aggregated": row["unique_words_aggregated"],
            "duplicate_records": row["duplicate_records"],
            "malformed_json_records": row["malformed_json_records"],
            "missing_fields": json.loads(row["missing_fields_json"]),
            "rejection_reasons": json.loads(row["rejection_reasons_json"]),
            "elapsed_seconds": row["elapsed_seconds"],
            "throughput_lines_sec": row["throughput_lines_sec"],
            "peak_memory_mb": row["peak_memory_mb"],
            "completed_at": row["completed_at"],
        }

    def integrity_check(self) -> Dict[str, Any]:
        """
        Runs SQLite database integrity validation and cross-table consistency checks.
        """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        integrity_res = [row[0] for row in cursor.fetchall()]

        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = [dict(row) for row in cursor.fetchall()]

        words_count = self.count()

        cursor.execute("SELECT COUNT(*) AS total FROM word_pos")
        word_pos_count = int(cursor.fetchone()["total"])

        cursor.execute("SELECT COUNT(*) AS total FROM senses")
        senses_count = int(cursor.fetchone()["total"])

        cursor.execute("SELECT COUNT(DISTINCT normalized) AS distinct_words FROM word_pos")
        distinct_words_pos = int(cursor.fetchone()["distinct_words"])

        return {
            "sqlite_integrity_check": integrity_res,
            "foreign_key_violations": fk_violations,
            "is_healthy": (integrity_res == ["ok"] and len(fk_violations) == 0),
            "words_row_count": words_count,
            "word_pos_row_count": word_pos_count,
            "senses_row_count": senses_count,
            "distinct_normalized_words_in_pos": distinct_words_pos,
        }


class SqliteLexiconBuilder:
    """
    Controlled batch ingestion engine that streams Wiktextract JSONL datasets
    directly into a high-performance SQLite database without RAM exhaustion.
    """

    def __init__(
        self,
        analyzer: Optional[WordAnalyzer] = None,
        extractor: Optional[WiktionaryExtractor] = None,
    ) -> None:
        self.analyzer = analyzer or WordAnalyzer()
        self.extractor = extractor or WiktionaryExtractor(analyzer=self.analyzer)

    def build(
        self,
        source_file: Union[str, Path],
        db_path: Union[str, Path],
        batch_size: int = 25000,
        max_lines: Optional[int] = None,
        validate_candidates: bool = True,
        rebuild: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        report_every: int = 10000,
    ) -> SqliteLexicon:
        """
        Ingests a JSONL dataset into SQLite in memory-bounded batch transactions.

        Safety:
        - If rebuild=True, builds into a temporary database and atomically renames on success.
        - Idempotent: repeated ingestions merge cleanly without duplicating records.
        """
        source_path = Path(source_file).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        target_db = Path(db_path).resolve()
        target_db.parent.mkdir(parents=True, exist_ok=True)

        working_db = target_db
        if rebuild:
            working_db = target_db.with_suffix(".tmp.sqlite")
            if working_db.is_file():
                working_db.unlink()

        conn = sqlite3.connect(working_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        start_time = time.perf_counter()

        import psutil
        process = psutil.Process()
        peak_rss_mb = process.memory_info().rss / (1024 * 1024)

        # Audit counters
        total_lines_read = 0
        english_records = 0
        non_english_skipped = 0
        valid_candidates = 0
        invalid_candidates_skipped = 0
        duplicate_records = 0
        malformed_json_records = 0
        missing_fields: Dict[str, int] = {
            "missing_word": 0,
            "missing_lang": 0,
            "missing_pos": 0,
            "empty_senses": 0,
        }
        rejection_reasons: Dict[str, int] = {}

        # In-memory batch accumulation bounded by batch_size
        batch_entries: Dict[str, LexicalEntry] = {}

        def commit_batch() -> None:
            nonlocal batch_entries, peak_rss_mb
            if not batch_entries:
                return

            curr_rss = process.memory_info().rss / (1024 * 1024)
            if curr_rss > peak_rss_mb:
                peak_rss_mb = curr_rss

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor = conn.cursor()

            # Identify words that already exist in DB to perform idempotent merge
            # Safely chunk to stay within SQLite host parameter limits
            keys = list(batch_entries.keys())
            existing_rows: Dict[str, Any] = {}
            for i in range(0, len(keys), 500):
                chunk = keys[i : i + 500]
                placeholders = ",".join("?" for _ in chunk)
                cursor.execute(
                    f"SELECT id, normalized, entry_json FROM words WHERE normalized IN ({placeholders})",
                    chunk,
                )
                for row in cursor.fetchall():
                    existing_rows[row["normalized"]] = row

            for norm, entry in batch_entries.items():
                if norm in existing_rows:
                    # Merge with existing record
                    row = existing_rows[norm]
                    word_id = row["id"]
                    existing_entry = LexicalEntry.from_dict(json.loads(row["entry_json"]))
                    existing_entry.merge(entry)
                    final_entry = existing_entry

                    # Update word row
                    cursor.execute(
                        """
                        UPDATE words SET
                            word = ?,
                            language = ?,
                            primary_pos = ?,
                            senses_count = ?,
                            definitions_count = ?,
                            forms_count = ?,
                            pronunciations_count = ?,
                            etymology = ?,
                            entry_json = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            final_entry.word,
                            final_entry.language,
                            final_entry.primary_pos,
                            len(final_entry.senses),
                            len(final_entry.definitions),
                            len(final_entry.forms),
                            len(final_entry.pronunciations),
                            final_entry.etymology,
                            json.dumps(final_entry.to_dict(), ensure_ascii=False),
                            now_iso,
                            word_id,
                        ),
                    )

                    # Replace POS index and senses
                    cursor.execute("DELETE FROM word_pos WHERE word_id = ?", (word_id,))
                    cursor.execute("DELETE FROM senses WHERE word_id = ?", (word_id,))
                else:
                    final_entry = entry
                    cursor.execute(
                        """
                        INSERT INTO words (
                            normalized, word, language, primary_pos,
                            senses_count, definitions_count, forms_count,
                            pronunciations_count, etymology, entry_json,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            final_entry.normalized,
                            final_entry.word,
                            final_entry.language,
                            final_entry.primary_pos,
                            len(final_entry.senses),
                            len(final_entry.definitions),
                            len(final_entry.forms),
                            len(final_entry.pronunciations),
                            final_entry.etymology,
                            json.dumps(final_entry.to_dict(), ensure_ascii=False),
                            now_iso,
                            now_iso,
                        ),
                    )
                    word_id = cursor.lastrowid

                # Insert child word_pos rows
                for pos in final_entry.parts_of_speech:
                    cursor.execute(
                        "INSERT OR IGNORE INTO word_pos (word_id, normalized, pos) VALUES (?, ?, ?)",
                        (word_id, final_entry.normalized, pos),
                    )

                # Insert child senses rows
                for idx, s in enumerate(final_entry.senses):
                    cursor.execute(
                        """
                        INSERT INTO senses (
                            word_id, normalized, pos, sense_index,
                            glosses_json, tags_json, examples_json, categories_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            word_id,
                            final_entry.normalized,
                            s.pos,
                            idx,
                            json.dumps(s.glosses, ensure_ascii=False),
                            json.dumps(s.tags, ensure_ascii=False),
                            json.dumps(s.examples, ensure_ascii=False),
                            json.dumps(s.categories, ensure_ascii=False),
                        ),
                    )

            conn.commit()
            batch_entries.clear()

        # Stream raw lines line-by-line
        try:
            with open(source_path, "r", encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue

                    total_lines_read += 1

                    try:
                        record = json.loads(stripped)
                    except json.JSONDecodeError:
                        malformed_json_records += 1
                        continue

                    if not isinstance(record, dict):
                        malformed_json_records += 1
                        continue

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

                    # Step 1: Language Filter
                    if not self.extractor.is_english(record):
                        non_english_skipped += 1
                        continue

                    english_records += 1

                    # Step 2: Word Candidate Validation
                    if validate_candidates:
                        val = self.analyzer.validate_candidate(raw_word)
                        if not val.is_valid:
                            invalid_candidates_skipped += 1
                            rejection_reasons[val.reason] = rejection_reasons.get(val.reason, 0) + 1
                            continue

                    valid_candidates += 1

                    # Step 3: Parse Record
                    entry = self.extractor.parse_record(record)
                    norm = entry.normalized

                    # Step 4: Batch Aggregation
                    if norm in batch_entries:
                        duplicate_records += 1
                        batch_entries[norm].merge(entry)
                    else:
                        batch_entries[norm] = entry

                    # Transaction commit boundary
                    if len(batch_entries) >= batch_size:
                        commit_batch()

                    if progress_callback is not None and total_lines_read % report_every == 0:
                        elapsed = time.perf_counter() - start_time
                        progress_callback(
                            {
                                "total_lines_read": total_lines_read,
                                "english_records": english_records,
                                "valid_candidates": valid_candidates,
                                "elapsed_seconds": elapsed,
                                "rate": (total_lines_read / elapsed) if elapsed > 0 else 0.0,
                            }
                        )

                    if max_lines is not None and total_lines_read >= max_lines:
                        break

            # Commit final trailing batch
            commit_batch()

        except Exception:
            conn.rollback()
            conn.close()
            if rebuild and working_db.is_file():
                working_db.unlink()
            raise

        elapsed_total = time.perf_counter() - start_time
        throughput = (total_lines_read / elapsed_total) if elapsed_total > 0 else 0.0

        # Store metadata in database
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metadata_pairs = {
            "project": "VEDA",
            "component": "Production Lexicon",
            "version": "0.1.0",
            "schema_version": "0.1.0",
            "extractor_version": "0.1.0",
            "normalization_version": "0.1.0",
            "language_scope": "English",
            "source_dataset": str(source_path.name),
            "created_at": now_utc,
            "processing_config": json.dumps(
                {
                    "batch_size": batch_size,
                    "max_lines": max_lines,
                    "validate_candidates": validate_candidates,
                    "rebuild": rebuild,
                }
            ),
        }

        cursor = conn.cursor()
        for k, v in metadata_pairs.items():
            cursor.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (k, v),
            )

        # Count total unique entries
        cursor.execute("SELECT COUNT(*) AS total FROM words")
        unique_words_count = int(cursor.fetchone()["total"])

        # Store ingestion stats
        cursor.execute(
            """
            INSERT INTO ingestion_stats (
                source_file, total_lines_read, english_records, non_english_skipped,
                valid_candidates, invalid_candidates_skipped, unique_words_aggregated,
                duplicate_records, malformed_json_records, missing_fields_json,
                rejection_reasons_json, elapsed_seconds, throughput_lines_sec, peak_memory_mb, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(source_path.name),
                total_lines_read,
                english_records,
                non_english_skipped,
                valid_candidates,
                invalid_candidates_skipped,
                unique_words_count,
                duplicate_records,
                malformed_json_records,
                json.dumps(missing_fields),
                json.dumps(rejection_reasons),
                round(elapsed_total, 4),
                round(throughput, 1),
                round(peak_rss_mb, 2),
                now_utc,
            ),
        )

        try:
            conn.commit()
        finally:
            conn.close()

        # Atomic final rename if building into temp database
        if rebuild and working_db != target_db:
            os.replace(working_db, target_db)

        return SqliteLexicon(target_db, read_only=True, registry=self.analyzer.registry)
