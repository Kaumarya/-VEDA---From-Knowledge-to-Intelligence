"""
VEDA Phase 4.4 Quality Gates & Comprehensive Evaluation Runner

Evaluates all formal Quality Gates defined in docs/veda_quality_gates.md:
- Gate A: English Language & Quality Filter (>= 95% on held-out test split, Wilson 95% CI)
- Gate B: Near-Duplicate Detection & MinHash/LSH (>= 95% Precision and Recall, Wilson 95% CI)
- Gate C: Data Integrity, Provenance & Conservation (100% Pass Rate)
- Gate D: Tokenizer Round-Trip & Boundary Invariants (100% Pass Rate)
- Gate E: Neural Foundation Structural & Checkpoint Invariants

Generates reproducible structured artifact: data/corpus/phase4.4_eval_results.json
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
import torch

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.characters.registry import CharacterRegistry
from foundation.corpus.eval_dataset_v2 import export_all_v2_datasets
from foundation.corpus.filtering import QualityFilter
from foundation.corpus.language_audit import classify_with_quarantine
from foundation.corpus.near_deduplication import (
    MinHashLSHCandidateDetector,
    get_k_shingles,
    jaccard_similarity,
)
from foundation.lexicon.storage import SqliteLexicon
from foundation.model.dataset import ControlledLanguageDataset, detect_train_test_leakage
from foundation.model.transformer import CausalLM, TransformerConfig
from tokenizer.char_tokenizer import CharacterTokenizer


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Calculates Wilson score 95% confidence interval for binomial proportion."""
    if total == 0:
        return 0.0, 0.0
    p_hat = successes / total
    denom = 1.0 + (z**2) / total
    center = (p_hat + (z**2) / (2.0 * total)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z**2) / (4.0 * total**2))
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


# ---------------------------------------------------------------------------
# GATE A: Language Quality Filter Evaluation
# ---------------------------------------------------------------------------

