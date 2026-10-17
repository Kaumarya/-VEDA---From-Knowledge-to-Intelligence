"""
Unit tests for VEDA Neural Foundation (Phase 4.3)

Tests:
1. Model configuration and initialization from random weights.
2. Causal masking integrity (no future token information leakage).
3. Forward pass, loss computation, backpropagation, and finite gradients.
4. Parameter update verification (weights change after optimizer step).
5. Loss decrease on a tiny training fixture (overfitting verification).
6. Checkpoint save, reload, and exact numerical reproduction.
7. Train/test data leakage detector.
"""

import tempfile
from pathlib import Path
import pytest
import torch
import torch.nn as nn
import torch.optim as optim

from foundation.model.transformer import CausalLM, TransformerConfig
from foundation.model.dataset import ControlledLanguageDataset, detect_train_test_leakage
from tokenizer.char_tokenizer import CharacterTokenizer


@pytest.fixture
def tokenizer() -> CharacterTokenizer:
    return CharacterTokenizer()


@pytest.fixture
def small_config() -> TransformerConfig:
    return TransformerConfig(
        vocab_size=117,
        d_model=32,
        n_heads=2,
        n_layers=2,
        d_ff=64,
        max_seq_len=32,
        dropout=0.0,
    )


def test_transformer_config_validation() -> None:
    # d_model must be divisible by n_heads
    with pytest.raises(ValueError, match="divisible by n_heads"):
        TransformerConfig(d_model=33, n_heads=4)

    # vocab_size must be positive
    with pytest.raises(ValueError, match="vocab_size must be positive"):
        TransformerConfig(vocab_size=0)

    # max_seq_len must be positive
    with pytest.raises(ValueError, match="max_seq_len must be positive"):
        TransformerConfig(max_seq_len=-5)


def test_model_initialization_random_weights(small_config: TransformerConfig) -> None:
    torch.manual_seed(42)
    model = CausalLM(small_config)

    # Verify model has expected parameter count
    total_params = model.count_parameters()
    assert total_params > 0

    # Verify no weights are uninitialized (NaN/Inf)
    for name, p in model.named_parameters():
        assert torch.isfinite(p).all(), f"Parameter {name} has non-finite values"
        if "weight" in name:
            assert not (p == 0.0).all(), f"Weight tensor {name} is unexpectedly all zeros"


def test_causal_masking_prevents_future_leakage(small_config: TransformerConfig) -> None:
    torch.manual_seed(123)
    model = CausalLM(small_config)
    model.eval()

    # Sequence A: [5, 10, 15, 20]
    # Sequence B: [5, 10, 15, 99] (differs only at position index 3)
    seq_a = torch.tensor([[5, 10, 15, 20]], dtype=torch.long)
    seq_b = torch.tensor([[5, 10, 15, 99]], dtype=torch.long)

    with torch.no_grad():
        logits_a, _ = model(seq_a)
        logits_b, _ = model(seq_b)

    # Causal property: Logits at positions 0, 1, 2 must be identical because token 3 is future
    assert torch.allclose(logits_a[:, :3, :], logits_b[:, :3, :], atol=1e-5), (
        "Causal violation: changing token at pos 3 affected logits at earlier positions"
    )

    # Logit at pos 3 can and should differ
    assert not torch.allclose(logits_a[:, 3, :], logits_b[:, 3, :], atol=1e-3)


def test_forward_backward_and_finite_gradients(small_config: TransformerConfig) -> None:
    torch.manual_seed(42)
    model = CausalLM(small_config)
    model.train()

    inputs = torch.randint(0, small_config.vocab_size, (2, 16))
    targets = torch.randint(0, small_config.vocab_size, (2, 16))

    logits, loss = model(inputs, targets=targets)
    assert loss is not None
    assert torch.isfinite(loss)
    assert loss.item() > 0.0

    loss.backward()

    # Verify all gradients exist and are finite
    for name, param in model.named_parameters():
        if param.requires_grad:
            assert param.grad is not None, f"Gradient missing for {name}"
            assert torch.isfinite(param.grad).all(), f"Gradient non-finite for {name}"


def test_parameter_update_changes_weights(small_config: TransformerConfig) -> None:
    torch.manual_seed(42)
    model = CausalLM(small_config)
    optimizer = optim.AdamW(model.parameters(), lr=1e-2)

    # Clone initial parameter values
    initial_params = [p.clone().detach() for p in model.parameters()]

    inputs = torch.randint(0, small_config.vocab_size, (2, 16))
    targets = torch.randint(0, small_config.vocab_size, (2, 16))

    optimizer.zero_grad()
    _, loss = model(inputs, targets=targets)
    assert loss is not None
    loss.backward()
    optimizer.step()

    # Confirm parameters actually changed
    changed = False
    for init_p, current_p in zip(initial_params, model.parameters()):
        if not torch.equal(init_p, current_p):
            changed = True
            break
    assert changed, "Parameters did not change after optimizer step"


