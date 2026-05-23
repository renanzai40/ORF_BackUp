"""Tests for AI-powered layout analyzer."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.ai.layout_analyzer import LayoutAnalyzer, OverflowIssue, OverflowFix, Severity


@pytest.fixture
def sample_document(tmp_path: Path) -> Path:
    """Create a sample document for testing."""
    doc_path = tmp_path / "test.md"
    doc_path.write_text("# Test Document\n\nSome content here.")
    return doc_path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a sample PDF for testing."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test content")
    return pdf_path


class TestOverflowIssue:
    """Test OverflowIssue dataclass."""

    def test_creation_with_defaults(self):
        """Test creating an OverflowIssue with default severity."""
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Sample text",
            overflow_percentage=5.0,
            severity=Severity.LOW
        )
        assert issue.file_path == "/test/doc.md"
        assert issue.element_id == "p_001"
        assert issue.original_text == "Sample text"
        assert issue.overflow_percentage == 5.0
        assert issue.severity == Severity.LOW

    def test_creation_with_high_overflow(self):
        """Test that overflow percentage affects severity."""
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Sample text",
            overflow_percentage=30.0,
            severity=Severity.LOW
        )
        # __post_init__ should upgrade severity
        assert issue.severity == Severity.HIGH

    def test_negative_overflow_clamped_to_zero(self):
        """Test that negative overflow is clamped to 0."""
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Sample text",
            overflow_percentage=-5.0,
            severity=Severity.LOW
        )
        assert issue.overflow_percentage == 0

    def test_overflow_over_100_clamped(self):
        """Test that overflow over 100 is clamped to 100."""
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Sample text",
            overflow_percentage=150.0,
            severity=Severity.LOW
        )
        assert issue.overflow_percentage == 100


class TestOverflowFix:
    """Test OverflowFix dataclass."""

    def test_creation(self):
        """Test creating an OverflowFix."""
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Sample text",
            overflow_percentage=15.0,
            severity=Severity.MEDIUM
        )
        fix = OverflowFix(
            issue=issue,
            suggested_text="Sample",
            reduction_percentage=50.0
        )
        assert fix.issue == issue
        assert fix.suggested_text == "Sample"
        assert fix.reduction_percentage == 50.0


class TestLayoutAnalyzer:
    """Test LayoutAnalyzer class."""

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        analyzer = LayoutAnalyzer()
        assert analyzer._api_key is None
        assert analyzer._vision_client is None

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        analyzer = LayoutAnalyzer(api_key="test-key")
        assert analyzer._api_key == "test-key"

    def test_set_api_key(self):
        """Test setting API key after initialization."""
        analyzer = LayoutAnalyzer()
        analyzer.set_api_key("new-key")
        assert analyzer._api_key == "new-key"

    def test_analyze_nonexistent_file(self, tmp_path: Path):
        """Test analyzing a nonexistent file returns empty list."""
        analyzer = LayoutAnalyzer()
        result = analyzer.analyze(tmp_path / "nonexistent.md")
        assert result == []

    def test_analyze_markdown_file(self, sample_document: Path):
        """Test analyzing a markdown file."""
        analyzer = LayoutAnalyzer()
        
        with patch.object(analyzer, '_render_to_images', return_value=[]) as mock_render:
            result = analyzer.analyze(sample_document)
            mock_render.assert_called_once_with(sample_document)
            assert result == []

    @patch('subprocess.run')
    def test_render_markup_falls_back_to_pandoc(self, mock_run, tmp_path: Path):
        """Test rendering markup uses pandoc."""
        mock_run.return_value = MagicMock(returncode=0)
        
        analyzer = LayoutAnalyzer()
        md_path = tmp_path / "test.md"
        md_path.write_text("# Test")
        
        with patch.object(analyzer, '_render_pdf', return_value=[]):
            images = analyzer._render_markup(md_path)
        
        # pandoc was attempted
        assert mock_run.called

    def test_fix_overflow_returns_mock_when_no_api_key(self):
        """Test fix_overflow returns mock when no API key."""
        analyzer = LayoutAnalyzer()
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="This is a long text that might overflow",
            overflow_percentage=15.0,
            severity=Severity.MEDIUM
        )
        
        fix = analyzer.fix_overflow(issue)
        assert fix is not None
        assert fix.suggested_text != issue.original_text

    def test_fix_overflow_preserves_short_text(self):
        """Test that fix_overflow preserves very short text."""
        analyzer = LayoutAnalyzer()
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="Hi",
            overflow_percentage=5.0,
            severity=Severity.LOW
        )
        
        fix = analyzer.fix_overflow(issue)
        assert fix is not None
        assert fix.suggested_text == "Hi"


class TestLayoutAnalyzerIntegration:
    """Integration tests with mocked vision API."""

    @patch.object(LayoutAnalyzer, '_render_to_images')
    @patch.object(LayoutAnalyzer, '_get_vision_client')
    def test_analyze_with_mocked_vision(self, mock_get_client, mock_render, sample_document: Path, tmp_path: Path):
        """Test analyze with mocked vision client."""
        mock_render.return_value = [tmp_path / "page1.png"]
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '[{"element_id": "p_001", "overflow_percentage": 15.5, "text": "Test text"}]'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        analyzer = LayoutAnalyzer(api_key="fake-key")
        result = analyzer.analyze(sample_document)
        
        assert len(result) == 1
        assert result[0].element_id == "p_001"
        assert result[0].overflow_percentage == 15.5

    @patch.object(LayoutAnalyzer, '_get_vision_client')
    def test_fix_overflow_with_mocked_llm(self, mock_get_client):
        """Test fix_overflow with mocked LLM."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"suggested_text": "Short", "reduction_percentage": 50}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        analyzer = LayoutAnalyzer(api_key="fake-key")
        issue = OverflowIssue(
            file_path="/test/doc.md",
            element_id="p_001",
            original_text="This is a very long text that should be shortened",
            overflow_percentage=25.0,
            severity=Severity.MEDIUM
        )
        
        fix = analyzer.fix_overflow(issue)
        assert fix is not None
        assert fix.suggested_text == "Short"


class TestSeverityEnum:
    """Test Severity enum."""

    def test_severity_values(self):
        """Test Severity enum values."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"

    def test_severity_is_enum(self):
        """Test that Severity is an Enum."""
        assert isinstance(Severity.LOW, Severity)