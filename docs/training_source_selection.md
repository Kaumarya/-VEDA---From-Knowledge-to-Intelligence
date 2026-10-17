# VEDA Training Source Selection & Licensing Governance
## Authoritative Source Portfolio & Legal Evaluation Specification (Phase 4.2)

```
========================================================================================
VEDA — "From Knowledge to Intelligence"
Foundational Architectural Specification: Training Source Selection & Licensing Governance
Document ID: VEDA-POLICY-SOURCES-v0.1
Status: RATIFIED SPECIFICATION — PHASE 4.2.1
========================================================================================
```

> [!CAUTION]
> **LEGAL NOTICE & ENGINEERING BOUNDARY**:
> The VEDA Source Governance Engine is an automated engineering gating system and technical provenance ledger. It does **not** constitute legal advice, a formal attorney-client opinion, or an absolute guarantee of copyright status across all world jurisdictions.

---

## 1. Executive Summary & Foundational Governance Mission

A foundational principle of Project VEDA is that language model intelligence must be built upon an **auditable, legally verified, and intellectually rigorous source foundation**. 

Many modern large language models have been trained on indiscriminate, web-scraped data containing unvetted intellectual property, private personal data, and low-quality search-engine-optimized spam. VEDA strictly rejects this approach.

> [!CRITICAL]
> **The Core Governance Invariant**:
> $$\text{Publicly Accessible} \neq \text{Public Domain} \neq \text{Training Permitted}$$
> 
> 1. **Publicly Accessible**: Content visible on the open internet without an authentication paywall (e.g. personal blogs, news articles, discussion forums, social media, code repositories). Such accessibility confers **zero legal or ethical rights** for machine learning pretraining.
> 2. **Public Domain**: Works where copyright protection has legally lapsed (e.g., published in the United States prior to 1929, or authors deceased > 70 years in life+70 jurisdictions) or works explicitly dedicated to the public domain via CC0 1.0 Universal.
> 3. **Training Permitted**: Works accompanied by an explicit, verifiable affirmative license grant (e.g., CC0, Public Domain, CC-BY 4.0, CC-BY 2.5, MIT, Apache 2.0, PSFL) that legally authorizes automated extraction, derivative processing, and computational training.

Under Phase 4.2.1, no dataset or text archive may enter VEDA's ingestion pipeline without passing the machine-readable **Source Registry** and receiving an authoritative, non-stale `VERIFIED_PERMITTED` classification.

---

## 2. Machine-Readable Source Registry Schema (Phase 4.2.1 Hardening)

All candidate sources are cataloged in `data/corpus/source_registry.json` and parsed via `foundation/corpus/sources.py` (`SourceRegistry`).

### Required Schema Fields

