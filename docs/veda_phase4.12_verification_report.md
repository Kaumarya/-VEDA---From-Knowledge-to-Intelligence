# VEDA Phase 4.12 Verification Report
## Independent Corpus-Quality Validation, Benchmark Governance, and Certification Readiness

**Project:** VEDA — From Knowledge to Intelligence  
**Phase:** 4.12  
**Date:** 2026-10-17  
**Evaluation Scope:** English Language Filtering (`classify_with_quarantine`) & Near-Duplicate Detection (`NearDuplicateDetector.are_near_duplicates`)  
**Implementation Environments:** Python 3.14.8 (`.venv`) and Python 3.9.13 (System Global)  
**Governance & Independence Status:** **PROVISIONAL — INDEPENDENCE UNVERIFIED** (Gate E / Gate F)  
**Final Phase Status:** **PHASE 5 REMAINS PAUSED / AUTHORIZATION WITHHELD**

---

## 1. Executive Summary and Final Status

Phase 4.12 was executed to independently validate VEDA's corpus quality controls—specifically the English-language filter and the semantic safety-aware near-duplicate detection pipeline—prior to authorizing Phase 5 model development.

Per the requirements of the Phase 4.12 specification:
1. **Benchmark Authorship & Disclosure:** In the absence of an external third-party human reviewer, candidate benchmark v8.0 was constructed by the automated verification agent under strict written criteria. Because the benchmark was generated internally, it is formally designated **PROVISIONAL — INDEPENDENCE UNVERIFIED**. It is not claimed to be third-party independent.
2. **Strict Sealed Evaluation:** No model weights, thresholds, or code paths were tuned or altered against the v8.0 test split. The evaluation was run directly through the frozen production code paths.
3. **Dual-Runtime Validation:** Both the official evaluation script and the full 289-test regression suite executed across both supported runtimes: Python 3.14.8 and Python 3.9.13. Dual-runtime parity was 100%.
4. **Empirical Gate Findings:**
   - **Task A (Language Filter):** Evaluated at **93.33%** exact 3-class accuracy on the sealed test set ($N=60$), falling short of the proposed 95.0% Gate A threshold (**FAIL / BLOCKED**).
   - **Task B (Near-Deduplication Accuracy):** Evaluated at **95.00%** accuracy on the sealed test set ($N=20$), meeting the 95.0% Gate B threshold (**PASS**).
   - **Task C (False-Merge Control & Safety):** Observed **88.89%** precision on the test set with **1 safety-critical false merge** (`v8_dedup_test_018`, merging "showed evidence" with "showed no evidence" due to the omission of `"no"` from `neg_particles`), violating Gate C's requirement of 100% precision and zero safety merges (**FAIL / BLOCKED**).
   - **Gate D (Dual-Runtime Reproducibility):** **PASS** (100% test pass rate across 289 tests on both Python 3.14.8 and Python 3.9.13).
   - **Gate E (Third-Party Independence):** **UNVERIFIED** (internally authored provisional set).
   - **Gate F (Corpus Governance & Fail-Closed):** **PASS** (all 7 fail-closed gate tests passed under both runtimes).
5. **Phase Decision:** Because Gates A, C, and E are not satisfied, Phase 4.12 concludes with an explicit **BLOCK**. Ingestion remains fail-closed and **Phase 5 pretraining remains strictly PAUSED**.

---

## 2. Scope and Explicit Exclusions

### In-Scope
- Audit of existing baseline files, hashes, and git state.
- Construction and SHA-256 provenance registration of the provisional v8.0 benchmark (`eval_language_dataset_v8.json` and `eval_near_dedup_dataset_v8.json`).
- Automated leakage, contamination, and n-gram overlap audit against historical benchmarks (v3, v4, v5, v6, v7) and the regression test suite.
- Sealed evaluation through production code paths:
  - `foundation/corpus/language_audit.py::classify_with_quarantine`
  - `foundation/corpus/near_deduplication.py::NearDuplicateDetector.are_near_duplicates`
