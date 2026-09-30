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
- [ ] **Phase 4 — English Corpus Pipeline**
- [ ] **Phase 5 — Mathematical and Neural Foundations** (Tensors, linear layers, loss, backprop)
- [ ] **Phase 6 — Transformer Architecture** (Self-attention, causal masking, MLP, blocks)
- [ ] **Phase 7 — VEDA Pretraining**
- [ ] **Phase 8 — Evaluation & Benchmarking**
- [ ] **Phase 9 — Instruction Tuning**
- [ ] **Phase 10 — Inference Engine**
- [ ] **Phase 11 — Modular RAG System**
- [ ] **Phase 12 — VEDA Chat Application**

---

## Current Status: Phase 3 (Foundation Hardening & Full-System Audit)

Milestones completed:
- **Character Registry**: Encapsulated in `foundation.characters.registry.CharacterRegistry`.
  - Authoritative inventory: **113 registered characters** (95 printable ASCII + 18 essential whitespace & typography) + **4 special tokens** (`<PAD>`, `<UNK>`, `<BOS>`, `<EOS>`) = **117 total tokenizer vocabulary**.
- **Character Tokenizer**: Implemented in `tokenizer.char_tokenizer.CharacterTokenizer` with lossless roundtrip.
- **Character Knowledge Base**: Implemented in `foundation.characters.knowledge.CharacterKnowledge` with JSON dataset at `data/characters/veda_character_knowledge_v0.1.json`.
- **Word Foundation**: Implemented in `foundation.words.word.Word` and `foundation.words.analyzer.WordAnalyzer` with controlled vocabulary at `data/words/veda_words_v0.1.json`.
- **Lexical Foundation & Production SQLite**:
  - Full production SQLite database at `data/lexicon/veda_lexicon_v0.1.sqlite` (959,688 unique words, 1,049,403 POS entries, 1,322,676 senses, 2.24 GB).
  - Out-of-core memory safety with < 3 MB RSS overhead on open and sub-millisecond lookups (~160 μs).
  - Sample database at `data/lexicon/veda_lexicon_sample.sqlite` (6 words, 155 KB).
- **Architectural Data Contracts**: Explicit boundaries established between Character, Character Knowledge, Word, Lexical Entry, Corpus Record, Token, Training Example, and Model.
- **Orthography Policy**: Explicit v0.1 policy separating language classification (`en`), orthographic constraints (`plain_ascii`), and character registry representability.
- **Audit & Security Tooling**: Streaming dataset profiler, SQL injection defense, boundary invariance, and logical database checksum fingerprinting.
- **Round-Trip Invariants**:
  - Characters: `decode(encode(text)) == text`
  - Words: `decode_word(encode_word(word)) == normalized_word`
  - Lexicon: `Lexicon.from_dict(lex.to_dict()) == lex`
  - SQLite: `SqliteLexicon.lookup(w) == In_Memory_Lexicon[w]`
- **Testing**: 95 unit tests passing across all layers (Pytest 100% green).

### Running Tests

Execute the full unit test suite:

```bash
pytest -v
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
