"""
VEDA Quality Filter & Language Identification Audit Test Suite (Phase 4.2.2)

Tests adversarial examples against QualityFilter and measures false positive /
false negative boundaries as required by Section F.
"""

import unittest

from foundation.corpus.filtering import QualityFilter
from foundation.corpus.language_audit import (
    build_adversarial_language_dataset,
    evaluate_language_filter,
)
from foundation.corpus.schemas import RejectionReason


class TestCorpusLanguageAudit(unittest.TestCase):
    """Adversarial language heuristic audit tests."""

    def setUp(self) -> None:
        self.qf = QualityFilter()
        self.samples = build_adversarial_language_dataset()

    def test_language_filter_adversarial_evaluation(self) -> None:
        """Verifies language filter evaluation measures false positives and false negatives."""
        report = evaluate_language_filter(self.qf, self.samples)
        self.assertEqual(report["total_evaluated_samples"], 14)
        # Measured: German text with cognates 'in' and 'so' is a known false positive
        self.assertGreater(report["false_positives"], 0)
        # Verify operating boundaries are clearly documented
        self.assertIn("stopword_heuristic_scope", report["operating_boundaries"])
        self.assertIn("script_vs_language_distinction", report["operating_boundaries"])

    def test_german_cognate_false_positive_documented(self) -> None:
        """Demonstrates that German text sharing cognates 'in' and 'so' can bypass naive stopword checks."""
        german_text = (
            "Das ist in der Tat so ein großes Problem für die gesamte Gesellschaft. "
            "Wir müssen diese Fragen gründlich und ohne Vorurteile untersuchen."
        )
        decision = self.qf.evaluate(german_text)
        # This is an intentional heuristic boundary test: German text with 'in' and 'so' passes stopword count
        self.assertTrue(decision.is_accepted, "Documented boundary: German cognates bypass naive stopword threshold")

    def test_cyrillic_script_rejection(self) -> None:
        """Verifies non-Latin Cyrillic script is rejected via non_latin_ratio."""
        cyrillic_text = "Это пример текста на русском языке, который использует кириллический алфавит."
        decision = self.qf.evaluate(cyrillic_text)
        self.assertFalse(decision.is_accepted)
        self.assertEqual(decision.rejection_reason, RejectionReason.NON_ENGLISH_SCRIPT)

    def test_scientific_prose_preservation(self) -> None:
        """Verifies authentic English scientific prose with technical nomenclature passes filtering."""
        sci_text = (
            "Barium chlorate decomposes at elevated temperature yielding barium chloride "
            "and gaseous oxygen molecules through an exothermic reaction pathway."
        )
        decision = self.qf.evaluate(sci_text)
        self.assertTrue(decision.is_accepted)
        self.assertIsNone(decision.rejection_reason)

    def test_v1_adversarial_language_benchmark_coverage(self) -> None:
        """Verifies the v1 benchmark has exactly 21 samples covering all 9 required categories."""
        from foundation.corpus.language_audit import build_v1_adversarial_language_benchmark
        samples = build_v1_adversarial_language_benchmark()
        self.assertEqual(len(samples), 21)

        expected_categories = {
            "ordinary_english_prose",
            "scientific_mathematical_english",
            "short_signs_captions_headings",
            "code_logs_tables_technical",
            "foreign_latin_script_french_german_spanish",
            "foreign_names_and_quotes",
            "mixed_language_pedagogy",
            "non_latin_script",
            "unicode_punctuation_edge_cases",
        }
        actual_categories = {s.category for s in samples}
        self.assertEqual(actual_categories, expected_categories)

    def test_quarantine_routing_policy(self) -> None:
        """Verifies that borderline text with minimal stopwords is routed to QUARANTINE."""
        from foundation.corpus.language_audit import classify_with_quarantine
        # German text with cognates 'in' and 'so':
        german_text = (
            "Das ist in der Tat so ein großes Problem für die gesamte Gesellschaft. "
            "Wir müssen diese Fragen gründlich und ohne Vorurteile untersuchen."
        )
        result = classify_with_quarantine(german_text, self.qf)
        # Should be quarantined because stopword count is 2 (minimal) on a 19-word text
        self.assertEqual(result["outcome"], "QUARANTINE")
        self.assertEqual(result["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_evaluate_language_benchmark_with_quarantine(self) -> None:
        """Runs the complete benchmark evaluation with quarantine and verifies metrics output."""
        from foundation.corpus.language_audit import (
            build_v1_adversarial_language_benchmark,
            evaluate_language_benchmark_with_quarantine,
        )
        samples = build_v1_adversarial_language_benchmark()
        report = evaluate_language_benchmark_with_quarantine(self.qf, samples)

        self.assertEqual(report["total_evaluated_samples"], 21)
        self.assertGreaterEqual(report["total_quarantined"], 3)
        self.assertGreater(report["benchmark_accuracy"], 0.80)
        self.assertEqual(len(report["results_by_category"]), 9)

