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
- [ ] **Phase 3 — English Lexical Foundation** (Wiktionary/Wiktextract streaming extraction)
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

## Current Status: Phase 2 (Word Foundation v0.1)

Milestones completed:
- **Character Registry**: Verified and encapsulated in `foundation.characters.registry.CharacterRegistry`.
- **Character Tokenizer**: Implemented in `tokenizer.char_tokenizer.CharacterTokenizer`.
- **Character Knowledge Base**: Implemented in `foundation.characters.knowledge.CharacterKnowledge` with JSON dataset at `data/characters/veda_character_knowledge_v0.1.json`.
- **Word Foundation**: Implemented in `foundation.words.word.Word` and `foundation.words.analyzer.WordAnalyzer` with controlled vocabulary at `data/words/veda_words_v0.1.json`.
- **Round-Trip Invariants**:
  - Characters: `decode(encode(text)) == text`
  - Words: `decode_word(encode_word(word)) == normalized_word`
- **Testing**: 44 unit tests passing across all layers.

### Running Tests

Execute the full unit test suite with Python's built-in `unittest` runner:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
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