- Measurement of Wilson 95% score confidence intervals, per-class precision/recall/F1, and confusion matrices.
- Investigation and root-cause analysis of all classification and deduplication errors.
- Fail-closed security tests of the corpus production gate (`tests/test_corpus_production_gate_fail_closed.py`).
- Complete regression suite execution under Python 3.14.8 and Python 3.9.13.

### Explicit Exclusions
- **No Phase 5 Model Pretraining:** No transformer training or weight updates.
- **No Foundation Model Weights:** No downloading or importing of third-party foundation weights.
- **No Hosted LLM APIs:** No OpenAI, Anthropic, Gemini, or external API calls.
- **No Unauthorized Corpus Ingestion:** Corpus production gate remains locked; zero unapproved external text ingested.
- **No Result-Driven Benchmark Tuning:** Rules and thresholds were not adjusted to artificially force a 100% benchmark score on v8.

---

## 3. Baseline Repository Status and Artifact Hashes

### 3.1 Baseline Git State
- **HEAD Commit:** `14c29b420e421bf4ebffa441778d47db49ac74bd`
- **Branch:** `main` (tracked)
- **Pre-existing Modified Files:** `README.md`, `foundation/lexicon/storage.py`, `requirements.txt`, `veda.py` (preserved intact).

### 3.2 Baseline Artifact Hashes
Recorded in `data/corpus/phase4.12_baseline_manifest.json`:

| File / Component | SHA-256 Hash |
| :--- | :--- |
| `foundation/corpus/language_audit.py` | `6926c6bb18a343e3f7b93dee16434466a7aa4740953e4c7b3bf00702f7512524` |
| `foundation/corpus/filtering.py` | `a84d68b299cd793aef577a52de63230ff807fd909f25cca3b64b9327a6991aec` |
| `foundation/corpus/near_deduplication.py` | `9fffa9183d8f80f14ff338aa807dc7bf10288a829df0d5f1b0346e005a4db0b5` |
| `tests/test_near_deduplication_safety.py` | `53917fcd6121955ca1150513f18b9b0f73394ca623c011b7778a0f9dcfd58a70` |
| `tests/test_language_filter_hardening.py` | `2e8cadb2139a9ffdca97fb9dbe1e322ac60ca317ed772054d677b42a71397bae` |
| `tests/test_corpus_production_gate_fail_closed.py` | `3db43c71a425db0746f45739b80b8f0dbed7e5f9905fc583887ea7c17b43056f` |
| `data/corpus/eval_language_dataset_v7.json` | `99291f7c75370abe37b7d3e2e8c0d2d7977c38c18c458cadf958f3a79ecb1a4d` |
| `data/corpus/eval_near_dedup_dataset_v7.json` | `f44be30ccbd82af6e6ed93fdb175bdc3708c0204c26d0db69f4a6eb7f1ce1370` |

---

## 4. Benchmark Design, Authorship, and Access Governance

### 4.1 Authorship and Provenance Disclosure
- **Benchmark Name:** VEDA Provisional Certification Benchmark v8.0
- **Author/Builder:** Antigravity Automated Verification Agent
- **Construction Date:** 2026-10-17
- **Governance Classification:** **PROVISIONAL — INDEPENDENCE UNVERIFIED**
- **Access Control:** All candidate examples were compiled into frozen JSON artifacts before test execution. The implementation code was frozen at Stage Zero and was not tuned or modified following test execution.

### 4.2 Benchmark Datasets and Cryptographic Hashes

