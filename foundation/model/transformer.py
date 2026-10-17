"""
VEDA Causal Language Model Architecture (v0.1 Foundation)

A decoder-only causal Transformer built from first principles with PyTorch.
Designed for deterministic, isolated, from-scratch neural experiments
without pretrained weights or external model dependencies.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class TransformerConfig:
    """Configuration hyperparameters for VEDA CausalLM."""

    vocab_size: int = 117
    d_model: int = 64
    n_heads: int = 4
    n_layers: int = 2
    d_ff: int = 256
    max_seq_len: int = 64
    dropout: float = 0.0
    bias: bool = True
    pad_token_id: int = 0

    def __post_init__(self) -> None:
        if self.d_model % self.n_heads != 0:
            raise ValueError(
                f"d_model ({self.d_model}) must be divisible by n_heads ({self.n_heads})"
            )
        if self.vocab_size <= 0:
            raise ValueError(f"vocab_size must be positive, got {self.vocab_size}")
        if self.max_seq_len <= 0:
            raise ValueError(f"max_seq_len must be positive, got {self.max_seq_len}")

    def to_dict(self) -> dict[str, Any]:
        """Converts config to primitive dictionary for safe serialization."""
        return {
            "vocab_size": self.vocab_size,
            "d_model": self.d_model,
            "n_heads": self.n_heads,
            "n_layers": self.n_layers,
            "d_ff": self.d_ff,
            "max_seq_len": self.max_seq_len,
            "dropout": self.dropout,
            "bias": self.bias,
            "pad_token_id": self.pad_token_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransformerConfig:
        """Constructs TransformerConfig from primitive dictionary."""
        return cls(**data)


class CausalSelfAttention(nn.Module):
    """Multi-head causal self-attention with lower-triangular causal mask."""

    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.d_model = config.d_model
        self.n_heads = config.n_heads
        self.head_dim = config.d_model // config.n_heads

        self.qkv_proj = nn.Linear(config.d_model, 3 * config.d_model, bias=config.bias)
        self.out_proj = nn.Linear(config.d_model, config.d_model, bias=config.bias)
        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

        # Causal mask buffer: upper triangle is masked out (value 0)
        mask = torch.tril(torch.ones(config.max_seq_len, config.max_seq_len)).view(
            1, 1, config.max_seq_len, config.max_seq_len
        )
        self.register_buffer("mask", mask)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.size()

        # Project and separate Q, K, V: shape (B, T, 3 * C) -> 3 x (B, T, C)
        qkv = self.qkv_proj(x)
        q, k, v = qkv.split(self.d_model, dim=2)

        # Reshape to (B, n_heads, T, head_dim)
        q = q.view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention
        scale = 1.0 / math.sqrt(self.head_dim)
        scores = torch.matmul(q, k.transpose(-2, -1)) * scale

        # Apply causal mask: mask positions where self.mask is 0
        causal_mask = self.mask[:, :, :seq_len, :seq_len]
        scores = scores.masked_fill(causal_mask == 0, float("-inf"))

        weights = F.softmax(scores, dim=-1)
        weights = self.attn_dropout(weights)

        # Context output: (B, n_heads, T, head_dim) -> (B, T, C)
        out = torch.matmul(weights, v)
        out = out.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)

        return self.resid_dropout(self.out_proj(out))


class MLP(nn.Module):
    """Position-wise feed-forward network with GELU activation."""

    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.fc1 = nn.Linear(config.d_model, config.d_ff, bias=config.bias)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(config.d_ff, config.d_model, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.act(x)
        x = self.fc2(x)
        return self.dropout(x)


class TransformerBlock(nn.Module):
    """Pre-LayerNorm Transformer decoder block."""

    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(config.d_model)
        self.attn = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.d_model)
        self.mlp = MLP(config)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Pre-LN residual stream
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class CausalLM(nn.Module):
    """
    VEDA Causal Language Model.
    Decoder-only architecture with learned token and position embeddings.
    """

    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.config = config

        self.wte = nn.Embedding(
            config.vocab_size, config.d_model, padding_idx=config.pad_token_id
        )
        self.wpe = nn.Embedding(config.max_seq_len, config.d_model)
        self.drop = nn.Dropout(config.dropout)

        self.blocks = nn.ModuleList(
            [TransformerBlock(config) for _ in range(config.n_layers)]
        )
        self.ln_f = nn.LayerNorm(config.d_model)
        self.lm_head = nn.Linear(config.d_model, config.vocab_size, bias=False)

        # Initialize all parameters from scratch with calibrated normal distributions
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        """Initialize weights from scratch using normal distribution (std=0.02)."""
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass of the causal language model.

        Args:
            input_ids: LongTensor of shape (batch_size, seq_len)
            targets: Optional LongTensor of shape (batch_size, seq_len) for loss computation

        Returns:
            (logits, loss) where logits has shape (batch_size, seq_len, vocab_size)
            and loss is scalar cross-entropy or None if targets not provided.
        """
        batch_size, seq_len = input_ids.size()
        if seq_len > self.config.max_seq_len:
            raise ValueError(
                f"Sequence length {seq_len} exceeds maximum sequence length {self.config.max_seq_len}"
            )

        device = input_ids.device
        positions = torch.arange(0, seq_len, dtype=torch.long, device=device).unsqueeze(0)

        # Embed tokens and positions
        tok_emb = self.wte(input_ids)
        pos_emb = self.wpe(positions)
        x = self.drop(tok_emb + pos_emb)

        # Pass through sequential decoder blocks
        for block in self.blocks:
            x = block(x)

        # Final LayerNorm and projection to vocabulary logits
        x = self.ln_f(x)
        logits = self.lm_head(x)

        loss: Optional[torch.Tensor] = None
        if targets is not None:
            # Shifted cross-entropy: compute loss ignoring padding tokens
            loss = F.cross_entropy(
                logits.view(-1, self.config.vocab_size),
                targets.view(-1),
                ignore_index=self.config.pad_token_id,
            )

        return logits, loss

    def count_parameters(self, trainable_only: bool = True) -> int:
        """Returns total count of parameters in the model."""
        if trainable_only:
            return sum(p.numel() for p in self.parameters() if p.requires_grad)
        return sum(p.numel() for p in self.parameters())

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Saves model configuration and state_dict securely using atomic file write."""
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = p.with_name(f"{p.name}.tmp_{os.getpid()}_{id(self)}.pt")
        payload = {
            "config": self.config.to_dict(),
            "state_dict": self.state_dict(),
            "veda_model_version": "0.1.0",
        }
        try:
            torch.save(payload, tmp_path)
            tmp_path.replace(p)
        except Exception:
            if tmp_path.is_file():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    @classmethod
    def load_checkpoint(cls, path: Union[str, Path], map_location=None) -> CausalLM:
        """Loads model from checkpoint securely with weights_only=True."""
        p = Path(path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {p}")
        payload = torch.load(p, map_location=map_location, weights_only=True)
        if not isinstance(payload, dict) or "config" not in payload or "state_dict" not in payload:
            raise ValueError(f"Malformed checkpoint format in {p}")
        config = TransformerConfig.from_dict(payload["config"])
        model = cls(config)
        model.load_state_dict(payload["state_dict"])
        return model
