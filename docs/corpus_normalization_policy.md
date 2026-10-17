# VEDA Corpus Text Normalization Policy (Phase 4)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Text Normalization Policy & Transform Taxonomy
Document ID: VEDA-POLICY-NORM-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Executive Summary & Foundational Rules

Text normalization prepares raw source documents for segmentation, tokenization, and language modeling.

> [!CRITICAL]
> **Rule 1: Preserve Both Raw and Normalized Text.**
> Raw text (`raw_text`) must **never** be overwritten or discarded. Every `CorpusRecord` maintains both `raw_text` (unmodified origin) and `normalized_text` (reproducibly transformed target). This ensures total auditability and allows reprocessing under future policy revisions.

> [!CRITICAL]
> **Rule 2: Do Not Lowercase the Training Corpus.**
> The Lexicon normalized headwords to lowercase for canonical dictionary indexing. **The Training Corpus must preserve authentic capitalization.** Capitalization conveys vital linguistic information: sentence boundaries, proper nouns, acronyms, titles, and semantic distinctions (e.g. *Apple* the corporation vs. *apple* the fruit; *May* the month vs. *may* the modal verb).

> [!CRITICAL]
> **Rule 3: Unicode Standardization and Tokenizer Decoupling.**
> Normalization maps unstandardized variants to their canonical counterparts (e.g. NFC composition, standardized dashes, entities), removing corrupt noise while preserving maximal semantic signal. In accordance with `docs/corpus_unicode_policy.md`, corpus normalization preserves authentic typography and valid Latin loanwords (*café*, *naïve*, *résumé*), strictly decoupling corpus representability from the Phase 1 reference character tokenizer's 113-character vocabulary.

---

## 2. Normalization Transformation Taxonomy

Every transformation in VEDA is classified across two axes:
- **Information Preservation**: `Lossless` (no linguistic data lost) vs. `Lossy` (some variance discarded).
- **Invertibility**: `Reversible` (original string can be algorithmically reconstructed) vs. `Irreversible` (one-way canonicalization).

| Dimension / Feature | Raw Input Pattern | Canonical Transformed Target | Type | Invertibility | Rationale |
|---|---|---|---|---|---|
| **Unicode Normalization** | Any Unicode encoding | Unicode `NFC` (Canonical Composition) | Lossless | Reversible (via NFD) | Unifies precomposed characters with combining sequences into deterministic byte sequences. |
| **Line Endings** | `\r\n` (CRLF) or `\r` (CR) | `\n` (LF) | Lossless | Reversible (with OS tag) | Standardizes cross-platform line breaks to UNIX format. |
| **Horizontal Whitespace** | `\t`, non-breaking space (U+00A0), multiple spaces `   ` | Single space `' '` | Lossy | Irreversible | Eliminates layout formatting artifacts and redundant spaces. |
| **Vertical Whitespace** | 3 or more consecutive newlines (`\n\n\n+`) | Exactly two newlines (`\n\n`) | Lossy | Irreversible | Preserves paragraph breaks while eliminating blank page gaps. |
| **Record Boundaries** | Leading/trailing whitespace | Stripped (`text.strip()`) | Lossy | Irreversible | Eliminates margin padding around records. |
| **Control Characters** | ASCII `0x00..0x08`, `0x0B..0x0C`, `0x0E..0x1F`, `0x7F` | Removed (`""`) | Lossy | Irreversible | Control codes and null bytes are non-linguistic terminal/transmission artifacts. |
| **HTML / XML Tags** | `<b>text</b>`, `<p>para</p>` | Plain text content (`text`, `para`) | Lossy | Irreversible | Extracts human-readable prose from web/e-book markup. |
| **HTML Named Entities** | `&amp;`, `&quot;`, `&lt;`, `&gt;`, `&apos;` | `&`, `"`, `<`, `>`, `'` | Lossless | Reversible | Restores genuine typographical characters from entity encoding. |
| **HTML Numeric Entities** | `&#160;`, `&#8212;` | ` `, `—` | Lossless | Reversible | Restores genuine Unicode symbols from decimal/hex escapes. |
| **Typographical Quotes** | `“` (U+201C), `”` (U+201D) | Preserved (`“`, `”`) | Lossless | Reversible | Registered in VEDA Character Registry; teaches correct quote directionality. |
| **Typographical Apostrophe** | `’` (U+2019), `‘` (U+2018) | Preserved (`’`, `‘`) | Lossless | Reversible | Registered in VEDA Character Registry; preserves English typography. |
| **Dashes** | Hyphen `-`, En-dash `–`, Em-dash `—` | Preserved (`-`, `–`, `—`) | Lossless | Reversible | All three are registered in VEDA Character Registry with distinct syntactic roles. |
| **Ellipses** | `...` (three dots) | Standardized to `…` (U+2026) | Lossy | Irreversible | Standardizes running dots to canonical registered ellipsis character. |
| **Casing** | `The Apple company...` | Unchanged (`The Apple company...`) | Lossless | Reversible | Preserves syntactic, morphological, and named-entity signals. |
| **Digits & Numbers** | `1984`, `3.14159` | Unchanged (`1984`, `3.14159`) | Lossless | Reversible | Standard Arabic digits `0..9` are registered; numerals must be learned. |
| **URLs & Links** | `https://example.com/page?id=1` | Preserved or placeholder `[URL]` | Lossy | Irreversible | Web URLs in prose may be normalized to avoid tokenization bloat. |
| **Email Addresses** | `user@example.com` | Preserved or placeholder `[EMAIL]` | Lossy | Irreversible | PII prevention & standardization. |
| **Emojis & Foreign Scripts** | `Hello 😊`, `नमस्ते` | Filtered / Stripped | Lossy | Irreversible | Unregistered in v0.1 Character Registry. Records with high density are rejected. |

