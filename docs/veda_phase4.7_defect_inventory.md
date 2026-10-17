# VEDA PHASE 4.7: COMPREHENSIVE DEFECT INVENTORY & REMEDIATION LOG

**Project**: VEDA — “From Knowledge to Intelligence”  
**Phase**: 4.7  
**Date**: October 15, 2026  
**Primary Runtime**: Python 3.14.8 AMD64  

---

## 1. Overview of Defect Management

In Phase 4.7, seven defects (`DEF-4.7-01` through `DEF-4.7-07`) were formally investigated, reproduced, remediated, and locked with regression tests in accordance with Section 13 of the Engineering Specification.

All remediations followed the principle of minimal surgical intervention: preserving existing documentation and comments, maintaining backward compatibility, and avoiding uncontrolled refactoring.

---

## 2. Defect Register

### DEF-4.7-01: Foreign Latin-Script Figure Caption Bypass
- **Severity**: **HIGH**
- **Affected File & Function**: `foundation/corpus/language_audit.py::QualityFilter.evaluate_text`
- **Reproduction**:
  Input: `"Figure 3: Représentation schématique du cycle cellulaire chez les eucaryotes."`
- **Expected Behavior**: Quarantined or rejected as French prose.
- **Actual Behavior (Before Fix)**: Accepted as valid English prose (`decision = "ACCEPT"`).
- **Root Cause**: An unrestricted `_CAPTION_PATTERN` regex (`r"^(?:Figure|Fig\.?|Table)\s+\d+[:.]"`) accepted any sentence with a figure prefix, assuming it was English, despite containing French cognates without English stopwords.
- **Minimal Justified Fix**: Updated caption handling to inspect linguistic content. If caption contains non-English cognates and lacks English stopwords, it is not exempted and routes to quarantine/rejection.
- **Regression Test**: `tests/test_language_filter_hardening.py::test_foreign_figure_captions_not_bypassed_as_english`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_language_filter_hardening.py -k test_foreign_figure_captions_not_bypassed_as_english`
- **Result After Fix**: **VERIFIED PASS** (French caption correctly routed to `QUARANTINE` or `REJECT`).
- **Remaining Risk**: Extremely short multi-lingual technical captions (e.g., `"Fig 1: DNA"`) may require custom heuristic rules.

---

### DEF-4.7-02: English Verb-Initiated Prose Falsely Quarantined as SQL
- **Severity**: **HIGH**
- **Affected File & Function**: `foundation/corpus/language_audit.py::QualityFilter.evaluate_text`
- **Reproduction**:
  Input: `"Select an option from the main menu to begin configuring your environment."`
- **Expected Behavior**: Accepted as ordinary English imperative prose.
- **Actual Behavior (Before Fix)**: Falsely routed to `QUARANTINE` with reason `technical_or_code_snippet`.
- **Root Cause**: Overly broad `_SQL_PATTERN` (`r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b"`) checked only the initial verb without checking for SQL-specific structural clauses (`FROM`, `WHERE`, `INTO`, `TABLE`).
- **Minimal Justified Fix**: Hardened SQL regex to require a supporting clause (e.g., `SELECT ... FROM`, `INSERT INTO`, `CREATE TABLE`) before flagging as SQL.
- **Regression Test**: `tests/test_language_filter_hardening.py::test_english_imperative_verbs_not_flagged_as_sql`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_language_filter_hardening.py -k test_english_imperative_verbs_not_flagged_as_sql`
- **Result After Fix**: **VERIFIED PASS** (Imperative English prose correctly accepted).
- **Remaining Risk**: None identified.

---

### DEF-4.7-03: Physical Unit / Dimensional Mismatch Bypass
- **Severity**: **CRITICAL**
- **Affected File & Function**: `foundation/corpus/near_deduplication.py::NearDuplicateSafetyGuard.is_safe_to_merge`
- **Reproduction**:
  Input Pair:
  - Text A: `"The patient was administered 10 meters of saline solution."`
  - Text B: `"The patient was administered 10 grams of saline solution."`
- **Expected Behavior**: Merge blocked due to physical dimension incompatibility (Length vs Mass).
- **Actual Behavior (Before Fix)**: `is_safe_to_merge` returned `True` (False Merge occurred).
- **Root Cause**: Safety guard compared scalar magnitudes after base conversion (`vals_a == vals_b`). Since $10 == 10$, scalar comparison passed, but dimensional base unit (`meter` vs `gram`) was completely ignored!
- **Minimal Justified Fix**: Added `PHYSICAL_BASE_UNITS` mapping and verified base dimensions before scalar comparison. If dimensions differ, guard returns `(False, "UNIT_MISMATCH")`.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_physical_unit_dimension_mismatch_blocks_merge`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_physical_unit_dimension_mismatch_blocks_merge`
- **Result After Fix**: **DEFECT FIXED AND RETESTED** (Zero false merges on dimensional mismatches).
- **Remaining Risk**: Obscure imperial unit conversions (e.g. furlongs, hogsheads) are not in base unit dictionary; they fall back to count.

---

### DEF-4.7-04: Calendar Month Discrepancies Bypassing Date Guard
- **Severity**: **HIGH**
- **Affected File & Function**: `foundation/corpus/near_deduplication.py::NearDuplicateSafetyGuard.check_date_conflict`
- **Reproduction**:
  Input Pair:
  - Text A: `"The event occurred on March 15, 2024."`
  - Text B: `"The event occurred on November 15, 2024."`
- **Expected Behavior**: Merge blocked due to temporal discrepancy.
- **Actual Behavior (Before Fix)**: `check_date_conflict` returned `False` (safe to merge).
- **Root Cause**: `check_date_conflict` extracted 4-digit years only (`\b(?:19|20)\d{2}\b`). Since both contained `2024`, no conflict was detected.
- **Minimal Justified Fix**: Added month name extraction (`MONTH_PATTERN`). If both texts contain recognized months and the month sets are disjoint, guard flags a date conflict.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_calendar_month_conflict_blocks_merge`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_calendar_month_conflict_blocks_merge`
- **Result After Fix**: **DEFECT FIXED AND RETESTED** (Calendar month discrepancies reliably blocked).
- **Remaining Risk**: Numeric month formats (e.g. `03/15/2024` vs `15/03/2024`) require US vs UK date parsing context.

---

### DEF-4.7-05: Non-Unit English Function Words Extracted as Units
- **Severity**: **MEDIUM**
- **Affected File & Function**: `foundation/corpus/near_deduplication.py::NearDuplicateSafetyGuard._extract_quantities`
- **Reproduction**:
  Input Pair:
  - Text A: `"The house features 5 different bedrooms."`
  - Text B: `"The house features 5 separate bedrooms."`
- **Expected Behavior**: Safe to merge (valid near-duplicate).
- **Actual Behavior (Before Fix)**: Merge blocked due to spurious unit conflict (`different` vs `separate`).
- **Root Cause**: Quantity regex accepted arbitrary following tokens as "units".
- **Minimal Justified Fix**: Strictly constrained recognized units to keys in `UNIT_TO_BASE`. Any non-unit word defaults safely to `"count"`.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_non_unit_word_extraction`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_non_unit_word_extraction`
- **Result After Fix**: **DEFECT FIXED AND RETESTED** (Non-unit words normalized to count; valid near-duplicates permitted).
- **Remaining Risk**: None identified.

---

### DEF-4.7-06: Atomic Checkpoint Tempfile Abandonment Risk
- **Severity**: **MEDIUM**
- **Affected File & Function**: `foundation/model/transformer.py::CausalLM.save_checkpoint`
- **Reproduction**:
  Triggering an exception during `torch.save` left a lingering `.tmp` file in the destination folder without cleaning up, risking filename collisions across concurrent processes.
- **Expected Behavior**: Isolated temp files with automatic cleanup on failure.
- **Actual Behavior (Before Fix)**: Hardcoded `.tmp` filename, no PID isolation, unhandled exceptions left orphan files.
- **Minimal Justified Fix**: Temp file format changed to `.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.pt`. Wrapped serialization in `try...finally` with `unlink(missing_ok=True)`.
- **Regression Test**: `tests/test_neural_foundation.py::test_causal_lm_save_checkpoint_failure_cleanup`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_neural_foundation.py -k test_causal_lm_save_checkpoint_failure_cleanup`
- **Result After Fix**: **DEFECT FIXED AND RETESTED** (Temp files cleaned up reliably; atomic durability verified).
- **Remaining Risk**: Underlying OS filesystem must support atomic rename (`os.replace`).

---

### DEF-4.7-07: Benchmark Template Leakage & Contamination
- **Severity**: **HIGH**
- **Affected Files**: `scripts/build_phase46_datasets.py`, `data/corpus/eval_language_dataset_v4.json`, `data/corpus/eval_near_dedup_dataset_v4.json`
- **Reproduction**:
  Inspection of v4.0 dataset showed repeated templates with indexed suffixes (`Batch run index {i+1}`).
- **Expected Behavior**: Evaluators use diverse, non-templated samples with disjoint author provenance.
- **Actual Behavior (Before Fix)**: Synthetic loop templates allowed memorization and false 100% scores.
- **Minimal Justified Fix**: Reclassified v4.0 as a development/regression set. Created `scripts/build_phase47_independent_datasets.py` and generated independent benchmark v5.0.
- **Regression Test**: `scripts/evaluate_phase47_certification.py`
- **Verification Command**: `.venv\Scripts\python.exe scripts/evaluate_phase47_certification.py`
- **Result After Fix**: **DEFECT FIXED AND RETESTED** (Independent benchmark established and hashed).
- **Remaining Risk**: Finite sample size ($N=50$) requires continuing expansion in future phases.
