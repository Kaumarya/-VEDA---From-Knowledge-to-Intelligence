"""
VEDA Performance Baselines Benchmark Suite (Phase 4.3)
Measures:
1. Corpus Pipeline (Controlled Pilot)
2. Quality & Language Filtering (21-sample benchmark)
3. Near-Duplicate MinHash/LSH Detection (12-pair benchmark)
4. SQLite Lexicon Lookup & to_word() Reconstruction
5. Deduplication Engine Stress Test (5,000 synthetic records)

Repeated runs (N=5) are executed to capture mean, standard deviation, and peak memory.
"""

import json
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psutil

from foundation.corpus.deduplication import DeduplicationEngine
from foundation.corpus.filtering import QualityFilter
from foundation.corpus.language_audit import (
    build_v1_adversarial_language_benchmark,
    classify_with_quarantine,
)
from foundation.corpus.near_deduplication import evaluate_near_duplicate_strategy
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import CorpusDocument, CorpusSource, LicensingStatus
from foundation.lexicon.storage import SqliteLexicon

def get_process_memory_mb() -> float:
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def benchmark_corpus_pipeline(num_runs: int = 5) -> dict:
    """Benchmark 1: Controlled Corpus Pilot Ingestion."""
    pilot_dir = Path("data/corpus/pilot")
    with open(pilot_dir / "pilot_sources.json", "r", encoding="utf-8") as f:
        sources = [CorpusSource.from_dict(item) for item in json.load(f)]
    with open(pilot_dir / "pilot_documents.json", "r", encoding="utf-8") as f:
        documents = [CorpusDocument.from_dict(item) for item in json.load(f)]

    durations = []
    fingerprints = []
    mem_before_list = []
    mem_after_list = []

    for i in range(num_runs):
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"veda_bench_pipe_{i}_"))
        pipeline = CorpusPipeline(corpus_name="veda_bench_pilot", split_seed=42)
        try:
            mem_b = get_process_memory_mb()
            t0 = time.perf_counter()
            manifest = pipeline.process_corpus(sources, documents, tmp_dir)
            t1 = time.perf_counter()
            mem_a = get_process_memory_mb()

            durations.append(t1 - t0)
            mem_before_list.append(mem_b)
            mem_after_list.append(mem_a)
            fingerprints.append(manifest.artifacts["logical_fingerprint"])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # Invariance check
    assert len(set(fingerprints)) == 1, "Non-deterministic pipeline output detected across runs!"

    return {
        "workload": "Corpus Pipeline Pilot (9 documents, 3 sources, 15 records)",
        "runs": num_runs,
        "mean_seconds": round(statistics.mean(durations), 6),
        "std_seconds": round(statistics.stdev(durations) if len(durations) > 1 else 0.0, 6),
        "min_seconds": round(min(durations), 6),
        "max_seconds": round(max(durations), 6),
        "mean_memory_rss_mb": round(statistics.mean(mem_after_list), 2),
        "memory_delta_mb": round(statistics.mean(mem_after_list) - statistics.mean(mem_before_list), 4),
        "logical_fingerprint": fingerprints[0],
        "retained_records": manifest.statistics["retained_records"],
        "rejected_records": manifest.statistics["rejected_records"],
    }

def benchmark_language_filtering(num_runs: int = 5) -> dict:
    """Benchmark 2: Quality & Language Filter with Quarantine."""
    qf = QualityFilter()
    samples = build_v1_adversarial_language_benchmark()

    latencies_per_sample = []
    durations = []

    for _ in range(num_runs):
        t0 = time.perf_counter()
        for s in samples:
            ts0 = time.perf_counter()
            classify_with_quarantine(s.text, qf)
            ts1 = time.perf_counter()
            latencies_per_sample.append((ts1 - ts0) * 1e6)  # microseconds
        t1 = time.perf_counter()
        durations.append(t1 - t0)

    total_evals = num_runs * len(samples)
    throughput_samples_per_sec = total_evals / sum(durations)

    return {
        "workload": "Language Filter with Quarantine (21 adversarial samples across 9 categories)",
        "runs": num_runs,
        "total_evaluations": total_evals,
        "mean_latency_microseconds": round(statistics.mean(latencies_per_sample), 2),
        "p95_latency_microseconds": round(sorted(latencies_per_sample)[int(0.95 * len(latencies_per_sample))], 2),
        "throughput_samples_per_sec": round(throughput_samples_per_sec, 1),
    }

def benchmark_near_deduplication(num_runs: int = 5) -> dict:
    """Benchmark 3: Near-Duplicate MinHash/LSH Detection (128 perms, 16 bands)."""
    durations = []
    results = None

    for _ in range(num_runs):
        t0 = time.perf_counter()
        results = evaluate_near_duplicate_strategy()
        t1 = time.perf_counter()
        durations.append(t1 - t0)

    s1 = results["stage1_candidate_retrieval"]
    s2 = results["stage2_final_decision"]

    return {
        "workload": "Near-Duplicate MinHash/LSH (12 benchmark pairs, 128 perms, 16x8 bands)",
        "runs": num_runs,
        "mean_seconds": round(statistics.mean(durations), 6),
        "std_seconds": round(statistics.stdev(durations) if len(durations) > 1 else 0.0, 6),
        "stage1_recall": s1["candidate_recall"],
        "stage1_selectivity": s1["candidate_selectivity"],
        "stage2_precision": s2["precision"],
        "stage2_recall": s2["recall"],
        "stage2_f1": s2["f1_score"],
    }

