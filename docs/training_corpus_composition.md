# VEDA Training Corpus Target Composition
## Linguistic Distribution, Domain Taxonomy & Provisional Budget Allocation (Phase 4.2)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Training Corpus Composition & Domain Balance
Document ID: VEDA-POLICY-COMPOSITION-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.2.1
========================================================================================
```

---

## 1. Executive Summary & Design Principles

The objective of Project VEDA is to cultivate language intelligence from first principles without relying on opaque pretrained checkpoints. 

To achieve this, the training corpus must provide a balanced, intellectually rigorous exposure to the full breadth of the English language. A model trained exclusively on one genre (e.g., only 19th-century fiction, or only Wikipedia, or only technical manuals) develops severe stylistic blind spots, skewed token distributions, and degraded generalization.

### Core Architectural Principles
1. **Linguistic Depth Over Uncurated Volume**: High-quality, syntactically complete, and coherent prose delivers far greater statistical learning signal per token than billions of noisy, auto-translated, or repetitive web pages.
2. **Provisional Allocation**: All category percentages defined herein are explicitly designated as **provisional planning targets**. They will be calibrated empirically following source-level extraction pilots and deduplication measurement.
3. **Strict Decoupling of Lexicon from Running Discourse**:
   $$\text{Lexical Knowledge (Phase 3)} \neq \text{General Language Exposure (Phase 4)}$$
   Dictionary definitions provide discrete word sense boundaries and phonetic representations; they do **not** provide narrative progression, logical argumentation, or conversational pragmatics.

---

## 2. Seven-Category Domain Taxonomy

The VEDA English training corpus is structured across seven distinct categories:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   VEDA TRAINING CORPUS COMPOSITION                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
       ┌──────────────┬─────────────┼──────────────┬──────────────┐
       ▼              ▼             ▼              ▼              ▼
  [1. Books &    [2. Educ. &   [3. Science &  [4. General    [5. Reference &
   Literature]   Explanatory]   Technical]     Prose/News]    Encyclopedic]
      (35%)         (25%)          (15%)          (15%)          (10% gated)
       │              │             │              │              │
       └──────────────┴─────────────┼──────────────┴──────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            [6. Dialogue &                   [7. Lexical
            Conversational]                  Resources]
           (0% active; 5% gated)          (Discrete Reference)
```

---

### Category 1: Books and Long-Form Writing

- **Purpose**: Instill deep syntactic coherence, complex multi-clause sentence structures, rich literary vocabulary, narrative arc progression, and sustained discourse context spanning thousands of tokens.
- **Candidate Source Types**: Public-domain literature, classical essays, historical narratives, philosophy (Standard Ebooks, Project Gutenberg).
- **Provisional Target Share**: **35%** (High Priority)
- **Quality Risks**: Archaic orthography and syntax (e.g. *thou*, *thee*, *betwixt*), historical racial or colonial stereotypes, OCR artifacts in non-proofread editions.
- **Duplication Risks**: High cross-edition duplication (e.g., dozens of digitized editions of *Pride and Prejudice* across Gutenberg mirrors). Handled via document-level exact and normalized deduplication.
- **Licensing Constraints**: Public Domain (pre-1929 US publication) or CC0. Project Gutenberg boilerplate (license headers/footers) must be excised.
- **Cognitive Contribution**: **Language Exposure** (syntax, narrative coherence, figurative language) + **Lexical Knowledge** (historical and literary vocabulary).

---

### Category 2: Educational and Explanatory Material

- **Purpose**: Teach explanatory reasoning, pedagogical progression ("concept A leads to concept B"), structured definitions embedded in context, and expository clarity.
- **Candidate Source Types**: Peer-reviewed college textbooks, high school curricula, educational guides, tutorial lectures (OpenStax, Wikibooks).
- **Provisional Target Share**: **25%** (High Priority)
- **Quality Risks**: Repetitive exercise problem sets, multiple-choice questions without explanatory context, index and glossary fragmentation.
- **Duplication Risks**: Low across textbooks; moderate within problem-set answer keys.
- **Licensing Constraints**: CC-BY 4.0 (OpenStax — requires attribution preserved in provenance) or CC0. Wikibooks gated under CC-BY-SA review.
- **Cognitive Contribution**: **Language Exposure** (structured expository syntax) + **Lexical Knowledge** (foundational domain terminology).

---

### Category 3: Science, Mathematics, and Technical Writing

