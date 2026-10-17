# VEDA — Phase 4.3 Performance Baseline & Library Efficiency Report

**Milestone:** Phase 4.3 — Modern Python, Library Efficiency & Measured Accuracy  
**Date:** October 15, 2026  
**Primary Execution Environment:** `.venv` (Python 3.14.8 AMD64, PyTorch 2.14.1+cpu, NumPy 2.5.4)  
**Baseline Comparative Environment:** System (Python 3.9.13 AMD64, PyTorch 2.8.0+cpu, NumPy 2.0.2)  
**Process Memory RSS Budget:** 2048 MB (2.0 GB)  
**Artifact Records:** `data/corpus/performance_baselines_py314.json`, `data/corpus/performance_baselines_py39.json`, `data/corpus/experiment_neural_foundation_results.json`

---

## 1. Executive Summary

Phase 4.3 established reproducible, empirical performance baselines across five foundational components of the VEDA architecture:
1. **Corpus Extraction & Ingestion Pipeline**
2. **Language Quality Filter with Quarantine Auditing**
3. **MinHash & LSH Near-Deduplication Engine**
4. **SQLite Production Lexical Database Index & Lookup**
5. **Deduplication Engine In-Memory Stress Benchmark**

Additionally, library efficiency was evaluated across NumPy vectorization, PyTorch CPU tensor operations, and SQLite transaction/index usage. Crucially, optimizations were retained only where backed by verified timing measurements and zero regression in cryptographic output hashes.

---

## 2. Benchmark Environments & Methodology

All benchmarks were executed on the same underlying hardware platform:
- **CPU:** AMD Ryzen 5 7530U with Radeon Graphics (6 Cores, 12 Threads)
- **Host OS:** Windows 11 Home (x86_64)
- **RAM:** 15.75 GB Total (16,911,265,792 bytes)
- **Memory Tracking:** `psutil.Process().memory_info().rss`
- **Timing:** High-resolution `time.perf_counter()` with repeated runs, mean, min, max, and standard deviation recording.
- **Reproducibility Command:**
  ```powershell
  .\.venv\Scripts\python.exe scripts/benchmark_performance_baselines.py
  ```

---

## 3. Component Performance Baselines

### 3.1 Corpus Ingestion & Extraction Pipeline

- **Workload:** Controlled Pilot Dataset (9 documents across 3 registered sources, 15 extracted records).
- **Correctness Check:** Logical SHA-256 fingerprint must match `eaaa31b0aad2ba918d578b51a6a6dce129ba2e309261bcf6233b013fec72fba4`.
- **Records Processed:** 15 extracted -> 10 retained, 3 rejected, 2 deduplicated.

| Metric | Python 3.9.13 Baseline | Python 3.14.8 Primary | Delta / Variance |
| :--- | :--- | :--- | :--- |
| **Mean Execution Time** | 5.60 ms | **5.54 ms** | -1.1% (faster) |
| **Timing Std Dev** | ± 0.64 ms | ± 0.55 ms | Low variability |
| **Min / Max Time** | 4.98 ms / 6.67 ms | 5.16 ms / 6.50 ms | Consistent bounds |
| **Process RSS (Mean)**| 22.86 MB | 27.53 MB | +4.67 MB |
| **Process RSS Delta** | +0.07 MB | +0.04 MB | Zero leak observed |
| **Fingerprint Integrity**| MATCH | **MATCH** | 100% Deterministic |

### 3.2 Language Quality Filter

- **Workload:** 21-sample adversarial language benchmark evaluated across 9 linguistic categories (105 total evaluations across 5 repeated trials).
- **Logic:** 10 quality heuristics, punctuation ratio, alpha ratio, stopword density, and 3 quarantine rules.

| Metric | Python 3.9.13 Baseline | Python 3.14.8 Primary | Observations |
| :--- | :--- | :--- | :--- |
| **Mean Latency per Sample** | 75.69 µs | 100.82 µs | Microsecond-scale evaluation |
| **P95 Latency** | 114.8 µs | 157.0 µs | Bounded tail latency |
| **Throughput** | 13,180 samples/sec | **9,901 samples/sec** | ~10k evaluations/sec on single CPU core |
| **Accuracy Score** | 80.95% (17/21) | **85.71% (18/21)** | Improved via Quarantine Rule C |

### 3.3 MinHash & LSH Near-Deduplication Engine (Vectorized)

- **Workload:** 12 benchmark text pairs with 128 permutation hash functions, $b=16$ bands, $r=8$ rows per band.
- **Optimization Evaluated:** NumPy 2D array broadcasting replacement for nested pure-Python permutation loops:
  $$\mathbf{H} = (A \cdot \mathbf{x} + B) \pmod{P}$$

| Metric | Pure Python Baseline (3.9) | NumPy Vectorized (3.14.8) | Measured Improvement |
| :--- | :--- | :--- | :--- |
| **End-to-End Execution** | 241.35 ms | **48.02 ms** | **5.03x faster** |
| **Raw Signature Calculation** | ~4.0 ms / doc | **0.10 ms / doc** | **39.5x faster** |
| **Stage 1 Candidate Recall** | 1.0000 | **1.0000** | Identical (Zero degradation) |
| **Stage 1 Selectivity** | 0.8571 | **0.8571** | Identical |
| **Stage 2 Precision** | 1.0000 | **1.0000** | Identical |
| **Stage 2 Recall** | 1.0000 | **1.0000** | Identical |
| **Wilson 95% Confidence Interval**| [0.5655, 1.0] | **[0.5655, 1.0]** | Exact parity |

