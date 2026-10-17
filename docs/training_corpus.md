# VEDA Training Corpus Specification (Phase 4)
## Objectives, Architectural Role & Linguistic Scope

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Training Corpus Objective & Design
Document ID: VEDA-CORPUS-SPEC-v0.1
Status: DESIGN SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Executive Summary: The Core Mission

VEDA (*From Knowledge to Intelligence*) builds an English-first language model from first principles without relying on third-party pretrained weights, proprietary APIs, or opaque training datasets.

Phase 1 established the **Character Foundation** (113 registered characters + 4 control tokens).  
Phase 2 established the **Word Foundation** (morphological candidate validation and character ID mapping).  
Phase 3 established the **Production Lexicon** (959,688 words, 1,049,403 POS entries, 1,322,676 senses in SQLite).

**Phase 4 establishes the Training Corpus Architecture.**

> [!CRITICAL]
> **Fundamental Architectural Axiom: The Lexicon is NOT the Training Corpus.**
> - **The Lexicon** provides structured, authoritative *lexical knowledge* (definitions, parts of speech, phonetics, inflections).
> - **The Training Corpus** provides natural-language running discourse from which the neural model learns *statistical structure, syntax, and generative coherence*.
> 
> Converting the 959,688 lexical entries directly into a text file and treating it as a training corpus is an anti-pattern. Dictionaries lack document-level narrative flow, discourse markers, conversational transitions, and syntactic variety. The training corpus must be an independently sourced, curated, and governed system.

---

## 2. Lexical Knowledge vs. Language Exposure

The distinction between structured knowledge and natural exposure is central to VEDA:

```
┌──────────────────────────────────────────────┐       ┌──────────────────────────────────────────────┐
│             PRODUCTION LEXICON               │       │               TRAINING CORPUS                │
│             (Lexical Knowledge)              │       │             (Language Exposure)              │
├──────────────────────────────────────────────┤       ├──────────────────────────────────────────────┤
│ • Ground-truth definitions & senses          │       │ • Continuous running discourse & paragraphs  │
│ • Grammatical POS categories                 │       │ • Complex syntactic dependencies             │
│ • IPA phonetic pronunciations                │       │ • Pragmatic and contextual usage             │
│ • Exact inflected lemma mappings             │       │ • Discourse transitions & narrative flow     │
│ • Morphological bounds                       │       │ • Factual exposition & world knowledge       │
│ • Static reference dictionary (SQLite)       │       │ • Versioned, split, and filtered sequences   │
└──────────────────────────────────────────────┘       └──────────────────────────────────────────────┘
                       │                                                      │
                       ▼                                                      ▼
        Constrains & Validates Vocabulary                       Trains Neural Sequence Dynamics
```

---

## 3. What Should the Initial Corpus Teach VEDA?

The initial pretraining corpus must instill fundamental linguistic competence in the nascent model:

1. **Syntactic Competence**:
   - Standard English clause structures: Subject-Verb-Object (SVO), subordinate clauses, relative clauses, passive constructions, conditionals, questions, and imperatives.
   - Punctuation dynamics: Proper comma delimitation, quotation dialog boundaries, colon/semicolon transitions, parentheses, and sentence termination (`.`, `!`, `?`).
   - Morphosyntactic agreement: Subject-verb agreement, pronoun-antecedent agreement, and tense consistency.

2. **Semantic Coherence**:
   - Topical consistency across multi-sentence paragraphs.
   - Coreference resolution across sentences (e.g., matching pronouns to their referents).
   - Lexical variety and synonym substitution in context.

3. **Discourse Dynamics**:
   - Logical transitions (`however`, `furthermore`, `consequently`, `in contrast`).
   - Structural exposition (introductions, evidence presentation, arguments, summaries).

4. **Broad Lexical Vocabulary in Context**:
   - Exposing the model to the rich vocabulary codified in the Phase 3 Lexicon as it actually appears in human writing.

---

## 4. In-Scope vs. Out-of-Scope Text