| Field Name | Type | Description | Mandatory Invariant |
|---|---|---|---|
| `source_id` | `string` | Stable slug identifier (`^[a-z0-9_.-]+$`). | Unique across the entire repository. |
| `name` | `string` | Official human-readable title of the archive. | Non-empty. |
| `publisher` | `string` | Sponsoring institution, foundation, or organization. | Must identify legal publisher. |
| `version` | `string` | Release tag, commit hash, or date version identifier. | Must be pinned and reproducible. |
| `url_or_path` | `string` | Canonical HTTP/HTTPS URL for source acquisition. | Official upstream repository URL. |
| `acquisition_date` | `string` | ISO-8601 date of acquisition or review (`YYYY-MM-DD`). | Binds provenance timestamps. |
| `source_hash` | `string` | Hex SHA-256 cryptographic checksum of archive. | Exactly 64 hex characters. |
| `checksum_procedure`| `string` | Concrete instructions for re-verifying archive hash. | Reproducible command. |
| `license` | `string` | Formal legal license name (e.g. `CC0-1.0`, `CC-BY-4.0`). | Standard SPDX identifier where available. |
| `license_url` | `string` | Canonical link to legal deed or license text. | Active HTTP/HTTPS URL. |
| `licensing_status` | `enum` | One of 4 authoritative governance states. | Strict enum enforcement. |
| `commercial_permitted`| `bool/null`| Whether commercial exploitation of text is permitted. | Explicit boolean evaluation. |
| `training_permitted_status`| `string` | `EXPLICITLY_PERMITTED`, `PROHIBITED`, or `UNCLEAR`. | Must match governance state. |
| `attribution_requirements`| `string` | Specific text or metadata credit required by license. | Recorded in `manifest.json`. |
| `redistribution_requirements`| `string` | Legal conditions for redistributing raw/derived text. | Evaluated for ShareAlike risk. |
| `modification_conditions`| `string` | Explicit rights to modify, clean, and normalize text. | Recorded in registry. |
| `work_level_scope` | `string` | Subcollection, edition, or work-level granularity. | Distinguishes works within collection. |
| `jurisdiction_limitations`| `string` | Jurisdiction boundaries (e.g. US pre-1929 vs life+70).| Identifies geographic restrictions. |
| `access_api_terms` | `string` | Terms of service governing downloading and bulk APIs. | Rate limits & robots.txt compliance. |
| `mixed_license_risks` | `string` | Known third-party components (images, footnotes). | Parser stripping requirements. |
| `evidence_retrieval_date`| `string` | ISO date license deed/terms were audited. | Stamped audit date. |
| `evidence_checksum` | `string` | Hex SHA-256 hash of authoritative license text. | 64-char hex string. |
| `reviewer_identity` | `string` | Name and role of human/committee auditor. | Auditable responsibility. |
| `review_date` | `string` | Date of governance decision. | Audit trail. |
| `re_review_triggers` | `string` | Events triggering mandatory re-review. | 180-day cycle or upstream change. |
| `approval_expiration_date`| `string` | Expiration timestamp; stale approval blocks gate. | Fail-closed expiration. |
| `approx_doc_count` | `int` | Approximate document/book count. | Split distribution planning. |
| `reviewer_notes` | `string` | Architectural analysis of linguistic value and risks. | Explicit qualitative assessment. |
| `unresolved_questions` | `string` | Open questions, legal reviews, or tooling prerequisites.| Unresolved gating criteria. |

---

## 3. The Four Governance States

Every candidate source is classified into exactly one of four mutually exclusive states:

```
                          ┌───────────────────────────┐
                          │   CANDIDATE DATA SOURCE   │
                          └─────────────┬─────────────┘
                                        │
                         Legal & Provenance Evaluation
                                        │
           ┌────────────────────┬───────┴────────────┬───────────────────┐
           ▼                    ▼                    ▼                   ▼
  [VERIFIED PERMITTED]  [REQUIRES REVIEW]        [UNKNOWN]          [EXCLUDED]
           │                    │                    │                   │
           ▼                    ▼                    ▼                   ▼
       ADMITTED              BLOCKED              BLOCKED             BLOCKED
   (Eligible for        (Legal or PII        (Unverified or      (Copyrighted or
  training splits)      clarity needed)     missing license)       prohibited)
```

1. **`VERIFIED_PERMITTED`**:
   - The license grant affirmatively and unambiguously permits computational processing, derivative compilation, and machine learning training (e.g. Public Domain, CC0 1.0, CC-BY 4.0, CC-BY 2.5, MIT, Apache 2.0, PSFL).
   - Commercial permissions are documented.
   - PII and privacy risks have been evaluated as minimal.
   - **Only sources in this state may enter training splits.**

2. **`REQUIRES_REVIEW`**:
   - The text possesses an open license, but downstream implications are contested or legally unresolved (e.g. `CC-BY-SA` ShareAlike downstream weight status).
   - Restricted clauses exist (e.g. `CC-BY-NC` non-commercial, `CC-BY-ND` no derivatives).
   - High OCR error rates or crowdsourced safety risks require specialized pre-filtering before admission.
   - **Strictly blocked at the governance gate.**

3. **`UNKNOWN`**:
   - Sources lacking explicit license metadata, provenance receipts, or verifiable legal ownership.
   - **Strictly blocked at the governance gate.** Must never be assumed permissible.

4. **`EXCLUDED`**:
   - Proprietary, all-rights-reserved copyright, paywalled publications, automated scrape dumps violating terms of service, or datasets containing high-density private personal data (PII).
   - **Permanently prohibited from Project VEDA.**

---

