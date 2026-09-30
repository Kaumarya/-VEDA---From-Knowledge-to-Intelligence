"""
VEDA Lexicon Storage Benchmark Suite (Phase 3 — Empirical Performance Profiling)

Provides reproducible micro-benchmarks for SQLite Lexicon lookups,
latency distributions (median, p95, p99), process memory (RSS) tracking,
and throughput metrics from first principles.
"""

from __future__ import annotations

import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import psutil

from foundation.lexicon.storage import SqliteLexicon


@dataclass
class QueryBenchmarkResult:
    """Latency distribution and throughput for a query pattern."""
    query_type: str
    iterations: int
    median_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    min_latency_us: float
    max_latency_us: float
    avg_latency_us: float
    qps: float  # Queries per second

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StorageBenchmarkReport:
    """Comprehensive benchmark results including latency and memory profile."""
    database_file: str
    database_size_bytes: int
    database_size_mb: float
    total_words: int
    iterations_per_test: int
    queries: Dict[str, QueryBenchmarkResult]
    memory_profile: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database_file": self.database_file,
            "database_size_bytes": self.database_size_bytes,
            "database_size_mb": self.database_size_mb,
            "total_words": self.total_words,
            "iterations_per_test": self.iterations_per_test,
            "queries": {k: v.to_dict() for k, v in self.queries.items()},
            "memory_profile": self.memory_profile,
        }

    def summary_text(self) -> str:
        sep = "=" * 76
        sub_sep = "-" * 76
        lines: List[str] = [
            sep,
            "               VEDA SQLITE STORAGE BENCHMARK REPORT",
            sep,
            f"{'Database Path:':<30} {self.database_file}",
            f"{'Database Size:':<30} {self.database_size_bytes:,} bytes ({self.database_size_mb:.3f} MB)",
            f"{'Unique Word Count:':<30} {self.total_words:,} words",
            f"{'Iterations Per Test:':<30} {self.iterations_per_test:,}",
            sub_sep,
            "1. LATENCY DISTRIBUTIONS (Microseconds, μs)",
            f"{'Query Pattern':<26} {'Median':>9} {'p95':>9} {'p99':>9} {'Avg':>9} {'QPS':>12}",
            sub_sep,
        ]

        for q_name, res in self.queries.items():
            lines.append(
                f"{res.query_type:<26} "
                f"{res.median_latency_us:>8.2f}μs "
                f"{res.p95_latency_us:>8.2f}μs "
                f"{res.p99_latency_us:>8.2f}μs "
                f"{res.avg_latency_us:>8.2f}μs "
                f"{res.qps:>11,.0f}"
            )

        lines.extend([
            sub_sep,
            "2. PROCESS MEMORY PROFILE (Resident Set Size, RSS)",
            f"{'RSS Before Opening DB:':<30} {self.memory_profile['rss_before_open_mb']:.2f} MB",
            f"{'RSS After Opening DB:':<30} {self.memory_profile['rss_after_open_mb']:.2f} MB",
            f"{'Delta on Open:':<30} {self.memory_profile['rss_delta_open_mb']:+.2f} MB",
            f"{'RSS After 25,000+ Queries:':<30} {self.memory_profile['rss_after_queries_mb']:.2f} MB",
            f"{'Delta During Queries:':<30} {self.memory_profile['rss_delta_queries_mb']:+.2f} MB",
            sub_sep,
            "3. ARCHITECTURAL TAKEAWAYS",
            " - Indexed B-tree lookup operates in O(log N) depth without loading dictionary into RAM.",
            f" - Memory overhead on DB connection is < {max(0.5, self.memory_profile['rss_delta_open_mb']):.2f} MB.",
            " - True random-access persistence suitable for scaling to complete Wiktextract.",
            sep,
        ])
        return "\n".join(lines)


