# VEDA Corpus Unicode & Representability Policy (Phase 4.1)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Corpus Unicode Policy & Representability Boundaries
Document ID: VEDA-POLICY-UNICODE-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.1 HARDENING
========================================================================================
```

---

## 1. The Core Architectural Boundary: Corpus $\neq$ Tokenizer $\neq$ Model

A central architectural defect identified in Phase 4 was the premature coupling of Corpus Quality Filtering to the Phase 1 Character Tokenizer Registry (`CharacterRegistry`, 113 characters).

VEDA enforces strict separation across three orthogonal representational boundaries:

```
┌────────────────────────────────────────────────────────┐
│ 1. CORPUS TEXT & UNICODE POLICY                         │ Natural English discourse, loanwords, typography
└───────────────────────────┬────────────────────────────┘
                            │ Normalization (NFC, control stripping) & Quality Filter
┌───────────────────────────▼────────────────────────────┐
│ 2. CORPUS RECORD (Storage Contract)                     │ Immutable UTF-8 text (raw_text & normalized_text)
└───────────────────────────┬────────────────────────────┘
                            │ Tokenizer Mapping (Character, BPE, WordPiece, Byte-Fallback)
┌───────────────────────────▼────────────────────────────┐
│ 3. TOKENIZER VOCABULARY                                │ Discrete integer indices (0..V-1) + <UNK>
└───────────────────────────┬────────────────────────────┘
                            │ Embedding Layer Lookup (W_emb[token_id])
┌───────────────────────────▼────────────────────────────┐
│ 4. NEURAL MODEL REPRESENTATION                         │ Continuous vector space (d_model tensors)
└────────────────────────────────────────────────────────┘
```

### Invariant Rules:
1. **Corpus Autonomy**: The corpus must **never** reject authentic English discourse merely because the active tokenizer cannot represent a character.
2. **Tokenizer Evolution Invariance**: When VEDA transitions from the v0.1 reference character tokenizer to subword tokenizers (BPE, SentencePiece) or byte-fallback tokenizers in future phases, **the corpus dataset must not require re-curation**.
3. **Decoupled Quality Filtering**: Corpus quality filtering evaluates linguistic coherence, symbol density, and encoding corruption based on Unicode standards and English language policy—**not** membership in a specific tokenizer vocabulary.

---

## 2. Unicode Categorization & Transform Taxonomy

Every Unicode sequence encountered by the corpus curation pipeline is deterministically mapped to one of five actions:

```
[RAW UNICODE CHARACTER]
       │
       ├─► PRESERVED   : Retained verbatim in raw_text and normalized_text
       ├─► NORMALIZED  : Deterministically transformed to canonical Unicode standard
       ├─► FILTERED    : Stripped during normalization (e.g. non-linguistic control codes)
       ├─► REJECTED    : Triggers record-level rejection and logging to Rejection Ledger
       └─► QUARANTINED : Held in review queue due to unverified language/source status
