# VEDA Phase 4.2.2 Accuracy Audit, Evidence Repair & Regression Certification Report
## Authoritative Technical Audit of Source Governance, Evidence Checksums, Metrics & Reproducibility

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Authoritative Audit & Regression Certification Report: Phase 4.2.2
Document ID: VEDA-REPORT-AUDIT-v4.2.2
Date: 2026-10-15
Operating System: Windows 10 (10.0.26300 64-bit, 16 Logical Cores, 15.75 GB RAM)
Baseline Test Suite: 196 / 196 passing (Phase 4.2.1)
Final Certified Test Suite: 204 / 204 passing (Phase 4.2.2)
Final Certification Status: ACCURACY AUDIT PASSED — PRODUCTION INGESTION STILL BLOCKED
========================================================================================
```

---

## 1. Executive Summary & Audit Mandate

Phase 4.2.2 is an **evidence-integrity and accuracy audit phase** for Project VEDA ("From Knowledge to Intelligence"). Its strict mandate is to audit, detect, and correct factual inaccuracies, fabricated or unverified evidence, misleading metrics, unsupported accuracy claims, and inconsistencies in the Phase 4.2 and Phase 4.2.1 implementations and reports.

### Strict Scope & Policy Invariants
1. **Evidence-Integrity Mandate**: No new corpus features were introduced unless strictly necessary to correct a demonstrated defect.
2. **No Large-Scale Downloads**: No production datasets were downloaded; no bulk crawling was initiated.
3. **No Downstream Training**: No Transformer, neural pretraining, or production tokenizer training was initiated.
4. **Separation of Software Validation from Rights Clearance**: Passing an automated Python validator certifies only that the code and schema contracts are syntactically sound; it does **not** grant legal copyright clearance. Engineering review is explicitly distinguished from independent legal counsel.
5. **Fail-Closed Governance**: All candidate production sources with unacquired physical archives or unverified license evidence documents are downgraded from `VERIFIED_PERMITTED` to `REQUIRES_REVIEW` (with 2 permanently `EXCLUDED`). Currently, **zero** candidate production sources are authorized for production ingestion.

---

## 2. Test Suite Audit & Baseline Comparison

Every test in the VEDA test suite was executed directly against the local repository using `pytest`. No test passed by assertion or assumption.

### Baseline vs. Final Summary

| Test Milestone | Total Tests | Passed | Failed | Skipped | Execution Time | Scope / Components Tested |
|---|---|---|---|---|---|---|
| **Phase 4.2.1 Baseline** | 196 | 196 | 0 | 0 | 1.34s | Phases 1–3 Lexicon + Phase 4.2.1 Ingestion Gate |
| **Phase 4.2.2 Final** | **204** | **204** | **0** | **0** | **1.37s** | Hardened Schemas, Byte Verification, Language Audit |

### Certified Test Distribution Across Modules

```
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\karnik YOGA\OneDrive\Desktop\veda
collected 204 items

tests/test_character_foundation.py .........................             [ 12%]
tests/test_corpus_contracts.py ........................................  [ 31%]
tests/test_corpus_governance_hardening.py ..............                 [ 38%]
tests/test_corpus_language_audit.py ....                                 [ 40%]
tests/test_english_foundation.py ...........................             [ 53%]
tests/test_lexicon_storage.py ...................................        [ 70%]
tests/test_word_foundation.py .......................................... [ 91%]
tests/test_adversarial_audit.py ..................                       [100%]

============================= 204 passed in 1.37s =============================
```

### New Regression Tests Added in Phase 4.2.2 (8 Tests)

1. `test_schema_rejects_empty_file_sha256_for_nonempty_source`: Verifies that `CorpusSource` raises `ValueError` if an empty-file SHA-256 placeholder (`e3b0c442...`) is provided when `expected_size_mb > 0`.
2. `test_schema_verify_artifact_bytes_against_physical_file`: Confirms that `verify_artifact_bytes()` validates real physical file bytes and detects bit-level discrepancies.
3. `test_source_governance_rejects_not_verified_hashes_for_permitted`: Confirms that `validate_source_governance()` and `assert_permitted_admissible()` fail-closed when `artifact_sha256` or `license_evidence_sha256` is `"NOT_VERIFIED"`.
4. `test_preflight_budget_check_fails_if_host_reserve_violated`: Verifies that `verify_host_reserve_margin()` halts with `ResourceBudgetExceededError` if available disk space violates the 40% host reserve floor (135.65 GB).
5. `test_adversarial_language_evaluation_suite`: Evaluates the QualityFilter on the complete 14-sample adversarial language benchmark.
6. `test_language_filter_adversarial_german_cognate_limitation`: Validates the empirical finding that German text containing shared cognates (*"in"*, *"so"*) bypasses stopword heuristics, documenting the heuristic boundary.
7. `test_language_filter_adversarial_cyrillic_rejection`: Proves that non-Latin scripts (Cyrillic) are deterministically rejected by the script ratio filter.
8. `test_language_filter_adversarial_scientific_prose_preservation`: Ensures dense technical English lacking common conversational stopwords is preserved without false rejection.

---

## 3. Classified Findings by Severity

The audit identified 9 concrete findings across the repository, categorized strictly by severity:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AUDIT FINDINGS CLASSIFICATION                   │
├──────────┬───────┬─────────────────────────────────────────────────────┤
│ Severity │ Count │ Primary Areas                                       │
├──────────┼───────┼─────────────────────────────────────────────────────┤
│ CRITICAL │   3   │ Fabricated Hashes, License Checksums, Fake Permits  │
│ HIGH     │   3   │ Composition Conflation, Benchmark Drift, Budget Sync│
│ MEDIUM   │   2   │ Language Filter Overclaim, Static Preflight Risk    │
│ LOW      │   1   │ Pilot Checksum Procedure Ambiguity                  │
└──────────┴───────┴─────────────────────────────────────────────────────┘
```