| Dataset Name | Split Count | SHA-256 Hash | File Path |
| :--- | :--- | :--- | :--- |
| `eval_language_dataset_v8.json` | Dev: 60, Test: 60 (Total: 120) | `020c81dc26ce49fde0f29c873e74cc5fe6f12a7dfcce34908341084e4b3108e8` | `data/corpus/eval_language_dataset_v8.json` |
| `eval_near_dedup_dataset_v8.json` | Dev: 20, Test: 20 (Total: 40) | `96fee87e5c4a2890bfab20398da96a8f7d2f63d0cedc707e6efe5521d323a467` | `data/corpus/eval_near_dedup_dataset_v8.json` |

---

## 5. Leakage and Contamination Audit

The audit script `scripts/audit_phase412_overlap.py` evaluated cross-contamination across:
1. Exact string matches against prior benchmarks (v3, v4, v5, v6, v7).
2. Punctuation-stripped normalized text matches against prior benchmarks.
3. Token Jaccard similarity ($\ge 0.80$) against prior benchmarks.
4. Dev vs. Test cross-split leakage.
5. Reversed pair duplicate matching.
6. Test suite literal collisions in `tests/`.

### 5.1 Audit Results Summary

```json
{
  "summary": {
    "task_a_exact_matches": 0,
    "task_a_normalized_matches": 0,
    "task_a_high_jaccard_matches": 0,
    "task_a_cross_split_matches": 0,
    "task_a_test_file_overlaps": 0,
    "task_b_exact_matches": 0,
    "task_b_normalized_matches": 0,
    "task_b_cross_split_matches": 0
  }
}
```

**Finding:** The v8.0 benchmark has **0% exact, normalized, or high-similarity overlap** with any previous benchmark version (v3 through v7), exhibits **zero cross-split contamination** between dev and test sets, and has zero collisions with the repository's test fixtures.

---

## 6. Stage Two — English-Language Filter Evaluation (Task A)

### 6.1 Dataset Taxonomy & Distribution
Each split of `eval_language_dataset_v8.json` ($N=60$) is balanced across the 15 required categories:
- **ACCEPT ($N=30$):**
  - Ordinary English prose ($N=10$)
  - Expository academic and scientific prose ($N=8$)
  - Scientific figure captions ($N=5$)
  - Foreign names, quotes, and Latin legal terminology ($N=4$)
  - English imperatives and concise instructions ($N=3$)
- **QUARANTINE ($N=20$):**
  - Code, SQL queries, and structured data ($N=5$)
  - Imperative industrial signage and advisory notices ($N=5$)
  - Short headings, appendices, and index fragments ($N=5$)
  - Germanic Latin-script natural prose (German & Dutch) ($N=5$)
- **REJECT ($N=10$):**
  - Romance Latin-script natural prose (French, Spanish, Italian) ($N=5$)
  - Non-Latin script prose (Russian Cyrillic, Chinese Hanzi) ($N=2$)
  - Malformed symbol noise, repetitive log dumps, and consonant garbage ($N=3$)

### 6.2 Quantitative Results

| Split | Total ($N$) | Correct | Accuracy | 95% Wilson CI | Macro-F1 | False Rej Rate | False Acc Rate | Quarantine Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Development** | 60 | 58 | 96.67% | $[0.8864, 0.9908]$ | 0.9522 | 0.00% | 0.00% | 30.00% |
| **Test (Sealed)** | 60 | 56 | **93.33%** | $[0.8407, 0.9738]$ | **0.9206** | **13.33%** | **0.00%** | **33.33%** |

### 6.3 Per-Class Performance (Test Split)

| Class | Ground Truth | Precision | Recall | F1-Score |
| :--- | :--- | :--- | :--- | :--- |
| **ACCEPT** | 30 | 1.0000 | 0.8667 | 0.9286 |
| **QUARANTINE** | 20 | 1.0000 | 1.0000 | 1.0000 |
| **REJECT** | 10 | 0.7143 | 1.0000 | 0.8333 |

### 6.4 Confusion Matrix (Test Split)

