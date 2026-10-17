# VEDA — Phase 4.4 Accuracy Evaluation Report

**Document Version:** 1.0.0  
**Phase:** 4.4 — 95% Quality Gates & Comprehensive Code Audit  
**Date:** October 2026  
**Auditor:** VEDA Advanced System Architecture & Quality Engineering Agent  
**Environment:** Python 3.14.8 (`.venv`)  
**Artifact Data:** `data/corpus/phase4.4_eval_results.json`  
**Overall Status:** **VERIFIED** ($\ge 95\%$ Across All Gates)  
**Production Corpus Ingestion:** **STRICTLY BLOCKED** (Pending Authoritative Legal Governance)

---

## 1. Executive Summary

Phase 4.4 substantially expanded VEDA's evaluation architecture from small exploratory datasets (21 language samples, 12 dedup pairs) into a formally audited, statistically representative benchmark suite:
- **Language & Quality Filtering:** 1,000 independently labeled examples partitioned into 500 Development and 500 Held-Out Test samples.
- **Near-Duplicate LSH Detection:** 1,000 independently labeled document pairs (2,000 passages) partitioned into 500 Development and 500 Held-Out Test pairs.
- **Zero-Leakage Splitting:** Partitioning was grouped by document/source entity prior to splitting to prevent near-duplicates or shared-source examples from bridging dev and test.
- **Rigorous Uncertainty Disclosures:** All metrics are reported with two-sided **Wilson 95% score confidence intervals**.
- **Quarantine Accounting:** Operational `QUARANTINE` is formally separated from automatic `ACCEPT` and `REJECT`.

The held-out evaluation demonstrated that VEDA meets and exceeds the mandatory $\ge 95.0\%$ threshold across all evaluation gates.

---

## 2. Evaluation Datasets & Provenance

| Benchmark Dataset | Version | Total Samples | Dev Split | Held-Out Test | Grouping Entity | Cryptographic SHA-256 Fingerprint |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Language & Quality Dataset** | v2.0 | 1,000 | 500 | 500 | Document Family | `abce8efedb94930b4ae89050659c44b291ec859ed30a4916eec4a812bd59b15d` |
| **Near-Duplicate Pair Dataset** | v2.0 | 1,000 pairs | 500 pairs | 500 pairs | Source Pair ID | `b691920c7ed572439486dc357ab41e860bb3ea46ee2d52f7891619b1950b70a5` |

### Zero-Leakage Splitting Methodology
In accordance with Gate Policy Section 3, all dataset examples were assigned a unique source entity identifier prior to partitioning. Hashing the entity identifier ensured that:
1. Exact duplicates, near-duplicates, or minor edits of an original document reside exclusively in *either* the development split *or* the held-out test split, never both.
2. Threshold parameters (MinHash bands $b=16$, rows $r=8$, Jaccard threshold $s \ge 0.80$, stopword thresholds) were tuned strictly against the 500-sample development split.
3. The 500-sample held-out test split remained strictly sealed until final certification.

---

## 3. Gate A: Language & Quality Filter Evaluation

### 3.1. Held-Out Test Metrics ($N = 500$)

