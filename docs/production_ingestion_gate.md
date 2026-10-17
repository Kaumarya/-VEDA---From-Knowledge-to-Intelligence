# VEDA Production Ingestion Gate Specification
## Formal Preconditions & Verification Criteria for Production Corpus Ingestion (Phase 4.2.1)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Production Corpus Ingestion Gate
Document ID: VEDA-GATE-INGESTION-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.2.1 HARDENING
========================================================================================
```

---

## 1. Executive Summary & Purpose

The **Production Ingestion Gate** is an inviolable architectural barrier. It prevents premature, uncontrolled, or legally compromised data ingestion from polluting the VEDA pretraining foundation.

> [!CRITICAL]
> **Production Gate Invariant**:
> No production-scale data download or ingestion may commence until **all 12 gate criteria** are formally satisfied, empirically verified, and ratified.
> 
> A successful small-scale pilot or passing unit test suite demonstrates pipeline *capability*; it does **NOT** constitute automatic authorization to begin large-scale production ingestion.

---

## 2. The 12 Mandatory Gate Preconditions

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION INGESTION GATE CHECKLIST                  │
├────┬──────────────────────────────────────┬─────────────┬──────────────┤
│ #  │ Gate Criterion                       │ Mech. Status│ Source Status│
├────┼──────────────────────────────────────┼─────────────┼──────────────┤
│ 1  │ Work-Level Licensing & Evidence Aud. │ [CERTIFIED] │ BLOCKED (0/12│
│ 2  │ Active (Non-Stale) Approval Check    │ [CERTIFIED] │ BLOCKED (0/12│
│ 3  │ Acquisition & Checksum Procedure     │ [CERTIFIED] │ NOT_VERIFIED │
│ 4  │ Composition: 5 Distinct Levels Defined│ [CERTIFIED] │ Level 1 Rat. │
│ 5  │ Resource & Peak Storage Budget Pinned│ [CERTIFIED] │ 120 GB Cap   │
│ 6  │ Preflight Disk Safety Checker        │ [CERTIFIED] │ 40% Reserve  │
│ 7  │ Related-Work Grouping (group_id)     │ [CERTIFIED] │ Zero Leakage │
│ 8  │ Cross-Source Attribution Preserved   │ [CERTIFIED] │ Audit Preserv│
│ 9  │ Near-Duplicate Candidate Retrieval   │ [CERTIFIED] │ Smoke Tested │
│ 10 │ Storage Format & Atomic Rollback     │ [CERTIFIED] │ Zero .tmp    │
│ 11 │ Dual Fingerprinting Validated        │ [CERTIFIED] │ Cryptographic│
│ 12 │ Controlled Pilot & Adversarial Tests │ [CERTIFIED] │ 204 Tests OK │
└────┴──────────────────────────────────────┴─────────────┴──────────────┘
```

---

### Gate 1: Source & Licensing Governance Review
- **Requirement**: Every candidate archive must be cataloged in `data/corpus/source_registry.json` and possess an affirmative `VERIFIED_PERMITTED` status.
- **Verification Rule**:
  $$\forall S \in \text{CandidateSources}: \quad S.\text{licensing\_status} \equiv \text{LicensingStatus.VERIFIED\_PERMITTED}$$
- **Blocking Condition**: Any source with status `REQUIRES_REVIEW`, `UNKNOWN`, or `EXCLUDED` is blocked at the pipeline entry. Sources with contested ShareAlike terms (e.g. Wikipedia CC-BY-SA) remain blocked until legal counsel ratifies pretraining compatibility.

### Gate 2: Source Versioning & Provenance Lineage
- **Requirement**: Source archives must be tied to a pinned release version, snapshot date, or commit hash. Upstream dynamic "latest" URLs that change silently are prohibited.
- **Verification Rule**: Every record in `train.jsonl` must trace to an exact `source_id`, `document_id`, `segment_index`, and character offsets `[start:end]`.

### Gate 3: Source Acquisition & Checksum Procedure
- **Requirement**: A deterministic, scriptable acquisition method and an expected 64-character SHA-256 archive hash must be documented in `checksum_procedure`.
- **Verification Rule**: Before uncompressing or reading an archive, the pipeline must verify:
  $$\text{sha256}(D_{\text{archive}}) == S.\text{source\_hash}$$
  Any checksum mismatch aborts the ingestion job immediately.

