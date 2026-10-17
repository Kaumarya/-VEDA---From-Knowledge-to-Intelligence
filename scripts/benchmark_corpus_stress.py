"""
VEDA Synthetic Stress Benchmark Runner (Phase 4.1 — Hardening & Certification)

Executes synthetic stress benchmarks across varying scales (e.g. 1,000, 5,000, 10,000 docs),
measuring throughput, memory RSS, determinism, and terminal state conservation.
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.stress import generate_synthetic_stress_corpus


def get_current_rss_mb() -> float:
    """Returns current process RSS in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def run_stress_benchmark(num_docs: int = 5000, output_dir: str = "data/corpus/stress_output") -> None:
    out_path = Path(output_dir)
    if out_path.exists():
        shutil.rmtree(out_path)

    print("============================================================")
    print(f"VEDA Corpus Pipeline Stress Benchmark: {num_docs:,} Documents")
    print("============================================================")

    initial_rss = get_current_rss_mb()
    print(f"Initial RSS Memory: {initial_rss:.2f} MB")
    print("Generating synthetic stress dataset...")

    t0_gen = time.perf_counter()
    sources, documents = generate_synthetic_stress_corpus(num_documents=num_docs, seed=42)
    t_gen = time.perf_counter() - t0_gen
    print(f"Generated {len(documents):,} documents across {len(sources)} sources in {t_gen:.2f}s")

    gen_rss = get_current_rss_mb()
    print(f"In-Memory Dataset RSS: {gen_rss:.2f} MB")

    pipeline = CorpusPipeline(
        corpus_name="veda_synthetic_stress",
        corpus_version="0.1.0",
    )

    print("\nExecuting CorpusPipeline...")
    t0_proc = time.perf_counter()
    manifest = pipeline.process_corpus(sources, documents, out_path)
    t_proc = time.perf_counter() - t0_proc
    peak_rss = get_current_rss_mb()

    stats = manifest.statistics
    docs_per_sec = num_docs / max(1e-6, t_proc)
    recs_per_sec = stats["total_records_processed"] / max(1e-6, t_proc)

    # Compute output size
    total_size_bytes = sum(f.stat().st_size for f in out_path.glob("*.jsonl"))
    size_mb = total_size_bytes / (1024 * 1024)

    print("\n------------------------------------------------------------")
    print("STRESS BENCHMARK RESULTS")
    print("------------------------------------------------------------")
    print(f"Input Documents:         {stats['total_documents']:,}")
    print(f"Retained Documents:      {stats['retained_documents']:,}")
    print(f"Rejected Documents:      {stats['rejected_documents']:,}")
    print(f"Document Conservation:   {stats['retained_documents'] + stats['rejected_documents'] == stats['total_documents']}")
    print(f"Processed Records:       {stats['total_records_processed']:,}")
    print(f"Retained Records:        {stats['retained_records']:,}")
    print(f"Rejected Records:        {stats['rejected_records']:,}")
    print(f"Duplicate Records:       {stats['duplicate_records']:,}")
    print(f"Record Conservation:     {stats['retained_records'] + stats['rejected_records'] + stats['duplicate_records'] == stats['total_records_processed']}")
    print(f"Processing Runtime:      {t_proc:.2f} seconds")
    print(f"Throughput (Docs/sec):   {docs_per_sec:,.1f} docs/sec")
    print(f"Throughput (Recs/sec):   {recs_per_sec:,.1f} recs/sec")
    print(f"Output Dataset Size:     {size_mb:.2f} MB")
    print(f"Peak RSS Memory:         {peak_rss:.2f} MB (Delta: +{peak_rss - initial_rss:.2f} MB)")
    print(f"Content Fingerprint:     {manifest.artifacts['content_fingerprint']}")
    print(f"Manifest Fingerprint:    {manifest.artifacts['manifest_fingerprint']}")
    print("------------------------------------------------------------\n")

    print("Rejection Breakdown:")
    for reason, count in stats["rejection_breakdown"].items():
        print(f"  {reason:24}: {count:,}")

    print("\nSplit Distribution:")
    for split, count in stats["split_counts"].items():
        print(f"  {split.upper():12}: {count:,} records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VEDA Corpus Stress Benchmark")
    parser.add_argument("--docs", type=int, default=10000, help="Number of documents to test (default: 10000)")
    parser.add_argument("--output", type=str, default="data/corpus/stress_output", help="Output directory")
    args = parser.parse_args()

    run_stress_benchmark(num_docs=args.docs, output_dir=args.output)