### A. Target Content (In-Scope)
1. **Expository & Educational Prose**: Curated encyclopedic articles, academic overviews, high-quality open textbooks, and scientific explanations.
2. **Public-Domain Literary & Historical Prose**: High-quality narrative fiction, essays, historical records, and speeches (e.g., curated Project Gutenberg texts).
3. **Structured Reference Expositions**: Explanatory manuals, non-fiction essays, and peer-reviewed educational materials with clear paragraph structure.
4. **Curated Dialogue**: Well-edited conversational prose demonstrating turn-taking, interrogatives, and conversational norms.

### B. Prohibited Content (Out-of-Scope & Excluded)
1. **Unfiltered Web Crawls / SEO Spam**: Scraped commercial web text containing keyword stuffing, affiliate links, and automated gibberish.
2. **Boilerplate & Navigation Content**: Cookie notices, copyright footers, navigation headers, sidebar menus, and "click here" prompts.
3. **Machine-Generated Artifacts**: Synthetic gibberish, OCR hallucination text, unedited automated translations, and low-quality LLM dump text.
4. **Source Code & Markup Only**: Unannotated raw HTML, CSS, JavaScript, JSON dumps, or programming code repositories (VEDA v0.1 is an English natural-language model).
5. **Toxic, Abusive, or PII Content**: Unmoderated forum dumps, hate speech, private personal data (emails, phone numbers, addresses).
6. **Corrupted & Malformed Data**: Null bytes, invalid UTF-8 byte streams, repetitive garbage sequences (`aaaaaaa...`), and unprintable binary sequences.

---

## 5. Objectives: Language Modeling vs. Factual Knowledge

### A. Primary Objective: Causal Language Modeling
The primary objective of the initial VEDA corpus is **autoregressive causal language modeling**: learning the statistical probability distribution $P(w_t \mid w_{<t})$ over coherent English sequences. The model must first learn how English functions before it can reliably store or recall facts.

### B. Secondary Objective: Factual Foundations
Factual knowledge is an emergent property of high-quality training text. However:
- VEDA will **not** attempt to force a compact v0.1 model to memorize all world facts within its parametric weights.
- Long-term factual precision will be supported by the Phase 11 Modular RAG (Retrieval-Augmented Generation) system.
- The pretraining corpus must focus on **factually sound, well-structured sources** to avoid entraining false lexical or world patterns.

### C. Target Source Balance

| Content Category | Target Share | Rationale |
|---|---|---|
| **Expository / Encyclopedic Prose** | **55% – 65%** | Maximizes grammatical precision, informational density, and factual coherence. |
| **Narrative Literature & Essays** | **25% – 35%** | Provides syntactic diversity, dialogue, figurative language, and complex clause structures. |
| **Curated Dialogue / Explanatory Q&A** | **5% – 10%** | Teaches conversational framing and direct question-answer transitions. |

---

## 6. Unresolved Corpus Design Decisions

In strict accordance with VEDA design governance, the following decisions are explicitly recognized as unresolved and must be formally ratified before production corpus ingestion:

1. `[UNRESOLVED — REQUIRES DECISION]` **Exact Training-Eligible Source Corpus Selection**:
   - Candidate A: Curated subset of Project Gutenberg (Standard Ebooks quality tier, verified public domain / CC0).
   - Candidate B: Cleaned English Wikipedia / Simple English Wikipedia abstracts.
   - Candidate C: Curated OpenStax textbooks and scientific open-access papers.
   - *Status*: Awaiting licensing review and pilot distribution analysis.

2. `[UNRESOLVED — REQUIRES DECISION]` **Target Pretraining Corpus Size (Token/Character Budget)**:
   - Option A: Small scale (~10 Million words / ~50 MB text) for rapid cycle validation.
   - Option B: Medium scale (~100 Million words / ~500 MB text) for baseline model competence.
   - Option C: Large scale (~1 Billion+ words) for production pretraining.
   - *Status*: Awaiting compute budget and model parameter sizing (Phase 5/6).

3. `[UNRESOLVED — REQUIRES DECISION]` **Handling of Technical / Mathematical Notation**:
   - Whether LaTeX equations (`$E=mc^2$`) should be normalized to natural English prose ("E equals m c squared"), preserved verbatim, or excluded from v0.1.
   - *Status*: Deferred to specialized domain corpus policy.
