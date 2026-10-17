# VEDA PHASE 4.8: COMPREHENSIVE ACCURACY, BENCHMARK INDEPENDENCE & EVALUATION REPORT

**Project**: VEDA — “From Knowledge to Intelligence”  
**Phase**: 4.8  
**Date**: October 15, 2026  
**Primary Runtime**: Python 3.14.8 AMD64 (`.venv\Scripts\python.exe`)  
**Certification Artifact**: `data/corpus/phase4.8_eval_results.json` (SHA-256: `b996b34180a4a367255e6b2aba9ad1f31677d73de0b50c9146b4c609c3c72fa4`)

---

## 1. Executive Summary & Verification Standards

Phase 4.8 achieved **100% observed accuracy** on both approved final evaluation tasks evaluated on the officially certified, non-templated, independent benchmark (**v6.0**):
- **Task A (Language Identification & Quality Filtering)**: **100.00% Accuracy ($60/60$)**, Precision(ACCEPT) = $1.0000$, Recall(ACCEPT) = $1.0000$, $F_1 = 1.0000$, Wilson 95% CI $[0.9398, 1.0000]$.
- **Task B (Near-Deduplication & Semantic Safety Guard)**: **100.00% Accuracy ($20/20$)**, Precision = $1.0000$, Recall = $1.0000$, $F_1 = 1.0000$, Wilson 95% CI $[0.8389, 1.0000]$.
- **Critical Safety Regression Invariants**: **11/11 Prevented (0 False Merges)** across dosage flips, physical dimensional conflicts, calendar dates, entity IDs, polarity flips, and negation inversions.

In accordance with Section A and Section H of the Engineering Specification, universal real-world 100% accuracy is explicitly disclaimed. The reported results reflect true empirical measurements under controlled, reproducible conditions.

---

## 2. Benchmark Independence & Provenance Audit

| Benchmark Version | Phase Created | Independence Assessment & Role | SHA-256 Hash |
| :--- | :---: | :--- | :--- |
| **v3.0** | Phase 4.4 | Authentic historical samples ($N=33$ Lang, $N=11$ Dedup). Golden baseline. | `246b44999add21bc...` |
| **v4.0** | Phase 4.6 | **Calibrated Regression Suite**. Contained synthetic loop templates (`{i+1}`). Retained for regression testing. | `c1b892e3ed62a029...` |
| **v5.0** | Phase 4.7 | **Development & Calibration Suite**. Held-out errors were inspected to diagnose `DEF-4.8-01` through `DEF-4.8-05`. Formally retired as independent test. | `dbea6251c6ea1dbb...` |
| **v6.0** | **Phase 4.8** | **Official Independent Final Certification Suite**. Hand-authored natural sentences, zero template loops, disjoint academic domains, frozen prior to evaluation. | `8b29614da8c41b06...` |

---

## 3. Task A: Language Filtering Evaluation

### 3.1 Overall Performance Across Benchmark Suites

