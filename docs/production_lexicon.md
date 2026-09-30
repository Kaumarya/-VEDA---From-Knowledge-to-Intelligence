# VEDA Production Lexicon Specification (Phase 3)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Production Lexicon Infrastructure & Data Architecture Specification
========================================================================================
```

## 1. Scope & Architectural Role

The **VEDA Production Lexicon** is structured **lexical knowledge infrastructure**.

> [!IMPORTANT]
> **Architectural Boundary**: The Production Lexicon is NOT a training corpus.
> - **Lexicon**: Structured lexical knowledge (definitions, POS, pronunciations, inflections, etymology, relations) serving as a deterministic ground truth.
> - **Training Corpus**: Natural-language sentence/document sequences used for neural training (Phase 4).
> - **Tokenizer**: Discrete character/subword mapping infrastructure.
> - **Model**: Learned representations and neural weights.

The Lexicon acts as the definitive lexical dictionary against which characters, words, parts of speech, and downstream tokenizer vocabularies are referenced and validated.

---

## 2. Source Dataset & Provenance

- **Primary Source**: Wiktextract English dictionary dump (`raw-wiktextract-data.jsonl`, ~25.18 GB).
- **Source Integrity**: The raw dump remains completely immutable on disk. It is read strictly via streaming read-only streams.
- **Provenance Tracking**: Every entry carries metadata indicating:
  - Source identity (`Wiktionary (Wiktextract)`)
  - Schema version (`0.1.0`)
  - Extractor version (`0.1.0`)
  - Ingestion timestamp (ISO 8601 UTC)
  - Processing configuration (batch size, validation flags)

---

## 3. Inclusion & Orthography Policy (v0.1)

In strict adherence to the **VEDA v0.1 Orthography Policy**, vocabulary admitted to the Lexicon must satisfy:

1. **Language Scope**: English (`lang == 'English'` or `lang_code == 'en'`). All non-English records are filtered out.
2. **Plain ASCII Alphabet**: Words must consist solely of standard ASCII lowercase letters `[a-z]` (`[A-Z]` normalized via lowercase).
3. **Exclusions**:
   - **Multiword Expressions**: Space-containing entries (`apple pie`) are excluded from single-word lexical tables.
   - **Hyphenated Compounds**: Punctuation-containing entries (`apple-pie`) are excluded from v0.1.
   - **Apostrophe Contractions**: Contracted forms (`don't`) are excluded from single-word lexical tables.
   - **Numerics & Punctuation**: Digits and symbols (`123`, `hello!`) are rejected.
   - **Non-ASCII Characters**: Foreign diacritics and emojis (`café`, `hello😊`) are excluded.

*All rejected records are tallied by specific rejection reason (`whitespace`, `hyphenated`, `unsupported_characters`, etc.) and preserved in `ingestion_stats`.*

---

## 4. Extraction & Ingestion Pipeline

```
Raw JSONL Line
      ↓
JSON Deserialization (UTF-8 / Mojibake Repair)
      ↓
Language Filter (lang == 'English')
      ↓
Word Candidate Validation (v0.1 Orthography Policy)
      ↓
Wiktionary Record Parsing:
  - POS extraction
  - Senses & glosses
  - Grammatical tags & examples
  - IPA transcriptions (sounds)
  - Inflected forms
  - Synonyms & antonyms
  - Etymology text
      ↓
In-Memory Batch Aggregation (Dict[normalized, LexicalEntry], batch_size = 25,000)
      ↓
Controlled Batch Transaction (SQLite Commit)
  - Chunked query on existing keys
  - LexicalEntry.merge() for collisions
  - UPSERT words + child rows in word_pos and senses
      ↓
Database Integrity Verification (PRAGMA integrity_check)
      ↓
Atomic Rename to Final Database
```

---

## 5. Lexical Aggregation Semantics

When multiple records or POS entries exist for the same canonical normalized word:

1. **Multi-POS Preservation**: A word functioning as multiple parts of speech (e.g., `free` as adjective, verb, adverb, noun, numeral) preserves all grammatical categories in `parts_of_speech` and `definitions_by_pos`.
2. **Multi-Sense Distinguishability**: Distinct senses under the same POS are preserved with their respective glosses, tags, and usage examples.
3. **Gloss Deduplication**: Duplicate definitions across Wiktionary senses are deduplicated, while distinct contextual examples and tags are retained.
4. **Inflections & Forms**: Inflected forms (`freer`, `freest`, `frees`, `freeing`, `freed`) are merged into a unified set.
5. **Pronunciations & Relations**: IPA transcriptions, synonyms, and antonyms are aggregated without duplication.
6. **Idempotent Ingestion**: Re-running ingestion of the same raw dataset merges cleanly with zero duplicate records, POS rows, or senses.

---

## 6. Storage & Query Capabilities

Backed by `foundation/lexicon/storage.py` (`SqliteLexicon`):

1. **Exact Normalized Lookup**: $O(\log N)$ B-Tree query by canonical lowercase string (`db.lookup("apple")`).
2. **Case-Normalized Lookup**: Automatically canonicalizes surface casing (`Apple` $\to$ `apple`) ensuring case-insensitive lookups.
3. **Exact Surface Form Query**: Optional query matching exact capitalization (`db.lookup("Apple", exact_surface=True)`).
4. **Indexed POS Filtering**: Querying words by part-of-speech (`db.lookup("run", pos="verb")` or `db.filter_by_pos("verb")`).
5. **Word Integration**: Seamlessly reconstructs rich `Word` instances connected to the `CharacterRegistry` (`db.to_word("free")`).
6. **Integrity Assurance**: Self-validating via `db.integrity_check()`, verifying SQLite B-tree pages and foreign keys.

---

## 7. Known Limitations & Roadmap

