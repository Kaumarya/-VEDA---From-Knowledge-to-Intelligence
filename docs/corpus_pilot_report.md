# VEDA Phase 4.2.1 Controlled Corpus Ingestion Pilot Report
## Empirical Verification of Eligible Source Acquisition, Conservation, and Hardened Gates

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Milestone: Phase 4.2.1 Controlled Ingestion Pilot & Gate Hardening Report
Document ID: VEDA-REPORT-PILOT-4.2.1
Date: 2026-10-15
Status: HARDENING PASSED — PRODUCTION DECISIONS STILL PENDING
========================================================================================
```

---

## 1. Executive Summary

In accordance with Phase 4.2.1 specifications, the controlled ingestion pilot was executed and hardened with targeted adversarial checks:
1. Source acquisition and provenance preservation
2. Source checksum recording and auditable evidence
3. Normalization and filtering
4. Document and record conservation accounting ($N_{\text{docs}} = N_{\text{ret}} + N_{\text{rej}}$ and $N_{\text{proc}} = N_{\text{ret}} + N_{\text{rej}} + N_{\text{dup}}$)
5. Exact and normalized deduplication
6. Rejection reasons and auditable counts
7. Deterministic document-level and related-work grouping (`group_id`)
8. Storage round-trip and integrity
9. Manifest and fingerprint reproducibility
10. Failure recovery and clean rebuild equivalence
11. Cross-source duplicate attribution preservation
12. Preflight disk space safety check & strict fail-closed governance gate

> [!IMPORTANT]
> **Scope & Representation Disclaimer**: This pilot verifies **pipeline capability, conservation accounting, governance gating, related-work grouping, and deterministic reproducibility**. It does **NOT** claim to represent the final pretraining token distribution. Production ingestion remains explicitly gated under `docs/production_ingestion_gate.md`.

---

## 2. Ingested Sources & Document Portfolio

The pilot evaluated 3 candidate sources and 9 pilot documents (plus synthetic adversarial test cases):

| Source ID | Name | License | Governance Status | Expected Ingestion Outcome |
|---|---|---|---|---|
| `standard_ebooks_pilot` | Standard Ebooks Pilot | Public Domain / CC0 1.0 | `VERIFIED_PERMITTED` | Admitted to pipeline |
| `python_docs_pilot` | Python Docs Pilot | PSFL v2 / 0BSD | `VERIFIED_PERMITTED` | Admitted to pipeline |
| `unapproved_gated_source` | Third-Party Scrape Archive | All Rights Reserved | `REQUIRES_REVIEW` | Intercepted at Governance Gate |

---

## 3. Empirical Ingestion Metrics

```
Execution Runtime:             0.0062 seconds
Process Memory (RSS Before):   21.20 MB
Process Memory (RSS After):    21.44 MB
Net Memory Delta (RSS):        +0.24 MB
```

### Document-Level Conservation
$$\text{Total Documents } (9) = \text{Retained Documents } (5) + \text{Rejected Documents } (4) \quad \checkmark$$

### Record-Level Conservation
$$\text{Processed Records } (15) = \text{Retained Records } (10) + \text{Rejected Records } (3) + \text{Duplicate Records } (2) \quad \checkmark$$

Every document and record entered exactly one terminal classification state with zero unaccounted leakage.

---

## 4. Rejection & Deduplication Ledger

| Rejection Category | Stage | Count | Document / Record Example |
|---|---|---|---|
| **`DUPLICATE` (Document)** | Deduplication | 1 | `se_doc_001_exact_dup` (exact match to `se_doc_001`) |
| **`DUPLICATE` (Record)** | Deduplication | 1 | Paragraph 1 of `py_doc_003_norm_dup` (normalized match to `py_doc_001`) |
| **`GOVERNANCE_BLOCKED`** | Governance Gate | 1 | `gated_doc_001` (`unapproved_gated_source` with status `REQUIRES REVIEW`) |
| **`TOO_SHORT_CHARS`** | Quality Filter | 1 | `short_doc_001` (18 characters < 50 threshold) |
| **`NO_ENGLISH_STOPWORDS`**| Quality Filter | 1 | `foreign_latin_doc_001` (French passage lacking English function words) |
| **Total Rejections Logged** | — | **5** | All recorded in `rejections.jsonl` with provenance |

---

## 5. Storage Split Distribution & Cryptographic Identity

### Partition Allocation
- **Train Split (`train.jsonl`)**: 8 records (80.0%)
- **Validation Split (`validation.jsonl`)**: 0 records (0.0% due to discrete hash distribution on 5 retained documents)
- **Test Split (`test.jsonl`)**: 2 records (20.0%)
- **Total Retained**: 10 records (100.0%)

### Dual Cryptographic Fingerprints
- **Content Fingerprint**:
  `eab5d3870d09131ed0769c94047bd8bdaedf84e0c3268f551dafaa627bc86028`
  *(Bit-for-bit identical to Phase 4.1 / Phase 4.2 baseline)*
- **Manifest Fingerprint**:
  `3a26f1d140daaf7decdb3577dbc3ce99f22262c172cb7e11f01002017ade075a`
  *(Updated to pin grouping_version 0.1.0 and deterministic_group_hash_v1)*

---

## 6. Verification of the 12 Hardened Pilot Checks

| Check # | Evaluation Criterion | Observed Result | Status |
|---|---|---|---|
| **1** | Source acquisition & provenance preservation | Lineage to `source_id`, `document_id`, offsets preserved in all records | **PASS** |
| **2** | Source checksum recording & evidence | 64-char SHA-256 archive hashes and evidence recorded in manifest | **PASS** |
| **3** | Normalization & filtering | Whitespace standardized; NFC precomposed; control chars stripped | **PASS** |
| **4** | Conservation accounting | $N_{\text{docs}} = 5 + 4 = 9$; $N_{\text{rec}} = 10 + 3 + 2 = 15$ | **PASS** |
| **5** | Exact & normalized deduplication | Caught exact document duplicate and normalized whitespace duplicate | **PASS** |
| **6** | Rejection reasons & auditable counts | Rejections logged with metric, threshold, and snippet | **PASS** |
| **7** | Deterministic document-level splitting | All segments of a document placed in the same split; zero split leakage | **PASS** |
| **8** | Storage round-trip & integrity | `CorpusReader.read_records` reconstructed 100% of fields | **PASS** |
| **9** | Manifest & fingerprint reproducibility | Bit-for-bit identical fingerprints on rebuild | **PASS** |
| **10** | Failure recovery & clean rebuild | Interrupted build cleaned `.tmp` files; clean rebuild passed | **PASS** |
| **11** | Related-Work Grouping & Cross-Source Dedup | Chapter and excerpt unified via `group_id`; contributing sources preserved | **PASS** |
| **12** | Preflight Disk Check & Fail-Closed Gate | Aborted before writing files on 10 TB request; unapproved source blocked | **PASS** |

---

## 7. Pilot Conclusion & Gate Status

The Phase 4.2.1 controlled ingestion pilot demonstrated 100% compliance across all 12 operational and adversarial checks.

- **Pilot Outcome**: **PASSED**
- **Authoritative Status**: **`HARDENING PASSED — PRODUCTION DECISIONS STILL PENDING`**
- Large-scale production ingestion remains unauthorized until the source portfolio, license evidence, composition, resource budget, near-duplicate evaluation, and training-split policy are explicitly approved.
