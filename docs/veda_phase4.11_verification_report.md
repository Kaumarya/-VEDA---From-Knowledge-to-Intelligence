# VEDA PHASE 4.11: NEAR-DEDUPLICATION POLARITY FIX & REGRESSION VERIFICATION REPORT
**Remediation of Resource Quota Polarity Defect, End-to-End Detector Verification, and Dual-Runtime Testing**

- **Project**: VEDA — “From Knowledge to Intelligence”
- **Phase**: 4.11 (Near-Deduplication Polarity Inversion Remediation & Full Verification)
- **Date**: October 17, 2026
- **Primary Supported Interpreter**: Python 3.14.8 AMD64 (`.venv\Scripts\python.exe`)
- **Baseline Preserved Interpreter**: Python 3.9.13 (Global Installation: `C:\Users\karnik YOGA\AppData\Local\Programs\Python\Python39\python.exe`)
- **Authority**: Antigravity Independent Verification Agent
- **Corpus Ingestion Gate**: **STRICTLY BLOCKED (Fail-Closed Governance Preserved)**
- **Phase 5 Advance Status**: **STRICTLY PAUSED / ON HOLD**

---

## Executive Summary

Phase 4.11 addressed the remaining known near-deduplication false merge in the development benchmark (`v7_dedup_dev_010`, category `hard_negative_semantic_divergence`), verified that the correction operates across all inflections in a direction-independent manner, established a unified production detector interface [`NearDuplicateDetector.are_near_duplicates()`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L550), and proved through comprehensive multi-runtime testing that no regressions were introduced to language filtering or earlier safety guards.

### Key Outcomes:
1. **Defect Remediation (`expand` vs `reduce` / `contract`)**:
   - `expand`, `expands`, `expanded`, `expanding` were incorporated into the growth/increase polarity set in [`SemanticSafetyGuard.POLARITY_PAIRS`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L298-L312).
   - Its classical antonym family `contract`, `contracts`, `contracted`, `contracting` alongside `reduce`, `reduces`, `reduced`, `reducing`, and `decrease` were unified into the opposing contraction/decrease set.
   - The groundwater-quota pair (*"The state environmental commission resolved to expand [vs reduce] commercial groundwater extraction quotas..."*) is now deterministically blocked with conflict type `POLARITY_INVERSION`.
2. **Unified Production Interface**:
   - Implemented [`NearDuplicateDetector`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L550) with method [`are_near_duplicates(text_a, text_b)`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L573), returning structured [`NearDuplicateResult`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L537) capturing candidate screening status, safety guard validation, conflict classifications, and reasons.