## 4. Evaluation of Candidate Source Categories

A comprehensive legal and linguistic evaluation was conducted across 14 candidate sources:

### Category A: Public-Domain Books & Long-Form Writing

#### 1. Standard Ebooks (`standard_ebooks`)
- **Publisher**: Standard Ebooks Volunteer Association (`standardebooks.org`)
- **License**: Public Domain (US) + CC0 1.0 Universal (editorial additions, markup, and typography).
- **Status**: **`VERIFIED_PERMITTED`**
- **Quality & Diversity**: Outstanding editorial standard. Texts are meticulously proofread against physical first editions, formatted with rich typographic punctuation (smart quotes `“”`, em-dashes `—`, accented loanwords *café*), and free of optical character recognition (OCR) artifacts.
- **Duplication Risk**: Low. Standard Ebooks maintains one definitive edition per work.
- **Contribution**: Provides sustained long-form literary English, complex paragraph syntax, extensive vocabulary, and natural narrative structure.
- **Gate Decision**: **Admitted to Eligible Pilot Portfolio.**

#### 2. Project Gutenberg (`project_gutenberg`)
- **Publisher**: Project Gutenberg Literary Archive Foundation (`gutenberg.org`)
- **License**: Public Domain in the United States.
- **Status**: **`VERIFIED_PERMITTED`** (Subject to Boilerplate Stripping Requirement)
- **Quality & Diversity**: Massive scale (70,000+ titles) spanning 18th, 19th, and early 20th-century English literature, philosophy, scientific treatises, and historical documents.
- **Risks**:
  - **License Boilerplate**: Every Gutenberg text contains 200–500 lines of legal disclaimers and trademark boilerplate at the start and end. Ingesting this uncleaned causes neural models to memorize Project Gutenberg legal clauses.
  - **Mandatory Policy**: All PG documents must pass through a strict `*** START OF THE PROJECT GUTENBERG EBOOK ***` and `*** END OF THE PROJECT GUTENBERG EBOOK ***` header/footer stripper before entering VEDA normalization.
- **Contribution**: Massive historical English vocabulary, syntactic breadth, and long-range coherence.
- **Gate Decision**: **Admitted to Production Portfolio.**

#### 3. Internet Archive / Open Library Pre-1928 Scans (`internet_archive_open_library`)
- **Publisher**: Internet Archive (`archive.org`)
- **License**: Public Domain (claimed) / Mixed.
- **Status**: **`REQUIRES_REVIEW`**
- **Risks**: High OCR error rate (scanning artifacts, character substitutions like `tbe` for `the`, broken hyphenation across line wraps). Inconsistent metadata verification across participating digitizing libraries.
- **Gate Decision**: **Blocked from Ingestion until OCR post-correction and metadata verification tooling are validated.**

---

### Category B: Official Documentation & Educational Material

#### 4. OpenStax College Textbooks (`openstax_textbooks`)
- **Publisher**: Rice University / OpenStax (`openstax.org`)
- **License**: Creative Commons Attribution 4.0 International (CC-BY 4.0).
- **Status**: **`VERIFIED_PERMITTED`**
- **Quality & Diversity**: Peer-reviewed college textbooks written by domain experts across biology, physics, chemistry, calculus, sociology, psychology, American history, and economics.
- **Legal Compliance**: CC-BY 4.0 requires attribution, which is preserved in `manifest.json` and record provenance. Commercial training is permitted.
- **Contribution**: Exemplary expository English, clear conceptual definitions, logical transitions, scientific vocabulary, and structured pedagogical prose.
- **Gate Decision**: **Admitted to Production Portfolio.**

#### 5. Python Official Documentation (`python_docs`)
- **Publisher**: Python Software Foundation (`docs.python.org`)
- **License**: Python Software Foundation License Version 2 (PSFL v2) / Zero-Clause BSD.
- **Status**: **`VERIFIED_PERMITTED`**
- **Quality & Diversity**: Highly structured, grammatically rigorous technical English. Clear narrative tutorials, precise functional descriptions, and standardized terminology.
- **Contribution**: High-precision expository reasoning, technical English discourse, and structured syntax.
- **Gate Decision**: **Admitted to Eligible Pilot Portfolio.**

