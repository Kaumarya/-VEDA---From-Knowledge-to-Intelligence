# VEDA — Accuracy Engineering Audit & From-Scratch Model Roadmap

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Authoritative Accuracy Engineering Audit & Future LLM Quality Roadmap
Document ID: VEDA-ROADMAP-ACCURACY-v1.0
Audit Date: 2026-10-15
Milestone Focus: Corpus Fidelity, Evaluation Rigor & Neural Model Accuracy
========================================================================================
```

---

## 1. Executive Vision & Architectural Discipline

Project VEDA is grounded in a singular methodological principle:

$$\text{\textbf{UNDERSTAND}} \longrightarrow \text{\textbf{DESIGN}} \longrightarrow \text{\textbf{IMPLEMENT}} \longrightarrow \text{\textbf{TEST}} \longrightarrow \text{\textbf{MEASURE}} \longrightarrow \text{\textbf{DOCUMENT}} \longrightarrow \text{\textbf{IMPROVE}}$$

We reject the practice of taking opaque, pretrained model checkpoints or calling commercial black-box APIs and labeling the result "intelligence." Real language intelligence requires understanding how representations form, how inductive biases operate, how corpora transmit statistical structure, and how evaluation protocols measure genuine comprehension.

This roadmap establishes a rigorous, evidence-based quality framework spanning:
1. **Source & Data Integrity**: Ground truth byte identity, provenance tracking, and fail-closed gates.
2. **Language & Text Quality**: Categorical error measurement, cognate vulnerability mitigation, and quarantine routing.
3. **Deduplication Reliability**: Two-stage evaluation, confidence intervals, and the strict distinction between lexical shingles and semantic equivalence.
4. **Evaluation Integrity**: Data isolation, related-work group partitioning, and empirical metric discipline.
5. **From-Scratch Neural Model Accuracy**: An end-to-end plan covering tokenization, domain mixture balance, learning dynamics, perplexity measurement, and ablation protocols.

---

## 2. Area A — Source and Data Integrity Audit

Accuracy in language modeling begins with absolute certainty regarding what text enters the pipeline. A corrupt or legally encumbered training corpus permanently invalidates all downstream weights.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   DATA INTEGRITY & PROVENANCE CHAIN                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    [Authoritative External Source Archive] (Published release / manifest)
                                    │
                                    ▼
       [Physical Byte SHA-256 Checksum] (Verified against on-disk bytes)
                                    │
                                    ▼
          [Authentic Legal Instrument] (Full text archived & hashed)
                                    │
                                    ▼
         [Fail-Closed Governance Gate] (Rejects if any field unverified)
                                    │
                                    ▼
       [Document & Segment Lineage] (source_id, doc_id, char offsets)
                                    │
                                    ▼
        [Exact Count Conservation] (Input = Retained + Rejected + Dup)
```

### Established Integrity Invariants

1. **Physical Byte Identity Over Synthetic Placeholders**:
   - Every published checksum must represent the SHA-256 digest of actual physical bytes on disk. Purported hashes calculated from URLs, titles, or metadata strings are strictly banned.
   - Unacquired archives must be labeled explicitly as `NOT_ACQUIRED` / `NOT_VERIFIED`.
2. **Complete Provenance Chain**:
   - Every atomic `CorpusRecord` maintains direct lineage:
     $$\text{Provenance} = (\text{source\_id}, \text{document\_id}, \text{segment\_index}, \text{start\_char\_offset}, \text{end\_char\_offset})$$
   - Slice alignment invariant: `doc_text[start:end] == rec.raw_text`.
3. **Deduplication Attribution Preservation**:
   - When duplicate segments from multiple sources collide, the retained canonical record accumulates all contributing source IDs and attribution notices via `DeduplicationEngine.get_contributors()`.
   - The rejection ledger records the duplicate event, preserving cross-source auditability.
4. **Strict Count Reconciliation**:
   $$\text{Total Documents Processed} = \text{Retained Documents} + \text{Rejected Documents}$$
   $$\text{Total Records Processed} = \text{Retained Records} + \text{Rejected Records} + \text{Duplicate Records}$$
   Any deviation represents a critical data loss defect.

---

## 3. Area B — Language and Text Quality Audit

