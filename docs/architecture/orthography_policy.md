# VEDA v0.1 Orthography & Word Policy

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Specification: Orthographic Policy, Character Representability & Deduplication
========================================================================================
```

## 1. Separation of Concerns: Language $\neq$ Orthography $\neq$ Representability

A major blind spot in language modeling is conflating language, alphabet encoding, and character registry support into a single opaque boolean. 

VEDA establishes a strict conceptual separation across three orthogonal dimensions:

```
[ A. Language Classification ]  ──►  Is this record linguistically English? (lang="en")
[ B. Orthographic Validation   ]  ──►  Does this string meet v0.1 plain candidate constraints?
[ C. Character Support         ]  ──►  Are all characters present in CharacterRegistry?
```

### Why English $\neq$ ASCII
English orthography includes recognized loanwords and typographical borrowings featuring diacritics (e.g. *café*, *naïve*, *cliché*, *façade*, *résumé*).
- An entry with `lang="en"` and `word="café"` is an authentic **English dictionary word**.
- However, `'é'` (U+00E9) is not in the v0.1 113-character registry.
- Equating `English = ASCII` would falsely declare *café* to be a non-English word.
- Conversely, accepting any arbitrary Unicode character into the character foundation without registry indexing would break deterministic character ID conversions.

---

## 2. VEDA v0.1 Orthography Matrix

The table below defines the formal VEDA v0.1 handling across all orthographic categories:

| Input Category | Example | Language Scope | v0.1 Plain Candidate? | Registry Support? | Orthographic Category | Rejection Reason |
|---|---|---|---|---|---|---|
| **ASCII Alphabetic** | `apple`, `computer`, `VEDA` | English | **YES** | **YES** (100%) | `plain_ascii` | `VALID` |
| **Single Letter** | `A`, `I`, `x` | English | **YES** | **YES** (100%) | `plain_ascii` | `VALID` |
| **Latin Accented** | `café`, `naïve`, `résumé` | English | **NO** (Deferred to v0.2) | **NO** (Unregistered diacritics) | `latin_accented` | `CONTAINS_NON_ENGLISH_CHARS` |
| **Hyphenated Compounds** | `state-of-the-art`, `apple-pie` | English | **NO** (Deferred to tokenizer segmentation) | **YES** (`-` is in registry) | `hyphenated` | `CONTAINS_PUNCTUATION` |
| **Apostrophe Contractions** | `don't`, `it's`, `o'clock` | English | **NO** (Deferred to tokenizer segmentation) | **YES** (`'` is in registry) | `apostrophe_contraction` | `CONTAINS_PUNCTUATION` |
| **Numeric Strings** | `123`, `42` | Language-neutral | **NO** (Not an alphabetic word) | **YES** (Digits `0..9` in registry) | `numeric` | `CONTAINS_DIGITS` |
| **Alphanumeric Words** | `word2`, `mp3` | English / Technical | **NO** (Not a plain word) | **YES** | `contains_digits` | `CONTAINS_DIGITS` |
| **Punctuation Affixes** | `hello!`, `what?`, `cat.` | English + Punctuation | **NO** (Contains sentence punctuation) | **YES** | `contains_punctuation` | `CONTAINS_PUNCTUATION` |
| **Multiword Expressions** | `apple pie`, `prime minister` | English (Lexical phrase) | **NO** (Contains whitespace delimiters) | **YES** | `whitespace` | `CONTAINS_WHITESPACE` |
| **Non-Latin Scripts** | `नमस्ते`, `москва`, `北京` | Non-English | **NO** (Outside English scope) | **NO** | `non_latin_script` | `CONTAINS_NON_ENGLISH_CHARS` |
| **Emojis & Symbols** | `hello😊`, `☃`, `🤖` | Out-of-vocabulary | **NO** | **NO** | `symbol_or_emoji` | `CONTAINS_NON_ENGLISH_CHARS` |

---

## 3. Empirical Wiktextract Audit Findings

To substantiate the v0.1 orthography policy with empirical evidence rather than assumptions, a 20,013-line sample from `raw-wiktextract-data.jsonl` was audited:

- **Total English Records Processed**: 4,571 records.
- **Pure ASCII Words**: 4,564 records (**99.85%** of all English headwords).
- **Latin-Accented Words**: 7 records (**0.15%** of English headwords).
  - Encoded characters encountered:
    - `'é'` U+00E9 (LATIN SMALL LETTER E WITH ACUTE)
    - `'è'` U+00E8 (LATIN SMALL LETTER E WITH GRAVE)
    - `'ã'` U+00E3 (LATIN SMALL LETTER A WITH TILDE)
    - `'í'` U+00ED (LATIN SMALL LETTER I WITH ACUTE)
    - `'ï'` U+00EF (LATIN SMALL LETTER I WITH DIAERESIS)
    - `'ü'` U+00FC (LATIN SMALL LETTER U WITH DIAERESIS)
    - `'ç'` U+00E7 (LATIN SMALL LETTER C WITH CEDILLA)
- **Non-Latin Script Words in English Records**: Exactly **0** (0.00%).
- **Multiword Expressions**: 287 records (**6.28%**).
- **Hyphenated / Punctuation Words**: 59 records (**1.29%**).

### Architectural Conclusion
Restricting v0.1 plain English word candidates to pure ASCII alphabetic words captures **99.85%** of all English dictionary headwords while preserving mathematical determinism and avoiding complex Unicode decomposition ambiguities. Accented loanwords are recognized as distinct `latin_accented` forms and flagged for registry expansion in v0.2.

---

## 4. Lexicon Deduplication Policy

The Lexicon ingestion pipeline must never conflate different linguistic categories under crude lowercased string matching.

### Category Taxonomy

| Relationship | Definition | Handling in VEDA | Example |
|---|---|---|---|
| **Identical Records** | Exact duplicates across source files. | Deduplicated during line/JSON ingestion. | Repeated JSON lines in dump. |
| **Duplicate Records** | Same word, same POS, and overlapping senses. | Senses merged; glosses deduplicated without duplication. | Repeated headword exports from different Wiktionary revisions. |
| **Case Variants** | Same word differing only by capitalization. | Normalized to canonical lowercase key; `word.original` preserved on the first entry. | `Apple` vs `apple` $\to$ normalized to `apple`. |
| **Lexical Variants** | Alternative spelling variations. | Maintained as distinct lexical headwords or cross-referenced in `forms`. | `encyclopaedia` vs `encyclopedia`. |
| **Inflected Forms** | Grammatical inflections (plurals, tenses). | Preserved in the `forms` field of the base lemma entry. | `dictionaries` listed in `forms` of `dictionary`. |
| **Different Senses** | Distinct meanings belonging to the same part of speech. | Preserved as separate `LexicalSense` objects within `entry.senses`. | `dictionary` as a book vs `dictionary` as a programming associative array. |
| **Different Parts of Speech** | A single word functioning across multiple grammatical categories. | Consolidated into a single `LexicalEntry` with distinct entries in `definitions_by_pos` and `parts_of_speech`. | `free` (adjective, adverb, verb, noun, numeral). |
| **Homographs** | Words sharing identical spelling but differing in etymology and origin. | Aggregated into `senses` while preserving distinct `etymology` fields where available. | `lead` (metal) vs `lead` (to guide). |

> **Critical Rule**: Deduplication must **never** discard distinct parts of speech or senses. When merging records for `free`, the resulting `LexicalEntry` retains all 5 grammatical roles and all individual glosses.
