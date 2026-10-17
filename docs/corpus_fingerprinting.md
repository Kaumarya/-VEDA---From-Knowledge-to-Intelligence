# VEDA Corpus Fingerprinting & Identity Architecture (Phase 4.1)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Dual Fingerprint Model (Content vs. Manifest)
Document ID: VEDA-SPEC-FINGERPRINT-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.1 HARDENING
========================================================================================
```

---

## 1. Executive Summary & Design Rationale

In cryptographic dataset provenance, conflating **content identity** (what text was selected into which split) with **configuration identity** (what source versions, license declarations, and filter parameters produced it) creates ambiguity:

- A metadata update (e.g., correcting an attribution note or bumping a documentation version) should **not** invalidate the mathematical identity of the training tokens.
- Conversely, two pipelines that generate identical text using different seeds, different source commits, or different policy versions must be recognized as having **different provenance configurations**.

Phase 4.1 establishes a strict **Dual-Identity Fingerprint Architecture**:

```
┌────────────────────────────────────────────────────────┐
│ 1. CONTENT FINGERPRINT (content_fingerprint)            │
│ Canonical mathematical hash of the model-facing text.   │
└────────────────────────────────────────────────────────┘
                           ▲
                           │ references
┌──────────────────────────┴─────────────────────────────┐
│ 2. MANIFEST FINGERPRINT (manifest_fingerprint)         │
│ Reproducibility configuration & provenance identity.    │
└────────────────────────────────────────────────────────┘
```

---

## 2. Content Fingerprint (`content_fingerprint`)

The **Content Fingerprint** identifies the canonical textual corpus content and split assignments.

### Mathematical Definition:
For each accepted training record $r \in \text{Records}$:

$$\text{digest}(r) = \text{SHA256}\left(\text{record\_id} \parallel \text{"::"} \parallel \text{normalized\_text} \parallel \text{"::"} \parallel \text{split}\right)$$

The global Content Fingerprint is computed over all canonical record digests sorted lexicographically by `record_id`:

$$\text{content\_fingerprint} = \text{SHA256}\left(\bigoplus_{r \in \text{sorted}(\text{Records})} \text{record\_id} \parallel \text{":"} \parallel \text{digest}(r) \parallel \text{"\n"}\right)$$

### Invariant Properties:
1. **Content Sensitivity**: Any change to `record_id`, `normalized_text`, or `split` changes `content_fingerprint`.
2. **Platform Invariance**: Operating system newline translations (`\r\n` vs. `\n`) or filesystem directory paths have **zero** effect on `content_fingerprint`.
3. **Metadata Decoupling**: Changes to non-textual source descriptions, creator metadata, or execution timestamps do **not** change `content_fingerprint`.

---

## 3. Manifest Fingerprint (`manifest_fingerprint`)

The **Manifest Fingerprint** identifies the full reproducibility configuration of the corpus build.

### Canonical Schema Included in Manifest Hash:
```json
{
  "corpus_name": "veda_corpus_v0.1",
  "corpus_version": "0.1.0",
  "schema_version": "0.1.0",
  "pipeline_version": "0.1.0",
  "policies": {
    "deduplication_version": "0.1.0",
    "filtering_version": "0.1.0",
    "normalization_version": "0.1.0",
    "segmentation_version": "0.1.0",
    "split_version": "0.1.0"
  },
  "sources": [
    {
      "source_id": "gutenberg_essays",
      "version": "2026.09",
      "license": "Public Domain",
      "licensing_status": "VERIFIED PERMITTED",
      "source_hash": "a1b2c3..."
    }
  ],
  "split_seed": "VEDA_CORPUS_SEED_v0.1",
  "split_config": {
    "train_ratio": 0.90,
    "val_ratio": 0.05,
    "test_ratio": 0.05
  },
  "content_fingerprint": "204ba7ebeb83104ff56ffc54649a60645305427c5c222ec5f0f65284bd56bb7c",
  "artifact_hashes": {
    "train": "d8a084c647f9bfd6444e512885113ac7718fecdc0edefe815aefdf22c90a8c0d",
    "validation": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "test": "c6e3d1775f92e343fff541c13bb24d6ddf179535b9750bbb454e1e5bfc053d10",
    "rejections": "a9ab8eee402704557516823e17386ae32b44e2b0ed0c763e99460fe5d2e774ba"
  }
}
```

### Strictly Excluded (Nondeterministic Fields):
The following volatile variables are **strictly excluded** from the manifest hash calculation:
- `created_at` (run timestamp)
- Hostname, username, or operating system user
- Process ID (PID)
- Local filesystem paths or temporary directories (`tmp_path`)
- Random UUID tokens

$$\text{manifest\_fingerprint} = \text{SHA256}(\text{canonical\_json\_bytes}(\text{canonical\_config}))$$

---

## 4. Formal Four-Case Behavioral Matrix

| Case | Scenario | Content Fingerprint Result | Manifest Fingerprint Result |
|---|---|---|---|
| **CASE 1** | Same content + same configuration | **UNCHANGED** | **UNCHANGED** |
| **CASE 2** | Same content + changed policy/source metadata | **UNCHANGED** | **MUST CHANGE** |
| **CASE 3** | Changed corpus content (records/split) | **MUST CHANGE** | **MUST CHANGE** |
| **CASE 4** | Output directory path / filesystem location changed only | **UNCHANGED** | **UNCHANGED** |