---

## 3. Step-by-Step Normalization Pipeline

The normalizer executes transformations in a strictly deterministic sequence:

```
Raw String Input
       ↓
1. HTML Entity Decoding (e.g. &amp; → &, &ldquo; → “)
       ↓
2. HTML / XML Tag Stripping (removes markup tags while preserving textual body)
       ↓
3. Unicode Canonical Normalization (unicodedata.normalize('NFC', text))
       ↓
4. Line Ending Standardization (\r\n and \r → \n)
       ↓
5. Control Character & Null Byte Removal (removes 0x00..0x1F except \t, \n)
       ↓
6. Typographical Standardization (standardizes spacing around dashes, converts ... to …)
       ↓
7. Horizontal Whitespace Consolidation (converts \t and NBSP to space, collapses multiple spaces)
       ↓
8. Vertical Whitespace Consolidation (collapses 3+ newlines to exactly 2)
       ↓
9. Boundary Trimming (strips leading/trailing whitespace)
       ↓
Normalized String Output
```

---

## 4. Preservation Invariant & Contract

For any record processed by the normalizer:

$$\text{record.raw\_text} \equiv \text{Original Text as extracted from source}$$
$$\text{record.normalized\_text} \equiv \text{Normalizer}(\text{record.raw\_text})$$

The system guarantees:
1. `record.raw_text` is immutable.
2. `record.normalized_text` is deterministic: running the normalizer $N$ times produces bitwise identical strings.
3. Both fields are serialized side-by-side in storage.

---

## 5. Unresolved Policy Decisions

1. `[UNRESOLVED — REQUIRES DECISION]` **URL and Email Masking Policy**:
   - Option A: Retain URLs and emails verbatim in running prose.
   - Option B: Replace URLs with special token `<URL>` and emails with `<EMAIL>`.
   - Option C: Reject records containing URLs as commercial/web noise.
   - *Status*: Verbatim retention with whitespace normalization adopted for v0.1; special placeholder tokens deferred to tokenizer expansion.

2. `[UNRESOLVED — REQUIRES DECISION]` **Ellipsis Representation**:
   - Whether to standardize all three-dot sequences `...` to Unicode `…` (U+2026), or allow both `...` and `…`.
   - *Status*: Standardizing `...` to `…` adopted for canonical representation because `…` is registered in Character Registry.