def evaluate_gate_a_language(test_samples: List[Dict[str, Any]], filter_instance: QualityFilter) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("EVALUATING GATE A: ENGLISH LANGUAGE & QUALITY FILTER")
    print("=" * 70)

    total = len(test_samples)
    correct = 0
    accepted = 0
    rejected = 0
    quarantined = 0

    # Binary accuracy counters for non-quarantine decisions
    # True Positives: Ground Truth ACCEPT, System ACCEPT
    # False Positives: Ground Truth REJECT, System ACCEPT
    # True Negatives: Ground Truth REJECT, System REJECT
    # False Negatives: Ground Truth ACCEPT, System REJECT
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    category_records: Dict[str, Dict[str, Any]] = {}
    sample_records: List[Dict[str, Any]] = []

    for s in test_samples:
        cat = s["category"]
        if cat not in category_records:
            category_records[cat] = {
                "total": 0,
                "correct": 0,
                "accepted": 0,
                "rejected": 0,
                "quarantined": 0,
                "tp": 0,
                "fp": 0,
                "tn": 0,
                "fn": 0,
            }

        cat_stat = category_records[cat]
        cat_stat["total"] += 1

        clf = classify_with_quarantine(s["text"], filter_instance)
        actual = clf["outcome"]
        expected = s["expected_outcome"]

        is_match = (actual == expected)
        if is_match:
            correct += 1
            cat_stat["correct"] += 1

        if actual == "ACCEPT":
            accepted += 1
            cat_stat["accepted"] += 1
        elif actual == "REJECT":
            rejected += 1
            cat_stat["rejected"] += 1
        elif actual == "QUARANTINE":
            quarantined += 1
            cat_stat["quarantined"] += 1

        # Binary confusion metrics (where definitive expected outcome is known)
        if expected == "ACCEPT":
            if actual == "ACCEPT":
                tp += 1
                cat_stat["tp"] += 1
            elif actual == "REJECT":
                fn += 1
                cat_stat["fn"] += 1
        elif expected == "REJECT":
            if actual == "REJECT":
                tn += 1
                cat_stat["tn"] += 1
            elif actual == "ACCEPT":
                fp += 1
                cat_stat["fp"] += 1

        sample_records.append({
            "sample_id": s["sample_id"],
            "category": cat,
            "expected_outcome": expected,
            "actual_outcome": actual,
            "is_correct": is_match,
            "reason": clf["reason"],
            "quality_score": round(clf["quality_score"], 4),
        })

    overall_accuracy = correct / total if total > 0 else 0.0
    acc_ci = wilson_interval(correct, total)

    # Precision, Recall, F1 for definitive Accept decisions
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    prec_ci = wilson_interval(tp, tp + fp)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    rec_ci = wilson_interval(tp, tp + fn)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # False Acceptance Rate (FAR) and False Rejection Rate (FRR)
    far = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    frr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    quarantine_rate = quarantined / total if total > 0 else 0.0

    # Build category breakdown with sample size verification
    categories_summary: Dict[str, Any] = {}
    all_categories_pass = True

    for cat_name, stats in category_records.items():
        n = stats["total"]
        c = stats["correct"]
        cat_acc = c / n if n > 0 else 0.0
        cat_ci = wilson_interval(c, n)

        # Status: INCONCLUSIVE if N < 30
        if n < 30:
            cat_status = "INCONCLUSIVE"
        elif cat_acc >= 0.95:
            cat_status = "VERIFIED"
        else:
            cat_status = "BLOCKED"
            all_categories_pass = False

        categories_summary[cat_name] = {
            "sample_count": n,
            "correct_count": c,
            "accuracy": round(cat_acc, 4),
            "accuracy_95_ci": cat_ci,
            "accepted": stats["accepted"],
            "rejected": stats["rejected"],
            "quarantined": stats["quarantined"],
            "status": cat_status,
        }

    gate_status = "VERIFIED" if (overall_accuracy >= 0.95 and all_categories_pass) else "BLOCKED"

    print(f"Total Held-Out Samples:   {total}")
    print(f"Overall Accuracy:         {overall_accuracy:.4f} (95% CI: {acc_ci})")
    print(f"Precision (Accept):       {precision:.4f} (95% CI: {prec_ci})")
    print(f"Recall (Accept):          {recall:.4f} (95% CI: {rec_ci})")
    print(f"F1 Score:                 {f1:.4f}")
    print(f"False Acceptance Rate:    {far:.4f}")
    print(f"False Rejection Rate:     {frr:.4f}")
    print(f"Quarantine Rate:          {quarantine_rate:.4f} ({quarantined}/{total})")
    print(f"Gate A Status:            {gate_status}")

    return {
        "gate_name": "GATE_A_LANGUAGE_QUALITY_FILTER",
        "status": gate_status,
        "standard_threshold": 0.95,
        "total_evaluated_samples": total,
        "total_correct": correct,
        "accuracy": round(overall_accuracy, 4),
        "accuracy_95_ci": acc_ci,
        "precision": round(precision, 4),
        "precision_95_ci": prec_ci,
        "recall": round(recall, 4),
        "recall_95_ci": rec_ci,
        "f1_score": round(f1, 4),
        "false_acceptance_rate": round(far, 4),
        "false_rejection_rate": round(frr, 4),
        "quarantine_rate": round(quarantine_rate, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "quarantined": quarantined,
        },
        "category_results": categories_summary,
    }


# ---------------------------------------------------------------------------
# GATE B: Near-Duplicate Detection & MinHash/LSH Evaluation
# ---------------------------------------------------------------------------

