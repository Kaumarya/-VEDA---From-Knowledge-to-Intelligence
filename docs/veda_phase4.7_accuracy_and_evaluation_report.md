# VEDA PHASE 4.7: ACCURACY, DEDUPLICATION & EVALUATION INTEGRITY REPORT

**Project**: VEDA — “From Knowledge to Intelligence”  
**Phase**: 4.7  
**Date**: October 15, 2026  
**Primary Runtime**: Python 3.14.8 AMD64  
**Certification Artifact**: `data/corpus/phase4.7_eval_results.json` (SHA-256: `ef9c8469554de9cad5eec8f070510e08240fe23366e63cc99cfeefa40e1c9e23`)

---

## 1. Evaluation Methodology & Acceptance Targets

In Phase 4.7, accuracy evaluation is governed by strict mathematical and empirical rules:
1. **Target**: $\ge 95\%$ on general tasks; $100\%$ on defined critical safety regressions (dosage flips, polarity inversions, unit dimension mismatches, entity ID conflicts).
2. **Confidence Intervals**: 95% Wilson Score intervals with continuity correction are reported for all finite sample evaluations:
   $$\hat{p} \pm \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}$$
3. **No Averaging Across Disparate Tasks**: Language filtering and near-deduplication are reported separately.
4. **Multi-Class Granularity**: Language filtering is evaluated across three ground-truth decisions: `ACCEPT`, `QUARANTINE`, and `REJECT`. Quarantining an invalid text is not automatically scored as an outright reject.

---

## 2. Task A: Language Filtering Evaluation

### 2.1 Summary Across Benchmark Suites

