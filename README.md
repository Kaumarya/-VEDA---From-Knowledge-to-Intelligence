# VEDA — From Knowledge to Intelligence

VEDA is an educational and research initiative to build an English-first language model from first principles without using pretrained model weights or APIs (OpenAI, Gemini, Claude, Llama, Mistral, etc.).

## Core Principle

```
UNDERSTAND → DESIGN → IMPLEMENT → TEST → MEASURE → DOCUMENT → IMPROVE
```

- Every layer is built, understood, tested, and documented by us.
- External libraries are used strictly for numerical computation and system infrastructure, never as a surrogate for our own model architecture.
- Scope for v0.x: **English only**; multilingual expansion is deferred until foundational stages are verified.

---

## High-Level Roadmap

- [x] **Phase 0 — Project architecture, safety, and foundational documentation**
- [x] **Phase 1 — English Character Foundation**
  - [x] Character Registry & Schema Verification (`veda_characters_v0.1.json`)
  - [x] Character Tokenizer v0.1 (`encode`, `decode`, round-trip tests)
  - [x] Character Knowledge Base v0.1 (`foundation.characters.knowledge.CharacterKnowledge`)
- [ ] **Phase 2 — Word Foundation v0.1 & Tokenization**
  - [x] Word Foundation v0.1 (`foundation.words.word.Word`, `foundation.words.analyzer.WordAnalyzer`)
  - [x] Controlled Development Vocabulary (`data/words/veda_words_v0.1.json`)
  - [ ] Subword Tokenization / BPE from first principles
- [x] **Phase 3 — English Lexical Foundation v0.1 & Hardening**
  - [x] Streaming Wiktionary Ingestion Pipeline (`foundation.lexicon.extractor.WiktionaryExtractor`)
  - [x] Lexicon Repository & Querying (`foundation.lexicon.lexicon.Lexicon`)
  - [x] Production SQLite Storage (`foundation.lexicon.storage.SqliteLexicon`, `data/lexicon/veda_lexicon_v0.1.sqlite`)
  - [x] Unified VEDA CLI Tooling (`veda.py` / `scripts/lexicon_cli.py`)
  - [x] Integration with Character & Word layers (`lexicon.to_word()`, `WordLexicalData`)
  - [x] Serialized Lexicon artifacts (`data/lexicon/veda_lexicon_v0.1.json`, `veda_lexicon_v0.1.sqlite`)
  - [x] Data Contracts Formalized (`docs/architecture/data_contracts.md`)
  - [x] Orthography Policy & Unicode Profiling (`docs/architecture/orthography_policy.md`)
  - [x] Dataset Audit Tooling (`foundation.lexicon.audit.DatasetAuditor`, `scripts/audit_dataset.py`)
  - [x] Memory Scaling & Storage Decision Matrix (`docs/architecture/storage_and_memory.md`)
  - [x] Adversarial Audit & Regression Suite (Golden tests, security tests, determinism, idempotency)