def test_loss_decreases_on_tiny_fixture(
    tokenizer: CharacterTokenizer, small_config: TransformerConfig
) -> None:
    torch.manual_seed(999)
    model = CausalLM(small_config)
    model.train()
    optimizer = optim.AdamW(model.parameters(), lr=0.01)

    tiny_texts = ["the cat sat on the mat."]
    dataset = ControlledLanguageDataset(
        tiny_texts, tokenizer, max_seq_len=small_config.max_seq_len
    )
    inputs, targets = dataset.get_batch()

    losses = []
    for _ in range(25):
        optimizer.zero_grad()
        _, loss = model(inputs, targets=targets)
        assert loss is not None
        losses.append(loss.item())
        loss.backward()
        optimizer.step()

    initial_loss = losses[0]
    final_loss = losses[-1]

    # Verify that loss decreases significantly
    assert final_loss < initial_loss, f"Loss did not decrease: {initial_loss} -> {final_loss}"
    assert final_loss < initial_loss * 0.6, (
        f"Loss reduction was less than 40%: initial={initial_loss}, final={final_loss}"
    )


def test_checkpoint_save_and_reload(small_config: TransformerConfig) -> None:
    torch.manual_seed(42)
    model = CausalLM(small_config)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3)

    inputs = torch.randint(0, small_config.vocab_size, (1, 8))
    _, loss = model(inputs, targets=inputs)
    assert loss is not None
    loss.backward()
    optimizer.step()

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = Path(tmpdir) / "test_model_ckpt.pt"
        torch.save(
            {
                "config": small_config.to_dict(),
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
            },
            ckpt_path,
        )

        assert ckpt_path.is_file()

        # Load safely into a fresh model with weights_only=True
        reloaded_ckpt = torch.load(ckpt_path, weights_only=True)
        reloaded_model = CausalLM(TransformerConfig.from_dict(reloaded_ckpt["config"]))
        reloaded_model.load_state_dict(reloaded_ckpt["model_state"])

        # Compare outputs
        model.eval()
        reloaded_model.eval()
        test_inp = torch.randint(0, small_config.vocab_size, (1, 8))
        with torch.no_grad():
            orig_out, _ = model(test_inp)
            reloaded_out, _ = reloaded_model(test_inp)

        assert torch.allclose(orig_out, reloaded_out, atol=1e-6), (
            "Reloaded model outputs do not match original model"
        )


def test_train_test_leakage_detector() -> None:
    train_clean = [
        "The quick brown fox jumps over the lazy dog.",
        "A journey of a thousand miles begins with a single step.",
    ]
    test_clean = [
        "To be or not to be, that is the question.",
        "All that glitters is not gold.",
    ]

    clean_res = detect_train_test_leakage(train_clean, test_clean)
    assert not clean_res["leakage_detected"]
    assert clean_res["exact_match_count"] == 0
    assert clean_res["high_overlap_count"] == 0

    # Test exact duplicate leakage
    test_leaky_exact = [
        "The quick brown fox jumps over the lazy dog.",
        "Independent sentence.",
    ]
    leak_res = detect_train_test_leakage(train_clean, test_leaky_exact)
    assert leak_res["leakage_detected"]
    assert leak_res["exact_match_count"] == 1
    assert leak_res["exact_matches"][0]["match_type"] == "EXACT"

    # Test high character n-gram overlap leakage
    test_leaky_overlap = [
        "The quick brown fox jumps over the lazy dog!",  # near duplicate with punctuation change
    ]
    overlap_res = detect_train_test_leakage(train_clean, test_leaky_overlap)
    assert overlap_res["leakage_detected"]
    assert overlap_res["exact_match_count"] == 0
    assert overlap_res["high_overlap_count"] >= 1


def test_causal_lm_save_and_load_checkpoint_atomic(tmp_path: Path) -> None:
    """Verifies CausalLM save_checkpoint and load_checkpoint methods."""
    config = TransformerConfig(
        vocab_size=64,
        d_model=32,
        n_heads=2,
        n_layers=1,
        d_ff=64,
        max_seq_len=16,
    )
    model = CausalLM(config)
    ckpt_path = tmp_path / "model_ckpt.pt"

    # Save via helper
    model.save_checkpoint(ckpt_path)
    assert ckpt_path.is_file()

    # Load via helper
    loaded_model = CausalLM.load_checkpoint(ckpt_path)
    assert loaded_model.config == config

    inp = torch.randint(0, config.vocab_size, (1, 8))
    with torch.no_grad():
        out1, _ = model(inp)
        out2, _ = loaded_model(inp)
    assert torch.allclose(out1, out2, atol=1e-6)


def test_causal_lm_save_checkpoint_failure_cleanup(tmp_path: Path, monkeypatch) -> None:
    """Verifies that if serialization fails, temporary files are cleanly removed (DEF-4.7-06)."""
    config = TransformerConfig(vocab_size=32, d_model=16, n_heads=2, n_layers=1, d_ff=32, max_seq_len=8)
    model = CausalLM(config)
    ckpt_path = tmp_path / "fail_model.pt"

    def mock_save(*args, **kwargs):
        raise IOError("Simulated disk write failure")

    monkeypatch.setattr(torch, "save", mock_save)

    with pytest.raises(IOError, match="Simulated disk write failure"):
        model.save_checkpoint(ckpt_path)

    # Checkpoint should not exist and no temporary files should remain
    assert not ckpt_path.exists()
    temp_files = list(tmp_path.glob("*.pt*"))
    assert len(temp_files) == 0, f"Dangling temporary files found: {temp_files}"

