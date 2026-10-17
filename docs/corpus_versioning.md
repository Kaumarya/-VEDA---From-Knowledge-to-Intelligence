# VEDA Corpus Versioning, Manifest & Governance Specification

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Versioning, Machine Manifest & Data Governance
Document ID: VEDA-SPEC-MANIFEST-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4 ARCHITECTURE
========================================================================================
```

---

## 1. The Reproducibility Equation

A corpus must never be identified merely by a file name or timestamp. In VEDA, a corpus version represents a deterministic, reproducible mathematical artifact governed by the **Corpus Identity Equation**:

$$\text{Corpus Version} = f\left(\sum \text{Source Hashes}, \text{Schema Version}, \text{Policy Versions}, \text{Config Parameters}, \text{Seed}\right)$$

```
┌──────────────────────────────────────────────┐
│ Verified Source Archives & Cryptographic Hashes │
├──────────────────────────────────────────────┤
│ + Schema Version (Data Contract)             │
│ + Normalization Policy Version               │
│ + Quality Filtering Policy Version           │
│ + Deduplication Engine Version               │
│ + Splitting Seed & Ratio Configuration       │
│ + Pipeline Code Git Commit Hash              │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
         DETERMINISTIC DERIVED CORPUS
                       │
                       ▼
         LOGICAL DATASET FINGERPRINT
```

If any component on the left-hand side changes, the resulting corpus is a **different version**.

---

## 2. Multi-Dimensional Versioning Matrix

| Dimension | Field Name | Example Value | Description |
|---|---|---|---|
| **Corpus Version** | `corpus_version` | `"0.1.0"` | Semantic release version of the assembled training dataset |
| **Schema Version** | `schema_version` | `"0.1.0"` | Data contract version defining field definitions |
| **Source Catalog Version** | `sources_version` | `"0.1.0"` | Version of cataloged source archives and licenses |
| **Normalization Version** | `normalization_version`| `"0.1.0"` | Version of the text normalizer transform rules |
| **Filtering Version** | `filtering_version` | `"0.1.0"` | Version of quality filter thresholds |
| **Deduplication Version** | `deduplication_version`| `"0.1.0"` | Version of duplicate detection engine |
| **Split Version** | `split_version` | `"0.1.0"` | Version of the partition hash & seed algorithm |

---

## 3. The Corpus Manifest (`manifest.json`)

The corpus manifest is an authoritative, machine-readable JSON document sealed alongside every corpus release.

### Manifest Schema & Structure
```json
{
  "corpus_name": "veda_corpus_v0.1",
  "corpus_version": "0.1.0",
  "schema_version": "0.1.0",
  "created_at": "2026-10-02T16:00:00Z",
  "pipeline_version": "0.1.0",
  "split_seed": "VEDA_CORPUS_SEED_v0.1",
  "policies": {
    "normalization_version": "0.1.0",
    "filtering_version": "0.1.0",
    "deduplication_version": "0.1.0",
    "split_version": "0.1.0"
  },
  "sources": [
    {
      "source_id": "gutenberg_essays",
      "version": "2026-09",
      "license": "Public Domain",
      "licensing_status": "VERIFIED PERMITTED",
      "source_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "document_count": 12
    }
  ],
  "statistics": {
    "total_documents": 12,
    "total_records_processed": 1500,
    "retained_records": 1240,
    "rejected_records": 210,
    "duplicate_records": 50,
    "rejection_breakdown": {
      "EMPTY_TEXT": 10,
      "TOO_SHORT_CHARS": 85,
      "LOW_ALPHA_RATIO": 65,
      "HIGH_SYMBOL_RATIO": 30,
      "NON_ENGLISH_SCRIPT": 20
    },
    "duplicate_breakdown": {
      "exact_duplicates": 20,
      "normalized_duplicates": 30
    },
    "split_counts": {
      "train": 1116,
      "validation": 62,
      "test": 62
    },
    "character_counts": {
      "total_raw_characters": 894000,
      "total_normalized_characters": 881200,
      "train_characters": 793080,
      "validation_characters": 44060,
      "test_characters": 44060
    },
    "approx_word_counts": {
      "total_words": 152000,
      "train_words": 136800,
      "validation_words": 7600,
      "test_words": 7600
    }
  },
  "artifacts": {
    "train_file": "train.jsonl",
    "train_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    "validation_file": "validation.jsonl",
    "validation_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
    "test_file": "test.jsonl",
    "test_sha256": "c01826d9cf86071ef28f731295b9a89df8549e39401765c929a00732dc51bc04",
    "logical_fingerprint": "a9f3b8908f4c281f6d33b49912c9bf10e408573ef82bd1897c8cfd9894732152"
  }
}
```

---

## 4. The Logical Dataset Fingerprint

In addition to physical file hashes (which can vary if newline conventions or JSON key order differ across OS platforms), VEDA computes a **Canonical Logical Fingerprint**:

$$\text{Logical Fingerprint} = \text{SHA256}\left(\bigoplus_{i=1}^N \text{SHA256}\left(\text{record\_id} \parallel \text{normalized\_text} \parallel \text{split}\right)\right)$$

Where records are sorted by canonical `record_id`.
This guarantees that two pipelines running on Windows and Linux will produce the exact same logical dataset fingerprint if their textual contents and split assignments match.

---

## 5. Licensing & Provenance Governance Gate (Phase 4X)

Before any source is ingested into a VEDA training corpus, its governance status must be formally recorded:

```
┌────────────────────────────────────────────────────────┐
│               SOURCE GOVERNANCE GATE                   │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
    [VERIFIED PERMITTED]           [UNKNOWN / REQUIRES REVIEW / EXCLUDED]
            │                               │
            ▼                               ▼
       ADMITTED TO                     BLOCKED & QUARANTINED
     TRAINING CORPUS               (Will not enter training splits)
```

### Mandatory Status Categories:
1. `VERIFIED PERMITTED`: Source has a verified public domain, CC-BY, MIT, or compatible license explicitly permitting research and commercial training use.
2. `REQUIRES REVIEW`: Source has ambiguous licensing terms (e.g. non-commercial restriction `CC-BY-NC`, or unclear copyright expiration) requiring formal review.
3. `UNKNOWN`: Licensing status has not been evaluated. **Must NEVER be silently assumed permitted.**
4. `EXCLUDED`: Source is explicitly prohibited due to copyright restrictions, PII risk, or adverse content.

---

## 6. Unresolved Governance Decisions

1. `[UNRESOLVED — REQUIRES DECISION]` **Handling of CC-BY-NC (Non-Commercial) Sources**:
   - Whether VEDA (as an open educational initiative) should include CC-BY-NC textbooks, or strictly limit pretraining to unencumbered Public Domain / CC-BY sources.
   - *Status*: Strictly limited to unencumbered Public Domain / CC-BY in v0.1; NC review deferred to Phase 4 pilot source selection.
