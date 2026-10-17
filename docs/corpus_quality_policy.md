# VEDA Corpus Quality & Language Policy (Phase 4)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Quality Filtering, Metrics & Language Policy
Document ID: VEDA-POLICY-QUALITY-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Executive Summary & Filtering Principles

A foundational principle of VEDA is:

$$\text{MORE DATA} \neq \text{AUTOMATICALLY BETTER DATA}$$

Feeding an uncontrolled corpus containing web crawl garbage, OCR noise, boilerplates, and repetitive loops degrades model attention, induces hallucinations, and wastes computational resources.

However:
> [!WARNING]
> **Avoid Aggressive Over-Filtering**:
> False positives (discarding valid, complex, or succinct English prose) can be just as harmful as false negatives. Short dialogue lines, poetic verses, and technical definitions must not be blindly pruned by naive thresholds. Every filter must be justified by empirical linguistic rationale.

---

## 2. Measurable Quality Filters

Every candidate record passes through a battery of measurable, independent quality filters. If a filter fails, the record is rejected, and a structured entry is written to the **Rejection Ledger** with the exact trigger reason.

### Filter Catalog

| Filter Name | Rejection Code | Default Threshold | Evidence & Rationale | Information Risk (False Positive Risk) |
|---|---|---|---|---|
| **Empty or Whitespace** | `EMPTY_TEXT` | Length $= 0$ after trimming | Whitespace-only or empty strings contain zero information. | None. Empty strings are non-linguistic. |
| **Minimum Character Length** | `TOO_SHORT_CHARS` | $\text{len}(\text{norm}) < 25$ chars | Fragments under 25 chars lack complete clausal syntax (subject + predicate + object). | May discard short dialogue replies ("Yes.", "Indeed.") if segmented below paragraph level. |
| **Minimum Word Count** | `TOO_SHORT_WORDS` | $\text{words} < 4$ words | Meaningful English sentences rarely contain fewer than 4 tokens in expository prose. | May discard isolated titles or section headings. |
| **Maximum Character Length** | `TOO_LONG_CHARS` | $\text{len}(\text{norm}) > 15,000$ chars | Paragraphs exceeding 15,000 characters are almost always unsegmented book dumps or log files. | May reject dense 19th-century stream-of-consciousness essays unless segmented. |
| **Alphabetic Character Ratio** | `LOW_ALPHA_RATIO` | $\frac{\text{count}(\text{alpha})}{\text{len}(\text{norm})} < 0.65$ | Natural English prose is typically 75%–85% alphabetic. Ratios below 65% indicate tables, source code, ASCII art, or mathematical dumps. | May flag mathematical expositions, tables, or heavily punctuated poetry. |
| **Symbol & Punctuation Density** | `HIGH_SYMBOL_RATIO` | $\frac{\text{count}(\text{symbols})}{\text{len}(\text{norm})} > 0.20$ | Punctuation/symbols exceeding 20% indicates tabular borders (`|---|`), code fragments (`{};()`), or OCR scan noise. | May flag complex citations or nested parenthetical references. |
| **Corrupted / Unassigned Unicode** | `HIGH_UNREGISTERED_RATIO` | Presence of U+FFFD, surrogates (`Cs`), unassigned (`Cn`), or unrepresented codepoints $> 0.05$ | Corrupted byte sequences or unassigned codepoints represent decoding failures. *Note*: In accordance with `docs/corpus_unicode_policy.md`, corpus curation does NOT reject valid Latin loanwords merely because the Phase 1 character tokenizer lacks them. | May flag corrupt scans or non-standard private-use symbols. |
| **Character Repetition Loop** | `REPEATED_CHARS` | Max consecutive identical char run $> 4$ (e.g. `aaaaa`, `-----`) | English words never contain more than 2 consecutive identical letters (with rare 3-letter exceptions like *goddessship*). Runs of 5+ indicate layout decoration or keyboard mash. | May flag intentional horizontal rules (`-----`). |
| **Word Repetition Loop** | `REPEATED_WORDS` | Same word repeated $\ge 4$ times consecutively | "the the the the" is a classic web crawler loop or hallucination artifact. | Negligible in grammatical English prose. |
| **Common English Stopword Presence** | `NO_ENGLISH_STOPWORDS` | At least 1 stopword for texts with $\ge 8$ words, and at least 2 distinct stopwords for texts $\ge 15$ words | Any coherent English passage almost invariably includes function words (`the`, `and`, `of`, `to`, `in`, `is`, `that`). Prevents Latin-script foreign languages (French, German) from masquerading as English. | May reject lists of technical terminology without prose syntax. |
| **Boilerplate Signature** | `BOILERPLATE_CONTENT` | Matches known boilerplate patterns (e.g. "All rights reserved", "Terms of Service") | Legal disclaimers, cookie notices, and site navigation do not contribute to language understanding. | None if matched strictly on verified exact signatures. |

