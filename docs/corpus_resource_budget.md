# VEDA Corpus Resource & Training Budgets
## Physical System Sizing, Empirical Memory Bounds & Ingestion Capacity (Phase 4.2.1)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Resource Budget, Memory Limits & Sizing Plan
Document ID: VEDA-POLICY-BUDGET-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.2.1
========================================================================================
```

---

## 1. Measured Host Hardware Capacity & Storage Safety Margin

To prevent ungrounded architectural assumptions, hardware capacity was measured directly on the host development machine:

| Metric | Measured Specification | System Constraints |
|---|---|---|
| **Operating System** | Windows 10 (10.0.26300 64-bit) | Standard NTFS filesystem |
| **CPU Architecture** | 16 Logical Cores (12 Physical Cores) | Multi-threaded worker capacity |
| **Total Physical RAM** | **15.75 GB** | Physical installed memory |
| **Available Free RAM** | **3.53 GB** (at measurement) | Maximum safe single-process RAM budget: **2.0 GB** |
| **Total Disk Storage** | **951.65 GB** | Primary NVMe SSD volume |
| **Used Disk Space** | 612.52 GB | Host OS, user applications, raw datasets |
| **Free Disk Space** | **339.13 GB** | Maximum available physical capacity |

### Storage Envelope & Safety Reserve Rule
- **Minimum Free-Space Reserve**: The system enforces a mandatory reserve of **135.65 GB** (40% of available disk space, or at least 20 GB floor) reserved strictly for host OS virtual memory swap, system crash logs, and normal development operations.
- **Maximum Permissible Ingestion Envelope**: **120.0 GB** total disk budget allocated to all ingestion operations combined.
- **Preflight Disk Safety Check**: Implemented in `foundation/corpus/budget.py` (`PreflightStorageChecker`). Before any file or `.tmp` stream is opened, the preflight checker queries physical free space via `shutil.disk_usage()`. If free space is less than `estimated_job_bytes + minimum_reserve_bytes`, the pipeline halts immediately with `ResourceBudgetExceededError`, completely eliminating disk exhaustion risk.

---

## 2. Peak Concurrent Storage Accounting

Ingestion storage is **not** sequential; multiple artifacts must coexist concurrently during an active ingestion build. The table below audits all concurrent and non-concurrent disk components against the 120.0 GB envelope:

| Storage Component | Peak Footprint (GB) | Concurrency Status | Retention Lifecycle | Storage Layer | Metric Classification |
|---|---|---|---|---|---|
| **1. Downloaded Source Archives** | **25.0 GB** | Active Concurrent | Ephemeral / Staged in `data/raw/` | Compressed tar.gz/bz2/zip | Estimated Planning Envelope |
| **2. Extracted Source Files** | **35.0 GB** | Active Concurrent | Temporary during processing | Raw text / XML / JSONL | Estimated Planning Envelope |
| **3. Temporary Staging (`.tmp`)** | **15.0 GB** | Active Concurrent | Ephemeral (unlinked on finish) | Uncommitted `.tmp` JSONL | Architectural Boundary |
| **4. Normalized Corpus Output** | **15.0 GB** | Active Concurrent | Retained production dataset | `train.jsonl`, `val.jsonl`, `test.jsonl` | Sizing Target |
| **5. Deduplication Indexes** | **4.5 GB** | Active Concurrent | Intermediate hash sets / LSH buckets | Memory-mapped or SQLite index | Computational Bound |
| **6. SQLite Database Artifacts** | **5.0 GB** | Active Concurrent | Certified VEDA Lexicon & indices | Production SQLite files | Measured Empirical Base (2.24 GB) |
| **7. Manifests & Audit Logs** | **0.5 GB** | Active Concurrent | Retained audit trail | `manifest.json`, `rejections.jsonl` | Upper Bound Estimate |
| **8. Backups & Rollback Copies** | **10.0 GB** | Active Concurrent | Staged during rebuild/verification | Standby recovery archive | Mandatory Rollback Headroom |
| **PEAK CONCURRENT INGESTION FOOTPRINT** | **110.0 GB** | **MAX CONCURRENT** | **Within 120.0 GB Envelope** | **Leaves 229.1 GB Free (>135.65 GB Reserve)** | **Arithmetically Validated** |
| *Future Training Artifacts (Estimate)* | *25.0 GB* | *Deferred Downstream (Phase 7)* | *Future Checkpoints & Weights* | *Model weights & optimizer states* | *Non-Concurrent Model Estimate* |

### Operational Safety & Preflight Limitations
> [!WARNING]
> **Static Preflight vs. Dynamic Runtime Risk**:
> 1. **Arithmetic vs Operational Safety**: An arithmetically valid footprint (110.0 GB fitting in 120.0 GB) does not guarantee runtime safety on a shared operating system.
> 2. **External Invalidation**: `PreflightStorageChecker` inspects free disk space at job inception using `shutil.disk_usage()`. If external processes, Windows updates, or concurrent tools write to the host filesystem during ingestion, the preflight guarantee is compromised unless an active reserve margin (135.65 GB / 40%) is strictly enforced.
> 3. **Atomic Rollback Staging Overhead**: Atomic publishing requires writing `.tmp` splits concurrently alongside any preexisting production splits before renaming. If 15 GB of existing data exists and 15 GB of new `.tmp` data is being staged, 30 GB of storage is occupied simultaneously during the commit window. Component 8 explicitly allocates 10.0 GB for this staging/rollback overhead.
> 4. **Future Training Artifacts are Deferred**: Downstream model weights, gradients, and AdamW optimizer states (estimated at 25.0 GB) are strictly non-concurrent with raw corpus ingestion and belong to Phase 7. They must never be scheduled during raw corpus extraction.

---

## 3. Empirical Memory Profiling & Benchmark History

VEDA's streaming architecture is engineered for bounded $O(1)$ stream memory overhead. Process Resident Set Size (RSS) has been empirically measured across previous milestone benchmarks:

| Pipeline Operation | Workload / Scale | Measured Peak RSS | Net Memory Delta ($\Delta$) | Architectural Driver |
|---|---|---|---|---|
| **Phase 3 Lexicon Ingestion** | 25.18 GB raw Wiktextract | **285.40 MB** | $+265.0\text{ MB}$ | In-memory batch accumulation (25,000 words) |
| **Phase 3 Lexicon Lookup** | 959,688 words (2.24 GB DB) | **24.71 MB** | $+4.35\text{ MB}$ | SQLite B-tree page cache traversals |
| **Phase 4.1 Synthetic Stress** | 50,000 documents (Safe Dev) | **101.52 MB** | $+81.03\text{ MB}$ | Exact deduplication hash tables (`set` of SHA-256) |
| **Phase 4.1 Synthetic Stress** | 100,000 documents (Full Run) | **179.61 MB** | $+159.04\text{ MB}$ | Exact deduplication hash tables (158k records) |
| **Phase 4.2 / 4.2.1 Pilot Run** | 9 documents / 15 records | **21.04 MB** | $+0.21\text{ MB}$ | Baseline streaming pipeline memory |

### Memory Budget Envelope for Production Ingestion
- **Maximum Permitted Process RSS**: **1.5 GB** (Leaves $>2.0\text{ GB}$ headroom on a 3.5 GB available RAM system).
- **Streaming Ingestion Buffer**: $O(1)$ memory generator. Records are normalized, filtered, and flushed to disk segment-by-segment.
- **In-Memory State Scaling**: Memory consumption scales strictly with the cardinality of unique document and record hashes retained in the `DeduplicationEngine` (approximately 64 bytes per unique hash). Tracking 1,000,000 records requires $\approx 64 - 80\text{ MB}$ of resident RAM, well within the 1.5 GB budget.

---

## 4. Expected Source & Retained Corpus Sizing

### Sizing Estimates Across Production Phases

| Phase / Tier | Target Description | Raw Download Size | Uncompressed Raw Text | Retained Clean Corpus | Explicit Uncertainty Interval |
|---|---|---|---|---|---|
| **Phase 4.2 Pilot** | Controlled Eligible Sample | ~2.5 MB | ~5.0 MB | **~1.8 MB** | $\pm 10\%$ (High certainty) |
| **Phase 4 Initial Baseline** | Foundation English Corpus | ~15 - 25 GB | ~35 - 60 GB | **~8 - 15 GB** | $[15\%, 40\%]$ retained yield |
| **Phase 4 Target Production** | 250M - 500M words | ~40 - 75 GB | ~90 - 150 GB | **~25 - 45 GB** | $[20\%, 45\%]$ retained yield |

### Sources of Ingestion Uncertainty
1. **Boilerplate & License Disclaimers**: Stripping Gutenberg and wikitext headers eliminates 5% to 25% of raw source characters.
2. **Quality & Repetition Filtering**: Low-alphabetic formula dumps, ASCII art, and short snippets typically discard 15% to 30% of raw candidate paragraphs.
3. **Exact & Normalized Deduplication**: Syndicated news and mirrored books typically discard 10% to 25% of redundant records.
4. **Retained Yield Formula**:
   $$\text{Yield} = \frac{\text{Retained Clean Characters}}{\text{Raw Input Characters}} \in [0.20, 0.45]$$

---

## 4. Deduplication & Indexing Overhead

### A. Exact Hash Deduplication (Current Implementation)
- Tracks SHA-256 digests (32 bytes raw, 64 hex characters) of raw and normalized text.
- Overhead: $\approx 64\text{ bytes} \times N_{\text{records}}$.
- For $10^6$ records: $\approx 64\text{ MB}$ RAM overhead.

### B. Near-Duplicate MinHash LSH (Production Ingestion Prerequisite)
- **Signature Size**: 128 hash permutations per document using 64-bit integer seeds = $128 \times 8 = 1,024\text{ bytes}$ (1 KB) per document.
- **LSH Bands**: 16 bands of 8 rows each (detects Jaccard similarity $\ge 0.80$).
- **RAM Overhead for 1,000,000 Documents**:
  $$1,000,000 \times 1\text{ KB} \approx 1.0\text{ GB RAM}$$
- **Strategy**: For corpora $> 500,000$ documents, MinHash signatures must be persisted out-of-core in an indexed SQLite or RocksDB bucket structure rather than an in-memory hash table, preventing RAM exhaustion.

---

## 5. Provisional Character / Token Planning Budget

> [!IMPORTANT]
> **Planning Estimate Disclaimer**: The numbers below are **provisional planning estimates** for downstream compute and token capacity sizing. They are **not** measured token counts from a trained subword tokenizer.
> 
> Furthermore, the VEDA training corpus is **NOT** restricted to the Phase 1 113-character tokenizer inventory. All eligible Unicode characters (including authentic Latin loanwords *café*, Greek scientific symbols $\lambda$, and typographical punctuation) are authentically preserved in NFC.

### Provisional Pretraining Sizing Tiers

| Planning Tier | Estimated English Words | Estimated Characters (NFC) | Provisional Token Estimate ($\approx 1.25\times \text{Words}$) | Target Parameter Scale |
|---|---|---|---|---|
| **Tier 1 (Small / Proof of Concept)** | 25 Million | ~140 Million | ~30 Million tokens | 5M – 15M parameters |
| **Tier 2 (Foundation Baseline)** | 100 Million | ~550 Million | ~125 Million tokens | 25M – 50M parameters |
| **Tier 3 (Target Pretraining)** | 250 Million | ~1.4 Billion | ~310 Million tokens | 70M – 125M parameters |
| **Tier 4 (Expanded Corpus)** | 500 Million | ~2.8 Billion | ~625 Million tokens | 150M – 250M parameters |

*Basis of Calculation*: Standard English prose averages $\approx 5.5$ characters per word (including whitespace). Subword tokenizers (Byte-Pair Encoding / WordPiece) typically exhibit a fanout factor of $1.20 - 1.30$ tokens per English word.

---

## 6. Backup, Recovery & Data Retention

1. **Atomic Ingestion Isolation**:
   - `CorpusWriter` writes all split files to `.tmp` files (`train.jsonl.tmp`, `rejections.jsonl.tmp`).
   - If a build is interrupted by power failure, exception, or out-of-disk condition, temporary files are unlinked automatically on process termination.
   - Zero partially written datasets are published as valid.
2. **Two-Stage Archive Retention**:
   - **Stage 1 (Raw Source Archives)**: Stored in immutable `data/raw/` (ignored by git, verified against `source_hash`).
   - **Stage 2 (Retained Splits & Manifest)**: Stored in `data/corpus/processed/` accompanied by `manifest.json`.
3. **Dual Cryptographic Checksums**:
   - Every published dataset split records its SHA-256 byte digest in `manifest.json`.
   - Modifying a single character or byte in `train.jsonl` triggers immediate checksum mismatch.

---

## 7. Method for Revising Estimates Post-Pilot

Following the execution of the Phase 4.2 controlled pilot:
1. **Measure Real Yield**: Compute exact ratio of retained characters to raw source characters:
   $$R_{\text{yield}} = \frac{\text{retained\_char\_count}}{\text{raw\_source\_char\_count}}$$
2. **Measure Processing Rate**: Compute sustained throughput:
   $$\text{Throughput} = \frac{\text{documents\_processed}}{\text{elapsed\_seconds}}$$
3. **Calibrate Disk Envelope**: Scale the raw download target by $1 / R_{\text{yield}}$ to hit the exact 100M-word foundation target without exceeding the 120 GB host disk budget.