### Critical Severity Findings
- **Finding 1 (Fabricated & Empty SHA-256 Hashes)**: In `data/corpus/source_registry.json`, `source_hash` fields contained sequential dummy hex strings (`a1a2a3a4...`) and an empty-file SHA-256 digest (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`) assigned to Standard Ebooks (a 450 MB archive).
  - *Correction*: Defined explicit `EMPTY_FILE_SHA256` constant and rejection validator. Replaced all unacquired hashes with `"NOT_VERIFIED"`. Computed real physical byte digests for pilot documents.
- **Finding 2 (String Checksums Substituted for License Artifacts)**: In `data/corpus/source_registry.json`, `evidence_checksum` was derived by hashing literal license title and URL strings (e.g. `sha256("https://creativecommons.org/licenses/by/4.0/")`), fabricating a checksum without acquiring actual legal evidence documents.
  - *Correction*: Separated fields into `license_evidence_sha256` and `artifact_sha256`. Replaced string hashes with `"NOT_VERIFIED"` until authentic legal evidence documents are acquired.
- **Finding 3 (Premature `VERIFIED_PERMITTED` Approvals)**: Six candidate sources were marked `VERIFIED_PERMITTED` despite lacking acquired physical artifacts, checksum verifications, and formal legal clearance.
  - *Correction*: Downgraded all 12 candidate sources to `REQUIRES_REVIEW` (2 permanently `EXCLUDED`). Established fail-closed gate: `0` candidate sources currently permitted.

### High Severity Findings
- **Finding 4 (Conflation of Target Allocations with Actual Composition)**: `docs/training_corpus_composition.md` reallocated target shares (35:25:15 to 46.7:33.3:20.0) following the exclusion of Wikipedia, but presented these numbers in reports as if they proved actual corpus composition.
  - *Correction*: Formally split corpus composition into 5 distinct architectural levels. Labeled production levels 4 and 5 as `NOT YET MEASURED`. Documented exact denominators for all figures.
- **Finding 5 (Near-Duplicate Benchmark Discrepancy & Overclaim)**: The Phase 4.2.1 report claimed a 10-pair benchmark (4 positive, 6 negative), but the underlying code only contained a 5-pair synthetic smoke test. Furthermore, 100% precision/recall was claimed without statistical uncertainty bounds.
  - *Correction*: Constructed a true 10-pair held-out evaluation fixture (`build_eval_labeled_test_set`) and separate 6-pair dev set. Calculated Wilson score 95% confidence intervals ([0.5655, 1.0000]). Labeled the benchmark as a developmental smoke test and clarified that MinHash/LSH is candidate retrieval, not semantic equivalence.
- **Finding 6 (Downstream Training Artifact Misalignment & Reserve Omission)**: The resource budget table listed future training artifacts at 15.0 GB while code schemas specified 25.0 GB. Furthermore, the 40% host safety margin (135.65 GB) was asserted in documentation but lacked an programmatic unit test.
  - *Correction*: Aligned code and documentation to 25.0 GB (explicitly marked deferred to Phase 7, non-concurrent). Added `verify_host_reserve_margin()` and automated unit test.

### Medium Severity Findings
- **Finding 7 (Language Filter False Positives & Heuristic Overclaim)**: Previous documentation implied English stopwords and Latin script ratios were sufficient to verify English text.
  - *Correction*: Evaluated a 14-sample adversarial fixture in `foundation/corpus/language_audit.py`. Proved empirically that German text sharing cognates (*"in"*, *"so"*) bypasses stopword checks (FP=1), and short signs (<8 words) bypass stopword counts (FP=1). Established quarantine routing policy for ambiguous cases.
- **Finding 8 (Static Preflight Disk Limits & Rollback Overhead)**: The preflight disk check runs once at job start. Concurrent host background processes or Windows updates could invalidate disk headroom during a 10-hour ingestion run. Furthermore, atomic `.tmp` staging requires coexisting temporary and permanent splits during publishing.
  - *Correction*: Documented static vs dynamic limitations, allocated 10.0 GB rollback staging headroom, and enforced dynamic reservation checks.

### Low Severity Finding
- **Finding 9 (Pilot Hash Procedure Ambiguity)**: Documentation was ambiguous regarding whether pilot source hashes identified individual downloaded files or concatenated text buffers.
  - *Correction*: Documented that pilot source hashes represent the SHA-256 of the concatenated raw UTF-8 document text within the pilot fixture, verified down to the exact byte.

---

## 4. Inaccurate Claims & Explicit Corrections

A repository-wide search was conducted for common overclaims and unsupported statements. The table below lists each claim, its audited reality, and its corrected status:

| Claim Audited | Original Statement | Audit Finding / Reality | Corrected Formulation |
|---|---|---|---|
| **"100% accuracy"** | MinHash LSH achieves 100% precision & recall. | Evaluated on only 5–10 synthetic pairs. Wilson 95% CI is [0.5655, 1.0000]. | Developmental smoke test on 10 pairs; statistical lower bound is 56.6%; production accuracy unmeasured. |
| **"VERIFIED PERMITTED"** | 6 production sources are verified permitted. | Sources had dummy hashes and unacquired evidence. Software schema was valid, not legal rights. | 0 sources verified permitted; 12 downgraded to REQUIRES REVIEW; 2 EXCLUDED. |
| **"all defects resolved"** | All Phase 4.2 governance defects resolved. | Software architecture hardened, but external legal clearance and physical acquisition remain pending. | Ingestion gate mechanisms certified; external rights verification pending. |
| **"zero leakage"** | Complete zero leakage across splits. | Zero leakage guaranteed at document/group level via deterministic hash seed. Cross-doc near-duplicates across splits require pre-split MinHash index. | Document-level and group-level leakage zero by construction; cross-document near-duplicate indexing scoped. |
| **"production ready"** | Corpus pipeline is production ready. | Pipeline software is ready, but candidate sources are blocked. Ingestion cannot start. | Architecture certified; production ingestion strictly gated and blocked. |
| **"all sources verified"** | All registered sources verified. | Source metadata registered, but physical bytes and license documents unacquired. | Registry entries cataloged; physical bytes and legal evidence marked NOT_VERIFIED. |
| **"bit-for-bit identical"** | Pilot output is bit-for-bit identical. | True for tested pilot inputs (Content Fingerprint `eab5d387...`), but proves repeatability, not source authenticity or legal permission. | Deterministic repeatability verified for tested pilot inputs; does not certify upstream authenticity. |
| **"complete provenance"** | Complete provenance established. | Pipeline tracks `source_id`, `document_id`, and offsets. Upstream creator lineage requires external audit. | In-pipeline lineage tracked; external author provenance dependent on source release metadata. |
| **"peak storage 110 GB"** | 110 GB fits 120 GB envelope. | Arithmetically correct, but training artifacts were misaligned (15 GB vs 25 GB) and rollback staging was unmodeled. | 110 GB active concurrent ingestion footprint verified; 25 GB training artifacts deferred to Phase 7. |
| **"precision and recall"** | Deduplication precision = 1.0, recall = 1.0. | Measured on toy benchmark. Insufficient sample size for production inference. | Toy smoke-test metrics reported with Wilson 95% confidence intervals and sample size caveats. |

---

## 5. Source Hash Audit Table (All 14 Registered Sources)

Every registered source in `data/corpus/source_registry.json` was audited for physical existence, byte identity, and hash provenance:

| # | `source_id` | Declared `artifact_sha256` | Declared `license_evidence_sha256` | Physical File on Disk? | Expected Archive Size | Provenance / Release | Integrity Determination |
|---|---|---|---|---|---|---|---|
| 1 | `standard_ebooks` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 450 MB | Standard Ebooks v2026.1 git | `NOT_VERIFIED` (Unacquired) |
| 2 | `project_gutenberg` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 25,000 MB | aleph.gutenberg.org 2026.09 | `NOT_VERIFIED` (Unacquired) |
| 3 | `openstax_textbooks` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 1,800 MB | OpenStax CNX 2025.2 tarball | `NOT_VERIFIED` (Unacquired) |
| 4 | `python_docs` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 120 MB | Python 3.12.7 doc release | `NOT_VERIFIED` (Unacquired) |
| 5 | `wikinews_en` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 45 MB | Wikimedia 2026-09 dump | `NOT_VERIFIED` (Unacquired) |
| 6 | `plos_open_access` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 12,000 MB | PLOS Open Access 2025 XML | `NOT_VERIFIED` (Unacquired) |
| 7 | `simple_wikipedia` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 280 MB | Wikimedia 2026-09 dump | `NOT_VERIFIED` (Unacquired) |
| 8 | `wikipedia_en` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 22,000 MB | Wikimedia 2026-09 dump | `NOT_VERIFIED` (Unacquired) |
| 9 | `wikibooks_en` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 350 MB | Wikimedia 2026-09 dump | `NOT_VERIFIED` (Unacquired) |
| 10 | `openassistant_oasst2` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 150 MB | LAION OASST2 v2.0 JSONL | `NOT_VERIFIED` (Unacquired) |
| 11 | `internet_archive_open_library`| `NOT_VERIFIED` | `NOT_VERIFIED` | No (Production) | 8,000 MB | Open Library public dumps | `NOT_VERIFIED` (Unacquired) |
| 12 | `ubuntu_dialogue_corpus` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Excluded) | 1,200 MB | Ubuntu Community IRC logs | `EXCLUDED` (Unclear Rights) |
| 13 | `common_crawl_unfiltered` | `NOT_VERIFIED` | `NOT_VERIFIED` | No (Excluded) | 500,000 MB | Common Crawl WET dumps | `EXCLUDED` (Copyright Risk) |
| 14 | `wiktionary_lexicon_reference`| `NOT_VERIFIED` | `NOT_VERIFIED` | No (Isolated) | 2,240 MB | Wiktextract (Phase 3 Lexicon) | `NOT_VERIFIED` (Prose Gated)|

### Controlled Pilot Source Hashes (`data/corpus/pilot/pilot_sources.json`)

Unlike production candidates, the controlled pilot sources operate on real, acquired text records:

| Pilot `source_id` | Verified `artifact_sha256` (Physical UTF-8 Bytes) | Status | Verification Method |
|---|---|---|---|
| `standard_ebooks_pilot` | `42e3fbb30aa1871137e24a195cf79d95da036a5a35283b8b766db47977388247` | `PASS` | `hashlib.sha256(raw_text_bytes)` |
| `python_docs_pilot` | `7b5a758482deb5457ed580f9a18f48b233d637a6dd3327e890120dfeedc753e0` | `PASS` | `hashlib.sha256(raw_text_bytes)` |
| `unapproved_gated_source` | Synthetic non-matching digest | `PASS` | Deterministically rejected by gate |

---

## 6. Independent Rights-Validation Dimension Table (14 Sources x 8 Dimensions)

To eliminate the conflation of software validity with legal authorization, each source was evaluated across 8 independent dimensions. 

> [!IMPORTANT]
> **Legal Notice**: This evaluation constitutes an **engineering governance review** of technical metadata and license terms. It does **not** constitute independent legal counsel or formal copyright warranty.

### Evaluation Criteria
- **Dim 1**: Registry / Schema Validity (Syntactic compliance with `CorpusSource` schema)
- **Dim 2**: Artifact Integrity (Physical archive exists on disk and matches authentic SHA-256)
- **Dim 3**: License Evidence Availability (Authentic legal text archived on disk and hashed)
- **Dim 4**: Work-Level Eligibility Review (Audit of individual works within archive for copyright expiration)
- **Dim 5**: Training-Use Decision (Affirmative determination that pretraining on source is permissible)
- **Dim 6**: Raw-Corpus Redistribution Decision (Permission to distribute raw/normalized text in corpus release)
- **Dim 7**: Model-Distribution Risk Decision (Risk that trained model weights could face copyleft/infringement claims)
- **Dim 8**: Content-Quality Approval (High syntactic density, low OCR noise, editorial value)

### Classification Matrix

| `source_id` | Dim 1 (Schema) | Dim 2 (Artifact) | Dim 3 (Evidence) | Dim 4 (Work-Level) | Dim 5 (Training) | Dim 6 (Redist.) | Dim 7 (Model Risk) | Dim 8 (Quality) | Final Governance State |
|---|---|---|---|---|---|---|---|---|---|
| `standard_ebooks` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (CC0) | PASS (Low) | PASS | **REQUIRES REVIEW** |
| `project_gutenberg` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (US PD)| PASS (Low) | PASS | **REQUIRES REVIEW** |
| `openstax_textbooks` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (CC-BY)| PASS (Low) | PASS | **REQUIRES REVIEW** |
| `python_docs` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (PSFL) | PASS (Low) | PASS | **REQUIRES REVIEW** |
| `wikinews_en` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (CC-BY)| PASS (Low) | NOT_VERIFIED | **REQUIRES REVIEW** |
| `plos_open_access` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (CC-BY)| PASS (Low) | PASS | **REQUIRES REVIEW** |
| `simple_wikipedia` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL (CC-SA)| FAIL (SA Risk)| NOT_VERIFIED | **REQUIRES REVIEW** |
| `wikipedia_en` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL (CC-SA)| FAIL (SA Risk)| NOT_VERIFIED | **REQUIRES REVIEW** |
| `wikibooks_en` | PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL (CC-SA)| FAIL (SA Risk)| NOT_VERIFIED | **REQUIRES REVIEW** |
| `openassistant_oasst2`| PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PASS (Apache)| PASS (Low) | NOT_VERIFIED | **REQUIRES REVIEW** |
| `internet_archive_open_library`| PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL (Mixed)| FAIL (High) | NOT_VERIFIED | **REQUIRES REVIEW** |
| `ubuntu_dialogue_corpus` | PASS | N/A | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | **EXCLUDED** |
| `common_crawl_unfiltered` | PASS | N/A | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | **EXCLUDED** |
| `wiktionary_lexicon_reference`| PASS | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | FAIL (CC-SA)| FAIL (SA Risk)| PASS (Lexicon) | **REQUIRES REVIEW** |

---

## 7. Near-Duplicate Benchmark Reproduction & Calibration

The MinHash LSH implementation in `foundation/corpus/near_deduplication.py` was executed directly against a calibrated 10-pair held-out evaluation fixture (`build_eval_labeled_test_set`) and profiled across multiple text lengths.

### Pair Definition & Label Criteria
- **Positive Pair (`is_true_duplicate = True`)**: Represents substantial text duplication (>80% shared n-gram content), including bit-for-bit identity, whitespace/punctuation reformattings, single synonym edits, paragraph reorderings, and OCR character corruption.
- **Negative Pair (`is_true_duplicate = False`)**: Represents texts that are **not** duplicates, including shared domain vocabulary (physics vs biology), semantic inversions (negated engineering claims), shared publisher copyright boilerplate, identical configuration key templates, and distant literature prose.

### Reproduced Evaluation Results (Held-Out Benchmark, $N=10$)

```
Threshold: 0.80 Jaccard Similarity (128 MinHash Permutations, 16 Bands x 8 Rows)
True Positives (TP):  5
False Positives (FP): 0
True Negatives (TN):  5
False Negatives (FN): 0

Precision:   1.0000  (Wilson 95% Confidence Interval: [0.5655, 1.0000])
Recall:      1.0000  (Wilson 95% Confidence Interval: [0.5655, 1.0000])
Specificity: 1.0000  (Wilson 95% Confidence Interval: [0.5655, 1.0000])
F1 Score:    1.0000
Accuracy:    1.0000
```

### Detailed Confusion Matrix & Pair Evaluations

| Pair ID | True Label | Pred. Label | True Jaccard | MinHash Est. | Category / Description | Error Class |
|---|---|---|---|---|---|---|
| `eval_exact_001` | Duplicate | Duplicate | 1.0000 | 1.0000 | Bit-for-bit identical text | TP |
| `eval_near_ws_002` | Duplicate | Duplicate | 0.9761 | 0.9766 | Punctuation and double spacing | TP |
| `eval_near_syn_003` | Duplicate | Duplicate | 0.9571 | 0.9531 | Light synonym edit ('demonstrates' $\to$ 'proves') | TP |
| `eval_reordered_004` | Duplicate | Duplicate | 0.9761 | 0.9922 | Sentence reordering | TP |
| `eval_ocr_005` | Duplicate | Duplicate | 0.9573 | 0.9766 | Synthetic OCR character noise | TP |
| `eval_hard_neg_domain_006` | Non-Dup | Non-Dup | 0.5816 | 0.5938 | Shared domain terminology (Optics vs Bio) | TN |
| `eval_hard_neg_inversion_007` | Non-Dup | Non-Dup | 0.5225 | 0.4844 | Semantic inversion (Negated claim) | TN |
| `eval_hard_neg_boilerplate_008`| Non-Dup | Non-Dup | 0.2871 | 0.2969 | Identical copyright boilerplate tail | TN |
| `eval_hard_neg_params_009` | Non-Dup | Non-Dup | 0.4959 | 0.4531 | Identical configuration parameter template | TN |
| `eval_distant_neg_010` | Non-Dup | Non-Dup | 0.0149 | 0.0000 | Frankenstein literature vs Technical prose | TN |

### Statistical Limitations & Smoke-Test Disclosure
> [!CAUTION]
> **Sample Size & Retrieval Caveat**:
> 1. **Sample Size Constraint**: With $N=10$, the Wilson 95% confidence interval for precision and recall spans from **56.6% to 100.0%**. This evaluation confirms algorithmic functionality; it does **not** prove production accuracy across millions of documents.
> 2. **Candidate Retrieval Boundary**: MinHash LSH is strictly a **fast candidate retrieval heuristic**. It detects surface n-gram overlap. It does **not** determine semantic equivalence, intellectual property rights, fair use, or legal derivation.

### Runtime Throughput Benchmark

Benchmark executed on Windows 10 (16 logical cores) with 5 warm-up iterations and 30 timed iterations per length:

| Text Length | Shingle Size ($k$) | Mean Latency (ms) | Std Dev (ms) | Min Latency (ms) | Max Latency (ms) | Throughput (chars/sec) |
|---|---|---|---|---|---|---|
| **100 chars** | 5 | 1.453 ms | 0.100 ms | 1.403 ms | 1.826 ms | 68,828 chars/s |
| **500 chars** | 5 | 3.759 ms | 0.122 ms | 3.600 ms | 3.981 ms | 133,018 chars/s |
| **2,000 chars** | 5 | 3.936 ms | 0.555 ms | 3.704 ms | 6.673 ms | 508,080 chars/s |
| **5,000 chars** | 5 | 4.052 ms | 0.151 ms | 3.903 ms | 4.496 ms | 1,233,963 chars/s |

---

## 8. Corpus Composition Arithmetic & Denominators

To eliminate confusion between policy targets and empirical measurements, corpus composition is partitioned into **5 distinct architectural levels**:

```
LEVEL 1: Desired Target Allocation (Policy Target)
   │
   ▼
LEVEL 2: Eligible Target Reallocation (Exclusion Formula)
   │
   ▼
LEVEL 3: Measured Pilot Ingestion (Empirical Small Test)
   │
   ▼
LEVEL 4: Retained Production Corpus [NOT YET MEASURED]
   │
   ▼
LEVEL 5: Training-Token Exposure [NOT YET MEASURED]
```

### Composition Level Definitions & Mathematical Proofs

| Level | Name | Description | Denominator | Status |
|---|---|---|---|---|
| **Level 1** | Desired Target Allocation | Policy target balancing 5 domains | $100\%$ target pretraining tokens | Ratified Policy |
| **Level 2** | Eligible Target Reallocation | Proportional formula after blocking Gated sources | $\sum_{i \in \text{Eligible}} w_i = 75\%$ target tokens | Mathematical Model |
| **Level 3** | Measured Pilot Composition | Retained records in controlled pilot | $15$ retained split records | Empirically Measured |
| **Level 4** | Retained Production Corpus | Actual filtered records from production archives | Total retained production tokens | **NOT YET MEASURED** |
| **Level 5** | Training-Token Exposure | Tokens sampled during neural training epochs | Total pretraining training steps | **NOT YET MEASURED** |

### Level 1 vs. Level 2 Arithmetic

When Wikipedia / Encyclopedic prose is gated pending ShareAlike legal review, the remaining 75% target allocation is proportionally normalized across eligible domains:

$$\hat{w}_i = \frac{w_i}{\sum_{j \in \text{Eligible}} w_j} = \frac{w_i}{0.75}$$

- **Literature (Standard Ebooks / Gutenberg)**: $\frac{0.35}{0.75} = 46.666\dots\% \approx \mathbf{46.7\%}$
- **Educational (OpenStax Textbooks)**: $\frac{0.25}{0.75} = 33.333\dots\% \approx \mathbf{33.3\%}$
- **Technical & Scientific (Python Docs / PLOS)**: $\frac{0.15}{0.75} = 20.000\dots\% \approx \mathbf{20.0\%}$
- **Total Eligible Allocation**: $46.667\% + 33.333\% + 20.000\% = \mathbf{100.0\%}$

> [!NOTE]
> **Arithmetic Invariant**: Level 2 represents an adjusted target model for ingestion budgeting. It does **not** assert that the production corpus currently possesses this distribution.

### Level 3 Empirical Pilot Measurement (Actual Pilot Ingestion)

In the controlled pilot run (`scripts/run_corpus_pilot.py`), 9 documents were ingested, producing 15 retained records:

| Pilot Source | Domain | Documents Ingested | Segments Produced | Retained Split Records | Record Share (%) | Character Share (%) |
|---|---|---|---|---|---|---|
| `standard_ebooks_pilot` | Literature | 4 documents | 7 segments | 7 records | $46.67\%$ | $49.12\%$ |
| `python_docs_pilot` | Technical | 4 documents | 8 segments | 8 records | $53.33\%$ | $50.88\%$ |
| `unapproved_gated_source` | Gated | 1 document | 0 (Blocked) | 0 records | $0.00\%$ | $0.00\%$ |
| **PILOT TOTAL** | — | **9 documents** | **15 segments** | **15 records** | **100.00%** | **100.00%** |

---

## 9. Language and Quality-Filter Adversarial Evaluation

The heuristic QualityFilter in `foundation/corpus/filtering.py` was subjected to an adversarial benchmark of 14 complex edge cases in `foundation/corpus/language_audit.py`.

### Empirical Results Summary ($N=14$)
- **True Positives (TP)**: 7 (Valid scientific prose, code documentation, safety notices, quotes)
- **True Negatives (TN)**: 5 (Raw Python code, French text, Cyrillic text, chemistry formulas)
- **False Positives (FP)**: 2 (German cognate prose, short industrial safety signs)
- **False Negatives (FN)**: 0 (No valid English text was discarded)
- **Accuracy**: $85.71\%$
- **Precision**: $77.78\%$
- **Recall**: $100.00\%$

### Adversarial Case Breakdown

| Sample ID | Category | Text Snippet | Filter Decision | Rejection Reason | Correct? | Error Analysis |
|---|---|---|---|---|---|---|
| `lang_sci_001` | Scientific Low-Stopword | *"Barium chlorate decomposes..."* | ACCEPTED | None | Yes (TP) | High technical density preserved |
| `lang_formula_002` | Headings/Formulas | *"pH = pKa + log10([A-]/[HA])..."* | REJECTED | `LOW_ALPHA_RATIO` | Yes (TN) | Formula symbols filtered |
| `lang_caption_003` | Tables/Captions | *"Table 4.1: Empirical density..."* | ACCEPTED | None | Yes (TP) | Informative caption retained |
| `lang_short_004` | Short Text | *"Caution: High voltage. Authorized..."*| ACCEPTED | None | **No (FP)** | Short text (<8 words) bypasses stopword count |
| `lang_safety_005` | Short Technical | *"Warning: Do not operate machinery..."*| ACCEPTED | None | Yes (TP) | Complete imperative sentence |
| `lang_french_006` | Foreign Latin | *"Le développement de modèles..."* | REJECTED | `NO_ENGLISH_STOPWORDS`| Yes (TN) | French text correctly blocked |
| `lang_french_a_007` | Foreign Latin | *"C'est une belle journée à Paris..."* | REJECTED | `NO_ENGLISH_STOPWORDS`| Yes (TN) | Single loanword 'a' insufficient |
| `lang_german_008` | Foreign Latin | *"Das ist in der Tat so ein großes..."* | ACCEPTED | None | **No (FP)** | Shared cognates (*in*, *so*) triggered false acceptance |
| `lang_quote_009` | Foreign Quotes | *"The philosopher declared 'cogito'..."*| ACCEPTED | None | Yes (TP) | English sentence with quote |
| `lang_names_010` | Foreign Names | *"François and Søren collaborated..."*| ACCEPTED | None | Yes (TP) | Preserves diacritics in English |
| `lang_code_011` | Raw Code | `def compute_loss(y_true, y_pred):` | REJECTED | `LOW_ALPHA_RATIO` | Yes (TN) | Code punctuation rejected |
| `lang_doc_012` | Code Documentation | *"This function computes cross-entropy..."*| ACCEPTED | None | Yes (TP) | Explanatory docstring retained |
| `lang_grammar_013` | Mixed Language | *"In Latin, 'amare' means to love..."*| ACCEPTED | None | Yes (TP) | Linguistic pedagogy retained |
| `lang_cyrillic_014` | Non-Latin Script | *"Это пример текста на русском..."* | REJECTED | `NON_ENGLISH_SCRIPT` | Yes (TN) | Cyrillic script ratio = 1.0 |

### Operating Boundaries & Quarantine Architecture
1. **Stopwords $\neq$ Proof of English**: The German cognate test proved that foreign languages sharing small functional words (*in*, *so*, *on*, *me*) can satisfy minimal stopword thresholds. Stopwords indicate grammatical structure, not definitive language classification.
2. **Short Text Window**: Texts under 8 words bypass stopword counting to avoid discarding headings and titles. This creates a minor vulnerability where short non-English signs can pass.
3. **Quarantine Routing Policy**: Ambiguous texts (e.g. Latin script ratio $\ge 0.85$ but stopword count $\in \{1, 2\}$) should be routed to a quarantine stream (`quarantine.jsonl`) for second-stage fastText or n-gram language identification rather than being unconditionally published to pretraining splits.

---

## 10. Resource-Budget Verification & Safety Reserve

The physical system specifications were verified directly on the host machine:

### Host Hardware & Storage Audit

| Resource | Measured Host Capacity | Ingestion Budget | Allocation Rule |
|---|---|---|---|
| **Host SSD Storage** | **951.65 GB** | **120.0 GB Max** | Maximum allowable active ingestion footprint |
| **Free SSD Space** | **339.13 GB** | **135.65 GB Reserve**| Enforced 40% safety margin for host OS & virtual memory |
| **Host Physical RAM** | **15.75 GB** | **1.5 GB Max RSS** | Streaming generator pipeline ($O(1)$ memory buffer) |
| **Available RAM** | **3.53 GB** | **>2.0 GB Headroom**| Guard against out-of-memory thrashing |

### Peak Concurrent Ingestion Components (110.0 GB Total)

```
┌────────────────────────────────────────────────────────────────────────┐
│             PEAK CONCURRENT STORAGE BREAKDOWN (110.0 GB)               │
├──────────────────────────────────────┬─────────────┬───────────────────┤
│ Component                            │ Footprint   │ Lifecycle         │
├──────────────────────────────────────┼─────────────┼───────────────────┤
│ 1. Downloaded Source Archives        │ 25.0 GB     │ Ephemeral         │
│ 2. Extracted Source Files            │ 35.0 GB     │ Ephemeral         │
│ 3. Temporary Staging (.tmp splits)   │ 15.0 GB     │ Commit Window     │
│ 4. Normalized Production Splits      │ 15.0 GB     │ Retained Corpus   │
│ 5. Deduplication Indexes (MinHash)   │  4.5 GB     │ Intermediate      │
│ 6. SQLite Database Artifacts         │  5.0 GB     │ Certified Lexicon │
│ 7. Manifests & Rejection Logs        │  0.5 GB     │ Permanent Audit   │
│ 8. Backups & Rollback Headroom       │ 10.0 GB     │ Recovery Reserve  │
├──────────────────────────────────────┼─────────────┼───────────────────┤
│ TOTAL PEAK CONCURRENT INGESTION      │ 110.0 GB    │ Fits in 120 GB Cap│
├──────────────────────────────────────┼─────────────┼───────────────────┤
│ Downstream Training Artifacts        │ 25.0 GB     │ Deferred Phase 7  │
└──────────────────────────────────────┴─────────────┴───────────────────┘
```

### Reserve Protection & Preflight Limitations
- **Host Reserve Check**: Enforced by `verify_host_reserve_margin()`. Ensures that `free_space - job_bytes >= 135.65 GB`.
- **Static vs. Dynamic Monitoring**: `PreflightStorageChecker` inspects disk space at job start. In a production multi-hour ingestion job, an active background file watcher must poll disk space periodically to prevent external processes from exhausting the safety margin during extraction.
- **Rollback Staging**: The 10.0 GB rollback headroom accounts for the temporary coexistence of `.tmp` staging splits alongside existing production splits during atomic rename operations.

---

## 11. Controlled Pilot Reproducibility & Lexicon Verification

The controlled ingestion pilot was executed and validated for deterministic reproducibility.

### Pilot Cryptographic Signatures

```
================================================================================
PILOT CRYPTOGRAPHIC IDENTITY:
Content Fingerprint:  eab5d3870d09131ed0769c94047bd8bdaedf84e0c3268f551dafaa627bc86028
Manifest Fingerprint: f607062e552bc96e6ed5e841c116eaddc62a014ff3a972f907273622c10be65e
================================================================================
```

1. **Content Fingerprint (`eab5d387...`)**: 100% bit-for-bit identical across multiple repeated runs. Confirms that text normalizer, segmenter, deduplication engine, and split allocator execute deterministically without floating-point or hash-seed drift.
2. **Manifest Fingerprint (`f607062e...`)**: Deterministically reflects the genuine SHA-256 digests of the input pilot source files (`42e3fbb3...` and `7b5a7584...`).
3. **Conservation Invariants**:
   - Total Documents Ingested: 9 (8 accepted, 1 blocked)
   - Documents Blocked by Governance: 1 (`unapproved_gated_source`)
   - Records Produced: 15
   - Exact Deduplication Rejections: 0 (distinct pilot segments)
   - Retained Split Records: 15 (Train: 13, Val: 1, Test: 1)
   - Cross-Split Document Leakage: 0

### Phase 1–3 Production Lexicon Integrity

The certified production SQLite lexicon database (`data/lexicon/veda_lexicon.db`) was audited to ensure zero regressions:
- Total Lexicon Words: **959,688**
- Part of Speech Records: **1,049,403**
- Sense Definitions: **1,322,676**
- Schema Constraints / Foreign Key Violations: **0**
- SQLite Integrity Status: `ok` (`PRAGMA integrity_check`)
- Database File SHA-256: `e73f5c64b716d114833d73bead71ee436ac2f132180a4d5b7c802a4d7eb4c343`

---

## 12. Remaining Unresolved Issues & External Dependencies

The following external issues remain unresolved and must be addressed prior to authorizing large-scale production ingestion:

1. **Physical Production Archive Acquisition**: None of the 12 candidate production archives have been downloaded. Authentic SHA-256 byte digests must be recorded from physical release files.
2. **License Evidence Document Archival**: Full legal texts (terms of service, CC-BY licenses, PSFL grant notices) must be retrieved, saved as physical documents, and hashed.
3. **ShareAlike Legal Review**: Wikimedia Foundation CC-BY-SA terms require formal review by qualified legal counsel to determine whether model pretraining creates a "Derivative Work" subject to copyleft redistribution.
4. **Project Gutenberg Header Stripping Benchmark**: Automated regex markers for stripping Project Gutenberg boilerplates (`*** START OF THE PROJECT GUTENBERG EBOOK ***`) must be benchmarked on a sample of at least 100 books to ensure zero disclaimer leakage into training data.
5. **Multi-Lingual Second-Stage Filter**: An n-gram or fastText language identifier should be integrated to resolve the German/Latin cognate false positive boundary identified in Section 9.

---

## 13. Exact Commands & Reproducible Evidence Log

All audit results can be independently reproduced using the following commands:

```powershell
# 1. Run Complete Test Suite (204 tests)
pytest tests/ -v

# 2. Verify Source Governance CLI (0 permitted, 12 review, 2 excluded)
python veda.py corpus sources

# 3. Reproduce Controlled Ingestion Pilot & Cryptographic Fingerprints
python scripts/run_corpus_pilot.py

# 4. Reproduce MinHash Near-Deduplication Benchmark & Latency Profiling
python -c "from foundation.corpus.near_deduplication import evaluate_near_duplicate_strategy, benchmark_near_dedup_runtime; import json; print(json.dumps(evaluate_near_duplicate_strategy(), indent=2)); print(json.dumps(benchmark_near_dedup_runtime(), indent=2))"

# 5. Reproduce Adversarial Language Filter Evaluation
python -c "from foundation.corpus.language_audit import evaluate_language_filter; import json; print(json.dumps(evaluate_language_filter(), indent=2))"

# 6. Verify Production Lexicon SQLite Database Integrity
python veda.py lexicon verify
```

---

## 14. Authoritative Certification Determination

```
========================================================================================
FINAL AUDIT STATUS:
ACCURACY AUDIT PASSED — PRODUCTION INGESTION STILL BLOCKED
========================================================================================
```

### Rationalization:
1. **Accuracy Audit Passed**: All fabricated hashes, misleading 100% accuracy claims, synthetic benchmark discrepancies, composition arithmetic conflations, language filter overclaims, and resource budget misalignments have been corrected and verified with 204 passing regression tests.
2. **Production Ingestion Still Blocked**: Because physical production source archives have not been acquired and external legal evidence documents remain unverified, all candidate production sources remain in `REQUIRES_REVIEW` (with 2 `EXCLUDED`). The ingestion gate functions fail-closed and strictly blocks production ingestion.
3. **Strict Stop Enforced**: No production datasets were downloaded; no model training was initiated.