---

## 3. Language Policy (v0.1 English Scope)

### A. Separation of Concerns: English $\neq$ ASCII
VEDA's orthography policy strictly maintains that **English is not identical to ASCII**.
- Valid English vocabulary includes recognized loanwords with diacritics (*café*, *naïve*, *cliché*, *façade*, *résumé*).
- An English document containing loanwords or occasional French/Latin quotations (*ad hoc*, *de facto*, *et cetera*) is an authentic English text.

### B. Language Classification Rules
1. **Primary Language Acceptance**:
   - The document or source must be declared and verified as English (`en`).
   - If language metadata is missing, heuristic stopwords and character profiling are applied.
2. **Quoted Foreign Phrases & Loanwords**:
   - Isolated non-English words or brief quoted passages are permitted if the host record is predominantly English ($\ge 85\%$ English vocabulary).
3. **Multilingual & Code-Switching Records**:
   - Documents with balanced multilingual mixtures (e.g. bilingual Canadian government notices, dual-language dictionaries) are **excluded** from v0.1 single-language pretraining.
4. **Script Composition vs. Language Identity**:
   - VEDA strictly distinguishes *Language Identity* (English vs. Non-English) from *Script Composition* (Latin vs. Non-Latin ratio).
   - $\text{Latin Script} \neq \text{English}$: Pure French, German, or Spanish texts use Latin script, but lack English function words and are rejected under `NO_ENGLISH_STOPWORDS`.
   - $\text{Non-Latin Script} \neq \text{Non-English Document}$: Authentic English scientific, mathematical, and philosophical texts containing legitimate Greek variables ($\lambda, \omega$), foreign names (*Socrates (Σωκράτης)*), or citations (*Metaphysics (Τὰ μετὰ τὰ φυσικά)*) are **ACCEPTED** provided $\text{non\_latin\_ratio} \le 0.15$ and $\text{non\_latin\_count} \le 30$.
   - Predominantly non-Latin texts (where non-Latin characters exceed 15% ratio or run $> 30$ letters) are rejected under `NON_ENGLISH_SCRIPT`.
5. **Unknown Language Status**:
   - If language cannot be determined with high confidence, status is set to `UNKNOWN` and the record is held in the review quarantine. It is never silently admitted.

---

## 4. Quality Scoring Function

In addition to hard binary rejection, every accepted record receives a continuous `quality_score` $\in [0.0, 1.0]$:

$$S_\text{quality} = w_1 \cdot S_\text{alpha} + w_2 \cdot S_\text{length} + w_3 \cdot S_\text{vocab} + w_4 \cdot S_\text{punct}$$

Where:
- $S_\text{alpha} = \min\left(1.0, \frac{\text{alpha\_ratio}}{0.80}\right)$ (rewards natural letter balance)
- $S_\text{length} = \text{bell\_curve}(\text{word\_count}, \mu=150, \sigma=75)$ (rewards typical paragraph lengths)
- $S_\text{vocab} = \frac{\text{unique\_words}}{\text{total\_words}}$ (rewards lexical diversity)
- $S_\text{punct} = 1.0 - \text{penalty}(\text{excessive\_symbols})$

Records with $S_\text{quality} < 0.50$ can be filtered out during downstream training selection.

---

## 5. Unresolved Policy Decisions

1. `[UNRESOLVED — REQUIRES DECISION]` **Heuristic Language Detector vs. Pretrained Model**:
   - Whether language verification should rely on a pure zero-dependency Python stopword/n-gram frequency profiler or an external fastText classifier.
   - *Status*: Pure zero-dependency stopword & character frequency profiler adopted for v0.1 in line with first-principles guidelines.

2. `[UNRESOLVED — REQUIRES DECISION]` **Poetry & Short Verse Acceptance**:
   - Whether short poetic lines (often failing $\ge 25$ char or $\ge 4$ word thresholds) should have a separate bypass rule if source genre is `poetry`.
   - *Status*: Standard thresholds enforced for v0.1 general prose pretraining; specialized genre bypass deferred to v0.2.
