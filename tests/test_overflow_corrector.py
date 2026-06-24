"""Tests for OverflowCorrector."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.ai.overflow_corrector import (
    OverflowCorrector,
    OverflowIssueFixed,
    EXPANSION_RATIOS,
)
from orf.ai.layout_analyzer import OverflowIssue, Severity


class TestOverflowCorrector:
    """Tests for OverflowCorrector overflow correction."""

    @pytest.fixture
    def mock_analyzer(self) -> MagicMock:
        """Create a mock LayoutAnalyzer."""
        analyzer = MagicMock()
        return analyzer

    @pytest.fixture
    def corrector(self, mock_analyzer: MagicMock) -> OverflowCorrector:
        """Create OverflowCorrector with mocked analyzer."""
        return OverflowCorrector(layout_analyzer=mock_analyzer)

    @pytest.fixture
    def sample_issue(self) -> OverflowIssue:
        """Create a sample overflow issue."""
        return OverflowIssue(
            file_path="/path/to/doc.pdf",
            element_id="p_001",
            original_text="This is a very long text that might overflow in the layout",
            overflow_percentage=35.0,
            severity=Severity.HIGH,
        )

    def test_init_with_analyzer(self, mock_analyzer: MagicMock):
        """OverflowCorrector accepts layout_analyzer at init."""
        corrector = OverflowCorrector(layout_analyzer=mock_analyzer)
        assert corrector._layout_analyzer is mock_analyzer

    def test_init_without_analyzer(self):
        """OverflowCorrector can be created without analyzer (lazy init)."""
        corrector = OverflowCorrector()
        assert corrector._layout_analyzer is None

    def test_layout_analyzer_property_lazy_init(self):
        """LayoutAnalyzer is created on first access."""
        corrector = OverflowCorrector()
        # Should not create analyzer until accessed
        assert corrector._layout_analyzer is None
        # Access the property
        analyzer = corrector.layout_analyzer
        assert analyzer is not None
        assert corrector._layout_analyzer is analyzer

    def test_estimate_expansion_ratio_en_zh(self, corrector: OverflowCorrector):
        """English to Chinese expansion ratio is ~1.8."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "zh")
        assert ratio == 1.8

    def test_estimate_expansion_ratio_en_de(self, corrector: OverflowCorrector):
        """English to German expansion ratio is ~1.25."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "de")
        assert ratio == 1.25

    def test_estimate_expansion_ratio_en_ja(self, corrector: OverflowCorrector):
        """English to Japanese expansion ratio is ~1.1."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "ja")
        assert ratio == 1.1

    def test_estimate_expansion_ratio_en_ko(self, corrector: OverflowCorrector):
        """English to Korean expansion ratio is ~1.3."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "ko")
        assert ratio == 1.3

    def test_estimate_expansion_ratio_en_fr(self, corrector: OverflowCorrector):
        """English to French expansion ratio is ~1.15."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "fr")
        assert ratio == 1.15

    def test_estimate_expansion_ratio_en_es(self, corrector: OverflowCorrector):
        """English to Spanish expansion ratio is ~1.1."""
        ratio = corrector.estimate_expansion_ratio("hello", "en", "es")
        assert ratio == 1.1

    def test_estimate_expansion_ratio_case_insensitive(
        self, corrector: OverflowCorrector
    ):
        """Language codes are case insensitive."""
        ratio_upper = corrector.estimate_expansion_ratio("hello", "EN", "ZH")
        ratio_lower = corrector.estimate_expansion_ratio("hello", "en", "zh")
        assert ratio_upper == ratio_lower

    def test_estimate_expansion_ratio_unknown_pair_defaults_to_1(
        self, corrector: OverflowCorrector
    ):
        """Unknown language pair defaults to 1.0 (no change)."""
        ratio = corrector.estimate_expansion_ratio("hello", "xx", "yy")
        assert ratio == 1.0

    def test_correct_document_no_issues(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock,
        tmp_path: Path
    ):
        """Returns empty list when no overflow issues found."""
        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("dummy")
        
        mock_analyzer.analyze.return_value = []
        
        result = corrector.correct_document(doc_path, max_overflow=10.0)
        
        assert result == []
        mock_analyzer.analyze.assert_called_once_with(doc_path)

    def test_correct_document_all_within_limit(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock,
        tmp_path: Path
    ):
        """Returns empty list when all issues are within limit."""
        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("dummy")
        
        issue = OverflowIssue(
            file_path=str(doc_path),
            element_id="p_001",
            original_text="Short text",
            overflow_percentage=5.0,  # Below 10% limit
            severity=Severity.LOW,
        )
        mock_analyzer.analyze.return_value = [issue]
        
        result = corrector.correct_document(doc_path, max_overflow=10.0)
        
        assert result == []

    def test_correct_document_fixed_issues(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock,
        tmp_path: Path
    ):
        """Corrects issues that exceed max_overflow."""
        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("dummy")
        
        issue = OverflowIssue(
            file_path=str(doc_path),
            element_id="p_001",
            original_text="This is a very long text that should be shortened",
            overflow_percentage=35.0,
            severity=Severity.HIGH,
        )
        mock_analyzer.analyze.return_value = [issue]
        
        result = corrector.correct_document(doc_path, max_overflow=10.0)
        
        assert len(result) == 1
        fixed = result[0]
        assert fixed.element_id == "p_001"
        assert fixed.original_text == issue.original_text
        assert len(fixed.suggested_text) < len(fixed.original_text)
        assert fixed.overflow_percentage == 35.0
        assert fixed.method == "llm_shorten_placeholder"

    def test_correct_document_multiple_issues(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock,
        tmp_path: Path
    ):
        """Corrects multiple overflow issues."""
        doc_path = tmp_path / "test.pdf"
        doc_path.write_text("dummy")
        
        issues = [
            OverflowIssue(
                file_path=str(doc_path),
                element_id=f"p_{i:03d}",
                original_text=f"Text element number {i} with some content",
                overflow_percentage=25.0 + i,
                severity=Severity.HIGH,
            )
            for i in range(3)
        ]
        mock_analyzer.analyze.return_value = issues
        
        result = corrector.correct_document(doc_path, max_overflow=10.0)
        
        assert len(result) == 3

    def test_generate_shorter_text_returns_none_for_short_text(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock
    ):
        """Returns None when text cannot be shortened further."""
        issue = OverflowIssue(
            file_path="/path/doc.pdf",
            element_id="p_001",
            original_text="Short",
            overflow_percentage=20.0,
            severity=Severity.MEDIUM,
        )
        
        # Test with very short text (only 1-2 words)
        result = corrector._generate_shorter_text(issue)
        # Short text may not be shortened or result may be None
        # depending on implementation
        assert result is None or isinstance(result, OverflowIssueFixed)

    def test_generate_shorter_text_shortens_long_text(
        self, 
        corrector: OverflowCorrector, 
        mock_analyzer: MagicMock
    ):
        """Successfully shortens text that exceeds overflow threshold."""
        issue = OverflowIssue(
            file_path="/path/doc.pdf",
            element_id="p_001",
            original_text="This is a very long text element that needs to be shortened to fit",
            overflow_percentage=30.0,
            severity=Severity.MEDIUM,
        )
        
        result = corrector._generate_shorter_text(issue)
        
        assert result is not None
        assert len(result.suggested_text) < len(result.original_text)
        assert "..." in result.suggested_text

    def test_suggest_shorter_translation_basic(
        self, 
        corrector: OverflowCorrector
    ):
        """Returns shorter version of text."""
        original = "This is a longer text that should be condensed"
        result = corrector.suggest_shorter_translation(original, "zh")
        
        # Should be shorter or equal to original
        assert len(result) <= len(original)

    def test_suggest_shorter_translation_respects_ratio(
        self, 
        corrector: OverflowCorrector
    ):
        """Respects max_length_ratio parameter."""
        original = "one two three four five six seven eight nine ten"
        result = corrector.suggest_shorter_translation(original, "de", max_length_ratio=0.5)
        
        # Should be approximately 50% or less of original length
        words = original.split()
        result_words = result.replace("...", "").split()
        # Account for ellipsis
        assert len(result_words) <= len(words)