| Expected \ Predicted | ACCEPT | QUARANTINE | REJECT | Total |
| :--- | :---: | :---: | :---: | :---: |
| **ACCEPT** | 26 | 0 | 4 | 30 |
| **QUARANTINE** | 0 | 20 | 0 | 20 |
| **REJECT** | 0 | 0 | 10 | 10 |
| **Total Predicted** | 26 | 20 | 14 | 60 |

### 6.5 Failure Analysis for Language Filter
Four genuine English test samples were incorrectly rejected by the filter with `NO_ENGLISH_STOPWORDS`:

1. **`v8_lang_test_001` (Renewable Energy):**
   - *Text:* `"Offshore wind installations utilize heavy subsea power cables to transmit alternating current to mainland substations."`
   - *Expected:* `ACCEPT` | *Predicted:* `REJECT` (`NO_ENGLISH_STOPWORDS`)
   - *Root Cause:* The sentence contains 15 words. In `QualityFilter`, text with $\ge 15$ words invokes `min_stopwords_for_long_texts = 2`. The only stopword present is `"to"` (which appears twice). Because stopword counting evaluates the set cardinality (`set(clean_words)`), distinct stopword count is 1. Since $1 < 2$, the filter rejected fluent English prose.
2. **`v8_lang_test_002` (Agronomy):**
   - *Text:* `"Agricultural extension agents advised grain farmers to rotate legume crops to naturally replenish soil nitrogen reserves."`
   - *Expected:* `ACCEPT` | *Predicted:* `REJECT` (`NO_ENGLISH_STOPWORDS`)
   - *Root Cause:* 15 words; distinct stopword count = 1 (`"to"`). $1 < 2$.
3. **`v8_lang_test_015` (Proteomics):**
   - *Text:* `"Ubiquitin ligase cascades catalyze covalent substrate polyubiquitination and direct misfolded proteins toward twenty-six S proteasomal degradation."`
   - *Expected:* `ACCEPT` | *Predicted:* `REJECT` (`NO_ENGLISH_STOPWORDS`)
   - *Root Cause:* 16 words; distinct stopword count = 1 (`"and"`). `"toward"` is absent from `_COMMON_ENGLISH_STOPWORDS`. $1 < 2$.
4. **`v8_lang_test_017` (Anthropological Linguistics):**
   - *Text:* `"Anthropological linguistics explores how spatial cognitive reference frames vary systematically across unrelated indigenous language families."`
   - *Expected:* `ACCEPT` | *Predicted:* `REJECT` (`NO_ENGLISH_STOPWORDS`)
   - *Root Cause:* 15 words; distinct stopword count = 1 (`"how"`). `"across"` is absent from `_COMMON_ENGLISH_STOPWORDS`. $1 < 2$.

**Linguistic Finding:** Natural English scientific prose with technical compound nouns frequently uses only a single distinct preposition or conjunction across a 15-word sentence. The rigid threshold (`word_count >= 15` requiring $\ge 2$ distinct stopwords) introduces a 13.33% false rejection rate on technical English prose.

---

## 7. Stage Three — Near-Duplicate Detection Evaluation (Task B)

### 7.1 Dataset Structure & Intent
Each split of `eval_near_dedup_dataset_v8.json` ($N=20$) contains:
- **True Duplicates ($N=8$):**
  - Exact duplicates ($N=2$)
  - Reformatted/whitespace duplicates ($N=2$)
  - Voice and syntactic paraphrases ($N=2$)
  - Valid SI/IEC unit conversions ($N=4$, e.g. $8000\text{ mg} \leftrightarrow 8\text{ g}$, $180\text{ s} \leftrightarrow 3\text{ min}$, $400\text{ cm} \leftrightarrow 4.0\text{ m}$, $4096\text{ b} \leftrightarrow 4\text{ kib}$)
