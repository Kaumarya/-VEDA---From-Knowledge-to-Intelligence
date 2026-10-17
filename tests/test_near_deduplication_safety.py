"""
VEDA Phase 4.5 Safety-Aware Near-Deduplication Tests

Verifies Stage 3 SemanticSafetyGuard functionality:
1. Single-token numerical dosage inversions (e.g., 10 mg vs 100 mg).
2. SI unit conversion standardization (e.g., 1000 mg = 1 g).
3. Temporal year and calendar date discrepancies (e.g., 1824 vs 1827).
4. Logical polarity inversions (safe/non-toxic vs toxic/dangerous).
5. Asymmetric negation particle conflicts (not, never, cannot).
6. Legitimate grammatical voice paraphrases.
7. Stage 2 candidate detection vs Stage 3 safe merge decision separation.
"""

from __future__ import annotations

import unittest
from foundation.corpus.near_deduplication import (
    MinHashLSHCandidateDetector,
    SemanticSafetyGuard,
    SafetyVerificationResult,
    NearDuplicateDetector,
    NearDuplicateResult,
    evaluate_near_duplicate_strategy,
    build_phase45_safety_test_set,
    build_safety_critical_pairs,
)


class TestNearDeduplicationSafety(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = SemanticSafetyGuard()
        self.detector = MinHashLSHCandidateDetector(threshold=0.80)

    def test_numerical_inversion_dosage_10mg_vs_100mg(self) -> None:
        """Confirms 10mg vs 100mg dosage inversion is flagged as NUMERICAL_MISMATCH."""
        text_a = "The pediatric patient was administered 10mg of active medication every morning."
        text_b = "The pediatric patient was administered 100mg of active medication every morning."

        # Verify MinHash alone has high similarity >= 0.80
        sig_a = self.detector.compute_signature(text_a)
        sig_b = self.detector.compute_signature(text_b)
        est_j = self.detector.estimate_similarity(sig_a, sig_b)
        self.assertGreaterEqual(est_j, 0.80, "Lexical MinHash should produce high Jaccard on single-token flip")

        # Stage 3 Guard must detect numerical discrepancy and block merge
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "NUMERICAL_MISMATCH")

    def test_unit_conversion_normalization(self) -> None:
        """Confirms 1000 mg and 1 g normalize to SI base units and are recognized as safe."""
        text_a = "The laboratory protocol specified exactly 1000 mg of sodium chloride in solution."
        text_b = "The laboratory protocol specified exactly 1 g of sodium chloride in solution."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertTrue(res.is_safe_to_merge)
        self.assertFalse(res.conflict_detected)

    def test_temporal_date_conflict(self) -> None:
        """Confirms distinct historical calendar years are flagged as DATE_MISMATCH."""
        text_a = "The constitutional treaty was formally ratified in London in 1824."
        text_b = "The constitutional treaty was formally ratified in London in 1827."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        # Will be caught by numerical check or date check
        self.assertIn(res.conflict_type, ("NUMERICAL_MISMATCH", "DATE_MISMATCH"))

    def test_polarity_inversion_safe_vs_toxic(self) -> None:
        """Confirms safe/non-toxic vs toxic/dangerous is flagged as POLARITY_INVERSION."""
        text_a = "The compound demonstrated to be safe and non-toxic in preclinical screening."
        text_b = "The compound demonstrated to be toxic and dangerous in preclinical screening."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_polarity_inversion_permitted_vs_prohibited(self) -> None:
        """Confirms permitted vs prohibited is flagged as POLARITY_INVERSION."""
        text_a = "Operation of heavy machinery in Zone A is permitted during night hours."
        text_b = "Operation of heavy machinery in Zone A is prohibited during night hours."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_asymmetric_negation_particle(self) -> None:
        """Confirms asymmetric negation particles ('not') are flagged as NEGATION_INVERSION."""
        text_a = "The secondary reaction mechanism was observed to proceed under standard pressure."
        text_b = "The secondary reaction mechanism was not observed to proceed under standard pressure."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "NEGATION_INVERSION")

    def test_valid_paraphrase_allowed(self) -> None:
        """Confirms grammatical voice paraphrase with identical factual assertions is safe."""
        text_a = "Dr. Alvarez supervised 50 clinical trials across three major university hospitals."
        text_b = "Across three major university hospitals, 50 clinical trials were supervised by Dr. Alvarez."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertTrue(res.is_safe_to_merge)
        self.assertFalse(res.conflict_detected)

    def test_stage3_guard_on_expanded_benchmark(self) -> None:
        """
        Demonstrates that MinHash candidate detection produces false merges
        on safety-inverted pairs, while Stage 3 SemanticSafetyGuard achieves 100% precision.
        """
        pairs = build_phase45_safety_test_set()
        report = evaluate_near_duplicate_strategy(
            detector=self.detector,
            labeled_pairs=pairs,
            threshold=0.80,
            safety_guard=self.guard,
        )

        s2 = report["stage2_similarity_threshold"]
        s3 = report["stage3_safety_decision"]

        # Stage 2 MinHash alone suffers false positives on dosage/negation flips
        self.assertGreater(s2["false_positives"], 0, "Pure MinHash must exhibit false merges on dosage flips")

        # Stage 3 Safety Guard prevents false merges and achieves 100% precision
        self.assertEqual(s3["false_positives"], 0, "Stage 3 Guard must prevent all false merges")
        self.assertEqual(s3["precision"], 1.0)
        self.assertEqual(s3["recall"], 1.0)
        self.assertGreater(s3["false_merges_prevented"], 0)


    def test_entity_identifier_conflict(self) -> None:
        """Confirms entity identifier code mismatches (e.g. Sample-A101 vs Sample-B101) are flagged."""
        text_a = "Tissue biopsy Sample-A101 showed standard cellular morphology with no atypical changes."
        text_b = "Tissue biopsy Sample-B101 showed standard cellular morphology with no atypical changes."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "IDENTIFIER_MISMATCH")

    def test_time_unit_conversion_normalization(self) -> None:
        """Confirms 60 s and 1 min normalize to base units and are recognized as safe."""
        text_a = "The centrifuge was spun at high velocity for exactly 60 seconds."
        text_b = "The centrifuge was spun at high velocity for exactly 1 minute."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertTrue(res.is_safe_to_merge)
        self.assertFalse(res.conflict_detected)

    def test_comparison_threshold_antonyms(self) -> None:
        """Confirms comparison direction inversions (at least vs at most) are flagged."""
        text_a = "The assay requires at least 50% purity to proceed with molecular analysis."
        text_b = "The assay requires at most 50% purity to proceed with molecular analysis."

        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_physical_unit_dimension_mismatch_blocks_merge(self) -> None:
        """Confirms physical unit and dimension discrepancies block merging even when scalar number is identical (DEF-4.7-03)."""
        text_m = "The standard laboratory pipe measured 10 meters in total length."
        text_g = "The standard laboratory pipe measured 10 grams in total length."
        res1 = self.guard.verify_pair(text_m, text_g)
        self.assertFalse(res1.is_safe_to_merge)
        self.assertEqual(res1.conflict_type, "UNIT_MISMATCH")

        text_amp = "The electrical circuit was rated for 10 amperes maximum load."
        text_volt = "The electrical circuit was rated for 10 volts maximum load."
        res2 = self.guard.verify_pair(text_amp, text_volt)
        self.assertFalse(res2.is_safe_to_merge)
        self.assertEqual(res2.conflict_type, "UNIT_MISMATCH")

    def test_calendar_month_conflict_blocks_merge(self) -> None:
        """Confirms calendar month discrepancies block merging (DEF-4.7-04)."""
        text_mar = "The definitive international treaty was signed in Paris on March 15, 2024."
        text_nov = "The definitive international treaty was signed in Paris on November 15, 2024."
        res = self.guard.verify_pair(text_mar, text_nov)
        self.assertFalse(res.is_safe_to_merge)
        self.assertEqual(res.conflict_type, "DATE_MISMATCH")

    def test_non_unit_word_extraction(self) -> None:
        """Confirms common English prepositions following numbers are not treated as units (DEF-4.7-05)."""
        q = self.guard.extract_quantities("There were 10 of them in 5 different rooms.")
        self.assertEqual(q, [(10.0, "count"), (5.0, "count")])


    def test_polarity_inversion_greater_than_vs_less_than_with_preposition_under(self) -> None:
        """Regression test for DEF-4.8: Polarity inversion with shared preposition 'under'."""
        text_a = "The catalytic synthesis yield was recorded as greater than 80% under standardized operating parameters."
        text_b = "The catalytic synthesis yield was recorded as less than 80% under standardized operating parameters."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_binary_unit_conversion_bytes_to_mib(self) -> None:
        """Regression test for DEF-4.8: Binary unit normalization 1048576 bytes = 1 MiB."""
        text_a = "The kernel ring buffer allocated 1048576 bytes of physical RAM for storing debug trace records."
        text_b = "The kernel ring buffer allocated 1 mib of physical RAM for storing debug trace records."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertTrue(res.is_safe_to_merge)
        self.assertFalse(res.conflict_detected)

    def test_voice_paraphrase_candidate_retrieval_and_merge(self) -> None:
        """Regression test for DEF-4.8: Active vs passive voice paraphrase duplicate."""
        text_a = "The attending physician instructed the nurses that 250 mg of cephalosporin should be administered orally."
        text_b = "Nurses were instructed by the attending physician that 250 mg of cephalosporin should be administered orally."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertTrue(res.is_safe_to_merge)

    def test_polarity_inversion_base_form_approve_vs_reject(self) -> None:
        """Regression test for DEF-4.8.1: Base-form polarity inversion 'to approve' vs 'to reject'."""
        text_a = "The research committee voted to approve the proposed quantum computing curriculum for next semester."
        text_b = "The research committee voted to reject the proposed quantum computing curriculum for next semester."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_polarity_inversion_base_form_permit_vs_prohibit(self) -> None:
        """Confirms base form 'to permit' vs 'to prohibit' triggers POLARITY_INVERSION."""
        text_a = "The municipal council voted to permit commercial drone deliveries within residential zones."
        text_b = "The municipal council voted to prohibit commercial drone deliveries within residential zones."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_polarity_inversion_inflection_enables_vs_disables(self) -> None:
        """Confirms 3rd-person singular 'enables' vs 'disables' triggers POLARITY_INVERSION."""
        text_a = "The new software driver enables hardware acceleration for video decoding tasks."
        text_b = "The new software driver disables hardware acceleration for video decoding tasks."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_polarity_inversion_inflection_increases_vs_decreases(self) -> None:
        """Confirms 3rd-person singular 'increases' vs 'decreases' triggers POLARITY_INVERSION."""
        text_a = "Elevated ambient humidity increases the crystallization rate of the pharmaceutical compound."
        text_b = "Elevated ambient humidity decreases the crystallization rate of the pharmaceutical compound."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_negation_particle_never_conflict(self) -> None:
        """Confirms 'never' negation particle triggers NEGATION_INVERSION."""
        text_a = "The automated system can never overwrite encrypted backup partitions on the storage server."
        text_b = "The automated system can easily overwrite encrypted backup partitions on the storage server."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "NEGATION_INVERSION")

    def test_numerical_mismatch_decimal_quantities(self) -> None:
        """Confirms small decimal differences (0.005 v vs 0.050 v) trigger NUMERICAL_MISMATCH."""
        text_a = "The sample voltage was maintained at 0.005 volts during baseline calibration."
        text_b = "The sample voltage was maintained at 0.050 volts during baseline calibration."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "NUMERICAL_MISMATCH")

    def test_unit_mismatch_dimension_conflict(self) -> None:
        """Confirms pressure vs distance dimension conflict triggers UNIT_MISMATCH."""
        text_a = "The chemical reactor vessel was pressurized to 5.0 bar during high-temperature synthesis."
        text_b = "The chemical reactor vessel was pressurized to 5.0 meters during high-temperature synthesis."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "UNIT_MISMATCH")

    def test_date_conflict_calendar_month(self) -> None:
        """Confirms month discrepancies within identical dates trigger DATE_MISMATCH."""
        text_a = "The archaeological excavation concluded on July 14, 1984 after three seasons of fieldwork."
        text_b = "The archaeological excavation concluded on October 14, 1984 after three seasons of fieldwork."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "DATE_MISMATCH")

    def test_identifier_mismatch_satellite_codes(self) -> None:
        """Confirms alphanumeric device identifier mismatch triggers IDENTIFIER_MISMATCH."""
        text_a = "The telemetry stream from Satellite-A902 indicated nominal solar panel deployment."
        text_b = "The telemetry stream from Satellite-B902 indicated nominal solar panel deployment."
        res = self.guard.verify_pair(text_a, text_b)
        self.assertFalse(res.is_safe_to_merge)
        self.assertTrue(res.conflict_detected)
        self.assertEqual(res.conflict_type, "IDENTIFIER_MISMATCH")

    # ── Phase 4.11 Regression Tests: expand vs reduce / contract ─────────────

    def test_phase411_groundwater_quota_expand_vs_reduce_rejected(self) -> None:
        """Phase 4.11: Confirms groundwater-quota pair (expand vs reduce) is rejected by production detector.

        Tests full production pipeline path:
        1. Stage 2 candidate screening produces high similarity (>= 0.75).
        2. Stage 3 SemanticSafetyGuard detects POLARITY_INVERSION.
        3. End-to-end detector returns is_duplicate == False.
        """
        text_a = "The state environmental commission resolved to expand commercial groundwater extraction quotas along the coastal aquifer."
        text_b = "The state environmental commission resolved to reduce commercial groundwater extraction quotas along the coastal aquifer."

        detector = NearDuplicateDetector(threshold=0.75)
        res = detector.are_near_duplicates(text_a, text_b)

        self.assertTrue(res.is_candidate, "Candidate screening should detect high lexical similarity")
        self.assertFalse(res.is_duplicate, "Groundwater quota inversion must NOT be merged as duplicate")
        self.assertFalse(res.safety_guard_passed, "Safety guard must block the merge")
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")
        self.assertIn("expand", res.safety_guard_violations or "")
        self.assertIn("reduce", res.safety_guard_violations or "")

    def test_phase411_groundwater_quota_reversed_order_safe(self) -> None:
        """Phase 4.11: Confirms reversed argument order produces the exact same rejection."""
        text_a = "The state environmental commission resolved to expand commercial groundwater extraction quotas along the coastal aquifer."
        text_b = "The state environmental commission resolved to reduce commercial groundwater extraction quotas along the coastal aquifer."

        detector = NearDuplicateDetector(threshold=0.75)
        res = detector.are_near_duplicates(text_b, text_a)

        self.assertTrue(res.is_candidate)
        self.assertFalse(res.is_duplicate)
        self.assertFalse(res.safety_guard_passed)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_phase411_expand_vs_reduce_inflections_rejected(self) -> None:
        """Phase 4.11: Confirms inflected forms (expands/reduces, expanded/reduced, expanding/reducing) are rejected."""
        detector = NearDuplicateDetector(threshold=0.75)

        # 3rd-person singular present: expands vs reduces
        t1 = "The commission expands commercial groundwater extraction quotas along the coastal aquifer."
        t2 = "The commission reduces commercial groundwater extraction quotas along the coastal aquifer."
        r1 = detector.are_near_duplicates(t1, t2)
        self.assertFalse(r1.is_duplicate)
        self.assertEqual(r1.conflict_type, "POLARITY_INVERSION")

        # Past tense: expanded vs reduced
        t3 = "The commission expanded commercial groundwater extraction quotas along the coastal aquifer."
        t4 = "The commission reduced commercial groundwater extraction quotas along the coastal aquifer."
        r2 = detector.are_near_duplicates(t3, t4)
        self.assertFalse(r2.is_duplicate)
        self.assertEqual(r2.conflict_type, "POLARITY_INVERSION")

        # Present participle: expanding vs reducing
        t5 = "The commission is expanding commercial groundwater extraction quotas along the coastal aquifer."
        t6 = "The commission is reducing commercial groundwater extraction quotas along the coastal aquifer."
        r3 = detector.are_near_duplicates(t5, t6)
        self.assertFalse(r3.is_duplicate)
        self.assertEqual(r3.conflict_type, "POLARITY_INVERSION")

    def test_phase411_expand_vs_contract_antonym_rejected(self) -> None:
        """Phase 4.11: Confirms classical physical/economic antonyms expand vs contract are rejected."""
        detector = NearDuplicateDetector(threshold=0.75)
        t_exp = "The state environmental commission resolved to expand commercial groundwater extraction quotas along the coastal aquifer."
        t_con = "The state environmental commission resolved to contract commercial groundwater extraction quotas along the coastal aquifer."
        res = detector.are_near_duplicates(t_exp, t_con)
        self.assertFalse(res.is_duplicate)
        self.assertEqual(res.conflict_type, "POLARITY_INVERSION")

    def test_phase411_genuine_paraphrase_accepted(self) -> None:
        """Phase 4.11: Confirms genuine paraphrase (resolved vs decided) preserving meaning is accepted."""
        detector = NearDuplicateDetector(threshold=0.75)
        text_a = "The state environmental commission resolved to expand commercial groundwater extraction quotas along the coastal aquifer."
        text_b = "The state environmental commission decided to expand commercial groundwater extraction quotas along the coastal aquifer."

        res = detector.are_near_duplicates(text_a, text_b)
        self.assertTrue(res.is_candidate, "Lexical overlap should qualify as candidate")
        self.assertTrue(res.is_duplicate, "Genuine paraphrase must be accepted as near-duplicate")
        self.assertTrue(res.safety_guard_passed, "Safety guard should pass when assertions align")
        self.assertIsNone(res.conflict_type)

    # ── Phase 4.13 Regression Tests ──────────────────────────────────────────

    def test_phase413_containment_vessel_evidence_vs_no_evidence_rejected(self) -> None:
        """Phase 4.13 DEF-2: Confirms v8_dedup_test_018 (evidence vs no evidence) is blocked as NEGATION_INVERSION."""
        text_a = "The secondary containment vessel showed evidence of structural stress fracture under sustained pneumatic pressure."
        text_b = "The secondary containment vessel showed no evidence of structural stress fracture under sustained pneumatic pressure."

        detector = NearDuplicateDetector(threshold=0.75)

        # Forward order
        res_fwd = detector.are_near_duplicates(text_a, text_b)
        self.assertTrue(res_fwd.is_candidate, "High similarity must qualify for candidate screening")
        self.assertFalse(res_fwd.is_duplicate, "Evidence vs no evidence must NOT be merged")
        self.assertFalse(res_fwd.safety_guard_passed, "Safety guard must reject contradictory assertions")
        self.assertEqual(res_fwd.conflict_type, "NEGATION_INVERSION")

        # Reversed order
        res_rev = detector.are_near_duplicates(text_b, text_a)
        self.assertTrue(res_rev.is_candidate)
        self.assertFalse(res_rev.is_duplicate)
        self.assertFalse(res_rev.safety_guard_passed)
        self.assertEqual(res_rev.conflict_type, "NEGATION_INVERSION")

    def test_phase413_positive_vs_negative_claims_with_not_and_never(self) -> None:
        """Phase 4.13 DEF-2: Positive vs negative claims using 'not' and 'never' are rejected."""
        detector = NearDuplicateDetector(threshold=0.75)

        # not
        t1 = "The emergency fire suppression valve was activated immediately upon detection of smoke."
        t2 = "The emergency fire suppression valve was not activated immediately upon detection of smoke."
        r1 = detector.are_near_duplicates(t1, t2)
        self.assertFalse(r1.is_duplicate)
        self.assertEqual(r1.conflict_type, "NEGATION_INVERSION")

        # never vs easily
        t3 = "The automated safety control software can never bypass hardware emergency interlocks."
        t4 = "The automated safety control software can easily bypass hardware emergency interlocks."
        r2 = detector.are_near_duplicates(t3, t4)
        self.assertFalse(r2.is_duplicate)
        self.assertEqual(r2.conflict_type, "NEGATION_INVERSION")

    def test_phase413_negative_contractions_rejected(self) -> None:
        """Phase 4.13 DEF-2: Negative contractions (wasn't, isn't, couldn't) trigger NEGATION_INVERSION."""
        detector = NearDuplicateDetector(threshold=0.75)

        # wasn't vs was
        t1 = "The secondary cooling circuit was deployed during the transient."
        t2 = "The secondary cooling circuit wasn't deployed during the transient."
        r1 = detector.are_near_duplicates(t1, t2)
        self.assertFalse(r1.is_duplicate)
        self.assertEqual(r1.conflict_type, "NEGATION_INVERSION")

        # isn't vs is
        t3 = "The monitoring telemetry sensor is functioning within standard manufacturer tolerances."
        t4 = "The monitoring telemetry sensor isn't functioning within standard manufacturer tolerances."
        r2 = detector.are_near_duplicates(t3, t4)
        self.assertFalse(r2.is_duplicate)
        self.assertEqual(r2.conflict_type, "NEGATION_INVERSION")

        # couldn't vs could
        t5 = "Control room operators could override the automated reactor trip sequence manually."
        t6 = "Control room operators couldn't override the automated reactor trip sequence manually."
        r3 = detector.are_near_duplicates(t5, t6)
        self.assertFalse(r3.is_duplicate)
        self.assertEqual(r3.conflict_type, "NEGATION_INVERSION")

    def test_phase413_abbreviation_no_does_not_trigger_false_negation(self) -> None:
        """Phase 4.13 DEF-2: 'No.' as abbreviation for number does NOT trigger false negation conflict."""
        detector = NearDuplicateDetector(threshold=0.75)
        text_a = "Diagnostic telemetry from autonomous seabed Rover No. 5 confirmed normal motor torque and battery status."
        text_b = "Diagnostic telemetry from autonomous seabed Rover Number 5 confirmed normal motor torque and battery status."

        res = detector.are_near_duplicates(text_a, text_b)
        self.assertTrue(res.is_candidate)
        self.assertTrue(res.is_duplicate, "No. 5 vs Number 5 should be accepted as near-duplicates")
        self.assertTrue(res.safety_guard_passed)
        self.assertIsNone(res.conflict_type)

    def test_phase413_two_equivalent_negative_statements_eligible_for_merge(self) -> None:
        """Phase 4.13 DEF-2: Two statements both asserting negative claims are eligible for deduplication."""
        detector = NearDuplicateDetector(threshold=0.75)
        text_a = "The secondary containment vessel showed no evidence of structural stress fracture under sustained pneumatic pressure."
        text_b = "The secondary containment vessel showed no signs of structural stress fracture under sustained pneumatic pressure."

        res = detector.are_near_duplicates(text_a, text_b)
        self.assertTrue(res.is_candidate)
        self.assertTrue(res.is_duplicate, "Equivalent negative claims should merge")
        self.assertTrue(res.safety_guard_passed)
        self.assertIsNone(res.conflict_type)


if __name__ == "__main__":
    unittest.main()



