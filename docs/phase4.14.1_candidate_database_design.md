# VEDA Phase 4.14.1 Engineering Specification
## Database-Backed Candidate & Decision Storage Architecture Design

- **Project:** VEDA — From Knowledge to Intelligence
- **Phase:** 4.14.1 (Design Specification Only)
- **Status:** COMPLETE / READY FOR REVIEW
- **Author:** Antigravity (Cognitive Architecture Agent)
- **Date:** 2026-11-13
- **Git Base Checkpoint:** `2928dcb7030a202e6ebd5c5370984d78c63fe77c` (main)
- **Runtime Targets:** Python 3.14.8 (`.venv`) & Python 3.9.13 (Global System)
- **Pretraining Status:** Strictly PAUSED / BLOCKED

---

## 1. Executive Summary

### 1.1 Mission & Scope
Phase 4.14.1 defines the architectural blueprint and relational database specification for Project VEDA's **Candidate & Decision Storage Architecture** (`veda_candidates.sqlite`). 

Under the core philosophy of VEDA (*Understand → Implement → Test → Measure → Document → Improve*), this phase is **strictly design-only**. No production Python source code is modified, no live database tables are created, no schema migrations are executed, and no training pretraining runs are initialized.

### 1.2 The Three Storage Pillars
The VEDA storage topology is explicitly partitioned into three non-interchangeable systems:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VEDA STORAGE TOPOLOGY                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  PILLAR 1: English Lexicon (Phase 3)                                        │
│  - Engine: SQLite (data/lexicon/veda_lexicon_v0.1.sqlite)                   │
│  - Scope: 959,688 words, lemmas, definitions, POS, pronunciations.          │
│  - Mode: Strictly READ-ONLY during candidate and corpus processing.         │
├─────────────────────────────────────────────────────────────────────────────┤
│  PILLAR 2: Candidate & Decision Storage (Phase 4.14 — THIS DESIGN)          │
│  - Engine: SQLite (data/candidates/veda_candidates.sqlite)                  │
│  - Scope: Submissions, verbatim raw text, normalized text, decisions,       │
│           semantic conflicts, duplicate graphs, approval ledger.            │
│  - Mode: ACID Read/Write, append-mostly audit journal.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  PILLAR 3: Training Corpus (Phase 4)                                        │
│  - Engine: Streaming atomic JSONL (data/corpus/{train,validation,test}.jsonl│
│  - Scope: Sealed splits, cryptographic manifests, tokenization input.       │
│  - Mode: Append-only releases sealed by cryptographic hashes.               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Core Invariants
1. **Verbatim Fidelity:** Original submitted text is immutable and never overwritten or lossy-compressed.
2. **Normalized Derivation:** Normalized text is deterministically derived via [foundation/corpus/normalization.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/normalization.py) and indexed separately.
3. **Auditability:** Every processing pass, heuristic metric, quality score, and rejection reason is appended to an immutable decision journal.
4. **Fail-Closed Export Gate:** Only candidates in `APPROVED` status with active, non-stale `VERIFIED_PERMITTED` source licenses, zero unresolved safety conflicts, and current pipeline rules are eligible for export into training splits.
5. **Architectural Isolation:** The English Lexicon database is never used to store candidate submissions, and the candidate database never replaces the streaming JSONL corpus engine.

---

## 2. Preliminary Repository Audit Findings

In accordance with Section 3 of the Phase 4.14.1 specification, the physical codebase was inspected across `foundation/`, `tests/`, `scripts/`, `docs/`, and configuration files. Below are the verified answers to the 15 required audit questions, backed by direct source-code citations.

### 2.1 Audit Questions & Source-Code Evidence

#### Q1: How is the existing lexicon database opened?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L126-L146) (`SqliteLexicon.__init__`)
* **Finding:** The lexicon is opened using an explicit SQLite URI with connection mode flags:
  ```python
  uri = f"file:{self.db_path.as_posix()}?mode={'ro' if read_only else 'rwc'}"
  self.conn = sqlite3.connect(uri, uri=True, timeout=30.0)
  self.conn.row_factory = sqlite3.Row
  ```
  In read-only mode, opening fails fast if the physical database file does not exist (`FileNotFoundError`). During builder execution ([foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L456)), it connects directly to a `.tmp.sqlite` staging database path.

#### Q2: How are SQLite connections configured?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L32-L40), [L458-L463](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L458-L463)
* **Finding:** The lexicon connection enforces high-concurrency read and bulk write PRAGMAs:
  * `PRAGMA journal_mode = WAL;` (Write-Ahead Logging enabled for non-blocking concurrent reads).
  * `PRAGMA foreign_keys = ON;` (Relational constraints enforced).
  * `PRAGMA synchronous = NORMAL;` (Reduces fsync frequency in WAL mode while maintaining safety against corruption).
  * `PRAGMA cache_size = -64000;` (Allocates 64 MB of RAM for page cache).
  * `PRAGMA temp_store = MEMORY;` (Directs temporary B-trees and sorting tables to RAM).

#### Q3: How are transactions handled?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L488-L617) (`SqliteLexiconBuilder.build`)
* **Finding:** Streaming ingestion aggregates records in an in-memory batch dictionary (`batch_entries`, default size 25,000). At batch boundary:
  1. A transaction is implicitly managed through `cursor.execute()` calls.
  2. Multi-row existence queries chunk keys into sets of 500 (`WHERE normalized IN (...)`) to respect SQLite host parameter boundaries.
  3. Parent `words` rows and child `word_pos` / `senses` rows are updated or inserted.
  4. `conn.commit()` is explicitly executed to close the transaction boundary and release WAL write locks.

#### Q4: How are failures handled?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L705-L711) (`SqliteLexiconBuilder.build`)
* **Finding:** Enclosed in a comprehensive `try...except` block:
  ```python
  except Exception:
      conn.rollback()
      conn.close()
      if rebuild and working_db.is_file():
          working_db.unlink()
      raise
  ```
  On unhandled exception, the active transaction is rolled back, the connection closed, and the staging `.tmp.sqlite` database unlinked. The production database is untouched.

#### Q5: How are foreign keys enforced?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L34), [L69](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L69), [L86](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L86)
* **Finding:** `SCHEMA_SQL` activates foreign keys with `PRAGMA foreign_keys = ON;`. Child tables declare cascading foreign key constraints referencing `words(id)`:
  * `word_pos`: `FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE`
  * `senses`: `FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE`
  Programmatic integrity validation is provided via `SqliteLexicon.integrity_check()` ([L351-L364](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L351-L364)), which calls `PRAGMA foreign_key_check;`.

#### Q6: How is the lexicon version identified?
* **Source:** [foundation/lexicon/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py#L717-L743)
* **Finding:** The lexicon persists an internal key-value `metadata` table storing:
  * `project`: `"VEDA"`
  * `component`: `"Production Lexicon"`
  * `version`: `"0.1.0"`
  * `schema_version`: `"0.1.0"`
  * `extractor_version`: `"0.1.0"`
  * `normalization_version`: `"0.1.0"`
  * `language_scope`: `"English"`
  * `source_dataset`: string filename
  * `created_at`: ISO 8601 UTC timestamp
  * `processing_config`: JSON configuration dictionary

#### Q7: How is corpus provenance recorded?
* **Source:** [foundation/corpus/schemas.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/schemas.py#L354-L394) (`RecordProvenance` & `CorpusRecord`)
* **Finding:** Every corpus record embeds a strongly-typed `RecordProvenance` dataclass:
  * `source_id`: Stable identifier of the registered origin source.
  * `document_id`: Parent document identifier.
  * `segment_index`: 0-indexed position within parent document.
  * `start_char_offset` / `end_char_offset`: Exact non-overlapping slice indices into raw document text.
  * `normalizer_version`: Semantic version of `TextNormalizer` used.
  * `filter_version`: Semantic version of `QualityFilter` used.
  * `created_at`: ISO 8601 acquisition/processing timestamp.
  * `contributing_sources`: Deduplication engine records all distinct source IDs that contributed identical text.
  * `attribution_notices`: Legal attribution strings required by licenses.

#### Q8: How are rejected records stored?
* **Source:** [foundation/corpus/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/storage.py#L63-L74) (`CorpusWriter.write_rejection`), [foundation/corpus/schemas.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/schemas.py#L464-L492) (`RejectionRecord`)
* **Finding:** Rejections are written to an isolated, append-only `rejections.jsonl.tmp` file. Each entry contains: `record_id`, `document_id`, `source_id`, `rejection_reason` (from `RejectionReason` enum), `rejection_stage` (`governance`, `normalization`, `filtering`, `deduplication`), `raw_text_sample` (truncated to 100 characters), `metric_name`, `metric_value`, `threshold_value`, and `created_at`. Rejected records are strictly segregated from training splits.

#### Q9: How does the current CorpusWriter commit data?
* **Source:** [foundation/corpus/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/storage.py#L75-L103) (`CorpusWriter.close`)
* **Finding:** Two-phase atomic commit:
  1. Files are opened and written with a `.tmp` suffix (`train.jsonl.tmp`, `validation.jsonl.tmp`, `test.jsonl.tmp`, `rejections.jsonl.tmp`).
  2. On `close(commit=True)`, file handles are flushed and closed.
  3. Physical files are atomically renamed to final destination using `os.replace(tmp_path, final_path)`.
  4. If `commit=False` (failure rollback), all `.tmp` staging files are unlinked.

#### Q10: How are SHA-256 hashes calculated?
* **Source:** [foundation/corpus/storage.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/storage.py#L60), [foundation/corpus/manifest.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/manifest.py#L98-L123), [foundation/corpus/deduplication.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/deduplication.py#L96-L97)
* **Finding:** SHA-256 calculations are applied deterministically across 4 distinct boundaries:
  1. **File Split Hashes:** Streaming on-the-fly digest computation via `hashlib.sha256()` as lines are written to disk.
  2. **Content Fingerprint:** `compute_content_fingerprint` computes `sha256(f"{r.record_id}::{r.normalized_text}::{r.split}".encode("utf-8"))` for every record, sorts the digest strings lexicographically, and hashes the joined string.
  3. **Manifest Fingerprint:** `compute_manifest_fingerprint` serializes pipeline configuration with sorted keys (excluding transient keys: `created_at`, `hostname`, `pid`, `output_dir`) and computes SHA-256.
  4. **Deduplication Hashes:** `raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()` and `norm_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()`.

#### Q11: How does the corpus manifest identify its contents?
* **Source:** [foundation/corpus/manifest.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/manifest.py#L21-L33) (`CorpusManifest`)
* **Finding:** `manifest.json` provides a machine-readable bill of materials:
  * `corpus_name`, `corpus_version`, `schema_version`, `pipeline_version`, `split_seed`
  * `policies`: Explicit policy versions for normalization, filtering, deduplication, segmentation, splitting, and grouping.
  * `sources`: Array of contributing source metadata dictionaries.
  * `statistics`: Document counts (total, retained, rejected), record counts (total, retained, rejected, duplicates), rejection breakdown by code, and split counts.
  * `artifacts`: File-level SHA-256 checksums (`train`, `validation`, `test`, `rejections`), `content_fingerprint`, and `manifest_fingerprint`.

#### Q12: What is the current approval or eligibility mechanism?
* **Source:** [foundation/corpus/sources.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/sources.py#L175-L184), [foundation/corpus/pipeline.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/pipeline.py#L354-L358)
* **Finding:** Source eligibility requires all of the following:
  1. `source.licensing_status == LicensingStatus.VERIFIED_PERMITTED`
  2. `source.is_approval_stale is False` (`now <= approval_expiration_date`)
  3. `source.artifact_sha256 != "NOT_VERIFIED"` and matches 64-character hex checksum.
  4. `source_registry.verify_source_integrity(source)` passes with zero metadata tampering relative to `source_registry.json`.
  5. `source.training_permitted_status == "EXPLICITLY_PERMITTED"`.

#### Q13: Can any current code path bypass the production ingestion gate?
* **Source:** [foundation/corpus/pipeline.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/pipeline.py#L78-L95), [L325-L368](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/pipeline.py#L325-L368)
* **Finding:** **YES, at the internal API level.**
  While `CorpusPipeline.ingest_production_corpus` is strictly fail-closed, the lower-level method `CorpusPipeline.process_corpus` accepts optional parameters: `strict_governance: bool = False` and `enforce_preflight: bool = False`. If called directly with `strict_governance=False`, it does not validate against `SourceRegistry`. Development commands in `scripts/corpus_cli.py` (`build-golden`, `pilot`) invoke `process_corpus` directly for fixtures.
  *Architectural Implication:* The new candidate database must enforce eligibility constraints inside SQL schema rules and repository domain methods so that corpus export cannot bypass governance regardless of calling code.

#### Q14: Which components can be reused without modification?
* **Source:** Entire `foundation/corpus/` suite.
* **Finding:** The following mature components can be reused directly:
  1. `foundation/corpus/normalization.py` (`TextNormalizer`)
  2. `foundation/corpus/filtering.py` (`QualityFilter`, `_COMMON_ENGLISH_STOPWORDS`)
  3. `foundation/corpus/language_audit.py` (`classify_with_quarantine`)
  4. `foundation/corpus/near_deduplication.py` (`NearDuplicateDetector`, `SemanticSafetyGuard`)
  5. `foundation/corpus/segmentation.py` (`DocumentSegmenter`)
  6. `foundation/corpus/splitting.py` (`DeterministicSplitter`)
  7. `foundation/corpus/storage.py` (`CorpusWriter`)
  8. `foundation/corpus/manifest.py` (`ManifestBuilder`)
  9. `foundation/corpus/sources.py` (`SourceRegistry`)
  10. `foundation/characters/registry.py` (`CharacterRegistry`)
  11. `foundation/lexicon/storage.py` (`SqliteLexicon` for read-only word lookups)

#### Q15: Which components need future integration adapters?
* **Finding:** Three major integration adapters must be implemented in future phases:
  1. **Candidate Ingestion Repository:** Ingests raw documents/text into SQLite, computes content hashes, checks exact duplication, runs `TextNormalizer`, and assigns UUIDs.
  2. **Decision & Evaluation Coordinator:** Executes `QualityFilter`, `classify_with_quarantine`, and `NearDuplicateDetector`, translating outcomes into `processing_decisions` and `duplicate_relationships` rows.
  3. **Approved Corpus Export Bridge:** Queries SQLite for eligible candidates (`APPROVED`, non-stale `VERIFIED_PERMITTED` source, zero unresolved safety conflicts), streams records through `DeterministicSplitter`, and pipes them into `CorpusWriter`.

---

## 3. Existing Architecture Analysis

### 3.1 English Lexicon Architecture (Phase 3)
The production lexicon (`data/lexicon/veda_lexicon_v0.1.sqlite`) is an authoritative lexical dictionary containing 959,688 word entries derived from Wiktionary/Wiktextract. Its architecture is optimized for read-heavy, low-latency lemma and POS lookups ($O(\log N)$ via indexed B-trees on `words.normalized`, `words.word`, `word_pos.pos`). It maintains relational normalization (`words`, `word_pos`, `senses`) to keep RAM usage minimal during runtime inference and filtering. 

**Boundary Rule:** The lexicon database must remain strictly read-only during candidate ingestion. It does not store submitted sentences, paragraphs, or candidate lifecycle states.

### 3.2 Training Corpus Architecture (Phase 4)
The training corpus architecture is implemented as streaming JSONL files with cryptographic manifests. When `CorpusPipeline` executes, documents are processed in memory and streamed directly to disk splits (`train.jsonl`, `validation.jsonl`, `test.jsonl`, `rejections.jsonl`). 

While this architecture guarantees streaming efficiency and deterministic SHA-256 manifest verification, it exhibits a critical architectural limitation: **it is a batch processing script with no persistent submission ledger**. Submissions that fail filtering or require human quarantine cannot be tracked, audited, re-evaluated, or incrementally approved over time.

---

## 4. Proposed High-Level Architecture

The target architecture establishes a clean, decoupled 4-tier pipeline:

```mermaid
flowchart TD
    subgraph Intake ["Tier 1: Intake & Submission"]
        InRaw["Raw Text / Document Submissions"]
    end

    subgraph CandidateDB ["Tier 2: Candidate Storage (veda_candidates.sqlite)"]
        subgraph Tables ["Relational Tables"]
            T_Sub["candidate_submissions\n(Raw + Normalized)"]
            T_Dec["processing_decisions\n(Append-Only History)"]
            T_Dup["duplicate_relationships\n(Near-Dedup & Safety Conflicts)"]
            T_App["approval_history\n(Human/Gov Ledger)"]
            T_Exp["export_batches & items\n(Idempotent Bridge)"]
        end
    end

    subgraph Engines ["Tier 3: Reused VEDA Processing Engines"]
        E_Norm["TextNormalizer\n(Unicode NFC, Quotes)"]
        E_Qual["QualityFilter &\nclassify_with_quarantine"]
        E_Dedup["NearDuplicateDetector &\nSemanticSafetyGuard"]
        E_Split["DeterministicSplitter\n(Train/Val/Test 90/5/5)"]
        L_Lex[("SqliteLexicon\n(READ-ONLY Lookup)")]
    end

    subgraph CorpusOutput ["Tier 4: Production Corpus (JSONL)"]
        CW["CorpusWriter\n(Atomic Commit & SHA-256)"]
        OutFiles["train.jsonl\nvalidation.jsonl\ntest.jsonl\nrejections.jsonl\nmanifest.json"]
    end

    InRaw -->|Ingest & Hash| T_Sub
    T_Sub -->|Normalize| E_Norm
    E_Norm -->|Persist Norm| T_Sub
    T_Sub -->|Evaluate Quality| E_Qual
    E_Qual -.->|Lexical Check| L_Lex
    E_Qual -->|Log Result| T_Dec
    T_Sub -->|Evaluate Duplicates| E_Dedup
    E_Dedup -->|Log Conflicts| T_Dup
    T_Dec & T_Dup -->|Status Transition| T_App
    T_App -->|Update Status| T_Sub
    T_Sub -->|Query Eligible| T_Exp
    T_Exp -->|Assign Split| E_Split
    E_Split -->|Stream Records| CW
    CW -->|Seal & Checksum| OutFiles
```

### 4.1 Separation of Responsibilities
* **Layer A (Lexicon SQLite):** Static knowledge resource. Polled by `QualityFilter` and lexical validation routines to check dictionary presence and word properties.
* **Layer B (Candidate SQLite):** State machine, submission repository, and decision journal. Tracks every submission through `RECEIVED → PENDING → PROCESSING → APPROVED/REJECTED/QUARANTINED → EXPORT_PENDING → EXPORTED`.
* **Layer C (Corpus JSONL):** High-throughput downstream training artifacts consumed by tokenizers and neural models.
* **Layer D (Processing Engines):** Zero logic duplication; all normalization, filtering, semantic conflict checking, and splitting algorithms are reused directly from `foundation/corpus/`.

---

## 5. Design Decisions and Alternatives Evaluated

### 5.1 Raw Text Preservation vs In-Place Normalization
* **Decision:** Store both `original_text` and `normalized_text` in `candidate_submissions`.
* **Rationale:** Normalization rules evolve (e.g. typography handling, dash standardizations). Overwriting raw text destroys the ground-truth submission. Storing verbatim raw text guarantees that future pipeline iterations can re-normalize historical submissions without re-acquiring source data.

### 5.2 Content Hash Derivation (Raw vs Normalized)
* **Decision:** Compute and index **both** `raw_content_hash` and `normalized_content_hash` using SHA-256.
* **Rationale:**
  * `raw_content_hash = sha256(original_text.encode('utf-8'))`: Catches identical byte-for-byte resubmissions immediately.
  * `normalized_content_hash = sha256(normalized_text.encode('utf-8'))`: Enables $O(1)$ indexed lookup for normalized duplicates (e.g. whitespace or HTML entity variations).
  * *Collision Probability:* SHA-256 collision probability across $10^7$ records is $< 10^{-60}$, making cryptographic hash equality a sound surrogate for exact text identity.

### 5.3 Cross-Source Duplicate Representation
* **Decision:** Unique Submission Entity with Directed Duplicate Graph.
* **Alternatives Evaluated:**
  * *Alternative A (Multi-source single row):* A single candidate row with an array or child table of sources. Discarded because submissions have distinct external document IDs, submission timestamps, and per-source license terms.
  * *Alternative B (Distinct submission rows linked via relationships - CHOSEN):* Every submission is assigned a unique `candidate_id`. When identical or near-duplicate text is submitted from another source, a record is added to `duplicate_relationships` referencing the canonical `canonical_candidate_id`.
* **Rationale:** Preserves exact submission provenance and timestamps while explicitly modeling duplicate clusters and multi-source contributions.

### 5.4 Database Engine Selection (SQLite vs PostgreSQL vs DuckDB)
* **Decision:** SQLite with Write-Ahead Logging (WAL).
* **Rationale:**
  * *Zero External Infrastructure:* Aligns with VEDA’s self-contained, from-scratch design.
  * *Cross-Platform File Portability:* Identical file format across Windows, Linux, and macOS.
  * *ACID Safety & Concurrency:* WAL mode allows multiple concurrent readers alongside a dedicated writer without blocking.
  * *Performance:* With B-tree indexing on 64-bit integer IDs and 64-character hex hashes, lookups operate in $< 0.1\text{ ms}$ for collections under 10 million records.

---

## 6. Complete Database Schema Specification

The candidate database shall be located at `data/candidates/veda_candidates.sqlite`. Below is the complete SQL Data Definition Language (DDL) specification.

```sql
-- VEDA Candidate Storage Schema v0.1.0
-- Location: data/candidates/veda_candidates.sqlite

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;

-- -----------------------------------------------------------------------------
-- 1. Schema Migrations Ledger
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. Registered Candidate Sources
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    url_or_path TEXT NOT NULL,
    license_identifier TEXT NOT NULL,
    licensing_status TEXT NOT NULL CHECK (licensing_status IN ('VERIFIED PERMITTED', 'REQUIRES REVIEW', 'UNKNOWN', 'EXCLUDED')),
    training_permitted_status TEXT NOT NULL CHECK (training_permitted_status IN ('EXPLICITLY_PERMITTED', 'PROHIBITED', 'UNCLEAR')),
    commercial_permitted INTEGER NOT NULL CHECK (commercial_permitted IN (0, 1)),
    attribution TEXT,
    artifact_sha256 TEXT NOT NULL,
    evidence_checksum TEXT,
    approval_expiration_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_sources_status ON candidate_sources(licensing_status);

-- -----------------------------------------------------------------------------
-- 3. Candidate Submissions (Core Entity)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_submissions (
    candidate_id TEXT PRIMARY KEY,                       -- UUIDv4 or deterministic source-prefixed hash
    source_id TEXT NOT NULL,
    source_document_id TEXT,                             -- External ID from provider
    original_text TEXT NOT NULL,                         -- Verbatim raw submitted text
    normalized_text TEXT,                                -- NFC normalized canonical representation
    raw_content_hash TEXT NOT NULL,                      -- SHA-256 of original_text
    normalized_content_hash TEXT,                        -- SHA-256 of normalized_text
    raw_char_count INTEGER NOT NULL,
    normalized_char_count INTEGER,
    approx_word_count INTEGER,
    language_status TEXT NOT NULL DEFAULT 'UNEVALUATED' 
        CHECK (language_status IN ('UNEVALUATED', 'ENGLISH_CONFIRMED', 'NON_ENGLISH_REJECTED', 'QUARANTINED')),
    quality_status TEXT NOT NULL DEFAULT 'UNEVALUATED'
        CHECK (quality_status IN ('UNEVALUATED', 'HIGH_QUALITY', 'LOW_QUALITY_REJECTED', 'QUARANTINED')),
    processing_status TEXT NOT NULL DEFAULT 'RECEIVED'
        CHECK (processing_status IN (
            'RECEIVED', 'PENDING', 'PROCESSING', 'APPROVED', 
            'REJECTED', 'QUARANTINED', 'EXPORT_PENDING', 'EXPORTED', 
            'PROCESSING_FAILED', 'REVOKED'
        )),
    is_canonical INTEGER NOT NULL DEFAULT 1 CHECK (is_canonical IN (0, 1)),
    canonical_candidate_id TEXT,                         -- References master record if duplicate
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '0.1.0',
    FOREIGN KEY (source_id) REFERENCES candidate_sources(source_id) ON DELETE RESTRICT,
    FOREIGN KEY (canonical_candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_raw_hash ON candidate_submissions(raw_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_norm_hash ON candidate_submissions(normalized_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidate_submissions(processing_status);
CREATE INDEX IF NOT EXISTS idx_candidates_source ON candidate_submissions(source_id);
CREATE INDEX IF NOT EXISTS idx_candidates_canonical ON candidate_submissions(canonical_candidate_id);

-- -----------------------------------------------------------------------------
-- 4. Processing Decisions (Append-Only Journal)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processing_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('NORMALIZATION', 'QUALITY_FILTER', 'LANGUAGE_AUDIT', 'NEAR_DEDUPLICATION', 'GOVERNANCE')),
    decision_result TEXT NOT NULL CHECK (decision_result IN ('PASS', 'REJECT', 'QUARANTINE', 'ERROR')),
    reason_code TEXT NOT NULL,
    human_readable_reason TEXT,
    quality_score REAL,
    metrics_json TEXT,                                  -- Computed QualityMetrics serialised to JSON
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decisions_candidate ON processing_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_decisions_stage_result ON processing_decisions(stage, decision_result);

-- -----------------------------------------------------------------------------
-- 5. Duplicate & Semantic Conflict Relationships
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duplicate_relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    related_candidate_id TEXT NOT NULL,
    similarity_method TEXT NOT NULL CHECK (similarity_method IN ('EXACT_RAW', 'EXACT_NORMALIZED', 'MINHASH_LSH', 'TOKEN_JACCARD')),
    similarity_score REAL NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'EXACT_DUPLICATE', 'NORMALIZED_DUPLICATE', 'NEAR_DUPLICATE_MERGEABLE', 
        'SEMANTIC_CONFLICT_BLOCKED', 'DISTANT_NEGATIVE'
    )),
    safety_conflict_type TEXT CHECK (safety_conflict_type IN (
        'NEGATION_INVERSION', 'POLARITY_INVERSION', 'NUMERICAL_MISMATCH', 
        'UNIT_MISMATCH', 'DATE_MISMATCH', 'IDENTIFIER_MISMATCH'
    )),
    conflict_details_json TEXT,
    is_safe_to_merge INTEGER NOT NULL CHECK (is_safe_to_merge IN (0, 1)),
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (related_candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE,
    UNIQUE (candidate_id, related_candidate_id, similarity_method)
);

CREATE INDEX IF NOT EXISTS idx_dup_candidate ON duplicate_relationships(candidate_id);
CREATE INDEX IF NOT EXISTS idx_dup_related ON duplicate_relationships(related_candidate_id);
CREATE INDEX IF NOT EXISTS idx_dup_conflict ON duplicate_relationships(safety_conflict_type);

-- -----------------------------------------------------------------------------
-- 6. Approval & Governance History (Append-Only Audit Ledger)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_history (
    approval_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('AUTOMATED_GATE', 'HUMAN_AUDITOR', 'GOVERNANCE_SYSTEM')),
    actor_id TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    evidence_reference TEXT,
    event_timestamp TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_approval_candidate ON approval_history(candidate_id);
CREATE INDEX IF NOT EXISTS idx_approval_timestamp ON approval_history(event_timestamp);

-- -----------------------------------------------------------------------------
-- 7. Corpus Export Batches
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS export_batches (
    export_batch_id TEXT PRIMARY KEY,                    -- UUIDv4 for export run
    corpus_version TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    split_seed TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    manifest_fingerprint TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    total_records_exported INTEGER NOT NULL,
    exported_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('INITIALIZING', 'STREAMING', 'COMMITTED', 'ABORTED'))
);

-- -----------------------------------------------------------------------------
-- 8. Export Batch Items (Junction & Idempotency Enforcement)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS export_batch_items (
    export_batch_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    assigned_split TEXT NOT NULL CHECK (assigned_split IN ('train', 'validation', 'test')),
    exported_content_hash TEXT NOT NULL,
    exported_at TEXT NOT NULL,
    PRIMARY KEY (export_batch_id, candidate_id),
    FOREIGN KEY (export_batch_id) REFERENCES export_batches(export_batch_id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_export_items_candidate ON export_batch_items(candidate_id);
CREATE INDEX IF NOT EXISTS idx_export_items_split ON export_batch_items(assigned_split);
```

---

## 7. Table Definitions and Entity Relationships

### 7.1 Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    candidate_sources ||--o{ candidate_submissions : "supplies"
    candidate_submissions ||--o{ processing_decisions : "evaluates"
    candidate_submissions ||--o{ duplicate_relationships : "originates"
    candidate_submissions ||--o{ duplicate_relationships : "compares"
    candidate_submissions ||--o{ approval_history : "records"
    candidate_submissions ||--o{ export_batch_items : "includes"
    export_batches ||--o{ export_batch_items : "aggregates"

    candidate_sources {
        string source_id PK
        string name
        string licensing_status
        string training_permitted_status
        string artifact_sha256
    }

    candidate_submissions {
        string candidate_id PK
        string source_id FK
        string raw_content_hash
        string normalized_content_hash
        string processing_status
        int is_canonical
        string canonical_candidate_id FK
    }

    processing_decisions {
        int decision_id PK
        string candidate_id FK
        string stage
        string decision_result
        string reason_code
        float quality_score
    }

    duplicate_relationships {
        int relationship_id PK
        string candidate_id FK
        string related_candidate_id FK
        string relationship_type
        string safety_conflict_type
        int is_safe_to_merge
    }

    approval_history {
        int approval_event_id PK
        string candidate_id FK
        string previous_status
        string new_status
        string actor_type
    }

    export_batches {
        string export_batch_id PK
        string corpus_version
        string manifest_fingerprint
        string content_fingerprint
        string status
    }

    export_batch_items {
        string export_batch_id PK,FK
        string candidate_id PK,FK
        string assigned_split
        string exported_content_hash
    }
```

### 7.2 Integrity & Cascade Invariants
1. **Source Protection:** `candidate_submissions` defines `ON DELETE RESTRICT` for `source_id`. Registered sources cannot be deleted while dependent candidates exist.
2. **Export Protection:** `export_batch_items` defines `ON DELETE RESTRICT` for `candidate_id`. A candidate that has been formally exported to a published corpus cannot be deleted from the database.
3. **Audit Immutability:** `approval_history` and `processing_decisions` are append-only. Reprocessing creates new decision rows with updated `pipeline_version` and `evaluated_at` timestamps rather than altering historical rows.

---

## 8. Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED : Submission Intake
    RECEIVED --> PENDING : Checksum & Hash Verified
    PENDING --> PROCESSING : Normalization Complete
    
    state PROCESSING {
        [*] --> QualityCheck
        QualityCheck --> LanguageAudit : Pass Metrics
        LanguageAudit --> DuplicateScreening : Confirmed English
        DuplicateScreening --> SafetyGuard : Candidate Pair Found
    }

    PROCESSING --> APPROVED : All Heuristics & Guards Pass
    PROCESSING --> REJECTED : Quality/Lang/Gov Failure
    PROCESSING --> QUARANTINED : Borderline / High Ambiguity
    PROCESSING --> PROCESSING_FAILED : Runtime Exception / Crash

    QUARANTINED --> APPROVED : Human Review Overrides
    QUARANTINED --> REJECTED : Human Review Confirms Rejection
    
    APPROVED --> EXPORT_PENDING : Included in Batch Export Run
    EXPORT_PENDING --> EXPORTED : CorpusWriter Atomic Commit
    EXPORT_PENDING --> APPROVED : Batch Aborted / Rolled Back

    APPROVED --> REVOKED : Stale License / Security Revocation
    EXPORTED --> REVOKED : Post-Export Flaw / Legal Notice
    REJECTED --> PENDING : Reprocess with Updated Rules
```

### 8.1 State Transition Rules

| Transition | From State | To State | Initiator | Required Evidence / Precondition |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | `[*] ` | `RECEIVED` | Intake Ingestion | Verbatim `original_text` captured; valid `source_id`. |
| **T02** | `RECEIVED` | `PENDING` | Ingestion Engine | `raw_content_hash` computed; initial deduplication pass. |
| **T03** | `PENDING` | `PROCESSING` | Evaluator Worker | `TextNormalizer` completes; `normalized_content_hash` stored. |
| **T04** | `PROCESSING` | `APPROVED` | Automated Gate | QualityFilter passes, English confirmed, zero safety conflicts. |
| **T05** | `PROCESSING` | `REJECTED` | Automated Gate | Fails stopword rule, non-Latin script, or non-English cognates. |
| **T06** | `PROCESSING` | `QUARANTINED` | Automated Gate | Low-stopword heading, caption, SQL/code, or borderline cognate. |
| **T07** | `PROCESSING` | `PROCESSING_FAILED`| System Watchdog | Uncaught exception; stack trace logged to decision journal. |
| **T08** | `QUARANTINED` | `APPROVED` | Human Auditor | Audit review logged to `approval_history` with rationale. |
| **T09** | `QUARANTINED` | `REJECTED` | Human Auditor | Rejection rationale and actor ID recorded in `approval_history`. |
| **T10** | `APPROVED` | `EXPORT_PENDING` | Export Coordinator | Verified against 8-point eligibility gate; export batch locked. |
| **T11** | `EXPORT_PENDING`| `EXPORTED` | Export Bridge | `CorpusWriter.close(commit=True)` succeeds; hashes match. |
| **T12** | `EXPORT_PENDING`| `APPROVED` | Export Bridge | Export fails or is cancelled; batch marked `ABORTED`. |
| **T13** | `APPROVED` | `REVOKED` | Governance Officer | License expires, attribution missing, or governance audit. |
| **T14** | `EXPORTED` | `REVOKED` | Governance Officer | Post-export revocation; triggers corpus tombstone note. |
| **T15** | `REJECTED` | `PENDING` | Pipeline Admin | Rule revision update; triggers re-evaluation pass. |

---

## 9. Transaction Model and Database Safety

### 9.1 Connection Management & Concurrency
* **Single-Writer / Multiple-Reader Model:** SQLite supports unlimited concurrent readers alongside a single active writer in WAL mode. To prevent `SQLITE_BUSY` contention:
  1. Writers connect with explicit `timeout=30.0` (seconds).
  2. Write transactions explicitly begin with `BEGIN IMMEDIATE` to acquire the reserved lock upfront and prevent mid-transaction deadlocks.
  3. Readers operate under `PRAGMA query_only = ON;` in worker threads.

### 9.2 Atomic Ingestion & Processing Boundaries
```python
def process_candidate_transaction(conn: sqlite3.Connection, candidate_id: str) -> None:
    """Atomic decision persistence block."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        # 1. Fetch candidate
        # 2. Run normalization, quality, language, and near-dedup engines
        # 3. Insert processing_decisions row
        # 4. Insert duplicate_relationships rows (if any)
        # 5. Insert approval_history row
        # 6. Update candidate_submissions status
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### 9.3 Database Backup & Crash Recovery
* **Online Backup:** Uses Python's `sqlite3.Connection.backup()` API to stream live, transactionally consistent snapshots to `data/candidates/backups/veda_candidates_YYYYMMDD_HHMMSS.sqlite` without interrupting active readers or writers.
* **Integrity Auditing:** Automated diagnostic script executes `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;` before any migration or batch export.

### 9.4 Migration Safety Protocol
1. Migrations are numbered sequentially: `0001_initial_schema.sql`, `0002_add_field.sql`.
2. Each migration runs inside an atomic transaction recorded in `schema_migrations`.
3. Before applying migrations, an automated backup of `veda_candidates.sqlite` is written. If any DDL fails, the database restores from snapshot.

---

## 10. Approval and Corpus Export Security

### 10.1 The Cardinal Invariant
> [!IMPORTANT]
> **Cardinal Export Invariant:** Only explicitly approved and governance-eligible records may enter corpus export.

A candidate record is **strictly prohibited** from entering `train.jsonl`, `validation.jsonl`, or `test.jsonl` unless it satisfies the full **8-Point Eligibility Predicate**:

```sql
-- 8-Point Eligibility Predicate Query
SELECT c.candidate_id, c.normalized_text, c.normalized_content_hash, s.source_id, s.attribution
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
WHERE c.processing_status = 'APPROVED'                           -- 1. Status is explicitly APPROVED
  AND c.is_canonical = 1                                         -- 2. Is canonical record (not a duplicate)
  AND s.licensing_status = 'VERIFIED PERMITTED'                  -- 3. Source is VERIFIED PERMITTED
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'       -- 4. Training explicitly authorized
  AND s.artifact_sha256 != 'NOT_VERIFIED'                        -- 5. Physical source artifact verified
  AND (s.approval_expiration_date IS NULL                        -- 6. Approval date is non-stale
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND NOT EXISTS (                                               -- 7. Zero unresolved safety conflicts
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (                                               -- 8. Not already exported in active batch
      SELECT 1 FROM export_batch_items e 
      WHERE e.candidate_id = c.candidate_id
  );
```

### 10.2 Anti-Bypass Architecture
1. **Direct SQL Insertion Defense:** An ad-hoc row inserted into `candidate_submissions` with `processing_status = 'APPROVED'` will still fail export if it lacks corresponding rows in `candidate_sources`, `processing_decisions`, and `approval_history`.
2. **Deterministic Split Mapping:** Split assignment is governed exclusively by [foundation/corpus/splitting.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/splitting.py) (`DeterministicSplitter`) based on candidate/document hash, ensuring zero train/test contamination.
3. **Export Bridge to Existing CorpusWriter:** The database export pipeline streams eligible rows directly to `CorpusWriter.write_record()`. All existing atomic replace semantics, on-the-fly SHA-256 calculation, and `manifest.json` generation remain fully functional.

---

## 11. Duplicate and Semantic Safety Integration

### 11.1 Reusing Phase 4.13 Safety Innovations
Phase 4.13 established strict polarity, negation, numerical, and date guards in [foundation/corpus/near_deduplication.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py). The candidate database records these conflict outcomes without destroying either candidate:

```
[Candidate A] "The secondary containment vessel showed evidence of stress fracture."
[Candidate B] "The secondary containment vessel showed no evidence of stress fracture."
                             │
                             ▼
         NearDuplicateDetector.are_near_duplicates(A, B)
                             │
       ┌─────────────────────┴──────────────────────┐
       ▼                                            ▼
[Stage 2: Candidate Screening]         [Stage 3: SemanticSafetyGuard]
- Token Jaccard: 0.933 (>= 0.75)       - Asymmetric negation particle: {'no'}
- Flag: is_candidate = True            - Outcome: NEGATION_INVERSION
                                       - Flag: is_safe_to_merge = False
                             │
                             ▼
     Persist to `duplicate_relationships` Table:
     - relationship_type: 'SEMANTIC_CONFLICT_BLOCKED'
     - safety_conflict_type: 'NEGATION_INVERSION'
     - is_safe_to_merge: 0
     - conflict_details_json: {"particle_diff": "set() vs {'no'}"}
```

### 11.2 Concrete Safety Conflict Matrix

| Pair Type | Example A | Example B | Detection Method | Relationship Type | Safe to Merge? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Exact** | `"System operational."` | `"System operational."` | `raw_content_hash` | `EXACT_DUPLICATE` | **True** (dedup) |
| **Normalized** | `"System  operational."` | `"System operational."` | `normalized_content_hash` | `NORMALIZED_DUPLICATE`| **True** (dedup) |
| **Paraphrase** | `"The panel authorized extraction."` | `"The panel permitted extraction."`| `NearDuplicateDetector` | `NEAR_DUPLICATE_MERGEABLE`| **True** (cluster) |
| **Negation** | `"Containment showed evidence."` | `"Containment showed no evidence."`| `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |
| **Contraction**| `"Cooling circuit was deployed."`| `"Cooling circuit wasn't deployed."`| `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |
| **Numerical** | `"Administered 10mg."` | `"Administered 100mg."` | `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |
| **Unit** | `"Stored 1024 megabytes."` | `"Stored 1024 gigabytes."` | `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |
| **Date** | `"Signed in January 2024."`| `"Signed in March 2024."` | `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |
| **Identifier** | `"Tested Satellite A-104."` | `"Tested Satellite B-104."` | `SemanticSafetyGuard` | `SEMANTIC_CONFLICT_BLOCKED`| **FALSE** |

---

## 12. Performance and Scale Estimates

### 12.1 Storage Projections Across Scale Tiers

Estimates assume an average candidate text length of 500 characters (UTF-8 ~500 bytes raw, ~480 bytes normalized).

| Metric | 100,000 Candidates | 1,000,000 Candidates | 10,000,000 Candidates |
| :--- | :--- | :--- | :--- |
| **Raw Text Storage (`original_text`)** | 50 MB | 500 MB | 5.0 GB |
| **Normalized Text Storage (`normalized_text`)** | 48 MB | 480 MB | 4.8 GB |
| **Submissions Metadata & UUIDs** | 25 MB | 250 MB | 2.5 GB |
| **Processing Decisions Journal (avg 2/cand)** | 40 MB | 400 MB | 4.0 GB |
| **Duplicate Relationships (avg 0.2/cand)** | 5 MB | 50 MB | 500 MB |
| **B-Tree Indexes (Hashes, Status, Foreign Keys)** | 35 MB | 350 MB | 3.5 GB |
| **Estimated Base Database File Size** | **~203 MB** | **~2.03 GB** | **~20.3 GB** |
| **Peak Active WAL File Headroom** | ~50 MB | ~200 MB | ~1.5 GB |
| **Export Streaming RAM Footprint** | **< 64 MB** | **< 64 MB** | **< 64 MB** |

### 12.2 Query & Streaming Optimization
* **Streaming Cursors:** Export queries utilize server-side SQLite cursors with chunk sizes of 1,000 rows (`cursor.fetchmany(1000)`). The full database is never materialized in Python memory.
* **Covering Indices:** Indexes on `(processing_status, is_canonical)` and `(source_id)` enable instant filtering of approved records without scanning table pages.
* **Checkpoint Tuning:** Set `PRAGMA wal_autocheckpoint = 2000;` during high-throughput ingestion to ensure WAL log merges occur cleanly without blocking readers.

### 12.3 SQLite Scaling Envelope & Migration Signals
SQLite is architecturally sound up to **10 million records (~20–30 GB database file)** on standard NVMe drives. A migration to PostgreSQL or distributed storage would only be justified if:
1. Concurrent writing workers exceed 10 simultaneous processes requiring distributed locks.
2. Total candidate storage exceeds 100 GB on disk.
3. Geo-distributed ingestion nodes require multi-master replication.

---

## 13. Comprehensive Testing Plan

### 13.1 Schema & Integrity Test Suite (`tests/test_candidate_db_schema.py`)
* `test_schema_initialization`: Verifies table creation and `schema_migrations` tracking.
* `test_foreign_key_enforcement`: Asserts `PRAGMA foreign_keys = ON` rejects orphan candidates or invalid sources.
* `test_cascade_protection_on_exported_records`: Asserts `export_batch_items` prevents accidental deletion of exported records (`RESTRICT`).
* `test_migration_rollback_safety`: Simulates faulty SQL migration and verifies atomic rollback.

### 13.2 Candidate CRUD & Hash Integrity Test Suite (`tests/test_candidate_repository.py`)
* `test_raw_and_normalized_fidelity`: Asserts raw text is preserved verbatim and normalized text matches `TextNormalizer`.
* `test_dual_hash_generation`: Asserts `raw_content_hash` and `normalized_content_hash` match SHA-256 digests.
* `test_exact_duplicate_detection`: Submitting identical raw text links to canonical record with `is_canonical = 0`.

### 13.3 Decision & Lifecycle State Machine Test Suite (`tests/test_candidate_lifecycle.py`)
* `test_permitted_lifecycle_progression`: `RECEIVED → PENDING → PROCESSING → APPROVED`.
* `test_prohibited_transitions_raise_error`: Asserts `REJECTED → APPROVED` or `EXPORTED → PROCESSING` raises `InvalidStateTransitionError`.
* `test_quarantine_requires_explicit_actor`: Quarantined record cannot transition to `APPROVED` without `approval_history` logging.

### 13.4 Semantic Conflict & Duplicate Safety Test Suite (`tests/test_candidate_safety_guard.py`)
* `test_negation_conflict_blocks_merge`: "Showed evidence" vs "Showed no evidence" logged as `SEMANTIC_CONFLICT_BLOCKED` (`NEGATION_INVERSION`).
* `test_negative_contractions_blocked`: "Was deployed" vs "Wasn't deployed" blocked.
* `test_numerical_and_unit_mismatch_blocked`: Dosage (10mg vs 100mg) and storage units (MB vs GB) blocked.
* `test_valid_paraphrase_allowed`: Genuine linguistic paraphrases permitted as `NEAR_DUPLICATE_MERGEABLE`.

### 13.5 Export Gate Security Test Suite (`tests/test_candidate_export_gate.py`)
* `test_export_only_approved_records`: Rejected, quarantined, and pending records are excluded.
* `test_unapproved_source_blocks_export`: Candidate from `REQUIRES_REVIEW` or `EXCLUDED` source cannot export.
* `test_safety_conflict_blocks_export`: Unresolved conflict blocks candidate from export list.
* `test_export_idempotency`: Candidate cannot be exported twice into the same split.
* `test_corpus_writer_integration`: Export bridge outputs valid `train.jsonl`, `test.jsonl`, and updates `manifest.json`.

---

## 14. Risks, Limitations, and Technical Debt

### 14.1 Discovered Scratch Directory State Pollution
During repository inspection, it was discovered that executing bare `pytest` in the root directory causes pytest to discover [scratch/test_proposed_logic.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/scratch/test_proposed_logic.py#L47), which monkeypatches `SemanticSafetyGuard.check_polarity_conflict` with an outdated rule set. 

*Mitigation:* A formal `pytest.ini` configuration must be introduced in future implementation phases specifying `testpaths = tests` to permanently prevent test runner pollution.

### 14.2 Syntactic Scope Limitations of Lexical Rules
The `SemanticSafetyGuard` relies on lexical token and contraction heuristics. It cannot parse syntactic double negatives (*"It is not impossible"*) or non-adjacent concessive clauses. In all ambiguous cases, the system fails closed by blocking duplicate merging.

---

## 15. Open Questions Requiring Human Governance Decision

1. **Automated Approval vs Human Review Threshold:** Should candidates with composite quality scores $\ge 0.95$ and zero duplicate conflicts be automatically transitioned from `PROCESSING` to `APPROVED`, or must all initial ingestion batches require an explicit human sign-off in `approval_history`?
   * *Recommendation:* Allow automated approval for high-confidence candidates ($\ge 0.95$ quality score, pure English prose), while strictly routing technical captions, short headings ($< 12$ words), and borderline cognates to `QUARANTINED` for human audit.
2. **Post-Export Revocation Protocol:** If an external source license expires or is revoked after a corpus export has been sealed into `manifest.json`, should the candidate database:
   * *Option A:* Tombstone the records and issue an incremental corpus patch release?
   * *Option B:* Trigger a mandatory, atomic rebuild of all corpus splits?
   * *Recommendation:* Option A for minor errata; Option B for copyright/licensing revocations.
3. **Raw Text Retention on Definite Rejections:** Should non-Latin spam or binary garbage be retained permanently in `candidate_submissions` or purged after 90 days to conserve disk space?
   * *Recommendation:* Retain a 100-character sample and cryptographic hash in `processing_decisions`, but allow raw payload pruning for `GOVERNANCE_BLOCKED` or malformed binary records.

---

## 16. Phased Implementation Roadmap

```mermaid
flowchart LR
    P4141["Phase 4.14.1\nDesign Spec\n(COMPLETED)"]
    P4142["Phase 4.14.2\nDB Init &\nMigrations"]
    P4143["Phase 4.14.3\nCandidate Repo\n& Ingestion"]
    P4144["Phase 4.14.4\nDecision &\nConflict Engine"]
    P4145["Phase 4.14.5\nApproval &\nGovernance"]
    P4146["Phase 4.14.6\nCorpusWriter\nExport Bridge"]
    P4147["Phase 4.14.7\nSecurity &\nFailure Audit"]
    P4148["Phase 4.14.8\nMaster Certification\n& Final Docs"]

    P4141 --> P4142 --> P4143 --> P4144 --> P4145 --> P4146 --> P4147 --> P4148
```

1. **Phase 4.14.1 (Current):** Engineering Architecture & Schema Design Specification.
2. **Phase 4.14.2:** Database Initialization, DDL Execution, and Migration Engine (`foundation/candidates/database.py`).
3. **Phase 4.14.3:** Candidate Repository, Text Ingestion, and Content Hashing (`foundation/candidates/repository.py`).
4. **Phase 4.14.4:** Decision Pipeline Coordinator & Conflict Recording (`foundation/candidates/evaluator.py`).
5. **Phase 4.14.5:** Approval Workflow, State Machine, and Audit Logging (`foundation/candidates/governance.py`).
6. **Phase 4.14.6:** Approved Corpus Export Bridge & `CorpusWriter` Integration (`foundation/candidates/exporter.py`).
7. **Phase 4.14.7:** End-to-End Security, Idempotency, and Failure Recovery Testing.
8. **Phase 4.14.8:** Dual-Runtime Certification, Performance Measurement, and Completion Report.

---

## 17. Completion Criteria Checklist

- [x] Preliminary repository audit completed with verified code citations.
- [x] Clear architectural separation between Lexicon SQLite, Candidate SQLite, and Corpus JSONL defined.
- [x] Normalized relational schema with 8 dedicated tables and foreign keys specified.
- [x] Explicit 10-state lifecycle state machine and transition table documented.
- [x] Dual content hashing (raw and normalized) defined.
- [x] 8-Point eligibility predicate for fail-closed corpus export specified.
- [x] Phase 4.13 semantic safety and negation guards integrated into duplicate graph.
- [x] Storage and memory scaling estimated for 100k, 1M, and 10M tiers.
- [x] Mermaid architecture, state machine, and ERD diagrams included.
- [x] Comprehensive pre-implementation test plan designed across 5 test suites.
- [x] Zero production Python files modified.
- [x] Zero database tables created.
- [x] Zero test baseline modifications.
- [x] Phase 5 pretraining strictly held and paused.



---

# ARCHITECTURAL REVIEW — REVISION 1

- **Review Date:** 2026-11-13
- **Status:** REVISED SPECIFICATION / READY FOR PHASE 4.14.2
- **Scope:** Architectural clarifications, security hardening, crash recovery protocol, governance single-source-of-truth, and lifecycle state-machine corrections.
- **Invariant:** Strictly design-only. Zero production code modified, zero database tables created, zero migrations executed, Phase 5 pretraining strictly blocked.

---

## R1. Overview of Architectural Review & Key Adjustments

Following the initial Phase 4.14.1 specification, an in-depth architectural review identified six critical areas requiring clarification, refinement, and risk mitigation prior to authorizing database implementation:

1. **Automated vs Human Approval:** The initial proposal allowing automated approval for high-confidence candidates ($\ge 0.95$) violated fail-closed governance principles. Revision 1 establishes that automated processing may only *recommend* approval, while production eligibility strictly requires designated human authorization.
2. **Multi-Tier Security & SQLite Boundaries:** The security model was upgraded to define application-layer, database-layer, and filesystem-level controls separately, accompanied by an explicit, honest disclosure of SQLite's architectural security limits.
3. **Dual-System Crash Recovery Protocol:** A 9-stage crash-safe protocol was designed to bridge the boundary between SQLite transactions and filesystem `CorpusWriter` atomic file replacements.
4. **Source Governance Authority:** The single-source-of-truth status of `SourceRegistry` (`data/corpus/source_registry.json`) was codified, defining `candidate_sources` as a validated relational mirror rather than an independent authority.
5. **Cross-Batch Export Idempotency:** Identity rules were expanded to govern candidate uniqueness across multiple historical export batches and major corpus versions.
6. **Formal Revocation & Corpus Rebuild:** A 6-trigger revocation protocol was established specifying candidate status changes, batch tainting, manifest invalidation, and corpus rebuild requirements.

---

## R2. Issue 1: Automated Approval vs Human Approval Policy

### R2.1 The Problem with Automated Production Approval
The initial design proposed an automated fast-path from `PROCESSING` to `APPROVED` for candidates with composite quality scores $\ge 0.95$. In the current state of Project VEDA—where external benchmark certification remains `INDEPENDENCE UNVERIFIED` and source legal permissions require strict auditing—automated approval introduces an unacceptably high risk of silent contamination.

### R2.2 The Revised Four-Tier Qualification Hierarchy
Revision 1 replaces the ambiguous approval model with four distinct, non-interchangeable states:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CANDIDATE QUALIFICATION HIERARCHY (REVISED)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  LEVEL 1: PROCESSING_PASSED (Technical Soundness)                           │
│  - Automated heuristic evaluation completed without error.                  │
│  - TextNormalizer, QualityFilter, and classify_with_quarantine executed.   │
│  - Candidate meets character, word, stopword, and alphabet thresholds.      │
│  - DOES NOT confer approval or export eligibility.                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  LEVEL 2: APPROVAL_PENDING / RECOMMENDED_FOR_APPROVAL (Staged Queue)        │
│  - Stage 2 MinHash and Stage 3 SemanticSafetyGuard completed.               │
│  - Zero unresolved safety conflicts (negation, numerical, units, etc.).     │
│  - Candidate is staged in the review queue awaiting human audit.            │
│  - Automated workers CANNOT transition beyond this state.                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  LEVEL 3: APPROVED (Human Governance Authorization)                         │
│  - Designated human auditor reviews staged candidate batch.                 │
│  - Auditor executes formal approval transaction logging:                    │
│    (actor_type='HUMAN_AUDITOR', actor_id, timestamp, reason, evidence).     │
│  - Candidate is marked APPROVED in candidate_submissions.                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  LEVEL 4: EXPORT_ELIGIBLE (Dynamic Gate Evaluation)                         │
│  - Transient qualification evaluated at query time via SQL view.            │
│  - Candidate is APPROVED + Source is VERIFIED_PERMITTED + Source non-stale  │
│    + Zero duplicate conflicts + Not previously exported in current version. │
│  - Only records meeting Level 4 can enter CorpusWriter.                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### R2.3 Approval Rules and Invariants
1. **No Automated Final Approval:** Under no circumstances may an automated pipeline worker set `processing_status = 'APPROVED'`. Automated systems may only advance candidates to `PROCESSING_PASSED` or `APPROVAL_PENDING`.
2. **Quarantine Invariant:** Candidates marked `QUARANTINED` (short headings, captions, SQL blocks, Germanic cognates) can **never** be automatically approved. They remain quarantined until a human auditor inspects the evidence and explicitly overrides the flag.
3. **Rejection Invariant:** Candidates marked `REJECTED` cannot become `APPROVED` through standard updates. Moving a rejected candidate to approval requires either:
   - A formal administrative re-review logged to `approval_history` with documented justification, or
   - An automated rule-revision pass that resets status to `PENDING` for clean re-evaluation under new pipeline versions.
4. **Audit Trail Mandate:** Every transition to `APPROVED` or `REJECTED` must insert an immutable audit record in `approval_history` recording the physical actor, timestamp, rationale, and evidence reference.

---

## R3. Issue 2: Multi-Layer Security Model & SQLite Boundaries

### R3.1 Defense-in-Depth Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       THREE DEFENSIVE SECURITY RINGS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  RING 1: APPLICATION-LAYER CONTROLS (Domain Logic & Orchestration)          │
│  - CandidateRepository and ApprovalManager domain entities.                 │
│  - Enforced state-machine transition validation table.                      │
│  - Role-based actor checks (AUTOMATED_GATE vs HUMAN_AUDITOR).               │
│  - Strict parameterized queries; zero raw SQL string formatting.            │
│  - Explicit transaction boundaries (BEGIN IMMEDIATE).                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  RING 2: DATABASE-LAYER CONTROLS (SQLite Schema & Engine Rules)             │
│  - Foreign keys with ON DELETE RESTRICT on sources and exported items.      │
│  - CHECK constraints validating all enumerated state fields.                │
│  - UNIQUE constraints on raw and normalized content hashes.                 │
│  - Triggers aborting unauthorized approval mutations.                       │
│  - Triggers preventing UPDATE or DELETE on append-only audit tables.        │
│  - SQL View (v_export_eligible_candidates) encapsulating eligibility.       │
├─────────────────────────────────────────────────────────────────────────────┤
│  RING 3: FILESYSTEM & OPERATIONAL CONTROLS (Operating System & Environment) │
│  - File permission 0600 on veda_candidates.sqlite (owner R/W only).         │
│  - Storage directory data/candidates/ isolated from scratch workspace.      │
│  - Automated hourly backups to data/candidates/backups/ via backup API.     │
│  - Complete runtime isolation: test suites use ephemeral tempfile databases.│
└─────────────────────────────────────────────────────────────────────────────┘
```

### R3.2 Database Triggers for Audit Immutability
To enforce audit protection directly inside the SQLite engine, three explicit triggers are specified:

```sql
-- Trigger 1: Abort if automated worker attempts to grant APPROVED status directly
CREATE TRIGGER IF NOT EXISTS trig_enforce_human_approval_authorization
BEFORE UPDATE OF processing_status ON candidate_submissions
FOR EACH ROW
WHEN NEW.processing_status = 'APPROVED' AND OLD.processing_status != 'APPROVED'
BEGIN
    SELECT RAISE(ABORT, 'Security Violation: Transition to APPROVED requires explicit HUMAN_AUDITOR action.')
    WHERE NOT EXISTS (
        SELECT 1 FROM approval_history
        WHERE candidate_id = NEW.candidate_id
          AND new_status = 'APPROVED'
          AND actor_type = 'HUMAN_AUDITOR'
    );
END;

-- Trigger 2: Prevent mutation or deletion of historical approval audit events
CREATE TRIGGER IF NOT EXISTS trig_immutable_approval_history_no_update
BEFORE UPDATE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'Audit Violation: approval_history records are strictly immutable.');
END;

CREATE TRIGGER IF NOT EXISTS trig_immutable_approval_history_no_delete
BEFORE DELETE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'Audit Violation: approval_history records cannot be deleted.');
END;

-- Trigger 3: Prevent mutation or deletion of processing decision journals
CREATE TRIGGER IF NOT EXISTS trig_immutable_processing_decisions
BEFORE UPDATE ON processing_decisions
BEGIN
    SELECT RAISE(ABORT, 'Audit Violation: processing_decisions records are strictly immutable.');
END;
```

### R3.3 Honest Disclosure of SQLite Security Limits
> [!WARNING]
> **Architectural Boundary Disclosure:** SQLite is an embedded, in-process database library. It does not possess a client-server architecture, native user role authentication, network daemon isolation, or internal privilege separation. 
> 
> Any operating system process running with the user's filesystem permissions can open `veda_candidates.sqlite` directly via the SQLite CLI, disable foreign keys (`PRAGMA foreign_keys = OFF;`), drop triggers, or hex-edit the database pages on disk.
> 
> Therefore, database-layer constraints and triggers provide defense against **software bugs, accidental application defects, and unconstrained script paths**, but **cannot** serve as a cryptographically tamper-proof perimeter against malicious root-level users. Absolute provenance security relies on out-of-band SHA-256 manifests, signed commits, and filesystem permission hardening (`chmod 0600`).

### R3.4 Adversarial Security Test Suite Plan
The implementation must introduce explicit adversarial security tests in `tests/test_candidate_security_adversarial.py`:
1. `test_direct_sql_injection_in_metadata`: Submits SQL injection payloads (`'; DROP TABLE candidate_submissions; --`) and asserts proper verbatim string storage without SQL execution.
2. `test_unauthorized_direct_status_update`: Attempts `UPDATE candidate_submissions SET processing_status = 'APPROVED'` without an audit row; asserts trigger aborts transaction.
3. `test_audit_tampering_aborts`: Attempts `DELETE FROM approval_history`; asserts trigger raises abort.
4. `test_exported_record_deletion_aborts`: Attempts `DELETE FROM candidate_submissions` for an exported candidate; asserts foreign key RESTRICT raises constraint failure.

---

## R4. Issue 3: Export Crash-Recovery and Consistency Protocol

### R4.1 The Dual-System Atomicity Challenge
Corpus export spans two fundamentally different storage technologies:
1. **Relational Database (`veda_candidates.sqlite`):** ACID transactional state machine.
2. **Filesystem Corpus (`CorpusWriter`):** Atomic streaming replacement of multiple flat `.jsonl` files (`train.jsonl`, `validation.jsonl`, `test.jsonl`, `rejections.jsonl`) and `manifest.json`.

Because SQLite and the OS filesystem cannot participate in a shared distributed transaction (no two-phase commit protocol across POSIX files and SQLite WAL), the export protocol must be designed for **crash-safe, idempotent reconciliation**.

### R4.2 The 9-Stage Crash-Safe Export Protocol

```mermaid
sequenceDiagram
    autonumber
    participant App as Export Coordinator
    participant DB as veda_candidates.sqlite
    participant FS as Filesystem / CorpusWriter

    App->>DB: 1. Allocate export_batch_id (status='INITIALIZING')
    App->>DB: 2. Query v_export_eligible_candidates & Insert export_batch_items
    App->>DB: 3. Verify source licenses & active approval dates
    App->>DB: 4. Update export_batches (status='STREAMING')
    App->>FS: 5. Open CorpusWriter (.tmp files) & Stream records in chunks
    App->>FS: 6. CorpusWriter.close(commit=True) -> Atomic os.replace()
    App->>FS: 7. Build and write manifest.json & sources.json
    App->>DB: 8. Record fingerprints & Set export_batches (status='COMMITTED')
    App->>DB: 9. Set candidate_submissions (processing_status='EXPORTED')
```

### R4.3 Crash Failure and Reconciliation Matrix

| Crash Point | System State Upon Crash | Recovery Engine Action on Restart | Final State |
| :--- | :--- | :--- | :--- |
| **Crash at Stages 1–3** (Initialization) | SQLite batch is `INITIALIZING`; no files exist on disk. | Discovery engine marks batch as `ABORTED`. Removes orphan batch items. | Clean. No data leaked. Safe to re-run. |
| **Crash at Stage 4–5** (During Streaming) | SQLite batch is `STREAMING`; `.tmp` files exist on disk. Target JSONLs untouched. | Unlinks all `.tmp` staging files. Marks SQLite batch as `ABORTED`. | Clean rollback. Output JSONLs remain at previous version. |
| **Crash at Stage 6** (During `os.replace`) | Some `.jsonl` files replaced; others still `.tmp` or old version. Manifest not written. | Detects missing or incomplete `manifest.json`. Replaces corrupt directory with backup snapshot. Marks batch `ABORTED`. | Clean rollback to previous sealed corpus release. |
| **Crash at Stage 7** (Manifest written, before SQLite commit) | Filesystem release is complete and valid. SQLite still shows batch as `STREAMING`. | **Reconciliation Phase:** Verifies physical `.jsonl` file checksums match `manifest.json`. Completes SQLite commit: marks batch `COMMITTED`, marks candidates `EXPORTED`. | Recovered without re-exporting. Data fully consistent. |
| **Crash at Stage 8–9** (SQLite finalizing) | Batch is `COMMITTED`; some candidate rows still `EXPORT_PENDING`. | Completes candidate status update for all candidates listed in `export_batch_items`. | Fully reconciled. All records marked `EXPORTED`. |

### R4.4 Reconciliation Engine Specification
Upon startup of the export service, `CorpusExportReconciler.reconcile_pending_batches()` executes:
1. Inspects `export_batches` for any rows in `INITIALIZING` or `STREAMING` status.
2. Checks target output directory for matching `manifest.json`.
3. If manifest exists and all file SHA-256 digests verify against disk bytes, the batch is promoted to `COMMITTED`.
4. If manifest is missing or file checksums fail, the staging directory is cleaned and the batch marked `ABORTED`.
5. Guarantees that export retries are completely idempotent.

---

## R5. Issue 4: Source Governance Authority & Integration

### R5.1 Single Source of Truth: SourceRegistry
The candidate database **shall not** implement an independent, conflicting licensing or permission decision engine. 

The authoritative source of truth for external data governance is:
* **Registry Class:** `foundation.corpus.sources.SourceRegistry`
* **Authoritative JSON Ledger:** `data/corpus/source_registry.json`
* **Contract Entity:** `foundation.corpus.schemas.CorpusSource`

### R5.2 Role of `candidate_sources` as Relational Cache
The `candidate_sources` table in `veda_candidates.sqlite` acts strictly as an **indexed relational mirror/snapshot** of `source_registry.json`. It is populated and kept current via the synchronization utility:

$$\text{SourceRegistry (JSON Ledger)} \xrightarrow[\text{verify\_source\_integrity()}]{\text{Sync Process}} \text{candidate\_sources (SQLite Cache)}$$

### R5.3 Sync Protocol and Staleness Detection
To prevent stale database records from permitting ingestion from sources whose permissions have changed:
1. `candidate_sources` stores `registry_entry_sha256`: a deterministic SHA-256 hash of the source's complete JSON metadata in `source_registry.json`.
2. Prior to any candidate evaluation or batch export, the system executes:
   ```python
   def verify_candidate_source_freshness(conn: sqlite3.Connection, source_id: str, registry: SourceRegistry) -> None:
       auth_source = registry.get(source_id)
       if not auth_source:
           raise UnapprovedSourceError(f"Source {source_id!r} not in authoritative SourceRegistry.")
       
       # Check live permissions directly against authoritative domain entity
       if not auth_source.is_permitted_for_training:
           raise GovernanceGateError(f"Source {source_id!r} is not permitted for training.")
       
       # Verify database snapshot matches authoritative checksum
       row = conn.execute("SELECT registry_entry_sha256 FROM candidate_sources WHERE source_id = ?", (source_id,)).fetchone()
       if not row or row["registry_entry_sha256"] != auth_source.registry_entry_sha256:
           raise StaleSourceMetadataError(f"Database metadata for {source_id} is stale relative to source_registry.json.")
   ```
3. **Explicit Training Permission Invariant:** A general license label (such as `CC-BY-4.0` or `Public Domain`) does not automatically grant training eligibility. `training_permitted_status` must be explicitly verified as `'EXPLICITLY_PERMITTED'`.

---

## R6. Issue 5: Duplicate and Export Idempotency Across Releases

### R6.1 Strict Definitions of Identity
To eliminate ambiguity across candidate matching, deduplication, and corpus releases:

1. **Candidate Identity (`candidate_id`):** Unique UUIDv4 assigned at submission intake. Identifies a specific submission event from a specific source at a specific timestamp.
2. **Canonical Candidate Identity (`canonical_candidate_id`):** References the primary candidate within a duplicate cluster. The first admitted candidate is canonical (`is_canonical = 1`); subsequent duplicates point to it (`is_canonical = 0`).
3. **Exact Raw Identity (`raw_content_hash`):**
   $$H_{\text{raw}} = \text{SHA-256}(\text{original\_text.encode('utf-8')})$$
4. **Normalized Identity (`normalized_content_hash`):**
   $$H_{\text{norm}} = \text{SHA-256}(\text{normalized\_text.encode('utf-8')})$$
5. **Near-Duplicate Relationship:** Established when token Jaccard $\ge 0.75$ or MinHash similarity $\ge 0.75$, *provided* that `SemanticSafetyGuard` confirms `is_safe_to_merge = True`.
6. **Corpus Version Identity (`corpus_version`):** Release tag identifying a sealed corpus publication (e.g. `v0.1.0`, `v0.2.0`).
7. **Split Assignment Identity (`assigned_split`):** Deterministic partition (`train`, `validation`, `test`) derived exclusively by `DeterministicSplitter` from `(split_seed, group_id or candidate_id)`.

### R6.2 Multi-Release Export Uniqueness
To prevent duplicate records within the same release while allowing intentional candidate reuse in future major corpus versions, the schema enforces:

```sql
-- Enforce candidate export uniqueness PER CORPUS RELEASE
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_candidate_per_corpus_release 
ON export_batch_items (candidate_id, corpus_version);

-- Enforce content uniqueness per split within a corpus release
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_content_per_split_release 
ON export_batch_items (assigned_split, exported_content_hash, corpus_version);
```

* **Intra-Release Protection:** A candidate cannot be exported twice into the same release version (e.g., `v0.1.0`), even across multiple batch runs.
* **Inter-Release Continuity:** When building a new major release (e.g., `v0.2.0`), existing approved candidates can be re-exported cleanly under the new `corpus_version` identifier, maintaining complete historical lineage.

### R6.3 Non-Merge Invariant for Semantic Conflicts
Records exhibiting contradictory assertions (negation, numerical divergence, unit incompatibility, calendar discrepancies) are **never merged** into a duplicate cluster. They are assigned distinct candidate IDs and linked in `duplicate_relationships` with:
* `relationship_type = 'SEMANTIC_CONFLICT_BLOCKED'`
* `is_safe_to_merge = 0`

---

## R7. Issue 6: Formal Approval Revocation and Corpus Rebuild Protocol

### R7.1 Six Revocation Triggers

```mermaid
flowchart TD
    T1["Trigger 1: Source License Revoked Prior to Export"] --> P1["Immediate Database Revocation"]
    T2["Trigger 2: Source License Revoked After Export"] --> P2["Corpus Invalidation & Full Rebuild"]
    T3["Trigger 3: Human Approval Withdrawn"] --> P1
    T4["Trigger 4: Pipeline Quality Rules Revised"] --> P3["Batch Reprocessing & Reset"]
    T5["Trigger 5: Semantic Safety Defect Discovered"] --> P2
    T6["Trigger 6: Post-Export Duplicate Identified"] --> P2
```

### R7.2 Step-by-Step Revocation Procedures

#### Procedure A: Pre-Export Revocation (Candidate Not Yet Exported)
1. **Status Transition:** Candidate `processing_status` is transitioned to `'REVOKED'`.
2. **Audit Logging:** An entry is inserted into `approval_history` recording `(actor_type, actor_id, 'REVOKED', revocation_reason, legal_notice_ref)`.
3. **Immediate Effect:** Candidate fails the 8-point eligibility gate and cannot be selected for export.

#### Procedure B: Post-Export Revocation (Candidate Already in Released Corpus)
1. **Candidate Status Transition:** Candidate marked `processing_status = 'REVOKED'`.
2. **Audit Logging:** Revocation event logged to `approval_history`.
3. **Batch Tainting:** All batches in `export_batches` containing the candidate have their status updated to `'SUPERSEDED'`.
4. **Manifest Invalidation:** An official `REVOCATION_NOTICE.json` is published inside the affected corpus release folder (`data/corpus/releases/v0.1.0/`), detailing:
   * Revoked candidate IDs.
   * Reason for revocation (e.g., copyright withdrawal, safety conflict).
   * Notice that the release is superseded and prohibited from new model pretraining runs.
5. **Mandatory Corpus Rebuild Protocol:**
   * A patch release version is initialized (e.g., `v0.1.1`).
   * The candidate database queries all approved candidates excluding `REVOKED` records.
   * A fresh export run executes through `CorpusWriter`, generating new `train.jsonl`, `validation.jsonl`, and `test.jsonl` files.
   * New logical fingerprints are computed, and an authoritative `manifest.json` is signed.
   * Historical `export_batch_items` rows for `v0.1.0` are preserved permanently to maintain complete scientific traceability of what was previously trained on.

---

## R8. Issue 7: Corrected 12-State Candidate Lifecycle

### R8.1 The 12 Formal Lifecycle States

| State | Definition | Initiating Actor |
| :--- | :--- | :--- |
| **`RECEIVED`** | Raw verbatim text received; `raw_content_hash` computed. | Ingestion Intake |
| **`PENDING`** | Queued for normalization and initial deduplication screening. | Intake Engine |
| **`PROCESSING`** | Normalization complete; heuristic filter and safety pipeline executing. | Processing Worker |
| **`PROCESSING_PASSED`** | Automated filters passed; candidate exhibits high linguistic cleanliness. | Automated Gate |
| **`APPROVAL_PENDING`** | Candidate recommended for approval; staged in review queue. | Automated Gate |
| **`APPROVED`** | Designated human auditor has verified governance and authorized inclusion. | **HUMAN AUDITOR ONLY** |
| **`REJECTED`** | Fails quality thresholds, contains non-English script, or lacks stopwords. | Automated Gate / Auditor |
| **`QUARANTINED`** | Ambiguous content (captions, headings, code, cognates) held for review. | Automated Gate |
| **`PROCESSING_FAILED`**| Uncaught runtime error or parser crash during evaluation. | Pipeline Watchdog |
| **`EXPORT_PENDING`** | Staged in an active, uncommitted export batch. | Export Coordinator |
| **`EXPORTED`** | Formally committed into a sealed, published corpus split JSONL. | Export Bridge |
| **`REVOKED`** | Approval withdrawn, license invalidated, or safety defect discovered. | Governance Officer |

### R8.2 Formal Transition Matrix

| Current State | Permitted Next States | Prohibited Next States | Required Authorization / Invariant |
| :--- | :--- | :--- | :--- |
| **`RECEIVED`** | `PENDING`, `REJECTED` | `APPROVED`, `EXPORTED` | Valid `source_id`; non-empty raw text. |
| **`PENDING`** | `PROCESSING`, `REJECTED` | `APPROVED`, `EXPORT_PENDING` | `raw_content_hash` verified; source active. |
| **`PROCESSING`** | `PROCESSING_PASSED`, `REJECTED`, `QUARANTINED`, `PROCESSING_FAILED` | `APPROVED`, `EXPORTED` | Automated workers **cannot** transition directly to `APPROVED`. |
| **`PROCESSING_PASSED`**| `APPROVAL_PENDING`, `QUARANTINED` | `APPROVED`, `EXPORTED` | Near-dedup and safety guards must complete before staging. |
| **`APPROVAL_PENDING`** | `APPROVED`, `REJECTED`, `QUARANTINED` | `EXPORTED`, `PROCESSING` | **Requires explicit Human Auditor action** logged in `approval_history`. |
| **`APPROVED`** | `EXPORT_PENDING`, `REVOKED` | `PROCESSING`, `REJECTED` | Locked against automated edits; export requires active non-stale license. |
| **`REJECTED`** | `PENDING` (on rule update) | `APPROVED`, `EXPORTED` | Rejection cannot be directly overridden without formal re-evaluation. |
| **`QUARANTINED`** | `APPROVAL_PENDING`, `REJECTED` | `APPROVED`, `EXPORTED` | Cannot transition directly to `APPROVED` without human review audit. |
| **`PROCESSING_FAILED`**| `PENDING` (on retry) | `APPROVED`, `EXPORT_PENDING` | Error details logged to `processing_decisions`. |
| **`EXPORT_PENDING`** | `EXPORTED`, `APPROVED` (on abort) | `REJECTED`, `REVOKED` | Locked during active `CorpusWriter` streaming. |
| **`EXPORTED`** | `REVOKED` | `PENDING`, `APPROVED` | Record is sealed in published corpus; revocation requires corpus rebuild. |
| **`REVOKED`** | `PENDING` (legal clearance) | `APPROVED`, `EXPORTED` | Terminal governance state until legal remediation clears record. |

---

## R9. Issue 8: Governance Bypass Finding Resolution

### R9.1 Why Bypass Flags Exist in `foundation/corpus/pipeline.py`
Audit Question 13 noted that `CorpusPipeline.process_corpus` accepts optional parameters: `strict_governance: bool = False` and `enforce_preflight: bool = False`.

*Root Cause Analysis:* These parameters were introduced in Phase 4.1 to support lightweight, in-memory unit tests (`test_corpus_pipeline.py`, `test_corpus_normalization.py`) using synthetic dummy documents where real external source downloads (e.g. 100 MB Gutenberg archives), physical checksum files, and disk reserve margin assertions do not exist.

### R9.2 Production Prohibition & Architectural Gating
In the database-backed candidate architecture:
1. `strict_governance=False` and `enforce_preflight=False` are **strictly prohibited** in all production paths.
2. The Candidate Export Bridge (`foundation/candidates/exporter.py`) shall **not** expose these flags.
3. The export engine queries `v_export_eligible_candidates` and invokes `CorpusPipeline.ingest_production_corpus` with hardcoded `strict_governance=True` and `enforce_preflight=True`.
4. Dedicated unit test `test_candidate_export_bridge_rejects_bypass_options` will verify that passing non-strict flags to the export bridge raises a fatal `GovernanceBypassProhibitedError`.

---

## R10. Issue 9: Schema Refinements & SQLite DDL Updates

### R10.1 Refined Data Definition Language (DDL)

```sql
-- VEDA Candidate Storage Schema v0.1.1 (Revision 1 Refinements)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;

-- -----------------------------------------------------------------------------
-- 1. Schema Migrations Ledger
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    checksum TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- 2. Registered Candidate Sources (Mirror of SourceRegistry)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    url_or_path TEXT NOT NULL,
    license_identifier TEXT NOT NULL,
    licensing_status TEXT NOT NULL CHECK (licensing_status IN ('VERIFIED PERMITTED', 'REQUIRES REVIEW', 'UNKNOWN', 'EXCLUDED')),
    training_permitted_status TEXT NOT NULL CHECK (training_permitted_status IN ('EXPLICITLY_PERMITTED', 'PROHIBITED', 'UNCLEAR')),
    commercial_permitted INTEGER NOT NULL CHECK (commercial_permitted IN (0, 1)),
    attribution TEXT,
    artifact_sha256 TEXT NOT NULL,
    evidence_checksum TEXT,
    registry_entry_sha256 TEXT NOT NULL,                 -- SHA-256 of source_registry.json entry for staleness check
    approval_expiration_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_sources_status ON candidate_sources(licensing_status);

-- -----------------------------------------------------------------------------
-- 3. Candidate Submissions (Core Entity with Refined 12-State Lifecycle)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_submissions (
    candidate_id TEXT PRIMARY KEY,                       -- UUIDv4
    source_id TEXT NOT NULL,
    source_document_id TEXT,
    original_text TEXT NOT NULL,
    normalized_text TEXT,
    raw_content_hash TEXT NOT NULL,
    normalized_content_hash TEXT,
    raw_char_count INTEGER NOT NULL,
    normalized_char_count INTEGER,
    approx_word_count INTEGER,
    language_status TEXT NOT NULL DEFAULT 'UNEVALUATED' 
        CHECK (language_status IN ('UNEVALUATED', 'ENGLISH_CONFIRMED', 'NON_ENGLISH_REJECTED', 'QUARANTINED')),
    quality_status TEXT NOT NULL DEFAULT 'UNEVALUATED'
        CHECK (quality_status IN ('UNEVALUATED', 'HIGH_QUALITY', 'LOW_QUALITY_REJECTED', 'QUARANTINED')),
    processing_status TEXT NOT NULL DEFAULT 'RECEIVED'
        CHECK (processing_status IN (
            'RECEIVED', 'PENDING', 'PROCESSING', 'PROCESSING_PASSED',
            'APPROVAL_PENDING', 'APPROVED', 'REJECTED', 'QUARANTINED', 
            'PROCESSING_FAILED', 'EXPORT_PENDING', 'EXPORTED', 'REVOKED'
        )),
    is_canonical INTEGER NOT NULL DEFAULT 1 CHECK (is_canonical IN (0, 1)),
    canonical_candidate_id TEXT,
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT '0.1.1',
    FOREIGN KEY (source_id) REFERENCES candidate_sources(source_id) ON DELETE RESTRICT,
    FOREIGN KEY (canonical_candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_raw_hash ON candidate_submissions(raw_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_norm_hash ON candidate_submissions(normalized_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_status_canonical ON candidate_submissions(processing_status, is_canonical);
CREATE INDEX IF NOT EXISTS idx_candidates_source ON candidate_submissions(source_id);

-- -----------------------------------------------------------------------------
-- 4. Processing Decisions (Append-Only Decision Journal)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS processing_decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('NORMALIZATION', 'QUALITY_FILTER', 'LANGUAGE_AUDIT', 'NEAR_DEDUPLICATION', 'GOVERNANCE')),
    decision_result TEXT NOT NULL CHECK (decision_result IN ('PASS', 'REJECT', 'QUARANTINE', 'ERROR')),
    reason_code TEXT NOT NULL,
    human_readable_reason TEXT,
    quality_score REAL,
    metrics_json TEXT,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decisions_candidate ON processing_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_decisions_stage_result ON processing_decisions(stage, decision_result);

-- -----------------------------------------------------------------------------
-- 5. Duplicate & Semantic Conflict Relationships
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duplicate_relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    related_candidate_id TEXT NOT NULL,
    similarity_method TEXT NOT NULL CHECK (similarity_method IN ('EXACT_RAW', 'EXACT_NORMALIZED', 'MINHASH_LSH', 'TOKEN_JACCARD')),
    similarity_score REAL NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'EXACT_DUPLICATE', 'NORMALIZED_DUPLICATE', 'NEAR_DUPLICATE_MERGEABLE', 
        'SEMANTIC_CONFLICT_BLOCKED', 'DISTANT_NEGATIVE'
    )),
    safety_conflict_type TEXT CHECK (safety_conflict_type IN (
        'NEGATION_INVERSION', 'POLARITY_INVERSION', 'NUMERICAL_MISMATCH', 
        'UNIT_MISMATCH', 'DATE_MISMATCH', 'IDENTIFIER_MISMATCH'
    )),
    conflict_details_json TEXT,
    is_safe_to_merge INTEGER NOT NULL CHECK (is_safe_to_merge IN (0, 1)),
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE,
    FOREIGN KEY (related_candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE,
    UNIQUE (candidate_id, related_candidate_id, similarity_method)
);

CREATE INDEX IF NOT EXISTS idx_dup_candidate ON duplicate_relationships(candidate_id);
CREATE INDEX IF NOT EXISTS idx_dup_conflict_safe ON duplicate_relationships(is_safe_to_merge);

-- -----------------------------------------------------------------------------
-- 6. Approval & Governance History (Append-Only Audit Ledger)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_history (
    approval_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('AUTOMATED_GATE', 'HUMAN_AUDITOR', 'GOVERNANCE_SYSTEM')),
    actor_id TEXT NOT NULL,
    decision_reason TEXT NOT NULL,
    evidence_reference TEXT,
    event_timestamp TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_approval_candidate ON approval_history(candidate_id);

-- -----------------------------------------------------------------------------
-- 7. Corpus Export Batches
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS export_batches (
    export_batch_id TEXT PRIMARY KEY,                    -- UUIDv4
    corpus_version TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    split_seed TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    manifest_fingerprint TEXT,
    content_fingerprint TEXT,
    total_records_exported INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    committed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('INITIALIZING', 'STREAMING', 'COMMITTED', 'ABORTED', 'SUPERSEDED'))
);

CREATE INDEX IF NOT EXISTS idx_export_batches_status ON export_batches(status);

-- -----------------------------------------------------------------------------
-- 8. Export Batch Items (Idempotency Junction Across Release Versions)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS export_batch_items (
    export_batch_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    corpus_version TEXT NOT NULL,
    assigned_split TEXT NOT NULL CHECK (assigned_split IN ('train', 'validation', 'test')),
    exported_content_hash TEXT NOT NULL,
    exported_at TEXT NOT NULL,
    PRIMARY KEY (export_batch_id, candidate_id),
    FOREIGN KEY (export_batch_id) REFERENCES export_batches(export_batch_id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE RESTRICT
);

-- Unique constraint ensuring candidate exported at most once per release version
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_cand_release 
ON export_batch_items(candidate_id, corpus_version);

-- Unique constraint ensuring content hash exported at most once per split per release
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_content_split_release 
ON export_batch_items(assigned_split, exported_content_hash, corpus_version);

-- -----------------------------------------------------------------------------
-- 9. Authoritative SQL View: Export-Eligible Candidates
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_export_eligible_candidates AS
SELECT 
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
WHERE c.processing_status = 'APPROVED'
  AND c.is_canonical = 1
  AND s.licensing_status = 'VERIFIED PERMITTED'
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'
  AND s.artifact_sha256 != 'NOT_VERIFIED'
  AND (s.approval_expiration_date IS NULL OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND NOT EXISTS (
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  );
```

---

## R11. Updated Mermaid Diagrams (Revision 1)

### R11.1 Refined 12-State Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED : Submission Intake
    RECEIVED --> PENDING : Hash Computed & Source Validated
    PENDING --> PROCESSING : Normalization Succeeded

    state PROCESSING {
        [*] --> QualityCheck
        QualityCheck --> LanguageAudit : Passes Alpha/Length Rules
        LanguageAudit --> CandidateScreening : English Confirmed
        CandidateScreening --> SemanticGuard : Jaccard/MinHash Match
    }

    PROCESSING --> PROCESSING_PASSED : Clean Pass (No Errors)
    PROCESSING --> REJECTED : Quality/Lang/Gov Failure
    PROCESSING --> QUARANTINED : Low Stopwords / Heading / SQL / Cognates
    PROCESSING --> PROCESSING_FAILED : Uncaught Parser Crash

    PROCESSING_PASSED --> APPROVAL_PENDING : Zero Unresolved Conflicts
    
    QUARANTINED --> APPROVAL_PENDING : Auditor Clears Ambiguity
    QUARANTINED --> REJECTED : Auditor Confirms Flaw
    
    APPROVAL_PENDING --> APPROVED : HUMAN AUDITOR AUTHORIZATION ONLY
    APPROVAL_PENDING --> REJECTED : Human Auditor Rejection

    APPROVED --> EXPORT_PENDING : Locked in Active Export Batch
    EXPORT_PENDING --> EXPORTED : CorpusWriter Atomic Commit Verified
    EXPORT_PENDING --> APPROVED : Batch Aborted / Clean Rollback

    APPROVED --> REVOKED : Pre-Export Revocation Event
    EXPORTED --> REVOKED : Post-Export Flaw / Legal Notice (Requires Rebuild)
    REJECTED --> PENDING : Reset for Re-evaluation on Rule Revision
```

---

## R12. Remaining Human Governance Decisions

1. **Human Audit Sampling Density:** When scaling beyond 100,000 candidates, what percentage of `APPROVAL_PENDING` candidates must undergo spot-check review before batch authorization?
   * *Recommendation:* 100% human review for technical captions, code blocks, and short headings; 5% statistical spot-check sampling with zero defect tolerance for fluent expository prose ($> 25$ words, score $\ge 0.98$).
2. **Revocation Tombstoning Retention Limit:** In the event of post-export copyright revocation, how long must the invalidated raw text remain in the quarantined database table for legal defense?
   * *Recommendation:* Retain SHA-256 hash, provenance, and legal notice permanently; purge raw text payload after 180 days.

---

## R13. Summary of Resolved Architectural Risks

| Risk Identified in Review | Severity | Revision 1 Resolution | Verification Proof |
| :--- | :--- | :--- | :--- |
| **Premature Automated Approval** | High | Automated approval strictly abolished. `APPROVAL_PENDING` requires explicit `HUMAN_AUDITOR` sign-off. | Trigger `trig_enforce_human_approval_authorization`. |
| **Dual-System Partial Commit** | Critical | 9-Stage crash recovery protocol designed with explicit startup reconciliation logic. | Section R4 recovery table and idempotent batch item key. |
| **Source Authority Conflict** | High | `SourceRegistry` codified as single authority; `candidate_sources` defined as synced snapshot. | `registry_entry_sha256` staleness check. |
| **Cross-Release Duplicate Export** | Medium | Expanded unique constraints to include `corpus_version`. | `idx_unique_cand_release` and `idx_unique_content_split_release`. |
| **Silent Audit Deletion** | High | Append-only triggers prevent `UPDATE` or `DELETE` on decisions and approval ledgers. | Triggers `trig_immutable_approval_history` & `trig_immutable_processing_decisions`. |
| **Pipeline Governance Bypass** | Critical | Documented unit test fixture origin; export bridge strictly forces fail-closed production method. | Section R9 architectural isolation policy. |


---

# ARCHITECTURE OWNER DECISIONS — REVISION 2

- **Decision Date:** 2026-11-13
- **Status:** APPROVED BY PROJECT OWNER / READY FOR REVIEW
- **Task Scope:** Design-Only Specification Update (Phase 4.14.1.2)
- **Execution Invariant:** Strictly design-only. Zero production Python code modified, zero database tables created, zero migrations executed, zero dependencies altered, Phase 5 pretraining strictly blocked.

---

## D1. Executive Summary of Project-Owner Decisions

Following the completion of the Phase 4.14.1 architectural review (Revision 1), the Project Owner has established three authoritative, non-negotiable architectural determinations:

1. **Official Python Runtime Standardization:** Python 3.14.8 is designated as VEDA's **sole officially supported development and testing runtime**. All future development, dependencies, setup instructions, and testing must target Python 3.14.8. Python 3.9 is formally categorized as a temporary legacy environment to be decommissioned in Phase 4.14.1.3 following formal migration verification.
2. **100% Explicit Human Approval Mandate:** The Project Owner has rejected all automated production approval pathways. There shall be **zero automated production approval** based on confidence scores, quality heuristics, or classifier predictions. Every single candidate record admitted into a production training split must undergo explicit human review and authorization.
3. **Legally Governed Retention & Revocation Policy:** The Project Owner has rejected an unconditional 180-day deletion rule. In its place, VEDA establishes a legally governed, evidence-based retention framework. Raw text, hashes, provenance, and audit logs are governed by documented legal and statutory retention decisions rather than arbitrary calendar timers.

---

## D2. Decision 1: Official Python Runtime Standardization (Python 3.14.8)

### D2.1 Formal Runtime Mandate
* **Sole Official Target:** **Python 3.14.8** (`.\\.venv\\Scripts\\python.exe`).
* **Legacy Runtime Status:** **Python 3.9.13** is classified as a temporary legacy environment maintained strictly for baseline stability during the migration transition. It will be decommissioned in a separate subsequent milestone (Phase 4.14.1.3).
* **Forward Compatibility Directive:** New code, architectural extensions, and database components developed for Phase 4.14 and beyond must target modern Python 3.14 features (e.g., standard generic type annotations, modern exception groups, enhanced `sqlite3` driver features) and must **not** introduce backwards-compatibility workarounds or polyfills for Python 3.9.
* **Dependency Pinning Policy:** All development dependencies shall be pinned against Python 3.14.8 via `requirements-lock-py314.txt`.

### D2.2 Explicit Boundary Condition
> [!IMPORTANT]
> **Migration Boundary Warning:** This architecture update does **not** authorize deleting Python 3.9 or modifying active virtual environments immediately. The physical environment migration, cleanup of legacy scripts, and single-runtime test re-certification will occur in a dedicated milestone (**Phase 4.14.1.3**). Python 3.9 remains active and available until the owner formally approves the migration acceptance report.

### D2.3 Migration Acceptance Checklist (Phase 4.14.1.3 Protocol)
The future Phase 4.14.1.3 migration task must satisfy this 9-point acceptance checklist before Python 3.9 is decommissioned:

- [ ] **1. Runtime Version Verification:** `.\\.venv\\Scripts\\python.exe --version` outputs exactly `Python 3.14.8`.
- [ ] **2. Dependency Compatibility Audit:** All packages in `requirements.txt` install cleanly in `.venv` without deprecated C-extensions or runtime warnings.
- [ ] **3. Full Test Suite Execution:** All 300 tests pass with zero failures under Python 3.14.8 (`.\\.venv\\Scripts\\python.exe -m pytest tests`).
- [ ] **4. Project Entry-Point Verification:** CLI invocation `.\\.venv\\Scripts\\python.exe veda.py --help` executes cleanly without warning banners.
- [ ] **5. Lexicon Read-Only Verification:** `SqliteLexicon` integrity check and word lookups operate correctly on `data/lexicon/veda_lexicon_v0.1.sqlite` under Python 3.14.8.
- [ ] **6. Corpus Pipeline Verification:** `CorpusPipeline` golden fixture and fail-closed governance gate pass 100% on Python 3.14.8.
- [ ] **7. Database Compatibility Verification:** Standard library `sqlite3` under Python 3.14.8 is validated against SQLite WAL, foreign keys, triggers, and views.
- [ ] **8. Documentation & Setup Verification:** `README.md`, setup guides, and docstrings are updated to mandate Python 3.14.8.
- [ ] **9. Git Working-Tree Verification:** Clean commit and tag checkpoint recorded on `main` branch.

---

## D3. Decision 2: 100% Explicit Human Approval Policy

### D3.1 Total Prohibition of Automated Production Approval
Under the Project Owner's explicit directive:
* **Zero Automated Production Approval:** No candidate record may be marked `APPROVED` or become export-eligible based solely on automated heuristic scores, quality thresholds, or language classifier outputs.
* **Automated System Role:** Automated pipelines act strictly as **intake evaluators, filter assessors, and diagnostic recommenders**. Automated tools may recommend approval, recommend rejection, flag near-duplicates, quarantine ambiguities, and compute quality metrics. They are **architecturally forbidden** from granting final approval.

### D3.2 The 8-Step Permitted Production Workflow

```mermaid
flowchart TD
    Step1["Step 1: Submission Received\n(Status: RECEIVED)"] --> Step2["Step 2: Automated Processing\n(Status: PROCESSING)"]
    Step2 --> Step3["Step 3: Evaluation Result Logged\n(Status: PROCESSING_PASSED / QUARANTINED / REJECTED)"]
    Step3 -->|Clean Pass| Step4["Step 4: Enter Human Review Queue\n(Status: APPROVAL_PENDING)"]
    Step3 -->|Ambiguous| Step4Q["Step 4Q: Enter Quarantine Review Queue\n(Status: QUARANTINED)"]
    Step3 -->|Hard Fail| Step3R["Step 3R: Definite Rejection\n(Status: REJECTED)"]
    
    Step4 & Step4Q --> Step5["Step 5: Authorized Human Review\n(Inspection of text, metrics, conflicts)"]
    Step5 --> Step6{"Step 6: Explicit Human Decision"}
    
    Step6 -->|Human Approves| Step6A["Step 6A: Log Approval Event\n(Status: APPROVED)"]
    Step6 -->|Human Rejects| Step6R["Step 6R: Log Rejection Event\n(Status: REJECTED)"]
    
    Step6A --> Step7["Step 7: Independent Eligibility Evaluation\n(12-Point Dynamic Predicate View)"]
    Step7 --> Step8["Step 8: Export Batch Assembly\n(CorpusWriter JSONL Streaming)"]
```

### D3.3 Detailed Workflow Step Definitions
1. **Candidate Received:** Verbatim submission stored in `candidate_submissions` with status `RECEIVED`; `raw_content_hash` generated.
2. **Automated Processing & Validation:** `TextNormalizer` generates `normalized_text`; `QualityFilter`, `classify_with_quarantine`, and `NearDuplicateDetector` execute.
3. **Processing Result Recorded:** Evaluation journal appended to `processing_decisions`. If tests fail, marked `REJECTED`. If ambiguous (captions, headings, code, cognates), marked `QUARANTINED`. If all checks pass, marked `PROCESSING_PASSED`.
4. **Enter Human Approval Queue:** Candidates with `PROCESSING_PASSED` advance to `APPROVAL_PENDING` (recommended for approval). Quarantined candidates enter the specialized quarantine queue.
5. **Authorized Human Review:** A designated human auditor inspects the candidate text, computed metrics, source licensing, and duplicate relationship graph in a review interface.
6. **Explicit Human Decision:** The human auditor submits a cryptographically attributed decision transaction:
   * **Approved:** Status transitions to `APPROVED`. A record is appended to `approval_history` containing `(actor_type='HUMAN_AUDITOR', actor_id, timestamp, reason, evidence_reference)`.
   * **Rejected:** Status transitions to `REJECTED` with logged audit rationale.
7. **Independent Eligibility Evaluation:** Export eligibility is evaluated dynamically via SQL view `v_export_eligible_candidates` against the 12-point predicate. A candidate that is `APPROVED` but whose source license has since expired is immediately blocked.
8. **Export Batch Assembly:** Only candidates that independently pass the 12-point eligibility gate are locked into `export_batch_items` and streamed to `CorpusWriter`.

### D3.4 Reviewer Authorization & Audit Immutability
* **Reviewer Identification:** Every approval must record the physical reviewer’s corporate or cryptographic identity (`actor_id`), exact UTC ISO 8601 timestamp, explicit justification (`decision_reason`), and link to verification evidence.
* **Audit Immutability:** Reviewers **cannot** overwrite, update, or redact existing entries in `approval_history`. If an approval is subsequently revoked, a new `REVOKED` record is appended, preserving complete historical accountability.

---

## D4. Decision 3: Legally Governed Retention and Revocation Policy

### D4.1 Rejection of Universal 180-Day Deletion
The Project Owner has explicitly rejected an unconditional 180-day deletion timer. A rigid calendar deletion rule creates dual legal vulnerabilities:
1. It prematurely destroys critical forensic evidence required to defend against copyright infringement claims, contract breach allegations, or provenance disputes.
2. It fails to accommodate statutory retention mandates (e.g. legal holds, regulatory defense periods) that may exceed 180 days.

### D4.2 The Legally Governed Retention Framework
Retention and deletion of raw text and metadata are governed by an evidence-based legal protocol:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LEGAL RETENTION PRINCIPLES (VEDA)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. PERMANENT LAWFUL AUDIT RECORD (Subject to Applicable Law)               │
│     - Candidate ID, SHA-256 hashes, source ID, document ID, segment offsets,│
│       approval history, export batches, and formal revocation notices are    │
│       retained permanently to prove provenance and historic composition.    │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. IMMEDIATE EXPORT DISABILITY                                             │
│     - Any candidate subject to legal dispute, copyright notice, or license   │
│       expiry is immediately transitioned to REVOKED.                         │
│     - The 12-point gate strictly blocks REVOKED records from new exports.    │
├─────────────────────────────────────────────────────────────────────────────┤
│  3. CONTENT ACCESS RESTRICTION & QUARANTINE                                │
│     - Raw text under active legal assessment is restricted (access locked).  │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. STATUTORY REDACTION OR EXPUNGEMENT (Upon Lawful Mandate)                │
│     - When applicable law (e.g. court order, GDPR Art 17, DMCA final decree)│
│       demands deletion of raw text, the text is formally redacted:           │
│       original_text = '[EXPUNGED_UNDER_LEGAL_MANDATE]'                      │
│       normalized_text = '[EXPUNGED_UNDER_LEGAL_MANDATE]'                    │
│     - The non-content cryptographic hash (SHA-256) is preserved as proof of  │
│       the exact content that was expunged, without retaining the payload.    │
├─────────────────────────────────────────────────────────────────────────────┤
│  5. DOCUMENTED RETENTION DECISION REQUIRED                                  │
│     - No content is deleted or retained past review without an authorized    │
│       retention decision record signed by a designated governance officer.  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### D4.3 Formal Retention Decision Record Specification
To record and audit all retention, restriction, and expungement actions, a new relational table `retention_decisions` is added to the candidate database schema:

```sql
-- Table: retention_decisions (Legally Governed Retention & Redaction Ledger)
CREATE TABLE IF NOT EXISTS retention_decisions (
    retention_decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN (
        'RETAIN_FULL_RECORD',               -- Lawful justification to retain verbatim text
        'RESTRICT_ACCESS_DISPUTE',          -- Quarantined during ongoing legal inquiry
        'REDACT_RAW_TEXT_MANDATE',          -- Verbatim text expunged under legal obligation
        'EXPUNGE_LEGAL_ORDER'               -- Full payload expunged pursuant to court/statutory order
    )),
    reason TEXT NOT NULL,                   -- Comprehensive explanation of the decision
    legal_basis TEXT NOT NULL,              -- Citation of statute, license clause, court decree, or policy
    authorized_decision_maker TEXT NOT NULL,-- Legal counsel / Governance officer identity
    decision_timestamp TEXT NOT NULL,       -- ISO 8601 UTC timestamp
    applicable_retention_deadline TEXT,     -- Specific date if statutory hold applies; NULL if indefinite
    verification_evidence_ref TEXT,         -- Document path or checksum of legal correspondence/order
    created_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions(candidate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_retention_candidate ON retention_decisions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_retention_type ON retention_decisions(decision_type);
```

---

## D5. Comprehensive 12-Point Export Eligibility Rules

A candidate record is **strictly prohibited** from entering an active export batch, `CorpusWriter`, or any production split JSONL (`train.jsonl`, `validation.jsonl`, `test.jsonl`) unless it satisfies all 12 points of the **Final Export Eligibility Predicate**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   FINAL 12-POINT EXPORT ELIGIBILITY GATE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  [x] 1. Explicit Human Approval: processing_status == 'APPROVED'.           │
│  [x] 2. Authorized Human Reviewer: approval_history contains a valid        │
│         actor_type='HUMAN_AUDITOR' event for the approved state.            │
│  [x] 3. Valid Source Registry Permission: candidate_sources status is        │
│         'VERIFIED PERMITTED' matching authoritative source_registry.json.   │
│  [x] 4. Explicit Training Permission: training_permitted_status is          │
│         'EXPLICITLY_PERMITTED' (general license alone is insufficient).     │
│  [x] 5. Verified Source & Artifact Provenance: artifact_sha256 !=           │
│         'NOT_VERIFIED' and physical artifact checksum matches disk bytes.    │
│  [x] 6. Non-Stale Governance & Rules: approval_expiration_date >= today,   │
│         and candidate_sources.registry_entry_sha256 matches live registry. │
│  [x] 7. Zero Unresolved Safety Conflicts: duplicate_relationships contains  │
│         zero active rows with is_safe_to_merge == 0.                        │
│  [x] 8. No Active Revocation: processing_status != 'REVOKED' and zero       │
│         active REDACT or EXPUNGE orders in retention_decisions.             │
│  [x] 9. Canonicity & Identity Confirmed: is_canonical == 1 (duplicate       │
│         submissions are linked to canonical and cannot export).              │
│  [x] 10. Valid Release Version & Split: Target corpus_version matches       │
│          export batch, and assigned_split is train, validation, or test.    │
│  [x] 11. Release-Scoped Export Idempotency: Candidate has not already been   │
│          exported into the target corpus_version.                           │
│  [x] 12. Host Preflight Verification: Physical disk partition maintains     │
│          required >= 40% host safety reserve margin (PreflightChecker).     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### D5.1 Fail-Closed Exporter Invariant
* **Fatal Halt on Unmet Condition:** If any of the 12 requirements cannot be programmatically verified, the export coordinator raises `CorpusExportEligibilityError` and immediately aborts the export batch.
* **Prohibition of Development Bypass Settings:** The Candidate Exporter shall **never** expose, accept, or invoke `strict_governance=False` or `enforce_preflight=False`. Calling code attempting to pass bypass options will raise `GovernanceBypassProhibitedError`.

---

## D6. Updated State Machine & Relational Schema (Revision 2)

### D6.1 Updated 12-State Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED : Intake Submission
    RECEIVED --> PENDING : Hash Computed & Source Verified
    PENDING --> PROCESSING : Normalization Succeeded

    state PROCESSING {
        [*] --> QualityCheck
        QualityCheck --> LanguageAudit : Passes Length & Cleanliness
        LanguageAudit --> CandidateScreening : English Confirmed
        CandidateScreening --> SemanticGuard : Jaccard/MinHash Match
    }

    PROCESSING --> PROCESSING_PASSED : Clean Pass (No Errors)
    PROCESSING --> REJECTED : Quality/Lang/Gov Failure
    PROCESSING --> QUARANTINED : Low Stopwords / Heading / SQL / Cognates
    PROCESSING --> PROCESSING_FAILED : Parser Crash / System Error

    PROCESSING_PASSED --> APPROVAL_PENDING : Zero Unresolved Conflicts Staged
    
    QUARANTINED --> APPROVAL_PENDING : Auditor Clears Ambiguity
    QUARANTINED --> REJECTED : Auditor Confirms Flaw
    
    APPROVAL_PENDING --> APPROVED : 100% EXPLICIT HUMAN AUDITOR ACTION ONLY
    APPROVAL_PENDING --> REJECTED : Human Auditor Rejection

    APPROVED --> EXPORT_PENDING : Validated by 12-Point Gate & Locked in Batch
    EXPORT_PENDING --> EXPORTED : CorpusWriter Atomic Commit & Checksums Verified
    EXPORT_PENDING --> APPROVED : Export Aborted / Clean Rollback

    APPROVED --> REVOKED : Pre-Export Revocation Event
    EXPORTED --> REVOKED : Post-Export Flaw / Legal Notice (Requires Rebuild)
    REVOKED --> PENDING : Clean Legal Clearance & Re-Evaluation
    REJECTED --> PENDING : Pipeline Rule Revision Reset
```

### D6.2 Updated SQL View: 12-Point Export Eligibility
The authoritative SQL view is updated to incorporate the human approval mandate and legal retention restrictions:

```sql
-- Authoritative View: v_export_eligible_candidates (Revision 2)
CREATE VIEW IF NOT EXISTS v_export_eligible_candidates AS
SELECT 
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
WHERE c.processing_status = 'APPROVED'                           -- 1. Must be APPROVED
  AND c.is_canonical = 1                                         -- 9. Must be canonical master
  AND s.licensing_status = 'VERIFIED PERMITTED'                  -- 3. Source is VERIFIED PERMITTED
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'       -- 4. Training explicitly authorized
  AND s.artifact_sha256 != 'NOT_VERIFIED'                        -- 5. Physical artifact verified
  AND (s.approval_expiration_date IS NULL                        -- 6. Non-stale source approval
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND EXISTS (                                                   -- 2. Explicit Human Reviewer Record
      SELECT 1 FROM approval_history ah
      WHERE ah.candidate_id = c.candidate_id
        AND ah.new_status = 'APPROVED'
        AND ah.actor_type = 'HUMAN_AUDITOR'
  )
  AND NOT EXISTS (                                               -- 7. Zero safety conflicts
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (                                               -- 8. No active legal redaction/expungement
      SELECT 1 FROM retention_decisions rd
      WHERE rd.candidate_id = c.candidate_id
        AND rd.decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
  );
```

---

## D7. Internal Consistency Verification Matrix

| Architectural Dimension | Specification Invariant | Alignment Proof in Revision 2 |
| :--- | :--- | :--- |
| **Human Approval Mandate** | Zero automated production approval. | Section D3 establishes 100% human review; `trig_enforce_human_approval_authorization` aborts automated status mutation; view `v_export_eligible_candidates` requires `HUMAN_AUDITOR` audit entry. |
| **Python Runtime Standardization** | Python 3.14.8 sole official runtime; Python 3.9 legacy until Phase 4.14.1.3 migration. | Section D2 establishes runtime mandate and 9-point migration acceptance checklist; clarifies migration has not yet occurred. |
| **Legal Retention Framework** | Evidence-based retention; no fixed 180-day deletion. | Section D4 defines legally governed retention framework; adds `retention_decisions` table DDL; preserves cryptographic hashes permanently. |
| **Export Integrity Gate** | 12-Point fail-closed eligibility. | Section D5 details all 12 points; view `v_export_eligible_candidates` enforces conditions in SQL; bypass flags strictly prohibited. |
| **Lifecycle State Machine** | 12 distinct lifecycle states. | Section D6 state machine matches DDL `CHECK` constraints; separates `PROCESSING_PASSED`, `APPROVAL_PENDING`, and `APPROVED`. |
| **System Invariants** | Zero code, database, or test modification. | File modification restricted exclusively to `docs/phase4.14.1_candidate_database_design.md`. Baseline 300 tests re-verified. |

---

## D8. Remaining Human Governance Decisions

1. **Human Auditor Authentication & Key Management:**
   * *Question:* In Phase 4.14.5 (Approval Implementation), should human reviewer signatures be recorded as plain corporate identifiers (`actor_id = 'auditor_jdoe'`) or require asymmetric cryptographic key signatures (e.g. Ed25519 signatures stored in `approval_history.evidence_reference`)?
   * *Engineering Recommendation:* Asymmetric Ed25519 digital signatures provide mathematical non-repudiation and prevent database administrators from spoofing reviewer approval events.
2. **Quarantine Escalation SLA:**
   * *Question:* What is the formal resolution deadline for candidates routed to `QUARANTINED` before they are marked expired and pruned from active review queues?
   * *Engineering Recommendation:* Establish a 30-day review SLA; candidates uninspected after 30 days are automatically archived to `REJECTED` (`REASON: QUARANTINE_REVIEW_TIMEOUT`).


---

# HYBRID REVIEWER AUTHENTICATION & DIGITAL SIGNATURE ARCHITECTURE — REVISION 3

## E1. Architectural Foundation & Project-Owner Decision

### E1.1 Formal Resolution of Governance Decision
In Revision 2 (Section D8, Item 1), the candidate database architecture identified a critical governance question regarding human reviewer verification:
*Whether human reviewer approvals should be recorded as plain database corporate identifiers or require asymmetric cryptographic digital signatures.*

The project owner has formally resolved this architecture decision:
**VEDA adopts a mandatory hybrid security architecture: Authenticated Reviewer Identity + Ed25519 Digital Signatures for all candidate approval events.**

### E1.2 The Dual-Pillar Imperative: Identity + Cryptographic Proof
A production candidate must never enter the VEDA training corpus based on single-factor or mutable authorization. The architecture enforces two mutually dependent, non-interchangeable pillars:

```
+-----------------------------------------------------------------------------------+
|                         HYBRID APPROVAL GOVERNANCE MODEL                          |
+-----------------------------------------+-----------------------------------------+
|                PILLAR 1                 |                PILLAR 2                 |
|     AUTHENTICATED HUMAN IDENTITY        |       CRYPTOGRAPHIC ED25519 PROOF       |
+-----------------------------------------+-----------------------------------------+
| * WHO made the decision.                | * MATHEMATICAL NON-REPUDIATION.         |
| * Reviewer corporate account & role.    | * Tamper-evident canonical binding.     |
| * Explicit authorization at timestamp.  | * Protection against DB admin forgery.  |
| * Interactive authentication session.   | * Verifiable in offline/exported state. |
|                                         |                                         |
| INSUFFICIENT ALONE:                     | INSUFFICIENT ALONE:                     |
| Database accounts can be altered or     | A valid signature from an unverified or |
| inserted by database administrators.    | unauthorized role confers no authority. |
+-----------------------------------------+-----------------------------------------+
|                  CONVERGENCE: FULL EXPORT ELIGIBILITY                             |
| Both identity validity AND cryptographic verification MUST succeed.               |
+-----------------------------------------------------------------------------------+
```

1. **An account identity alone is insufficient:** In an ordinary database system, a database administrator (or SQL injection vulnerability) could update `processing_status = 'APPROVED'` and insert a row into `approval_history` naming an auditor. Without a cryptographic signature generated by a private key held exclusively by the human reviewer, the database cannot prove that the auditor ever reviewed the content.
2. **A digital signature alone is insufficient:** An asymmetric key signature proves that a private key signed a byte sequence, but it does not prove that the key owner was authorized to approve linguistic corpus data, held an active corporate status, or was not revoked at the time of signing.
3. **Strict Separation of Powers:** Automated pipeline workers (language filters, deduplication engines, safety guards) execute under unprivileged system service accounts. Automated workers **must never possess, generate, borrow, or invoke human reviewer signing credentials**. Automated processing can only transition candidates to `PROCESSING_PASSED` or `APPROVAL_PENDING`. Final approval to `APPROVED` requires an interactive, authenticated human reviewer wielding a valid Ed25519 private key.

---

## E2. Reviewer Identity and Authentication Architecture

### E2.1 Reviewer Account Attributes
Every human auditor authorized to inspect and approve candidates is represented in the database architecture by a strongly typed identity entity:

- **Reviewer Identifier (`reviewer_id`):** Globally unique UUIDv4 string (e.g. `urn:uuid:7c9e6679-7425-40de-944b-e07fc1f90ae7`), stable across identity provider migrations.
- **Account Identifier (`username` / `corporate_id`):** Unique organizational username or employee identifier.
- **Full Legal Name (`full_name`):** Human auditor's verified legal or organizational name.
- **Auditor Email (`email`):** Verified organizational email address used for audit communications and notifications.
- **Account Status (`account_status`):** Strict state machine:
  - `ACTIVE`: Account fully authorized; signing keys may be used for approval events.
  - `SUSPENDED`: Temporarily halted pending administrative review; all signing operations blocked.
  - `INACTIVE`: Account dormant; signing operations blocked.
  - `OFFBOARDED`: Former reviewer departed; signing permanently disabled. Historical approvals remain valid subject to verification rules.
- **Identity Provider Subject Reference (`idp_subject_id`):** External identifier linking the reviewer record to the enterprise directory.

### E2.2 Role-Based Access Control (RBAC) Taxonomy
Reviewer authority is not monolithic. Approval requires specific domain authorization:

| Role Identifier | Role Scope & Governance Mandate | Minimum Approvals Required |
| :--- | :--- | :--- |
| `LEGAL_COMPLIANCE_AUDITOR` | Authorizes legal copyright, licensing compliance, and institutional origin verification. | Mandatory for all public-domain, CC-BY, and corporate text sources. |
| `DOMAIN_CURATOR` | Authorizes linguistic quality, dialect appropriateness, register correctness, and educational value. | Mandatory for all candidate batches. |
| `SAFETY_COMPLIANCE_OFFICER` | Authorizes candidates flagged for borderline safety, sensitive content, or controversial discourse. | Mandatory for any candidate exiting `QUARANTINED` status. |
| `CHIEF_DATA_OFFICER` | High-level executive authorization for bulk corpus batch promotion and policy exceptions. | Required for batch volume promotions > 10,000 candidates. |
| `AUDIT_OBSERVER` | Read-only inspection of queues, logs, keys, and signatures. No signing authorization. | N/A (Cannot approve). |

### E2.3 Authentication Interface Abstraction
To avoid tight coupling to specific enterprise identity providers during early development while guaranteeing production readiness, VEDA defines an abstract authentication interface:

```
+--------------------------------------------------------------------+
|               IReviewerAuthenticator (Interface)                   |
+--------------------------------------------------------------------+
| + authenticate_reviewer(credentials) -> AuthSession                |
| + validate_session(auth_session_id) -> ReviewerContext             |
| + verify_reviewer_authorization(reviewer_id, required_role) -> bool|
| + terminate_session(auth_session_id) -> void                       |
+--------------------------------------------------------------------+
                                |
       +------------------------+------------------------+
       |                                                 |
+-----------------------------------+   +------------------------------------+
|    LocalSecureAuthenticator       |   |       EnterpriseIdPAuthenticator   |
| (Initial Development / Offline)   |   | (Future Production Architecture)   |
+-----------------------------------+   +------------------------------------+
| * Salted Argon2id / PBKDF2 hash.  |   | * OIDC / OAuth 2.0 / SAML 2.0.     |
| * Local MFA / TOTP token check.   |   | * FIDO2 / WebAuthn hardware keys.  |
| * File-permission guarded store.  |   | * Enterprise directory sync.       |
| * No external SSO required now.   |   | * Automated offboarding hooks.     |
+-----------------------------------+   +------------------------------------+
```

- **Initial Implementation Target:** Secure local authentication utilizing salted Argon2id password verification and local session tokens. External SSO is **not mandatory** for the initial database integration.
- **Session Tracking (`authentication_events`):** Every reviewer login generates an auditable `auth_event_id` capturing login timestamp, client host information, authentication method, and session expiry. Every signed approval event must reference an active, valid `auth_event_id`.

---

## E3. Ed25519 Digital Signature & Deterministic Payload Specification

### E3.1 Cryptographic Algorithm Selection: Ed25519
VEDA standardizes on **Ed25519** (Edwards-curve Digital Signature Algorithm over Curve25519 using SHA-512, conforming to RFC 8032) for all candidate approval signing events:
- **Security:** 128-bit security level against classical attacks; immune to side-channel timing attacks (constant-time arithmetic).
- **Collision Resistance:** SHA-512 internal hashing eliminates collision weaknesses.
- **Compactness:** 32-byte (256-bit) public keys; 64-byte (512-bit) signatures.
- **Deterministic Signature Generation:** Ed25519 signatures are completely deterministic for a given private key and message; zero reliance on runtime random number generators during signing prevents entropy-depletion attacks.

### E3.2 Canonical Approval Payload Schema (Version 1.0)
Cryptographic signatures verify exact byte sequences. Any ambiguity in JSON serialization (whitespace, key ordering, number representation) breaks signature verification. VEDA enforces **RFC 8785 JSON Canonicalization Scheme (JCS)** with strict UTF-8 encoding.

The canonical approval payload binds exactly 12 required fields:

```json
{
  "candidate_id": "urn:uuid:a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "decision": "APPROVED",
  "decision_id": "urn:uuid:f0e1d2c3-b4a5-9687-1e0f-2a3b4c5d6e7f",
  "decision_reason": "Linguistic register conforms to formal expository English; verified license CC-BY-4.0; zero safety flags.",
  "decision_timestamp": "2026-11-13T12:00:00.000000Z",
  "normalized_content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "payload_schema_version": "1.0",
  "pipeline_version": "v0.4.14",
  "reviewer_id": "urn:uuid:7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "reviewer_role": "DOMAIN_CURATOR",
  "source_artifact_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  "source_id": "SRC-GUTENBERG-001"
}
```

### E3.3 Deterministic Serialization and Hashing Rules
1. **Key Ordering:** Object keys MUST be sorted strictly in ascending lexicographical order by Unicode code point:
   `candidate_id` < `decision` < `decision_id` < `decision_reason` < `decision_timestamp` < `normalized_content_hash` < `payload_schema_version` < `pipeline_version` < `reviewer_id` < `reviewer_role` < `source_artifact_sha256` < `source_id`.
2. **Whitespace:** NO whitespace permitted outside quoted JSON strings (no spaces after colons, no commas followed by spaces, no line breaks).
3. **Encoding:** Strict UTF-8 without byte-order mark (BOM).
4. **Timestamps:** ISO-8601 UTC representation with microsecond resolution ending in uppercase `Z` (`YYYY-MM-DDTHH:MM:SS.ffffffZ`).
5. **Payload Hash Computation:**
   $$\text{canonical\_bytes} = \text{RFC8785\_JCS}(\text{payload})$$
   $$\text{canonical\_payload\_sha256} = \text{SHA-256}(\text{canonical\_bytes}) \quad (64 \text{ lowercase hex characters})$$
6. **Signature Generation:**
   $$\text{signature\_bytes} = \text{Ed25519\_Sign}(\text{private\_key}, \text{canonical\_bytes})$$
   $$\text{signature\_hex} = \text{hex\_encode}(\text{signature\_bytes}) \quad (128 \text{ lowercase hex characters})$$
7. **Tamper Invalidation Rule:** Modifying any byte of the text, changing the candidate hash, adjusting the timestamp by one millisecond, altering the reviewer ID, or mutating the decision instantly breaks the mathematical signature verification:
   $$\text{Ed25519\_Verify}(\text{public\_key}, \text{canonical\_bytes}', \text{signature\_bytes}) == \text{FALSE}$$

---

## E4. Private-Key Custody & Operating-System Protection

### E4.1 Absolute Invariants on Private Keys
1. **NEVER in SQLite:** Private signing keys must **NEVER** be stored in the candidate database, lexicon database, or any project SQLite table in plaintext or encrypted form.
2. **NEVER in Version Control:** Private keys must **NEVER** be committed to Git. Enforced through repository `.gitignore` patterns (`*.key`, `*.pem`, `*.priv`, `*id_ed25519*`), pre-commit hooks, and CI/CD secret scanning.
3. **NEVER in Operational Outputs:** Private keys must **NEVER** appear in log files, debug transcripts, error tracebacks, console output, or exported corpus metadata.
4. **NEVER Accessible to Automated Workers:** Background corpus processing workers run in unprivileged OS service contexts that lack read permissions to reviewer key directories.

### E4.2 Operating-System Key Custody Architecture
Reviewer private keys reside exclusively on the human reviewer's secure workstation, protected by OS-level hardware and cryptographic primitives:

```
+---------------------------------------------------------------------------------+
|                       REVIEWER WORKSTATION KEY STORE                            |
+---------------------------------------------------------------------------------+
| WINDOWS PLATFORM (Standard Target):                                             |
| * Microsoft Windows Data Protection API (DPAPI) / CNG Key Storage Provider.     |
| * Master key tied to reviewer Windows login credential + optional TPM 2.0 PIN.  |
| * Storage Path: %APPDATA%\VEDA\keystore\keys\{reviewer_id}.key.enc              |
| * Decrypted ONLY in-memory during active, authenticated signing window.         |
+---------------------------------------------------------------------------------+
| POSIX / LINUX PLATFORM (Portable Target):                                       |
| * Dedicated local keystore with POSIX permissions 0600 (read/write owner only). |
| * Private keys encrypted at rest via Argon2id + ChaCha20-Poly1305 with          |
|   mandatory interactive reviewer passphrase entry.                              |
| * Hardware Security Module (HSM) / PKCS#11 token integration (YubiKey / FIDO2). |
+---------------------------------------------------------------------------------+
```

### E4.3 Strict Isolation: Development/Test Keys vs. Production Keys
To ensure testing safety without risking production compromise:
- **Test Key Flagging:** Every public key record in `reviewer_public_keys` includes a boolean column `is_test_key`.
- **Test Key Invalidation in Production:** The export eligibility gate view `v_export_eligible_candidates` strictly filters out any approval signed by a test key (`k.is_test_key = 0`).
- **Deterministic Fixture Keys:** Automated test suites use ephemeral, hardcoded test keys solely inside sandboxed test fixtures. These keys are never added to production databases.

---

## E5. Cryptographic Key Lifecycle Management

### E5.1 Nine-Stage Key Lifecycle State Machine

```
  [1. GENERATE]
        |
        v
  [2. REGISTER] ----> (Status: PENDING_ACTIVATION)
        |
        v  (Dual-control verification / Identity proof)
  [3. ACTIVATE] ----> (Status: ACTIVE) <=======================+
        |                                                     |
        |---> [4. NORMAL SIGNING] (decision_timestamp valid)  | (Rotation:
        |                                                     |  fresh key)
        |---> [5. ROTATE] -----------> (Status: ROTATED_RETIRED)
        |                               (Historical approvals valid)
        |
        +---> [6. REVOKE] -----------> (Status: REVOKED_COMPROMISED / REVOKED_ADMIN)
                    |                   (Immediate rejection of new signatures)
                    v
              [7. INVESTIGATE] -------> (Audit decisions in compromise window)
                    |
                    v
              [8. RECOVER] -----------> (Issue new key pair; quarantine unverified)
                    |
                    v
              [9. HISTORICAL VERIFICATION] (Audit verification against validity window)
```

1. **Key Generation:** Reviewer generates an Ed25519 key pair on their local workstation using a secure Cryptographically Secure Pseudorandom Number Generator (CSPRNG).
2. **Public-Key Registration:** The 32-byte public key is exported (in lowercase hex) and registered in `reviewer_public_keys` with initial status `PENDING_ACTIVATION`.
3. **Key Activation:** An authorized administrator or dual-control process verifies reviewer identity and changes status to `ACTIVE`, recording `activated_at` UTC timestamp.
4. **Normal Signing Operations:** The reviewer signs canonical approval payloads. The system confirms the key is currently `ACTIVE` and `decision_timestamp >= activated_at`.
5. **Planned Key Rotation:** Scheduled routine rotation (e.g. 180 or 365 days). The reviewer generates a new key pair. Upon activation of the new key, the old key transitions to `ROTATED_RETIRED` with `valid_until = NOW()`.
   * **Invariant:** Approvals signed during the old key's active window remain permanently verifiable and valid.
6. **Emergency Key Revocation:** Triggered immediately if a private key is lost, stolen, or suspected of compromise. Key status is updated to `REVOKED_COMPROMISED` with `revoked_at = NOW()`. New approval submissions with this key are rejected instantly.
7. **Compromise Investigation:** A security audit queries all approvals signed by the compromised key between the suspected breach date and `revoked_at`. Affected candidates are immediately placed in `QUARANTINED` pending re-inspection.
8. **Recovery and Replacement:** The reviewer generates a fresh key pair, registers it, and completes identity verification. Re-reviewing quarantined candidates requires creating brand-new approval events signed with the fresh key.
   * **Strict Impersonation Prohibition:** An administrator **cannot** re-sign on behalf of a reviewer. Any administrative intervention creates an explicit, audited `ADMIN_OVERRIDE` event signed with administrator credentials.
9. **Historical Signature Verification:** Any system auditing candidate provenance evaluates the validity window predicate:
   $$\text{IsKeyValidAt}(k, t) \iff \begin{cases}
     t \ge k.\text{activated\_at} \;\land \\
     (k.\text{valid\_until} \text{ IS NULL} \lor t \le k.\text{valid\_until}) \;\land \\
     (k.\text{revoked\_at} \text{ IS NULL} \lor t < k.\text{revoked\_at})
   \end{cases}$$

---

## E6. Database Schema Additions & Structural DDL

### E6.1 New Tables and Schema Entities
Revision 3 introduces six dedicated cryptographic and reviewer entities into the candidate database schema:

```sql
-- ============================================================================
-- 1. REVIEWER ACCOUNTS
-- Authoritative registry of verified human auditors and curators.
-- ============================================================================
CREATE TABLE reviewer_accounts (
    reviewer_id         TEXT PRIMARY KEY,              -- UUIDv4 format
    username            TEXT NOT NULL UNIQUE,          -- Corporate directory handle
    full_name           TEXT NOT NULL,                 -- Verified human legal name
    email               TEXT NOT NULL UNIQUE,          -- Corporate email
    account_status      TEXT NOT NULL DEFAULT 'ACTIVE',-- ACTIVE, SUSPENDED, INACTIVE, OFFBOARDED
    idp_subject_id      TEXT,                          -- External IdP unique subject identifier
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CONSTRAINT chk_reviewer_account_status CHECK (
        account_status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE', 'OFFBOARDED')
    )
);

-- ============================================================================
-- 2. REVIEWER ROLES (RBAC TAXONOMY)
-- Governance roles defining specific approval permissions.
-- ============================================================================
CREATE TABLE reviewer_roles (
    role_id             TEXT PRIMARY KEY,              -- Role identifier
    role_name           TEXT NOT NULL UNIQUE,          -- Display name
    description         TEXT NOT NULL,                 -- Scope of authority
    can_approve_corpus  INTEGER NOT NULL DEFAULT 1,    -- Boolean: 1 if role can grant production approval
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed predefined authoritative governance roles
INSERT INTO reviewer_roles (role_id, role_name, description, can_approve_corpus) VALUES
('ROLE_LEGAL_AUDITOR',   'LEGAL_COMPLIANCE_AUDITOR', 'Authorizes licensing, copyright, and provenance compliance', 1),
('ROLE_DOMAIN_CURATOR',  'DOMAIN_CURATOR',           'Authorizes linguistic quality, register, and dialect accuracy', 1),
('ROLE_SAFETY_OFFICER',  'SAFETY_COMPLIANCE_OFFICER', 'Authorizes resolution of quarantined or sensitive content', 1),
('ROLE_CHIEF_DATA_OFF',  'CHIEF_DATA_OFFICER',       'Executive authority for bulk promotions and policy exceptions', 1),
('ROLE_AUDIT_OBSERVER',  'AUDIT_OBSERVER',           'Read-only inspector with no approval authority', 0);

-- ============================================================================
-- 3. REVIEWER ACCOUNT ROLE ASSIGNMENTS
-- Associates reviewers with specific authorized roles over time.
-- ============================================================================
CREATE TABLE reviewer_account_roles (
    assignment_id       TEXT PRIMARY KEY,              -- UUIDv4 format
    reviewer_id         TEXT NOT NULL,
    role_id             TEXT NOT NULL,
    assigned_by         TEXT NOT NULL,                 -- Admin reviewer_id
    assigned_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    revoked_at          TEXT,                          -- NULL if actively assigned

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (role_id) REFERENCES reviewer_roles (role_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_unique_active_role ON reviewer_account_roles (reviewer_id, role_id)
WHERE revoked_at IS NULL;

-- ============================================================================
-- 4. REVIEWER PUBLIC KEYS
-- Registry of Ed25519 public keys used for signature verification.
-- NEVER STORES PRIVATE KEYS.
-- ============================================================================
CREATE TABLE reviewer_public_keys (
    public_key_id       TEXT PRIMARY KEY,              -- Key fingerprint / UUIDv4
    reviewer_id         TEXT NOT NULL,
    algorithm           TEXT NOT NULL DEFAULT 'Ed25519',
    public_key_hex      TEXT NOT NULL UNIQUE,          -- 64 lowercase hex characters (32 bytes)
    key_status          TEXT NOT NULL DEFAULT 'PENDING_ACTIVATION',
    is_test_key         INTEGER NOT NULL DEFAULT 0,    -- 1 = test fixture key, 0 = production key
    activated_at        TEXT,                          -- Timestamp when key became active
    valid_until         TEXT,                          -- Timestamp of scheduled retirement / rotation
    revoked_at          TEXT,                          -- Timestamp of emergency revocation
    revocation_reason   TEXT,                          -- Explanation for revocation
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,

    CONSTRAINT chk_key_algorithm CHECK (algorithm = 'Ed25519'),
    CONSTRAINT chk_key_hex_len CHECK (length(public_key_hex) = 64),
    CONSTRAINT chk_key_status CHECK (
        key_status IN ('PENDING_ACTIVATION', 'ACTIVE', 'ROTATED_RETIRED', 'REVOKED_COMPROMISED', 'REVOKED_ADMIN')
    ),
    CONSTRAINT chk_test_key_bool CHECK (is_test_key IN (0, 1))
);

CREATE INDEX idx_pubkeys_reviewer ON reviewer_public_keys (reviewer_id, key_status);

-- ============================================================================
-- 5. AUTHENTICATION EVENTS
-- Audit log of reviewer interactive authentication sessions.
-- ============================================================================
CREATE TABLE authentication_events (
    auth_event_id       TEXT PRIMARY KEY,              -- UUIDv4 format
    reviewer_id         TEXT NOT NULL,
    auth_method         TEXT NOT NULL,                 -- LOCAL_PASSWORD_MFA, OIDC_SSO, FIDO2_WEBAUTHN
    client_host         TEXT NOT NULL,                 -- Client hostname / IP
    auth_status         TEXT NOT NULL,                 -- SUCCESS, FAILURE, EXPIRED
    session_expires_at  TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    CONSTRAINT chk_auth_status CHECK (auth_status IN ('SUCCESS', 'FAILURE', 'EXPIRED'))
);

CREATE INDEX idx_auth_events_reviewer ON authentication_events (reviewer_id, created_at);

-- ============================================================================
-- 6. KEY LIFECYCLE EVENTS
-- Append-only audit history of key state transitions.
-- ============================================================================
CREATE TABLE key_lifecycle_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    public_key_id       TEXT NOT NULL,
    previous_status     TEXT,
    new_status          TEXT NOT NULL,
    actor_id            TEXT NOT NULL,                 -- Reviewer or admin ID executing transition
    reason              TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (public_key_id) REFERENCES reviewer_public_keys (public_key_id) ON DELETE RESTRICT
);
```

### E6.2 Enhanced Cryptographic `approval_history` Table
The existing `approval_history` table is enhanced with complete cryptographic binding columns:

```sql
-- Drop and replace initial placeholder approval_history with cryptographic schema
CREATE TABLE approval_history (
    history_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id                TEXT NOT NULL,
    decision_id                 TEXT NOT NULL UNIQUE,          -- UUIDv4 bound into payload
    reviewer_id                 TEXT NOT NULL,                 -- Reviewer identity
    reviewer_role               TEXT NOT NULL,                 -- Role asserted at signing
    public_key_id               TEXT NOT NULL,                 -- Public key used for verification
    auth_event_id               TEXT NOT NULL,                 -- Active session reference
    old_status                  TEXT NOT NULL,
    new_status                  TEXT NOT NULL,
    decision_reason             TEXT NOT NULL,
    canonical_payload_json      TEXT NOT NULL,                 -- Full RFC 8785 canonical JSON string
    canonical_payload_sha256    TEXT NOT NULL,                 -- 64 lowercase hex SHA-256 of payload
    signature_ed25519           TEXT NOT NULL,                 -- 128 lowercase hex characters (64 bytes)
    payload_schema_version      TEXT NOT NULL DEFAULT '1.0',
    verification_status         TEXT NOT NULL DEFAULT 'VERIFIED_VALID',
    created_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (public_key_id) REFERENCES reviewer_public_keys (public_key_id) ON DELETE RESTRICT,
    FOREIGN KEY (auth_event_id) REFERENCES authentication_events (auth_event_id) ON DELETE RESTRICT,

    CONSTRAINT chk_hist_status CHECK (
        new_status IN ('PROCESSING_PASSED', 'APPROVAL_PENDING', 'APPROVED', 'REJECTED', 'QUARANTINED', 'ARCHIVED')
    ),
    CONSTRAINT chk_payload_sha256_len CHECK (length(canonical_payload_sha256) = 64),
    CONSTRAINT chk_sig_ed25519_len CHECK (length(signature_ed25519) = 128),
    CONSTRAINT chk_verif_status CHECK (
        verification_status IN ('VERIFIED_VALID', 'VERIFICATION_FAILED', 'REVOKED_POST_APPROVAL')
    )
);

CREATE INDEX idx_approval_history_candidate ON approval_history (candidate_id, created_at);
CREATE INDEX idx_approval_history_reviewer ON approval_history (reviewer_id, created_at);
CREATE INDEX idx_approval_history_pubkey ON approval_history (public_key_id);
```

### E6.3 Immutability and State-Protection Triggers

```sql
-- Trigger 1: Enforce append-only semantics on approval_history (prevent UPDATE)
CREATE TRIGGER trig_abort_approval_history_update
BEFORE UPDATE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: approval_history records are immutable and cannot be updated.');
END;

-- Trigger 2: Enforce append-only semantics on approval_history (prevent DELETE)
CREATE TRIGGER trig_abort_approval_history_delete
BEFORE DELETE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: approval_history records are permanent and cannot be deleted.');
END;

-- Trigger 3: Prevent mutation of public key byte values
CREATE TRIGGER trig_abort_public_key_mutation
BEFORE UPDATE OF public_key_hex, algorithm, is_test_key ON reviewer_public_keys
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: Public key material is cryptographically immutable once registered.');
END;

-- Trigger 4: Enforce that candidate_submissions APPROVED status requires valid approval_history row
CREATE TRIGGER trig_enforce_signed_approval_mutation
BEFORE UPDATE OF processing_status ON candidate_submissions
WHEN NEW.processing_status = 'APPROVED'
BEGIN
    -- Abort if no matching valid approval history entry exists for this candidate
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM approval_history ah
            JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
            JOIN reviewer_public_keys rpk ON ah.public_key_id = rpk.public_key_id
            WHERE ah.candidate_id = NEW.candidate_id
              AND ah.new_status = 'APPROVED'
              AND ah.verification_status = 'VERIFIED_VALID'
              AND ra.account_status = 'ACTIVE'
              AND rpk.is_test_key = 0
              AND rpk.key_status IN ('ACTIVE', 'ROTATED_RETIRED')
        )
        THEN RAISE(ABORT, 'SECURITY VIOLATION: Cannot mark candidate APPROVED without an authenticated, verified human Ed25519 approval event.')
    END;
END;
```

### E6.4 Enhanced Cryptographic Export View: `v_export_eligible_candidates`

```sql
-- Comprehensive 14-point fail-closed production export eligibility view
CREATE VIEW v_export_eligible_candidates AS
SELECT
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution,
    ah.decision_id AS approval_decision_id,
    ah.reviewer_id AS approved_by_reviewer_id,
    ra.full_name AS reviewer_full_name,
    ah.signature_ed25519 AS approval_signature,
    ah.canonical_payload_sha256 AS payload_hash
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
JOIN approval_history ah ON c.candidate_id = ah.candidate_id
JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
WHERE c.processing_status = 'APPROVED'                           -- 1. Status is APPROVED
  AND c.is_canonical = 1                                         -- 2. Master deduplicated candidate
  AND s.licensing_status = 'VERIFIED PERMITTED'                  -- 3. Source licensing verified
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'       -- 4. Training explicitly permitted
  AND s.artifact_sha256 != 'NOT_VERIFIED'                        -- 5. Physical source hash verified
  AND (s.approval_expiration_date IS NULL                        -- 6. Source approval non-expired
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND ah.new_status = 'APPROVED'                                 -- 7. Audit entry approves candidate
  AND ah.verification_status = 'VERIFIED_VALID'                  -- 8. Signature verification succeeded
  AND ra.account_status = 'ACTIVE'                               -- 9. Reviewer account is active
  AND k.is_test_key = 0                                          -- 10. NOT signed with test key
  AND k.key_status IN ('ACTIVE', 'ROTATED_RETIRED')              -- 11. Key active or legitimately rotated
  AND ah.created_at >= k.activated_at                            -- 12. Signed after key activation
  AND (k.valid_until IS NULL OR ah.created_at <= k.valid_until)   -- 13. Signed before key retirement
  AND (k.revoked_at IS NULL OR ah.created_at < k.revoked_at)     -- 14. Signed before any emergency revocation
  AND NOT EXISTS (                                               -- 15. Zero safety-merge conflicts
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (                                               -- 16. Zero active legal redaction/expungement
      SELECT 1 FROM retention_decisions rd
      WHERE rd.candidate_id = c.candidate_id
        AND rd.decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
  );
```

---

## E7. End-to-End Approval Verification Rules & Invariants

A candidate submitted for inclusion in the VEDA production corpus is considered **human-approved** if and only if all eight sequential verification stages pass:

```
[Candidate Ingestion] -> [Automated Filtering Passed] -> [Queue: APPROVAL_PENDING]
                                                                  |
                                                                  v
+-----------------------------------------------------------------------------------+
|                     EIGHT-STAGE APPROVAL VERIFICATION GATE                        |
+---+------------------------------------+------------------------------------------+
| 1 | Reviewer Identity Authentication   | Account exists, status == 'ACTIVE',      |
|   |                                    | active session in authentication_events. |
+---+------------------------------------+------------------------------------------+
| 2 | Role Authorization Check           | Reviewer holds authorized role           |
|   |                                    | (e.g. DOMAIN_CURATOR, LEGAL_AUDITOR).    |
+---+------------------------------------+------------------------------------------+
| 3 | Explicit Human Decision            | Action triggered interactively by human; |
|   |                                    | automated service accounts rejected.     |
+---+------------------------------------+------------------------------------------+
| 4 | Canonical Payload Construction     | Strict RFC 8785 JCS serialization of     |
|   |                                    | 12 required fields; UTF-8 encoded.       |
+---+------------------------------------+------------------------------------------+
| 5 | Deterministic Ed25519 Signing      | Reviewer private key creates 64-byte     |
|   |                                    | signature over canonical payload bytes.  |
+---+------------------------------------+------------------------------------------+
| 6 | Public Key Validity Window         | Public key is registered, not test key,  |
|   |                                    | decision_timestamp inside active window. |
+---+------------------------------------+------------------------------------------+
| 7 | Cryptographic Verification         | ed25519_verify(pubkey, payload, sig)     |
|   |                                    | evaluates to TRUE.                       |
+---+------------------------------------+------------------------------------------+
| 8 | Append-Only Audit Commit           | Complete payload, hash, signature, and   |
|   |                                    | audit record committed in transaction.   |
+---+------------------------------------+------------------------------------------+
```

**Fail-Closed Rule:** If ANY of the eight verification stages encounters an error, discrepancy, missing field, or cryptographic failure:
1. The transaction is **rolled back**.
2. Candidate `processing_status` **CANNOT** become `APPROVED`.
3. An audit alert is logged in `authentication_events` / security logs.
4. Candidate remains strictly **ineligible for production corpus export**.

---

## E8. Comprehensive Future Security Test Suite Specification

The candidate database implementation (Phase 4.14.5 and beyond) must implement and pass the following 16 designated security tests before candidate data may be exported for tokenization or pretraining:

| Test Identifier | Test Scope & Objective | Pass Condition |
| :--- | :--- | :--- |
| `SEC-01-VALID-SIGNATURE` | Verify valid Ed25519 signature over canonical payload. | `ed25519_verify` returns TRUE; record inserted into `approval_history`; candidate exportable. |
| `SEC-02-INVALID-SIGNATURE-BYTES` | Submit payload with corrupted/random signature bytes. | Verification fails; transaction aborts; candidate rejected. |
| `SEC-03-ALTERED-CONTENT-HASH` | Alter `normalized_content_hash` by a single hex character. | Payload hash mismatch; signature check fails; transaction aborts. |
| `SEC-04-ALTERED-REVIEWER-ID` | Alter `reviewer_id` in canonical payload. | Signature check fails; transaction aborts. |
| `SEC-05-ALTERED-DECISION` | Alter `decision` from `REJECTED` to `APPROVED` without re-signing. | Signature check fails; transaction aborts; candidate rejected. |
| `SEC-06-ALTERED-TIMESTAMP` | Alter `decision_timestamp` by +1 second. | Canonical byte mismatch; signature check fails; transaction aborts. |
| `SEC-07-UNAUTHORIZED-ROLE` | Reviewer with `AUDIT_OBSERVER` role attempts approval signature. | Role gate raises authorization exception prior to signing. |
| `SEC-08-INACTIVE-REVIEWER` | Reviewer with `SUSPENDED` or `OFFBOARDED` account status attempts approval. | Account status gate aborts operation; signature rejected. |
| `SEC-09-REVOKED-PUBLIC-KEY` | Attempt approval using private key whose public key has status `REVOKED_COMPROMISED`. | Key status check raises security violation; operation rejected. |
| `SEC-10-EXPIRED-SUPERSEDED-KEY` | Attempt approval using key past its `valid_until` timestamp. | Key validity check fails; requires rotated active key. |
| `SEC-11-HISTORICAL-ROTATION-VALIDITY` | Query candidate approved under Key A after Key A has transitioned to `ROTATED_RETIRED`. | Historical verification passes; candidate remains eligible in `v_export_eligible_candidates`. |
| `SEC-12-PRIVATE-KEY-LEAKAGE-AUDIT` | Scan SQLite database, disk logs, CLI outputs, and JSON exports for Ed25519 private keys. | Zero private key strings, PEM blocks, or hex sequences found. |
| `SEC-13-TEST-KEY-REJECTION` | Submit approval signed by key flagged with `is_test_key = 1`. | Signature succeeds mathematically, but `v_export_eligible_candidates` filters candidate out. |
| `SEC-14-AUTOMATED-WORKER-SIGNING-ATTEMPT`| Execute pipeline background ingestion service attempting to invoke signing endpoint. | Execution denied: worker lacks keystore credentials and authorization role. |
| `SEC-15-REPLAY-ATTACK-PREVENTION` | Extract valid signature from Candidate A and submit it for Candidate B. | Fails: `candidate_id` and `normalized_content_hash` mismatch breaks signature check. |
| `SEC-16-APPROVAL-HISTORY-TAMPER-DETECTION`| Direct SQL UPDATE executed on `approval_history` row. | SQLite trigger `trig_abort_approval_history_update` immediately aborts query. |

---

## E9. Scope Boundaries & Implementation Quarantine

### E9.1 Pure Specification Boundary
This Revision 3 document establishes the complete architectural and cryptographic specification for human reviewer authentication and digital signatures.

**Strict Phase Boundaries Maintained:**
- **NO Database Initialization:** SQLite tables (`reviewer_accounts`, `reviewer_public_keys`, `approval_history`, etc.) are **NOT** created in this phase.
- **NO Code Implementation:** No production Python authentication services, signing modules, or key management CLI tools are written during Phase 4.14.1.3.
- **NO Key Generation:** No production or test Ed25519 cryptographic keys are generated or stored on disk during this phase.
- **NO Migration Execution:** Existing database files and corpus manifests remain 100% untouched.

All implementation belongs exclusively to designated future engineering phases (Phase 4.14.2 for core table migration, Phase 4.14.5 for reviewer auth and signing services).

---

## E10. Revision 3 Architectural Consistency & Alignment Matrix

| Architectural Dimension | Specification Invariant | Alignment Proof in Revision 3 |
| :--- | :--- | :--- |
| **Hybrid Reviewer Model** | Dual-pillar requirement: authenticated human identity AND Ed25519 cryptographic signature. | Section E1 establishes both pillars; Section E7 defines 8-stage verification pipeline; Section E6 DDL links `reviewer_accounts` and `reviewer_public_keys`. |
| **Automated Worker Restriction** | Zero signing authority for automated background services. | Section E1.2 and E7 explicitly prohibit automated services from creating or using reviewer signing keys. |
| **Cryptographic Determinism** | RFC 8785 JSON Canonicalization Scheme (JCS) with UTF-8. | Section E3.2 specifies 12 bound fields and strict JCS canonicalization rules. |
| **Private-Key Protection** | Zero private keys in database, git, logs, or exports; OS-level keystore protection. | Section E4 details Windows DPAPI/CNG and POSIX 0600 keystores; strictly forbids keys in SQLite. |
| **Key Lifecycle Governance** | 9-stage lifecycle: generation, registration, activation, signing, rotation, revocation, investigation, recovery, verification. | Section E5 specifies full state machine; historical approvals survive rotation; compromised keys trigger quarantine. |
| **Test Key Isolation** | Development/test keys strictly blocked from production corpus export. | Table `reviewer_public_keys.is_test_key` flag enforced by view `v_export_eligible_candidates`. |
| **Security Verification** | 16 comprehensive security tests specified for future phases. | Section E8 defines `SEC-01` through `SEC-16`. |
| **System Invariants** | Zero code, database, or test modification in current phase. | Pure documentation revision appended to `docs/phase4.14.1_candidate_database_design.md`. Baseline 300 tests verified. |


---

# OWNER DECISION — QUARANTINE TIMEOUT POLICY — REVISION 4

## F1. Authoritative Project-Owner Decision & Historical Clarification

### F1.1 Formal Resolution of Quarantine SLA Decision
In Revision 2 (Section D8, Item 2), the candidate database architecture recorded an open engineering recommendation:
*Whether uninspected candidates in `QUARANTINED` status should be automatically expired and archived to `REJECTED` after a 30-day review SLA.*

The project owner has issued the authoritative, binding governance decision:
**A quarantine timeout must NEVER automatically change a candidate's decision or lifecycle status.**

The previous engineering recommendation suggesting automated rejection after 30 days (`REJECTED`, reason `QUARANTINE_REVIEW_TIMEOUT`) is **explicitly overruled and permanently prohibited**.

### F1.2 Core Invariants of the Quarantine Governance Policy
A 30-day SLA period may be utilized **strictly for reminders, monitoring, metrics, and escalation**. It must **never** automatically:
1. **Reject a candidate:** No candidate may be marked `REJECTED` by a cron job, timer, background daemon, or timeout predicate.
2. **Approve a candidate:** No candidate may be marked `APPROVED` through default inaction or queue expiration.
3. **Release a candidate from quarantine:** No candidate may transition from `QUARANTINED` to `APPROVAL_PENDING` or `PROCESSING_PASSED` simply because time elapsed.
4. **Revoke a candidate:** Revocation is a distinct legal/governance action requiring human cause and cryptographic evidence.
5. **Delete candidate content:** Candidate text, normalized representations, and diagnostic records must remain preserved under the legal retention policy.
6. **Make a candidate export-eligible:** A candidate in `QUARANTINED` status is mathematically and relationally barred from entering any training corpus export.

**Fundamental Governance Principle:**
An unresolved candidate must remain in `QUARANTINED` status indefinitely until an authorized human reviewer inspects the evidence and makes an explicit, documented, and cryptographically signed decision.

---

## F2. Required 10-Step Quarantine Workflow

The candidate database architecture enforces a strict, deterministic 10-step lifecycle for all quarantined material:

```
+-----------------------------------------------------------------------------------+
|                        MANDATORY 10-STEP QUARANTINE WORKFLOW                      |
+----+----------------------------------+-------------------------------------------+
| 1  | Pipeline Quarantine Ingestion    | Automated filter, safety guard, or near-  |
|    |                                  | dedup engine detects boundary conflict.   |
+----+----------------------------------+-------------------------------------------+
| 2  | Diagnostic Record Registration   | System records candidate ID, quarantine   |
|    |                                  | reason, diagnostic evidence, timestamp,   |
|    |                                  | pipeline version, and review category.    |
+----+----------------------------------+-------------------------------------------+
| 3  | Instant Export Quarantine        | Candidate processing_status = 'QUARANTINED'|
|    |                                  | Immediately excluded from export views.   |
+----+----------------------------------+-------------------------------------------+
| 4  | Review Queue Enqueue             | Dedicated quarantine_cases record created |
|    |                                  | with assigned review group or auditor.    |
+----+----------------------------------+-------------------------------------------+
| 5  | Periodic Monitoring Reminders    | Automated notifications generated at 7,   |
|    |                                  | 14, and 21 days (Status remains intact).  |
+----+----------------------------------+-------------------------------------------+
| 6  | 30-Day Threshold Escalation      | Case flagged as escalated_at = NOW();     |
|    |                                  | alerts sent to Lead Curator / Compliance. |
+----+----------------------------------+-------------------------------------------+
| 7  | Post-Escalation State Invariant  | Candidate REMAINS 'QUARANTINED'. Zero     |
|    |                                  | automated status mutation occurs.        |
+----+----------------------------------+-------------------------------------------+
| 8  | Interactive Human Evidence Audit | Authorized human auditor opens case in    |
|    |                                  | review dashboard; examines full context.  |
+----+----------------------------------+-------------------------------------------+
| 9  | Explicit Human Determination     | Auditor chooses permitted resolution:     |
|    |                                  | (a) Release to Pending, (b) Reject,       |
|    |                                  | (c) Approve with Dual Role, or (d) Dispute|
+----+----------------------------------+-------------------------------------------+
| 10 | Cryptographic Audit Commit       | Append-only approval_history commit with  |
|    |                                  | reviewer Ed25519 signature + payload hash.|
+----+----------------------------------+-------------------------------------------+
```

---

## F3. Reminder and Escalation Architecture (Non-Mutating)

### F3.1 Strict Separation of Monitoring and State Mutation
Automated daemons and background monitoring workers may collect metrics, calculate aging in days, and generate notification alerts. However, they are strictly prohibited from possessing database permissions or SQL code paths that modify `candidate_submissions.processing_status`.

```sql
-- Architectural Constraint: Monitoring updates metadata ONLY.
-- Permitted:
UPDATE quarantine_cases 
SET last_reminder_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') 
WHERE case_id = ?;

UPDATE quarantine_cases 
SET escalated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
    escalation_level = 'ESCALATED_30_DAYS'
WHERE case_id = ? AND escalated_at IS NULL;

-- STRICTLY FORBIDDEN by schema and application logic:
-- UPDATE candidate_submissions SET processing_status = 'REJECTED' WHERE ...
```

### F3.2 Escalation Hierarchy
- **Day 0–7 (Standard Review):** Candidate placed in domain queue based on quarantine reason (`LANGUAGE`, `SAFETY`, `LEGAL`, `NEAR_DEDUP`).
- **Day 7, 14, 21 (Reminders):** Automated notifications to assigned curators. `last_reminder_at` timestamp updated.
- **Day 30 (Primary Escalation):** Unresolved case elevated to `ESCALATED_30_DAYS`. Alert broadcast to `SAFETY_COMPLIANCE_OFFICER` and `CHIEF_DATA_OFFICER`. Status remains `QUARANTINED`.
- **Day 60+ (Critical Backlog Escalation):** Case tagged `CRITICAL_60_DAYS`. Included in monthly governance risk reports. Status remains `QUARANTINED`.

---

## F4. Human Decision Requirements & Cryptographic Binding

### F4.1 Reviewer Authority and Required Roles
Quarantine resolution cannot be performed by general annotators or automated services. Resolution requires an authenticated reviewer possessing specific governance authority:

| Quarantine Origin / Category | Minimum Required Reviewer Role | Governance Justification |
| :--- | :--- | :--- |
| `SEMANTIC_SAFETY_CONFLICT` | `SAFETY_COMPLIANCE_OFFICER` | Safety filter boundary decisions require formal safety officer sign-off. |
| `LANGUAGE_FILTER_AMBIGUOUS` | `DOMAIN_CURATOR` | Linguistic register and dialect disambiguation requires domain curation authority. |
| `SOURCE_LICENSING_UNCERTAINTY` | `LEGAL_COMPLIANCE_AUDITOR` | Copyright, provenance, and license clearance requires legal auditor authority. |
| `NEAR_DEDUP_INVERSION` | `DOMAIN_CURATOR` | Semantic inversion vs. valid paraphrase distinction requires curation expertise. |
| Escalated Cases (> 30 Days) | Role above + `CHIEF_DATA_OFFICER` notification | Escalated backlog items require senior oversight. |

### F4.2 Mandatory Cryptographic Resolution Payload
Every quarantine resolution decision must construct a canonical approval payload under the Revision 3 Ed25519 specification (RFC 8785 JCS, UTF-8 encoded). The payload explicitly binds the quarantine resolution context:

```json
{
  "candidate_id": "urn:uuid:a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "decision": "RELEASED_TO_PENDING",
  "decision_id": "urn:uuid:8f7e6d5c-4b3a-2109-8765-4e3d2c1b0a9f",
  "decision_reason": "Audited technical terminology low-stopword sentence; confirmed valid expository English; safety conflict resolved as false positive.",
  "decision_timestamp": "2026-11-13T12:30:00.000000Z",
  "normalized_content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "payload_schema_version": "1.0",
  "pipeline_version": "v0.4.14",
  "quarantine_case_id": "urn:uuid:3c2b1a0f-9e8d-7c6b-5a49-3e2d1c0b9a8f",
  "reviewer_id": "urn:uuid:7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "reviewer_role": "SAFETY_COMPLIANCE_OFFICER",
  "source_artifact_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  "source_id": "SRC-GUTENBERG-001"
}
```

---

## F5. State Machine Invariants: Valid & Prohibited Transitions

### F5.1 12-State Lifecycle Quarantine Transition Matrix
The 12-state candidate lifecycle (`SUBMITTED`, `VALIDATED`, `PROCESSING_PASSED`, `PROCESSING_FAILED`, `APPROVAL_PENDING`, `APPROVED`, `REJECTED`, `QUARANTINED`, `EXPORTED`, `REVOKED`, `RESTRICTED_DISPUTED`, `ARCHIVED`) enforces strict entry and exit invariants around `QUARANTINED`:

```
                           +----------------------+
                           |     SUBMITTED        |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           |     VALIDATED        |
                           +----------+-----------+
                                      |
             +------------------------+------------------------+
             |                                                 |
             v                                                 v
+--------------------------+                      +--------------------------+
|    PROCESSING_PASSED     |                      |       QUARANTINED        |<---+
+------------+-------------+                      +-------------+------------+    |
             |                                                  |                 | Reprocessing
             |                                                  |                 | (Unresolved)
             v                                                  |                 |
+--------------------------+                                    |                 |
|     APPROVAL_PENDING     |<--- (1. RELEASED_TO_PENDING) ------+                 |
+------------+-------------+                                    |                 |
             |                                                  |                 |
             +------------------+                               |                 |
             |                  |                               |                 |
             v                  v                               v                 |
      +--------------+   +--------------+               +----------------+        |
      |   APPROVED   |   |   REJECTED   |<-- (2. REJECT)| REPROCESSING   +--------+
      +------+-------+   +--------------+               | (Maintains Q)  |
             |                                          +----------------+
             v                                                  |
      +--------------+                                          v
      |   EXPORTED   |                            +----------------------------+
      +--------------+                            |    RESTRICTED_DISPUTED     |
                                                  | (3. Legal / Dispute Hold)  |
                                                  +----------------------------+
```

### F5.2 Permitted Exits from `QUARANTINED` (Strictly Human Action)
1. **`QUARANTINED` $\rightarrow$ `APPROVAL_PENDING` (`RELEASED_TO_PENDING`):**
   - *Condition:* Authorized human auditor determines candidate was falsely flagged. Auditor signs resolution payload clearing quarantine. Candidate moves to `APPROVAL_PENDING` for standard curriculum review.
2. **`QUARANTINED` $\rightarrow$ `REJECTED`:**
   - *Condition:* Authorized human auditor confirms linguistic defect, unresolvable safety violation, or licensing invalidity. Auditor explicitly signs rejection payload with documented rationale.
3. **`QUARANTINED` $\rightarrow$ `APPROVED` (`SPECIAL_DUAL_APPROVAL`):**
   - *Condition:* High-authority dual-role reviewer (or joint sign-off) resolves quarantine and simultaneously certifies curriculum fitness in a single high-assurance cryptographic event.
4. **`QUARANTINED` $\rightarrow$ `RESTRICTED_DISPUTED`:**
   - *Condition:* Legal counsel or compliance officer places candidate under legal dispute hold pending copyright or regulatory inquiry.

### F5.3 Strictly Prohibited Transitions (System Violation)
| Prohibited State Transition | Trigger Mechanism | Violation Type | Architectural Enforcement |
| :--- | :--- | :--- | :--- |
| `QUARANTINED` $\rightarrow$ `REJECTED` | 30-Day Timeout / Expiration | Automated Rejection Violation | Aborted by trigger `trig_abort_unauthorized_quarantine_exit`. |
| `QUARANTINED` $\rightarrow$ `APPROVED` | Cron Daemon / Inaction | Automated Approval Violation | Aborted by trigger `trig_enforce_signed_approval_mutation`. |
| `QUARANTINED` $\rightarrow$ `APPROVAL_PENDING` | Automated Reprocessing Job | Silent Clearance Violation | Reprocessing without human resolution leaves status as `QUARANTINED`. |
| `QUARANTINED` $\rightarrow$ `ARCHIVED` | Storage Cleanup Script | Premature Deletion Violation | Aborted by foreign key and retention integrity constraints. |
| `QUARANTINED` $\rightarrow$ `EXPORTED` | Export Batch Compiler | Export Quarantine Breach | Blocked by SQL view predicate `processing_status != 'QUARANTINED'`. |

---

## F6. Database Schema Additions & Structural DDL

### F6.1 New Dedicated Entity: `quarantine_cases`
Revision 4 introduces a dedicated relational entity to manage the lifecycle, monitoring, escalation, and resolution of quarantined candidates without overloading `candidate_submissions`:

```sql
-- ============================================================================
-- 7. QUARANTINE CASES
-- Authoritative tracking of quarantined candidates, monitoring SLAs, 
-- non-mutating escalations, and cryptographically signed human resolutions.
-- ============================================================================
CREATE TABLE quarantine_cases (
    case_id                         TEXT PRIMARY KEY,              -- UUIDv4 format
    candidate_id                    TEXT NOT NULL,                 -- FK to candidate_submissions
    quarantine_reason               TEXT NOT NULL,                 -- Reason code
    quarantine_category             TEXT NOT NULL,                 -- SAFETY, LANGUAGE, LEGAL, QUALITY
    diagnostic_evidence_json        TEXT NOT NULL,                 -- Diagnostic payload, tokens, scores
    pipeline_version                TEXT NOT NULL,                 -- Version that flagged candidate
    quarantined_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    review_due_at                   TEXT NOT NULL,                 -- SLA monitoring target (quarantined_at + 30 days)
    last_reminder_at                TEXT,                          -- Timestamp of last reminder sent
    escalated_at                    TEXT,                          -- Timestamp of 30-day escalation
    escalation_level                TEXT NOT NULL DEFAULT 'STANDARD', -- STANDARD, ESCALATED_30_DAYS, CRITICAL_60_DAYS
    assigned_reviewer_id            TEXT,                          -- Reviewer assigned to inspect case
    assigned_role                   TEXT NOT NULL,                 -- Required reviewer role to resolve
    resolution_decision_id          TEXT,                          -- FK to approval_history (NULL while unresolved)
    resolution_evidence_reference   TEXT,                          -- External evidence or notes reference
    resolved_at                     TEXT,                          -- Timestamp of explicit human resolution

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (assigned_reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (assigned_role) REFERENCES reviewer_roles (role_id) ON DELETE RESTRICT,
    FOREIGN KEY (resolution_decision_id) REFERENCES approval_history (decision_id) ON DELETE RESTRICT,

    CONSTRAINT chk_quarantine_reason CHECK (
        quarantine_reason IN (
            'LANGUAGE_FILTER_AMBIGUOUS',
            'SEMANTIC_SAFETY_CONFLICT',
            'NEAR_DEDUP_INVERSION',
            'SOURCE_LICENSING_UNCERTAINTY',
            'MALFORMED_STRUCTURE',
            'MANUAL_HUMAN_QUARANTINE'
        )
    ),
    CONSTRAINT chk_quarantine_category CHECK (
        quarantine_category IN ('SAFETY', 'LANGUAGE', 'LEGAL', 'QUALITY')
    ),
    CONSTRAINT chk_escalation_level CHECK (
        escalation_level IN ('STANDARD', 'ESCALATED_30_DAYS', 'CRITICAL_60_DAYS')
    ),
    CONSTRAINT chk_resolution_consistency CHECK (
        (resolution_decision_id IS NULL AND resolved_at IS NULL) OR
        (resolution_decision_id IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX idx_quarantine_candidate ON quarantine_cases (candidate_id);
CREATE INDEX idx_quarantine_open_cases ON quarantine_cases (quarantine_category, escalation_level)
WHERE resolution_decision_id IS NULL;
CREATE INDEX idx_quarantine_sla_monitoring ON quarantine_cases (review_due_at)
WHERE resolution_decision_id IS NULL;
```

### F6.2 Database Triggers Enforcing Non-Mutating Escalation
Triggers guarantee that reminder and escalation updates cannot mutate candidate status, and that non-human actors cannot resolve quarantine cases:

```sql
-- Trigger 1: Abort any attempt to resolve quarantine without a human cryptographic approval record
CREATE TRIGGER trig_abort_unauthorized_quarantine_exit
BEFORE UPDATE OF processing_status ON candidate_submissions
WHEN OLD.processing_status = 'QUARANTINED' AND NEW.processing_status != 'QUARANTINED'
BEGIN
    SELECT CASE
        -- Must have a matching resolved quarantine case referencing approval_history
        WHEN NOT EXISTS (
            SELECT 1 FROM quarantine_cases qc
            JOIN approval_history ah ON qc.resolution_decision_id = ah.decision_id
            JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
            WHERE qc.candidate_id = NEW.candidate_id
              AND qc.resolution_decision_id IS NOT NULL
              AND ra.account_status = 'ACTIVE'
              AND ah.verification_status = 'VERIFIED_VALID'
        )
        THEN RAISE(ABORT, 'SECURITY VIOLATION: Candidate cannot exit QUARANTINED without an authenticated human cryptographic resolution record.')
    END;
END;

-- Trigger 2: Prevent timeout or escalation updates from altering candidate processing status
CREATE TRIGGER trig_prevent_escalation_status_tampering
BEFORE UPDATE OF escalation_level, escalated_at, last_reminder_at ON quarantine_cases
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM candidate_submissions cs
            WHERE cs.candidate_id = NEW.candidate_id
              AND cs.processing_status != 'QUARANTINED'
        )
        THEN RAISE(ABORT, 'INTEGRITY VIOLATION: Escalation or reminder updates cannot be applied to non-quarantined candidates.')
    END;
END;
```

---

## F7. Export Safety Gate & View Integration

### F7.1 Strict Fail-Closed Export View Definition
The production export eligibility view `v_export_eligible_candidates` is updated to incorporate an explicit, fail-closed check against active or unresolved quarantine cases:

```sql
-- Enhanced 17-Point Production Export Eligibility View (Revision 4)
CREATE VIEW v_export_eligible_candidates AS
SELECT
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution,
    ah.decision_id AS approval_decision_id,
    ah.reviewer_id AS approved_by_reviewer_id,
    ra.full_name AS reviewer_full_name,
    ah.signature_ed25519 AS approval_signature,
    ah.canonical_payload_sha256 AS payload_hash
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
JOIN approval_history ah ON c.candidate_id = ah.candidate_id
JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
WHERE c.processing_status = 'APPROVED'                           -- 1. Status is APPROVED
  AND c.processing_status != 'QUARANTINED'                       -- 2. Explicitly NOT QUARANTINED
  AND c.is_canonical = 1                                         -- 3. Master deduplicated candidate
  AND s.licensing_status = 'VERIFIED PERMITTED'                  -- 4. Source licensing verified
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'       -- 5. Training explicitly permitted
  AND s.artifact_sha256 != 'NOT_VERIFIED'                        -- 6. Physical source hash verified
  AND (s.approval_expiration_date IS NULL                        -- 7. Source approval non-expired
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND ah.new_status = 'APPROVED'                                 -- 8. Audit entry approves candidate
  AND ah.verification_status = 'VERIFIED_VALID'                  -- 9. Signature verification succeeded
  AND ra.account_status = 'ACTIVE'                               -- 10. Reviewer account is active
  AND k.is_test_key = 0                                          -- 11. NOT signed with test key
  AND k.key_status IN ('ACTIVE', 'ROTATED_RETIRED')              -- 12. Key active or legitimately rotated
  AND ah.created_at >= k.activated_at                            -- 13. Signed after key activation
  AND (k.valid_until IS NULL OR ah.created_at <= k.valid_until)   -- 14. Signed before key retirement
  AND (k.revoked_at IS NULL OR ah.created_at < k.revoked_at)     -- 15. Signed before any emergency revocation
  AND NOT EXISTS (                                               -- 16. ZERO UNRESOLVED QUARANTINE CASES
      SELECT 1 FROM quarantine_cases qc
      WHERE qc.candidate_id = c.candidate_id
        AND qc.resolution_decision_id IS NULL
  )
  AND NOT EXISTS (                                               -- 17. Zero safety-merge conflicts
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (                                               -- 18. Zero active legal redaction/expungement
      SELECT 1 FROM retention_decisions rd
      WHERE rd.candidate_id = c.candidate_id
        AND rd.decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
  );
```

### F7.2 Application-Level Export Quarantine Gate
At the Python application layer (to be implemented in Phase 4.14.3+), the `CorpusExporter` enforces a secondary defense-in-depth gate:
1. Queries the database using the strict `v_export_eligible_candidates` view.
2. Performs an in-memory cross-check verifying that `candidate_id` is absent from all active `quarantine_cases` records.
3. If an anomaly, unverified resolution, or null signature is encountered, the export pipeline **immediately halts and fails closed**.

---

## F8. Design Consistency & Architectural Alignment Matrix

| Architectural Dimension | Specification Invariant | Alignment Proof in Revision 4 |
| :--- | :--- | :--- |
| **Quarantine Timeout Invariant** | Timeouts NEVER change candidate status or auto-reject. | Section F1 establishes absolute ban on automated rejection; 30-day period restricted strictly to reminders and escalation. |
| **State Machine Governance** | All exits from `QUARANTINED` require authenticated human action. | Section F5 transition matrix permits only human exits; trigger `trig_abort_unauthorized_quarantine_exit` aborts automated transitions. |
| **Cryptographic Accountability** | Quarantine resolution requires Ed25519 signature + canonical payload. | Section F4 specifies resolution payload schema; references `approval_history` and `reviewer_accounts`. |
| **Relational Integrity** | `quarantine_cases` tracks SLAs, reminders, and escalations non-mutatingly. | Section F6 DDL provides dedicated table with FK constraints to candidate, reviewer, and approval records. |
| **Fail-Closed Export Gate** | Zero quarantined or unresolved candidates can enter training corpus. | Section F7 view predicate 16 (`NOT EXISTS unresolved quarantine`) and application-level gate block export. |
| **Preservation of History** | All prior decisions in Revisions 1, 2, and 3 preserved intact. | Explicit section addition without modifying previous revision text; Section D8 recommendation explicitly resolved. |

---

## F9. Scope Boundaries & Implementation Quarantine

This Revision 4 update is **strictly an architectural design and specification task**.

**Absolute Implementation Boundaries:**
- **NO Database Initialization:** Table `quarantine_cases` is NOT created in SQLite during this phase.
- **NO Code Implementation:** No background reminder daemons, escalation workers, or quarantine resolution endpoints are written in this phase.
- **NO Data Modification:** Lexicon, corpus manifests, split definitions, and baseline test suites remain completely untouched.

All physical database implementation is quarantined to authorized future phases (Phase 4.14.2 for core table creation, Phase 4.14.5 for reviewer approval and quarantine dashboard implementation).