class StorageBenchmarkRunner:
    """Executes standardized, reproducible performance benchmarks on SqliteLexicon."""

    @staticmethod
    def _run_timing_loop(func, iterations: int) -> List[float]:
        """Runs func() for iterations times, measuring execution time in microseconds (μs)."""
        durations_us: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter_ns()
            func()
            t1 = time.perf_counter_ns()
            durations_us.append((t1 - t0) / 1000.0)
        return durations_us

    @classmethod
    def _compute_stats(cls, query_type: str, durations_us: List[float]) -> QueryBenchmarkResult:
        durations_us.sort()
        n = len(durations_us)
        median_val = statistics.median(durations_us)
        p95_val = durations_us[int(n * 0.95)] if n > 0 else 0.0
        p99_val = durations_us[int(n * 0.99)] if n > 0 else 0.0
        avg_val = sum(durations_us) / n if n > 0 else 0.0
        total_time_s = sum(durations_us) / 1_000_000.0
        qps = (n / total_time_s) if total_time_s > 0 else 0.0

        return QueryBenchmarkResult(
            query_type=query_type,
            iterations=n,
            median_latency_us=round(median_val, 2),
            p95_latency_us=round(p95_val, 2),
            p99_latency_us=round(p99_val, 2),
            min_latency_us=round(durations_us[0], 2) if n > 0 else 0.0,
            max_latency_us=round(durations_us[-1], 2) if n > 0 else 0.0,
            avg_latency_us=round(avg_val, 2),
            qps=round(qps, 1),
        )

    @classmethod
    def benchmark_database(
        cls,
        db_path: Union[str, Path],
        iterations: int = 5000,
    ) -> StorageBenchmarkReport:
        """Runs the complete suite of required lookup and memory benchmarks."""
        path = Path(db_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Database not found: {path}")

        file_size = path.stat().st_size
        process = psutil.Process(os.getpid())

        # Baseline RSS before opening database
        rss_before = process.memory_info().rss / (1024 * 1024)

        lexicon = SqliteLexicon(path, read_only=True)
        total_words = lexicon.count()

        # RSS after opening database
        rss_after_open = process.memory_info().rss / (1024 * 1024)

        words_sample = lexicon.words(limit=10)
        test_word = words_sample[0] if words_sample else "apple"
        test_word_upper = test_word.upper()

        queries: Dict[str, QueryBenchmarkResult] = {}

        # 1. Exact normalized-word lookup
        lat_norm = cls._run_timing_loop(lambda: lexicon.lookup(test_word), iterations)
        queries["exact_normalized"] = cls._compute_stats("1. Exact Normalized", lat_norm)

        # 2. Case-normalized lookup ('Apple' / 'APPLE')
        lat_case = cls._run_timing_loop(lambda: lexicon.lookup(test_word_upper), iterations)
        queries["case_normalized"] = cls._compute_stats("2. Case Normalized", lat_case)

        # 3. POS-filtered lookup ('word', pos='noun')
        lat_pos = cls._run_timing_loop(lambda: lexicon.lookup(test_word, pos="noun"), iterations)
        queries["pos_filtered"] = cls._compute_stats("3. POS Filtered", lat_pos)

        # 4. Repeated lookup (cycling through vocabulary)
        cycle_words = words_sample or [test_word]
        idx = 0
        def cycle_lookup():
            nonlocal idx
            lexicon.lookup(cycle_words[idx % len(cycle_words)])
            idx += 1

        lat_cycle = cls._run_timing_loop(cycle_lookup, iterations)
        queries["repeated_cycle"] = cls._compute_stats("4. Repeated Cycle", lat_cycle)

        # 5. Missing-word lookup ('nonexistentwordxyz')
        lat_missing = cls._run_timing_loop(lambda: lexicon.lookup("nonexistentwordxyz"), iterations)
        queries["missing_word"] = cls._compute_stats("5. Missing Word", lat_missing)

        # RSS after 5 * iterations queries
        rss_after_queries = process.memory_info().rss / (1024 * 1024)

        lexicon.close()

        memory_profile = {
            "rss_before_open_mb": round(rss_before, 2),
            "rss_after_open_mb": round(rss_after_open, 2),
            "rss_delta_open_mb": round(rss_after_open - rss_before, 2),
            "rss_after_queries_mb": round(rss_after_queries, 2),
            "rss_delta_queries_mb": round(rss_after_queries - rss_after_open, 2),
        }

        return StorageBenchmarkReport(
            database_file=str(path),
            database_size_bytes=file_size,
            database_size_mb=round(file_size / (1024 * 1024), 3),
            total_words=total_words,
            iterations_per_test=iterations,
            queries=queries,
            memory_profile=memory_profile,
        )