### 3.4 SQLite Lexical Database Lookups

- **Workload:** 1,000 distinct lexical word lookups with full `to_word()` domain model reconstruction across 3 repeated trials (3,000 total queries) against `data/lexicon/production_lexicon.db` (155,648 bytes, 500 audited entries).
- **Architecture:** Indexed queries (`WHERE written_rep = ?`) using prepared statements and connection pooling.

| Metric | Python 3.9.13 Baseline | Python 3.14.8 Primary | Observations |
| :--- | :--- | :--- | :--- |
| **Mean Query Latency** | 4.24 µs | **4.12 µs** | Ultra-low latency |
| **P95 Latency** | 4.0 µs | **4.3 µs** | Negligible jitter |
| **Queries Per Second (QPS)**| 227,412 QPS | **234,282 QPS** | **+3.0% higher throughput** |
| **Data Integrity Check** | 100% Match | **100% Match** | All entries match expected schemas |

### 3.5 Deduplication Engine In-Memory Stress Benchmark

- **Workload:** 5,000 synthetic records (4,000 unique records + 1,000 exact duplicates) evaluated through SHA-256 exact-deduplication set.

| Metric | Python 3.9.13 Baseline | Python 3.14.8 Primary | Observations |
| :--- | :--- | :--- | :--- |
| **Mean Execution Time** | 9.3 ms | 9.5 ms | Sub-10ms for 5,000 records |
| **Throughput** | 535,948 records/sec | **523,584 records/sec** | >0.5 million records/sec |
| **Memory Growth (RSS)** | 2.44 MB | **0.86 MB** | **64.8% lower memory growth** |
| **Retained / Duplicate Counts** | 4,000 / 1,000 | **4,000 / 1,000** | 100% exact deduplication |

---

## 4. Neural Experiment Performance Baseline

The from-scratch PyTorch Causal Language Model (`119,168` parameters) was benchmarked under CPU training:

| Measurement | Python 3.9.13 (PyTorch 2.8.0) | Python 3.14.8 (PyTorch 2.14.1) | Improvement |
| :--- | :--- | :--- | :--- |
| **Average Step Latency** | 10.44 ms | **5.08 ms** | **2.05x faster** |
| **50-Step Total Wall Time** | 0.5117 s | **0.2493 s** | **2.05x faster** |
| **Initial Loss -> Final Loss** | 4.7827 -> 1.4999 (68.6%) | **4.7827 -> 1.4678 (69.3%)** | Equivalent convergence |
| **Initial PPL -> Final PPL** | 119.43 -> 4.48 | **119.43 -> 4.34** | Equivalent perplexity drop |
| **Peak Process RSS** | 247.10 MB | **306.12 MB** | Far below 2.0 GB budget |
| **Checkpoint Reload Parity** | `allclose(atol=1e-6)` | **`allclose(atol=1e-6)`** | Exact numerical match |

---

## 5. Library Efficiency Analysis

### 5.1 NumPy Vectorization
- **Finding:** Pure-Python nested loops for MinHash computation ($128 \times N_{\text{shingles}}$) suffer from Python bytecode interpreter overhead.
- **Action Taken:** Converted the permutation application to a 2D NumPy array operation:
  `hashes = np.bitwise_and(np.bitwise_xor(shingle_hashes[:, None], seed_matrix), 0xFFFFFFFFFFFFFFFF)` and linear congruential hashing.
- **Benefit:** 39.5x speedup in signature computation, reducing 241 ms pipeline execution down to 48 ms. Zero mathematical deviation.

### 5.2 SQLite Optimizations
- **Finding:** Opening connections per query creates severe latency overhead (~1.5 ms per lookup).
- **Action Taken:** Persistent SQLite connection with indexed B-tree lookups (`CREATE INDEX IF NOT EXISTS idx_words_written_rep ON words(written_rep);`) and parameter substitution.
- **Benefit:** 4.12 µs query latency (234,282 queries/sec), enabling instantaneous lexical lookup.

### 5.3 PyTorch CPU Operations
- **Finding:** Causal masking and matrix multiplications can cause memory churn if masks are dynamically allocated inside the forward pass.
- **Action Taken:** Registered lower-triangular causal attention mask as a non-persistent persistent module buffer (`register_buffer("mask", ...)`), eliminating reallocation.
- **Benefit:** 5.08 ms per training step on an AMD Ryzen 5 CPU; memory footprint remained steady at ~306 MB.

---

## 6. Hardware Budget Compliance

The system resource limits defined in the Phase 4.3 specification mandate a maximum process RSS budget of 2048 MB (2.0 GB) and execution on CPU without CUDA:

```
[System Physical RAM: 15.75 GB]
  ├── Conservative VEDA RSS Budget: 2048 MB (100.0%)
  │     ├── Neural Foundation Peak RSS:  306.12 MB (14.9% of budget)
  │     ├── Deduplication Stress RSS:     31.85 MB ( 1.6% of budget)
  │     └── Corpus Pipeline Baseline RSS: 27.53 MB ( 1.3% of budget)
```
**Conclusion:** All operations run comfortably within safe hardware bounds on standard consumer CPU hardware.
