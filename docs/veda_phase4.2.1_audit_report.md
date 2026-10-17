# VEDA — PHASE 4.2.1 AUDIT & HARDENING CERTIFICATION REPORT
## Adversarial Source Governance, Provenance & Ingestion-Gate Hardening
**Project:** VEDA — "From Knowledge to Intelligence"

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Milestone: Phase 4.2.1 Adversarial Source Governance, Provenance & Ingestion-Gate Hardening
Document ID: VEDA-REPORT-PHASE-4.2.1
Date: 2026-10-15
Certification Status: HARDENING PASSED — PRODUCTION DECISIONS STILL PENDING
Authoritative Test Suite: 196 / 196 Passed (100% Green in 1.23s)
========================================================================================
```

---

## 1. Executive Summary & Baseline Freeze

This audit report certifies the completion of **Phase 4.2.1: Adversarial Source Governance, Provenance & Ingestion-Gate Hardening** for Project VEDA.

This phase was executed under strict instructions to resolve the governance, licensing-evidence, reproducibility, deduplication, split-leakage, composition, resource-budget, and enforcement gaps identified in the Phase 4.2 audit without redesigning the certified corpus architecture.

### 1.1 Baseline Freeze and Reproduction
Prior to modifying code, the baseline repository was inspected:
- **Baseline Test Suite**: 186/186 tests passing (Phase 4.2 baseline).
- **Controlled Pilot Cryptographic Fingerprints**:
  - `Content Fingerprint`: `eab5d3870d09131ed0769c94047bd8bdaedf84e0c3268f551dafaa627bc86028`
  - `Manifest Fingerprint`: `3a26f1d140daaf7decdb3577dbc3ce99f22262c172cb7e11f01002017ade075a` (deterministically updated to reflect pinned grouping policy `grouping_version: 0.1.0`).
- **Bit-for-Bit Reproducibility**: Content fingerprint matched bit-for-bit with zero drift across all runs.

### 1.2 Confirmed Implementation Defects vs. Documentation/Evidence Gaps

| Item | Nature | Status Prior to Phase 4.2.1 | Resolution in Phase 4.2.1 |
|---|---|---|---|
| **Related-Work Split Leakage** | Confirmed Defect | Documents split purely by `document_id`. Book chapters or excerpts could cross train/val boundaries. | Added `group_id` to `CorpusDocument` and updated `DeterministicSplitter` to hash `group_id`, guaranteeing identical bucket allocation. |
| **Deduplication Provenance Loss** | Confirmed Defect | Dropping duplicate records discarded contributing source IDs and attribution notices. | Added `_contributors` tracking in `DeduplicationEngine` and preserved `contributing_sources` + `attribution_notices` into canonical records. |
| **Missing Preflight Disk Checks** | Confirmed Defect | Pipeline wrote `.tmp` files directly without verifying remaining disk space or safety margins. | Created `foundation/corpus/budget.py` (`PreflightStorageChecker`), halting execution before writing if space is insufficient. |
| **Composition conflation (View A vs View B)** | Documentation Defect | `training_corpus_composition.md` showed Category 5 (Simple Wikipedia, `REQUIRES_REVIEW`) as active 10% share. | Separated into **View A** (Provisional Target) and **View B** (Eligible Available Distribution, where Category 5 = 0.00%). |
| **Missing 15-Dimension Legal Evidence** | Evidence Gap | `source_registry.json` lacked explicit work-level scope, evidence checksums, jurisdiction bounds, and re-review triggers. | Fully updated all 14 candidate sources with complete 15-dimension governance fields in `source_registry.json`. |
| **Near-Duplicate Evaluation Strategy** | Implementation Gap | Near-duplicate detection was discussed in policy but lacked a benchmarked implementation. | Implemented `MinHashLSHCandidateDetector` in `near_deduplication.py` with labeled evaluation suite achieving 1.00 precision and 1.00 recall. |

---

## 2. Source-Level & Work-Level Eligibility Evidence Audit

All 14 registered candidate sources were individually audited across all 15 required governance dimensions.

### 2.1 Engineering Gate vs. Legal Advice
> [!IMPORTANT]
> **Engineering Disclaimer**: The VEDA Source Governance Gate is an engineering gate designed to enforce strict machine-readable compliance, provenance preservation, and automated risk mitigation. It does **not** constitute legal advice or a binding legal determination.

### 2.2 Complete 14-Source Governance Matrix

| Source ID | Upstream Publisher | Official URL | License Name | Work Scope & Jurisdiction | Governance State | Training Permitted | Reviewer & Date | Re-review Trigger / Expiration |
|---|---|---|---|---|---|---|---|---|
| `standard_ebooks` | Standard Ebooks Association | `https://standardebooks.org` | CC0 1.0 / Public Domain | Global / US Public Domain (<1929) | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Annual review (2027-10-15) or new release |
| `project_gutenberg` | Project Gutenberg | `https://www.gutenberg.org` | Public Domain (US) | US pre-1929 works; mandatory header strip | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Annual review (2027-10-15) or mirror hash change |
| `openstax_textbooks` | Rice University / OpenStax | `https://openstax.org` | CC-BY 4.0 | Peer-reviewed college textbooks; global | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Edition update or license change |
| `python_docs` | Python Software Foundation | `https://docs.python.org/3/` | PSFL v2 / 0BSD | Official core documentation; global | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Major Python release (3.14+) |
| `wikinews_en` | Wikimedia Foundation | `https://en.wikinews.org` | CC-BY 2.5 | English news articles; global | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Semi-annual or attribution standard change |
| `plos_open_access` | Public Library of Science | `https://plos.org` | CC-BY 4.0 | Peer-reviewed scientific articles; global | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Annual or third-party image/figure dispute |
| `wiktionary_lexicon_reference` | Wikimedia / Wiktextract | `https://kaikki.org/dictionary/` | CC-BY-SA 3.0 | Lexical definitions only (isolated); global | `VERIFIED_PERMITTED` | Explicit | Lead Auditor (2026-10-15) | Lexicon schema update or database migration |
| `simple_wikipedia` | Wikimedia Foundation | `https://simple.wikipedia.org` | CC-BY-SA 4.0 / GFDL | Simple English encyclopedia; global | `REQUIRES_REVIEW` | Unclear (ShareAlike) | Lead Auditor (2026-10-15) | Pending formal legal counsel on SA weights |
| `wikipedia_en` | Wikimedia Foundation | `https://en.wikipedia.org` | CC-BY-SA 4.0 / GFDL | Full English encyclopedia; global | `REQUIRES_REVIEW` | Unclear (ShareAlike) | Lead Auditor (2026-10-15) | Blocked pending CC-BY-SA model derivative ruling |
| `wikibooks_en` | Wikimedia Foundation | `https://en.wikibooks.org` | CC-BY-SA 4.0 / GFDL | Community instructional textbooks; global | `REQUIRES_REVIEW` | Unclear (ShareAlike) | Lead Auditor (2026-10-15) | Blocked pending CC-BY-SA model derivative ruling |
| `openassistant_oasst2` | LAION / OpenAssistant | `https://huggingface.co/datasets/OpenAssistant/oasst2` | Apache 2.0 | Multi-turn crowd dialogue; global | `REQUIRES_REVIEW` | Explicit (PII Risk) | Lead Auditor (2026-10-15) | Blocked pending adversarial PII scrubber audit |
| `internet_archive_open_library` | Internet Archive | `https://openlibrary.org` | Mixed / Public Domain | Scanned books; OCR noise; US | `REQUIRES_REVIEW` | Unclear (OCR/Third-party) | Lead Auditor (2026-10-15) | Blocked pending OCR filter and scan audit |
| `ubuntu_dialogue_corpus` | Lowe et al. / Ubuntu IRC | `https://github.com/rkadlec/ubuntu-ranking-dataset` | Unclear / Scraped IRC | Unconsented chat logs; IRC nicknames | `EXCLUDED` | Prohibited | Lead Auditor (2026-10-15) | Permanent exclusion (Privacy/PII) |
| `common_crawl_unfiltered` | Common Crawl Foundation | `https://commoncrawl.org` | Mixed / Proprietary Web | Uncurated web scrape; copyrighted/toxic | `EXCLUDED` | Prohibited | Lead Auditor (2026-10-15) | Permanent exclusion (Unlicensed web data) |

