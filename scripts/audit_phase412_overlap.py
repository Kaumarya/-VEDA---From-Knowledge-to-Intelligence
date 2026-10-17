"""
VEDA Phase 4.12 Benchmark Leakage and Overlap Audit Script
Audits v8.0 datasets (Task A Language and Task B Near-Deduplication) for:
1. Exact string matches against historical benchmarks (v3, v4, v5, v6, v7).
2. Normalized string matches (lowercased, punctuation-stripped, whitespace-collapsed).
3. Near-duplicate overlap (token Jaccard >= 0.80) against prior benchmarks.
4. Reversed-order pair duplicates (Task B).
5. Cross-split contamination between v8 development and v8 test sets.
6. Test-suite contamination against tests/ directory.

Emits: data/corpus/phase4.12_leakage_audit.json
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

_ROOT = Path(__file__).resolve().parent.parent


def normalize_text(text: str) -> str:
    # Lowercase, collapse whitespace, strip peripheral whitespace
    t = re.sub(r"\s+", " ", text.strip().lower())
    # Strip standard punctuation for normalized comparison
    t_punct_stripped = re.sub(r"[^\w\s]", "", t)
    return t_punct_stripped.strip() if t_punct_stripped.strip() else t


def get_tokens(text: str) -> Set[str]:
    # Extract unicode words
    words = set(re.findall(r"\w+", text.lower(), re.UNICODE))
    if words:
        return words
    # If no word characters (e.g. pure ASCII symbol noise), extract character 3-grams
    clean = re.sub(r"\s+", "", text.lower())
    if len(clean) < 3:
        return {clean} if clean else set()
    return {clean[i:i+3] for i in range(len(clean) - 2)}


def token_jaccard(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def load_json_dataset(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def audit_language_benchmark() -> Dict[str, Any]:
    corpus_dir = _ROOT / "data" / "corpus"
    v8_path = corpus_dir / "eval_language_dataset_v8.json"
    v8_data = load_json_dataset(v8_path)
    if not v8_data:
        raise FileNotFoundError(f"Missing {v8_path}")

    v8_dev = v8_data["development_split"]
    v8_test = v8_data["test_split"]

    # Gather prior benchmark texts
    prior_benchmarks: Dict[str, List[str]] = {}
    for ver in ["v3", "v4", "v5", "v6", "v7"]:
        p = corpus_dir / f"eval_language_dataset_{ver}.json"
        if p.exists():
            data = load_json_dataset(p)
            texts = []
            if "samples" in data:
                texts.extend(s["text"] for s in data["samples"] if "text" in s)
            if "development_split" in data:
                texts.extend(s["text"] for s in data["development_split"] if "text" in s)
            if "test_split" in data:
                texts.extend(s["text"] for s in data["test_split"] if "text" in s)
            prior_benchmarks[ver] = texts

    # Also scan test files in tests/
    test_files_texts: Dict[str, List[str]] = {}
    tests_dir = _ROOT / "tests"
    for py_file in tests_dir.glob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            # find string literals longer than 30 chars
            literals = re.findall(r'["\']{1,3}([^"\'\n]{30,})["\']{1,3}', content)
            if literals:
                test_files_texts[py_file.name] = literals
        except Exception:
            pass

    results: Dict[str, Any] = {
        "v8_sample_counts": {
            "dev": len(v8_dev),
            "test": len(v8_test),
            "total": len(v8_dev) + len(v8_test),
        },
        "exact_matches_prior": [],
        "normalized_matches_prior": [],
        "high_jaccard_overlaps_prior": [],
        "cross_split_dev_test_matches": [],
        "test_file_literal_overlaps": [],
    }

    # 1. Check v8 dev vs test cross-split
    dev_exact = {s["text"]: s["sample_id"] for s in v8_dev}
    dev_norm = {normalize_text(s["text"]): s["sample_id"] for s in v8_dev}
    dev_tokens = [(s["sample_id"], get_tokens(s["text"])) for s in v8_dev]

    for s in v8_test:
        sid = s["sample_id"]
        txt = s["text"]
        norm = normalize_text(txt)
        toks = get_tokens(txt)

        if txt in dev_exact:
            results["cross_split_dev_test_matches"].append({
                "type": "exact", "test_id": sid, "dev_id": dev_exact[txt], "text": txt
            })
        elif norm in dev_norm:
            results["cross_split_dev_test_matches"].append({
                "type": "normalized", "test_id": sid, "dev_id": dev_norm[norm], "text": txt
            })

    # 2. Check v8 (dev + test) against prior versions
    all_v8 = [(s["sample_id"], s["text"], "dev") for s in v8_dev] + [
        (s["sample_id"], s["text"], "test") for s in v8_test
    ]

    for sid, txt, split in all_v8:
        norm = normalize_text(txt)
        toks = get_tokens(txt)

        for ver, ptexts in prior_benchmarks.items():
            for ptxt in ptexts:
                if txt == ptxt:
                    results["exact_matches_prior"].append({
                        "sample_id": sid, "split": split, "version": ver, "text": txt
                    })
                elif norm == normalize_text(ptxt):
                    results["normalized_matches_prior"].append({
                        "sample_id": sid, "split": split, "version": ver, "v8_text": txt, "prior_text": ptxt
                    })
                else:
                    j_sim = token_jaccard(toks, get_tokens(ptxt))
                    if j_sim >= 0.80:
                        results["high_jaccard_overlaps_prior"].append({
                            "sample_id": sid, "split": split, "version": ver, "jaccard": round(j_sim, 4),
                            "v8_text": txt, "prior_text": ptxt
                        })

        # 3. Check against test file string literals
        for tf_name, literals in test_files_texts.items():
            for lit in literals:
                if txt.strip() == lit.strip():
                    results["test_file_literal_overlaps"].append({
                        "sample_id": sid, "test_file": tf_name, "text": txt
                    })

    return results


def audit_near_dedup_benchmark() -> Dict[str, Any]:
    corpus_dir = _ROOT / "data" / "corpus"
    v8_path = corpus_dir / "eval_near_dedup_dataset_v8.json"
    v8_data = load_json_dataset(v8_path)
    if not v8_data:
        raise FileNotFoundError(f"Missing {v8_path}")

    v8_dev = v8_data["development_split"]
    v8_test = v8_data["test_split"]

    prior_benchmarks: Dict[str, List[Tuple[str, str]]] = {}
    for ver in ["v3", "v4", "v5", "v6", "v7"]:
        p = corpus_dir / f"eval_near_dedup_dataset_{ver}.json"
        if p.exists():
            data = load_json_dataset(p)
            pairs = []
            if "pairs" in data:
                pairs.extend((pr["text_a"], pr["text_b"]) for pr in data["pairs"] if "text_a" in pr)
            if "development_split" in data:
                pairs.extend((pr["text_a"], pr["text_b"]) for pr in data["development_split"] if "text_a" in pr)
            if "test_split" in data:
                pairs.extend((pr["text_a"], pr["text_b"]) for pr in data["test_split"] if "text_a" in pr)
            prior_benchmarks[ver] = pairs

    results: Dict[str, Any] = {
        "v8_pair_counts": {
            "dev": len(v8_dev),
            "test": len(v8_test),
            "total": len(v8_dev) + len(v8_test),
        },
        "exact_pair_matches_prior": [],
        "reversed_pair_matches_prior": [],
        "normalized_pair_matches_prior": [],
        "cross_split_dev_test_matches": [],
    }

    # Cross split dev vs test
    dev_pairs = set()
    for p in v8_dev:
        na = normalize_text(p["text_a"])
        nb = normalize_text(p["text_b"])
        dev_pairs.add((na, nb))
        dev_pairs.add((nb, na))

    for p in v8_test:
        na = normalize_text(p["text_a"])
        nb = normalize_text(p["text_b"])
        if (na, nb) in dev_pairs:
            results["cross_split_dev_test_matches"].append({
                "test_id": p["pair_id"], "text_a": p["text_a"][:50], "text_b": p["text_b"][:50]
            })

    # Prior benchmark checks
    all_v8 = [(p["pair_id"], p["text_a"], p["text_b"], "dev") for p in v8_dev] + [
        (p["pair_id"], p["text_a"], p["text_b"], "test") for p in v8_test
    ]

    for pid, ta, tb, split in all_v8:
        nta = normalize_text(ta)
        ntb = normalize_text(tb)

        for ver, pairs in prior_benchmarks.items():
            for pta, ptb in pairs:
                npta = normalize_text(pta)
                nptb = normalize_text(ptb)

                if (ta == pta and tb == ptb) or (ta == ptb and tb == pta):
                    results["exact_pair_matches_prior"].append({
                        "pair_id": pid, "split": split, "version": ver, "reversed": (ta == ptb)
                    })
                elif (nta == npta and ntb == nptb) or (nta == nptb and ntb == npta):
                    results["normalized_pair_matches_prior"].append({
                        "pair_id": pid, "split": split, "version": ver, "reversed": (nta == nptb)
                    })

    return results


def main() -> None:
    print("Running Phase 4.12 Benchmark Leakage and Overlap Audit...")
    lang_audit = audit_language_benchmark()
    dedup_audit = audit_near_dedup_benchmark()

    full_audit = {
        "audit_timestamp": "2026-10-17T21:55:00Z",
        "benchmark_versions_checked": ["v3", "v4", "v5", "v6", "v7"],
        "task_a_language": lang_audit,
        "task_b_near_dedup": dedup_audit,
        "summary": {
            "task_a_exact_matches": len(lang_audit["exact_matches_prior"]),
            "task_a_normalized_matches": len(lang_audit["normalized_matches_prior"]),
            "task_a_high_jaccard_matches": len(lang_audit["high_jaccard_overlaps_prior"]),
            "task_a_cross_split_matches": len(lang_audit["cross_split_dev_test_matches"]),
            "task_a_test_file_overlaps": len(lang_audit["test_file_literal_overlaps"]),
            "task_b_exact_matches": len(dedup_audit["exact_pair_matches_prior"]),
            "task_b_normalized_matches": len(dedup_audit["normalized_pair_matches_prior"]),
            "task_b_cross_split_matches": len(dedup_audit["cross_split_dev_test_matches"]),
        }
    }

    out_path = _ROOT / "data" / "corpus" / "phase4.12_leakage_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_audit, f, indent=2)

    print(f"Emitted {out_path.name}")
    print(f"Task A: Exact Matches = {full_audit['summary']['task_a_exact_matches']}, "
          f"Normalized Matches = {full_audit['summary']['task_a_normalized_matches']}, "
          f"High Jaccard (>0.80) = {full_audit['summary']['task_a_high_jaccard_matches']}, "
          f"Cross-Split = {full_audit['summary']['task_a_cross_split_matches']}, "
          f"Test File Overlaps = {full_audit['summary']['task_a_test_file_overlaps']}")
    print(f"Task B: Exact Matches = {full_audit['summary']['task_b_exact_matches']}, "
          f"Normalized Matches = {full_audit['summary']['task_b_normalized_matches']}, "
          f"Cross-Split = {full_audit['summary']['task_b_cross_split_matches']}")


if __name__ == "__main__":
    main()
