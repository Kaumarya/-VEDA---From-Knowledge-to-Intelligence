# VEDA — Phase 4.6: Comprehensive Defect Inventory & Code Audit

**Document:** `docs/veda_phase4.6_defect_inventory.md`  
**Date:** October 15, 2026  
**Status:** Certified & Implemented  
**Standardized Interpreter:** Python 3.14.8 AMD64 (`.venv\Scripts\python.exe`)  
**Baseline System Environment:** Python 3.9.13 AMD64 (`python.exe` / System PATH)  
**Governance Invariant:** Production Corpus Ingestion **STRICTLY BLOCKED** (Fail-Closed)

---

## 1. Overview of Defect Sweep Methodology

Section 3 of the Phase 4.6 Mission mandates an exhaustive defect sweep across the entire VEDA repository, investigating:
1. Boundary conditions, off-by-one errors, and normalization bugs.
2. Inconsistent tokenization and symbol ratios.
3. Incorrect metrics, rounding errors, and denominator calculations.
4. Data corruption, provenance tracking, and atomic file handling.
5. SQLite resource cleanup, open cursors, and interrupted transactions.
6. Checkpoint safety, atomic writes, and deserialization security (`weights_only=True`).
7. Missing type validation and misleading error messages.
8. Dependency conflicts and Python 3.14 environment-specific behavior.
9. Non-deterministic tests, ignored failures, and untested branches.
10. Stale documentation, dual-version instructions, and dead code.

---

## 2. Detailed Findings by Category

### 2.1 Near-Deduplication Semantic Safety (Stage 3 Guard)

In Phase 4.5, VEDA introduced the `SemanticSafetyGuard` to prevent lexical MinHash from falsely merging documents with critical semantic inversions (such as `10 mg` vs `100 mg`, or negation flips).

In Phase 4.6, systematic audit of near-duplicate failure modes revealed four critical coverage gaps:

1. **Time Units (`DEF-4.6-01`):**  
   *Problem:* Texts differing in time duration (e.g. `"Reaction time was 10 s"` vs `"Reaction time was 10 min"`, or `"Allowed wait is 15 min"` vs `"Allowed wait is 15 hr"`) were merged because `UNIT_FACTORS` only covered mass, length, volume, and data rate.  
   *Fix:* Added canonical time units (`s`, `sec`, `min`, `hr`, `day`) with exact conversion ratios (`s: 1.0`, `min: 60.0`, `hr: 3600.0`, `day: 86400.0`). Non-equivalent conversions flag conflict and block merging.

2. **Storage and Byte Multipliers (`DEF-4.6-02`):**  
   *Problem:* Memory and storage allocations differing by scale (e.g. `"Max buffer size is 16 MB"` vs `"Max buffer size is 16 GB"`) were merged.  
   *Fix:* Added binary and decimal storage units (`b`, `kb`, `mb`, `gb`, `tb`, `kib`, `mib`, `gib`, `tib`) with exact byte conversion factors to `SemanticSafetyGuard`.

3. **Comparison and Range Threshold Antonyms (`DEF-4.6-03`):**  
   *Problem:* Sentences sharing identical numerical quantities but having antonymic comparison thresholds (e.g. `"Patient temperature was at least 38 C"` vs `"Patient temperature was at most 38 C"`, or `"Yield was greater than 80%"` vs `"Yield was less than 80%"`) bypassed the negation guard because neither used grammatical negations (`not`, `never`).  
   *Fix:* Introduced `COMPARISON_ANTONYMS` map (`greater` vs `less`, `at least` vs `at most`, `minimum` vs `maximum`, `above` vs `below`, `exceed` vs `subceed/fall below`). The guard detects conflicting directional modifiers applied to identical contexts and blocks merging.