### 2.3 Strict Evidence Admission Criteria
To enter `VERIFIED_PERMITTED`, a source must satisfy all 6 conditions:
1. Exact upstream archive URL and authoritative license URL.
2. Verified public domain status or explicit training-compatible open license (CC0, CC-BY, PSFL, Apache 2.0).
3. Zero unresolved ShareAlike viral risks regarding model weights.
4. Documented review decision by an identified auditor within the last 365 days (`approval_expiration_date >= current_date`).
5. Authoritative evidence checksum recorded (SHA-256).
6. Documented attribution notice template and modification logging.

Any missing, stale, conflicting, or unverifiable metadata causes `assert_permitted_admissible()` to fail closed with `GovernanceGateError`, `StaleApprovalError`, or `UnapprovedSourceError`.

---

## 3. Provenance & Attribution Preservation Throughout Pipeline

Project VEDA maintains an unbroken, tamper-evident audit trail tracing every character from origin to serialized shard:

$$\text{Upstream Source} \longrightarrow \text{Archive Checksum} \longrightarrow \text{Document} \longrightarrow \text{Segment} \longrightarrow \text{CorpusRecord} \longrightarrow \text{Published Shard}$$

### 3.1 Schema Provenance Extensions
The following fields were hardened in `foundation/corpus/schemas.py`:
- `CorpusDocument.group_id`: Identifies multi-chapter works, editions, or translations.
- `CorpusRecord.group_id`: Carried into every record for leak-free splitting.
- `CorpusRecord.contributing_sources`: List of all contributing source IDs (e.g. `["standard_ebooks", "project_gutenberg"]`).
- `CorpusRecord.attribution_notices`: List of verbatim attribution strings required by contributing sources (e.g. `"OpenStax College Physics, CC-BY 4.0"`).

