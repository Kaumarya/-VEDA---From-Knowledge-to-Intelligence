# VEDA Corpus Segmentation, Deduplication & Splitting Policy

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Segmentation, Deduplication & Splitting
Document ID: VEDA-POLICY-SPLIT-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Document Segmentation: From Documents to Records

A raw document (e.g. a book, essay, or encyclopedic article) cannot be passed to a neural model as an undivided 500,000-character blob. It must be decomposed into coherent, consumable training units.

### A. The Canonical Segment: The Paragraph
In natural English writing, the **paragraph** is the foundational unit of coherent thought:
- A sentence is too short: it lacks multi-sentence coreference, rhetorical progression, and long-range topic consistency.
- An entire book is too long: it exceeds practical Transformer context windows and induces severe padding inefficiency.
- An arbitrary 512-character fixed chunk is destructive: it slices mid-sentence or mid-word, destroying syntactic structure.

> **VEDA Invariant**: The canonical `CorpusRecord` corresponds to a **structural paragraph** (or tightly bound group of short related paragraphs) maintaining natural sentence and clause integrity.

### B. Segmentation Rules:
1. **Paragraph Delimitation**: Paragraph boundaries are identified by double newlines (`\n\n`) or markup paragraph tags (`<p>...</p>`).
2. **Boundary Preservation**: Every segment records its exact character span `[start_char_offset, end_char_offset]` within the parent `raw_text`.
3. **Headings & Titles**: Section headings are preserved as context or attached to the following paragraph to retain topic grounding.
4. **Lists & Bullet Points**: Sequential list items are grouped into a single structured segment rather than isolated single-line fragments.
5. **Length Constraints**:
   - Minimum record length: $\ge 25$ characters, $\ge 4$ words.
   - Maximum record length: $\le 15,000$ characters. Paragraphs exceeding this bound are segmented at sentence boundaries (`. `, `? `, `! ` followed by capitalized words).

---

## 2. Deduplication Framework

Duplicated text in training data skews token distribution, forces the model to memorize redundant passages, and severely inflates downstream benchmark scores through leakage.

### A. Taxonomy of Duplicates

VEDA distinguishes **six distinct levels of duplication**:

```
┌────────────────────────────────────────────────────────┐
│ 1. Exact Duplicate                                     │ Bitwise identical raw string
├────────────────────────────────────────────────────────┤
│ 2. Normalized Duplicate                                │ Identical after Unicode & whitespace normalizer
├────────────────────────────────────────────────────────┤
│ 3. Document Duplicate                                  │ Same document ingested multiple times under new IDs
├────────────────────────────────────────────────────────┤
│ 4. Repeated Paragraph / Boilerplate                    │ High-frequency paragraph repeating across documents
├────────────────────────────────────────────────────────┤
│ 5. Repeated Sentence                                   │ Identical sentence appearing across diverse records
├────────────────────────────────────────────────────────┤
│ 6. Near Duplicate                                      │ High lexical overlap (Jaccard similarity ≥ 0.85)
└────────────────────────────────────────────────────────┘
```

> [!CRITICAL]
> **No Collapsed Duplicate Statistics**:
> Deduplication statistics must **never** lump all duplicates into a single uninformative number. The system must report exact duplicate counts, normalized duplicate counts, and document duplicate counts separately.

### B. Deduplication Execution Order
1. **Document-Level Hash Gate**: SHA-256 hash of `raw_text` rejects redundant documents before segmentation begins.
2. **Normalized Record Deduplication**: SHA-256 fingerprint of `normalized_text` prevents identical paragraphs from entering the corpus.
3. **Tracking & Ledgering**: The first occurrence of a record is marked canonical (`is_duplicate = False`); subsequent matches are marked duplicate (`is_duplicate = True`, `duplicate_of_id = <canonical_id>`) and excluded from final training splits.

---

## 3. Data Leakage Prevention: The Document Boundary Axiom

A fatal error in machine learning pipeline design is **record-level random splitting**:

```
[DOCUMENT A]
   ├── Paragraph 1  ──►  Assigned to TRAIN
   ├── Paragraph 2  ──►  Assigned to VALIDATION  (LEAKAGE!)
   └── Paragraph 3  ──►  Assigned to TEST        (CATASTROPHIC LEAKAGE!)
```

If paragraphs from the same document are distributed across Train and Test splits:
1. The model encounters identical characters, narrative arcs, specialized jargon, and factual details during training.
2. Evaluation perplexity and test loss drop artificially, creating an illusion of high generalization.
3. Downstream out-of-domain evaluation collapses.

> [!CRITICAL]
> **The Leakage Prevention Axiom**:
> **Dataset splitting is strictly performed at the DOCUMENT boundary, NEVER at the individual record or sentence boundary.**
> All records, segments, and sentences originating from Document $D_k$ belong strictly to the **same split**.
> A source may contain multiple documents which are independently assignable to splits.

```
[DOCUMENT A] ──► all segments ──► TRAIN
[DOCUMENT B] ──► all segments ──► VALIDATION
[DOCUMENT C] ──► all segments ──► TEST
```

### Three-Tiered Leakage Classification:
1. **Guaranteed by Construction**: Every document belongs to exactly one split; all records derived from it remain in that split.
2. **Controlled by Deduplication**: Bitwise exact document duplicates and normalized duplicate records are quarantined and prevented from crossing splits.
3. **Not Fully Eliminated by v0.1**: Near duplicates (minor edits, typos), paraphrases, and semantic duplicates are not detected by hash-based exact deduplication and require MinHash LSH in production ingestion.

---

## 4. Deterministic Train / Validation / Test Contract

### A. Deterministic Partitioning Algorithm
To guarantee 100% reproducibility across environments, split assignment is computed using a cryptographic hash bucket function:

$$\text{hash\_str} = \text{SHA256}(\text{seed} \parallel \text{"::"} \parallel \text{document\_id})$$
$$\text{bucket} = \text{int}(\text{hash\_str}[:8], 16) \pmod{1000}$$

Where:
- $\text{seed}$: A recorded integer or string (default: `"VEDA_CORPUS_SEED_v0.1"`).
- $\text{bucket} \in [0, 999]$.

### B. Default Split Allocation Ratios

| Split | Bucket Range | Percentage | Primary Architectural Purpose |
|---|---|---|---|
| **TRAIN** | `0 .. 899` | **90.0%** | Parametric weight optimization and next-token causal pretraining. |
| **VALIDATION** | `900 .. 949` | **5.0%** | Hyperparameter tuning, learning rate scheduling, and early stopping. |
| **TEST** | `950 .. 999` | **5.0%** | Final out-of-sample perplexity, bits-per-character (BPC), and linguistic evaluation. |

### C. Split Invariants:
1. **Zero Overlap**: $\text{Train} \cap \text{Validation} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Validation} \cap \text{Test} = \emptyset$.
2. **Determinism**: The same document list, seed, and split configuration will **always** produce identical split memberships.
3. **Immutability of Test Set**: Once a corpus version is sealed, the test set documents are cryptographically locked and must not be modified.

---

## 5. Unresolved Policy Decisions

1. `[UNRESOLVED — REQUIRES DECISION]` **Near-Duplicate Detection Algorithm in Production**:
   - Candidate A: Exact string SHA-256 on normalized text (fast, $O(1)$ memory lookup, zero false positives).
   - Candidate B: MinHash + LSH (Locality-Sensitive Hashing) for Jaccard threshold $\ge 0.85$.
   - *Status*: Candidate A (exact normalized deduplication) adopted for v0.1 foundation; MinHash LSH deferred to large-scale multi-gigabyte ingestion.

2. `[UNRESOLVED — REQUIRES DECISION]` **Author-Level vs Document-Level Grouping**:
   - For prolific authors (e.g. Shakespeare, Dickens), whether splitting should group all works of an author into the same split to avoid stylistic leakage.
   - *Status*: Document-level splitting adopted for v0.1; author grouping deferred to curated literary splits.