Evaluating text quality and language identity cannot rely on a single aggregate metric or a naive stopword ratio.

### Empirical Vulnerability Analysis: The Cognate Failure Mode

The VEDA `QualityFilter` incorporates an English stopword syntactic heuristic. Adversarial auditing revealed a critical failure mode:
- Western European languages sharing Latin script and cognates (e.g. German text containing *in* and *so*) can accumulate 2 stopwords on a 15–20 word sentence.
- A naive binary classifier with a threshold of $\ge 2$ stopwords misclassifies authentic German prose as English (**False Positive**).

### The Three-Way Decision & Quarantine Routing Policy

To eliminate false-positive contamination while protecting authentic technical prose:

```
┌────────────────────────────────────────────────────────────────────────┐
│                  THREE-WAY CLASSIFICATION POLICY                       │
├────────────────────────────────────────────────────────────────────────┤
│ 1. DIRECT ACCEPTANCE:                                                  │
│    - All structural metrics pass (alpha ratio, symbol ratio).          │
│    - High-confidence English stopword count (>= 3 stopwords).          │
│                                                                        │
│ 2. DIRECT REJECTION:                                                   │
│    - Structural failure (symbol ratio > 0.20, char runs > 4).          │
│    - Non-Latin script (Cyrillic, Greek, CJK > 15%).                    │
│    - Total absence of English stopwords (0 stopwords on prose).        │
│                                                                        │
│ 3. QUARANTINE ROUTING:                                                 │
│    - Borderline stopword count (exactly 1-2 stopwords on >= 15 words). │
│    - Short phrases (< 15 words) lacking functional syntactic context.  │
│    - Foreign pedagogical quotations embedded in English text.          │
│    - Routed to quarantine.jsonl for secondary scoring or human audit.  │
└────────────────────────────────────────────────────────────────────────┘
```

### 21-Sample Versioned Benchmark Across 9 Linguistic Categories

Implemented in [`foundation/corpus/language_audit.py`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/corpus/language_audit.py):

| Benchmark Category | Core Risk / Challenge | Expected Behavior | Measured Accuracy |
|---|---|---|---|
| **1. Ordinary English Prose** | Baseline syntax | Direct `ACCEPT` | 100.0% (3/3) |
| **2. Scientific & Mathematical** | Technical jargon, formulas | Direct `ACCEPT` (preserve technical prose) | 100.0% (2/2) |
| **3. Short Signs & Headings** | Lack of syntactic context | Route to `QUARANTINE` | 100.0% (2/2) |
| **4. Code, Logs & Tables** | Non-prose symbols, data dumps | Direct `REJECT` (`HIGH_SYMBOL_RATIO`) | 100.0% (2/2) |
| **5. Non-English European** | Cognates (*in*, *so*), loanwords | Direct `REJECT` or `QUARANTINE` | 100.0% (3/3) |
| **6. Foreign Quotes & Names** | Mixed language in English prose | `ACCEPT` prose, `QUARANTINE` isolated quote | 100.0% (2/2) |
| **7. Mixed-Language Pedagogy** | Language textbooks (*"La plume est..."*) | `ACCEPT` prose, `QUARANTINE` ambiguous | 100.0% (2/2) |
| **8. Non-Latin Script** | Cyrillic, Arabic, CJK | Direct `REJECT` (`NON_ENGLISH_SCRIPT`) | 100.0% (2/2) |
| **9. Unicode & Punctuation** | Typographical quotes, em-dashes | NFC `ACCEPT` or `REJECT` if spam runs | 100.0% (3/3) |

---

## 4. Area C — Near-Duplicate Detection Audit

### Two-Stage Evaluation Architecture

Near-duplicate detection in large corpora operates under severe computational constraints. Comparing all document pairs ($O(N^2)$) is impossible at scale. Therefore, VEDA implements a two-stage MinHash/LSH pipeline:

1. **Stage 1: Candidate Retrieval (LSH Band Collisions)**:
   - High-recall, sub-linear candidate filtering using $b=16$ bands of $r=8$ hash rows ($m=128$ permutations).
   - Metric: **Candidate Recall** (must approach 1.0) and **Candidate Selectivity** (fraction of non-duplicates filtered out before pairwise shingling).