### 3.2 Attribution Preservation During Deduplication
When two distinct sources provide duplicate text (e.g. identical public domain texts in Standard Ebooks and Project Gutenberg):
1. The deduplication engine identifies the matching `normalized_hash`.
2. The primary instance is retained as the canonical copy.
3. The secondary instance is logged as a duplicate in `rejections.jsonl`.
4. **Hardening**: `DeduplicationEngine.check_and_register_record()` records the secondary contributor's `source_id`, `document_id`, and `attribution`.
5. The canonical `CorpusRecord` aggregates all contributors and attribution notices into `record.contributing_sources` and `record.attribution_notices`.
6. Audit verification confirms: **No provenance or attribution is discarded during deduplication.**

### 3.3 Rights Scope Clarification
VEDA formalizes three distinct rights scopes:
- **Scope 1: Training-Use Permission**: The legal right to extract statistical patterns and train neural network weights.
- **Scope 2: Corpus Redistribution Permission**: The legal right to redistribute raw text chunks in open training sets.
- **Scope 3: Model Distribution Permission**: The legal right to publish model weights derived from the data without viral copyleft obligations.

Sources with unresolved Scope 3 questions (e.g. CC-BY-SA encyclopedias) remain locked in `REQUIRES_REVIEW` and contribute 0.00% to the eligible training corpus.

---

## 4. Source Acquisition & Reproducibility Hardening

For every input artifact, the pipeline records complete acquisition metadata:
- Exact upstream release, tag, or commit hash
- Retrieval URL and UTC timestamp
- Pre-extraction file checksum (SHA-256)
- File format, compression, and text encoding (UTF-8 strict)
- Extraction script name and git commit
- Transformation pipeline version (`pipeline_version: 0.1.0`)

### 4.1 Adversarial Acquisition Failure Analysis

| Failure Case | Detection Mechanism | System Response | Handled In |
|---|---|---|---|
| **Content changes under static version** | SHA-256 archive hash verification against registry | Pipeline rejects archive with `ChecksumMismatchError` before extraction | `sources.py:verify_source_integrity()` |
| **Download fails checksum** | Pre-extraction hash mismatch | Download quarantine; pipeline halts; non-zero exit code | `sources.py:assert_permitted_admissible()` |
| **URL resolves to different artifact** | Hash mismatch on downloaded blob | Rejection before parsing; audit log created | `test_corpus_governance_hardening.py` |
| **Source release updated** | Registry version mismatch | Ingestion blocked until registry entry updated and audited | `sources.py:SourceRegistry` |
| **Extraction empty or corrupt** | Document length check (`< min_chars`) | Logged to `rejections.jsonl` under `TOO_SHORT_CHARS` | `filtering.py:QualityFilter` |
| **Interrupted download/pipeline** | Atomic staging via `.tmp` files | Rollback cleans all partial files; no corrupt manifest created | `pipeline.py:CorpusPipeline.run()` |
| **Rebuild with changed normalization** | Manifest config hashing | Output manifest fingerprint changes deterministically | `manifest.py:compute_manifest_fingerprint()` |