- **Purpose**: Expose the model to formal scientific methodology, empirical analysis, technical precision, hypothesis testing, Greek symbolic usage ($\lambda, \omega$), and mathematical notation embedded in English prose.
- **Candidate Source Types**: Peer-reviewed scientific journals, technical documentation, software specifications (PLOS Open Access, Python Official Documentation).
- **Provisional Target Share**: **15%** (Medium-High Priority)
- **Quality Risks**: Dense tabular data, raw code blocks lacking narrative commentary, excessive citation strings, formula-heavy passages lacking English function words (filtered by `QualityFilter.symbol_ratio`).
- **Duplication Risks**: Low across scientific papers; moderate in technical documentation across minor software releases.
- **Licensing Constraints**: CC-BY 4.0 (PLOS — text and data mining explicitly authorized); PSFL / 0BSD (Python Docs).
- **Cognitive Contribution**: **Language Exposure** (logical transitions, formal register) + **Lexical Knowledge** (STEM vocabulary, technical nomenclature).

---

### Category 4: General Prose, Essays, and Contemporary Journalism

- **Purpose**: Ground the model in modern English syntax, active-voice discourse, factual reporting, contemporary civic vocabulary, and journalistic economy of expression.
- **Candidate Source Types**: Openly licensed news reporting, investigative journalism, contemporary essays, cultural critiques (Wikinews, open-access public interest essays).
- **Provisional Target Share**: **15%** (Medium Priority)
- **Quality Risks**: Short news wire snippets (< 100 words), datelines, repeated press release syndication, biased opinion pieces.
- **Duplication Risks**: High syndication duplication across news outlets. Exact and near-duplicate deduplication mandatory.
- **Licensing Constraints**: CC-BY 2.5 (Wikinews — attribution only; zero ShareAlike restriction).
- **Cognitive Contribution**: **Language Exposure** (modern active-voice prose, pragmatic world events) + **Lexical Knowledge** (contemporary idioms and institutional vocabulary).

---

### Category 5: Reference and Encyclopedic Material

- **Purpose**: Broad factual world knowledge across history, geography, arts, science, biography, and cultural institutions; concise multi-sentence factual summaries.
- **Candidate Source Types**: Simple English Wikipedia, English Wikipedia, open encyclopedic reference works.
- **Provisional Target Share**: **10%** (Provisional & Gated)
- **Quality Risks**: Severe wikitext template noise, infoboxes, citation brackets (`[1]`), disambiguation lists, vandalism, edit-warring instability.
- **Duplication Risks**: High internal circular linking and content mirroring across language variants.
- **Licensing Constraints**: **GATED UNDER REQUIRES_REVIEW**. CC-BY-SA 4.0 ShareAlike legal debate regarding neural model weight distribution must be formally resolved before production ingestion.
- **Cognitive Contribution**: **Language Exposure** (factual reference syntax) + **Lexical Knowledge** (encyclopedic entities and proper nouns).

---

### Category 6: Dialogue and Conversational Text

- **Purpose**: Impart multi-turn interaction dynamics, conversational pragmatics, interrogative/responsive structures, polite discourse, and instruction-following syntax.
- **Candidate Source Types**: OpenAssistant OASST2, open educational dialogue transcripts, public domain drama scripts (Shakespeare, Shaw).
- **Provisional Target Share**: **0% Active** (Planned 5% allocation once PII screening tooling is validated).
- **Quality Risks**: Toxic language, prompt injections, low-effort conversational quips, hallucinations in crowdsourced data.
- **Duplication Risks**: Common user prompt repetitions ("Hello", "Who are you?").
- **Licensing Constraints**: Apache 2.0 (OpenAssistant). Must pass PII detection and toxic content filtering. Uncurated chat dumps (e.g. Ubuntu IRC) are permanently `EXCLUDED`.
- **Cognitive Contribution**: **Language Exposure** (interpersonal pragmatics, question-answering dynamics).

---

### Category 7: Lexical Resources (Discrete Ground Truth)

- **Purpose**: Definitive lexical dictionary ground truth, morphological inflections, part-of-speech validation, and IPA phonetic transcriptions.
- **Candidate Source Types**: Wiktextract English Dictionary, WordNet, VEDA Production Lexicon SQLite.
- **Provisional Target Share**: **0% of Running Pretraining Discourse Splits**
- **CRITICAL ARCHITECTURAL DISTINCTION**:
  - The Lexicon is structured lexical reference knowledge (**Phase 3**).
  - It consists of isolated lemma definitions and pronunciation tags.
  - Feeding raw dictionary glosses as a primary pretraining corpus creates severe autoregressive pathology: the model learns repetitive dictionary formatting rather than coherent narrative thought.
  - The Lexicon's role is to evaluate, verify, and ground tokenization and lexical coverage, **not** to serve as natural running pretraining text.
- **Cognitive Contribution**: **Pure Lexical Knowledge** (isolated semantic definitions, morphological validation).

---

## 3. The Five Composition Distributions (Decoupling Theory from Measurement)