- [x] **Phase 4 — English Corpus Architecture & Data Contract**
  - [x] Corpus Objective & Linguistic Scope (`docs/training_corpus.md`)
  - [x] Corpus Data Contract & 6-Layer Hierarchy (`docs/corpus_data_contract.md`)
  - [x] Text Normalization Policy & RAW/Normalized Invariants (`docs/corpus_normalization_policy.md`)
  - [x] Quality Filtering, Metrics & English Language Policy (`docs/corpus_quality_policy.md`)
  - [x] Segmentation, Deduplication & Leakage-Free Splitting (`docs/corpus_split_policy.md`)
  - [x] Storage Evaluation & Streaming JSONL Architecture (`docs/corpus_storage.md`)
  - [x] Versioning Equation, Machine Manifest & Governance (`docs/corpus_versioning.md`)
  - [x] Corpus Pipeline, Golden Fixture & CLI Tooling (`foundation.corpus`, `scripts/corpus_cli.py`)
  - [x] Deterministic Splitting, Idempotency & Failure Recovery Verification
  - [x] **Phase 4.1**: Adversarial Pipeline Hardening, Unicode Decoupling, Dual Fingerprinting (`docs/veda_phase4.1_audit_report.md`)
  - [x] **Phase 4.2**: Training Source Selection, Machine-Readable Registry, Target Composition, Resource Budget, Production Gate & Controlled Pilot (`docs/veda_phase4.2_audit_report.md`)
  - [x] **Phase 4.2.1**: Adversarial Source Governance, Provenance & Ingestion-Gate Hardening (`docs/veda_phase4.2.1_audit_report.md`)
  - [x] **Phase 4.2.2**: Accuracy Audit, Evidence Repair & Regression Certification (`docs/veda_phase4.2.2_accuracy_audit_report.md`)
  - [x] **Phase 4.2.3**: Pending-Evidence Verification & Accuracy Validation (`docs/veda_phase4.2.3_verification_report.md`)
  - [x] **Phase 4.3**: Modern Python, Library Efficiency & Measured Accuracy (`docs/veda_phase4.3_environment_verification.md`, `docs/veda_phase4.3_performance_baseline.md`, `docs/veda_phase4.3_accuracy_experiments.md`)
  - [x] **Phase 4.4**: 95% Quality Gates & Comprehensive Code Audit (`docs/veda_quality_gates.md`, `docs/veda_phase4.4_code_audit.md`, `docs/veda_phase4.4_accuracy_evaluation.md`, `docs/veda_phase4.4_performance_regression.md`)
  - [x] **Phase 4.4.1**: Independent Verification & Benchmark Validation (`docs/veda_phase4.4.1_independent_verification.md`, `docs/veda_phase4.4.1_benchmark_integrity.md`, `data/corpus/phase4.4.1_verification_results.json`)
  - [x] **Phase 4.5**: Accuracy Recovery, Defect Sweep & Reliability Hardening (`docs/veda_phase4.5_accuracy_recovery.md`, `docs/veda_phase4.5_language_filter_evaluation.md`, `docs/veda_phase4.5_neardup_pipeline.md`)
  - [x] **Phase 4.6**: Python 3.14 Standardization & Accuracy Maximization (`docs/veda_phase4.6_python314_migration.md`, `docs/veda_phase4.6_accuracy_report.md`, `docs/veda_phase4.6_defect_inventory.md`, `docs/veda_phase4.6_test_results.md`, `data/corpus/phase4.6_eval_results.json`)
  - [x] **Phase 4.7**: Master Audit, Benchmark Integrity & Zero-Leakage Pre-Certification (`docs/veda_phase4.7_master_audit_report.md`, `docs/veda_phase4.7_accuracy_and_evaluation_report.md`)
  - [x] **Phase 4.8**: Defect Remediation & Master Certification (`docs/veda_phase4.8_master_certification_report.md`, `docs/veda_phase4.8_defect_and_remediation_log.md`)
  - [x] **Phase 4.9**: Certification Protocol & Governance Protocol (`docs/veda_phase4.9_certification_protocol.md`, `docs/veda_phase4.9_certification_readiness_report.md`)
  - [x] **Phase 4.10**: Audit Fixes & Verification (`docs/veda_phase4.10_verification_report.md`)
  - [x] **Phase 4.11**: Near-Deduplication Polarity Fix & Regression Verification (`docs/veda_phase4.11_verification_report.md`)
  - [x] **Phase 4.12**: Independent Validation, Governance & Provisional Benchmark v8.0 (`docs/veda_phase4.12_verification_report.md`)
  - [x] **Phase 4.13**: Remediate Language-Filter & Negation-Safety Defects (`docs/veda_phase4.13_verification_report.md`)
- [ ] **Phase 5 — Mathematical and Neural Foundations** (STRICTLY BLOCKED pending independent certification and explicit authorization)
- [ ] **Phase 6 — Transformer Architecture** (Self-attention, causal masking, MLP, blocks)
- [ ] **Phase 7 — VEDA Pretraining**
- [ ] **Phase 8 — Evaluation & Benchmarking**
- [ ] **Phase 9 — Instruction Tuning**
- [ ] **Phase 10 — Inference Engine**
- [ ] **Phase 11 — Modular RAG System**
- [ ] **Phase 12 — VEDA Chat Application**

---

## Current Status: Phase 4.13 Remediated & Verified (Phase 5 BLOCKED)

Milestones achieved:
- **Phase 4.13 Defect Remediation**:
  - **Language Filter Fix**: Dense technical English sentences with low stopword count (e.g. offshore-wind transmission cables) are preserved through an audited candidate path without diluting rejection of Romance cognates (`REJECT`) or Germanic cognates (`QUARANTINE`). Added function words (`how`, `where`, `why`, `toward`, `towards`, `throughout`, `whether`) to `_COMMON_ENGLISH_STOPWORDS`.
  - **Negation Safety Guard Fix**: Added `"no"`, `"none"`, `"nor"`, `"hardly"` to `neg_particles`. Integrated contraction normalization (`isn't`, `wasn't`, etc. -> `is not`, `was not`) and abbreviation guarding (`No. \d+` -> `number \d+`). Verified symmetric polarity conflict prevention across forward and reversed argument pairs.
- **Dual-Runtime Test Coverage (100% Parity across 300 Tests)**:
  - Python 3.14.8 (`.venv`): **300 passed / 0 failed in 4.95s**
  - Python 3.9.13 (Global): **300 passed / 0 failed in 4.70s**
- **Corpus Production Gate Verification**:
  - All 7 fail-closed gate tests passed on both runtimes (`tests/test_corpus_production_gate_fail_closed.py`). Production ingestion remains fail-closed.
- **Benchmark Governance & Independence Status**:
  - The v8.0 benchmark is formally **reclassified as development/regression data** because its examples were examined during Phase 4.12.
  - Independent benchmark certification is **PENDING** (governance status: **INDEPENDENCE UNVERIFIED**). No cosmetic 100% certification claim is made.