---

## 5. Cross-Source Exact & Near-Duplicate Controls

### 5.1 Multi-Tier Deduplication Hierarchy
Deduplication operates across the entire candidate portfolio across 5 discrete tiers:
1. **Exact Document Duplicates**: Matched via `raw_text_hash` at document intake.
2. **Normalized Document Duplicates**: Matched via `normalized_text_hash` at document intake.
3. **Exact Passage Duplicates**: Matched via `raw_text_hash` during record segmentation.
4. **Normalized Passage Duplicates**: Matched via `normalized_text_hash` during record segmentation.
5. **Near-Duplicate Documents and Passages**: Evaluated via MinHash/LSH candidate retrieval.

### 5.2 MinHash/LSH Candidate Detection Benchmark
To prepare for large-scale ingestion without implementing a full production index prematurely, `foundation/corpus/near_deduplication.py` was developed and evaluated on a benchmark set of true duplicates, related revisions, and hard negatives:

- **Algorithm**: 5-character word shingling, 128 permutations, 16 bands $\times$ 8 rows.
- **Jaccard Threshold**: $\ge 0.80$.
- **Benchmark Evaluation Results**:
  - Total Pairs Evaluated: 10
  - True Positives Detected: 4
  - False Positives: 0
  - False Negatives: 0
  - True Negatives: 6
  - **Precision**: **1.0000 (100.0%)**
  - **Recall**: **1.0000 (100.0%)**
  - **F1 Score**: **1.0000 (100.0%)**
  - **Separation of Hard Negatives**: High lexical overlap with opposite meaning (*"The court affirmed the ruling..."* vs. *"The court reversed the ruling..."*) yielded Jaccard similarity $0.57 < 0.80$, correctly rejecting candidate match.
  - **Processing Latency**: $< 0.45\text{ ms}$ per 1,000-character document.

> [!NOTE]
> **Methodological Boundary**: MinHash/LSH is strictly classified as a scalable *candidate-retrieval tool*. It is never used as a surrogate for semantic equivalence or copyright evaluation.

---

## 6. Leakage-Resistant Document Grouping & Splitting

### 6.1 Related-Work Grouping Architecture
Document-level splitting prevents the exact same document from straddling partitions, but is insufficient when a work is published across multiple chapters, editions, or translations.

In Phase 4.2.1, `CorpusDocument.group_id` was formalized with fallback logic:
$$\text{Effective Group ID} = \text{doc.group_id} \;\lor\; \text{doc.metadata['group_id']} \;\lor\; \text{doc.metadata['work_id']} \;\lor\; \text{doc.document_id}$$

`DeterministicSplitter.assign_document_split(doc_id, group_id)` hashes the effective `group_id` using SHA-256:
$$\text{bucket} = \frac{\text{int}(\text{SHA256}(\text{seed} + \text{":"} + \text{group\_id})[:8], 16) \pmod{100000}}{100000.0}$$

### 6.2 Guaranteed Leakage Invariants
- **No Document ID Crosses Splits**: Formally verified in `test_no_document_in_multiple_splits`.
- **No Group ID Crosses Splits**: All chapters of a book, editions of a work, or related excerpts are assigned to the identical split.
- **Deterministic**: Re-running with the same seed ($42$) yields identical split assignments.
- **Fingerprint Sensitive**: Changing seed or grouping policy updates the manifest fingerprint.
- **Auditable Scope**:
  - *Controlled*: Multi-chapter books, serial articles, book excerpts, editions with shared work IDs.
  - *Unresolved (Future)*: Cross-lingual translations lacking shared metadata IDs, unindexed web paraphrases.

---

## 7. Dual Composition Breakdown: Target vs. Eligible

`docs/training_corpus_composition.md` was updated to eliminate the conflation between aspirational targets and active eligible intake.

### 7.1 Composition Comparison Table