- **Non-Duplicates / Hard Safety Negatives ($N=12$):**
  - Distant topic negative ($N=1$)
  - Polarity inversion ($N=2$, e.g., expand vs reduce, safe vs dangerous/toxic)
  - Numerical dosage/magnitude mismatch ($N=2$, e.g., $0.004\text{ g}$ vs $0.040\text{ g}$, $0.015\ \Omega$ vs $0.150\ \Omega$)
  - Physical unit dimension conflict ($N=2$, e.g., $20.0\text{ bar}$ vs $20.0\text{ m}$, $60.0\text{ A}$ vs $60.0\text{ V}$)
  - Calendar date mismatch ($N=2$, e.g., 1869 vs 1875, February 18 vs September 18)
  - Negation particle inversion ($N=2$)
  - Alphanumeric entity identifier conflict ($N=1$, e.g., Turbine-X501 vs Turbine-Y501)

### 7.2 Quantitative Pipeline Results

| Split | Pairs ($N$) | Stage 2 (MinHash/Jaccard) Precision | Stage 3 (Guard) Precision | Final Accuracy | 95% Wilson CI | False Merges Prevented | Safety-Critical False Merges |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Development** | 20 | 42.11% | **100.00%** | **100.00%** | $[0.8389, 1.0000]$ | 11 | **0** |
| **Test (Sealed)** | 20 | 44.44% | **88.89%** | **95.00%** | $[0.7639, 0.9911]$ | 9 | **1** |

### 7.3 Stage-Specific Prevention Breakdown (Test Split)

- **Total Pairs Evaluated:** 20 (8 True Duplicates, 12 True Negatives)
- **Stage 2 Screening Candidates:** 18 pairs passed candidate threshold $\ge 0.75$.
  - True Duplicates Admitted: 8/8 (100% Stage 2 Recall)
  - False Duplicate Candidates Admitted: 10/12 (Distant negative correctly filtered out at Stage 2)
- **Stage 3 Safety Guard Actions:**
  - True Duplicates Permitted: 8/8
  - False Candidates Blocked by Safety Guard: **9 pairs prevented**
    - 2 Dosage inversions blocked (`NUMERICAL_DISCREPANCY`)
    - 2 Unit dimension mismatches blocked (`UNIT_MISMATCH`)
    - 2 Date mismatches blocked (`DATE_MISMATCH`)
    - 1 Polarity inversion blocked (`POLARITY_INVERSION`: expand vs reduce)
    - 1 Negation particle inversion blocked (`NEGATION_INVERSION`: can never vs can easily)
    - 1 Entity identifier mismatch blocked (`IDENTIFIER_MISMATCH`: Turbine-X501 vs Turbine-Y501)
  - False Candidates Permitted (Safety Violations): **1 pair**

### 7.4 Critical Safety Failure Analysis (`v8_dedup_test_018`)

- **Pair ID:** `v8_dedup_test_018`
- **Category:** `safety_negation_inversion`
- **Text A:** `"The secondary containment vessel showed evidence of structural stress fracture under sustained pneumatic pressure."`
- **Text B:** `"The secondary containment vessel showed no evidence of structural stress fracture under sustained pneumatic pressure."`
- **Expected Decision:** `False` (Do Not Merge)
- **Predicted Decision:** `True` (Merged as duplicate)
- **Stage 2 Similarity:** 0.8667 (Admitted as candidate)
- **Root-Cause Analysis:**
  In `foundation/corpus/near_deduplication.py`, `SemanticSafetyGuard.check_polarity_conflict` checks for asymmetric negation particles using the fixed set:
  ```python
  neg_particles = {
      "not",
      "never",
      "cannot",
      "neither",
      "without",
      "barely",
      "scarcely",
  }
```
  The particle `"no"` (used as a determiner expressing complete absence, e.g. "showed no evidence") was omitted from `neg_particles`. As a result, the asymmetric occurrence of `"no"` was treated as a standard non-negation stopword variation and allowed to pass into production merging.