def evaluate_gate_b_neardup(test_pairs: List[Dict[str, Any]], threshold: float = 0.80) -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("EVALUATING GATE B: NEAR-DUPLICATE DETECTION & MINHASH/LSH")
    print("=" * 70)

    detector = MinHashLSHCandidateDetector(threshold=threshold)
    total_pairs = len(test_pairs)

    # Stage 1: Candidate retrieval counters
    cand_tp = 0
    cand_fp = 0
    cand_tn = 0
    cand_fn = 0

    # Stage 2: Final decision counters
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    category_stats: Dict[str, Dict[str, Any]] = {}

    for pair in test_pairs:
        cat = pair["category"]
        if cat not in category_stats:
            category_stats[cat] = {
                "total": 0,
                "true_duplicates": 0,
                "tp": 0,
                "fp": 0,
                "tn": 0,
                "fn": 0,
            }

        cat_stat = category_stats[cat]
        cat_stat["total"] += 1
        is_true_dup = pair["is_true_duplicate"]
        if is_true_dup:
            cat_stat["true_duplicates"] += 1

        # Stage 1: LSH band collision
        pair_lsh = MinHashLSHCandidateDetector(
            threshold=threshold,
            num_perm=detector.num_perm,
            num_bands=detector.num_bands,
            k_shingle=detector.k_shingle,
        )
        pair_lsh.index_document(pair["doc_a_id"], pair["text_a"])
        retrieved_candidates = pair_lsh.query_candidates(pair["text_b"])
        has_collision = (pair["doc_a_id"] in retrieved_candidates)

        if is_true_dup and has_collision:
            cand_tp += 1
        elif not is_true_dup and has_collision:
            cand_fp += 1
        elif not is_true_dup and not has_collision:
            cand_tn += 1
        else:
            cand_fn += 1

        # Stage 2: Final MinHash Jaccard estimate
        sig_a = detector.compute_signature(pair["text_a"])
        sig_b = detector.compute_signature(pair["text_b"])
        est_jaccard = detector.estimate_similarity(sig_a, sig_b)
        predicted_dup = est_jaccard >= threshold

        if is_true_dup and predicted_dup:
            tp += 1
            cat_stat["tp"] += 1
        elif not is_true_dup and predicted_dup:
            fp += 1
            cat_stat["fp"] += 1
        elif not is_true_dup and not predicted_dup:
            tn += 1
            cat_stat["tn"] += 1
        else:
            fn += 1
            cat_stat["fn"] += 1

    # Stage 1 metrics
    cand_recall = cand_tp / (cand_tp + cand_fn) if (cand_tp + cand_fn) > 0 else 0.0
    cand_selectivity = cand_tn / (cand_tn + cand_fp) if (cand_tn + cand_fp) > 0 else 0.0

    # Stage 2 metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    prec_ci = wilson_interval(tp, tp + fp)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    rec_ci = wilson_interval(tp, tp + fn)
    accuracy = (tp + tn) / total_pairs if total_pairs > 0 else 0.0
    acc_ci = wilson_interval(tp + tn, total_pairs)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Category breakdown
    cat_summary: Dict[str, Any] = {}
    all_cats_pass = True

    for cat_name, stats in category_stats.items():
        n = stats["total"]
        cat_correct = stats["tp"] + stats["tn"]
        cat_acc = cat_correct / n if n > 0 else 0.0
        cat_ci = wilson_interval(cat_correct, n)

        if n < 30:
            c_status = "INCONCLUSIVE"
        elif cat_acc >= 0.95:
            c_status = "VERIFIED"
        else:
            c_status = "BLOCKED"
            all_cats_pass = False

        cat_summary[cat_name] = {
            "total_pairs": n,
            "correct_pairs": cat_correct,
            "accuracy": round(cat_acc, 4),
            "accuracy_95_ci": cat_ci,
            "tp": stats["tp"],
            "fp": stats["fp"],
            "tn": stats["tn"],
            "fn": stats["fn"],
            "status": c_status,
        }

    gate_status = "VERIFIED" if (precision >= 0.95 and recall >= 0.95 and all_cats_pass) else "BLOCKED"

    print(f"Total Held-Out Pairs:     {total_pairs}")
    print(f"Stage 1 Recall:           {cand_recall:.4f}")
    print(f"Stage 1 Selectivity:      {cand_selectivity:.4f}")
    print(f"Stage 2 Precision:        {precision:.4f} (95% CI: {prec_ci})")
    print(f"Stage 2 Recall:           {recall:.4f} (95% CI: {rec_ci})")
    print(f"Stage 2 Accuracy:         {accuracy:.4f} (95% CI: {acc_ci})")
    print(f"Stage 2 F1 Score:         {f1:.4f}")
    print(f"False Merges (FP):        {fp}")
    print(f"Missed Duplicates (FN):   {fn}")
    print(f"Gate B Status:            {gate_status}")

    return {
        "gate_name": "GATE_B_NEAR_DUPLICATE_LSH",
        "status": gate_status,
        "standard_threshold": 0.95,
        "total_evaluated_pairs": total_pairs,
        "stage1_candidate_retrieval": {
            "candidate_recall": round(cand_recall, 4),
            "candidate_selectivity": round(cand_selectivity, 4),
            "cand_tp": cand_tp,
            "cand_fp": cand_fp,
            "cand_tn": cand_tn,
            "cand_fn": cand_fn,
        },
        "stage2_final_decision": {
            "accuracy": round(accuracy, 4),
            "accuracy_95_ci": acc_ci,
            "precision": round(precision, 4),
            "precision_95_ci": prec_ci,
            "recall": round(recall, 4),
            "recall_95_ci": rec_ci,
            "f1_score": round(f1, 4),
            "false_merges_fp": fp,
            "missed_duplicates_fn": fn,
            "true_positives_tp": tp,
            "true_negatives_tn": tn,
        },
        "category_results": cat_summary,
    }


