# VEDA Corpus Licensing & Data Governance Policy (Phase 4.1)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Source Governance, Licensing & Eligibility
Document ID: VEDA-POLICY-GOVERNANCE-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.1 HARDENING
========================================================================================
```

---

## 1. Executive Summary & Legal Terminology Precision

A foundational ethical and legal requirement of VEDA is uncompromising provenance and data governance:

> [!CRITICAL]
> **The Three-Way Distinction**:
> $$\text{Publicly Accessible} \neq \text{Public Domain} \neq \text{Training Permitted}$$
> 
> 1. **Publicly Accessible**: Text is visible on the open web without a paywall (e.g. blog posts, newspaper articles, GitHub repos). This confers **zero** inherent rights for model pretraining.
> 2. **Public Domain**: Works where copyright has legitimately expired (e.g., author died > 70 years ago, pre-1928 publications in the US) or explicitly dedicated via CC0.
> 3. **Training Permitted**: Works possessing an affirmative, verified license grant (e.g. Public Domain, CC0, CC-BY, MIT, Apache 2.0) that explicitly allows extraction, processing, and machine learning training.

The system strictly avoids inaccurate umbrella terms such as *"Public Domain Source Corpus"* unless every constituent document has been legally verified as public domain. The authoritative terminology is:

$$\text{TRAINING-ELIGIBLE SOURCE CORPUS}$$

---

## 2. The Four Governance States

Every candidate data source cataloged in VEDA must be classified into exactly one of four governance states:

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

| Governance State | Formal Definition | Admissibility to Training Splits | Handling by Pipeline |
|---|---|---|---|
| **`VERIFIED PERMITTED`** | Source license is formally verified as CC0, Public Domain, CC-BY, MIT, or compatible with unrestricted pretraining. | **ADMITTED** | Processed through segmentation, filtering, and splitting. |
| **`REQUIRES REVIEW`** | Source has restrictive terms (e.g. `CC-BY-NC` non-commercial, `CC-BY-ND` no derivatives) or jurisdictional expiration ambiguity requiring legal review. | **BLOCKED** | Blocked at governance gate. Logged to `rejections.jsonl` under `GOVERNANCE_BLOCKED`. |
| **`UNKNOWN`** | Source licensing status has not been verified. | **STRICTLY BLOCKED** | Must **never** be silently assumed permitted. Quarantined in `rejections.jsonl`. |
| **`EXCLUDED`** | Source is explicitly prohibited due to copyright restrictions, paywalls, PII risk, or terms prohibiting AI training. | **STRICTLY PROHIBITED** | Immediately rejected and excluded from all pipeline operations. |

---

## 3. The Governance Invariant

$$\forall S_j \in \text{Sources}, \quad \text{Admit}(S_j) \iff S_j.\text{licensing\_status} \equiv \text{LicensingStatus.VERIFIED\_PERMITTED}$$

If a source has any other status:
- All documents from that source are intercepted before segmentation.
- A structured record is written to `rejections.jsonl` with `rejection_reason = GOVERNANCE_BLOCKED`.
- Zero records from that source enter `train.jsonl`, `validation.jsonl`, or `test.jsonl`.

---

## 4. Production Source Ingestion Gate

The completion of Phase 4.1 certifies the **architecture and governance mechanisms**. It does **NOT** authorize downloading or ingesting external production corpora until:
1. Each prospective external source is cataloged in `sources.json`.
2. Cryptographic archive hashes (`source_hash`) are verified against upstream releases.
3. Written licensing confirmation is established.
4. Attribution requirements are cataloged in `manifest.json`.
