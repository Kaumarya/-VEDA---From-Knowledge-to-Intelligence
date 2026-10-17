"""
VEDA Controlled Dataset Utilities & Train/Test Leakage Detection

Provides dataset batching from CharacterTokenizer and rigorous train/test
leakage detection to ensure clean evaluation partitioning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple
import torch

from tokenizer.char_tokenizer import CharacterTokenizer


class ControlledLanguageDataset:
    """
    Dataset wrapper converting raw string texts into autoregressive training pairs.
    Each example yields:
        input_ids: token IDs 0 .. T-2 (padded to max_seq_len)
        targets: token IDs 1 .. T-1 (padded to max_seq_len)
    """

    def __init__(
        self,
        texts: Sequence[str],
        tokenizer: CharacterTokenizer,
        max_seq_len: int = 64,
        add_special_tokens: bool = True,
    ) -> None:
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len
        self.add_special_tokens = add_special_tokens
        self.examples: List[Tuple[torch.Tensor, torch.Tensor]] = []

        for text in texts:
            tokens = tokenizer.encode(text, add_special_tokens=add_special_tokens)
            if len(tokens) < 2:
                continue

            # Truncate to max_seq_len + 1 so input and target both have length <= max_seq_len
            tokens = tokens[: self.max_seq_len + 1]

            inp_tokens = tokens[:-1]
            tgt_tokens = tokens[1:]

            # Pad up to max_seq_len
            pad_id = tokenizer.pad_token_id
            inp_pad_len = max_seq_len - len(inp_tokens)
            tgt_pad_len = max_seq_len - len(tgt_tokens)

            inp_padded = inp_tokens + [pad_id] * inp_pad_len
            tgt_padded = tgt_tokens + [pad_id] * tgt_pad_len

            self.examples.append(
                (
                    torch.tensor(inp_padded, dtype=torch.long),
                    torch.tensor(tgt_padded, dtype=torch.long),
                )
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.examples[idx]

    def get_batch(self) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns all examples stacked as a single batch (B, T)."""
        if not self.examples:
            raise ValueError("Dataset contains zero valid examples.")
        inputs = torch.stack([ex[0] for ex in self.examples], dim=0)
        targets = torch.stack([ex[1] for ex in self.examples], dim=0)
        return inputs, targets


def detect_train_test_leakage(
    train_texts: Sequence[str],
    test_texts: Sequence[str],
    ngram_size: int = 8,
    overlap_threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Rigorously detects train/test contamination through:
    1. Exact string matches (case-normalized, whitespace-normalized)
    2. Character n-gram Jaccard similarity exceeding overlap_threshold

    Returns:
        Dictionary with leakage detection status and diagnostic details.
    """
    exact_matches: List[Dict[str, Any]] = []
    high_overlap_pairs: List[Dict[str, Any]] = []

    def normalize(s: str) -> str:
        return " ".join(s.strip().lower().split())

    def get_ngrams(s: str, n: int) -> set[str]:
        cleaned = normalize(s)
        if len(cleaned) < n:
            return {cleaned}
        return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}

    norm_train = [normalize(t) for t in train_texts]
    train_ngrams = [get_ngrams(t, ngram_size) for t in train_texts]

    for test_idx, raw_test in enumerate(test_texts):
        norm_test = normalize(raw_test)
        test_ng = get_ngrams(raw_test, ngram_size)

        for train_idx, tr_str in enumerate(norm_train):
            # Check 1: Exact match
            if norm_test == tr_str:
                exact_matches.append(
                    {
                        "train_idx": train_idx,
                        "test_idx": test_idx,
                        "train_text": train_texts[train_idx],
                        "test_text": raw_test,
                        "match_type": "EXACT",
                    }
                )
                continue

            # Check 2: Character n-gram Jaccard
            tr_ng = train_ngrams[train_idx]
            intersection = len(test_ng & tr_ng)
            union = len(test_ng | tr_ng)
            jaccard = intersection / union if union > 0 else 0.0

            if jaccard >= overlap_threshold:
                high_overlap_pairs.append(
                    {
                        "train_idx": train_idx,
                        "test_idx": test_idx,
                        "train_text": train_texts[train_idx],
                        "test_text": raw_test,
                        "jaccard_overlap": round(jaccard, 4),
                        "match_type": "HIGH_NGRAM_OVERLAP",
                    }
                )

    has_leakage = len(exact_matches) > 0 or len(high_overlap_pairs) > 0

    return {
        "leakage_detected": has_leakage,
        "train_count": len(train_texts),
        "test_count": len(test_texts),
        "exact_match_count": len(exact_matches),
        "high_overlap_count": len(high_overlap_pairs),
        "exact_matches": exact_matches,
        "high_overlap_pairs": high_overlap_pairs,
    }
