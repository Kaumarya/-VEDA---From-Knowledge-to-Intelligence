# VEDA — Quality Gates & Accuracy Policy

**Document Version:** 1.0.0  
**Phase:** 4.4 — 95% Quality Gates & Comprehensive Code Audit  
**Status:** ACTIVE & MANDATORY  
**Scope:** VEDA System-Wide (Lexicon, Corpus, Tokenizer, Filtering, Deduplication, Neural Foundation)

---

## 1. Foundational Principles & Non-Equivalence Axiom

In VEDA, data quality, algorithmic correctness, and linguistic fidelity are strictly segregated into independent operational dimensions. Under no circumstances may distinct quality criteria be conflated:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        VEDA NON-EQUIVALENCE AXIOM                      │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Unit Test Pass Rate        ≠ Component Operational Accuracy         │
│ 2. Cryptographic Checksum     ≠ Legal Licensing Authenticity           │
│ 3. Lexical Lookup Throughput  ≠ Linguistic Coverage                    │
│ 4. Neural Optimization Loss   ≠ General Intelligence / Natural Fluency │
│ 5. Automated Acceptance       ≠ Absolute Factual Truth                 │
│ 6. Fast Inference / Execution ≠ Mathematical Soundness                 │
└────────────────────────────────────────────────────────────────────────┘
```

A test suite with 100% passing tests proves only that the specific assertions executed without raising exceptions; it does **not** prove that the underlying data distribution is free from contamination, bias, or false positives.

---

## 2. Component Quality Gates

### Gate A: English Language & Quality Filter Gate

#### 1. Measurable Standards
- **Minimum Overall Accuracy:** $\ge 95.0\%$ on an independently labeled, held-out evaluation test set ($N \ge 500$).
- **Critical Category Targets:** Precision $\ge 95.0\%$ and Recall $\ge 95.0\%$ for all critical categories where sample size $N \ge 30$.
- **Inconclusive Threshold:** Any category with $N < 30$ must be reported as **INCONCLUSIVE**, not passed.
- **Statistical Uncertainty:** Every accuracy metric, precision, and recall must be reported with a two-sided **Wilson 95% score confidence interval**:
  $$w = \frac{p + \frac{z^2}{2N} \pm z\sqrt{\frac{p(1-p)}{N} + \frac{z^2}{4N^2}}}{1 + \frac{z^2}{N}} \quad (z = 1.96)$$

#### 2. Quarantine Accounting
`QUARANTINE` is an explicit, operational third state distinct from automatic `ACCEPT` and automatic `REJECT`. Metrics must report:
- **Automatic Classification Accuracy:** Agreement with ground truth on definitive accept/reject samples.
- **Quarantine Routing Accuracy:** Percentage of ambiguous, terse, or cognate-heavy texts correctly routed to quarantine.
- **False Acceptance Rate (FAR):** Rate of non-English or corrupted text erroneously admitted as `ACCEPT`. (Hard ceiling: $\le 2.0\%$).
- **False Rejection Rate (FRR):** Rate of valid English prose erroneously discarded as `REJECT`. (Hard ceiling: $\le 2.0\%$).

#### 3. Category Coverage Mandate
The evaluation set must contain balanced, difficult adversarial examples across 9 distinct linguistic categories:
1. `ordinary_english_prose`: Expository and literary narrative prose.
2. `scientific_mathematical_english`: Dense technical prose, terminology, and chemical/physical formulas.
3. `short_signs_captions_headings`: Terse signage, table captions, and chapter titles lacking finite verbs.
4. `code_logs_tables_technical`: Source code snippets, compiler outputs, syslogs, and software docstrings.
5. `foreign_latin_script_french_german_spanish`: Non-English European languages sharing Latin script.
6. `foreign_names_and_quotes`: Valid English prose embedding classical maxims and accented international names.
7. `mixed_language_pedagogy`: English instructional texts teaching foreign grammatical constructs.
8. `non_latin_script`: Cyrillic, CJK ideographs, Arabic, Devanagari scripts.
9. `unicode_punctuation_edge_cases`: Typographical punctuation (em-dashes, curly quotes) and loanwords.

---

### Gate B: Near-Duplicate Detection & MinHash/LSH Gate

#### 1. Measurable Standards
- **Minimum Precision:** $\ge 95.0\%$ on an independently labeled pair-level test set ($N \ge 500$).
- **Minimum Recall:** $\ge 95.0\%$ on candidate retrieval and final Jaccard decision.
- **Wilson Confidence Intervals:** Must be disclosed for precision, recall, selectivity, and F1 score.

#### 2. Pairwise & Cluster-Level Error Tracking
- **False Merges (False Positives):** Semantically divergent documents erroneously grouped as duplicates (e.g. numerical dosage inversions, negation flips).
- **Missed Duplicates (False Negatives):** True near-duplicates missed due to formatting, paragraph reordering, or synonym substitutions.
- **Tuning Separation:** MinHash permutation thresholds ($s \ge 0.80$, $b=16$, $r=8$) must be tuned strictly on a **Development Set**. The **Held-Out Test Set** must never be used for parameter tuning.

#### 3. Required Pair Taxonomy
1. `exact_duplicates`: Identical texts with byte-level parity.
2. `formatting_and_whitespace`: Normalized whitespace, case changes, line break differences.
3. `minor_word_edits`: Synonym substitutions, adjective insertions, typo repairs.
4. `reordered_passages`: Paragraph and sentence permutations.
5. `short_texts`: Brief sentences with high shingle sensitivity.
6. `shared_boilerplate`: Unrelated texts sharing copyright, legal, or navigation notices.
7. `multilingual_text`: Parallel or translated passages.
8. `semantic_inversions`: Critical numerical, dosage, or negation inversions (e.g. "safe" vs "toxic").
9. `technical_overlap`: Configuration profiles sharing key schemas but diverging in values.
10. `distant_negatives`: Completely disjoint topics, authors, and genres.

---

### Gate C: Data Integrity & Provenance Gate

#### 1. Pass Rate
- **Strict Requirement:** **100% Pass Rate** across all mandatory integrity checks. Zero tolerances permitted.

#### 2. Verification Dimensions
- **Schema Validation:** Strict adherence to dataclass contracts and SQLite relational schemas.
- **Provenance Fidelity:** Every record must track `source_id`, `document_id`, `extraction_timestamp`, and URI.
- **Conservation of Records:** Ingestion equation invariant must hold:
  $$N_{\text{total\_extracted}} = N_{\text{retained}} + N_{\text{rejected}} + N_{\text{deduplicated}}$$
- **Cryptographic Fingerprinting:** Dual SHA-256 fingerprinting (content bytes and logical metadata).
- **Atomic File Operations:** All write operations must use atomic `os.replace` semantics to prevent partial file corruption upon power loss or interrupt.
- **Transaction Rollback:** Interrupted SQLite or streaming batch operations must cleanly roll back without leaving partial or corrupted records.
- **Fail-Closed Gate:** If license documentation, hash confirmation, or quality metrics fail, ingestion is **BLOCKED**.

---

### Gate D: Tokenizer Quality Gate

#### 1. Pass Rate
- **Strict Requirement:** **100% Round-Trip Correctness** for all characters within the declared Character Registry vocabulary:
  $$\forall s \in \Sigma^*: \quad \text{decode}(\text{encode}(s)) = s$$

#### 2. Boundary & Robustness Coverage
- **Empty String:** `encode("") == []` (or `[<BOS>, <EOS>]` when `add_special_tokens=True`).
- **Special Tokens:** `<PAD>`, `<UNK>`, `<BOS>`, `<EOS>` must map to fixed reserved IDs $0..3$.
- **Unsupported Unicode:** Unregistered characters and emojis must map deterministically to `<UNK>` without crashing.
- **Boundary Conditions:** Max sequence length truncation, invalid token ID rejection in strict mode, surrogate pairs.
- **Scope Restriction:** The tokenizer is strictly documented as an **English Character Tokenizer (v0.1, 117 tokens)**. It must never claim universal multilingual Unicode coverage.

---

### Gate E: Neural Foundation Quality Gate

#### 1. Mathematical & Structural Invariants
- **Causal Masking:** Modifying token at position $t+k$ ($k > 0$) must produce **zero change** in logits at position $t$.
- **Finite Computation:** Loss and gradients must be strictly finite ($\ne \text{NaN}, \pm\infty$).
- **Parameter Optimization:** Weights must change under optimization ($\exists \theta \in \Theta: \theta_{t+1} \ne \theta_t$).
- **Overfitting Capability:** Model must be capable of reducing cross-entropy loss by $\ge 50\%$ on a tiny controlled training fixture.
- **Checkpoint Exact Parity:** Checkpoint serialization and deserialization via `torch.load(..., weights_only=True)` must yield exact numerical outputs:
  $$\max |\hat{Y}_{\text{orig}} - \hat{Y}_{\text{reloaded}}| \le 10^{-6}$$
- **Data Leakage:** Held-out evaluation split must verify $0.0\%$ n-gram overlap against training data.

#### 2. Non-Claim Mandate
The neural foundation experiment is an architectural sanity check. It must **never** claim conversational fluency, reasoning, or language comprehension.

---

### Gate F: Full Language Model Pretraining Gate (Future Milestone)

- **Baselines Prerequisite:** Pretraining acceptance requires establishing held-out next-token cross-entropy and perplexity baselines before specifying a 95% target.
- **No Conflation:** Natural language next-token prediction accuracy on open-domain corpora cannot arbitrarily be set to 95% without task-specific framing.
- **Downstream Criteria:** Downstream evaluation (e.g. grammar correction, closed-book factual retrieval, syntactic parsing) must have predefined, task-specific ground-truth benchmarks.

---

## 3. Gate Status Taxonomy

Every VEDA component evaluation must output an authoritative status code:

| Status Code | Definition | Operational Action |
| :--- | :--- | :--- |
| **`VERIFIED`** | Predefined target met with statistical significance ($N \ge 30$, 95% Wilson CI bounds verified, 0 critical regressions). | Component certified for pipeline integration. |
| **`INCONCLUSIVE`** | Target appears met, but sample size $N < 30$ yields overly wide confidence intervals. | Additional labeled evaluation samples required before certification. |
| **`BLOCKED`** | Measured metric falls below the 95% threshold, or an unhandled critical defect exists. | Component barred from production; fix-and-verify required. |
| **`NOT TESTED`** | Component has not undergone empirical evaluation against the formal benchmark. | Must not be claimed as passing or verified. |

---

## 4. Production Ingestion Gate Invariant

Regardless of component-level test scores:
$$\text{Production Corpus Ingestion} = \text{BLOCKED}$$
Production ingestion remains fail-closed until:
1. Legal ownership and public domain status of each candidate source is independently verified with documentary evidence.
2. Source-specific license terms are certified by legal governance.
3. Ingestion storage and memory resource ceilings are proven on production-scale dry runs.
