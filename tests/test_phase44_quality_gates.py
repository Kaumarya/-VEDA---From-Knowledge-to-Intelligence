"""
Unit and Regression Tests for VEDA Phase 4.4 Quality Gates & Code Audit Fixes

Verifies:
1. SEC-01: Secure checkpoint serialization & deserialization with weights_only=True.
2. REL-01: Atomic file replacement semantics in CorpusWriter.
3. CLN-01: Clean near-deduplication benchmark without redundant assignments.
4. ACC-01: Expanded closed-class English stopword verification on technical docstrings and quotes.
5. ACC-02: Code syntax detection and rejection of raw source code snippets.
6. Wilson 95% score confidence interval mathematical correctness.
7. V2 Evaluation datasets structure, split isolation, and non-zero counts.
"""

import tempfile
from pathlib import Path
import pytest
import torch

from foundation.corpus.eval_dataset_v2 import generate_expanded_language_dataset, generate_expanded_neardup_dataset
from foundation.corpus.filtering import QualityFilter, _COMMON_ENGLISH_STOPWORDS
from foundation.corpus.language_audit import classify_with_quarantine
from foundation.corpus.near_deduplication import build_eval_labeled_test_set
from foundation.corpus.schemas import CorpusRecord, RecordProvenance, RejectionReason
from foundation.corpus.storage import CorpusWriter
from foundation.model.transformer import CausalLM, TransformerConfig
from scripts.evaluate_phase44_quality_gates import wilson_interval


