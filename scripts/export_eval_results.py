"""
VEDA Evaluation Export Script (Phase 4.2.3)
Generates reproducible JSON evaluation artifacts for:
1. Near-duplicate MinHash/LSH evaluation (Stage 1 & Stage 2)
2. English language quality filtering benchmark (with quarantine)
"""

import json
import sys
from pathlib import Path

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.corpus.near_deduplication import evaluate_near_duplicate_strategy
from foundation.corpus.filtering import QualityFilter
from foundation.corpus.language_audit import (
    build_v1_adversarial_language_benchmark,
    evaluate_language_benchmark_with_quarantine,
)

def main() -> None:
    data_dir = Path("data/corpus")
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run near-deduplication evaluation
    dedup_results = evaluate_near_duplicate_strategy()
    dedup_path = data_dir / "eval_near_dedup_results.json"
    with open(dedup_path, "w", encoding="utf-8") as f:
        json.dump(dedup_results, f, indent=2)

    # 2. Run language filter benchmark evaluation
    qf = QualityFilter()
    samples = build_v1_adversarial_language_benchmark()
    lang_results = evaluate_language_benchmark_with_quarantine(qf, samples)
    lang_path = data_dir / "eval_language_filter_results.json"
    with open(lang_path, "w", encoding="utf-8") as f:
        json.dump(lang_results, f, indent=2)

    print("=== DEDUP EVALUATION ===")
    s1 = dedup_results["stage1_candidate_retrieval"]
    s2 = dedup_results["stage2_final_decision"]
    print(f"Total pairs: {dedup_results['total_evaluated_pairs']}")
    print(f"Stage 1 Recall: {s1['candidate_recall']:.4f}, Selectivity: {s1['candidate_selectivity']:.4f}")
    print(f"Stage 2 Precision: {s2['precision']:.4f}, Recall: {s2['recall']:.4f}, F1: {s2['f1_score']:.4f}")
    print(f"Wilson 95% CI Recall: {s2['recall_95_ci']}")

    print("\n=== LANGUAGE FILTER EVALUATION ===")
    print(f"Total Samples: {lang_results['total_evaluated_samples']}")
    print(f"Benchmark Accuracy: {lang_results['benchmark_accuracy']:.4f}")
    print(f"Total Accepted: {lang_results['total_accepted']}")
    print(f"Total Rejected: {lang_results['total_rejected']}")
    print(f"Total Quarantined: {lang_results['total_quarantined']}")

if __name__ == "__main__":
    main()
