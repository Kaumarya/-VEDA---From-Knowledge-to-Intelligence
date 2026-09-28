# VEDA Character Tokenizer v0.1
*Component: Tokenizer (Phase 1 — English Character Foundation)*

---

## 1. WHAT IT IS
The **VEDA Character Tokenizer v0.1** is a foundational, deterministic character-level tokenizer for the VEDA language model. It maps raw text strings into discrete integer token IDs and reconstructs strings back from sequences of token IDs without relying on external pretrained tokenizers, byte-pair encoding (BPE) libraries, or third-party APIs.

It operates over a strictly governed vocabulary derived from `veda_characters_v0.1.json`, comprising:
- **4 Special Control Tokens**: `<PAD>`, `<UNK>`, `<BOS>`, `<EOS>`
- **113 English-Oriented Characters**: ASCII control codes (`\t`, `\n`), standard printable ASCII (alphabets, digits, spaces, punctuation, symbols), and select high-frequency English typographical characters (curly quotes, dashes, ellipsis, currency symbols).
- **Total Vocabulary Size**: Exactly **117 tokens**.

---

## 2. WHY IT EXISTS
Language models fundamentally operate on numerical representations (vectors and discrete token indices), not raw Unicode character glyphs. Building a language model from first principles requires full ownership of the tokenization abstraction:

1. **First-Principles Understanding**: Before introducing complex subword algorithms (BPE, WordPiece, Unigram), character tokenization makes the mapping between symbolic text and integer representations completely transparent, deterministic, and verifiable.
2. **Deterministic Round-Trip Guarantee**: A character tokenizer guarantees lossless reconstruction (`decode(encode(text)) == text`) for all registered characters, removing token boundary ambiguities.
3. **Controlled Scope**: In accordance with VEDA Phase 1 requirements, restricting initial tokenization to English characters establishes a bounded domain before scaling to multi-lingual vocabularies or subword merging.
4. **Architectural Separation**: Separates the character registry (data schema) from tokenization mechanics (encoder/decoder logic), laying the groundwork for downstream embedding and causal attention layers.

---

## 3. HOW IT WORKS

### 3.1 Vocabulary Architecture and Mapping
The vocabulary space $V$ is partitioned into two disjoint index ranges:

$$\text{Vocab} = \mathcal{S} \cup \mathcal{C}$$

Where:
- $\mathcal{S} = \{ \text{<PAD>}: 0,\ \text{<UNK>}: 1,\ \text{<BOS>}: 2,\ \text{<EOS>}: 3 \}$
- $\mathcal{C}$ consists of the 113 characters from the VEDA Character Registry.

To eliminate any ID collision between special tokens and characters (both numbered from 0 in registry lists), character token IDs are offset by $|\mathcal{S}| = 4$:

$$\text{TokenID}(c) = |\mathcal{S}| + \text{RegistryID}(c) \quad \text{for } c \in \mathcal{C}$$

$$\text{TokenID}(s) = \text{RegistryID}(s) \quad \text{for } s \in \mathcal{S}$$

| Token Type | Range | Examples |
|---|---|---|
| Special Control Tokens | `0 .. 3` | `<PAD>` (0), `<UNK>` (1), `<BOS>` (2), `<EOS>` (3) |
| Whitespace & Control | `4 .. 7` | `\t` (4), `\n` (5), `' '` (6), `!` (7) |
| Standard ASCII | `8 .. 100` | `"`, `#`, `0..9`, `A..Z`, `a..z`, symbols |
| Typographical & Currency | `101 .. 116` | `‘`, `’`, `“`, `”`, `–`, `—`, `…`, `\xa0`, `©`, `®`, `°`, `·`, `•`, `£`, `€`, `¥` |
| **Total Vocab Size** | **117** | Indices strictly continuous from `0` to `116` |

### 3.2 Encoding Flow
Given an input string $T = (c_1, c_2, \dots, c_N)$:
1. If `add_special_tokens=True`, prepend $\text{TokenID}(\text{<BOS>}) = 2$.
2. For each character $c_i$:
   - If $c_i \in \text{Vocab}$, map to $\text{TokenID}(c_i)$.
   - If $c_i \notin \text{Vocab}$, map to $\text{TokenID}(\text{<UNK>}) = 1$.
3. If `add_special_tokens=True`, append $\text{TokenID}(\text{<EOS>}) = 3$.
4. Return the resulting integer list.

### 3.3 Decoding Flow
Given a sequence of token IDs $(t_1, t_2, \dots, t_M)$:
1. For each token ID $t_i$:
   - If $t_i \in \text{SpecialTokens}$ and `skip_special_tokens=True`, omit.
   - If $t_i \in \text{SpecialTokens}$ and `skip_special_tokens=False`, output special token string (e.g. `"<UNK>"`).
   - If $t_i \in \text{Characters}$, output the character string.
   - If $t_i \notin \text{Vocab}$, handle according to `errors` policy (`"replace"` -> `"<UNK>"`, `"strict"` -> raise `ValueError`, `"ignore"` -> drop).