- **Safety Impact:** Catastrophic in safety-critical domains (failing to distinguish structural presence of fracture from absence of fracture).
- **Remediation Plan (Post-Phase 4.12):** Add `"no"` and `"none"` to `neg_particles` in `SemanticSafetyGuard` during the next development phase, followed by validation on a fresh sealed benchmark v9.0.

---

## 8. Historical Regression Tracking (v3, v6, v7)

To confirm that existing baseline capabilities remain intact, the frozen evaluator was executed across historical benchmarks:

| Benchmark Dataset | Split / Scope | Samples / Pairs | Accuracy | Precision | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Golden Benchmark v3.0** | Language (`eval_language_dataset_v3.json`) | $N=60$ | 100.00% | 1.0000 | **GREEN** |
| **Golden Benchmark v3.0** | Dedup (`eval_near_dedup_dataset_v3.json`) | $N=20$ | 100.00% | 1.0000 | **GREEN** |
| **Historical Benchmark v6.0** | Language Test (`eval_language_dataset_v6.json`) | $N=60$ | 100.00% | 1.0000 | **GREEN** |
| **Historical Benchmark v6.0** | Dedup Test (`eval_near_dedup_dataset_v6.json`) | $N=20$ | 100.00% | 1.0000 | **GREEN** |
| **Historical Benchmark v7.0** | Language Test (`eval_language_dataset_v7.json`) | $N=60$ | 100.00% | 1.0000 | **GREEN** |
| **Historical Benchmark v7.0** | Dedup Test (`eval_near_dedup_dataset_v7.json`) | $N=20$ | 100.00% | 1.0000 | **GREEN** |

All historical regression suites reproduced with 100% fidelity.

---

## 9. Corpus-Ingestion Security and Fail-Closed Governance

The production corpus ingestion gate was tested under both runtimes via `tests/test_corpus_production_gate_fail_closed.py`.

### 9.1 Ingestion Gate Security Checks

| Gate Condition Tested | Expected Behavior | Observed Result (Py 3.14.8 & Py 3.9.13) | Security Status |
| :--- | :--- | :--- | :--- |
| Unregistered source ID | Rejection (`SOURCE_UNREGISTERED`) | Rejected | **FAIL-CLOSED** |
| Unacquired source candidate | Rejection (`SOURCE_NOT_ACQUIRED`) | Rejected | **FAIL-CLOSED** |
| Tampered source metadata (hash mismatch) | Rejection (`METADATA_HASH_MISMATCH`) | Rejected | **FAIL-CLOSED** |
| Stale governance approval | Rejection (`APPROVAL_EXPIRED`) | Rejected | **FAIL-CLOSED** |
| Explicitly excluded source | Rejection (`SOURCE_EXCLUDED`) | Rejected | **FAIL-CLOSED** |
| Host reserve memory violation | Immediate halt before processing | Halted | **FAIL-CLOSED** |
| Atomic pipeline crash | Rollback without partial files | Atomic Clean Rollback | **FAIL-CLOSED** |

**Confirmation:** Production corpus ingestion remains strictly fail-closed. No bypass mechanisms exist, and no corpus data was ingested.

---

## 10. Dual-Environment Verification Results

### 10.1 Primary Environment: Python 3.14.8
- **Executable Path:** `C:\Users\karnik YOGA\OneDrive\Desktop\veda\.venv\Scripts\python.exe`
- **Command:** `.\.venv\Scripts\python.exe -m pytest tests/ -v`
- **Exit Code:** `0`
- **Summary:** **289 passed**, 0 failed, 0 warnings
- **Runtime:** 4.89 seconds
- **Evaluator Execution:** `.\.venv\Scripts\python.exe scripts/evaluate_phase412_certification.py` (Exit code `0`)

