# VEDA English Lexical Foundation v0.1
*Component: Lexical Foundation (Phase 3 — From Words to Meaning)*

```
VEDA Multi-Layer Architecture:
Character Registry  ──►  Character Knowledge  ──►  Word Foundation  ──►  Lexicon Foundation  ──►  Tokenizer / Model
 ("Represent Symbol")    ("Understand Symbol")     ("Compose Words")   ("Define Meaning")     ("Tokenize & Learn")
```

---

## 1. What the Lexical Foundation Is

In the VEDA architecture, the **Lexical Foundation** is the semantic subsystem that endows structural word candidates with dictionary definitions, parts of speech, pronunciations, inflected forms, and semantic relationships (synonyms, antonyms, etymology).

While:
- **Phase 1 (Character Foundation)** defines symbol identity and discrete token indices,
- **Phase 2 (Word Foundation)** composes symbols into morphological words and validates orthographic candidate constraints,
- **Phase 3 (Lexical Foundation)** answers:
  > *"What does this word mean, how is it used, how is it pronounced, and how is it related to other words?"*

---

## 2. Ingestion Pipeline & Architecture

The Lexical Foundation processes Wiktionary raw dumps (such as Wiktextract JSONL datasets) through a strictly non-allocating streaming pipeline:

```mermaid
graph TD
    RawFile[raw-wiktextract-data.jsonl / veda_sample.jsonl] --> Stream[Streaming Generator O(1) Memory]
    Stream --> LangFilter{Language Check: English?}
    LangFilter -- No (Latin, German, Scots, etc.) --> SkipForeign[Skip Non-English Record]
    LangFilter -- Yes --> CandidateCheck{WordAnalyzer Candidate Validation}
    CandidateCheck -- Fails (digits, punctuation, spaces, non-ASCII) --> SkipInvalid[Skip Non-Word Candidate]
    CandidateCheck -- Passes (e.g. dictionary, free, portmanteau) --> MojibakeRepair[Clean Mojibake / Double UTF-8 Encoding]
    MojibakeRepair --> SensesParse[Parse Senses, Glosses, POS, IPA, Forms]
    SensesParse --> Aggregator{Normalized Word in Lexicon?}
    Aggregator -- Found --> MergeEntry[Merge Senses & Parts of Speech]
    Aggregator -- Not Found --> InsertEntry[Create New LexicalEntry]
    MergeEntry --> InMemLexicon[In-Memory Indexed Lexicon]
    InsertEntry --> InMemLexicon
    InMemLexicon --> WordBridge[to_word -> Rich Word Instance with Character IDs]
    InMemLexicon --> JsonExport[Persist to veda_lexicon_v0.1.json]
```

### Key Architectural Invariants
1. **$O(1)$ Stream Memory**: The extractor never loads entire multi-gigabyte files (e.g. the 25 GB `raw-wiktextract-data.jsonl`) into memory. Files are processed line-by-line.
2. **Deterministic Canonical Identity**: Every entry is normalized using the canonical lowercase rule of `WordAnalyzer.normalize_word()`.
3. **Single Source of Truth**: Character decomposition is derived strictly from the canonical [CharacterRegistry](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/characters/registry.py#L59).
4. **Lossless Multi-POS Aggregation**: Words that exist across multiple parts of speech (e.g., `free` as adjective, adverb, verb, noun, numeral) are aggregated into a single unified record without dropping definitions.

---

## 3. Core Data Structures

### `LexicalSense` ([schemas.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/schemas.py#L18))
Represents a specific meaning of a word under a given part of speech:
- `pos`: Part of speech (`"noun"`, `"verb"`, `"adj"`, etc.).
- `glosses`: List of definition strings.
- `tags`: Usage labels (`["transitive"]`, `["colloquial"]`, `["archaic"]`).
- `examples`: Real-world example sentences and quotations.
- `categories`: Subject taxonomy tags (`["Lexicography"]`, `["Computing"]`).

### `LexicalEntry` ([schemas.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/schemas.py#L46))
Consolidated dictionary entry for a word:
- `word`: Original surface spelling (e.g. `"dictionary"`).
- `normalized`: Canonical lowercase key (e.g. `"dictionary"`).
- `parts_of_speech`: Complete list of parts of speech (`["noun", "verb"]`).
- `primary_pos`: Primary grammatical category (`"noun"`).
- `definitions`: Flat deduplicated list of all definitions.
- `definitions_by_pos`: Dictionary mapping each POS to its specific definitions.
- `senses`: Structured list of `LexicalSense` instances.
- `pronunciations`: IPA transcriptions (e.g. `["/ˈdɪk.ʃə.nə.ɹi/"]`).
- `forms`: Inflected forms (e.g. `["dictionaries"]`, `["freer"]`).
- `synonyms`: Associated synonyms.
- `antonyms`: Associated antonyms.
- `etymology`: Historical origins if present.

### `Lexicon` ([lexicon.py](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/lexicon/lexicon.py#L18))
In-memory dictionary repository providing:
- $O(1)$ key lookup: `lexicon["free"]`, `"free" in lexicon`, `lexicon.get("free")`.
- POS filtering: `lexicon.filter_by_pos("verb")`.
- Word generation: `lexicon.to_word("free") -> Word`.
- Serialization: `lexicon.save_to_json()` and `Lexicon.from_json_file()`.

---

## 4. Integration with Word Foundation

The Lexicon layer connects directly to Phase 2:

```python
from foundation.lexicon import WiktionaryExtractor

extractor = WiktionaryExtractor()
lexicon = extractor.extract_lexicon("veda_sample.jsonl")

# Retrieve rich Word object
word = lexicon.to_word("free")

# Word properties (Phase 2)
assert word.normalized == "free"
assert word.characters == ['f', 'r', 'e', 'e']
assert word.character_ids == [72, 84, 71, 71]

# Lexical properties (Phase 3)
assert word.lexical.part_of_speech == "adj"
assert word.lexical.parts_of_speech == ["adj", "adv", "verb", "noun", "num"]
assert len(word.lexical.definitions) >= 30
```

Furthermore, [WordAnalyzer](file:///c:/Users/karnik%20YOGA/OneDrive/Desktop/veda/foundation/words/analyzer.py#L18) now supports attaching a Lexicon:
- `analyzer.is_word_candidate("blork") -> True` (valid morphology)
- `analyzer.is_dictionary_word("blork") -> False` (not in lexicon)
- `analyzer.is_dictionary_word("free") -> True` (in lexicon)

---

## 5. Sample Dataset Verification

Extracted and verified against `veda_sample.jsonl`:
- **Total Lines Read**: 20
- **English Records Parsed**: 13
- **Foreign Records Filtered**: 7 (Galician, Low German, Latin, Portuguese, Scots, German)
- **Valid Candidates Accepted**: 13 (0 invalid candidates)
- **Unique Words Aggregated**: 6 (`dictionary`, `encyclopaedia`, `encyclopedia`, `free`, `portmanteau`, `thesaurus`)
- **Total Definitions**: 63 (average 10.5 definitions per word)
- **Extraction Speed**: ~2,000 lines/second

---

## 6. How to Run

```bash
# Run automated showcase:
python scripts/lexicon_demo.py

# Query specific word:
python scripts/lexicon_demo.py --word "free"

# Interactive lookup REPL:
python scripts/lexicon_demo.py --interactive

# Run unit tests:
pytest tests/test_lexicon.py -v
```