```

### Authoritative Category Matrix

| Input Category | Concrete Examples | Pipeline Action | Resulting Form | Rationale |
|---|---|---|---|---|
| **ASCII Letters & Digits** | `Apple`, `apple`, `NASA`, `1984` | **PRESERVED** | Exact casing & digits preserved | Foundational English alphabetic & numeric text. Capitalization conveys essential syntax and named entities. |
| **Standard English Contractions** | `don't`, `it's`, `o'clock`, `we've` | **PRESERVED** | Preserved verbatim (`'`) | Universal English orthography. |
| **Hyphenated Compounds** | `co-operate`, `state-of-the-art` | **PRESERVED** | Preserved verbatim (`-`) | Standard English morphological compounding. |
| **Typographical Quotes** | `“hello”`, `‘hello’` | **PRESERVED** | Preserved verbatim (`“`, `”`, `‘`, `’`) | Standard English book typography. Teaches correct quote orientation. |
| **Typographical Dashes** | En-dash `–`, Em-dash `—` | **PRESERVED** | Preserved verbatim (`–`, `—`) | Distinct syntactic roles in English prose (ranges vs. parenthetical clauses). |
| **Typewriter Hyphens** | `--` or `---` | **NORMALIZED** | Standardized to em-dash `—` | Reconstructs authorial typographical dash from plain-text transcription conventions. |
| **Ellipses** | Running dots `...` (3+ dots) | **NORMALIZED** | Standardized to Unicode `…` (U+2026) | Canonical typographical ellipsis representation. |
| **Latin Accented Loanwords** | `café`, `naïve`, `résumé`, `cliché` | **PRESERVED** | Retained with diacritics in `NFC` | Authentic English dictionary words and literary borrowings. Must NOT be stripped or rejected. |
| **Foreign Proper Names** | `Poincaré`, `Gödel`, `Brontë` | **PRESERVED** | Retained with diacritics in `NFC` | Standard English scholarly, biographical, and literary discourse. |
| **Combining Diacritics** | `e` + `\u0301` (decomposed `é`) | **NORMALIZED** | Composed to precomposed NFC `é` (U+00E9) | Enforces deterministic byte equality and eliminates Unicode decomposition ambiguities. |
| **Standard Math & Symbols** | `24°`, `±2°`, `10 × 5`, `100 ÷ 2`, `≤`, `≥` | **PRESERVED** | Preserved verbatim in `NFC` | Scientific, historical, and expository numeric context. |
| **Currency Symbols** | `$`, `£`, `€`, `¥` | **PRESERVED** | Preserved verbatim | Economic and narrative prose context. |
| **HTML Entities** | `&amp;`, `&quot;`, `&lt;`, `&#8212;` | **NORMALIZED** | Decoded to genuine characters (`&`, `"`, `<`, `—`) | Extracts genuine human prose from markup transcripts. |
| **HTML / XML Tags** | `<p>text</p>`, `<b>bold</b>` | **FILTERED** | Tags stripped, inner text retained | Eliminates document formatting markup while preserving prose. |
| **Horizontal Whitespace** | `\t`, `\u00a0` (NBSP), multiple spaces `   ` | **NORMALIZED** | Collapsed to single space `' '` | Normalizes irregular indentation and typography layout artifacts. |
| **Linebreaks** | `\r\n` (CRLF) or `\r` (CR) | **NORMALIZED** | Standardized to Unix LF (`\n`) | Ensures cross-platform file hash determinism. |
| **Vertical Whitespace Runs** | 3+ consecutive newlines (`\n\n\n+`) | **NORMALIZED** | Collapsed to exactly 2 newlines (`\n\n`) | Preserves paragraph breaks while eliminating blank page padding. |
| **Control Characters** | `0x00..0x08`, `0x0B..0x0C`, `0x0E..0x1F`, `0x7F` | **FILTERED** | Stripped from string | Non-linguistic transmission codes and null bytes are removed. |
| **Dominant Non-Latin Scripts**| `नमस्ते`, `Москва`, `北京` | **REJECTED** | Record rejected (`NON_ENGLISH_SCRIPT`) | Text where non-Latin letters exceed 15% ratio or run > 30 chars is outside English-first scope. |
| **Excessive Symbol Density** | `+---+---+`, `/* code dumps */` | **REJECTED** | Record rejected (`HIGH_SYMBOL_RATIO`) | ASCII art, tables, and raw source code lacking English prose syntax. |
| **Excessive Repetition Loops** | `aaaaaaa...`, `the the the the...` | **REJECTED** | Record rejected (`REPEATED_CHARS` / `REPEATED_WORDS`) | Machine generator traps and crawler artifacts. |
| **Emojis & Pictographs** | `Hello 😊🎉` | **FILTERED / PRESERVED** | Preserved if isolated; rejected if high symbol ratio | Isolated emojis do not disqualify prose; high symbol density rejects noise. |
| **Unverified / Excluded Sources** | Any text from `UNKNOWN` or `EXCLUDED` source | **QUARANTINED / REJECTED** | Blocked at governance gate (`GOVERNANCE_BLOCKED`) | Strict legal and provenance protection. |

---

## 3. Disentangling Language Identity, Script Composition, Content Quality, and Unicode Representability