4. **Entity and Identifier Conflicts (`DEF-4.6-04`):**  
   *Problem:* Documents referring to distinct entities via alphanumeric identifiers (e.g. `"Patient ID-9021"` vs `"Patient ID-9022"`, `"Model VEDA-7B"` vs `"Model VEDA-13B"`, or `"CVE-2024-1234"` vs `"CVE-2024-5678"`) have $>90\%$ lexical Jaccard similarity and were merged.  
   *Fix:* Added `check_identifier_conflict` and `IDENTIFIER_PATTERN` to extract uppercase/hyphenated entity codes and flag conflict when distinct identifiers are present.

### 2.2 Language & Quality Filtering (Task A)

1. **Latin Homograph Collision with English Stopword `"has"` (`DEF-4.6-05`):**  
   *Problem:* In Latin texts, `"has"` is the accusative feminine plural demonstrative pronoun. In earlier versions, `"has"` was treated unconditionally as an English auxiliary verb, allowing certain Latin sentences with high cognate density to pass into English acceptance.  
   *Fix:* Added `"has"` to `_AMBIGUOUS_COGNATE_STOPWORDS` and implemented Rule A2 checking for Romance/Latin cognate markers (`_ROMANCE_COGNATES`, `_FOREIGN_COGNATES`), ensuring foreign Latin-script texts are routed to `QUARANTINE` or `REJECT`.

2. **Academic Figure Captions Stopword Sparsity (`DEF-4.6-06`):**  
   *Problem:* Highly formal scientific figure captions (e.g. `"Figure 15: Pressure-volume isotherm showing liquid-gas critical point behavior during supercritical compression at 350 K."`) contain dense technical nomenclature with zero standard English conversational stopwords (`the`, `is`, `a`). They were prematurely rejected by `QualityFilter` as `NO_ENGLISH_STOPWORDS`.  
   *Fix:* Added formal caption prefix detection (`_CAPTION_PATTERN`: `Figure`, `Fig.`, `Table`, `Plate`, `Scheme`, `Diagram`) with alphabetic ratio validation ($\ge 0.70$) in `classify_with_quarantine` before stopword-count rejection.

3. **Structured SQL and Imperative Signage Misclassified (`DEF-4.6-07`):**  
   *Problem:* Structured SQL code (`SELECT * FROM users WHERE status = 'active'`) and imperative safety signage (`Caution: High Voltage Overhead. Do not touch bare conductors.`) were hitting `QualityFilter` before reaching `classify_with_quarantine` quarantine routing, triggering `NO_ENGLISH_STOPWORDS` or `HIGH_SYMBOL_RATIO` and getting marked `REJECT`.  
   *Fix:* Re-ordered classification flow in `classify_with_quarantine` so that structured SQL syntax (`_SQL_PATTERN`) and signage prefixes (`Caution:`, `Warning:`, `Alert:`, `Notice:`) are evaluated *before* the general prose quality filter, safely routing them to `QUARANTINE`.

### 2.3 Neural Architecture & Checkpoint Management

1. **Neural Checkpoint Persistence Missing Safe Save/Load (`DEF-4.6-08`):**  
   *Problem:* `CausalLM` in `foundation/model/transformer.py` lacked standardized, atomic checkpoint serialization and safe deserialization methods. Developers had to use ad-hoc `torch.save` calls, risking partial writes on process termination and unsafe unpickling.  
   *Fix:* Implemented `save_checkpoint(filepath)` using an atomic temporary file (`.tmp.pt` + `os.replace`) and `load_checkpoint(filepath, map_location)` enforcing `weights_only=True` (`SEC-01` compliance).

---

## 3. Formal Machine-Readable Defect Inventory