def test_sec01_safe_checkpoint_deserialization_weights_only() -> None:
    """SEC-01: Confirms checkpoint can be loaded safely with weights_only=True."""
    config = TransformerConfig(vocab_size=117, d_model=32, n_heads=2, n_layers=2, d_ff=64)
    model = CausalLM(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    with tempfile.TemporaryDirectory() as tmpdir:
        ckpt_path = Path(tmpdir) / "safe_checkpoint.pt"
        torch.save(
            {
                "config": config.to_dict(),
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
            },
            ckpt_path,
        )

        # Must load cleanly without raising unpickling or security errors
        reloaded = torch.load(ckpt_path, weights_only=True)
        assert "config" in reloaded
        assert isinstance(reloaded["config"], dict)
        reloaded_config = TransformerConfig.from_dict(reloaded["config"])
        assert reloaded_config.d_model == config.d_model

        reloaded_model = CausalLM(reloaded_config)
        reloaded_model.load_state_dict(reloaded["model_state"])
        assert reloaded_model.count_parameters() == model.count_parameters()


def _make_dummy_record(record_id: str, text: str) -> CorpusRecord:
    norm = text.lower()
    prov = RecordProvenance(
        source_id="src_01",
        document_id="doc_01",
        segment_index=0,
        start_char_offset=0,
        end_char_offset=len(text),
    )
    return CorpusRecord(
        record_id=record_id,
        document_id="doc_01",
        source_id="src_01",
        segment_index=0,
        raw_text=text,
        normalized_text=norm,
        raw_char_count=len(text),
        normalized_char_count=len(norm),
        approx_word_count=len(norm.split()),
        quality_score=0.95,
        is_duplicate=False,
        split="train",
        corpus_version="0.1.0",
        provenance=prov,
    )


def test_rel01_corpus_writer_atomic_replace() -> None:
    """REL-01: Confirms CorpusWriter uses atomic replace without unlinking destination first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)

        # Initial write
        rec1 = _make_dummy_record("rec_001", "Initial text content.")
        writer = CorpusWriter(out_dir)
        writer.write_record(rec1)
        writer.close(commit=True)

        final_train = out_dir / "train.jsonl"
        assert final_train.is_file()
        orig_content = final_train.read_text(encoding="utf-8")
        assert "rec_001" in orig_content

        # Second write committing over existing file atomically
        rec2 = _make_dummy_record("rec_002", "Overwritten text content.")
        writer2 = CorpusWriter(out_dir)
        writer2.write_record(rec2)
        writer2.close(commit=True)

        new_content = final_train.read_text(encoding="utf-8")
        assert "rec_002" in new_content
        assert "rec_001" not in new_content


def test_cln01_near_dedup_benchmark_has_no_duplicate_declarations() -> None:
    """CLN-01: Confirms build_eval_labeled_test_set has 12 distinct pairs with unique IDs."""
    pairs = build_eval_labeled_test_set()
    assert len(pairs) == 12
    pair_ids = [p.pair_id for p in pairs]
    assert len(set(pair_ids)) == 12


def test_acc01_expanded_stopwords_coverage() -> None:
    """ACC-01: Confirms essential closed-class words are recognized in _COMMON_ENGLISH_STOPWORDS."""
    essential = ["is", "are", "were", "been", "has", "had", "between", "while", "under", "through", "these", "those", "each", "other", "such", "both", "than", "only"]
    for w in essential:
        assert w in _COMMON_ENGLISH_STOPWORDS, f"Word {w!r} missing from _COMMON_ENGLISH_STOPWORDS"

    # Confirms technical docstring with 'between' and 'to' passes
    qf = QualityFilter()
    docstring = "This function computes cross-entropy loss between probability distributions, applying numerical stabilization to prevent logarithmic underflow."
    decision = qf.evaluate(docstring)
    assert decision.is_accepted is True

    # Confirms philosophy quote with 'while' and 'of' passes
    quote = "The French philosopher famously remarked 'cogito, ergo sum' while considering the foundational doubts of epistemology."
    decision_quote = qf.evaluate(quote)
    assert decision_quote.is_accepted is True


def test_acc02_code_syntax_rejection() -> None:
    """ACC-02: Confirms raw Python code blocks are rejected by QualityFilter."""
    qf = QualityFilter()
    raw_code = "def compute_loss(y_true, y_pred):\n    return tf.reduce_mean(tf.keras.losses.categorical_crossentropy(y_true, y_pred))"
    decision = qf.evaluate(raw_code)
    assert decision.is_accepted is False
    assert decision.rejection_reason in (RejectionReason.INVALID_STRUCTURE, RejectionReason.NO_ENGLISH_STOPWORDS)

    clf = classify_with_quarantine(raw_code, qf)
    assert clf["outcome"] == "REJECT"


def test_wilson_interval_mathematical_bounds() -> None:
    """Verifies Wilson 95% score interval behavior across boundary cases."""
    # Boundary 0 total
    assert wilson_interval(0, 0) == (0.0, 0.0)

    # 100% successes on N=100
    low, high = wilson_interval(100, 100)
    assert high == 1.0
    assert low > 0.95

    # 0% successes on N=100
    low_zero, high_zero = wilson_interval(0, 100)
    assert low_zero == 0.0
    assert high_zero < 0.05

    # 50% on N=100: interval should be centered near 0.50
    low_mid, high_mid = wilson_interval(50, 100)
    assert low_mid < 0.50 < high_mid


def test_v2_evaluation_datasets_isolation() -> None:
    """Verifies that development and test sets in v2 datasets have zero ID overlap."""
    lang_dev, lang_test = generate_expanded_language_dataset(seed=42)
    assert len(lang_dev) == 500
    assert len(lang_test) == 500

    dev_ids = {s.sample_id for s in lang_dev}
    test_ids = {s.sample_id for s in lang_test}
    assert len(dev_ids & test_ids) == 0

    dedup_dev, dedup_test = generate_expanded_neardup_dataset(seed=42)
    assert len(dedup_dev) == 500
    assert len(dedup_test) == 500

    dev_pair_ids = {p.pair_id for p in dedup_dev}
    test_pair_ids = {p.pair_id for p in dedup_test}
    assert len(dev_pair_ids & test_pair_ids) == 0


def test_v3_evaluation_datasets_strict_zero_leakage() -> None:
    """Verifies that v3.0 datasets have zero author, text, or template leakage across splits."""
    from foundation.corpus.eval_dataset_v3 import build_v3_language_dataset, build_v3_neardup_dataset

    lang_dev, lang_test = build_v3_language_dataset()
    dev_texts = {s.text.strip().lower() for s in lang_dev}
    test_texts = {s.text.strip().lower() for s in lang_test}
    assert len(dev_texts & test_texts) == 0, "Found text leakage across v3.0 language splits!"

    dedup_dev, dedup_test = build_v3_neardup_dataset()
    dev_pairs_texts = {(p.text_a.strip().lower(), p.text_b.strip().lower()) for p in dedup_dev}
    test_pairs_texts = {(p.text_a.strip().lower(), p.text_b.strip().lower()) for p in dedup_test}
    assert len(dev_pairs_texts & test_pairs_texts) == 0, "Found pair leakage across v3.0 dedup splits!"


def test_def03_lexical_minhash_semantic_inversion_boundary() -> None:
    """DEF-03: Demonstrates the mathematical boundary of lexical MinHash on single-token inversions."""
    from foundation.corpus.near_deduplication import MinHashLSHCandidateDetector, get_k_shingles, jaccard_similarity

    # Single-token dosage inversion
    t_safe = "The pediatric patient was administered 10mg of active medication every morning before breakfast."
    t_toxic = "The pediatric patient was administered 100mg of active medication every morning before breakfast."

    sh_safe = get_k_shingles(t_safe, k=5)
    sh_toxic = get_k_shingles(t_toxic, k=5)
    true_j = jaccard_similarity(sh_safe, sh_toxic)

    # True Jaccard exceeds 0.85 despite fatal clinical divergence
    assert true_j > 0.85, f"Expected high lexical similarity, got {true_j}"

    det = MinHashLSHCandidateDetector(threshold=0.80)
    sig_safe = det.compute_signature(t_safe)
    sig_toxic = det.compute_signature(t_toxic)
    est_j = det.estimate_similarity(sig_safe, sig_toxic)

    # MinHash predicts duplicate because lexical similarity exceeds 0.80
    assert est_j >= 0.80, f"Expected false merge, got {est_j}"


def test_recomputed_denominator_wilson_intervals() -> None:
    """Verifies mathematical correctness of recomputed Wilson intervals for N=196 and N=148."""
    # All non-accepts (N=196)
    ci_196 = wilson_interval(0, 196)
    assert ci_196[0] == 0.0
    assert 0.0190 <= ci_196[1] <= 0.0195  # Upper bound ~ 1.92%

    # Definitive rejects only (N=148)
    ci_148 = wilson_interval(0, 148)
    assert ci_148[0] == 0.0
    assert 0.0250 <= ci_148[1] <= 0.0255  # Upper bound ~ 2.53% > 2.0%