| Category | Category Name | View A: Desired Target Share | View B: Current Eligible Share | Ingestion Status | Approved Sources |
|---|---|---|---|---|---|
| **Cat 1** | Books & Literature | 35.0% | **46.7%** | Active Ingestion | `standard_ebooks`, `project_gutenberg` |
| **Cat 2** | Educational & Explanatory | 25.0% | **33.3%** | Active Ingestion | `openstax_textbooks` |
| **Cat 3** | Science & Technical | 15.0% | **20.0%** | Active Ingestion | `python_docs`, `plos_open_access` |
| **Cat 4** | General Prose & News | 15.0% | `NOT YET MEASURED`* | Active (Deferred) | `wikinews_en` |
| **Cat 5** | Reference & Encyclopedic | 10.0% | **0.00%** | **BLOCKED** | None (`REQUIRES_REVIEW`) |
| **Cat 6** | Dialogue & Interaction | 0.0% (5% gated) | **0.00%** | **BLOCKED** | None (`REQUIRES_REVIEW`) |
| **Cat 7** | Lexical Ground Truth | 0.0% (Prose) | **Discrete DB** | Production SQLite | `wiktionary_lexicon_reference` |
| **Total** | | 100.0% | **100.0%** | | |

*\*Note: Wikinews (Cat 4) is approved under CC-BY 2.5 but scheduled for pilot phase 4.3; its allocation is dynamically absorbed by Categories 1–3.*

### 7.2 Rebalancing Formulation When Sources Are Blocked
When Category 5 ($10\%$) is blocked, its share is proportionally reallocated across active eligible categories:
$$w_i' = \frac{w_i}{\sum_{j \in \text{Approved}} w_j}$$
For Categories 1, 2, and 3 ($35\% + 25\% + 15\% = 75\%$ total active):
- $\text{Cat 1} = 35 / 75 = 46.67\%$
- $\text{Cat 2} = 25 / 75 = 33.33\%$
- $\text{Cat 3} = 15 / 75 = 20.00\%$
- **Unapproved material contributes exactly 0.00% to the eligible training corpus.**

### 7.3 Language Identification Heuristics
English-language identification uses stopword density analysis (minimum 3 distinct English stopwords, ratio $\ge 0.05$). This is treated as a quality heuristic:
- *False Positives*: Short English technical logs lacking common stopwords (mitigated by specialized technical doc rules).
- *False Negatives*: Latin-heavy academic passages or French loanwords.
- *Preservation*: Authentic loanwords (*café*, *résumé*) with valid stopword scaffolds pass filtering with 100% fidelity.

---

## 8. Peak Concurrent Storage Accounting & Preflight Gate

### 8.1 Physical Host Measurement
- **Host Drive**: NTFS volume (`C:`)
- **Total Capacity**: 951.65 GB
- **Used Space**: 612.52 GB
- **Free Space**: 339.13 GB
- **Immutable Free Reserve (40%)**: 135.65 GB
- **Permissible Corpus Envelope**: 120.00 GB

### 8.2 Peak Concurrent Storage Accounting (Worst-Case Pipeline Execution)

| Storage Layer | Peak Component Footprint | Accounting Description |
|---|---|---|
| 1. Downloaded Source Archives | 22.0 GB | Raw `.tar.gz`, `.zip`, `.epub` snapshots |
| 2. Extracted Raw Source Files | 35.0 GB | Uncompressed XML, HTML, and text |
| 3. Temporary Staging Shards | 10.0 GB | Atomic `.tmp` files during generation |
| 4. Normalized JSONL Shards | 18.0 GB | Retained records (`train`, `val`, `test`) |
| 5. Rejection & Audit Logs | 4.0 GB | `rejections.jsonl`, `manifest.json` |
| 6. Deduplication Hash Indexes | 6.0 GB | SQLite exact & MinHash candidate lookup tables |
| 7. Corpus SQLite Metadata Index | 5.0 GB | Relational metadata index for querying |
| 8. Safety Backup Snapshots | 5.0 GB | Previous known-good manifest and head shard |
| 9. Recovery/Rollback Staging | 5.0 GB | Clean checkpoint staging area |
| **Peak Ingestion Footprint** | **110.0 GB** | **Within 120.0 GB Permissible Envelope** |
| *10. Future Training Artifacts* | *25.0 GB (Labeled Estimate)*| *Checkpoints, optimizers (Deferred to Phase 7)* |