2. **Stage 2: Final Duplicate Decision (MinHash Signature Jaccard)**:
   - Precision-oriented decision threshold ($\tau=0.80$).
   - Metric: **Precision**, **Recall**, **Specificity**, **F1-Score**, and **Wilson 95% Confidence Intervals**.

### Measured Benchmark Performance

Evaluated against the calibrated 12-pair benchmark ([`data/corpus/eval_near_dedup_results.json`](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/data/corpus/eval_near_dedup_results.json)):
- **Stage 1 Candidate Recall**: **1.0000** ($[0.5655, 1.0000]$) — 100% of true duplicates retrieved.
- **Stage 1 Selectivity**: **0.8571** ($[0.4869, 0.9743]$) — 85.7% of negative pairs eliminated prior to verification.
- **Stage 2 Precision**: **1.0000** ($[0.5655, 1.0000]$) — Zero false positives at $\tau=0.80$.
- **Stage 2 Recall**: **1.0000** ($[0.5655, 1.0000]$) — 100% of true duplicates identified.

### Methodological Invariant: Lexical Shingles $\neq$ Semantic Equivalence

> [!CAUTION]
> **Do Not Confuse Lexical Overlap with Semantic Truth**:
> MinHash measures Jaccard similarity across k-shingles (sequences of words or characters). It is completely blind to negation, numerical dosage, and semantic inversion.
> 
> As demonstrated by pair `eval_critical_numerical_inversion_012`:
> - Passage A describes a clinical trial with 5.0 mg dosage resulting in complete remission with zero adverse events.
> - Passage B describes a clinical trial with 50.0 mg dosage resulting in severe toxicity with multiple fatal cardiac events.
> - Surface 5-shingle Jaccard overlap: **78.57%**.
> - The two passages make diametrically opposed, life-critical assertions.
> 
> MinHash/LSH must be documented strictly as a **lexical redundancy filter**, never as an arbiter of factual truth or semantic equivalence.

---

## 5. Area D — Evaluation Integrity & Split Isolation

A fundamental failure mode in NLP and LLM training is data contamination across splits. If an excerpt of a book appears in the training set and another chapter appears in the test set, test perplexity measures memorization rather than generalization.

### Deterministic Group Partitioning

VEDA enforces leak-free dataset partitioning:

$$\text{Document Hash} = \text{SHA-256}(\text{raw\_text})$$
$$\text{Partition Key} = \text{group\_id} \quad (\text{defaults to } \text{document\_id})$$
$$\text{Split Value} = \frac{\text{int}(\text{SHA-256}(\text{Partition Key} + \text{seed})[:8], 16)}{2^{32} - 1} \in [0.0, 1.0)$$

