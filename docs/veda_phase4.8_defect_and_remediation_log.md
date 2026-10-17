# VEDA PHASE 4.8: DEFECT INVESTIGATION, REMEDIATION LOG & REGRESSION REGISTER

**Project**: VEDA — “From Knowledge to Intelligence”  
**Phase**: 4.8  
**Date**: October 15, 2026  
**Primary Runtime**: Python 3.14.8 AMD64  
**Baseline Runtime**: Python 3.9.13 (Protected)  

---

## 1. Overview & Forensic Objectives

In Phase 4.8, every single error reported in `data/corpus/phase4.7_eval_results.json` was forensically analyzed down to the underlying character, token, regex, and AST execution levels. No error was dismissed or masked by aggregate metrics.

Six primary failure modes were isolated:
1. `DEF-4.8-01`: Germanic Latin text with zero English stopwords rejected instead of quarantined (`v5_test_for_043`).
2. `DEF-4.8-02`: German figure caption with zero English stopwords rejected instead of quarantined (`v5_test_forcap_046`).
3. `DEF-4.8-03`: Directional polarity inversion (`greater than` vs `less than`) masked by shared preposition `"under"` (`v5_test_pair_015`).
4. `DEF-4.8-04`: Binary storage unit `mib` missing from `UNIT_TO_BASE` (`v5_test_pair_006`).
5. `DEF-4.8-05`: Active/passive voice paraphrase rejected by rigid character-order MinHash threshold (`v5_test_pair_003`).
6. `DEF-4.8-06`: Missing standard closed-class prepositions in `_COMMON_ENGLISH_STOPWORDS` (`against`, `near`, `during`, etc.).

---

## 2. Forensic Defect Registry

### DEF-4.8-01: Germanic Latin Text with Zero English Stopwords Rejected
- **Sample ID**: `v5_test_for_043`
- **Category**: `foreign_latin_script`
- **Text**: `"De windmolens langs de polderkanalen speelden een cruciale rol bij het droogleggen van de laaggelegen landerijen."` (Dutch engineering history)
- **Ground-Truth Label**: `QUARANTINE` | **Predicted Label**: `REJECT`
- **Label Ambiguity**: Unambiguous. Dutch prose with recognized Germanic cognates (`een`, `van`, `het`) represents coherent natural language in a related European tongue; per corpus quality policy, it belongs in `QUARANTINE` for multilingual pipeline routing rather than `REJECT` (which is reserved for non-Latin scripts, corrupted bytes, and token noise).
- **Failure Mechanism**: In `foundation/corpus/language_audit.py::classify_with_quarantine`, line 703:
  `if stopword_count in (1, 2) and bool(clean_words & _GERMANIC_COGNATES):`
  Because this Dutch sentence contains zero English stopwords (`stopword_count == 0`), the condition failed. It fell through to line 712 and returned deterministic `REJECT` with reason `NO_ENGLISH_STOPWORDS`.
- **Relevant Source Function**: `foundation/corpus/language_audit.py::classify_with_quarantine`
- **Minimal Justified Fix**: Expanded the condition to:
  `if stopword_count in (0, 1, 2) and metrics.alpha_ratio >= 0.70 and metrics.non_latin_ratio == 0.0 and word_count >= 6 and bool(clean_words & _GERMANIC_COGNATES):`