3. **Dedicated Regression Tests**:
   - Added 5 new regression tests in [`tests/test_near_deduplication_safety.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L297-L380) covering the exact groundwater pair, reversed argument ordering, inflected forms (`expands`/`reduces`, `expanded`/`reduced`, `expanding`/`reducing`), physical/economic antonyms (`expand`/`contract`), and preservation of genuine paraphrases (*resolved* vs *decided*).
4. **Dual-Environment Test Suite Execution**:
   - **Python 3.14.8 (`.venv`)**: **289 passed in 4.86s**, 0 failed, 0 errors, 0 warnings (Exit Code: `0`).
   - **Python 3.9.13 (Baseline)**: **289 passed in 4.52s**, 0 failed, 0 errors, 0 warnings (Exit Code: `0`).
5. **Evaluator Audit & Benchmark Metrics**:
   - Near-Deduplication Development Split ($N=20$): Improved from 95.00% ($19/20$) to **100.00%** ($20/20$), 0 false merges, 11 of 11 safety merges prevented.
   - Near-Deduplication Test Split ($N=20$): Maintained **100.00%** ($20/20$), 0 false merges, 11 of 11 safety merges prevented.
   - Language Filter Development Split ($N=60$): Maintained **100.00%** ($60/60$).
   - Language Filter Test Split ($N=60$): Maintained **100.00%** ($60/60$).
   - Historical Benchmarks v3.0 and v6.0: Maintained **100.00%** across all tasks.
6. **Benchmark Status & Governance**:
   - V7 was used during defect inspection and remains designated an internal development/regression suite.
   - **Gate F (Benchmark Independence)** remains **UNVERIFIED**.
   - Production ingestion remains **STRICTLY BLOCKED (Fail-Closed)**. Phase 5 remains **ON HOLD**.

---

## 1. Baseline Commit, Working-Tree State & Checksums

### 1.1 Working Tree & Environment Baseline
- **Repository Root**: `C:\Users\karnik YOGA\OneDrive\Desktop\veda`
- **Active Git Branch**: `main` (synchronized with `origin/main`)
- **Current HEAD Commit**: `14c29b420e421bf4ebffa441778d47db49ac74bd`
- **Tracked Modifications Preserved**: [`README.md`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/README.md), [`foundation/lexicon/storage.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/storage.py), [`requirements.txt`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/requirements.txt), [`veda.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/veda.py).
- **Untracked Datasets, Reports & Scratch Files**: All existing files in `data/corpus/`, `docs/`, `scratch/`, and `tests/` preserved without deletion or reset.
- **Python Interpreters**:
  - Python 3.14.8 AMD64 (`.venv\Scripts\python.exe`) active and standardized.
  - Python 3.9.13 AMD64 (`C:\Users\karnik YOGA\AppData\Local\Programs\Python\Python39\python.exe`) verified untouched.

### 1.2 Cryptographic Checksums (SHA-256)

| Artifact Path | SHA-256 Checksum | Purpose / Status |
| :--- | :--- | :--- |
| `foundation/corpus/near_deduplication.py` | `9FFFA9183D8F80F14FF338AA807DC7BF10288A829DF0D5F1B0346E005A4DB0B5` | Polarity fix & NearDuplicateDetector |
| `tests/test_near_deduplication_safety.py` | `53917FCD6121955CA1150513F18B9B0F73394CA623C011B7778A0F9DCFD58A70` | Phase 4.11 focused regression tests |
| `foundation/corpus/language_audit.py` | `6926C6BB18A343E3F7B93DEE16434466A7AA4740953E4C7B3BF00702F7512524` | Language filter & taxonomy (unchanged) |
| `tests/test_language_filter_hardening.py` | `2E8CADB2139A9FFDCA97FB9DBE1E322AC60CA317ED772054D677B42A71397BAE` | Hardening tests (unchanged) |
| `data/corpus/eval_near_dedup_dataset_v7.json` | `F44BE30CCBD82AF6E6ED93FDB175BDC3708C0204C26D0DB69F4A6EB7F1CE1370` | Regression benchmark dataset v7 (untouched) |
| `data/corpus/eval_language_dataset_v7.json` | `99291F7C75370ABE37B7D3E2E8C0D2D7977C38C18C458CADF958F3A79ECB1A4D` | Regression benchmark dataset v7 (untouched) |
| `data/corpus/phase4.9_eval_results.json` | `9AA8A1FAB9208B41DD1FBF56CD2A969F77E39DBF8A97A2CCE16E7DD66BFD742D` | Master evaluation output artifact |
| `docs/veda_phase4.10_verification_report.md` | `811ECCFA9F3DD664133A84B025BA7039F0053CAB7456811A45BFD9ED8BF47F53` | Phase 4.10 verification report |

---

## 2. Root Cause & Defect Remediation

### 2.1 Analysis of the Known False Merge (`v7_dedup_dev_010`)
In Phase 4.9 and 4.10, pair `v7_dedup_dev_010` in the Near-Deduplication Development Split was falsely merged:
- **Text A**: *"The state environmental commission resolved to expand commercial groundwater extraction quotas along the coastal aquifer."*
- **Text B**: *"The state environmental commission resolved to reduce commercial groundwater extraction quotas along the coastal aquifer."*
- **Expected Result**: `False` (Opposing actions on resource extraction quotas; merging them causes critical semantic contamination).
- **Predicted Result Before Fix**: `True` (False merge, Stage 3 FP=1).

**Root Cause**:
Stage 2 candidate screening computed a MinHash estimated Jaccard $\ge 0.75$ and token Jaccard of $13/15 = 0.8667$, flagging the pair as a near-duplicate candidate. In Stage 3, [`SemanticSafetyGuard`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L168) inspected the differing words `{'expand'}` vs `{'reduce'}`. While `reduce` was present in the contraction/decrease set of `POLARITY_PAIRS`, `expand` was absent from the corresponding positive set (`increase`). Consequently, no polarity conflict was raised.

### 2.2 Minimal, Justified Linguistic Fix
Rather than creating an overly narrow single-word override, we integrated the complete inflectional family of `expand` into the primary scalar/magnitude polarity pair in [`foundation/corpus/near_deduplication.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L307-L310):

