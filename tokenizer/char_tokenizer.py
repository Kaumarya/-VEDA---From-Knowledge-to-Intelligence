"""
VEDA Character Tokenizer v0.1 (Phase 1 — English Character Foundation)

This module implements the foundational character-level tokenizer for VEDA,
built directly from first principles using the VEDA Character Registry.

Architecture:
    Text (str)
       ↓
    Characters (List[str])
       ↓ (Vocabulary Mapping)
    Token IDs (List[int])
       ↓ (Reverse Mapping)
    Reconstructed Text (str)

Vocabulary Ordering:
    - IDs 0..3: Reserved for Special Tokens (<PAD>, <UNK>, <BOS>, <EOS>)
    - IDs 4..116: Assigned to Registered English Characters (offset by len(special_tokens))
    Total Vocabulary Size: 117
"""

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Union

# Ensure project root is in sys.path when invoked directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from foundation.characters.registry import CharacterRegistry, SpecialTokenEntry


class CharacterTokenizer:
    """
    Character-level tokenizer for the VEDA language model (v0.1).

    Maps English characters to deterministic token IDs using the VEDA Character Registry.
    Guarantees exact round-trip reconstruction for all characters in the registry:
        decode(encode(text)) == text
    """

    DEFAULT_REGISTRY_FILENAMES = (
        "veda_characters_v0.1.json",
        "data/characters/veda_characters_v0.1.json",
    )

    def __init__(
        self,
        registry: Optional[Union[CharacterRegistry, str, Path]] = None,
    ) -> None:
        """
        Initializes the CharacterTokenizer from a CharacterRegistry instance or file path.

        If registry is None, searches canonical default locations.
        """
        if registry is None:
            self._registry = self._find_and_load_default_registry()
        elif isinstance(registry, (str, Path)):
            self._registry = CharacterRegistry.from_json_file(registry)
        elif isinstance(registry, CharacterRegistry):
            self._registry = registry
        else:
            raise TypeError(
                f"Expected CharacterRegistry, str, Path, or None; got {type(registry).__name__}"
            )

        # Build vocabulary mappings
        self._token_to_id: Dict[str, int] = {}
        self._id_to_token: Dict[int, str] = {}
        self._special_token_set: Set[str] = set()
        self._special_id_set: Set[int] = set()

        self._build_vocabulary()

    def _find_and_load_default_registry(self) -> CharacterRegistry:
        """Finds the default character registry JSON file relative to workspace or module."""
        # 1. Search in current working directory / workspace
        cwd = Path.cwd()
        for rel in self.DEFAULT_REGISTRY_FILENAMES:
            candidate = cwd / rel
            if candidate.is_file():
                return CharacterRegistry.from_json_file(candidate)

        # 2. Search relative to this file's directory tree
        pkg_root = Path(__file__).resolve().parent.parent
        for rel in self.DEFAULT_REGISTRY_FILENAMES:
            candidate = pkg_root / rel
            if candidate.is_file():
                return CharacterRegistry.from_json_file(candidate)

        raise FileNotFoundError(
            f"Could not locate character registry. Checked: {self.DEFAULT_REGISTRY_FILENAMES} "
            f"in cwd ({cwd}) and package root ({pkg_root})."
        )

    def _build_vocabulary(self) -> None:
        """
        Constructs the unified vocabulary mapping from the registry.

        Layout:
        1. Special tokens take indices 0 .. S-1 (where S = len(special_tokens))
        2. Registered characters take indices S .. S + C - 1 (where C = len(characters))
        """
        # Assign special tokens
        for st in self._registry.special_tokens:
            self._token_to_id[st.token] = st.id
            self._id_to_token[st.id] = st.token
            self._special_token_set.add(st.token)
            self._special_id_set.add(st.id)

        # Assign character tokens, contiguous right after special tokens
        special_offset = self._registry.special_token_count
        for char_entry in self._registry.characters:
            token_id = special_offset + char_entry.id
            token_str = char_entry.character

            if token_str in self._token_to_id:
                raise ValueError(
                    f"Token collision detected: {repr(token_str)} already in vocabulary"
                )

            self._token_to_id[token_str] = token_id
            self._id_to_token[token_id] = token_str

        # Canonical special token IDs
        self._pad_token = "<PAD>"
        self._unk_token = "<UNK>"
        self._bos_token = "<BOS>"
        self._eos_token = "<EOS>"

        self._pad_token_id = self._token_to_id[self._pad_token]
        self._unk_token_id = self._token_to_id[self._unk_token]
        self._bos_token_id = self._token_to_id[self._bos_token]
        self._eos_token_id = self._token_to_id[self._eos_token]

    # Properties
    @property
    def registry(self) -> CharacterRegistry:
        """Returns the underlying CharacterRegistry."""
        return self._registry

    @property
    def vocab_size(self) -> int:
        """Total size of the active tokenizer vocabulary."""
        return len(self._token_to_id)

    @property
    def pad_token(self) -> str:
        return self._pad_token

    @property
    def pad_token_id(self) -> int:
        return self._pad_token_id

    @property
    def unk_token(self) -> str:
        return self._unk_token

    @property
    def unk_token_id(self) -> int:
        return self._unk_token_id

    @property
    def bos_token(self) -> str:
        return self._bos_token

    @property
    def bos_token_id(self) -> int:
        return self._bos_token_id

    @property
    def eos_token(self) -> str:
        return self._eos_token

    @property
    def eos_token_id(self) -> int:
        return self._eos_token_id

    @property
    def special_tokens(self) -> List[str]:
        """Returns a list of registered special tokens."""
        return [st.token for st in self._registry.special_tokens]

    def get_vocab(self) -> Dict[str, int]:
        """Returns a copy of the token-to-ID vocabulary dictionary."""
        return dict(self._token_to_id)

    def token_to_id(self, token: str) -> Optional[int]:
        """Looks up the token ID for a given string token."""
        return self._token_to_id.get(token)

    def id_to_token(self, token_id: int) -> Optional[str]:
        """Looks up the token string for a given integer token ID."""
        return self._id_to_token.get(token_id)

    def is_special_token(self, token: str) -> bool:
        """Checks if a string is a recognized special token."""
        return token in self._special_token_set

    def is_special_id(self, token_id: int) -> bool:
        """Checks if an integer ID is a recognized special token ID."""
        return token_id in self._special_id_set

    # Core Methods: encode and decode
    def encode(
        self,
        text: str,
        add_special_tokens: bool = False,
    ) -> List[int]:
        """
        Encodes an input text string into a list of integer token IDs.

        Args:
            text: The input English string to tokenize.
            add_special_tokens: If True, prepends <BOS> and appends <EOS>.

        Returns:
            A list of integer token IDs. Unknown characters map to <UNK> (id 1).
        """
        if not isinstance(text, str):
            raise TypeError(f"encode() expects string input, got {type(text).__name__}")

        token_ids: List[int] = []

        if add_special_tokens:
            token_ids.append(self._bos_token_id)

        for char in text:
            token_id = self._token_to_id.get(char, self._unk_token_id)
            token_ids.append(token_id)

        if add_special_tokens:
            token_ids.append(self._eos_token_id)

        return token_ids

    def decode(
        self,
        token_ids: Sequence[int],
        skip_special_tokens: bool = False,
        errors: str = "replace",
    ) -> str:
        """
        Decodes a sequence of integer token IDs back into a text string.

        Args:
            token_ids: Sequence of integer token IDs.
            skip_special_tokens: If True, omits all special tokens (<PAD>, <UNK>, <BOS>, <EOS>).
            errors: Error handling mode for unrecognized token IDs:
                    - 'replace': Replaces invalid IDs with the <UNK> string.
                    - 'strict': Raises ValueError on invalid IDs.
                    - 'ignore': Skips invalid IDs silently.

        Returns:
            The decoded text string.
        """
        if not isinstance(token_ids, Sequence):
            token_ids = list(token_ids)

        if errors not in ("replace", "strict", "ignore"):
            raise ValueError(f"Unknown errors mode: {errors!r}. Must be 'replace', 'strict', or 'ignore'.")

        result: List[str] = []

        for tid in token_ids:
            if not isinstance(tid, int):
                raise TypeError(f"Token IDs must be integers, got {type(tid).__name__} ({tid!r})")

            token_str = self._id_to_token.get(tid)

            if token_str is None:
                if errors == "strict":
                    raise ValueError(f"Token ID {tid} is not in tokenizer vocabulary (vocab_size={self.vocab_size})")
                elif errors == "ignore":
                    continue
                else:  # 'replace'
                    token_str = self._unk_token

            if skip_special_tokens and tid in self._special_id_set:
                continue

            result.append(token_str)

        return "".join(result)

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenizes text into a list of individual token strings (characters or <UNK>).
        Useful for inspecting token boundaries and representations.
        """
        if not isinstance(text, str):
            raise TypeError(f"tokenize() expects string input, got {type(text).__name__}")

        tokens: List[str] = []
        for char in text:
            if char in self._token_to_id:
                tokens.append(char)
            else:
                tokens.append(self._unk_token)
        return tokens

    def __repr__(self) -> str:
        return (
            f"CharacterTokenizer(vocab_size={self.vocab_size}, "
            f"special_tokens={len(self._special_id_set)}, "
            f"characters={self._registry.character_count})"
        )


if __name__ == "__main__":
    import sys

    tokenizer = CharacterTokenizer()
    sample = sys.argv[1] if len(sys.argv) > 1 else "Hello VEDA!"
    encoded = tokenizer.encode(sample)
    decoded = tokenizer.decode(encoded)
    print(f"Input:    {sample!r}")
    print(f"Encoded:  {encoded}")
    print(f"Decoded:  {decoded!r}")
    print(f"Match:    {sample == decoded}")