#### 6. English Wikibooks (`wikibooks_en`)
- **Publisher**: Wikimedia Foundation (`en.wikibooks.org`)
- **License**: Creative Commons Attribution-ShareAlike 4.0 (CC-BY-SA 4.0) & GFDL.
- **Status**: **`REQUIRES_REVIEW`**
- **Legal Consideration**: ShareAlike condition requires derivative adaptations to be released under the same license. Ongoing international legal ambiguity regarding whether machine learning model weights constitute an adaptation under CC-BY-SA.
- **Gate Decision**: **Blocked pending formal legal policy determination.**

---

### Category C: Openly Licensed Encyclopedic Reference

#### 7. Simple English Wikipedia (`simple_wikipedia`)
- **Publisher**: Wikimedia Foundation (`simple.wikipedia.org`)
- **License**: CC-BY-SA 4.0 & GFDL.
- **Status**: **`REQUIRES_REVIEW`**
- **Linguistic Value**: Outstanding conceptual clarity. Explains complex world phenomena using direct, foundational English sentence structures and core vocabulary.
- **Legal Consideration**: Subject to the CC-BY-SA ShareAlike review.
- **Gate Decision**: **Blocked pending formal legal policy determination.**

#### 8. English Wikipedia Full Dump (`wikipedia_en`)
- **Publisher**: Wikimedia Foundation (`en.wikipedia.org`)
- **License**: CC-BY-SA 4.0 & GFDL.
- **Status**: **`REQUIRES_REVIEW`**
- **Risks**: Massive wikitext template noise (infoboxes, citation templates, coordinate tags, disambiguation lists), vandalism, and CC-BY-SA ShareAlike terms.
- **Gate Decision**: **Blocked pending legal review and wikitext cleaning pipeline implementation.**

---

### Category D: Openly Licensed News, Essays & Scientific Research

#### 9. English Wikinews (`wikinews_en`)
- **Publisher**: Wikimedia Foundation (`en.wikinews.org`)
- **License**: Creative Commons Attribution 2.5 Generic (CC-BY 2.5).
- **Status**: **`VERIFIED_PERMITTED`**
- **Crucial Distinction**: Unlike Wikipedia and Wikibooks, **Wikinews is licensed under pure CC-BY (Attribution-only), NOT CC-BY-SA!** There is zero ShareAlike restriction.
- **Quality & Contribution**: Contemporary journalistic reporting, active-voice prose, world events coverage, and professional news syntax.
- **Gate Decision**: **Admitted to Production Portfolio.**

#### 10. PLOS Peer-Reviewed Open Access Scientific Research (`plos_open_access`)
- **Publisher**: Public Library of Science (`plos.org`)
- **License**: Creative Commons Attribution 4.0 International (CC-BY 4.0).
- **Status**: **`VERIFIED_PERMITTED`**
- **Policy Stance**: PLOS explicitly permits and encourages automated Text and Data Mining (TDM) across its entire corpus.
- **Contribution**: High-level academic discourse, formal research methodology, empirical reasoning, Greek scientific symbols ($\lambda, \alpha$), and mathematical prose.
- **Gate Decision**: **Admitted to Production Portfolio.**

---

### Category E: Conversational & Dialogue Text

#### 11. OpenAssistant OASST2 (`openassistant_oasst2`)
- **Publisher**: LAION / OpenAssistant Community
- **License**: Apache 2.0.
- **Status**: **`REQUIRES_REVIEW`**
- **Risks**: While Apache 2.0 provides an affirmative commercial license, crowdsourced dialogues carry severe risks of personally identifiable information (PII) leakage, prompt injection attacks, and inconsistent quality.
- **Gate Decision**: **Blocked until automated PII scrubbing and safety filtering are established.**

#### 12. Ubuntu IRC Dialogue Corpus (`ubuntu_dialogue_corpus`)
- **Publisher**: Lowe et al. / Ubuntu Community
- **License**: Unclear / Scraped IRC Logs.
- **Status**: **`EXCLUDED`**
- **Reason**: Scraped from public IRC channels without affirmative participant consent. High PII density (real usernames, IP addresses, system crash dumps, pasted passwords).
- **Gate Decision**: **Permanently Excluded.**