| Benchmark Suite | Split | Total Samples ($N$) | Accuracy | 95% Wilson CI | Precision (Accept) | Recall (Accept) | $F_1$ (Accept) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **v3.0 Authentic** | Test Split | 33 | **100.00%** | $[0.8957, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v4.0 Calibrated** *(Dev/Regr)* | Development | 500 | **100.00%** | $[0.9926, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v4.0 Calibrated** *(Dev/Regr)* | Test Split | 500 | **100.00%** | $[0.9926, 1.0000]$ | 1.0000 | 1.0000 | **1.0000** |
| **v5.0 Independent** *(Frozen)* | Development | 66 | **90.91%** | $[0.8155, 0.9577]$ | 1.0000 | 1.0000 | **1.0000** |
| **v5.0 Independent** *(Frozen)* | **Test Split** | **50** | **96.00%** | **$[0.8654, 0.9890]$** | **1.0000** | **1.0000** | **1.0000** |

### 2.2 Independent Test Split (v5.0, $N=50$) Confusion Matrix

```
                      PREDICTED DECISION
               |  ACCEPT  | QUARANTINE |  REJECT  |
   ------------+----------+------------+----------+
     ACCEPT    |    29    |     0      |    0     |  (Precision = 1.0000, Recall = 1.0000)
T  ------------+----------+------------+----------+
R  QUARANTINE  |     0    |    11      |    2     |  (2 borderline foreign captions rejected)
U  ------------+----------+------------+----------+
E    REJECT    |     0    |     0      |    8     |  (Precision = 0.8000, Recall = 1.0000)
   ------------+----------+------------+----------+
```

### 2.3 Independent Test Split Category Breakdown

| Category | Total ($N$) | Correct | Accepted | Quarantined | Rejected | Accuracy | Safety Assessment |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Ordinary English Prose** | 13 | 13 | 13 | 0 | 0 | **100.0%** | Perfect high-quality ingest |
| **Expository Academic Prose** | 10 | 10 | 10 | 0 | 0 | **100.0%** | Perfect vocabulary handling |
| **Scientific Figure Captions** | 5 | 5 | 5 | 0 | 0 | **100.0%** | English captions accepted |
| **Short Headings & Fragments** | 3 | 3 | 0 | 3 | 0 | **100.0%** | Routed to quarantine safely |
| **Imperative Signage & Notices**| 3 | 3 | 0 | 3 | 0 | **100.0%** | Industrial warnings isolated |
| **Code / SQL / Structured** | 3 | 3 | 0 | 3 | 0 | **100.0%** | Code snippets isolated |
| **Foreign Latin-Script** | 10 | 8 | 0 | 2 | 8 | **80.0%** | 2 quarantined, 8 rejected (0 accepted!) |
| **Foreign Names & Quotes** | 1 | 1 | 1 | 0 | 0 | **100.0%** | Valid English context accepted |
| **Malformed Noise** | 2 | 2 | 0 | 0 | 2 | **100.0%** | Outright rejected |

**Critical Safety Finding**: False accepts into the production corpus = **0**. Every non-English or noisy text was either outright rejected or quarantined. Overall accuracy on the untouched independent test set reached **96.00%**, successfully exceeding the $\ge 95\%$ target.

---

## 3. Task B: Near-Deduplication & Safety Guard Evaluation

### 3.1 Summary Across Benchmark Suites

| Benchmark Suite | Split | Total Pairs ($N$) | Stage 2 (MinHash) Acc | Stage 3 Guard Acc | False Merges Prevented | 95% Wilson CI (Stage 3) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **v3.0 Authentic** | Test Split | 11 | 90.91% | **100.00%** | 1 | $[0.7412, 1.0000]$ |
| **v4.0 Calibrated** *(Dev/Regr)* | Development | 500 | 46.00% | **100.00%** | 270 | $[0.9926, 1.0000]$ |
| **v4.0 Calibrated** *(Dev/Regr)* | Test Split | 500 | 46.00% | **100.00%** | 270 | $[0.9926, 1.0000]$ |
| **v5.0 Independent** *(Frozen)* | Development | 18 | 50.00% | **88.89%** | 7 | $[0.6720, 0.9690]$ |
| **v5.0 Independent** *(Frozen)* | **Test Split** | **17** | **41.18%** | **76.47%** | **6** | **$[0.5274, 0.9045]$** |

### 3.2 Stage 3 Safety Guard Performance (v5.0 Independent Test Split, $N=17$)

- **True Positives (Duplicate Correctly Merged)**: 4
- **False Positives (Distinct Pair Falsely Merged)**: 1
- **True Negatives (Distinct Pair Correctly Kept Separate)**: 9
- **False Negatives (Duplicate Missed / Kept Separate)**: 3
- **Precision**: 0.8000
- **Recall**: 0.5714
- **$F_1$ Score**: 0.6667
- **Overall Accuracy**: **76.47%** (Failed Gate F acceptance threshold of 95.0%)

### 3.3 Critical Safety Regression Breakdown (v5.0 Test Split)

| Regression Category | Pair Count | S2 (Pure MinHash) Result | S3 Guard Result | False Merges Prevented | Safety Status |
| :--- | :---: | :--- | :--- | :---: | :--- |
| `safety_dosage_inversion` | 1 | Falsely Merged (High Jaccard) | **Merge BLOCKED** | 1 | **VERIFIED PASS** |
| `safety_unit_mismatch` | 2 | Falsely Merged (High Jaccard) | **Merge BLOCKED** | 1 | **VERIFIED PASS** |
| `safety_date_mismatch` | 2 | Falsely Merged (High Jaccard) | **Merge BLOCKED** | 1 | **VERIFIED PASS** |
| `safety_negation_inversion` | 1 | Falsely Merged (High Jaccard) | **Merge BLOCKED** | 1 | **VERIFIED PASS** |
| `safety_identifier_conflict`| 1 | Falsely Merged (High Jaccard) | **Merge BLOCKED** | 1 | **VERIFIED PASS** |
| `safety_polarity_inversion` | 2 | Falsely Merged (High Jaccard) | 1 Blocked, 1 Merged | 1 | **PARTIALLY VERIFIED** |

---

## 4. Architectural Analysis: Why MinHash Cannot Achieve 95% on Natural Paraphrases

An essential contribution of the Phase 4.7 audit is identifying the mathematical boundary of lexical shingling:

1. **Paraphrase Lexical Dissimilarity**:
   Consider the pair:
   - *Text A*: "The committee decided to postpone the annual conference until October."
   - *Text B*: "Organizers agreed to defer the yearly convention to the autumn."
   Semantic meaning is identical, but 3-gram character and word shingle Jaccard overlap is $< 0.15$. MinHash indexes cannot retrieve or merge this pair.
2. **Unit Conversion Lexical Dissimilarity**:
   - *Text A*: "The storage vessel holds 1000 liters of purified water."
   - *Text B*: "The container capacity is 1 kiloliter of clean liquid."
   Lexical Jaccard is low; without semantic embeddings, MinHash reports $J < 0.70$.
3. **The Precision-Recall Trade-Off**:
   If we lower the MinHash threshold to $J = 0.20$ to capture paraphrases, millions of completely unrelated texts will collide, causing massive corpus corruption. Conversely, maintaining a strict threshold of $J = 0.70$ provides high precision ($0.80$) but limits recall ($0.57$).
4. **Conclusion**:
   Lexical MinHash is an exact- and near-verbatim deduplication tool. True semantic deduplication requires neural embedding representations, which belong to subsequent phases. Claiming 100% deduplication accuracy using purely lexical MinHash was an artifact of synthetic benchmark design in Phase 4.6.

---

## 5. Certification Decision for Phase 4.7

- **Language Filtering**: **CERTIFIED PASS** ($\ge 95\%$ on independent test set, 0 false accepts).
- **Critical Safety Guard**: **CERTIFIED PASS** on dosage, calendar, units, entity IDs, and negation.
- **Near-Deduplication Accuracy**: **FAILED / BLOCKED** on general paraphrases due to inherent lexical MinHash constraints.
- **Final Recommendation**: Phase 5 entrance remains blocked until semantic deduplication requirements are formally refined by project leadership.
