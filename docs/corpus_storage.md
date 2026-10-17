# VEDA Corpus Storage Architecture & Trade-Off Analysis

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Corpus Storage Architecture & Trade-Off Analysis
Document ID: VEDA-STORAGE-CORPUS-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Storage Requirements & Design Goals

The storage format for VEDA's training corpus must satisfy conflicting access patterns:
1. **Streaming Sequential Reads**: Pretraining causal models requires reading billions of tokens sequentially without loading entire datasets into memory.
2. **Deterministic Reproducibility**: Data must be byte-for-byte or record-for-record auditable across platforms without opaque binary lock-in.
3. **Traceable Provenance**: Each record must preserve rich structured metadata alongside text.
4. **Zero-Dependency Simplicity**: Adheres strictly to VEDA's first-principles architecture, avoiding mandatory non-standard C++ compiled binary dependencies where standard formats suffice.

---

## 2. Comprehensive Format Evaluation Matrix

| Storage Format | Streaming Writes | Random Access | Sequential Training Reads | Metadata Querying | Reproducibility & Portability | Storage Size / Overhead | Implementation Complexity |
|---|---|---|---|---|---|---|---|
| **JSONL (Plain)** | **Excellent** ($O(1)$ append) | Poor ($O(N)$ scan) | **Excellent** ($O(1)$ memory streaming line by line) | Poor (requires sequential scan) | **Maximum** (universal UTF-8 plain text) | Moderate (uncompressed text + JSON keys) | **Lowest** (Python standard library `json`) |
| **Compressed JSONL (`.jsonl.gz`)** | Good (streaming gzip flush) | Poor ($O(N)$ scan) | **Excellent** (standard `gzip.open` line iterator) | Poor | **High** (universal standard) | **Best** (~70% compression ratio) | **Low** (Python standard library `gzip`) |
| **SQLite (`.sqlite`)** | Moderate (requires WAL & batch commits) | **Excellent** ($O(\log N)$ indexed B-tree) | Good (cursor traversal, higher CPU per row) | **Outstanding** (full SQL relational queries) | **High** (single-file cross-platform) | Moderate (~20% overhead for B-tree pages) | Moderate (standard library `sqlite3`) |
| **Apache Parquet (`.parquet`)** | Poor (requires column chunk batching) | Moderate (row-group level) | **Outstanding** (columnar vectorization) | Good (column predicate pushdown) | Moderate (requires `pyarrow` / `fastparquet`) | **Excellent** (Snappy/ZSTD dictionary compression) | **High** (violates zero-dependency rule for v0.1) |

---

## 3. Storage Architecture Decision

### A. Phase 4 Selected Architecture: Multi-Tier Hybrid
In alignment with VEDA principles, the Phase 4 training corpus adopts a **multi-tier hybrid storage strategy**:

```
[ RAW SOURCE CATALOG ]   ──►  JSON / SQLite Catalog (source metadata & licenses)
         │
         ▼
[ INGESTION & PIPELINE ] ──►  Streaming Processing (Document → Segment → Record)
         │
         ▼
[ CORPUS ARTIFACTS ]     ──►  Deterministic JSONL partitioned by Split:
                               ├── train.jsonl
                               ├── validation.jsonl
                               └── test.jsonl
         │
         ▼
[ CORPUS MANIFEST ]      ──►  manifest.json (Cryptographic record hashes, counts, metadata)
```

### B. Rationale for Primary JSONL Format:
1. **Zero External Dependencies**: Implemented natively in pure Python 3.9+ standard library.
2. **Infinite Streamability**: Autoregressive DataLoaders can read millions of lines with zero RAM explosion ($O(1)$ buffer).
3. **Atomic File Safety**: Writes to temporary `.tmp` files and executes atomic filesystem renames upon completion.
4. **Human & Tool Inspectability**: Engineers can inspect individual records via standard terminal utilities (`head`, `grep`, `jq`) without proprietary viewers.
5. **Lossless Round-Trip**: Exact UTF-8 string encoding is preserved without columnar type-coercion surprises.

---

## 4. Directory Layout Specification

A generated corpus release is stored in `data/corpus/<corpus_id>_v<version>/`:

```
data/corpus/veda_corpus_v0.1/
├── manifest.json              # Canonical machine-readable manifest & checksums
├── sources.json               # Catalog of verified sources, licenses, and hashes
├── rejections.jsonl           # Structured rejection ledger with provenance & reasons
├── train.jsonl                # 90% Training split records
├── validation.jsonl           # 5% Validation split records
└── test.jsonl                 # 5% Cryptographically locked test split records
```

---

## 5. Unresolved Policy Decisions

1. `[UNRESOLVED — REQUIRES DECISION]` **Zstandard (`.zst`) vs. Gzip (`.gz`) Compression**:
   - Gzip is built into Python stdlib; Zstandard requires `zstandard` package but offers 3x faster decompression.
   - *Status*: Plain JSONL adopted for v0.1 development and testing; Gzip designated as default standard compressed format.

2. `[UNRESOLVED — REQUIRES DECISION]` **Pre-tokenized Binary Tensor Cache**:
   - Whether Phase 4 should produce token ID memory-mapped files (`train.bin`, `uint16`) alongside JSONL.
   - *Status*: Strictly prohibited in Phase 4 under scope restrictions (Tokenization and Tensor creation belong to Phase 5/6).