def benchmark_sqlite_lexicon(num_queries: int = 1000, num_runs: int = 3) -> dict:
    """Benchmark 4: SQLite Lexicon Queries and Word Reconstruction."""
    db_path = Path("data/lexicon/veda_lexicon_sample.sqlite")
    if not db_path.exists():
        return {"error": "Sample database not found"}

    lex = SqliteLexicon(db_path)
    sample_words = ["apple", "run", "fast", "knowledge", "intelligence", "book", "tree", "river"]

    latencies_us = []
    durations = []

    for _ in range(num_runs):
        t0 = time.perf_counter()
        for i in range(num_queries):
            word = sample_words[i % len(sample_words)]
            q_t0 = time.perf_counter()
            entry = lex.lookup(word)
            if entry:
                _ = lex.to_word(word)
            q_t1 = time.perf_counter()
            latencies_us.append((q_t1 - q_t0) * 1e6)
        t1 = time.perf_counter()
        durations.append(t1 - t0)

    total_queries = num_queries * num_runs
    qps = total_queries / sum(durations)

    return {
        "workload": f"SQLite Lexicon Lookup + to_word() Reconstruction ({num_queries} queries x {num_runs} runs)",
        "database_size_bytes": db_path.stat().st_size,
        "mean_latency_microseconds": round(statistics.mean(latencies_us), 2),
        "p95_latency_microseconds": round(sorted(latencies_us)[int(0.95 * len(latencies_us))], 2),
        "queries_per_second": round(qps, 1),
    }

def benchmark_deduplication_stress(num_records: int = 5000, num_runs: int = 3) -> dict:
    """Benchmark 5: Exact & Normalized Deduplication Engine Stress."""
    unique_texts = [f"This is synthetic sentence number {i} with ample English vocabulary and words." for i in range(4000)]
    dup_texts = [unique_texts[i % 500] for i in range(1000)]
    all_texts = unique_texts + dup_texts

    durations = []
    mems = []

    for _ in range(num_runs):
        engine = DeduplicationEngine()
        mem_b = get_process_memory_mb()
        t0 = time.perf_counter()
        for idx, text in enumerate(all_texts):
            engine.check_and_register_record(
                record_id=f"rec_{idx}",
                raw_text=text,
                normalized_text=text.lower(),
                source_id="src_synthetic",
            )
        t1 = time.perf_counter()
        mem_a = get_process_memory_mb()
        durations.append(t1 - t0)
        mems.append(mem_a - mem_b)

    stats = engine.stats.to_dict()
    throughput = num_records / statistics.mean(durations)

    return {
        "workload": f"Deduplication Engine Stress (5,000 records, 4,000 unique + 1,000 duplicates)",
        "runs": num_runs,
        "mean_seconds": round(statistics.mean(durations), 4),
        "std_seconds": round(statistics.stdev(durations) if len(durations) > 1 else 0.0, 4),
        "throughput_records_per_sec": round(throughput, 1),
        "retained_records": stats["retained_records"],
        "exact_duplicates": stats["exact_duplicates"],
        "memory_growth_mb": round(statistics.mean(mems), 2),
    }

def main() -> None:
    print("=" * 80)
    print("       VEDA PERFORMANCE BASELINES BENCHMARK SUITE (PHASE 4.3)")
    print(f"       Interpreter: {sys.executable}")
    print(f"       Version:     {sys.version.split()[0]}")
    print("=" * 80)

    report = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "host_cpu": os.environ.get("PROCESSOR_IDENTIFIER", "x86_64"),
    }

    print("\n[1/5] Benchmarking Corpus Pipeline (5 repeated runs)...")
    pipe_res = benchmark_corpus_pipeline(5)
    report["corpus_pipeline"] = pipe_res
    print(f"  Mean: {pipe_res['mean_seconds']*1000:.2f} ms ± {pipe_res['std_seconds']*1000:.2f} ms | RSS: {pipe_res['mean_memory_rss_mb']} MB")

    print("\n[2/5] Benchmarking Language Filtering with Quarantine (5 repeated runs)...")
    lang_res = benchmark_language_filtering(5)
    report["language_filtering"] = lang_res
    print(f"  Mean Latency: {lang_res['mean_latency_microseconds']:.1f} µs | Throughput: {lang_res['throughput_samples_per_sec']:.0f} samples/s")

    print("\n[3/5] Benchmarking Near-Duplicate MinHash/LSH (5 repeated runs)...")
    dedup_res = benchmark_near_deduplication(5)
    report["near_deduplication"] = dedup_res
    print(f"  Mean: {dedup_res['mean_seconds']*1000:.2f} ms | S1 Recall: {dedup_res['stage1_recall']} | S2 F1: {dedup_res['stage2_f1']}")

    print("\n[4/5] Benchmarking SQLite Lexicon (3 runs x 1,000 queries)...")
    sql_res = benchmark_sqlite_lexicon(1000, 3)
    report["sqlite_lexicon"] = sql_res
    print(f"  Mean Latency: {sql_res['mean_latency_microseconds']:.1f} µs | QPS: {sql_res['queries_per_second']:.0f} queries/s")

    print("\n[5/5] Benchmarking Deduplication Engine Stress (5,000 records)...")
    stress_res = benchmark_deduplication_stress(5000, 3)
    report["deduplication_stress"] = stress_res
    print(f"  Throughput: {stress_res['throughput_records_per_sec']:.0f} rec/s | Retained: {stress_res['retained_records']} | Dups: {stress_res['exact_duplicates']}")

    ver_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    out_path = Path(f"data/corpus/performance_baselines_{ver_tag}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[OK] Performance baselines saved to: {out_path}")

if __name__ == "__main__":
    main()