---

### Category F: Raw Web Crawls

#### 13. Common Crawl Unfiltered Dumps (`common_crawl_unfiltered`)
- **Publisher**: Common Crawl Foundation
- **License**: All Rights Reserved / Mixed Internet Content.
- **Status**: **`EXCLUDED`**
- **Reason**: Violates VEDA's foundational governance principle. Contains copyrighted books, paywalled news, private contact information, SEO spam, and toxic noise.
- **Gate Decision**: **Permanently Excluded from Project VEDA.**

---

### Category G: Lexical Reference Resources

#### 14. Wiktextract English Dictionary (`wiktionary_lexicon_reference`)
- **Publisher**: Wikimedia Foundation / Tatu Ylonen
- **License**: CC-BY-SA 3.0 Unported.
- **Status**: **`VERIFIED_PERMITTED` (Strictly as Lexicon Reference)**
- **Architectural Role**: Serves as the authoritative **Phase 3 Lexical Database** (959,688 words, definitions, POS, IPA).
- **CRITICAL DISTINCTION**: Dictionaries provide discrete lemma lookups. They **must NOT** be ingested as running prose for pretraining. Autoregressive language models require natural discursive flow, narrative transitions, and multi-sentence coherence, which dictionaries cannot provide.
- **Gate Decision**: **Maintained as discrete Lexical Reference; excluded from running discourse pretraining splits.**

---

## 5. Summary Portfolio Matrix

| Source ID | Content Category | License | Status | Commercial | ML Training | Admissibility |
|---|---|---|---|---|---|---|
| `standard_ebooks` | Books & Literature | Public Domain / CC0 | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED (PILOT)** |
| `project_gutenberg`| Books & Literature | Public Domain (US) | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED** |
| `openstax_textbooks`| Educational (College)| CC-BY 4.0 | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED** |
| `python_docs` | Technical Docs | PSFL v2 / 0BSD | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED (PILOT)** |
| `wikinews_en` | News & Journalism | CC-BY 2.5 | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED** |
| `plos_open_access` | Scientific Research | CC-BY 4.0 | `VERIFIED_PERMITTED` | Yes | Explicit | **ADMITTED** |
| `simple_wikipedia` | Encyclopedic (Simple) | CC-BY-SA 4.0 | `REQUIRES_REVIEW` | Yes | Unclear (SA)| **BLOCKED** |
| `wikipedia_en` | Encyclopedic (Full) | CC-BY-SA 4.0 | `REQUIRES_REVIEW` | Yes | Unclear (SA)| **BLOCKED** |
| `wikibooks_en` | Educational Books | CC-BY-SA 4.0 | `REQUIRES_REVIEW` | Yes | Unclear (SA)| **BLOCKED** |
| `openassistant_oasst2`| Dialogue | Apache 2.0 | `REQUIRES_REVIEW` | Yes | Explicit | **BLOCKED (PII)** |
| `internet_archive_open_library`| Books (Scans) | Mixed / PD | `REQUIRES_REVIEW` | Unclear | Unclear | **BLOCKED (OCR)** |
| `ubuntu_dialogue_corpus`| IRC Chat Logs | Scraped / Unclear | `EXCLUDED` | No | Prohibited | **PERMANENTLY EXCLUDED** |
| `common_crawl_unfiltered`| Raw Web Crawl | Mixed Copyright | `EXCLUDED` | No | Prohibited | **PERMANENTLY EXCLUDED** |
| `wiktionary_lexicon_reference`| Lexical Reference | CC-BY-SA 3.0 | `VERIFIED_PERMITTED` | Yes | Explicit | **LEXICON ONLY (NON-PROSE)** |

---

## 6. Pilot Source Selection

For the Phase 4.2 controlled ingestion pilot, two exemplary `VERIFIED_PERMITTED` sources are selected:
1. **`standard_ebooks`**: Representative of authentic public-domain long-form prose and literary English.
2. **`python_docs`**: Representative of rigorous expository and technical documentation.

Both sources feature unambiguous, affirmative legal grants, high editorial quality, rich typography, zero contemporary PII risk, and deterministic archive checksums.