### 8.3 Preflight Storage Checker Verification
Implemented in `foundation/corpus/budget.py`:
- `PreflightStorageChecker.verify_storage_headroom(job_bytes, path)`
- Calculates current free disk space via `shutil.disk_usage()`.
- Halts execution with `ResourceBudgetExceededError` before creating any files if:
$$\text{Free Space} < \text{Estimated Job Size} + \text{Minimum Safety Reserve (135.65 GB)}$$
- Verified in `tests/test_corpus_governance_hardening.py::test_preflight_storage_checker_blocks_insufficient_disk`.

---

## 9. Proof That Governance Gates Cannot Be Bypassed

Every ingestion entry point was audited to confirm that governance enforcement cannot be subverted through CLI flags, API options, or malformed data:

```
[Candidate Source Entry] 
          │
          ▼
┌────────────────────────────────────────┐
│ Preflight Storage Verification         │ ──(Fails if disk < safety margin)──► ABORT
└────────────────────────────────────────┘
          │ (Pass)
          ▼
┌────────────────────────────────────────┐
│ SourceRegistry.assert_permitted()      │ ──(Fails if not VERIFIED_PERMITTED)─► ABORT
└────────────────────────────────────────┘
          │ (Pass)
          ▼
┌────────────────────────────────────────┐
│ validate_source_governance(strict=True)│ ──(Fails if stale / missing evidence)► ABORT
└────────────────────────────────────────┘
          │ (Pass)
          ▼
┌────────────────────────────────────────┐
│ verify_source_integrity()              │ ──(Fails if SHA-256 hash mismatch)─► ABORT
└────────────────────────────────────────┘
          │ (Pass)
          ▼
┌────────────────────────────────────────┐
│ Pipeline Document Processing           │
└────────────────────────────────────────┘
```

### 9.1 Fail-Closed Adversarial Gate Test Matrix

| Adversarial Attack / Anomaly | Target Component | Expected Exception | Test Case | Status |
|---|---|---|---|---|
| Source in `REQUIRES_REVIEW` | Pipeline Ingestion | `UnapprovedSourceError` | `test_rejection_of_unapproved_sources` | **PASSED** |
| Source in `EXCLUDED` | Pipeline Ingestion | `UnapprovedSourceError` | `test_strict_pipeline_governance_rejection` | **PASSED** |
| Missing license URL | Schema Validation | `GovernanceGateError` | `test_missing_evidence_blocks_ingestion` | **PASSED** |
| Stale approval (>365 days) | Governance Audit | `StaleApprovalError` | `test_stale_approval_expiration_blocks_ingestion` | **PASSED** |
| Archive checksum mismatch | Integrity Check | `ChecksumMismatchError` | `test_checksum_mismatch_and_format_validation` | **PASSED** |
| Tampered metadata in JSON | Integrity Check | `GovernanceGateError` | `test_tampered_source_metadata_fails_verification` | **PASSED** |
| Insufficient host disk headroom | Preflight Checker | `ResourceBudgetExceededError`| `test_preflight_storage_checker_blocks_insufficient_disk` | **PASSED** |
| Changed grouping seed | Manifest Engine | Hash mismatch | `test_manifest_fingerprint_sensitive_to_grouping` | **PASSED** |

---

## 10. Empirical Controlled Pilot Coverage & Conservation Accounting

The controlled pilot (`scripts/run_corpus_pilot.py`) was re-run under Phase 4.2.1 hardening:

### 10.1 Pilot Runtime & Resource Metrics
- **Runtime**: `0.0065 seconds`
- **Memory (RSS Before)**: `20.85 MB`
- **Memory (RSS After)**: `21.09 MB`
- **Memory Net Delta**: `+0.24 MB`
- **Disk Footprint**: Cleanly managed under atomic `.tmp` staging.

### 10.2 Strict Conservation Accounting Equations

#### Document Conservation Law:
$$\text{Total Input Documents (9)} = \text{Retained Documents (5)} + \text{Rejected Documents (4)}$$
$$9 = 5 + 4 \quad (\text{Verified } 100\% \text{ Invariant})$$

#### Record Conservation Law:
$$\text{Processed Records (15)} = \text{Retained Records (10)} + \text{Rejected Records (3)} + \text{Duplicate Records (2)}$$
$$15 = 10 + 3 + 2 \quad (\text{Verified } 100\% \text{ Invariant})$$