- **Regression Test**: `tests/test_language_filter_hardening.py::test_dutch_sentence_with_zero_english_stopwords_quarantined`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_language_filter_hardening.py -k test_dutch_sentence_with_zero_english_stopwords_quarantined`
- **Result**: **DEFECT FIXED AND RETESTED (PASS)**

---

### DEF-4.8-02: German Figure Caption with Zero English Stopwords Rejected
- **Sample ID**: `v5_test_forcap_046`
- **Category**: `foreign_latin_script`
- **Text**: `"Abbildung 13: Gemessene Strom-Spannungs-Kennlinie der Halbleiterdiode bei Raumtemperatur."` (German semiconductor caption)
- **Ground-Truth Label**: `QUARANTINE` | **Predicted Label**: `REJECT`
- **Label Ambiguity**: Unambiguous. Contains Germanic cognates `der` and `bei` with German technical prefix `Abbildung 13:`. Belongs in `QUARANTINE`.
- **Failure Mechanism**: Like `DEF-4.8-01`, `stopword_count` was 0, so line 703 failed to trigger.
- **Relevant Source Function**: `foundation/corpus/language_audit.py::classify_with_quarantine`
- **Minimal Justified Fix**: Resolved by the `stopword_count in (0, 1, 2)` fix and adding `"bei"` to `_GERMANIC_COGNATES`.
- **Regression Test**: `tests/test_language_filter_hardening.py::test_german_caption_with_zero_english_stopwords_quarantined`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_language_filter_hardening.py -k test_german_caption_with_zero_english_stopwords_quarantined`
- **Result**: **DEFECT FIXED AND RETESTED (PASS)**

---

### DEF-4.8-03: Polarity Inversion Masked by Shared Preposition `"under"`
- **Pair ID**: `v5_test_pair_015`
- **Category**: `safety_polarity_inversion`
- **Text A**: `"The catalytic synthesis yield was recorded as greater than 80% under standardized operating parameters."`
- **Text B**: `"The catalytic synthesis yield was recorded as less than 80% under standardized operating parameters."`
- **Ground-Truth Label**: `False` (Distinct - Do Not Merge) | **Predicted Label**: `True` (False Merge)
- **Label Ambiguity**: Unambiguous. Incompatible factual claims ("greater than" vs "less than").
- **Failure Mechanism**: In `SemanticSafetyGuard.POLARITY_PAIRS`, the directional set is:
  `({"greater", "above", "exceeds", "at_least", "minimum", "more"}, {"less", "below", "under", "at_most", "maximum", "fewer"})`.
  In `check_polarity_conflict`:
  `a_has_pos = bool(words_a & pos_set)` (found `"greater"`)
  `a_has_neg = bool(words_a & neg_set)` (found `"under"`!)
  Because Text A had the preposition `"under"` in `"under standardized operating parameters"`, `a_has_neg` was `True`!
  Line 385 evaluated:
  `if (a_has_pos and not a_has_neg and b_has_neg and not b_has_pos):`
  Because `a_has_neg` was `True`, the entire polarity check was disabled!
- **Relevant Source Function**: `foundation/corpus/near_deduplication.py::SemanticSafetyGuard.check_polarity_conflict`
- **Minimal Justified Fix**: Refactored `check_polarity_conflict` to compute `diff_a = words_a - words_b` and `diff_b = words_b - words_a`. Testing polarity pairs on the *differing* words ensures that shared prepositions like `"under"` appearing in both sentences do not mask the genuine polarity flip between `"greater"` and `"less"`.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_polarity_inversion_greater_than_vs_less_than_with_preposition_under`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_polarity_inversion_greater_than_vs_less_than_with_preposition_under`
- **Result**: **DEFECT FIXED AND RETESTED (PASS - Zero False Merges)**

---

### DEF-4.8-04: Binary Storage Unit `mib` Missing from `UNIT_TO_BASE`
- **Pair ID**: `v5_test_pair_006`
- **Category**: `unit_conversion_duplicate`
- **Text A**: `"The kernel ring buffer allocated 1048576 bytes of physical RAM for storing debug trace records."`
- **Text B**: `"The kernel ring buffer allocated 1 mib of physical RAM for storing debug trace records."`
- **Ground-Truth Label**: `True` (Valid Unit Duplicate) | **Predicted Label**: `False` (Missed Duplicate)
- **Label Ambiguity**: Unambiguous. $1\text{ MiB} = 2^{20}\text{ bytes} = 1048576\text{ bytes}$.
- **Failure Mechanism**: In `SemanticSafetyGuard.UNIT_TO_BASE`, `kib` ($1024$) and `gib` ($1073741824$) were defined, but `mib` was missing. When parsing `"1 mib"`, the unit defaulted to `"count"`, creating a spurious numerical mismatch between `1048576.0 b` and `1.0 count`.
- **Relevant Source Function**: `foundation/corpus/near_deduplication.py::SemanticSafetyGuard.UNIT_TO_BASE`
- **Minimal Justified Fix**: Added `"mib": ("b", 1048576.0)`, `"mebibyte": ("b", 1048576.0)`, `"mebibytes": ("b", 1048576.0)`, and equivalent binary units to `UNIT_TO_BASE`.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_binary_unit_conversion_bytes_to_mib`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_binary_unit_conversion_bytes_to_mib`
- **Result**: **DEFECT FIXED AND RETESTED (PASS)**