# ---------------------------------------------------------------------------
# GATE C: Data Integrity, Provenance & Conservation Evaluation
# ---------------------------------------------------------------------------

def evaluate_gate_c_integrity() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("EVALUATING GATE C: DATA INTEGRITY, PROVENANCE & CONSERVATION")
    print("=" * 70)

    db_path = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_sample.sqlite"
    if not db_path.is_file():
        db_path = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_v0.1.sqlite"
    assert db_path.is_file(), f"Lexicon database missing at {db_path}"

    lexicon = SqliteLexicon(db_path, read_only=True)
    check_results = lexicon.integrity_check()
    lexicon.close()

    is_healthy = check_results["is_healthy"]
    sqlite_ok = check_results["sqlite_integrity_check"] == ["ok"]
    fk_ok = len(check_results["foreign_key_violations"]) == 0
    words_count = check_results["words_row_count"]

    gate_status = "VERIFIED" if (is_healthy and sqlite_ok and fk_ok and words_count > 0) else "BLOCKED"

    print(f"Database Path:            {db_path.name}")
    print(f"SQLite PRAGMA Integrity:  {check_results['sqlite_integrity_check']}")
    print(f"Foreign Key Violations:   {len(check_results['foreign_key_violations'])}")
    print(f"Verified Words Count:     {words_count}")
    print(f"Gate C Status:            {gate_status}")

    return {
        "gate_name": "GATE_C_DATA_INTEGRITY",
        "status": gate_status,
        "standard_threshold": 1.00,
        "pass_rate": 1.00 if gate_status == "VERIFIED" else 0.00,
        "details": {
            "sqlite_integrity": sqlite_ok,
            "foreign_keys_valid": fk_ok,
            "words_row_count": words_count,
            "word_pos_count": check_results["word_pos_row_count"],
            "senses_count": check_results["senses_row_count"],
            "distinct_normalized_words": check_results["distinct_normalized_words_in_pos"],
        },
    }


# ---------------------------------------------------------------------------
# GATE D: Tokenizer Round-Trip & Boundary Invariants
# ---------------------------------------------------------------------------

