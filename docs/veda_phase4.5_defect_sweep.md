# VEDA — Phase 4.5: Comprehensive Defect Sweep & Forensic Reliability Audit

**Document:** `docs/veda_phase4.5_defect_sweep.md`  
**Author:** VEDA Quality Engineering & Architecture  
**Status:** Certified & Implemented  
**Scope:** Repository-wide audit covering all modules, pipelines, tests, and configurations  

---

## 1. Overview of Defect Sweep Methodology

Section 3 of the Phase 4.5 Mission mandates a comprehensive small-issue and regression sweep across every relevant module in the repository. The audit executed systematic static and dynamic inspections evaluating boundary conditions, error handling, atomic resource management, input edge cases, data structures, and cross-Python environment parity.

---

## 2. Checklist Findings by Category

### 2.1. Boundary Conditions & Off-by-One Checks
- **Audited Modules:** `foundation/corpus/filtering.py`, `foundation/corpus/segmentation.py`, `foundation/corpus/near_deduplication.py`.
- **Finding:** In `QualityFilter`, short text boundary threshold logic was examined. For short texts ($10 \le \text{word\_count} < 15$), required stopword count is 1; for texts $\ge 15$ words, required stopword count is 2. The boundary condition operates deterministically as intended.
- **Action Taken:** Preserved calibrated thresholds; hardened caption length boundaries ($\text{word\_count} \ge 6$) to accommodate concise, technical 6-word figure labels.

### 2.2. Acceptance, Rejection, Quarantine & Fallback Behaviors
- **Audited Modules:** `foundation/corpus/language_audit.py`, `foundation/corpus/filtering.py`.
- **Defects Identified:**
  - `DEFECT-4.5-02`: Academic captions (`Figure 3...`) quarantined as cognate risks due to low stopword density.
  - `DEFECT-4.5-03`: German prose with cognates blindly rejected as `NO_ENGLISH_STOPWORDS` instead of routed to `QUARANTINE`.
- **Action Taken:** Fixed both defects with general linguistic rules (`_CAPTION_PATTERN`, `_GERMANIC_COGNATES`, `_AMBIGUOUS_COGNATE_STOPWORDS`).

### 2.3. Empty Input, Whitespace-Only Input, and Malformed Input
- **Audited Modules:** `foundation/corpus/normalization.py`, `foundation/corpus/filtering.py`.
- **Defect Identified (`DEFECT-4.5-04`):** Passing whitespace-only strings (e.g. `" "*60`) previously bypassed `EMPTY_TEXT` because `char_length` was computed before trimming, triggering `TOO_SHORT_WORDS` instead.
- **Action Taken:** Updated `QualityFilter.evaluate()` to check `if metrics.char_length == 0 or not normalized_text.strip(): return EMPTY_TEXT`.

### 2.4. Unexpected Data Types & Type Safety
- **Audited Modules:** `TextNormalizer`, `QualityFilter`, `classify_with_quarantine`.
- **Defect Identified (`DEFECT-4.5-05`):** Passing non-string objects (`None`, `int`, `bytes`, `dict`) caused unhandled `AttributeError` or unexpected behavior downstream.
- **Action Taken:** Added explicit defensive assertions: `if not isinstance(text, str): raise TypeError(...)` across all input entry points.

### 2.5. Unsafe File Handling, Atomic Writes & Interrupted Operations
- **Audited Modules:** `foundation/lexicon/storage.py`, `foundation/model/transformer.py`.
- **Defect Identified (`DEFECT-4.5-06`):** In `SqliteLexiconBuilder.build()`, if an exception occurred during batch insertion, the SQLite connection remained open and the temporary database (`.tmp.sqlite`) was left uncleaned.
- **Action Taken:** Encapsulated batch insertion lifecycle in a `try...finally` block with guaranteed connection closure and temp DB unlinking on failure. Checkpoint serialization continues using safe dictionary structures with `weights_only=True` restoration (`SEC-01`).

### 2.6. Denominator Calculations, Rounding & Metric Aggregation
- **Audited Modules:** `foundation/corpus/near_deduplication.py`, `scripts/evaluate_phase45_accuracy_recovery.py`.
- **Verification:** Audited denominator consistency. The Phase 4.4 clerical carryover ($203$ vs $196$) was thoroughly analyzed in Phase 4.4.1. All Phase 4.5 evaluations compute denominators directly from raw prediction counts without hardcoded constants.

