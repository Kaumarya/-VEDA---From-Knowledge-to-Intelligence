"""
VEDA Corpus Storage (Phase 4 — Training Corpus Architecture)

Provides atomic, streaming JSONL storage for corpus records, rejection ledgers,
and source catalogs, enforcing file integrity with on-the-fly cryptographic checksums.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, TextIO

from foundation.corpus.schemas import CorpusRecord, CorpusSource, RejectionRecord


class CorpusWriter:
    """
    Manages streaming atomic writes across train, validation, test, and rejection splits.
    """

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._files: Dict[str, TextIO] = {}
        self._tmp_paths: Dict[str, Path] = {}
        self._final_paths: Dict[str, Path] = {}
        self._hashers: Dict[str, Any] = {}
        self._line_counts: Dict[str, int] = {}
        self._is_closed = False

        # Initialize split files
        for split in ("train", "validation", "test", "rejections"):
            filename = f"{split}.jsonl"
            tmp_path = self.output_dir / f"{filename}.tmp"
            final_path = self.output_dir / filename

            self._tmp_paths[split] = tmp_path
            self._final_paths[split] = final_path
            self._files[split] = open(tmp_path, "w", encoding="utf-8", newline="\n")
            self._hashers[split] = hashlib.sha256()
            self._line_counts[split] = 0

    def write_record(self, record: CorpusRecord) -> None:
        """Writes an accepted CorpusRecord to its designated split JSONL."""
        if self._is_closed:
            raise RuntimeError("Cannot write to closed CorpusWriter")

        split = record.split
        if split not in self._files:
            raise ValueError(f"Unknown split: {split!r}")

        line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        encoded = line.encode("utf-8")

        self._files[split].write(line)
        self._hashers[split].update(encoded)
        self._line_counts[split] += 1

    def write_rejection(self, rejection: RejectionRecord) -> None:
        """Writes a rejected candidate entry to rejections.jsonl."""
        if self._is_closed:
            raise RuntimeError("Cannot write to closed CorpusWriter")

        line = json.dumps(rejection.to_dict(), ensure_ascii=False) + "\n"
        encoded = line.encode("utf-8")

        self._files["rejections"].write(line)
        self._hashers["rejections"].update(encoded)
        self._line_counts["rejections"] += 1

    def close(self, commit: bool = True) -> Dict[str, str]:
        """
        Closes all open file streams.
        If commit=True, atomically renames .tmp files to their final destination.
        If commit=False, deletes all .tmp files.

        Returns a dictionary of final file checksums: {split: sha256_hex}.
        """
        if self._is_closed:
            return {}

        self._is_closed = True
        checksums: Dict[str, str] = {}

        # First flush and close all file handles
        for split, f in self._files.items():
            f.flush()
            f.close()
            checksums[split] = self._hashers[split].hexdigest()

        if commit:
            # Atomic rename from .tmp to final
            for split, tmp_path in self._tmp_paths.items():
                final_path = self._final_paths[split]
                if tmp_path.exists():
                    os.replace(tmp_path, final_path)
        else:
            # Rollback / cleanup on failure
            for tmp_path in self._tmp_paths.values():
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

        return checksums

    @property
    def line_counts(self) -> Dict[str, int]:
        return dict(self._line_counts)


class CorpusReader:
    """
    Streaming iterator over corpus records in a JSONL file with O(1) memory.
    """

    @staticmethod
    def read_records(file_path: Path) -> Iterator[CorpusRecord]:
        """Yields CorpusRecord instances line by line."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Corpus file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    data = json.loads(clean_line)
                    yield CorpusRecord.from_dict(data)
                except Exception as e:
                    raise ValueError(f"Corrupted record at {path}:{line_no}: {e}") from e

    @staticmethod
    def read_rejections(file_path: Path) -> Iterator[Dict[str, Any]]:
        """Yields rejection ledger dicts line by line."""
        path = Path(file_path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                clean_line = line.strip()
                if clean_line:
                    yield json.loads(clean_line)