### Gate 4: Corpus Composition Target Approved
- **Requirement**: Target domain balance must adhere to `docs/training_corpus_composition.md` (35% Literature, 25% Educational, 15% Science/STEM, 15% General Prose/News, 10% Encyclopedic [Gated]).
- **Verification Rule**: Lexical dictionary definitions (Phase 3) must be strictly isolated from running pretraining prose.

### Gate 5: Target Size and Resource Budgets Approved
- **Requirement**: Maximum storage envelope must not exceed 120 GB (preserving a 40% disk safety margin on the 339 GB host SSD). Peak process RSS must remain under 1.5 GB.
- **Verification Rule**: Out-of-disk monitoring and stream-based generator processing enforced throughout ingestion.

### Gate 6: Component Policy Versions Pinned
- **Requirement**: All text processing engines must pin immutable version tags:
  - Text Normalizer: `0.1.0` (NFC Unicode, smart quote preservation)
  - Quality Filter: `0.1.0` (decoupled from character registry; `non_latin_ratio <= 0.15`)
  - Document Segmenter: `0.1.0` (paragraph boundary offsets)
  - Deduplication Engine: `0.1.0` (document SHA-256 + record raw/normalized SHA-256)
- **Verification Rule**: Recorded in `manifest.json.policies`.

### Gate 7: Near-Duplicate Strategy Scoped
- **Requirement**: Exact hash deduplication operates on literal string matches. For production web-scale corpora, MinHash Local-Sensitivity Hashing (128 permutations, Jaccard threshold 0.80) is required.
- **Verification Rule**: For the initial 100M-word foundation corpus from high-editorial curated sources (Standard Ebooks, OpenStax, Python Docs), exact and normalized deduplication is formally certified. An external MinHash LSH indexer is scoped for multi-gigabyte open-web expansions.

### Gate 8: Document-Level Split Policy & Seed Pinned
- **Requirement**: Split partition assignment must execute strictly at the **Document level**:
  $$h(\text{document\_id}, \text{seed}) \pmod{10000} \to \text{Split}$$
- **Verification Rule**: Random seed pinned to `"veda_split_seed_v0.1"`. Default split ratios pinned to `train=0.90`, `validation=0.05`, `test=0.05`. Cross-split document leakage is zero by construction.

### Gate 9: Storage Format & Recovery Procedure Validated
- **Requirement**: Streaming JSONL storage with UNIX newlines (`\n`) and atomic `.tmp` staging must be verified.
- **Verification Rule**: Forced process interruption cleans up `.tmp` files; clean rebuild produces bit-for-bit identical checksums.

### Gate 10: Dual Fingerprinting Architecture Validated
- **Requirement**: Both cryptographic identities must be computed and verified:
  - **Content Fingerprint**: Identifies canonical text content across splits.
  - **Manifest Fingerprint**: Identifies configuration, split seed, source hashes, and artifact digests.
- **Verification Rule**: Volatile execution timestamps, hostnames, and file paths are excluded from fingerprints.

### Gate 11: Controlled Pilot & Full Regression Suite Passing
- **Requirement**: A controlled pilot using authentic `VERIFIED_PERMITTED` sources must execute with 100% invariant compliance. The full test suite (176 baseline tests + governance gate tests) must pass with 0 errors and 0 failures.

---

## 3. Production Ingestion Authorization Decision

```
========================================================================================
CURRENT AUTHORIZATION STATUS:
ACCURACY AUDIT PASSED — PRODUCTION INGESTION STRICTLY BLOCKED
========================================================================================
```

### Rationalization & Audit Decision:
1. **Pipeline & Governance Mechanisms Certified**: The ingestion pipeline, atomic staging, fingerprinting, split allocation, and fail-closed governance enforcement are fully certified (204 unit tests green, controlled pilot verified).
2. **Candidate Sources Blocked**: All 12 candidate production sources in `data/corpus/source_registry.json` are downgraded to `REQUIRES_REVIEW` (with 2 permanently `EXCLUDED`). Their `artifact_sha256` and `license_evidence_sha256` fields are designated `NOT_VERIFIED` pending authoritative acquisition and rights verification.
3. **Pending Prerequisites Prior to Production Execution**:
   - Physical artifact acquisition and computation of authentic SHA-256 byte digests.
   - Retrieval and archival of authentic license evidence texts (not title/URL hashes).
   - Formal legal review of CC-BY-SA, ODC-BY, and public domain term boundaries.
   - Downstream subword tokenizer vocabulary design (Phase 5).
4. **Final Decision**: Production ingestion is **STRICTLY BLOCKED**. No production dataset may be ingested until external verification is complete and ratified.