### 2.7. Determinism & Ordering Stability
- **Audited Modules:** `MinHashLSHCandidateDetector`, `CharacterTokenizer`, `CausalLM`.
- **Verification:** Deterministic hash seeds (`seed=42`) and stable dictionary key ordering ensure bit-for-bit reproducible MinHash signatures, candidate sets, and tokenizer outputs. PyTorch manual seeds ensure deterministic transformer output.

### 2.8. Cross-Python Environment Parity
- **Environments Tested:** Python 3.14.8 (`.venv`) and Python 3.9.13 (System ML environment).
- **Verification:** All 254 unit and regression tests pass identically across both versions with zero platform-specific divergence.

---

## 3. Formal Machine-Readable Defect Inventory

| Defect ID | Title | Severity | Reproducibility | Root Cause | Fix Status | Test Reference | Residual Risk |
| :--- | :--- | :---: | :---: | :--- | :---: | :--- | :--- |
| **DEFECT-4.5-01** | Near-Dedup Lexical MinHash Single-Token Inversion False Merge | **CRITICAL** | 100% | Lexical character MinHash is invariant to single-token flips in long documents ($\Delta J < 5\%$). | **FIXED** | `test_near_deduplication_safety.py::test_numerical_inversion_dosage_10mg_vs_100mg` | Low; domain-specific non-SI units deferred to Phase 5. |
| **DEFECT-4.5-02** | Scientific Academic Caption Quarantined | **MODERATE** | 100% | Academic captions heavy in noun phrases have low stopword density ($1$ stopword), triggering cognate quarantine. | **FIXED** | `test_language_filter_hardening.py::test_academic_figure_caption_accepted` | Negligible. |
| **DEFECT-4.5-03** | Germanic Cognate Text Blindly Rejected | **MODERATE** | 100% | `QualityFilter` rejected text with $\ge 15$ words and $1$ stopword as `NO_ENGLISH_STOPWORDS` at step 1 before reaching quarantine. | **FIXED** | `test_language_filter_hardening.py::test_german_sentence_routed_to_quarantine` | Negligible. |
| **DEFECT-4.5-04** | Whitespace-Only Text Inconsistently Categorized | **MINOR** | 100% | `char_length` was evaluated before stripping, causing whitespace strings to report `TOO_SHORT_WORDS` instead of `EMPTY_TEXT`. | **FIXED** | `test_language_filter_hardening.py::test_whitespace_only_evaluated_as_empty_text` | Zero. |
| **DEFECT-4.5-05** | Missing Type Validation on Non-String Inputs | **MINOR** | 100% | Missing defensive `isinstance(text, str)` assertions in `TextNormalizer` and `QualityFilter`. | **FIXED** | `test_language_filter_hardening.py::test_type_validation_on_non_string_inputs` | Zero. |
| **DEFECT-4.5-06** | Resource Leak Risk on Interrupted Lexicon Build | **MINOR** | Reproducible on error | Unhandled exception during batch build left connection unclosed and temp DB unlinked. | **FIXED** | `tests/test_sqlite_storage.py` | Zero. |

---

## 4. Items Intentionally Left Unresolved & Project Scope Boundaries

In accordance with Section 7 of the Phase 4.5 Mission, the following items are **intentionally preserved or deferred**:

1. **Production Corpus Ingestion Gate Remains Strictly Blocked:**  
   Ingestion into the pretraining bundle remains blocked until publisher licensing agreements, legal documentation, and external provenance verification are formally certified.
2. **From-Scratch Architecture Preservation:**  
   No external pretrained LLM checkpoints, hosted APIs, or pre-trained weights were introduced. VEDA maintains strict independence.
3. **Downstream LLM Training Phases Deferred:**  
   Token pretraining, multi-billion token training loops, instruction tuning, RAG systems, and UI components remain deferred to Phases 5, 6, and 7.
4. **Domain-Specific Non-SI Unit Extensions:**  
   Historical non-SI measurement units (e.g. apothecaries' minims, fluid scruples) are not in the primary training corpus and will be addressed during specialized domain tokenization in Phase 5.
