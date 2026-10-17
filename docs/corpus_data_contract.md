# VEDA Corpus Data Contract & Provenance Specification

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Corpus Data Contract, Hierarchy & Provenance
Document ID: VEDA-CONTRACT-CORPUS-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. Architectural Hierarchy: Conceptual Layers

The VEDA training corpus is organized into **six discrete conceptual layers**:

```
┌────────────────────────────────────────────────────────┐
│ 1. CORPUS                                              │ The complete, versioned training collection
└───────────────────────────┬────────────────────────────┘
                            │ contains 1..N
┌───────────────────────────▼────────────────────────────┐
│ 2. SOURCE                                              │ Identifiable external origin (e.g. Gutenberg)
└───────────────────────────┬────────────────────────────┘
                            │ produces 1..N
┌───────────────────────────▼────────────────────────────┐
│ 3. DOCUMENT                                            │ Coherent authorial unit (article, book, essay)
└───────────────────────────┬────────────────────────────┘
                            │ partitioned into 1..N
┌───────────────────────────▼────────────────────────────┐
│ 4. TEXT SEGMENT                                        │ Coherent structural block (section, paragraph)
└───────────────────────────┬────────────────────────────┘
                            │ parsed into 1..N
┌───────────────────────────▼────────────────────────────┐
│ 5. SENTENCE                                            │ Single grammatical clause / sentence
└───────────────────────────┬────────────────────────────┘
                            │ assembled into
┌───────────────────────────▼────────────────────────────┐
│ 6. CORPUS RECORD                                       │ Canonical atomic training record
└────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Physical vs. Conceptual Decoupling**:
> These six conceptual layers must **not** be collapsed into a single monolithic database table.
> - **Source** metadata is stored in an authoritative catalog / manifest.
> - **Document** boundaries are preserved for deduplication and data leakage prevention.
> - **Segments and Sentences** are intermediate structures computed during ingestion and segmentation.
> - **Corpus Record** is the finalized, normalized, validated, and split-assigned artifact ready for training consumption.

---

## 2. Formal Schema Definitions

### Layer 1: Corpus (`Corpus`)
Represents the entire curated dataset collection at a specific release version.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `corpus_id` | `str` | `^[a-z0-9_-]+$` | No | Non-empty ASCII string | Unique identifier for the corpus collection |
| `corpus_version` | `str` | SemVer `MAJOR.MINOR.PATCH` | No | Valid semantic version string | Release version of the corpus |
| `description` | `str` | Any text | No | Max length 1,000 chars | High-level summary of corpus purpose |
| `created_at` | `str` | ISO-8601 UTC timestamp | No | Valid UTC timestamp string | Creation timestamp |
| `schema_version` | `str` | SemVer `MAJOR.MINOR.PATCH` | No | Matches schema contract version | Version of this data contract |

---

### Layer 2: Source Contract (`CorpusSource`)
Every corpus source must be explicitly cataloged and verified for training governance before ingestion.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `source_id` | `str` | `^[a-z0-9_.-]+$` | No | Non-empty unique identifier | Primary key identifying the data source |
| `name` | `str` | Printable text | No | Length 1..200 chars | Human-readable name of the source |
| `version` | `str` | Any version tag | No | Non-empty string | Source release version or date tag |
| `url_or_path` | `str` | Valid URI or relative path | No | Non-empty path/URI | Authoritative acquisition location |
| `acquisition_date` | `str` | ISO-8601 Date (`YYYY-MM-DD`) | No | Valid date format | Date the source was downloaded |
| `source_hash` | `str` | `^[a-f0-9]{64}$` | No | Valid 64-char SHA-256 hex string | Cryptographic hash of original raw archive |
| `license` | `str` | SPDX identifier or name | No | Non-empty string (e.g. `CC-BY-4.0`, `Public Domain`) | Authoritative license terms |
| `licensing_status` | `str` | `VERIFIED PERMITTED`, `REQUIRES REVIEW`, `UNKNOWN`, `EXCLUDED` | No | Must be one of the four enum values | Governance gate status |
| `attribution` | `str` | Printable text | Yes | Free text if required by license | Required attribution text |
| `language` | `str` | ISO 639-1 code (`en`, `mul`) | No | Default `en` | Primary language of source |
| `source_type` | `str` | `book`, `encyclopedia`, `essay`, `educational`, `news`, `synthetic` | No | Controlled category string | Structural genre/origin of source |
| `description` | `str` | Printable text | Yes | Optional descriptive text | Contextual notes on source curation |

> [!CAUTION]
> **Licensing & Governance Gate**:
> Public accessibility does **not** grant automatic training rights. If `licensing_status` is `UNKNOWN` or `EXCLUDED`, the pipeline must block the source from entering training splits.

---

### Layer 3: Document (`CorpusDocument`)
Represents an individual authorial work, chapter, or article within a source.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `document_id` | `str` | `^[a-z0-9_.-]+$` | No | Globally unique across corpus | Deterministic identifier (`{source_id}:{doc_hash[:16]}`) |
| `source_id` | `str` | Matches existing `source_id` | No | Must exist in Source catalog | Foreign reference to originating source |
| `title` | `str` | Printable text | Yes | Optional title string | Title of book, article, or section |
| `author` | `str` | Printable text | Yes | Optional author name | Originating author or organization |
| `raw_text` | `str` | Valid UTF-8 string | No | Non-empty string | Unmodified raw text as ingested |
| `raw_char_count` | `int` | $\ge 1$ | No | Must equal `len(raw_text)` | Length of raw text in Unicode characters |
| `document_hash` | `str` | `^[a-f0-9]{64}$` | No | SHA-256 of `raw_text.encode('utf-8')` | Cryptographic fingerprint of raw document |
| `metadata` | `dict` | Key-value pairs | Yes | Valid JSON-serializable dict | Source-specific metadata (publication year, genre, etc.) |

---

### Layer 4: Text Segment (`TextSegment`)
Represents a structural block (paragraph, section) extracted from a Document.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `segment_id` | `str` | `^[a-z0-9_.-]+$` | No | Unique (`{document_id}:s{index}`) | Identifier of the structural segment |
| `document_id` | `str` | Matches `document_id` | No | Valid document reference | Reference to parent document |
| `segment_index` | `int` | $\ge 0$ | No | Zero-indexed sequential order | Position of segment in document |
| `raw_text` | `str` | Valid UTF-8 string | No | Non-empty string | Original segment text |
| `start_char_offset` | `int` | $\ge 0$ | No | Start position in parent `raw_text` | Exact character offset in document |
| `end_char_offset` | `int` | $> \text{start\_char\_offset}$ | No | End position in parent `raw_text` | Exact end character offset in document |
| `segment_type` | `str` | `paragraph`, `heading`, `list_item`, `quote`, `table_row` | No | Default `paragraph` | Structural semantic category |

---

### Layer 5: Sentence (`Sentence`)
Represents a single grammatical sentence unit.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `sentence_id` | `str` | `^[a-z0-9_.-]+$` | No | Unique (`{segment_id}:sent{index}`) | Identifier of sentence |
| `segment_id` | `str` | Matches `segment_id` | No | Valid segment reference | Reference to parent segment |
| `sentence_index` | `int` | $\ge 0$ | No | Zero-indexed sequential order | Position in parent segment |
| `raw_text` | `str` | Valid UTF-8 string | No | Non-empty | Original sentence text |
| `start_char_offset` | `int` | $\ge 0$ | No | Relative offset in segment | Offset in parent segment |
| `end_char_offset` | `int` | $> \text{start\_char\_offset}$ | No | Relative end in segment | End offset in parent segment |

---

### Layer 6: Corpus Record (`CorpusRecord`)
The **canonical training record** consumed by the tokenizer and neural modeling pipeline.

| Field Name | Type | Allowed Values | Nullable | Validation Rules | Description |
|---|---|---|---|---|---|
| `record_id` | `str` | `^[a-f0-9]{32}$` or `^[a-z0-9_.-]+$` | No | Deterministic unique ID | Unique identifier for the training record |
| `document_id` | `str` | Matches `document_id` | No | Must exist in parent Document | Originating parent document identifier |
| `source_id` | `str` | Matches `source_id` | No | Must exist in Source catalog | Originating source catalog identifier |
| `segment_index` | `int` | $\ge 0$ | No | Sequential position | Position index within document |
| `language` | `str` | ISO 639-1 (`en`) | No | Must be `en` in v0.1 | Primary language classification |
| `raw_text` | `str` | Valid UTF-8 string | No | Non-empty string | The original unnormalized text |
| `normalized_text` | `str` | Valid UTF-8 string | No | Non-empty; passes normalization rules | The normalized text ready for tokenization |
| `raw_char_count` | `int` | $\ge 1$ | No | Must equal `len(raw_text)` | Length of raw text |
| `normalized_char_count` | `int` | $\ge 1$ | No | Must equal `len(normalized_text)` | Length of normalized text |
| `approx_word_count` | `int` | $\ge 1$ | No | Word count after whitespace split | Approximate word count |
| `quality_score` | `float` | $0.0 \le s \le 1.0$ | No | Score produced by quality filter suite | Composite quality assessment score |
| `is_duplicate` | `bool` | `True`, `False` | No | Set by deduplication engine | Flag indicating duplicate status |
| `duplicate_of_id` | `str` | Record ID or `None` | Yes | Non-null only if `is_duplicate` is `True` | Pointer to original canonical record |
| `split` | `str` | `train`, `validation`, `test` | No | Must be one of the three splits | Dataset split assignment |
| `corpus_version` | `str` | SemVer `MAJOR.MINOR.PATCH` | No | Matches release version | Release version of corpus |
| `provenance` | `dict` | RecordProvenance dict | No | Valid provenance schema | End-to-end lineage tracing metadata |

---

## 3. Provenance Chain & Traceability

Every `CorpusRecord` maintains strict end-to-end lineage tracing back to its raw physical source:

```
[SOURCE ARCHIVE]
       │  source_hash (SHA-256), acquisition_date, license
       ▼