To prevent conflating provisional research aspirations with active legal authorizations or small pilot fixtures, VEDA strictly formalizes five distinct composition levels:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        VEDA FIVE-TIER CORPUS COMPOSITION MODEL                         │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│ LEVEL 1: Desired Target Model     │ Provisional planning target (35:25:15:15:10:0:0)   │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ LEVEL 2: Eligible Rebalancing     │ Mathematical reallocation formula when gates block │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ LEVEL 3: Measured Pilot Fixture   │ Controlled pilot execution (10 retained records)   │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ LEVEL 4: Actual Retained Corpus   │ NOT YET MEASURED (Production ingestion not begun)  │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ LEVEL 5: Training Token Exposure  │ NOT YET MEASURED (Tokenizer design in Phase 5-6)   │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

### Level 1: Desired Target Distribution (Provisional Research Target)

Level 1 represents the long-term research objective for the eventual training corpus once all licensing ambiguities and filtering pipelines are fully certified:

| Domain Category | Target Share | Target Unit | Denominator | Candidate Sources | Licensing Review Status |
|---|---|---|---|---|---|
| **1. Books & Long-Form Writing** | 35.0% | Tokens / Chars | Total planned corpus tokens | Standard Ebooks, Project Gutenberg | `REQUIRES_REVIEW` (Artifacts unacquired) |
| **2. Educational & Explanatory** | 25.0% | Tokens / Chars | Total planned corpus tokens | OpenStax Textbooks | `REQUIRES_REVIEW` (Artifacts unacquired) |
| **3. Science & Technical** | 15.0% | Tokens / Chars | Total planned corpus tokens | PLOS Open Access, Python Docs | `REQUIRES_REVIEW` (Artifacts unacquired) |
| **4. General Prose & News** | 15.0% | Tokens / Chars | Total planned corpus tokens | Wikinews (CC-BY 2.5) | `REQUIRES_REVIEW` (Artifacts unacquired) |
| **5. Encyclopedic Reference** | 10.0% | Tokens / Chars | Total planned corpus tokens | Simple Wikipedia, English Wikipedia | `REQUIRES_REVIEW` (CC-BY-SA Gated) |
| **6. Dialogue & Interaction** | 0.0% (5% planned) | Tokens / Chars | Total planned corpus tokens | OpenAssistant (Apache 2.0) | `REQUIRES_REVIEW` (PII Filter Gated) |
| **7. Lexical Resources** | 0.0% (Discrete) | Lemmas / Senses | Discrete SQLite DB | Wiktextract (Phase 3 SQLite) | Isolated from prose splits |
| **Total** | **100.0%** | — | — | — | Comprehensive Pretraining Baseline |

---

### Level 2: Eligible Source Availability & Proportional Reallocation Formula

When candidate sources in a category are blocked, under review, or unacquired, their active ingestion allocation is reset to $0.00\%$. The remaining categories are rebalanced **strictly as a provisional target reallocation**, NOT as proof of actual corpus content:

$$w_i' = \frac{w_i}{\sum_{j \in \text{Eligible}} w_j}$$

- When Category 5 (10%) and Category 6 (0%) are gated, the active target sum is $35 + 25 + 15 + 15 = 90\%$.
- The rebalanced theoretical target shares are:
  - Category 1: $35 / 90 = 38.89\%$
  - Category 2: $25 / 90 = 27.78\%$
  - Category 3: $15 / 90 = 16.67\%$
  - Category 4: $15 / 90 = 16.67\%$
- If Category 4 (Wikinews) is additionally deferred, the 3-category rebalance ($35 + 25 + 15 = 75\%$) yields:
  - Category 1: $35 / 75 = 46.67\%$
  - Category 2: $25 / 75 = 33.33\%$
  - Category 3: $15 / 75 = 20.00\%$
- **CRITICAL ARITHMETIC NOTICE**: This reallocation is a mathematical target formula. It does **not** prove that any physical production corpus has been ingested with this distribution.

---

### Level 3: Measured Controlled Pilot Distribution (Empirical Fixture)

The controlled pilot (`scripts/run_corpus_pilot.py`) was executed on 9 synthetic/sample documents across 3 pilot sources. The **empirically measured** distribution of the pilot is:

| Domain Category | Pilot Sources | Input Docs | Retained Docs | Retained Records | Share of Retained Records | Retained Characters | Share of Retained Chars |
|---|---|---|---|---|---|---|---|
| **Cat 1: Books & Literature** | `standard_ebooks_pilot` | 5 | 3 | 6 | **60.0%** | 2,752 | **62.8%** |
| **Cat 2: Educational** | None in pilot | 0 | 0 | 0 | **0.0%** | 0 | **0.0%** |
| **Cat 3: Technical Docs** | `python_docs_pilot` | 3 | 2 | 4 | **40.0%** | 1,627 | **37.2%** |
| **Cat 4: General News** | None in pilot | 0 | 0 | 0 | **0.0%** | 0 | **0.0%** |
| **Cat 5: Encyclopedic** | None in pilot | 0 | 0 | 0 | **0.0%** | 0 | **0.0%** |
| **Cat 6: Dialogue** | None in pilot | 0 | 0 | 0 | **0.0%** | 0 | **0.0%** |
| **Cat 7: Gated Unapproved** | `unapproved_gated_source`| 1 | 0 (Blocked) | 0 | **0.0%** | 0 | **0.0%** |
| **Total Measured Pilot** | 3 Sources | 9 | 5 | 10 | **100.0%** | 4,379 | **100.0%** |