2. Concatenate and return the reconstructed string.

---

## 4. HOW WE IMPLEMENTED IT

The implementation is located across two modular packages:

### `foundation/characters/`
- [CharacterEntry](file:///foundation/characters/registry.py): Immutable dataclass holding character glyph, Unicode codepoint (`U+XXXX`), Unicode name, category, linguistic type (`letter`, `punctuation`, `number`, `symbol`, `whitespace`), case (`uppercase`, `lowercase`, `None`), and normalization.
- [SpecialTokenEntry](file:///foundation/characters/registry.py): Immutable dataclass holding ID, token representation, and architectural purpose.
- [CharacterRegistry](file:///foundation/characters/registry.py): Validates uniqueness of characters, verifies contiguous numbering, checks codepoint parity against Python's `ord()`, and provides $O(1)$ bidirectional lookup.

### `tokenizer/`
- [CharacterTokenizer](file:///tokenizer/char_tokenizer.py):
  - Automatically locates the canonical registry file (`veda_characters_v0.1.json`).
  - Constructs continuous non-overlapping vocabulary mappings.
  - Implements `encode()`, `decode()`, `tokenize()`, `get_vocab()`.
  - Exposes standard model properties: `vocab_size` (117), `pad_token_id` (0), `unk_token_id` (1), `bos_token_id` (2), `eos_token_id` (3).

---

## 5. HOW WE TESTED IT

The test suite in [tests/test_char_tokenizer.py](file:///tests/test_char_tokenizer.py) and [tests/test_character_registry.py](file:///tests/test_character_registry.py) executes 24 automated unit tests covering all 10 required prompt specifications:

1. **Normal Sentence Encoding**: Verified encoding of `"The quick brown fox jumps over the lazy dog."` into valid, bounded integers.
2. **Decoding Encoded Result**: Verified decoding of token ID sequences back into original English text.
3. **Round-Trip Equality**: Verified `decode(encode(text)) == text` across arbitrary English sentences.
4. **Spaces**: Tested single, multiple, leading, trailing, internal spaces, and mixed whitespace.
5. **Punctuation**: Tested ASCII symbols (`!`, `?`, quotes, brackets) and extended typography (`“`, `”`, `–`, `—`, `…`, currency).
6. **Newline**: Tested single newlines, multiple consecutive newlines, and multiline documents.
7. **Unknown Characters**: Tested handling of out-of-vocabulary characters (e.g. emojis `🤖`, `🚀`), verifying they map to `<UNK>` (ID 1) and decode appropriately with and without `skip_special_tokens`.
8. **Empty Strings**: Verified `encode("") == []` and `decode([]) == ""`.
9. **Repeated Characters**: Tested single-character runs (`aaaaaaa`, `ZZZZZZZZZZ`, `..........`) and multi-run repeated character sequences (`!!!!!?????`, `aaabbbccc`).
10. **Mixed Uppercase/Lowercase**: Tested preservation of case distinction (`"VeDa"` vs `"veda"`) ensuring distinct token IDs for upper and lower case letters.

### Additional Verifications:
- Vocabulary size is exactly 117 with strictly contiguous IDs (`0..116`).
- Sequence boundaries (`add_special_tokens=True`) correctly prepend `<BOS>` and append `<EOS>`.
- Error handling modes (`strict`, `replace`, `ignore`) for invalid token IDs.
- Type enforcement (rejecting non-strings and non-integer sequences).

---

## 6. WHAT LIMITATIONS IT HAS
1. **Sequence Length**: Because each character is an individual token, the sequence length in tokens equals the string length in characters ($N_\text{tokens} = N_\text{chars}$). For a given context window (e.g. 512 tokens), this limits the context to ~512 characters (~100 words), compared to subword tokenizers which average ~4 characters per token.
2. **English Scope**: Characters outside the 113 English registry entries (e.g., Devanagari, Gurmukhi, accented non-English Latin glyphs) map to `<UNK>`. This is an intentional constraint for Phase 1.
3. **Efficiency**: For larger language models, subword tokenization (BPE) will eventually be implemented in Phase 2 to increase information density per token.

---

## 7. WHAT COMES NEXT
1. **Phase 1 Normalization Subsystem**: Character-level normalization rules (canonical Unicode normalization NFC/NFKD, whitespace standardizers) under `foundation/normalization/`.
2. **Phase 2 Subword Tokenizer Exploration**: Byte-pair encoding (BPE) built from our own corpus and lexicon once the dictionary pipeline is validated.
3. **Phase 3 English Lexical Foundation**: Lexicon and dictionary ingestion pipeline utilizing `veda_sample.jsonl` (streaming without loading multi-gigabyte data into memory).