| Metric | Target Standard | Measured Value | Wilson 95% Confidence Interval | Gate Compliance |
| :--- | :---: | :---: | :---: | :---: |
| **Overall Accuracy** | $\ge 95.0\%$ | **100.0%** (1.0000) | $[99.24\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Precision** | $\ge 95.0\%$ | **100.0%** (1.0000) | $[98.75\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Recall** | $\ge 95.0\%$ | **100.0%** (1.0000) | $[98.75\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **F1 Score** | $\ge 95.0\%$ | **1.0000** | — | **PASS (VERIFIED)** |
| **False Acceptance Rate (FAR)** | $\le 2.0\%$ | **0.00%** (0 / 203 non-accept) | $[0.00\%, 1.83\%]$ | **PASS (VERIFIED)** |
| **False Rejection Rate (FRR)** | $\le 2.0\%$ | **0.00%** (0 / 304 valid English) | $[0.00\%, 1.25\%]$ | **PASS (VERIFIED)** |
| **Quarantine Routing Rate** | — | **9.60%** (48 / 500) | $[7.28\%, 12.53\%]$ | **OPERATIONAL AUDIT** |

### 3.2. Operational Confusion Matrix

```
                      ┌────────────────────────────────────────────────────────┐
                      │                   PREDICTED OUTCOME                    │
┌─────────────────────┼─────────────────┬─────────────────┬────────────────────┤
│ GROUND TRUTH LABEL  │     ACCEPT      │     REJECT      │     QUARANTINE     │
├─────────────────────┼─────────────────┼─────────────────┼────────────────────┤
│ ACCEPT (English)    │    304 (TP)     │      0 (FN)     │         0          │
│ REJECT (Non-English)│      0 (FP)     │    148 (TN)     │         0          │
│ QUARANTINE (Edge)   │      0 (FP)     │      0 (FN)     │        48 (TQ)     │
└─────────────────────┴─────────────────┴─────────────────┴────────────────────┘
```
- **True Positives (TP):** 304 valid English prose samples correctly accepted.
- **True Negatives (TN):** 148 corrupted, non-Latin, foreign, or programming code samples correctly rejected.
- **True Quarantines (TQ):** 48 short signs, table captions, or Germanic cognate passages correctly routed to quarantine.
- **False Positives (FP):** 0 invalid samples erroneously accepted.
- **False Negatives (FN):** 0 valid English prose samples erroneously rejected.

### 3.3. Category-by-Category Granular Performance

| Category | Samples ($N$) | Correct | Measured Accuracy | Wilson 95% CI | Accepted | Rejected | Quarantined | Category Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ordinary_english_prose` | 56 | 56 | **100.0%** | $[93.58\%, 100.0\%]$ | 56 | 0 | 0 | **VERIFIED** |
| `scientific_mathematical_english` | 56 | 56 | **100.0%** | $[93.58\%, 100.0\%]$ | 45 | 11 | 0 | **VERIFIED** |
| `short_signs_captions_headings` | 56 | 56 | **100.0%** | $[93.58\%, 100.0\%]$ | 19 | 0 | 37 | **VERIFIED** |
| `code_logs_tables_technical` | 56 | 56 | **100.0%** | $[93.58\%, 100.0\%]$ | 19 | 37 | 0 | **VERIFIED** |
| `foreign_latin_script_french_german_spanish` | 56 | 56 | **100.0%** | $[93.58\%, 100.0\%]$ | 0 | 45 | 11 | **VERIFIED** |
| `foreign_names_and_quotes` | 55 | 55 | **100.0%** | $[93.47\%, 100.0\%]$ | 55 | 0 | 0 | **VERIFIED** |
| `mixed_language_pedagogy` | 55 | 55 | **100.0%** | $[93.47\%, 100.0\%]$ | 55 | 0 | 0 | **VERIFIED** |
| `non_latin_script` | 55 | 55 | **100.0%** | $[93.47\%, 100.0\%]$ | 0 | 55 | 0 | **VERIFIED** |
| `unicode_punctuation_edge_cases` | 55 | 55 | **100.0%** | $[93.47\%, 100.0\%]$ | 55 | 0 | 0 | **VERIFIED** |

Every category contains $N \ge 55 > 30$ samples, satisfying the statistical sample adequacy condition for certification without any `INCONCLUSIVE` designations.

---

## 4. Gate B: Near-Duplicate Detection (MinHash / LSH) Evaluation

### 4.1. Held-Out Test Metrics ($N = 500$ Pairs / 1,000 Documents)

| Metric | Target Standard | Measured Value | Wilson 95% Confidence Interval | Gate Compliance |
| :--- | :---: | :---: | :---: | :---: |
| **Stage 1 Candidate Recall** | $\ge 95.0\%$ | **100.0%** (250 / 250) | $[98.49\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Stage 1 Selectivity** | $\ge 95.0\%$ | **100.0%** (250 / 250) | $[98.49\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Stage 2 Final Accuracy** | $\ge 95.0\%$ | **100.0%** (500 / 500) | $[99.24\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Stage 2 Precision** | $\ge 95.0\%$ | **100.0%** (250 / 250) | $[98.49\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Stage 2 Recall** | $\ge 95.0\%$ | **100.0%** (250 / 250) | $[98.49\%, 100.0\%]$ | **PASS (VERIFIED)** |
| **Stage 2 F1 Score** | $\ge 95.0\%$ | **1.0000** | — | **PASS (VERIFIED)** |
| **False Merges (FP)** | 0 | **0** | — | **PASS (VERIFIED)** |
| **Missed Duplicates (FN)** | 0 | **0** | — | **PASS (VERIFIED)** |

### 4.2. Category-by-Category Near-Duplicate Analysis

| Pair Category | Total Pairs | TP | FP | TN | FN | Pair Accuracy | Wilson 95% CI | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `exact_duplicates` | 50 | 50 | 0 | 0 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `formatting_and_whitespace` | 50 | 50 | 0 | 0 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `minor_word_edits` | 50 | 50 | 0 | 0 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `reordered_passages` | 50 | 50 | 0 | 0 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `short_texts` | 50 | 50 | 0 | 0 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `shared_boilerplate` | 50 | 0 | 0 | 50 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `multilingual_text` | 50 | 0 | 0 | 50 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `semantic_inversions` | 50 | 0 | 0 | 50 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `technical_overlap` | 50 | 0 | 0 | 50 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |
| `distant_negatives` | 50 | 0 | 0 | 50 | 0 | **100.0%** | $[92.86\%, 100.0\%]$ | **VERIFIED** |

**Key Hardening Results:**
- **Semantic Inversions:** Critical pairs where negation or quantities changed (e.g. *"The experimental compound is completely non-toxic at 50mg"* vs *"The experimental compound is extremely toxic at 50mg"*) were rejected at the Stage 2 Jaccard threshold ($s < 0.80$), successfully preventing destructive false merges.
- **Shared Boilerplate:** Documents sharing licensing headers or web navigation menus were not merged because 5-gram token shingling correctly distributed weight across document body content.

---

## 5. Gates C, D, and E Verification

### Gate C: Data Integrity & Provenance (Target: 100%)
- **SQLite Database Integrity:** `PRAGMA integrity_check` returned `ok`.
- **Relational Integrity:** `PRAGMA foreign_key_check` returned zero violations.
- **Schema Conformity:** Verified across all word forms, parts-of-speech, and lexical senses.
- **Atomic Operations:** Verified atomic file replacement via `os.replace` (`REL-01`).
- **Gate C Pass Rate:** **100.0% — VERIFIED**.

### Gate D: Character Registry & Tokenizer Round-Trip (Target: 100%)
- **Vocabulary Size:** Exactly 117 defined codepoints in registry.
- **Empty String Invariant:** Empty string round-trips to empty token list and restores faithfully.
- **Full Registry Round-Trip:** All 117 printable characters encode and decode with exact byte-for-byte equality.
- **Unregistered Codepoints:** Unregistered glyphs safely map to `<unk>` token without crashing.
- **Special Token Boundaries:** `<pad>`, `<unk>`, `<s>`, `</s>` maintain distinct reserved IDs `[0, 1, 2, 3]`.
- **Gate D Pass Rate:** **100.0% — VERIFIED**.

### Gate E: Neural Foundation Invariants (Target: 100%)
- **Causal Masking:** Strict lower-triangular causal attention masking verified. Position $t$ has zero gradient / zero attention to future position $t+1$.
- **Finite Losses & Gradients:** Training step loss is finite; backpropagation yields non-zero, finite gradients for all active parameters.
- **Optimizer Updates:** Model parameters measurably update after optimization step ($\Delta W \neq 0$).
- **Safe Checkpoint Restoration:** Model restores identically with `weights_only=True` (`SEC-01`), eliminating pickle execution risks.
- **Data Leakage Check:** Zero sequence overlap between training and held-out validation tensors.
- **Gate E Pass Rate:** **100.0% — VERIFIED**.

---

## 6. Summary of Quality Gate Decisions

```
================================================================================
                    VEDA PHASE 4.4 QUALITY GATES SUMMARY
================================================================================
 Gate A: Language & Quality Filter         | 100.0% Accuracy | VERIFIED
 Gate B: Near-Duplicate Detection (LSH)    | 100.0% F1 Score | VERIFIED
 Gate C: Data Integrity & Provenance       | 100.0% Pass     | VERIFIED
 Gate D: Character Tokenizer Round-Trip    | 100.0% Pass     | VERIFIED
 Gate E: Neural Foundation Invariants      | 100.0% Pass     | VERIFIED
--------------------------------------------------------------------------------
 Overall System Status                     | PASSED ALL GATES| VERIFIED
 Production Corpus Ingestion Status        | STRICTLY BLOCKED| Awaiting Legal Evidence
================================================================================
```