*Measurement Denominator*: 10 retained pilot records (or 4,379 normalized characters).  
*Notice*: The pilot tests pipeline mechanics, conservation laws, deduplication, and failure recovery. It does **not** represent production corpus composition.

---

### Level 4: Actual Retained Production Corpus Composition

- **Current Status**: **`NOT YET MEASURED`**
- **Measurement Method**: Full enumeration of all serialized JSONL shards (`train.jsonl`, `val.jsonl`, `test.jsonl`).
- **Measurement Denominator**: Total retained characters in published corpus release.
- **Ingestion Precondition**: Production ingestion remains strictly unauthorized until external artifacts and licensing evidence documents are verified and ratified.
- **Reported Value**: `0.00 GB / NOT YET MEASURED`.

---

### Level 5: Actual Training-Token Exposure

- **Current Status**: **`NOT YET MEASURED`**
- **Measurement Method**: Token count output from the VEDA BPE/Subword tokenizer (Phase 5–6).
- **Measurement Denominator**: Total integer token IDs consumed by the neural pretraining engine (Phase 7).
- **Reported Value**: `0 Tokens / NOT YET MEASURED`.

---

## 4. Measurement Accounting & Non-Equivalence Principles

### A. Document Counts $\neq$ Token Exposure
Document counts are **never** used as a proxy for training exposure:
- A single book in Category 1 may contain 150,000 words (800,000 characters).
- A news article in Category 4 may contain 300 words (1,800 characters).
- Equating documents would severely over-represent short news wire snippets and starve the model of long-range syntactic signal.
- Ingestion metrics report:
  1. Input and retained document counts
  2. Input and retained paragraph/record counts
  3. Total UTF-8 character volume in NFC
  4. Final token counts (measured once the Phase 5 subword tokenizer is trained)

### B. Summary of Composition Status Across Levels

| Level | Description | Scope | Status |
|---|---|---|---|
| **Level 1** | Desired Target Distribution | Planning Model | Ratified provisional targets (35:25:15:15:10:0:0) |
| **Level 2** | Eligible Target Rebalancing | Mathematical Formula | Rebalanced target proportions when gates block |
| **Level 3** | Measured Pilot Composition | Engineering Fixture | 10 records (60% Cat 1, 40% Cat 3; 4,379 chars) |
| **Level 4** | Retained Production Corpus | Physical Ingestion | **NOT YET MEASURED** (Production ingestion blocked) |
| **Level 5** | Training Token Exposure | Pretraining Engine | **NOT YET MEASURED** (Deferred to Phase 5–7) |

---

## 5. Quality & Language Filtering Heuristics Evaluation

Quality filtering and English-language detection are engineering heuristics with measurable false-positive and false-negative rates, **not ground truth**:

```
┌────────────────────────────────────────────────────────────────────────┐
│             THREE-TIER HEURISTIC LANGUAGE VERIFICATION                 │
├────────────────────────────────────────────────────────────────────────┤
│ 1. SCRIPT VERIFICATION: Unicode Latin Block NFC Check                  │
│    (Ensures character representability; does NOT prove English)        │
│                                                                        │
│ 2. LEXICAL STOPWORD FREQUENCY: High-Frequency Function Words           │
│    (the, and, of, to, in, that, is, was, for, with)                    │
│    (Separates English from French/German Latin text; heuristic only)   │
│                                                                        │
│ 3. STRUCTURAL INTEGRITY: Word Length & Alpha-to-Symbol Ratios          │
│    (Filters out ASCII art, formula dumps, machine logs)                │
└────────────────────────────────────────────────────────────────────────┘
```

### Empirical Heuristic Limitations
1. **Script vs Language**: Latin script is shared across hundreds of languages. Verifying that a document contains NFC Latin characters (*café*, *résumé*) does not confirm that the language is English.
2. **Stopwords vs Meaning**: A technical glossary or mathematical theorem may contain genuine English concepts but have a depressed stopword ratio. `QualityFilter` thresholds are empirically calibrated to avoid dropping technical prose.
3. **Loanword Authenticity**: Authentic English literature contains naturalized loanwords (*façade*, *naïve*, *vis-à-vis*). The VEDA normalization engine preserves these in NFC without ASCII folding.