- **Pending Deliverables & Active Blockers**:
  - **SQLite-backed input integration testing**: **PENDING**.
  - **Independent benchmark certification**: **PENDING** (requires third-party authored sealed dataset).
  - **Production corpus source permissions & governance**: **PENDING** where unresolved.
  - **Phase 5 Model Pretraining**: **STRICTLY BLOCKED** until required quality gates pass independent certification and explicit authorization is given. Production ingestion remains fail-closed.

### Running Tests (Python 3.14)

Execute the full unit and regression test suite using the standardized Python 3.14 virtual environment:

```bash
.\.venv\Scripts\python.exe -m pytest
```

Execute the Phase 4.6 Standardization & Accuracy Maximization Evaluator:

```bash
.\.venv\Scripts\python.exe scripts/evaluate_phase46_standardization.py
```

### Training Corpus CLI Tooling

Audit source governance, run ingestion pilots, build golden fixtures, and inspect manifests:

```bash
# List and audit registered candidate sources across governance states
.\.venv\Scripts\python.exe veda.py corpus sources

# Run the Phase 4.2 controlled ingestion pilot
.\.venv\Scripts\python.exe veda.py corpus pilot

# Build golden corpus fixture (14 documents, edge cases, splitting)
.\.venv\Scripts\python.exe veda.py corpus build-golden --output data/corpus/golden_output

# Verify cryptographic file integrity and checksums against manifest
.\.venv\Scripts\python.exe veda.py corpus verify data/corpus/golden_output

# Inspect detailed machine manifest, statistics, and logical fingerprint
.\.venv\Scripts\python.exe veda.py corpus inspect-manifest data/corpus/golden_output/manifest.json
```

### Dataset Audit (Phase 3 Hardening)

Run the empirical quality and Unicode profiler across any Wiktextract sample:

```bash
# Audit small sample:
python scripts/audit_dataset.py --file veda_sample.jsonl

# Audit N lines of raw dataset:
python scripts/audit_dataset.py --file raw-wiktextract-data.jsonl --max-lines 20000
```


### Unified VEDA CLI (Production Lexicon)

Query, verify, benchmark, and inspect the SQLite production lexicon:

```bash
# View lexicon statistics and quality metrics
python veda.py lexicon stats

# Build sample database (6 words)
python veda.py lexicon build-sample

# Lookup word across all POS categories
python veda.py lexicon lookup free

# Lookup word filtered by specific part of speech
python veda.py lexicon lookup free --pos verb

# Verify database integrity (PRAGMA integrity_check + foreign keys)
python veda.py lexicon verify

# Run microsecond latency and RSS benchmark
python veda.py lexicon benchmark
```

### Lexicon Streaming Demonstration (In-Memory Reference)

Inspect streaming ingestion, word senses, parts of speech, and IPA pronunciations:

```bash
# Run demonstration:
python scripts/lexicon_demo.py

# Inspect specific word:
python scripts/lexicon_demo.py --word "free"

# Interactive REPL:
python scripts/lexicon_demo.py --interactive
```

### Word Foundation Inspection

Inspect word decomposition, validation, and character ID conversions:

```bash
# Run demonstration:
python scripts/word_demo.py

# Inspect specific word:
python scripts/word_demo.py --word "Apple"

# Interactive REPL:
python scripts/word_demo.py --interactive
```

### Character Knowledge Inspection

Inspect structured character knowledge interactively or via CLI:

```bash
# Run demonstration:
python scripts/character_demo.py

# Inspect specific character:
python scripts/character_demo.py --char "A"

# Interactive REPL:
python scripts/character_demo.py --interactive
```

### Testing Custom Inputs

You can test custom inputs interactively or directly via the command line:

1. **Interactive REPL**:
   ```bash
   python scripts/demo_tokenizer.py --interactive
   ```
2. **Single Input Inspection**:
   ```bash
   python scripts/demo_tokenizer.py --text "Your custom sentence here!"
   ```
3. **Automated Demonstration Suite**:
   ```bash
   python scripts/demo_tokenizer.py
   ```
4. **Quick One-Line Direct Invocation**:
   ```bash
   python tokenizer/char_tokenizer.py "Hello VEDA!"
   ```

---

## Project Structure

```
veda/
│
├── README.md                              # Project mission, principles, and overview
├── requirements.txt                      # Dependencies (Python 3.9+ standard library for Phase 1)
├── .gitignore                            # Large data & environment safety rules
│
├── data/
│   ├── raw/                              # Immutable raw datasets (never committed to git)
│   ├── samples/                          # Small validation samples
│   ├── processed/                        # Normalized & reproducible artifacts
│   └── characters/                       # Character registry data
│       └── veda_characters_v0.1.json
│
├── foundation/
│   ├── __init__.py
│   └── characters/                       # Character registry classes & validation
│       ├── __init__.py
│       └── registry.py
│
├── tokenizer/                            # VEDA Tokenizer subsystem
│   ├── __init__.py
│   └── char_tokenizer.py                # CharacterTokenizer v0.1
│
├── tests/                                # Unit test suite
│   ├── __init__.py
│   ├── test_character_registry.py
│   └── test_char_tokenizer.py
│
└── docs/                                 # Architectural & component documentation
    └── tokenizer/
        └── character_tokenizer_v0.1.md
```