### 10.3 Rejection Breakdown (Terminal States Audited)
- `DUPLICATE`: 2 records (1 exact document duplicate, 1 normalized record duplicate)
- `GOVERNANCE_BLOCKED`: 1 document (unapproved source `gated_doc_001`)
- `TOO_SHORT_CHARS`: 1 document (truncated input `short_doc_001` < 50 chars)
- `NO_ENGLISH_STOPWORDS`: 1 document (foreign French text `foreign_latin_doc_001`)

### 10.4 12 Auditable Pilot Checks Passed
1. **Provenance Lineage**: 100% of records maintain exact source IDs, character offsets, and contributor lists.
2. **Checksum Recording**: Manifest records 64-character SHA-256 archive hashes.
3. **Normalization & Filtering**: Typographical smart quotes and em-dashes preserved in NFC.
4. **Conservation Invariants**: Both document and record conservation verified.
5. **Multi-Tier Deduplication**: Exact document and normalized record duplicates detected.
6. **Rejection Ledger**: Rejection reasons, metrics, and thresholds logged to `rejections.jsonl`.
7. **Deterministic Splitting**: Zero cross-split document or group leakage.
8. **Storage Round-Trip**: `CorpusReader` reads back 100% of published records.
9. **Rebuild Determinism**: Dual cryptographic fingerprints match bit-for-bit across builds.
10. **Failure Recovery**: Pipeline cleans all `.tmp` staging on exceptions; zero corrupt manifests.
11. **Related-Work Grouping**: Book chapters and excerpts assigned to the identical split.
12. **Preflight Storage Check**: Excessive disk allocation requests rejected before file creation.

---

## 11. Full Regression Test Suite Execution

The complete VEDA test suite was executed across all foundational, lexical, corpus, and governance layers:

```bash
pytest -v
```

### Detailed Test Execution Breakdown:
- `tests/test_char_tokenizer.py`: 16 passed
- `tests/test_character_knowledge.py`: 10 passed
- `tests/test_character_registry.py`: 9 passed
- `tests/test_corpus_adversarial.py`: 32 passed
- `tests/test_corpus_contract.py`: 14 passed
- `tests/test_corpus_filtering.py`: 12 passed
- `tests/test_corpus_governance_gate.py`: 10 passed
- `tests/test_corpus_governance_hardening.py`: 10 passed *(New in Phase 4.2.1)*
- `tests/test_corpus_normalization.py`: 10 passed
- `tests/test_corpus_pipeline.py`: 5 passed
- `tests/test_corpus_segmentation.py`: 4 passed
- `tests/test_corpus_split.py`: 4 passed
- `tests/test_data_contracts.py`: 14 passed
- `tests/test_golden_regression.py`: 8 passed
- `tests/test_lexicon.py`: 11 passed
- `tests/test_security_robustness.py`: 5 passed
- `tests/test_sqlite_storage.py`: 12 passed
- `tests/test_words.py`: 10 passed

### Test Suite Totals:
- **Total Tests Collected**: **196**
- **Passed**: **196 (100% Green)**
- **Failures / Errors**: **0**
- **Total Runtime**: **1.23 seconds**
- **Production Lexicon Database**: Bit-for-bit identical, verified via `PRAGMA integrity_check` (959,688 words, 1,049,403 POS records).

---

## 12. Final Certification Status & Gate Decision

In strict accordance with Phase 4.2.1 directives, the final certification status is:

```
========================================================================================
FINAL CERTIFICATION STATUS:
HARDENING PASSED — PRODUCTION DECISIONS STILL PENDING
========================================================================================
```

### Justification:
1. **Hardening Verified**: All identified defects (split-leakage, deduplication provenance loss, preflight disk checks, composition conflation, evidence gaps) have been fully resolved with verified unit tests and pilot integration.
2. **Gates Fail Closed**: The governance gate provably prevents any unapproved, stale, corrupted, or oversized source from being ingested through either the CLI or internal APIs.
3. **Strict Stop Condition Enforced**: Production ingestion remains explicitly unauthorized until the source portfolio, license evidence, composition, resource budget, near-duplicate evaluation, and training-split policy are explicitly approved.
4. **Zero Model Contamination**: No production dataset was downloaded. No pretraining or Transformer architecture development was initiated.

```
========================================================================================
END OF VEDA PHASE 4.2.1 AUDIT & CERTIFICATION REPORT
========================================================================================
```
