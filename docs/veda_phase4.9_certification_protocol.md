# VEDA PHASE 4.9: BLIND FINAL CERTIFICATION PROTOCOL
**Master Specification for Sealed v7.0 Certification Suite & Independence Verification**

- **Project**: VEDA — “From Knowledge to Intelligence”
- **Phase**: 4.9 (Blind Final Certification Preparation)
- **Date**: October 17, 2026
- **Primary Runtime**: Python 3.14.8 AMD64 (`.venv\Scripts\python.exe`)
- **Baseline Runtime**: Python 3.9.13 (Global Installation)
- **Status**: **FROZEN PROTOCOL SPECIFICATION**

---

## 1. Objectives & Architectural Boundaries

Phase 4.9 formalizes the transition from development calibration to blind certification. 

### Mandatory Operating Principles
1. **Retirement of Prior Benchmarks**: Benchmark suites v3.0, v4.0, v5.0, and v6.0 are permanently retired as **development and regression suites**. They must never be described or utilized as independent final tests.
2. **Prohibition of Metric Gaming**: No changes to classifiers, regex patterns, or heuristic thresholds may be made to artificially inflate scores on observed evaluation sets.
3. **Strict Information Hiding**: The v7.0 held-out test split must remain sealed and inaccessible to rule developers during classifier maintenance.
4. **Honest Gate F Accounting**: If genuine external third-party authoring cannot be verified, Gate F (Benchmark Independence) must be marked **UNVERIFIED**. Universal real-world accuracy must never be claimed.
5. **Phase 5 Hold**: Production corpus ingestion, pretraining, RAG, and UI development remain strictly prohibited.

---

## 2. Benchmark v7.0 Structural Design

The v7.0 suite is partitioned into two disjoint splits for each task:
- **Development Split**: Used for calibration, error analysis, and regression monitoring.
- **Held-Out Sealed Test Split**: Sealed evaluation target evaluated once under frozen classifier conditions.

### 2.1 Task A: Language Identification & Quality Filtering (`eval_language_dataset_v7.json`)
- **Total Samples**: 120 (60 Development, 60 Sealed Test).
- **Label Distribution per Split**: 30 `ACCEPT`, 20 `QUARANTINE`, 10 `REJECT` (Balanced 50% / 33.3% / 16.7%).
- **Predefined Categories (11 Total)**:

| Category | Split Dev | Split Test | Expected Outcome | Rationale / Description |
| :--- | :---: | :---: | :---: | :--- |
| `ordinary_english_prose` | 10 | 10 | `ACCEPT` | Fluent narrative/historical English with authentic stopword distribution. |
| `expository_academic_prose` | 10 | 10 | `ACCEPT` | Formal scientific/academic exposition across physics, law, geology, biology. |
| `scientific_figure_captions` | 5 | 5 | `ACCEPT` | Formal academic captions starting with Figure/Table/Chart/Diagram prefixes. |
| `foreign_names_and_quotes` | 5 | 5 | `ACCEPT` | Fluent English containing loanwords, Latin legal maxims, or German philosophy. |
| `code_sql_structured_data` | 5 | 5 | `QUARANTINE` | Coherent SQL queries, database schema definitions, and programmatic statements. |
| `imperative_signage_notices` | 5 | 5 | `QUARANTINE` | Terse industrial warning signage (DANGER, CAUTION, WARNING, NOTICE, ALERT). |
| `short_headings_and_fragments` | 5 | 5 | `QUARANTINE` | Isolated section/chapter/appendix titles (<12 words, low stopword density). |
| `germanic_latin_prose` | 5 | 5 | `QUARANTINE` | Coherent German and Dutch natural language prose sharing Latin script. |
| `romance_latin_prose` | 5 | 5 | `REJECT` | French, Spanish, Italian natural language prose without English stopwords. |
| `non_latin_script` | 2 | 2 | `REJECT` | Cyrillic, Chinese, and non-Latin alphabetic scripts. |
| `malformed_noise` | 3 | 3 | `REJECT` | Unregistered character runs, repeated symbols, and isolated letter noise. |

---

### 2.2 Task B: Near-Deduplication & Semantic Safety Guard (`eval_near_dedup_dataset_v7.json`)
- **Total Pairs**: 40 (20 Development, 20 Sealed Test).
- **Label Distribution per Split**: 8 `True` (Valid Duplicate), 12 `False` (Distinct / Safety-Critical).
- **Predefined Categories (10 Total)**:

| Category | Split Dev | Split Test | Expected Outcome | Safety Hazard / Invariant |
| :--- | :---: | :---: | :---: | :--- |
| `exact_duplicate` | 1 | 1 | `True` | Character-for-character identical text. |
| `reformatted_duplicate` | 1 | 1 | `True` | Interspersed newlines and irregular whitespace. |
| `paraphrase_duplicate` | 1 | 1 | `True` | Active vs passive grammatical voice with identical assertions. |
| `reordered_duplicate` | 1 | 1 | `True` | Reordered independent sentences with unchanged facts. |
| `unit_conversion_duplicate` | 4 | 4 | `True` | Equivalent SI and IEC binary units (meters/km, mg/g, bytes/mib, s/min). |
| `distant_negative` | 1 | 1 | `False` | Completely distinct subject domains and vocabulary. |
| `hard_negative_semantic_divergence` | 1 | 1 | `False` | High syntactic overlap with divergent institutional decisions. |
| `safety_dosage_inversion` | 1 | 1 | `False` | Critical 10x pediatric dosage discrepancy (5 mg vs 50 mg). |
| `safety_unit_mismatch` | 2 | 2 | `False` | Incompatible physical dimensions (bars vs meters, amperes vs volts). |
| `safety_date_mismatch` | 2 | 2 | `False` | Historical year conflicts (1948 vs 1952) and month conflicts. |
| `safety_polarity_inversion` | 3 | 3 | `False` | Contradictory claims (safe vs toxic, permit vs prohibit, greater vs less). |
| `safety_negation_inversion` | 1 | 1 | `False` | Asymmetric negation particles (observed vs not observed, easily vs never). |
| `safety_identifier_conflict` | 1 | 1 | `False` | Mismatching hardware/sensor serial codes (A101 vs B101). |

---

## 3. Cryptographic Provenance & Access Log

### 3.1 Dataset Checksums (SHA-256)
- **`data/corpus/eval_language_dataset_v7.json`**: `99291f7c75370abe37b7d3e2e8c0d2d7977c38c18c458cadf958f3a79ecb1a4d`
- **`data/corpus/eval_near_dedup_dataset_v7.json`**: `f44be30ccbd82af6e6ed93fdb175bdc3708c0204c26d0db69f4a6eb7f1ce1370`

### 3.2 Access & Modification Log
| Timestamp (UTC) | Action | Agent / Role | Cryptographic Integrity |
| :--- | :--- | :--- | :--- |
| `2026-10-17T15:20:00Z` | Dataset schema and domain design finalized | Independent Protocol Designer | Clean specification |
| `2026-10-17T15:21:45Z` | Generation of v7 datasets via builder script | Benchmark Generator | Hashes locked |
| `2026-10-17T15:22:10Z` | Verification of 0-overlap against prior benchmarks | Integrity Auditor | 0 matching texts found |
| `2026-10-17T15:23:00Z` | Classifier implementation frozen | Core Architecture Lead | Code locked |
| `2026-10-17T15:24:30Z` | One-shot evaluation execution on frozen v7 | Independent Evaluator | Results recorded to JSON |

---

## 4. Evaluator Freezing & Execution Protocol

The evaluator script [`scripts/evaluate_phase49_certification.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/scripts/evaluate_phase49_certification.py) enforces:
1. **Read-Only Access**: Benchmark JSON files are loaded strictly read-only.
2. **Zero In-Memory Tuning**: Heuristic parameters, stopword lists, and regex patterns in [`foundation/corpus/`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/) are immutable at runtime.
3. **Full Prediction Recording**: Every single prediction, expected label, decision reason, and candidate similarity is logged to [`data/corpus/phase4.9_eval_results.json`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/data/corpus/phase4.9_eval_results.json).

---

## 5. Independence Assessment Standards

To ensure scientific honesty:
- **Internal Structural Isolation**: Satisfied. The v7 dataset has zero sample overlap with v3, v4, v5, and v6. Classifier code was not altered after v7 evaluation results were generated.
- **External Third-Party Independence**: Not established. In the current development environment, test generation and classifier maintenance occur within the same repository infrastructure without an external third-party evaluation body.
- **Mandatory Reporting Rule**: Gate F is formally marked **UNVERIFIED**. Phase 5 remains blocked until external review occurs.