def evaluate_gate_d_tokenizer() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("EVALUATING GATE D: TOKENIZER ROUND-TRIP & BOUNDARY INVARIANTS")
    print("=" * 70)

    tokenizer = CharacterTokenizer()
    vocab_size = tokenizer.vocab_size

    # Test 1: Empty string round-trip
    empty_enc = tokenizer.encode("", add_special_tokens=False)
    empty_dec = tokenizer.decode(empty_enc)
    empty_pass = (empty_enc == [] and empty_dec == "")

    # Test 2: Full registry characters exact round-trip
    registry_chars = [c.character for c in tokenizer.registry.characters]
    full_string = "".join(registry_chars)
    full_enc = tokenizer.encode(full_string, add_special_tokens=False)
    full_dec = tokenizer.decode(full_enc)
    full_pass = (full_dec == full_string and len(full_enc) == len(registry_chars))

    # Test 3: Unregistered characters deterministically map to UNK without crash
    unreg_sample = "Hello 🚀 World 🌍!"
    unreg_enc = tokenizer.encode(unreg_sample, add_special_tokens=False)
    has_unk = tokenizer.unk_token_id in unreg_enc
    unreg_dec = tokenizer.decode(unreg_enc)
    unreg_pass = (has_unk and "<UNK>" in unreg_dec)

    # Test 4: Special tokens ID mapping
    specials_pass = (
        tokenizer.pad_token_id == 0
        and tokenizer.unk_token_id == 1
        and tokenizer.bos_token_id == 2
        and tokenizer.eos_token_id == 3
    )

    all_passed = empty_pass and full_pass and unreg_pass and specials_pass
    gate_status = "VERIFIED" if all_passed else "BLOCKED"

    print(f"Vocabulary Size:          {vocab_size} (Declared Scope: English Character Foundation)")
    print(f"Empty String Invariant:   {empty_pass}")
    print(f"Full Registry Round-Trip: {full_pass}")
    print(f"Unregistered <UNK> Map:   {unreg_pass}")
    print(f"Special Tokens Contract:  {specials_pass}")
    print(f"Gate D Status:            {gate_status}")

    return {
        "gate_name": "GATE_D_TOKENIZER_ROUND_TRIP",
        "status": gate_status,
        "standard_threshold": 1.00,
        "pass_rate": 1.00 if all_passed else 0.00,
        "details": {
            "vocab_size": vocab_size,
            "empty_string_pass": empty_pass,
            "full_registry_roundtrip_pass": full_pass,
            "unregistered_unk_mapping_pass": unreg_pass,
            "special_tokens_contract_pass": specials_pass,
        },
    }


# ---------------------------------------------------------------------------
# GATE E: Neural Foundation Invariants & Deserialization Security
# ---------------------------------------------------------------------------

def evaluate_gate_e_neural() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("EVALUATING GATE E: NEURAL FOUNDATION & DESERIALIZATION SECURITY")
    print("=" * 70)

    tokenizer = CharacterTokenizer()
    config = TransformerConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=32,
        n_heads=2,
        n_layers=2,
        d_ff=64,
        max_seq_len=32,
        dropout=0.0,
    )
    torch.manual_seed(42)
    model = CausalLM(config)
    model.eval()

    # 1. Causal attention masking integrity
    seq_a = torch.tensor([[5, 10, 15, 20]], dtype=torch.long)
    seq_b = torch.tensor([[5, 10, 15, 99]], dtype=torch.long)
    with torch.no_grad():
        out_a, _ = model(seq_a)
        out_b, _ = model(seq_b)
    causal_ok = bool(torch.allclose(out_a[:, :3, :], out_b[:, :3, :], atol=1e-5))

    # 2. Gradient finiteness and parameter update
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    inputs = torch.randint(0, config.vocab_size, (2, 16))
    targets = torch.randint(0, config.vocab_size, (2, 16))
    optimizer.zero_grad()
    _, loss = model(inputs, targets=targets)
    assert loss is not None
    loss.backward()

    grads_finite = all(
        p.grad is not None and torch.isfinite(p.grad).all()
        for p in model.parameters()
        if p.requires_grad
    )

    params_before = [p.clone().detach() for p in model.parameters()]
    optimizer.step()
    params_changed = any(
        not torch.equal(pb, pa) for pb, pa in zip(params_before, model.parameters())
    )

    # 3. Checkpoint Serialization & weights_only=True Deserialization Security
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = artifacts_dir / "gate_e_security_checkpoint.pt"

    torch.save(
        {
            "config": config.to_dict(),
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
        },
        ckpt_path,
    )

    reloaded_dict = torch.load(ckpt_path, weights_only=True)
    fresh_model = CausalLM(TransformerConfig.from_dict(reloaded_dict["config"]))
    fresh_model.load_state_dict(reloaded_dict["model_state"])

    model.eval()
    fresh_model.eval()
    with torch.no_grad():
        orig_out, _ = model(inputs)
        reloaded_out, _ = fresh_model(inputs)
    reload_match = bool(torch.allclose(orig_out, reloaded_out, atol=1e-6))

    # 4. Train / Test Leakage Detection
    train_texts = ["The quick brown fox jumps over the lazy dog."]
    test_texts = ["To be, or not to be, that is the question."]
    leakage_rep = detect_train_test_leakage(train_texts, test_texts)
    no_leakage = not leakage_rep["leakage_detected"]

    all_passed = causal_ok and grads_finite and params_changed and reload_match and no_leakage
    gate_status = "VERIFIED" if all_passed else "BLOCKED"

    print(f"Causal Masking Invariant: {causal_ok}")
    print(f"Finite Gradients:         {grads_finite}")
    print(f"Parameters Change Step:   {params_changed}")
    print(f"Secure Reload Match:      {reload_match} (weights_only=True)")
    print(f"Zero Train/Test Leakage:  {no_leakage}")
    print(f"Gate E Status:            {gate_status}")

    return {
        "gate_name": "GATE_E_NEURAL_FOUNDATION",
        "status": gate_status,
        "standard_threshold": 1.00,
        "pass_rate": 1.00 if all_passed else 0.00,
        "details": {
            "causal_masking_ok": causal_ok,
            "gradients_finite": grads_finite,
            "parameters_changed": params_changed,
            "checkpoint_reload_exact_match": reload_match,
            "safe_deserialization_weights_only": True,
            "train_test_leakage_free": no_leakage,
        },
    }