---

### DEF-4.8-05: Active/Passive Voice Paraphrase Filtered by Rigid Order MinHash
- **Pair ID**: `v5_test_pair_003`
- **Category**: `paraphrase_duplicate`
- **Text A**: `"The attending physician instructed the nurses that 250 mg of cephalosporin should be administered orally."`
- **Text B**: `"Nurses were instructed by the attending physician that 250 mg of cephalosporin should be administered orally."`
- **Ground-Truth Label**: `True` (Valid Paraphrase Duplicate) | **Predicted Label**: `False`
- **Label Ambiguity**: Unambiguous. Factual content, numbers, entities, and clinical outcomes are 100% identical.
- **Failure Mechanism**: 5-character shingle MinHash evaluates contiguous character n-grams across word boundaries. Reordering clauses drops character shingle Jaccard to $0.7109 < 0.75$, filtering out the candidate in Stage 2 before the Stage 3 safety guard could verify semantic equivalence. However, word token Jaccard is $0.875$ (87.5%)!
- **Relevant Source Function**: `foundation/corpus/near_deduplication.py::evaluate_near_duplicate_strategy`
- **Minimal Justified Fix**: Candidate retrieval computes combined similarity:
  $S(A, B) = \max(J_{\text{MinHash}}(A, B), J_{\text{token}}(A, B))$.
  If combined similarity $\ge 0.75$ and Stage 3 `verify_pair` detects zero factual, date, numerical, or polarity conflicts, the pair is verified safe to merge.
- **Regression Test**: `tests/test_near_deduplication_safety.py::test_voice_paraphrase_candidate_retrieval_and_merge`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_near_deduplication_safety.py -k test_voice_paraphrase_candidate_retrieval_and_merge`
- **Result**: **DEFECT FIXED AND RETESTED (PASS)**

---

### DEF-4.8-06: Missing Standard Prepositions in `_COMMON_ENGLISH_STOPWORDS`
- **Sample IDs**: `v6_lang_test_002` (contained `against`), `v6_lang_test_010` (contained `near`)
- **Category**: `ordinary_english_prose`
- **Ground-Truth Label**: `ACCEPT` | **Predicted Label**: `REJECT`
- **Label Ambiguity**: Unambiguous. Fluent natural English sentences rejected because `against` and `near` were omitted from `_COMMON_ENGLISH_STOPWORDS`.
- **Failure Mechanism**: QualityFilter requires $\ge 2$ stopwords. Sentences with 1 auxiliary verb and 1 standard preposition were rejected with `NO_ENGLISH_STOPWORDS`.
- **Relevant Source Function**: `foundation/corpus/filtering.py::_COMMON_ENGLISH_STOPWORDS`
- **Minimal Justified Fix**: Added standard English prepositions and closed-class conjunctions/pronouns:
  `against`, `near`, `during`, `across`, `without`, `over`, `within`, `along`, `among`, `upon`, `its`, `because`, `since`, `inside`, `via`.
- **Regression Test**: `tests/test_language_filter_hardening.py`
- **Verification Command**: `.venv\Scripts\python.exe -m pytest tests/test_language_filter_hardening.py`
- **Result**: **DEFECT FIXED AND RETESTED (PASS)**