| Defect ID | Title | Severity | Reproducibility | Root Cause | Fix Status | Verification Reference |
| :--- | :--- | :---: | :---: | :--- | :---: | :--- |
| **`DEF-4.6-01`** | Time Unit Conflict Missed in Near-Dedup | **HIGH** | 100% | `SemanticSafetyGuard` lacked duration unit conversions (`s`, `min`, `hr`, `day`). | **FIXED** | `tests/test_near_deduplication_safety.py::test_time_unit_conflict_blocks_merge` |
| **`DEF-4.6-02`** | Storage Unit Conflict Missed in Near-Dedup | **HIGH** | 100% | `SemanticSafetyGuard` lacked storage/byte multiplier factors (`KB`, `MB`, `GB`, `KiB`). | **FIXED** | `tests/test_near_deduplication_safety.py::test_storage_unit_conflict_blocks_merge` |
| **`DEF-4.6-03`** | Comparison Threshold Antonyms Unchecked | **HIGH** | 100% | Antonymic modifiers (`at least` vs `at most`, `greater` vs `less`) not checked by negation guard. | **FIXED** | `tests/test_near_deduplication_safety.py::test_comparison_threshold_antonyms_blocks_merge` |
| **`DEF-4.6-04`** | Entity / Identifier Conflict Unchecked | **HIGH** | 100% | Distinct alphanumeric entity IDs (`ID-9021` vs `ID-9022`) merged due to high lexical Jaccard. | **FIXED** | `tests/test_near_deduplication_safety.py::test_identifier_conflict_blocks_merge` |
| **`DEF-4.6-05`** | Latin Homograph `"has"` Stopword Collision | **MODERATE** | 100% | Latin demonstrative `"has"` treated as English auxiliary verb stopword. | **FIXED** | `scripts/evaluate_phase46_standardization.py` (v4.0 Test Split) |
| **`DEF-4.6-06`** | Technical Figure Caption Stopword Sparsity | **MODERATE** | 100% | Formal scientific captions with zero stopwords rejected by `QualityFilter`. | **FIXED** | `tests/test_language_filter_hardening.py::test_academic_figure_caption_accepted` |
| **`DEF-4.6-07`** | SQL and Signage Prematurely Rejected | **MODERATE** | 100% | Structured SQL and signage failed quality filter before reaching quarantine routing. | **FIXED** | `foundation/corpus/language_audit.py::classify_with_quarantine` |
| **`DEF-4.6-08`** | Missing Atomic Checkpoint Save/Load in `CausalLM` | **MODERATE** | 100% | Ad-hoc checkpoint saving risked non-atomic writes and unsafe unpickling. | **FIXED** | `tests/test_neural_foundation.py::test_causal_lm_checkpoint_save_and_load` |

---

## 4. Regression Test Suite Expansion

In Phase 4.6, the test suite was expanded from **254 tests to 258 tests** (+4 new regression tests):

1. `test_time_unit_conflict_blocks_merge`: Confirms that `10 s` vs `10 min` triggers unit conflict and blocks merge.
2. `test_storage_unit_conflict_blocks_merge`: Confirms that `16 MB` vs `16 GB` triggers unit conflict and blocks merge.
3. `test_comparison_threshold_antonyms_blocks_merge`: Confirms that `at least 38 C` vs `at most 38 C` triggers comparison antonym conflict and blocks merge.
4. `test_identifier_conflict_blocks_merge`: Confirms that `ID-9021` vs `ID-9022` triggers entity identifier conflict and blocks merge.
5. In addition, existing test `test_causal_lm_checkpoint_save_and_load` in `tests/test_neural_foundation.py` was extended to test atomic temporary file replacement and safe `weights_only=True` deserialization.

---

## 5. Items Intentionally Left Unresolved & Project Scope Boundaries

In strict compliance with VEDA Phase 4.6 Mission Section 5:

1. **Production Corpus Ingestion Gate Remains Strictly Blocked:**  
   Ingestion into the production pretraining bundle remains blocked until publisher licensing agreements, legal documentation, and external provenance verification are formally certified (`tests/test_corpus_production_gate_fail_closed.py`).
2. **From-Scratch Architecture Preservation:**  
   No external pretrained LLM checkpoints, hosted APIs, or pre-trained weights were introduced. VEDA maintains 100% architectural independence.
3. **Downstream Training Phases Deferred:**  
   Large-scale pretraining, instruction tuning, RAG pipelines, and chat UI development remain reserved for subsequent project phases.
