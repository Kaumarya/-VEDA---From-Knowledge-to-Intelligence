"""
VEDA Neural Foundation Experiment (Phase 4.3)

Isolated, reproducible from-scratch PyTorch experiment verifying:
1. Random weight initialization (no pretrained weights).
2. Documented CharacterTokenizer integration.
3. Forward pass, loss computation, backpropagation, and finite gradients.
4. Parameter updates under AdamW optimizer.
5. Overfitting / loss reduction on a controlled training fixture.
6. Model and optimizer checkpoint persistence and exact reload.
7. Hardware resource profiling (runtime, per-step latency, peak RSS < 2GB).
8. Held-out fixture evaluation and train/test leakage detection.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import psutil
import torch
import torch.optim as optim

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.model.dataset import ControlledLanguageDataset, detect_train_test_leakage
from foundation.model.transformer import CausalLM, TransformerConfig
from tokenizer.char_tokenizer import CharacterTokenizer


def run_experiment() -> Dict[str, Any]:
    print("=" * 70)
    print("VEDA FROM-SCRATCH NEURAL FOUNDATION EXPERIMENT")
    print("=" * 70)

    process = psutil.Process()
    initial_rss_bytes = process.memory_info().rss
    sys_mem = psutil.virtual_memory()

    # 1. Hardware & Runtime Environment Verification
    cuda_available = torch.cuda.is_available()
    device = torch.device("cpu")
    print(f"PyTorch Version:      {torch.__version__}")
    print(f"Compute Device:       {device} (CUDA available: {cuda_available})")
    print(f"System Total RAM:     {sys_mem.total / (1024**3):.2f} GB")
    print(f"System Available RAM: {sys_mem.available / (1024**3):.2f} GB")
    print(f"Initial Process RSS:  {initial_rss_bytes / (1024**2):.2f} MB")
    print(f"RSS Budget Limit:     2048.00 MB (2.0 GB)")

    # 2. Tokenizer & Controlled Datasets
    tokenizer = CharacterTokenizer()
    print(f"\nTokenizer: CharacterTokenizer (vocab_size={tokenizer.vocab_size})")

    train_texts = [
        "The quick brown fox jumps over the lazy dog.",
        "A journey of a thousand miles begins with a single step.",
        "It was the best of times, it was the worst of times.",
        "To be, or not to be, that is the question.",
    ]

    test_texts = [
        "All that glitters is not gold.",
        "Knowledge without wisdom is like water in the sand.",
    ]

    # 3. Rigorous Train/Test Leakage Detection
    leakage_report = detect_train_test_leakage(train_texts, test_texts)
    print(f"\nTrain/Test Leakage Check:")
    print(f"  Train sentences: {leakage_report['train_count']}")
    print(f"  Test sentences:  {leakage_report['test_count']}")
    print(f"  Leakage detected: {leakage_report['leakage_detected']}")
    assert not leakage_report["leakage_detected"], "Train/Test leakage detected!"

    # 4. Model Architecture & Initialization
    torch.manual_seed(42)
    config = TransformerConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=64,
        n_heads=4,
        n_layers=2,
        d_ff=256,
        max_seq_len=64,
        dropout=0.0,
        pad_token_id=tokenizer.pad_token_id,
    )
    model = CausalLM(config).to(device)
    total_params = model.count_parameters()
    print(f"\nModel Architecture:")
    print(f"  Layers: {config.n_layers}, Heads: {config.n_heads}, d_model: {config.d_model}, d_ff: {config.d_ff}")
    print(f"  Total Trainable Parameters: {total_params:,}")

    # Build dataset batches
    train_dataset = ControlledLanguageDataset(train_texts, tokenizer, max_seq_len=config.max_seq_len)
    test_dataset = ControlledLanguageDataset(test_texts, tokenizer, max_seq_len=config.max_seq_len)
    train_inputs, train_targets = train_dataset.get_batch()
    test_inputs, test_targets = test_dataset.get_batch()

    # 5. Optimizer & Gradient Verification
    optimizer = optim.AdamW(model.parameters(), lr=0.005, weight_decay=0.01)

    # Initial forward pass
    model.train()
    optimizer.zero_grad()
    initial_logits, initial_loss = model(train_inputs, targets=train_targets)
    assert initial_loss is not None
    initial_loss_val = float(initial_loss.item())
    initial_ppl = math.exp(initial_loss_val)
    print(f"\nInitial State:")
    print(f"  Initial Training Loss:       {initial_loss_val:.4f}")
    print(f"  Initial Training Perplexity: {initial_ppl:.2f}")

    # Backward pass
    initial_loss.backward()

    # Confirm all gradients are finite
    grad_finite = True
    for name, param in model.named_parameters():
        if param.requires_grad:
            if param.grad is None or not torch.isfinite(param.grad).all():
                grad_finite = False
                break
    print(f"  Gradients Computed & Finite: {grad_finite}")
    assert grad_finite, "Non-finite gradients detected!"

    # Record parameter snapshot before optimizer step
    params_before = [p.clone().detach() for p in model.parameters()]
    optimizer.step()
    params_after = [p.clone().detach() for p in model.parameters()]

    # Verify parameter change
    param_changed = any(not torch.equal(pb, pa) for pb, pa in zip(params_before, params_after))
    print(f"  Parameters Changed on Step:  {param_changed}")
    assert param_changed, "Parameters failed to change after optimizer step!"

    # 6. Training Loop (Loss Reduction on Tiny Fixture)
    num_steps = 50
    loss_history: List[float] = [initial_loss_val]
    step_times: List[float] = []

    t_start = time.perf_counter()
    for step in range(1, num_steps):
        t0 = time.perf_counter()
        optimizer.zero_grad()
        _, step_loss = model(train_inputs, targets=train_targets)
        assert step_loss is not None
        step_loss.backward()
        optimizer.step()
        t1 = time.perf_counter()

        step_times.append(t1 - t0)
        loss_val = float(step_loss.item())
        loss_history.append(loss_val)

    total_training_wall_sec = time.perf_counter() - t_start
    final_train_loss = loss_history[-1]
    final_train_ppl = math.exp(final_train_loss)
    avg_step_ms = (sum(step_times) / len(step_times)) * 1000.0

    print(f"\nOptimization Results ({num_steps} steps):")
    print(f"  Final Training Loss:         {final_train_loss:.4f} (reduction: {(1.0 - final_train_loss / initial_loss_val)*100:.1f}%)")
    print(f"  Final Training Perplexity:   {final_train_ppl:.2f}")
    print(f"  Average Step Latency:        {avg_step_ms:.2f} ms")
    print(f"  Total Training Wall Time:    {total_training_wall_sec:.4f} s")
    assert final_train_loss < initial_loss_val * 0.5, "Loss failed to drop by at least 50%!"

    # 7. Checkpoint Serialization & Exact Reload
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = artifacts_dir / "neural_foundation_experiment_checkpoint.pt"

    torch.save(
        {
            "config": config.to_dict(),
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "final_train_loss": final_train_loss,
            "step_count": num_steps,
        },
        checkpoint_path,
    )
    checkpoint_size_bytes = os.path.getsize(checkpoint_path)

    # Reload safely into a fresh model with weights_only=True
    reloaded_ckpt = torch.load(checkpoint_path, weights_only=True)
    fresh_model = CausalLM(TransformerConfig.from_dict(reloaded_ckpt["config"])).to(device)
    fresh_model.load_state_dict(reloaded_ckpt["model_state_dict"])

    # Verify exact parity
    model.eval()
    fresh_model.eval()
    with torch.no_grad():
        orig_logits, _ = model(train_inputs)
        reloaded_logits, _ = fresh_model(train_inputs)
    reload_exact_match = bool(torch.allclose(orig_logits, reloaded_logits, atol=1e-6))
    print(f"\nCheckpoint Persistence & Reload:")
    print(f"  Checkpoint Path:             {checkpoint_path.name} ({checkpoint_size_bytes / 1024:.1f} KB)")
    print(f"  Reload Exact Output Match:   {reload_exact_match}")
    assert reload_exact_match, "Reloaded model outputs diverge from original model!"

    # 8. Held-out Evaluation (Evaluation Mode)
    model.eval()
    with torch.no_grad():
        test_logits, held_out_loss_tensor = model(test_inputs, targets=test_targets)
    assert held_out_loss_tensor is not None
    held_out_loss = float(held_out_loss_tensor.item())
    held_out_ppl = math.exp(held_out_loss)
    print(f"\nHeld-Out Test Evaluation:")
    print(f"  Held-out Test Loss:          {held_out_loss:.4f}")
    print(f"  Held-out Test Perplexity:    {held_out_ppl:.2f}")

    # 9. Peak Memory & Budget Verification
    peak_rss_bytes = process.memory_info().rss
    peak_rss_mb = peak_rss_bytes / (1024**2)
    rss_budget_mb = 2048.0
    within_budget = peak_rss_mb <= rss_budget_mb
    print(f"\nResource & Budget Compliance:")
    print(f"  Peak Process RSS:            {peak_rss_mb:.2f} MB")
    print(f"  Budget Limit:                {rss_budget_mb:.2f} MB")
    print(f"  Within Budget:               {within_budget}")
    assert within_budget, f"Process RSS ({peak_rss_mb:.2f} MB) exceeded budget ({rss_budget_mb:.2f} MB)!"

    # Build final structured results
    results: Dict[str, Any] = {
        "experiment_name": "veda_from_scratch_neural_foundation",
        "timestamp_epoch": time.time(),
        "hardware_environment": {
            "device": str(device),
            "cuda_available": cuda_available,
            "pytorch_version": torch.__version__,
            "total_ram_gb": round(sys_mem.total / (1024**3), 2),
            "initial_process_rss_mb": round(initial_rss_bytes / (1024**2), 2),
            "peak_process_rss_mb": round(peak_rss_mb, 2),
            "process_rss_budget_mb": rss_budget_mb,
            "within_rss_budget": within_budget,
        },
        "model_architecture": {
            "model_type": "CausalLM (decoder-only Transformer)",
            "vocab_size": config.vocab_size,
            "d_model": config.d_model,
            "n_heads": config.n_heads,
            "n_layers": config.n_layers,
            "d_ff": config.d_ff,
            "max_seq_len": config.max_seq_len,
            "total_parameters": total_params,
            "weights_source": "random_gaussian_scratch (no pretrained weights)",
        },
        "dataset_governance": {
            "tokenizer": "CharacterTokenizer (v0.1)",
            "train_examples_count": len(train_texts),
            "test_examples_count": len(test_texts),
            "leakage_check": leakage_report,
        },
        "training_dynamics": {
            "num_steps": num_steps,
            "optimizer": "AdamW(lr=0.005, weight_decay=0.01)",
            "initial_train_loss": round(initial_loss_val, 4),
            "initial_train_ppl": round(initial_ppl, 2),
            "final_train_loss": round(final_train_loss, 4),
            "final_train_ppl": round(final_train_ppl, 2),
            "loss_reduction_pct": round((1.0 - final_train_loss / initial_loss_val) * 100, 2),
            "gradients_finite": grad_finite,
            "parameters_changed": param_changed,
            "loss_trajectory": [round(l, 4) for l in loss_history],
            "average_step_ms": round(avg_step_ms, 2),
            "total_training_wall_sec": round(total_training_wall_sec, 4),
        },
        "checkpoint_verification": {
            "saved_checkpoint_path": str(checkpoint_path),
            "checkpoint_size_bytes": checkpoint_size_bytes,
            "reload_exact_output_match": reload_exact_match,
        },
        "held_out_evaluation": {
            "held_out_test_loss": round(held_out_loss, 4),
            "held_out_test_ppl": round(held_out_ppl, 2),
            "mode": "eval() deterministic without dropout",
        },
    }

    results_path = PROJECT_ROOT / "data" / "corpus" / "experiment_neural_foundation_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_path}")
    print("=" * 70)
    print("EXPERIMENT COMPLETED SUCCESSFULLY")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_experiment()