```python
# Before:
({"increase", "increases", "increased", "increasing", "gain", "gains", "rise", "rises"}, 
 {"decrease", "decreases", "decreased", "decreasing", "reduce", "reduces", "reduced", "reducing", "loss", "losses", "fall", "falls", "drop", "drops"}),

# After (Phase 4.11):
(
    {"increase", "increases", "increased", "increasing", "gain", "gains", "rise", "rises", "expand", "expands", "expanded", "expanding"},
    {"decrease", "decreases", "decreased", "decreasing", "reduce", "reduces", "reduced", "reducing", "contract", "contracts", "contracted", "contracting", "loss", "losses", "fall", "falls", "drop", "drops"},
),
```

### 2.3 Direction-Independent Symmetry
[`SemanticSafetyGuard.check_polarity_conflict()`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L392-L422) checks:
```python
if (a_pos and b_neg and not a_neg and not b_pos) or \
   (a_neg and b_pos and not a_pos and not b_neg):
    return ("POLARITY_INVERSION", f"Contradictory polarity detected: '{match_a}' vs '{match_b}'")
```
Because both branches `(a_pos and b_neg)` and `(a_neg and b_pos)` are symmetrical:
- `verify_pair(text_a, text_b)` flags `['expand']` vs `['reduce']` -> `POLARITY_INVERSION`.
- `verify_pair(text_b, text_a)` flags `['reduce']` vs `['expand']` -> `POLARITY_INVERSION`.
Reversing the argument order guarantees identical safety enforcement.

### 2.4 End-to-End Detector Implementation
To provide a first-class production entrypoint, we implemented [`NearDuplicateDetector`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L550):
```python
class NearDuplicateDetector:
    def __init__(self, threshold: float = 0.75, num_perm: int = 128, num_bands: int = 16, k_shingle: int = 5):
        self.threshold = threshold
        self.candidate_detector = MinHashLSHCandidateDetector(...)
        self.safety_guard = SemanticSafetyGuard()

    def are_near_duplicates(self, text_a: str, text_b: str) -> NearDuplicateResult:
        # 1. Fast path for identical strings
        # 2. Stage 2 candidate screening (max of MinHash est_jaccard and token_jaccard >= threshold)
        # 3. Stage 3 SemanticSafetyGuard verification
        ...
```

---

## 3. Dedicated Regression Tests

