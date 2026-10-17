"""
VEDA Phase 4.12 Independent Evaluation & Certification Runner
Executes comprehensive validation across:
1. Sealed Provisional Benchmark v8.0:
   - Task A: Language Identification & Quality Filtering (Dev N=60, Test N=60)
     Using production entry point: classify_with_quarantine()
   - Task B: Near-Deduplication & Semantic Safety Guard (Dev N=20, Test N=20)
     Using production entry point: NearDuplicateDetector.are_near_duplicates()
2. Historical Regression Tracking:
   - Golden Benchmark v3.0
   - Historical Benchmark v6.0
   - Historical Benchmark v7.0

Emits: data/corpus/phase4.12_eval_results.json
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from foundation.corpus.filtering import QualityFilter
from foundation.corpus.language_audit import (
    classify_with_quarantine,
)
from foundation.corpus.near_deduplication import (
    NearDuplicateDetector,
    _wilson_score_interval,
)


def get_git_info() -> Dict[str, str]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        commit = "unknown"
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        branch = "unknown"
    return {"commit": commit, "branch": branch}


def compute_file_sha256(path: Path) -> str:
    if not path.exists():
        return "FILE_NOT_FOUND"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def evaluate_language_split(
    samples_data: List[Dict[str, Any]],
    qf: QualityFilter,
) -> Dict[str, Any]:
    total = len(samples_data)
    correct = 0
    accepted = 0
    rejected = 0
    quarantined = 0

    category_stats: Dict[str, Dict[str, int]] = {}
    confusion_matrix = {
        "ACCEPT": {"ACCEPT": 0, "QUARANTINE": 0, "REJECT": 0},
        "QUARANTINE": {"ACCEPT": 0, "QUARANTINE": 0, "REJECT": 0},
        "REJECT": {"ACCEPT": 0, "QUARANTINE": 0, "REJECT": 0},
    }

    false_accepts: List[Dict[str, Any]] = []
    false_rejects: List[Dict[str, Any]] = []
    unnecessary_quarantines: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    predictions_record: List[Dict[str, Any]] = []

    for s in samples_data:
        text = s["text"]
        expected = s.get("expected_outcome") or s.get("expected_decision")
        if not expected and "should_accept" in s:
            expected = "ACCEPT" if s["should_accept"] else "REJECT"

        category = s.get("category", "general")
        sample_id = s.get("sample_id", s.get("id", "unknown"))

        clf = classify_with_quarantine(text, qf)
        pred = clf["outcome"]

        stats = category_stats.setdefault(category, {
            "total": 0, "correct": 0, "accepted": 0, "rejected": 0, "quarantined": 0
        })
        stats["total"] += 1

        if pred == "ACCEPT":
            accepted += 1
            stats["accepted"] += 1
        elif pred == "REJECT":
            rejected += 1
            stats["rejected"] += 1
        elif pred == "QUARANTINE":
            quarantined += 1
            stats["quarantined"] += 1

        confusion_matrix[expected][pred] += 1

        is_correct = (pred == expected)
        if is_correct:
            correct += 1
            stats["correct"] += 1
        else:
            err_record = {
                "sample_id": sample_id,
                "category": category,
                "domain": s.get("domain", "unknown"),
                "expected": expected,
                "predicted": pred,
                "reason": clf.get("reason"),
                "text_snippet": text[:80] + ("..." if len(text) > 80 else ""),
            }
            errors.append(err_record)

            # Failure taxonomies
            if expected in ("QUARANTINE", "REJECT") and pred == "ACCEPT":
                false_accepts.append(err_record)
            elif expected == "ACCEPT" and pred == "REJECT":
                false_rejects.append(err_record)
            elif expected == "ACCEPT" and pred == "QUARANTINE":
                unnecessary_quarantines.append(err_record)

        predictions_record.append({
            "sample_id": sample_id,
            "category": category,
            "expected": expected,
            "predicted": pred,
            "is_correct": is_correct,
            "reason": clf.get("reason"),
        })

    accuracy = correct / total if total > 0 else 0.0

    # Per-class metrics
    tp_acc = confusion_matrix["ACCEPT"]["ACCEPT"]
    fp_acc = confusion_matrix["QUARANTINE"]["ACCEPT"] + confusion_matrix["REJECT"]["ACCEPT"]
    fn_acc = confusion_matrix["ACCEPT"]["QUARANTINE"] + confusion_matrix["ACCEPT"]["REJECT"]
    prec_accept = tp_acc / (tp_acc + fp_acc) if (tp_acc + fp_acc) > 0 else (1.0 if tp_acc == 0 and fp_acc == 0 else 0.0)
    rec_accept = tp_acc / (tp_acc + fn_acc) if (tp_acc + fn_acc) > 0 else (1.0 if tp_acc == 0 and fn_acc == 0 else 0.0)
    f1_accept = 2 * (prec_accept * rec_accept) / (prec_accept + rec_accept) if (prec_accept + rec_accept) > 0 else 0.0

    tp_quar = confusion_matrix["QUARANTINE"]["QUARANTINE"]
    fp_quar = confusion_matrix["ACCEPT"]["QUARANTINE"] + confusion_matrix["REJECT"]["QUARANTINE"]
    fn_quar = confusion_matrix["QUARANTINE"]["ACCEPT"] + confusion_matrix["QUARANTINE"]["REJECT"]
    prec_quar = tp_quar / (tp_quar + fp_quar) if (tp_quar + fp_quar) > 0 else 0.0
    rec_quar = tp_quar / (tp_quar + fn_quar) if (tp_quar + fn_quar) > 0 else 0.0
    f1_quar = 2 * (prec_quar * rec_quar) / (prec_quar + rec_quar) if (prec_quar + rec_quar) > 0 else 0.0

    tp_rej = confusion_matrix["REJECT"]["REJECT"]
    fp_rej = confusion_matrix["ACCEPT"]["REJECT"] + confusion_matrix["QUARANTINE"]["REJECT"]
    fn_rej = confusion_matrix["REJECT"]["ACCEPT"] + confusion_matrix["REJECT"]["QUARANTINE"]
    prec_rej = tp_rej / (tp_rej + fp_rej) if (tp_rej + fp_rej) > 0 else 0.0
    rec_rej = tp_rej / (tp_rej + fn_rej) if (tp_rej + fn_rej) > 0 else 0.0
    f1_rej = 2 * (prec_rej * rec_rej) / (prec_rej + rec_rej) if (prec_rej + rec_rej) > 0 else 0.0

    macro_f1 = (f1_accept + f1_quar + f1_rej) / 3.0

    ci_low, ci_high = _wilson_score_interval(correct, total)

    return {
        "total_samples": total,
        "correct_predictions": correct,
        "incorrect_predictions": total - correct,
        "accuracy": round(accuracy, 4),
        "accuracy_95_ci": [round(ci_low, 4), round(ci_high, 4)],
        "macro_f1": round(macro_f1, 4),
        "per_class": {
            "ACCEPT": {"precision": round(prec_accept, 4), "recall": round(rec_accept, 4), "f1": round(f1_accept, 4)},
            "QUARANTINE": {"precision": round(prec_quar, 4), "recall": round(rec_quar, 4), "f1": round(f1_quar, 4)},
            "REJECT": {"precision": round(prec_rej, 4), "recall": round(rec_rej, 4), "f1": round(f1_rej, 4)},
        },
        "rates": {
            "english_false_rejection_rate": round(len(false_rejects) / max(1, (tp_acc + fn_acc)), 4),
            "non_english_false_acceptance_rate": round(len(false_accepts) / max(1, (total - (tp_acc + fn_acc))), 4),
            "quarantine_rate": round(quarantined / total, 4) if total > 0 else 0.0,
        },
        "confusion_matrix": confusion_matrix,
        "category_stats": category_stats,
        "false_accepts_count": len(false_accepts),
        "false_rejects_count": len(false_rejects),
        "unnecessary_quarantines_count": len(unnecessary_quarantines),
        "errors": errors,
        "predictions": predictions_record,
    }


def evaluate_near_dedup_split(
    pairs_data: List[Dict[str, Any]],
    detector: NearDuplicateDetector,
) -> Dict[str, Any]:
    total_pairs = len(pairs_data)

    stage2_tp = 0
    stage2_fp = 0
    stage2_tn = 0
    stage2_fn = 0

    stage3_tp = 0
    stage3_fp = 0
    stage3_tn = 0
    stage3_fn = 0

    false_merges_prevented = 0
    safety_critical_false_merges = 0

    category_stats: Dict[str, Dict[str, int]] = {}
    errors: List[Dict[str, Any]] = []
    predictions_record: List[Dict[str, Any]] = []

    for p in pairs_data:
        text_a = p["text_a"]
        text_b = p["text_b"]
        is_true_dup = bool(p.get("is_true_duplicate", p.get("is_duplicate")))
        category = p.get("category", "general")
        pair_id = p.get("pair_id", p.get("id", "unknown"))

        cat = category_stats.setdefault(category, {
            "total": 0, "correct": 0, "s2_false_merges": 0, "s3_false_merges": 0, "prevented": 0
        })
        cat["total"] += 1

        # Production entry point invocation
        result = detector.are_near_duplicates(text_a, text_b)

        s2_cand = result.is_candidate
        candidate_similarity = result.candidate_similarity
        final_merge = result.is_duplicate
        guard_reason = result.safety_guard_violations or "MERGE_PERMITTED"
        conflict_type = result.conflict_type

        # Stage 2 metrics
        if is_true_dup and s2_cand:
            stage2_tp += 1
        elif not is_true_dup and s2_cand:
            stage2_fp += 1
            cat["s2_false_merges"] += 1
        elif not is_true_dup and not s2_cand:
            stage2_tn += 1
        else:
            stage2_fn += 1

        # Prevention tracking
        if s2_cand and not final_merge and not is_true_dup:
            false_merges_prevented += 1
            cat["prevented"] += 1

        # Stage 3 evaluation
        is_correct = (final_merge == is_true_dup)
        if is_true_dup and final_merge:
            stage3_tp += 1
            cat["correct"] += 1
        elif not is_true_dup and final_merge:
            stage3_fp += 1
            cat["s3_false_merges"] += 1
            if category.startswith("safety_") or "inversion" in category or "mismatch" in category or "conflict" in category:
                safety_critical_false_merges += 1
            errors.append({
                "id": pair_id, "category": category, "expected": is_true_dup, "predicted": True,
                "reason": f"False Merge: {guard_reason}", "text_a": text_a[:60], "text_b": text_b[:60]
            })
        elif not is_true_dup and not final_merge:
            stage3_tn += 1
            cat["correct"] += 1
        else:
            stage3_fn += 1
            errors.append({
                "id": pair_id, "category": category, "expected": is_true_dup, "predicted": False,
                "reason": f"Missed Duplicate: {guard_reason}", "text_a": text_a[:60], "text_b": text_b[:60]
            })

        predictions_record.append({
            "pair_id": pair_id,
            "category": category,
            "expected": is_true_dup,
            "s2_candidate": s2_cand,
            "candidate_similarity": round(candidate_similarity, 4),
            "s3_final_merge": final_merge,
            "is_correct": is_correct,
            "conflict_type": conflict_type,
            "reason": guard_reason,
        })

    s3_acc = (stage3_tp + stage3_tn) / total_pairs if total_pairs > 0 else 0.0
    s3_prec = stage3_tp / (stage3_tp + stage3_fp) if (stage3_tp + stage3_fp) > 0 else (1.0 if stage3_tp == 0 and stage3_fp == 0 else 0.0)
    s3_rec = stage3_tp / (stage3_tp + stage3_fn) if (stage3_tp + stage3_fn) > 0 else (1.0 if stage3_tp == 0 and stage3_fn == 0 else 0.0)
    s3_f1 = 2 * (s3_prec * s3_rec) / (s3_prec + s3_rec) if (s3_prec + s3_rec) > 0 else 0.0
    ci_low, ci_high = _wilson_score_interval(stage3_tp + stage3_tn, total_pairs)

    return {
        "total_pairs": total_pairs,
        "correct_predictions": stage3_tp + stage3_tn,
        "incorrect_predictions": total_pairs - (stage3_tp + stage3_tn),
        "stage2_candidate_screening": {
            "tp": stage2_tp, "fp": stage2_fp, "tn": stage2_tn, "fn": stage2_fn,
            "precision": round(stage2_tp / (stage2_tp + stage2_fp), 4) if (stage2_tp + stage2_fp) > 0 else 0.0,
            "recall": round(stage2_tp / (stage2_tp + stage2_fn), 4) if (stage2_tp + stage2_fn) > 0 else 0.0,
        },
        "stage3_final_decision": {
            "tp": stage3_tp, "fp": stage3_fp, "tn": stage3_tn, "fn": stage3_fn,
            "accuracy": round(s3_acc, 4),
            "accuracy_95_ci": [round(ci_low, 4), round(ci_high, 4)],
            "precision": round(s3_prec, 4),
            "recall": round(s3_rec, 4),
            "f1": round(s3_f1, 4),
            "false_positive_rate": round(stage3_fp / max(1, (stage3_fp + stage3_tn)), 4),
            "false_negative_rate": round(stage3_fn / max(1, (stage3_tp + stage3_fn)), 4),
            "false_merges_prevented": false_merges_prevented,
            "safety_critical_false_merges": safety_critical_false_merges,
        },
        "category_stats": category_stats,
        "errors": errors,
        "predictions": predictions_record,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="VEDA Evaluation & Certification Runner")
    parser.add_argument(
        "--output",
        default="phase4.13_eval_results.json",
        help="Output filename or path (default: phase4.13_eval_results.json in data/corpus)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("VEDA Corpus Quality Evaluation Runner (Phase 4.13 Remediation)")
    print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"Python Runtime: {sys.version.split()[0]} ({sys.executable})")
    print("=" * 70)

    corpus_dir = _ROOT / "data" / "corpus"
    git_info = get_git_info()

    # Load Source Code Hashes
    source_hashes = {
        "foundation/corpus/language_audit.py": compute_file_sha256(_ROOT / "foundation/corpus/language_audit.py"),
        "foundation/corpus/filtering.py": compute_file_sha256(_ROOT / "foundation/corpus/filtering.py"),
        "foundation/corpus/near_deduplication.py": compute_file_sha256(_ROOT / "foundation/corpus/near_deduplication.py"),
        "tests/test_near_deduplication_safety.py": compute_file_sha256(_ROOT / "tests/test_near_deduplication_safety.py"),
        "tests/test_language_filter_hardening.py": compute_file_sha256(_ROOT / "tests/test_language_filter_hardening.py"),
        "tests/test_corpus_production_gate_fail_closed.py": compute_file_sha256(_ROOT / "tests/test_corpus_production_gate_fail_closed.py"),
    }

    # Initialize Production Modules
    qf = QualityFilter()
    dedup_detector = NearDuplicateDetector(threshold=0.75)

    eval_results: Dict[str, Any] = {
        "meta": {
            "phase": "4.13",
            "eval_name": "remediated_corpus_quality_regression_v8",
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git": git_info,
            "python_runtime": {
                "version": sys.version,
                "executable": sys.executable,
                "platform": platform.platform(),
            },
            "source_code_hashes": source_hashes,
            "governance_status": "RECLASSIFIED_DEVELOPMENT_REGRESSION — INDEPENDENCE UNVERIFIED",
        },
        "benchmarks": {},
    }

    # 1. Benchmark v8.0 (Primary Phase 4.12 Validation Target)
    lang_v8_path = corpus_dir / "eval_language_dataset_v8.json"
    dedup_v8_path = corpus_dir / "eval_near_dedup_dataset_v8.json"

    if not lang_v8_path.exists() or not dedup_v8_path.exists():
        raise FileNotFoundError("v8.0 datasets missing. Run scripts/build_phase412_v8_datasets.py first.")

    with open(lang_v8_path, "r", encoding="utf-8") as f:
        lang_v8_data = json.load(f)
    with open(dedup_v8_path, "r", encoding="utf-8") as f:
        dedup_v8_data = json.load(f)

    lang_v8_hash = compute_file_sha256(lang_v8_path)
    dedup_v8_hash = compute_file_sha256(dedup_v8_path)

    print(f"\n--- Evaluating Sealed Provisional Benchmark v8.0 ---")
    print(f"Task A Dataset: {lang_v8_path.name} (SHA-256: {lang_v8_hash})")
    print(f"Task B Dataset: {dedup_v8_path.name} (SHA-256: {dedup_v8_hash})")

    task_a_v8_dev = evaluate_language_split(lang_v8_data["development_split"], qf)
    task_a_v8_test = evaluate_language_split(lang_v8_data["test_split"], qf)
    task_b_v8_dev = evaluate_near_dedup_split(dedup_v8_data["development_split"], dedup_detector)
    task_b_v8_test = evaluate_near_dedup_split(dedup_v8_data["test_split"], dedup_detector)

    print(f"\n[Task A: Language Filtering v8.0]")
    print(f"  Dev  (N={task_a_v8_dev['total_samples']}): Accuracy={task_a_v8_dev['accuracy']*100:.2f}% "
          f"(95% CI: {task_a_v8_dev['accuracy_95_ci']}), Macro-F1={task_a_v8_dev['macro_f1']:.4f}")
    print(f"  Test (N={task_a_v8_test['total_samples']}): Accuracy={task_a_v8_test['accuracy']*100:.2f}% "
          f"(95% CI: {task_a_v8_test['accuracy_95_ci']}), Macro-F1={task_a_v8_test['macro_f1']:.4f}")
    print(f"  Test Per-Class: ACCEPT F1={task_a_v8_test['per_class']['ACCEPT']['f1']:.4f}, "
          f"QUARANTINE F1={task_a_v8_test['per_class']['QUARANTINE']['f1']:.4f}, "
          f"REJECT F1={task_a_v8_test['per_class']['REJECT']['f1']:.4f}")
    print(f"  Test Rates: False Rejection={task_a_v8_test['rates']['english_false_rejection_rate']*100:.2f}%, "
          f"False Acceptance={task_a_v8_test['rates']['non_english_false_acceptance_rate']*100:.2f}%, "
          f"Quarantine Rate={task_a_v8_test['rates']['quarantine_rate']*100:.2f}%")

    print(f"\n[Task B: Near-Deduplication v8.0]")
    print(f"  Dev  (N={task_b_v8_dev['total_pairs']}): Stage 2 Prec={task_b_v8_dev['stage2_candidate_screening']['precision']*100:.1f}%, "
          f"Stage 3 Prec={task_b_v8_dev['stage3_final_decision']['precision']*100:.1f}%, "
          f"Acc={task_b_v8_dev['stage3_final_decision']['accuracy']*100:.1f}%, "
          f"Prevented={task_b_v8_dev['stage3_final_decision']['false_merges_prevented']}, "
          f"Safety Violations={task_b_v8_dev['stage3_final_decision']['safety_critical_false_merges']}")
    print(f"  Test (N={task_b_v8_test['total_pairs']}): Stage 2 Prec={task_b_v8_test['stage2_candidate_screening']['precision']*100:.1f}%, "
          f"Stage 3 Prec={task_b_v8_test['stage3_final_decision']['precision']*100:.1f}%, "
          f"Acc={task_b_v8_test['stage3_final_decision']['accuracy']*100:.1f}%, "
          f"Prevented={task_b_v8_test['stage3_final_decision']['false_merges_prevented']}, "
          f"Safety Violations={task_b_v8_test['stage3_final_decision']['safety_critical_false_merges']}")

    eval_results["benchmarks"]["v8_provisional"] = {
        "dataset_hashes": {"language_v8": lang_v8_hash, "near_dedup_v8": dedup_v8_hash},
        "task_a_language": {"development": task_a_v8_dev, "test": task_a_v8_test},
        "task_b_near_dedup": {"development": task_b_v8_dev, "test": task_b_v8_test},
    }

    # 2. Historical Regression Tracking (v3, v6, v7)
    print(f"\n--- Running Historical Regression Benchmarks ---")
    regression_benchmarks = {}

    for ver in ["v7", "v6", "v3"]:
        l_path = corpus_dir / f"eval_language_dataset_{ver}.json"
        d_path = corpus_dir / f"eval_near_dedup_dataset_{ver}.json"

        ver_res: Dict[str, Any] = {}
        if l_path.exists():
            with open(l_path, "r", encoding="utf-8") as f:
                ldata = json.load(f)
            l_hash = compute_file_sha256(l_path)
            ver_res["language_hash"] = l_hash
            if "test_split" in ldata:
                ver_res["task_a_test"] = evaluate_language_split(ldata["test_split"], qf)
                print(f"  [{ver.upper()} Language Test (N={ver_res['task_a_test']['total_samples']})]: "
                      f"Accuracy={ver_res['task_a_test']['accuracy']*100:.2f}%")
            elif "samples" in ldata:
                ver_res["task_a_samples"] = evaluate_language_split(ldata["samples"], qf)
                print(f"  [{ver.upper()} Language Samples (N={ver_res['task_a_samples']['total_samples']})]: "
                      f"Accuracy={ver_res['task_a_samples']['accuracy']*100:.2f}%")

        if d_path.exists():
            with open(d_path, "r", encoding="utf-8") as f:
                ddata = json.load(f)
            d_hash = compute_file_sha256(d_path)
            ver_res["near_dedup_hash"] = d_hash
            if "test_split" in ddata:
                ver_res["task_b_test"] = evaluate_near_dedup_split(ddata["test_split"], dedup_detector)
                print(f"  [{ver.upper()} Dedup Test (N={ver_res['task_b_test']['total_pairs']})]: "
                      f"Accuracy={ver_res['task_b_test']['stage3_final_decision']['accuracy']*100:.2f}%, "
                      f"Prec={ver_res['task_b_test']['stage3_final_decision']['precision']*100:.2f}%")
            elif "pairs" in ddata:
                ver_res["task_b_pairs"] = evaluate_near_dedup_split(ddata["pairs"], dedup_detector)
                print(f"  [{ver.upper()} Dedup Pairs (N={ver_res['task_b_pairs']['total_pairs']})]: "
                      f"Accuracy={ver_res['task_b_pairs']['stage3_final_decision']['accuracy']*100:.2f}%, "
                      f"Prec={ver_res['task_b_pairs']['stage3_final_decision']['precision']*100:.2f}%")

        regression_benchmarks[ver] = ver_res

    eval_results["benchmarks"]["regression_benchmarks"] = regression_benchmarks

    # Save Results
    out_arg = Path(args.output)
    if out_arg.is_absolute():
        out_results_path = out_arg
    elif str(out_arg).startswith("data") or "data" in out_arg.parts:
        out_results_path = _ROOT / out_arg
    else:
        out_results_path = corpus_dir / out_arg

    out_results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_results_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, indent=2)

    out_hash = compute_file_sha256(out_results_path)
    print(f"\nEvaluation complete. Results written to {out_results_path.name} (SHA-256: {out_hash})")
    print("=" * 70)


if __name__ == "__main__":
    main()