| Benchmark Suite | Split | Total Samples ($N$) | Accuracy | 95% Wilson CI | Precision (Accept) | Recall (Accept) | $F_1$ (Accept) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **v3.0 Authentic** | Held-Out Test | 33 | **100.00%** | $[0.8957, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v4.0 Calibrated** *(Regr)* | Held-Out Test | 500 | **98.60%** | $[0.9715, 0.9932]$ | 1.0000 | 0.9720 | **0.9858** |
| **v5.0 Dev / Regr** | Held-Out Test | 50 | **100.00%** | $[0.9286, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v6.0 Official Final** | Development | 60 | **100.00%** | $[0.9398, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v6.0 Official Final** | **Held-Out Test** | **60** | **100.00%** | **$[0.9398, 1.0000]$** | **1.0000** | **1.0000** | **1.0000** |

### 3.2 v6.0 Independent Test Split ($N=60$) Confusion Matrix

```
                      PREDICTED DECISION
               |  ACCEPT  | QUARANTINE |  REJECT  |
   ------------+----------+------------+----------+
     ACCEPT    |    30    |     0      |    0     |  (Precision = 1.0000, Recall = 1.0000)
T  ------------+----------+------------+----------+
R  QUARANTINE  |     0    |    20      |    0     |  (Precision = 1.0000, Recall = 1.0000)
U  ------------+----------+------------+----------+
E    REJECT    |     0    |     0      |   10     |  (Precision = 1.0000, Recall = 1.0000)
   ------------+----------+------------+----------+
```

### 3.3 v6.0 Independent Test Split Category Breakdown

| Category | Sample Count ($N$) | Correct | Accepted | Quarantined | Rejected | Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Ordinary English Prose** | 10 | 10 | 10 | 0 | 0 | **100.0%** |
| **Expository Academic Prose** | 10 | 10 | 10 | 0 | 0 | **100.0%** |
| **Scientific Figure Captions** | 5 | 5 | 5 | 0 | 0 | **100.0%** |
| **Foreign Names & Quotes** | 5 | 5 | 5 | 0 | 0 | **100.0%** |
| **Code / SQL / Structured** | 5 | 5 | 0 | 5 | 0 | **100.0%** |
| **Imperative Signage Notices** | 5 | 5 | 0 | 5 | 0 | **100.0%** |
| **Short Headings & Fragments** | 5 | 5 | 0 | 5 | 0 | **100.0%** |
| **Germanic Latin Prose (DE/NL)** | 5 | 5 | 0 | 5 | 0 | **100.0%** |
| **Romance Latin Prose (FR/ES/IT)**| 5 | 5 | 0 | 0 | 5 | **100.0%** |
| **Malformed Noise & Non-Latin** | 5 | 5 | 0 | 0 | 5 | **100.0%** |

- **False Ingestion (Acceptance) Count**: **0**
- **False Rejection Count**: **0**
- **Unnecessary Quarantine Count**: **0**

---

## 4. Task B: Near-Deduplication & Safety Guard Evaluation

### 4.1 Overall Performance Across Benchmark Suites

| Benchmark Suite | Split | Total Pairs ($N$) | Stage 2 Acc | Stage 3 Guard Acc | False Merges Prevented | 95% Wilson CI (Stage 3) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **v3.0 Authentic** | Held-Out Test | 11 | 90.91% | **100.00%** | 1 | $[0.7412, 1.0000]$ |
| **v4.0 Calibrated** *(Regr)* | Held-Out Test | 500 | 46.00% | **100.00%** | 270 | $[0.9926, 1.0000]$ |
| **v5.0 Dev / Regr** | Held-Out Test | 17 | 100.00% | **100.00%** | 9 | $[0.8157, 1.0000]$ |
| **v6.0 Official Final** | Development | 20 | 85.00% | **90.00%** | 10 | $[0.6990, 0.9721]$ |
| **v6.0 Official Final** | **Held-Out Test** | **20** | **95.00%** | **100.00%** | **11** | **$[0.8389, 1.0000]$** |

### 4.2 v6.0 Independent Test Split ($N=20$) Breakdown

- **True Positives (Duplicate Correctly Merged)**: 8
- **False Positives (Distinct Pair Falsely Merged)**: **0**
- **True Negatives (Distinct Pair Correctly Blocked)**: 12
- **False Negatives (Duplicate Missed / Discarded)**: 0
- **Precision**: **1.0000**
- **Recall**: **1.0000**
- **$F_1$ Score**: **1.0000**
- **Overall Accuracy**: **100.00%**
- **False Merges Prevented**: **11**

### 4.3 Detailed Pair Verification in v6.0 Independent Test Split

| Pair ID | Category | Ground Truth | Final Merge Decision | Safety Conflict Reason | Status |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `v6_dedup_test_001` | `exact_duplicate` | True | **True** | None (100% lexical match) | **PASS** |
| `v6_dedup_test_002` | `reformatted_duplicate` | True | **True** | None (Whitespace normalized) | **PASS** |
| `v6_dedup_test_003` | `paraphrase_duplicate` | True | **True** | None (Active/passive voice verified) | **PASS** |
| `v6_dedup_test_004` | `reordered_duplicate` | True | **True** | None (Reordered clauses verified) | **PASS** |
| `v6_dedup_test_005` | `unit_conversion_duplicate`| True | **True** | None ($5000\text{ m} = 5\text{ km}$) | **PASS** |
| `v6_dedup_test_006` | `unit_conversion_duplicate`| True | **True** | None ($1048576\text{ B} = 1\text{ MiB}$) | **PASS** |
| `v6_dedup_test_007` | `unit_conversion_duplicate`| True | **True** | None ($2000\text{ mg} = 2\text{ g}$) | **PASS** |
| `v6_dedup_test_008` | `unit_conversion_duplicate`| True | **True** | None ($120\text{ min} = 2\text{ hr}$) | **PASS** |
| `v6_dedup_test_009` | `distant_negative` | False | **False** | Filtered by Stage 2 similarity | **PASS** |
| `v6_dedup_test_010` | `safety_dosage_inversion` | False | **False** | Quantity discrepancy: $15\text{ mg}$ vs $150\text{ mg}$ | **PASS** |
| `v6_dedup_test_011` | `safety_unit_mismatch` | False | **False** | Physical dimension: $30\text{ bar}$ vs $30\text{ g}$ | **PASS** |
| `v6_dedup_test_012` | `safety_unit_mismatch` | False | **False** | Physical dimension: $25\text{ m}$ vs $25\text{ s}$ | **PASS** |
| `v6_dedup_test_013` | `safety_date_mismatch` | False | **False** | Year conflict: $1783$ vs $1789$ | **PASS** |
| `v6_dedup_test_014` | `safety_date_mismatch` | False | **False** | Month conflict: March vs October | **PASS** |
| `v6_dedup_test_015` | `safety_polarity_inversion`| False | **False** | Polarity: nontoxic/safe vs toxic/harmful | **PASS** |
| `v6_dedup_test_016` | `safety_polarity_inversion`| False | **False** | Polarity: greater than vs less than | **PASS** |
| `v6_dedup_test_017` | `safety_polarity_inversion`| False | **False** | Polarity: permitted vs prohibited | **PASS** |
| `v6_dedup_test_018` | `safety_negation_inversion`| False | **False** | Asymmetric negation: operated vs never | **PASS** |
| `v6_dedup_test_019` | `safety_identifier_conflict`| False | **False** | Identifier code: NAV-301 vs NAV-302 | **PASS** |
| `v6_dedup_test_020` | `hard_negative_divergence` | False | **False** | Polarity: increased vs decreased | **PASS** |

---

## 5. Summary Conclusion

1. **Defects Fully Remediated**: All root causes identified during Phase 4.7 (`DEF-4.8-01` through `DEF-4.8-06`) were eliminated.
2. **Benchmark Integrity Restored**: Independent evaluation on the frozen v6.0 benchmark confirms **100.00% observed accuracy** on both general language filtering and near-deduplication, with zero false merges on safety regressions.
3. **Reproducibility**: All evaluation outputs are deterministically reproducible using `.venv\Scripts\python.exe scripts/evaluate_phase48_certification.py`.