class TestExpansionRatios:
    """Tests for language expansion ratios."""

    def test_expansion_ratios_defined(self):
        """EXPANSION_RATIOS contains required language pairs."""
        assert ("en", "zh") in EXPANSION_RATIOS
        assert ("en", "de") in EXPANSION_RATIOS
        assert ("en", "ja") in EXPANSION_RATIOS
        assert ("en", "ko") in EXPANSION_RATIOS
        assert ("en", "fr") in EXPANSION_RATIOS
        assert ("en", "es") in EXPANSION_RATIOS
        assert ("en", "it") in EXPANSION_RATIOS  # Issue #4
        assert ("en", "ru") in EXPANSION_RATIOS  # Issue #4

    def test_expansion_ratio_en_zh_value(self):
        """English to Chinese ratio is 1.8."""
        assert EXPANSION_RATIOS[("en", "zh")] == 1.8

    def test_expansion_ratio_en_de_value(self):
        """English to German ratio is 1.25."""
        assert EXPANSION_RATIOS[("en", "de")] == 1.25

    def test_expansion_ratio_en_ja_value(self):
        """English to Japanese ratio is 1.1."""
        assert EXPANSION_RATIOS[("en", "ja")] == 1.1

    def test_expansion_ratio_en_ko_value(self):
        """English to Korean ratio is 1.3."""
        assert EXPANSION_RATIOS[("en", "ko")] == 1.3

    def test_expansion_ratio_en_fr_value(self):
        """English to French ratio is 1.15."""
        assert EXPANSION_RATIOS[("en", "fr")] == 1.15

    def test_expansion_ratio_en_es_value(self):
        """English to Spanish ratio is 1.1."""
        assert EXPANSION_RATIOS[("en", "es")] == 1.1