- Documents sharing a `group_id` (e.g. all chapters of an author's novel, all sections of a textbook) receive the identical `Split Value`.
- As verified in `test_split_grouping_prevents_related_work_leakage`, 100% of related chapters reside in the same split (e.g., all in `train` or all in `test`).

### Units & Denominator Accounting

- **Unit Tests $\neq$ Corpus Accuracy**: Passing 220 software unit tests certifies software correctness; it does not prove that an uninspected corpus is accurate.
- **Composition Levels**:
  - Level 1: Planning Target Ratio (Policy)
  - Level 2: Active Reallocated Target Ratio (Policy calculation)
  - Level 3: Controlled Pilot Measurement (Empirical fixture: 10 records, 4,379 chars)
  - Level 4: Retained Production Corpus (**`NOT YET MEASURED`**)
  - Level 5: Training Token Exposure (**`NOT YET MEASURED`**)

---

## 6. Area E — Future From-Scratch Neural Model Accuracy Plan

When Project VEDA transitions to Phase 5–7 (neural architecture, tokenization, and pretraining), model accuracy will be engineered through the following eight-pillar methodology:

```
┌────────────────────────────────────────────────────────────────────────┐
│           VEDA FROM-SCRATCH NEURAL MODEL ACCURACY ROADMAP              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    ▼                               ▼                               ▼
[1. Tokenizer Fidelity]     [2. Domain Composition]     [3. Optimization Dynamics]
  - BPE vocab sizing          - 7-category weights        - Cosine lr schedule
  - Compression ratio         - Deduplication yield       - Weight decay (0.1)
  - Byte-fallback             - Epoch curriculum          - Gradient clipping
    │                               │                               │
    └───────────────────────────────┼───────────────────────────────┘
                                    │
    ┌───────────────────────────────┼───────────────────────────────┐
    ▼                               ▼                               ▼
[4. Overfitting Detection]  [5. Perplexity Tracking]    [6. Baselines & Ablation]
  - Train/Val loss delta      - Held-out test sets        - N-gram language model
  - Early stopping rule       - LAMBADA & WikiText        - No-attention baseline
  - Checkpoint validation     - Subword-adjusted PPL      - Depth vs width study
    │                               │                               │
    └───────────────────────────────┼───────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        [7. Checkpoint Determinism]     [8. Compute & Memory Bounds]
          - Fixed random seeds            - Chinchilla token scaling
          - Optimizer state sealing       - Process RSS < 1.5 GB
          - Bit-identical forward pass    - Local CPU/IPEX optimization
```

---

### Pillar 1: Subword Tokenizer Evaluation & Coverage

1. **Vocabulary Size Calibration**:
   - Target vocabulary: **16,384** to **32,768** tokens.
   - Sizing criteria: Balancing embedding table memory against sequence compression ratio:
     $$\text{Compression Ratio} = \frac{\text{Raw UTF-8 Bytes}}{\text{Subword Tokens}} \in [3.5, 4.5]$$
2. **Fertility & Character Coverage**:
   - Fertility: Average subword tokens per word (target: $< 1.3$ on standard English).
   - Character coverage: **100%** byte-level fallback ensuring zero `<unk>` token dropouts on rare Unicode characters.
3. **Round-Trip Reconstruction Invariant**:
   - Every tokenized string must satisfy:
     $$\text{decode}(\text{encode}(\text{text})) == \text{text}$$
   - Verified across all ASCII, Latin-1, and typographically rich English prose.

---

### Pillar 2: Training Data Quality & Curriculum Mixture

1. **Seven-Category Target Domain Mixture**:
   - Books & Classical Literature (35%): Long-range syntactic coherence and narrative arc.
   - Educational & Pedagogical Material (25%): Expository reasoning and conceptual progression.
   - Science, Math & Technical Documentation (15%): Formal logic, algorithmic structure, and nomenclature.
   - General Prose & Contemporary Journalism (15%): Modern active-voice syntax and contemporary events.
   - Reference & Encyclopedic (10% gated): Fact-dense world knowledge.
2. **Quality vs Volume Trade-off**:
   - Pretraining on 500 million meticulously cleaned, deduplicated, and syntactically rich tokens yields substantially higher downstream comprehension than pretraining on 50 billion noisy web scrapes.
3. **Curriculum Strategy**:
   - Phase A (Foundations): Balanced exposure to general literature and explanatory prose.
   - Phase B (Specialization): Increased mixture of scientific logic, mathematics, and technical reasoning.

---

### Pillar 3: Optimization Dynamics & Convergence Discipline

1. **Architecture Specifications (VEDA-Small Foundation)**:
   - Architecture: Decoder-only Transformer with causal attention masking.
   - Context Window: 512 to 1,024 tokens.
   - Model Dimensions: $d_{\text{model}} = 512$, $n_{\text{heads}} = 8$, $n_{\text{layers}} = 8$, $d_{\text{ff}} = 2048$.
   - Parameter Count: Approximately **25M to 45M parameters** (sized specifically for high-throughput CPU/IPEX training).
2. **Optimizer & Schedule**:
   - Optimizer: AdamW ($\beta_1 = 0.9$, $\beta_2 = 0.98$, $\epsilon = 10^{-8}$, weight decay = $0.1$).
   - Schedule: Linear warmup over 2,000 steps followed by Cosine Annealing decay to 10% peak learning rate.
   - Gradient clipping: Maximum $L_2$ gradient norm $\le 1.0$.

---

### Pillar 4: Loss Curves & Overfitting Detection

1. **Validation Loss Invariant**:
   - Evaluate validation cross-entropy loss every 250 optimization steps on held-out validation shards.
2. **Overfitting Early Warning Indicator**:
   $$\Delta_{\text{overfit}} = \mathcal{L}_{\text{val}}(t) - \mathcal{L}_{\text{train}}(t)$$
   - If $\Delta_{\text{overfit}}$ increases continuously across 3 consecutive evaluation checkpoints, trigger early stopping and checkpoint rollback.
3. **Training Loss Target**:
   - Monitor cross-entropy loss convergence toward theoretical entropy limits:
     $$\mathcal{L}(t) = -\frac{1}{N} \sum_{i=1}^N \log P(w_i \mid w_{<i})$$

---

### Pillar 5: Perplexity & Held-Out Language Model Evaluation

1. **Perplexity Definition & Denominators**:
   $$\text{PPL} = \exp\left( \frac{1}{T} \sum_{t=1}^T \mathcal{L}_t \right)$$
   - Denominator: Total evaluated subword tokens $T$ on strictly held-out test splits.
2. **Subword Tokenizer Sensitivity**:
   - Perplexities across different tokenizers cannot be compared directly without length-normalization. All reported perplexities must cite the exact tokenizer vocabulary size and average token length.
3. **Standardized Zero-Shot Linguistic Probes**:
   - Evaluate on standardized grammatical and comprehension benchmarks:
     - BLiMP (Benchmark of Linguistic Minimal Pairs): Subject-verb agreement, filler-gap dependencies.
     - LAMBADA: Target word prediction given long narrative context.
     - WikiText-2 / WikiText-103: Standardized held-out perplexity comparison.

---

### Pillar 6: Reproducible Checkpoints & Determinism

1. **Fixed Seed Protocol**:
   - Global deterministic seeding:
     ```python
     torch.manual_seed(42)
     np.random.seed(42)
     torch.use_deterministic_algorithms(True)
     ```
2. **Checkpoint State Integrity**:
   - Saved checkpoints must serialize:
     - Model weights (`model.state_dict()`)
     - Optimizer states (`optimizer.state_dict()`)
     - Learning rate scheduler state
     - Exact token step and global epoch
     - Content SHA-256 fingerprint of the training split shard
3. **Bit-for-Bit Inference Reproducibility**:
   - Greedy argmax generation from an identical checkpoint on identical input prompt must produce bit-for-bit identical token sequences.

---

### Pillar 7: Baselines and Ablation Protocols

Every modeling choice must be justified through controlled ablation experiments:

| Experiment | Configuration A | Configuration B | Evaluation Question |
|---|---|---|---|
| **Ablation 1: Positional Embedding** | Rotary Positional Embeddings (RoPE) | Learned absolute embeddings | Does RoPE improve long-context extrapolation? |
| **Ablation 2: Normalization** | RMSNorm (Pre-LayerNorm) | LayerNorm | Does RMSNorm stabilize training dynamics on CPU? |
| **Ablation 3: Activation Function** | SwiGLU | GeLU / ReLU | Does SwiGLU provide superior gradient flow per FLOP? |
| **Baseline 1: Statistical N-Gram** | 4-gram Kneser-Ney language model | Transformer-Tiny | Measures the neural model's margin over statistical memory. |
| **Baseline 2: Random Weights** | Untrained initialized Transformer | Trained Transformer | Establishes the empirical lower bound for perplexity. |

---

### Pillar 8: Compute, Memory & Resource Budget Scaling

1. **Chinchilla Optimal Compute Ratio**:
   - To achieve optimal parameter utilization:
     $$\text{Optimal Tokens} \approx 20 \times \text{Number of Parameters}$$
   - For a 30M parameter VEDA-Small model: Target training volume is $\approx 600\text{M}$ tokens.
2. **Process RSS Memory Envelope**:
   - Maximum permitted training process RSS: **2.0 GB**.
   - Achieved through micro-batching (batch size 16 to 32) combined with gradient accumulation (accumulation steps 4 to 8).
3. **Hardware Utilization**:
   - Optimized for host 13th Gen Intel Core i5-13500H (12 physical cores, 16 threads).
   - Intel oneDNN vectorization enabled via PyTorch CPU backend.

---

```
========================================================================================
END OF ROADMAP — ACCURACY AUDIT RATIFIED — PRODUCTION INGESTION BLOCKED
========================================================================================
```
