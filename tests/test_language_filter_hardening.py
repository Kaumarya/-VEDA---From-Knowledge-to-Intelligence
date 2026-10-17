"""
VEDA Phase 4.5 Language Filter Hardening & Defect Sweep Tests

Verifies:
1. Academic figure and table captions are accepted (v3_test_cap_001).
2. German sentences with cognates are routed to quarantine instead of blind rejection (v3_test_de_002).
3. Non-English Latin texts lacking cognates are rejected deterministically.
4. Raw SQL queries and code structures are routed to quarantine.
5. Empty strings and whitespace-only strings evaluate to EMPTY_TEXT.
6. Type validation on non-string inputs across all corpus processors.
"""

from __future__ import annotations

import unittest
from foundation.corpus.filtering import QualityFilter, RejectionReason
from foundation.corpus.language_audit import classify_with_quarantine
from foundation.corpus.normalization import TextNormalizer


class TestLanguageFilterHardening(unittest.TestCase):
    def setUp(self) -> None:
        self.qf = QualityFilter()
        self.normalizer = TextNormalizer()

    def test_academic_figure_caption_accepted(self) -> None:
        """Confirms legitimate academic figure/table captions are ACCEPTED."""
        caption = "Figure 3. Representative electron micrographs showing mitochondrial morphology in control versus treated cortical neurons."
        res = classify_with_quarantine(caption, self.qf)
        self.assertEqual(res["outcome"], "ACCEPT")
        self.assertEqual(res["reason"], "FLUENT_ACADEMIC_CAPTION")

        table_caption = "Table 2: Measured thermodynamic activation parameters for substituted benzaldehydes in aqueous solution."
        res2 = classify_with_quarantine(table_caption, self.qf)
        self.assertEqual(res2["outcome"], "ACCEPT")
        self.assertEqual(res2["reason"], "FLUENT_ACADEMIC_CAPTION")

    def test_german_sentence_routed_to_quarantine(self) -> None:
        """Confirms German text with cognates is routed to QUARANTINE instead of blind REJECT."""
        german_text = "Es ist in der Tat eine sehr ernste Situation fuer alle Beteiligten in diesem Land."
        res = classify_with_quarantine(german_text, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_dutch_sentence_routed_to_quarantine(self) -> None:
        """Confirms Dutch text with Germanic cognates is routed to QUARANTINE."""
        dutch_text = "Het Nederlands is een West-Germaanse taal die gesproken wordt door miljoenen mensen."
        res = classify_with_quarantine(dutch_text, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_foreign_latin_without_cognates_rejected(self) -> None:
        """Confirms French, Spanish, and Italian texts without English cognates are REJECTED.

        Phase 4.10 Audit: Spanish text containing 'de' must evaluate to REJECT.
        'de' is multilingual (Spanish/French preposition, Dutch article) and intentionally
        kept in _AMBIGUOUS_COGNATE_STOPWORDS rather than _GERMANIC_COGNATES.
        Therefore, Romance Latin prose without English stopwords is deterministically REJECTED.
        """
        french_text = "Tant qu'il existera, par le fait des lois et des mœurs, une damnation sociale créant des enfers."
        res = classify_with_quarantine(french_text, self.qf)
        self.assertEqual(res["outcome"], "REJECT")

        spanish_text = "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho tiempo que vivía un hidalgo."
        res_es = classify_with_quarantine(spanish_text, self.qf)
        self.assertEqual(res_es["outcome"], "REJECT")
        self.assertEqual(res_es["reason"], "NO_ENGLISH_STOPWORDS")

    def test_sql_query_quarantined(self) -> None:
        """Confirms raw SQL queries are routed to QUARANTINE."""
        sql_query = "SELECT user_id, email, created_at FROM production_users WHERE is_active = 1 ORDER BY created_at DESC LIMIT 50;"
        res = classify_with_quarantine(sql_query, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "CODE_SQL_QUERY_DATA")

    def test_whitespace_only_evaluated_as_empty_text(self) -> None:
        """Confirms whitespace-only strings evaluate to EMPTY_TEXT rejection reason."""
        decision = self.qf.evaluate("   \n\t   \r\n   ")
        self.assertFalse(decision.is_accepted)
        self.assertEqual(decision.rejection_reason, RejectionReason.EMPTY_TEXT)

    def test_empty_string_evaluated_as_empty_text(self) -> None:
        """Confirms empty strings evaluate to EMPTY_TEXT rejection reason."""
        decision = self.qf.evaluate("")
        self.assertFalse(decision.is_accepted)
        self.assertEqual(decision.rejection_reason, RejectionReason.EMPTY_TEXT)

    def test_type_validation_on_non_string_inputs(self) -> None:
        """Confirms TypeError is raised when non-string objects are passed."""
        with self.assertRaises(TypeError):
            self.normalizer.normalize(12345)  # type: ignore

        with self.assertRaises(TypeError):
            self.qf.evaluate(None)  # type: ignore

        with self.assertRaises(TypeError):
            self.qf.compute_metrics(b"bytes are not str")  # type: ignore

        with self.assertRaises(TypeError):
            classify_with_quarantine({"key": "value"})  # type: ignore

    def test_foreign_academic_figure_caption_rejected(self) -> None:
        """Confirms foreign Latin-script captions are NOT accepted as English prose (DEF-4.7-01)."""
        french_cap = "Figure 1: Schema du circuit montrant anode et cathode dans le reservoir liquide."
        res_fr = classify_with_quarantine(french_cap, self.qf)
        self.assertNotEqual(res_fr["outcome"], "ACCEPT")

        german_cap = "Abbildung 3: Schematische Darstellung der Versuchsanordnung mit Temperaturmessung."
        res_de = classify_with_quarantine(german_cap, self.qf)
        self.assertNotEqual(res_de["outcome"], "ACCEPT")

        spanish_cap = "Figura 4: Diagrama de fases para el sistema binario en funcion de la temperatura."
        res_es = classify_with_quarantine(spanish_cap, self.qf)
        self.assertNotEqual(res_es["outcome"], "ACCEPT")

    def test_english_imperative_prose_not_misidentified_as_sql(self) -> None:
        """Confirms ordinary English prose imperatives are ACCEPTED and not quarantined as SQL (DEF-4.7-02)."""
        prose_select = "Select an option from the menu below to proceed with the transaction."
        res_sel = classify_with_quarantine(prose_select, self.qf)
        self.assertEqual(res_sel["outcome"], "ACCEPT")

        prose_create = "Create a new document by clicking on the main toolbar icon."
        res_cre = classify_with_quarantine(prose_create, self.qf)
        self.assertEqual(res_cre["outcome"], "ACCEPT")

        prose_update = "Update your preferences in the profile settings page regularly."
        res_upd = classify_with_quarantine(prose_update, self.qf)
        self.assertEqual(res_upd["outcome"], "ACCEPT")


    def test_dutch_sentence_with_zero_english_stopwords_quarantined(self) -> None:
        """Regression test for DEF-4.8: Dutch prose with 0 English stopwords routes to QUARANTINE."""
        dutch_text = "De windmolens langs de polderkanalen speelden een cruciale rol bij het droogleggen van de laaggelegen landerijen."
        res = classify_with_quarantine(dutch_text, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_german_caption_with_zero_english_stopwords_quarantined(self) -> None:
        """Regression test for DEF-4.8: German caption with 0 English stopwords routes to QUARANTINE."""
        german_cap = "Abbildung 13: Gemessene Strom-Spannungs-Kennlinie der Halbleiterdiode bei Raumtemperatur."
        res = classify_with_quarantine(german_cap, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_french_caption_with_des_rejected(self) -> None:
        """Regression test for DEF-4.8: French text containing 'des' is REJECTED and not misclassified as Germanic."""
        french_cap = "Tableau 12: Valeurs moyennes des constantes elastiques determinees par methode ultrasonore sous vide."
        res = classify_with_quarantine(french_cap, self.qf)
        self.assertEqual(res["outcome"], "REJECT")

    # ── Phase 4.10 Regression Tests ──────────────────────────────────────────

    def test_phase410_dense_academic_english_with_only_in_accepted(self) -> None:
        """Phase 4.10 DEF-A: Dense scientific English with sole stopword 'in' must ACCEPT.

        Root cause: Quarantine Rule A (OR condition) fired when found_sws was a
        subset of _AMBIGUOUS_COGNATE_STOPWORDS even with zero foreign cognates.
        Fix: Changed OR to AND—ambiguous stopwords alone are insufficient for quarantine.
        """
        text = "Fourier transform infrared spectroscopy characterizes vibrational molecular absorption bands in synthetic polymeric thin films."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "ACCEPT")
        self.assertEqual(res["reason"], "FLUENT_ENGLISH_PROSE")

    def test_phase410_dense_academic_english_with_only_for_accepted(self) -> None:
        """Phase 4.10 DEF-A: Dense scientific English with sole stopword 'for' must ACCEPT."""
        text = "Synchrotron radiation sources produce intense collimated monochromatic X-ray beams for macromolecular crystallography."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "ACCEPT")
        self.assertEqual(res["reason"], "FLUENT_ENGLISH_PROSE")

    def test_phase410_dense_academic_english_with_in_and_a_accepted(self) -> None:
        """Phase 4.10 DEF-A: Dense scientific English with stopwords 'in' + 'a' must ACCEPT."""
        text = "Cellular apoptosis initiates a controlled proteolytic caspase cascade resulting in systematic non-inflammatory cell clearance."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "ACCEPT")
        self.assertEqual(res["reason"], "FLUENT_ENGLISH_PROSE")

    def test_phase410_dutch_text_with_aan_quarantined_not_rejected(self) -> None:
        """Phase 4.10 DEF-B: Dutch text with 'aan' must be QUARANTINED, not REJECTED.

        Root cause: 'aan' (Dutch preposition 'to/at') was missing from _GERMANIC_COGNATES,
        causing Dutch text lacking sufficient English stopwords to fall through to rejection.
        Fix: Added 'aan' to _GERMANIC_COGNATES while keeping ambiguous 'de' excluded.
        """
        text = "De moderne windturbines in de Noordzee leveren duurzame elektrische stroom aan duizenden huishoudens in West-Europa."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    def test_phase410_dutch_text_with_voor_quarantined(self) -> None:
        """Phase 4.10 DEF-B2: Dutch text with 'voor' must be QUARANTINED, not REJECTED."""
        text = "De moderne windturbines in de Noordzee leveren duurzame elektrische energie voor miljoenen huishoudens."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "QUARANTINE")
        self.assertEqual(res["reason"], "BORDERLINE_STOPWORDS_COGNATE_RISK")

    # ── Phase 4.13 Regression Tests ──────────────────────────────────────────

    def test_phase413_offshore_wind_technical_sentence_accepted(self) -> None:
        """Phase 4.13 DEF-1: Offshore wind technical sentence with sole distinct stopword 'to' must ACCEPT.

        Original failure: 15-word sentence with distinct stopword count = 1 ('to' used twice).
        QualityFilter required >= 2 stopwords when word_count >= 15, rejecting fluent English.
        """
        text = "Offshore wind installations utilize heavy subsea power cables to transmit alternating current to mainland substations."
        res = classify_with_quarantine(text, self.qf)
        self.assertEqual(res["outcome"], "ACCEPT")
        self.assertEqual(res["reason"], "FLUENT_ENGLISH_PROSE")

    def test_phase413_all_phase412_technical_failures_accepted(self) -> None:
        """Phase 4.13 DEF-1: All 4 technical sentences identified in Phase 4.12 report must ACCEPT."""
        sentences = [
            # v8_lang_test_001
            "Offshore wind installations utilize heavy subsea power cables to transmit alternating current to mainland substations.",
            # v8_lang_test_002
            "Agricultural extension agents advised grain farmers to rotate legume crops to naturally replenish soil nitrogen reserves.",
            # v8_lang_test_015
            "Ubiquitin ligase cascades catalyze covalent substrate polyubiquitination and direct misfolded proteins toward twenty-six S proteasomal degradation.",
            # v8_lang_test_017
            "Anthropological linguistics explores how spatial cognitive reference frames vary systematically across unrelated indigenous language families.",
        ]
        for s in sentences:
            res = classify_with_quarantine(s, self.qf)
            self.assertEqual(res["outcome"], "ACCEPT", f"Failed on: {s}")
            self.assertEqual(res["reason"], "FLUENT_ENGLISH_PROSE")

    def test_phase413_independently_authored_technical_sentences_accepted(self) -> None:
        """Phase 4.13 DEF-1: Independently authored dense English technical prose with few stopwords must ACCEPT."""
        cases = [
            "Cryogenic turbopump impellers deliver liquid hydrogen propellant directly toward rocket combustion chambers.",
            "Superconducting quantum interference devices detect minute magnetic flux variations inside shielded laboratory enclosures.",
            "Autonomous underwater oceanographic submersibles map deep benthic hydrothermal vent chimneys along active midocean volcanic spreading centers.",
            "Seismic accelerometers record high-frequency ground motion waveforms across active tectonic rift zones.",
        ]
        for c in cases:
            res = classify_with_quarantine(c, self.qf)
            self.assertEqual(res["outcome"], "ACCEPT", f"Failed on: {c}")

    def test_phase413_spanish_with_de_and_no_strictly_rejected(self) -> None:
        """Phase 4.13: Spanish text containing 'de' and 'no' must evaluate to REJECT with NO_ENGLISH_STOPWORDS.

        Ensures that accepting 1-stopword English technical sentences does not cause false accepts of Romance prose.
        """
        spanish_text = "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho tiempo que vivía un hidalgo."
        res = classify_with_quarantine(spanish_text, self.qf)
        self.assertEqual(res["outcome"], "REJECT")
        self.assertEqual(res["reason"], "NO_ENGLISH_STOPWORDS")

    def test_phase413_french_and_italian_prose_strictly_rejected(self) -> None:
        """Phase 4.13: French and Italian prose without English stopwords must evaluate to REJECT."""
        french_text = "Les proprietes rheologiques des fluides non newtoniens dependent fortement de la vitesse de cisaillement appliquee."
        res_fr = classify_with_quarantine(french_text, self.qf)
        self.assertEqual(res_fr["outcome"], "REJECT")

        italian_text = "La presenza di campi magnetici intensi influenza la traiettoria delle particelle cariche nel plasma stellare."
        res_it = classify_with_quarantine(italian_text, self.qf)
        self.assertEqual(res_it["outcome"], "REJECT")

    def test_phase413_short_technical_headings_quarantined_not_rejected(self) -> None:
        """Phase 4.13: Short technical headings (8-11 words, clean Latin) must route to QUARANTINE."""
        heading_1 = "Chapter 4: Advanced Solid-State Nuclear Magnetic Resonance Spectroscopy Techniques."
        res_1 = classify_with_quarantine(heading_1, self.qf)
        self.assertEqual(res_1["outcome"], "QUARANTINE")
        self.assertEqual(res_1["reason"], "SHORT_HEADING_LOW_STOPWORD_DENSITY")

        heading_2 = "Part III: Computational Fluid Dynamics Grid Generation Algorithms."
        res_2 = classify_with_quarantine(heading_2, self.qf)
        self.assertEqual(res_2["outcome"], "QUARANTINE")
        self.assertEqual(res_2["reason"], "SHORT_HEADING_LOW_STOPWORD_DENSITY")


if __name__ == "__main__":
    unittest.main()