- **Single-Word Scope**: v0.1 deliberately restricts lexical entries to single-token plain ASCII words. Phrasal verbs, idioms, and multiword compounds will be addressed in future lexical layers.
- **Accented Loanwords**: Loanwords retaining foreign diacritics (`café`, `naïve`) are excluded in v0.1 and will be incorporated when the Character Registry expands to Latin-1 Supplement.
- **Static Ground Truth**: The lexicon is an offline reference database, not a dynamic web crawler. Updates require rebuilding from updated Wiktextract releases.

---

## 8. Authoritative Character Registry Count Resolution

To resolve discrepancies across earlier draft reports between "113 registered characters" and "95 tokens":

| Category | Count | Codepoint Range / Symbols | Architectural Role |
|---|---|---|---|
| **Standard Printable ASCII** | 95 | U+0020 (space) to U+007E (`~`) | Complete basic English alphabetic, punctuation, and digit inventory. |
| **Typographic & Whitespace** | 18 | `\t`, `\n`, `\r`, NBSP, `‘’`, `“”`, `–`, `—`, `…`, `•`, `£€¥`, `©®`, `°±×÷` | Rich English punctuation, typographic quotation, and currency symbols. |
| **Total Registered Characters** | **113** | Registry schema `veda_characters_v0.1.json` | Explicit symbol universe known to the symbolic foundation. |
| **Special Control Tokens** | 4 | `<PAD>` (0), `<UNK>` (1), `<BOS>` (2), `<EOS>` (3) | Tokenizer sequence control abstractions. |
| **Total Tokenizer Vocabulary** | **117** | `CharacterTokenizer.vocab_size` ($113 + 4$) | Discrete integer token index space for neural computation. |

*Formal conclusion*: There are exactly **113 registered characters** and **4 special tokens**, yielding a tokenizer vocabulary of **117 tokens**. The label "95 tokens" in informal discussions was shorthand for the 95 printable ASCII codepoints.

---

## 9. Grammatical Category (POS) Distribution & Multi-Functionality

In natural English, lexical words frequently exhibit polysemy and syntactic multi-functionality (zero-derivation / conversion). A single lemma can function as a noun, verb, and adjective (e.g., *light*, *run*, *free*, *fly*).

In the VEDA Production Lexicon:
- **Total Unique Words**: 959,688
- **Total Relational POS Records (`word_pos`)**: 1,049,403
- **Mean Parts of Speech per Word**: $1.0935$

| Part of Speech | Unique Words | Percentage of Vocabulary |
|---|---|---|
| **Noun** | 694,769 | 72.40% |
| **Verb** | 162,118 | 16.89% |
| **Adjective** | 148,806 | 15.51% |
| **Adverb** | 22,257 | 2.32% |
| **Name / Proper Noun** | 9,927 | 1.03% |
| **Other / Minor Categories** | 11,526 | 1.20% |
| **Total Sum of Percentages** | **1,049,403** | **109.35%** |

> [!NOTE]
> Because POS categories are **not mutually exclusive**, the mathematical sum of POS percentages across words naturally exceeds $100\%$ ($109.35\%$). This reflects true linguistic multi-functionality rather than an accounting defect.

---

## 10. Ingestion Statistics & Conservation Formula

The raw Wiktextract dump was audited and ingested with streaming verification. The mathematical relationship between candidate counts, collisions, and unique vocabulary is governed by an exact conservation formula:

$$\text{Valid Candidates} = \text{Unique Words Aggregated} + \text{In-Batch Collisions} + \text{Cross-Batch Collisions}$$

Substituting empirical values:
$$1,080,184 = 959,688 + 94,040 + 26,456$$
$$1,080,184 = 959,688 + 120,496 = 1,080,184 \quad \checkmark$$

### Exact Ingestion Accounting:
- **Total Raw Lines Read**: 9,997,014 lines (~25.18 GB).
- **English Records Extracted**: 1,475,349 records (14.76%).
- **Non-English Records Skipped**: 8,521,665 records (85.24%).
- **Valid Candidates**: 1,080,184 records (73.22% of English records).
- **Invalid Candidates Skipped**: 395,165 records (26.78% of English records):
  - Whitespace / Multiword: 289,311 records (73.21% of rejections)
  - Punctuation / Hyphenated: 97,419 records (24.65% of rejections)
  - Digits / Alphanumeric: 7,511 records (1.90% of rejections)
  - Non-ASCII Characters: 924 records (0.23% of rejections)
- **Unique Vocabulary Written to Database**: Exactly **959,688 words**.
- **Duplicate Record Collisions Merged**: Exactly **120,496 collisions** (94,040 in-batch + 26,456 cross-batch).
- **Malformed JSON Lines**: Exactly **0** (0.00%).

---

## 11. Production Dataset Fingerprint & Cryptographic Integrity

To guarantee that the production database remains immutable and bit-for-bit verifiable across environments and future builds, a logical fingerprint was computed across all 959,688 records:

- **Database Path**: `data/lexicon/veda_lexicon_v0.1.sqlite`
- **Database File Size**: 2,240,503,808 bytes (2,136.71 MB)
- **Total Unique Words**: 959,688
- **Total Relational POS Records**: 1,049,403
- **Total Senses Records**: 1,322,676
- **Total Gloss Definitions**: 1,324,578
- **Total Inflected Forms**: 632,884
- **Total IPA Pronunciations**: 168,055
- **Logical Data SHA-256 (Word + Primary POS)**:
  `ce7f5994f6146d235c02d54e60cf9cf373d57d4f34c5c6e8152f978f47e1a8a6`
- **Full Logical SHA-256 (Canonical JSON Hash)**:
  `e69d2756ce4e966390936c4dedfe320c8e148cd5433d4a2267ab86378bd89b2e`