Five new unit tests were added to [`tests/test_near_deduplication_safety.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L297-L380):

1. [`test_phase411_groundwater_quota_expand_vs_reduce_rejected`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L299-L318):
   - Asserts that [`NearDuplicateDetector.are_near_duplicates()`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/near_deduplication.py#L573) identifies the pair as a candidate (`is_candidate == True`), blocks the merge (`is_duplicate == False`), flags `safety_guard_passed == False`, and reports `conflict_type == "POLARITY_INVERSION"`.
2. [`test_phase411_groundwater_quota_reversed_order_safe`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L319-L330):
   - Evaluates `(text_b, text_a)` and verifies that `is_duplicate == False` and `conflict_type == "POLARITY_INVERSION"`.
3. [`test_phase411_expand_vs_reduce_inflections_rejected`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L331-L355):
   - Verifies 3rd-person singular present: `expands` vs `reduces` -> Rejected (`POLARITY_INVERSION`).
   - Verifies past tense: `expanded` vs `reduced` -> Rejected (`POLARITY_INVERSION`).
   - Verifies present participle: `expanding` vs `reducing` -> Rejected (`POLARITY_INVERSION`).
4. [`test_phase411_expand_vs_contract_antonym_rejected`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L356-L365):
   - Verifies classical antonyms `expand` vs `contract` -> Rejected (`POLARITY_INVERSION`).
5. [`test_phase411_genuine_paraphrase_accepted`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_near_deduplication_safety.py#L366-L377):
   - Verifies that a genuine paraphrase with identical semantic assertion (*"resolved to expand"* vs *"decided to expand"*) is correctly accepted as a duplicate (`is_duplicate == True`, `conflict_type is None`).

---

## 4. Evaluation Audit & Benchmark Results

The Phase 4.9 evaluator ([`scripts/evaluate_phase49_certification.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/scripts/evaluate_phase49_certification.py)) was executed against the benchmark datasets.

### 4.1 Task B: Near-Deduplication Before vs After

| Benchmark Split | Total Pairs | Metric | Phase 4.10 (Before) | Phase 4.11 (After) | Status |
| :--- | :---: | :--- | :---: | :---: | :---: |
| **Development Split** | 20 | **Accuracy** | 95.00% ($19/20$) | **100.00%** ($20/20$) | **PASS** |
| | | **Precision** | 88.89% | **100.00%** | **PASS** |
| | | **Recall** | 100.00% | **100.00%** | **PASS** |
| | | **$F_1$ Score** | 0.9412 | **1.0000** | **PASS** |
| | | **False Merges** | 1 (`v7_dedup_dev_010`) | **0** | **PASS** |
| | | **Safety Merges Blocked** | 10 / 11 | **11 / 11** | **PASS** |
| | | **95% Wilson CI** | $[0.7639, 0.9911]$ | **$[0.8389, 1.0000]$** | **PASS** |
| **Held-Out Test Split** | 20 | **Accuracy** | 100.00% ($20/20$) | **100.00%** ($20/20$) | **PASS** |
| | | **Precision** | 100.00% | **100.00%** | **PASS** |
| | | **Recall** | 100.00% | **100.00%** | **PASS** |
| | | **$F_1$ Score** | 1.0000 | **1.0000** | **PASS** |
| | | **False Merges** | 0 | **0** | **PASS** |
| | | **Safety Merges Blocked** | 11 / 11 | **11 / 11** | **PASS** |
| | | **95% Wilson CI** | $[0.8389, 1.0000]$ | **$[0.8389, 1.0000]$** | **PASS** |

### 4.2 Detailed Outcome of `v7_dedup_dev_010`
- **Candidate Screening (Stage 2)**: Candidate similarity = $0.8521 \ge 0.75$ -> Candidate confirmed (`is_candidate = True`).
- **Safety Guard (Stage 3)**: Difference set `{'expand'}` vs `{'reduce'}` matched `increase` vs `decrease` polarity sets -> Conflict detected (`POLARITY_INVERSION`).
- **Merge Decision**: Blocked (`is_duplicate = False`).
- **Ground Truth**: `is_true_duplicate = False`.
- **Verdict**: **CORRECT PREDICTION** (False merge eliminated).