# ---------------------------------------------------------------------------
# MAIN EVALUATION PIPELINE
# ---------------------------------------------------------------------------

def run_phase44_quality_evaluation() -> Dict[str, Any]:
    print("=" * 70)
    print("VEDA PHASE 4.4 QUALITY GATES & COMPREHENSIVE EVALUATION")
    print("=" * 70)

    # 1. Export / Load Datasets
    data_dir = PROJECT_ROOT / "data" / "corpus"
    meta = export_all_v2_datasets(data_dir)

    with open(data_dir / "eval_language_dataset_v2.json", "r", encoding="utf-8") as f:
        lang_data = json.load(f)
    with open(data_dir / "eval_near_dedup_dataset_v2.json", "r", encoding="utf-8") as f:
        dedup_data = json.load(f)

    lang_test = lang_data["held_out_test_split"]["samples"]
    dedup_test = dedup_data["held_out_test_split"]["pairs"]

    q_filter = QualityFilter()

    # 2. Evaluate all Gates
    res_a = evaluate_gate_a_language(lang_test, q_filter)
    res_b = evaluate_gate_b_neardup(dedup_test)
    res_c = evaluate_gate_c_integrity()
    res_d = evaluate_gate_d_tokenizer()
    res_e = evaluate_gate_e_neural()

    # 3. Aggregate Final Status
    gate_statuses = [
        res_a["status"],
        res_b["status"],
        res_c["status"],
        res_d["status"],
        res_e["status"],
    ]

    all_verified = all(s == "VERIFIED" for s in gate_statuses)
    overall_phase_status = "VERIFIED" if all_verified else "BLOCKED"

    final_payload = {
        "evaluation_name": "VEDA_Phase_4.4_Quality_Gates_Certification",
        "timestamp_epoch": time.time(),
        "overall_status": overall_phase_status,
        "production_corpus_ingestion_status": "STRICTLY_BLOCKED (Awaiting legal & source governance)",
        "hardware_environment": {
            "python_executable": sys.executable,
            "python_version": sys.version,
            "system_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "process_rss_mb": round(psutil.Process().memory_info().rss / (1024**2), 2),
            "device": "cpu",
            "cuda_available": torch.cuda.is_available(),
        },
        "datasets_provenance": meta,
        "gates": {
            "gate_a_language_filter": res_a,
            "gate_b_near_deduplication": res_b,
            "gate_c_data_integrity": res_c,
            "gate_d_tokenizer": res_d,
            "gate_e_neural_foundation": res_e,
        },
    }

    out_json = data_dir / "phase4.4_eval_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)

    print("\n" + "=" * 70)
    print(f"PHASE 4.4 CERTIFICATION COMPLETE: OVERALL STATUS = {overall_phase_status}")
    print(f"Results saved to: {out_json}")
    print("=" * 70)

    return final_payload


if __name__ == "__main__":
    run_phase44_quality_evaluation()
