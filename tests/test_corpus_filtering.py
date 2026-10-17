"""
VEDA Quality & Language Filtering Tests (Phase 4 — Training Corpus Architecture)

Validates adherence to docs/corpus_quality_policy.md:
- Accepts grammatical, natural English prose with high quality score.
- Rejects empty, too short, and too long inputs.
- Rejects non-Latin scripts, corrupted symbol noise, and repetition loops.
- Rejects boilerplate legal notices and cookie banners.
"""

from foundation.corpus.filtering import QualityFilter
from foundation.corpus.schemas import RejectionReason


class TestQualityFilter:
    """Test suite for QualityFilter."""

    def setup_method(self):
        self.filter = QualityFilter()

    def test_valid_english_prose_accepted(self):
        text = (
            "The development of linguistic competence requires exposure to diverse, "
            "coherent discourse across multiple contexts. Through disciplined observation, "
            "we discover fundamental statistical structures."
        )
        dec = self.filter.evaluate(text)
        assert dec.is_accepted is True
        assert dec.rejection_reason is None
        assert dec.quality_score >= 0.75
        assert dec.metrics.alpha_ratio > 0.75

    def test_empty_text_rejected(self):
        dec = self.filter.evaluate("")
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.EMPTY_TEXT

    def test_too_short_chars_rejected(self):
        dec = self.filter.evaluate("Too short.")
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.TOO_SHORT_CHARS
        assert dec.failed_metric == "char_length"

    def test_too_short_words_rejected(self):
        # 36 characters (passes min_char_length >= 25) but only 2 words (< 4 words)
        dec = self.filter.evaluate("Antidisestablishmentarianism exists.")
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.TOO_SHORT_WORDS
        assert dec.failed_metric == "word_count"

    def test_too_long_chars_rejected(self):
        massive_text = "word " * 3500  # > 15,000 chars
        dec = self.filter.evaluate(massive_text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.TOO_LONG_CHARS

    def test_non_latin_script_rejected(self):
        hindi_text = "नमस्ते दोस्तों, यह एक हिंदी वाक्य है जो मॉडल में नहीं जाना चाहिए।"
        dec = self.filter.evaluate(hindi_text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.NON_ENGLISH_SCRIPT

    def test_low_alpha_ratio_rejected(self):
        ascii_table = "+-------+-------+-------+\n| 12345 | 67890 | 00000 |\n+-------+-------+-------+"
        dec = self.filter.evaluate(ascii_table)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.LOW_ALPHA_RATIO

    def test_high_symbol_ratio_rejected(self):
        code_fragment = "if (x > y) { return arr[i] * matrix[j][k] + (val / 100); };"
        dec = self.filter.evaluate(code_fragment)
        assert dec.is_accepted is False
        assert dec.rejection_reason in (RejectionReason.HIGH_SYMBOL_RATIO, RejectionReason.LOW_ALPHA_RATIO)

    def test_character_repetition_loop_rejected(self):
        text = "This is a sentence with a runaway mash aaaaaaaaaaaaaaaaaa inside it."
        dec = self.filter.evaluate(text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.REPEATED_CHARS

    def test_word_repetition_loop_rejected(self):
        text = "The model was trapped in a loop the the the the the that never ended."
        dec = self.filter.evaluate(text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.REPEATED_WORDS

    def test_boilerplate_notice_rejected(self):
        text = "All rights reserved. Terms of service and privacy policy apply to all users."
        dec = self.filter.evaluate(text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.BOILERPLATE_CONTENT

    def test_no_english_stopwords_rejected_for_long_text(self):
        # Long sequence of words lacking standard English function words
        text = "Pneumonoultramicroscopicsilicovolcanoconiosis pseudopseudohypoparathyroidism floccinaucinihilipilification antidisestablishmentarianism honorificabilitudinitatibus supercalifragilisticexpialidocious incomprehensibilities interdenominationalism uncharacteristically compartmentalization photoelectroluminescence psychophysicotherapeutics radioimmunoelectrophoresis spectrophotofluorometrically hepaticocholangiocholecystenterostomies"
        dec = self.filter.evaluate(text)
        assert dec.is_accepted is False
        assert dec.rejection_reason == RejectionReason.NO_ENGLISH_STOPWORDS