[DOCUMENT]
       │  document_id, document_hash, raw_char_count
       ▼
[TEXT SEGMENT]
       │  segment_id, segment_index, [start_offset:end_offset]
       ▼
[CORPUS RECORD]
       │  record_id, raw_text, normalized_text, split
       ▼
[PROCESSED TOKEN SEQUENCE] (Phase 6 Pretraining)
```

### Provenance Metadata Structure (`RecordProvenance`)
```json
{
  "source_id": "gutenberg_essays",
  "document_id": "gutenberg_essays:d7a810f2",
  "segment_index": 4,
  "start_char_offset": 1280,
  "end_char_offset": 1742,
  "normalizer_version": "0.1.0",
  "filter_version": "0.1.0",
  "pipeline_run_id": "run-20261002-01",
  "created_at": "2026-10-02T15:30:00Z"
}
```

---

## 4. Rejection Tracking Ledger (`RejectionRecord`)

When text fails quality, language, or length filtering, **provenance is NOT destroyed**. The system appends a structured rejection record to a rejection ledger:

| Field Name | Type | Allowed Values | Nullable | Description |
|---|---|---|---|---|
| `record_id` | `str` | Deterministic ID | No | Identifier of the rejected record |
| `document_id` | `str` | Parent document ID | No | Parent document identifier |
| `source_id` | `str` | Originating source ID | No | Originating source |
| `rejection_reason` | `str` | Controlled enum code | No | E.g. `TOO_SHORT`, `HIGH_SYMBOL_DENSITY`, `NON_ENGLISH` |
| `rejection_stage` | `str` | `normalization`, `filtering`, `deduplication` | No | Stage where text was rejected |
| `metric_name` | `str` | Name of failed metric | Yes | E.g. `char_length`, `alpha_ratio` |
| `metric_value` | `float` | Observed value | Yes | Empirical value triggering threshold |
| `threshold_value` | `float` | Configured cutoff | Yes | Defined cutoff boundary |
| `raw_text_sample` | `str` | Truncated snippet (max 100 chars) | No | Sample of rejected text for auditing |

---

## 5. Unresolved Decisions in Data Contract

1. `[UNRESOLVED — REQUIRES DECISION]` **Sub-document Hierarchical Depth**:
   - Whether section hierarchies (Chapter $\to$ Section $\to$ Subsection $\to$ Paragraph) require dedicated relational models or if flat Document $\to$ Segment decomposition is sufficient for v0.1.
   - *Status*: Flat Document $\to$ Segment adopted for v0.1; nested hierarchy deferred to future structured document milestones.

2. `[UNRESOLVED — REQUIRES DECISION]` **Sentence-Level vs. Paragraph-Level Canonical Training Units**:
   - Whether training examples in pretraining will pack multiple paragraphs across document boundaries or train strictly on isolated paragraphs.
   - *Status*: Paragraph/segment adopted as canonical `CorpusRecord` unit for curation; sequence packing deferred to DataLoader implementation in Phase 5.
