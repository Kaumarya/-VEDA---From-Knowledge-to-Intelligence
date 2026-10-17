"""
VEDA Text Normalization Tests (Phase 4 — Training Corpus Architecture)

Validates adherence to docs/corpus_normalization_policy.md:
- Preserves authentic capitalization (never lowercases).
- Normalizes Unicode to NFC.
- Standardizes linebreaks and collapses redundant whitespace.
- Strips non-linguistic control characters & null bytes.
- Preserves registered typographical quotes, dashes, and symbols.
"""

from foundation.corpus.normalization import TextNormalizer


class TestTextNormalizer:
    """Test suite for TextNormalizer."""

    def setup_method(self):
        self.normalizer = TextNormalizer()

    def test_preserves_authentic_casing(self):
        text = "The Apple Corporation was founded in California. NASA launched Voyager."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == text
        assert "Apple" in res.normalized_text
        assert "NASA" in res.normalized_text
        assert "California" in res.normalized_text

    def test_line_ending_standardization(self):
        crlf_text = "First line.\r\nSecond line.\rThird line.\nFourth line."
        res = self.normalizer.normalize(crlf_text)
        assert "\r" not in res.normalized_text
        assert res.normalized_text == "First line.\nSecond line.\nThird line.\nFourth line."
        assert "newline_standardize" in res.applied_transforms

    def test_whitespace_consolidation(self):
        text = "This   sentence\thas    irregular\u00a0spacing."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == "This sentence has irregular spacing."
        assert "whitespace_collapse" in res.applied_transforms

    def test_vertical_whitespace_consolidation(self):
        text = "Paragraph one.\n\n\n\n\nParagraph two."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == "Paragraph one.\n\nParagraph two."

    def test_control_character_stripping(self):
        text = "Clean text\x00with null\x07and bell\x1fcontrols."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == "Clean textwith nulland bellcontrols."
        assert "strip_control_chars" in res.applied_transforms

    def test_html_tag_stripping_and_entity_decoding(self):
        text = "<p>This is <b>bold</b> text &amp; &quot;quoted&quot;.</p>"
        res = self.normalizer.normalize(text)
        assert res.normalized_text == 'This is bold text & "quoted".'
        assert "html_tag_strip" in res.applied_transforms
        assert "html_unescape" in res.applied_transforms

    def test_preserves_registered_typographical_quotes_and_dashes(self):
        text = "“It’s a marvelous discovery,” she said—with great enthusiasm."
        res = self.normalizer.normalize(text)
        # All curly quotes and em-dash are registered; must remain intact
        assert res.normalized_text == text

    def test_standardizes_running_dots_to_ellipsis(self):
        text = "Waiting for the results... they finally arrived."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == "Waiting for the results… they finally arrived."
        assert "standardize_ellipsis" in res.applied_transforms

    def test_standardizes_typewriter_dashes(self):
        text = "The truth--if we dare admit it--is simple."
        res = self.normalizer.normalize(text)
        assert res.normalized_text == "The truth—if we dare admit it—is simple."
        assert "standardize_dashes" in res.applied_transforms

    def test_empty_and_whitespace_only_input(self):
        res_empty = self.normalizer.normalize("")
        assert res_empty.normalized_text == ""
        assert res_empty.is_modified is False

        res_ws = self.normalizer.normalize("   \t  \n\n  ")
        assert res_ws.normalized_text == ""