To prevent architectural drift and eliminate false equivalences, VEDA strictly formalizes four independent, orthogonal dimensions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE FOUR ORTHOGONAL EVALUATION AXES                             │
├─────────────────────────┬──────────────────────────────────────────────────────────────┤
│ 1. LANGUAGE IDENTITY    │ Is the linguistic text authentic English?                    │
│    (English vs Foreign) │ Evaluated via provenance ('language=en') and function word   │
│                         │ stopword density.                                            │
│                         │ Invariant: Latin Script ≠ English (rejects French/German).   │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 2. SCRIPT COMPOSITION   │ What is the ratio of Latin to Non-Latin characters?          │
│    (Dominant Script)    │ Evaluated via non_latin_ratio (threshold <= 0.15).           │
│                         │ Invariant: Non-Latin Script ≠ Non-English Document           │
│                         │ (admits English containing Greek symbols or foreign names).  │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 3. CONTENT QUALITY      │ Does the text exhibit grammatical prose syntax?              │
│    (Prose vs Noise)     │ Evaluated via alpha_ratio, symbol_ratio, repetition loops,   │
│                         │ and boilerplate signatures.                                  │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 4. UNICODE              │ Are codepoints valid, assigned, precomposed Unicode?         │
│    REPRESENTABILITY     │ Evaluated via NFC normalization and Cn/Cs/U+FFFD rejection.  │
│    (Corpus vs Tokenizer)│ Invariant: Corpus Representability ≠ Tokenizer Vocabulary.   │
└─────────────────────────┴──────────────────────────────────────────────────────────────┘
```

### Treatment of Legitimate English Prose Inclusions

English expository, scientific, encyclopedic, and philosophical prose routinely incorporates non-English fragments, technical symbols, and citations. VEDA governs these seven categories with explicit, reproducible rules:

#### 1. Foreign Names in Original Scripts
- **Examples**: *Socrates (Σωκράτης)*, *Leo Tolstoy (Лев Толстой)*, *Confucius (孔子)*, *Maimonides (משה בן מימון)*.
- **Classification**: **PRESERVED & ACCEPTED**.
- **Rule**: When embedded in predominantly Latin English prose, parenthetical or glossed names occupy $< 10\%$ of alphabetic characters and are standard English biographical practice.
- **Condition**: $\text{non\_latin\_ratio} \le 0.15$ and $\text{non\_latin\_count} \le 30$.

#### 2. Quoted Foreign Text & Maxims
- **Examples**: *The Delphic inscription "γνῶθι σεαυτόν" (know thyself)*; *Descartes' axiom "cogito, ergo sum"*; *the German concept of "Weltanschauung"*.
- **Classification**: **PRESERVED & ACCEPTED** (for brief quotations within English prose).
- **Rule**: Isolated quotations or maxims within an English explanatory sentence are authentic English usage. Pure foreign-language blocks (an entire paragraph of untranslated French, German, or Greek) are **REJECTED** under `NO_ENGLISH_STOPWORDS` or `NON_ENGLISH_SCRIPT`.

#### 3. Greek Scientific and Mathematical Symbols
- **Examples**: *wavelength $\lambda$*, *angular frequency $\omega$*, *significance level $\alpha = 0.05$*, *error margin $\Delta$*, *phase angle $\theta$*, *density matrix $\rho$*.
- **Classification**: **PRESERVED & ACCEPTED**.
- **Rule**: Standard English physics, mathematics, and statistics notation. These characters have Unicode category `Lu`/`Ll` (Greek alphabet), but in English scientific context their density is $< 5\%$ of letters. They must NOT cause document rejection.

#### 4. Mathematical Notation
- **Examples**: Prose with inline relations (*"for all $x \in S$, $f(x) \ge 0$"*).
- **Classification**: **PRESERVED & ACCEPTED** when embedded in syntactically complete English prose.
- **Rule**: Pure formula dumps lacking prose syntax (*"$\forall x \in S : f(x) \le \sum y_i \wedge \exists z : g(z) = 0$"*) have low alphabetic ratios and high symbol densities, and are **REJECTED** under `LOW_ALPHA_RATIO` ($< 0.65$) or `HIGH_SYMBOL_RATIO` ($> 0.20$).

#### 5. Academic Citations with Foreign Titles
- **Examples**: *See Aristotle, Metaphysics (Τὰ μετὰ τὰ φυσικά, 980a)*; *Kant, Critique of Pure Reason (Kritik der reinen Vernunft, B132)*.
- **Classification**: **PRESERVED & ACCEPTED**.
- **Rule**: Standard scholarly citation apparatus. Preserved in original scripts provided the surrounding discourse is English.

#### 6. Programming Source Code
- **Examples**: Raw code blocks (`if (x > y) { return arr[i] * matrix[j][k]; };`).
- **Classification**: **REJECTED** (`HIGH_SYMBOL_RATIO` or `LOW_ALPHA_RATIO`).
- **Rule**: Raw code fragments lack natural English syntax and contain excessive braces, operators, and semicolons ($> 20\%$ symbols). Conversely, English prose explaining algorithms (*"The quicksort algorithm partitions an array using a pivot element."*) is **ACCEPTED**.

#### 7. Multilingual Fragments & Loanwords
- **Examples**: *esprit de l'escalier*, *zeitgeist*, *ad hoc*, *de facto*, *in situ*.
- **Classification**: **PRESERVED & ACCEPTED**.
- **Rule**: Integrated English loanwords and idiomatic expressions are accepted. Pure Latin-script foreign languages (e.g. complete paragraphs in French, German, or Spanish) lack English function words (`the`, `of`, `and`, `to`, `is`, `in`, `that`, `for`, `with`) and are **REJECTED** under `NO_ENGLISH_STOPWORDS`.

---

## 4. Can a Valid Corpus Record Contain Characters Not in Tokenizer v0.1?

> [!IMPORTANT]
> **Definitive Architectural Answer: YES.**
> 
> A valid `CorpusRecord` represents natural English language discourse.
> 
> If a record contains authentic English words with diacritics (*café*, *naïve*, *résumé*) or legitimate scientific Greek letters (*$\lambda$*, *$\omega$*):
> 1. It **is accepted** by the corpus pipeline.
> 2. It **is stored** in `normalized_text` preserving all characters in NFC format.
> 3. If passed to the Phase 1 *CharacterTokenizer v0.1*, characters outside its 113-character registry will map to `<UNK>` (Token ID 1).
> 4. When Phase 2/4.2 introduces a subword tokenizer (BPE or Byte-fallback), those exact same corpus records will tokenize cleanly without `<UNK>` degradation.
> 
> Conflating the two would corrupt the training data by forcing synthetic degradation (stripping accents, dropping sentences) before the model architecture even begins.

---

## 5. Rejection Criteria Definition

A record is rejected **strictly** on the basis of:
1. **Empty / Whitespace-only content** (`EMPTY_TEXT`)
2. **Length bounds violations** (`TOO_SHORT_CHARS`, `TOO_SHORT_WORDS`, `TOO_LONG_CHARS`)
3. **Non-English script dominance** (`NON_ENGLISH_SCRIPT`: $\text{non\_latin\_ratio} > 0.15$ or $\text{non\_latin\_count} > 30$)
4. **Non-linguistic symbol / punctuation noise** (`HIGH_SYMBOL_RATIO`: symbol ratio $> 0.20$)
5. **Low alphabetic density** (`LOW_ALPHA_RATIO`: alpha ratio $< 0.65$)
6. **Repetition loops** (`REPEATED_CHARS` $> 4$, `REPEATED_WORDS` $> 3$)
7. **Boilerplate signatures** (`BOILERPLATE_CONTENT`)
8. **Absence of English function stopwords** (`NO_ENGLISH_STOPWORDS`: $< 1$ stopword for $\ge 8$ words, $< 2$ stopwords for $\ge 15$ words)
9. **Corrupted Unicode codepoints** (`HIGH_UNREGISTERED_RATIO`: U+FFFD, surrogate halves `Cs`, unassigned `Cn`)
10. **Data Governance block** (`GOVERNANCE_BLOCKED` for non-permitted sources)
11. **Duplicate collision** (`DUPLICATE`)

Rejection is **NEVER** based on:
- Uppercase vs lowercase capitalization.
- Presence of recognized Latin-accented letters (`é`, `è`, `ê`, `ï`, `ñ`, `ü`, `ç`, etc.).
- Presence of registered or standard typographical punctuation (`“`, `”`, `‘`, `’`, `–`, `—`, `…`).
- Presence of standard Greek mathematical/scientific letters in English prose.
- Presence of parenthetical foreign names or citations in English prose.
- Membership in any specific tokenizer's discrete vocabulary.