### 10.2 Compatibility Environment: Python 3.9.13
- **Executable Path:** `C:\Users\karnik YOGA\AppData\Local\Programs\Python\Python39\python.exe`
- **Command:** `& "C:\Users\karnik YOGA\AppData\Local\Programs\Python\Python39\python.exe" -m pytest tests/ -v`
- **Exit Code:** `0`
- **Summary:** **289 passed**, 0 failed, 0 warnings
- **Runtime:** 4.51 seconds
- **Evaluator Execution:** `& "C:\Users\karnik YOGA\AppData\Local\Programs\Python\Python39\python.exe" scripts/evaluate_phase412_certification.py` (Exit code `0`)

Dual-environment equivalence is complete and verified across all 289 unit tests and both evaluations.

---

## 11. Acceptance Gate Audit & Decisions

| Gate | Acceptance Criterion | Observed Value | Gate Decision | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Gate A** | Language Filter Accuracy $\ge 95.0\%$ on sealed test set | **93.33%** | **FAIL / BLOCKED** | Below 95% threshold due to 4 technical prose false rejections ($N=60$). |
| **Gate B** | Near-Duplicate Detection Accuracy $\ge 95.0\%$ | **95.00%** | **PASS** | Evaluated at exactly 95.00% on the sealed test set ($N=20$). |
| **Gate C** | False-Merge Control Precision $= 100\%$, Zero safety merges | **88.89%** Precision, **1 safety merge** | **FAIL / BLOCKED** | Safety-critical false merge on `v8_dedup_test_018` ("evidence" vs "no evidence"). |
| **Gate D** | Dual-Runtime Reproducibility (Py 3.14.8 & Py 3.9.13) | **289 / 289 passed** on both | **PASS** | 100% green pass rate and identical evaluations across both runtimes. |
| **Gate E** | Independent Third-Party Review & Provenance | **Internally Authored** | **UNVERIFIED** | Provisional internal construction; third-party review not arranged. |
| **Gate F** | Corpus Ingestion Security & Fail-Closed Status | **100% Fail-Closed** | **PASS** | All 7 security checks verified under both runtimes. |
| **Gate G** | Reproducibility & Cryptographic Integrity | **Deterministic & Recorded** | **PASS** | Exact hashes and commands recorded; zero leakage verified. |

---

## 12. Residual Risks and Next Steps

### 12.1 Residual Risks Identified
1. **Technical English Stopword Density Defect:** In sentences with $\ge 15$ words, requiring $\ge 2$ distinct stopwords erroneously rejects grammatically sound English prose that uses a single preposition (e.g. "to" or "and") connecting complex noun phrases.
2. **Negation Particle Omission:** The word `"no"` was omitted from `neg_particles` in `SemanticSafetyGuard`, permitting contradictory claims (e.g. "evidence" vs "no evidence") to merge when lexical similarity is otherwise high.
3. **Internal Authorship Limitation:** Until an independent third party conducts a sealed review, benchmarks generated by the implementation agent remain provisional.

### 12.2 Next Steps
1. In a subsequent remediation phase (Phase 4.13), update `neg_particles` to include `"no"` and `"none"`.
2. Calibrate `QualityFilter`'s stopword threshold for long technical sentences (e.g., admitting clean Latin-script text with 1 stopword when alpha ratio is high and foreign cognates are zero).
3. Generate a new sealed certification dataset (v9.0) to independently re-validate both pipelines without reusing v8.0 as an unblinded test set.

---

## 13. Explicit Phase Authorization Decision

In accordance with Phase 4.12 success criteria and the quantitative gate decisions:

> [!CAUTION]
> **GATE DECISION: BLOCKED**  
> Gates A and C failed on the sealed v8.0 provisional test set (Language Filter: 93.33% vs 95.0% threshold; Near-Deduplication: 1 observed safety-critical false merge on negation inversion). Gate E remains UNVERIFIED.  
>  
> **Phase 5 Model Development and Pretraining remains strictly PAUSED / ON HOLD.**  
> No model training, neural weight initialization for pretraining, corpus ingestion, or Phase 5 development is authorized until a subsequent remediation phase resolves the identified defects and achieves passing certification on a new independent benchmark.