### 4.3 Task A: Language Identification Invariance Check
- **Development Split ($N=60$)**: **100.00%** ($60/60$, Wilson CI $[0.9398, 1.0000]$).
- **Held-Out Test Split ($N=60$)**: **100.00%** ($60/60$, Wilson CI $[0.9398, 1.0000]$).
- Zero non-English texts falsely accepted.
- All 4 Phase 4.10 corrected samples (`v7_lang_dev_019`, `v7_lang_test_018`, `v7_lang_test_020`, `v7_lang_test_047`) confirmed passing.
- Spanish Cervantes prose with `de` confirmed `REJECT` (`NO_ENGLISH_STOPWORDS`).

### 4.4 Historical Benchmark Regression Invariance
- **Authentic Benchmark v3.0 ($N=33$ Lang, $N=11$ Dedup)**: 100.00% accuracy, 0 false merges.
- **Retired Development Benchmark v6.0 ($N=60$ Lang, $N=20$ Dedup)**: 100.00% accuracy, 0 false merges.

---

## 5. Full Test Suite Results Across Both Runtimes

| Test Execution Command | Python Version | Exit Code | Tests Passed | Tests Failed | Warnings | Duration |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `.\.venv\Scripts\python.exe -m pytest tests/ -v` | **Python 3.14.8** | **`0`** | **289** | **0** | **0** | **4.86s** |
| `& "C:\Users\...\python.exe" -m pytest tests/ -v` | **Python 3.9.13** | **`0`** | **289** | **0** | **0** | **4.52s** |

Every unit and regression test across both runtime environments passed with zero errors and zero warnings.

---

## 6. Formal Quality Gate Determinations

| Gate | Description | Target | Verified Value | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Gate A** | Language Filter Accuracy (v7 Test) | $\ge 95\%$ | **100.00%** ($60/60$) | **PASS** |
| **Gate B** | Near-Dedup Accuracy (v7 Test) | $\ge 95\%$ | **100.00%** ($20/20$) | **PASS** |
| **Gate C** | Near-Dedup Precision (v7 Test) | $100\%$ | **100.00%** (0 false merges) | **PASS** |
| **Gate D** | Critical Safety Merges Blocked | $100\%$ | **11 / 11** in Dev, **11 / 11** in Test | **PASS** |
| **Gate E** | Language Quality Score Calibration | Continuous $[0.70, 1.0]$ | Calibrated | **PASS** |
| **Gate F** | Benchmark Independence (Third-Party) | Independent Blind | Inspected during defect remediation; retained as dev/regression suite | **UNVERIFIED** |
| **Gate G** | Multi-Version Regression Invariance | $\ge 95\%$ | v3: 100%, v6: 100%, v7: 100% | **PASS** |
| **Gate H** | Cryptographic Provenance Hashes | $100\%$ | All SHA-256 hashes verified & recorded | **PASS** |
| **Gate I** | Model Provenance (Zero Pretrained Weights)| Native PyTorch | Clean, from-scratch random weights | **PASS** |
| **Gate J** | Checkpoint Deserialization Security | `weights_only=True` | Verified in code and test suite | **PASS** |
| **Gate K** | Corpus Production Gate Fail-Closed | Zero unapproved ingestion | Enforced by [`test_corpus_production_gate_fail_closed.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/tests/test_corpus_production_gate_fail_closed.py) | **BLOCKED (Fail-Closed)** |
| **Gate L** | Full Regression Suite Passing | $100\%$ | **289 passed** on Py3.14 & Py3.9 | **PASS** |

---

## 7. Scope Restrictions & Phase Governance

1. **Production Corpus Ingestion**: Remains **STRICTLY BLOCKED (Fail-Closed)**.
2. **Phase 5 Authorization**: Remains **PAUSED / ON HOLD**. Pretraining, model initialization, RAG, and UI development must not commence.
3. **Benchmark Independence Disclosure**: Because benchmark v7 was inspected and corrected against during development, it is formally classified as an internal **regression test suite**. Perfect performance on v7 does **not** constitute independent certification. Independent blind certification requires an externally held, unopened benchmark (v8).
