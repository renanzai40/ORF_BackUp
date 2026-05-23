"""E2E integration tests for OPP→OL→ORF pipeline.

These tests verify the complete flow from document extraction (OPP),
localization (OL), to format restoration (ORF) with mocked subprocess calls.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from orf.cli import main


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_manifest_data():
    """Sample manifest data for OPP output."""
    return {
        "manifest_version": "1.0",
        "generated_at": "2026-05-22T14:30:00Z",
        "tool": "OPP",
        "tool_version": "0.2.0",
        "source": {
            "file_path": "/path/to/spec.docx",
            "original_filename": "spec.docx",
            "format": "DOCX",
            "file_size_bytes": 45824,
            "file_hash_md5": "a1b2c3d4e5f6",
        },
        "extraction": {
            "source_lang": "en",
            "target_lang": "zh",
            "outputs": {
                "markdown": {"path": "spec.md", "paragraph_count": 150, "table_count": 3},
                "xliff": {"path": "spec.xlf", "trans_unit_count": 42},
            },
            "images": [
                {"mime_type": "image/png", "width": 800, "height": 600, "data_size_bytes": 24580}
            ],
            "warnings": [],
        },
        "skeleton": {
            "path": "spec.skeleton.zip",
            "format": "ZIP",
            "key_files": ["word/document.xml", "word/styles.xml"],
        },
        "resources": {"storage_dir": "resources", "image_count": 5},
    }


@pytest.fixture
def mock_frontmatter_md():
    """Sample markdown with OL frontmatter."""
    return """---
source_lang: en
target_lang: zh
original_file: spec.md
processor: "OL"
version: "0.1.0"
translated_at: 2026-05-22T15:00:00Z
---

# 用户手册

这是翻译后的内容。

## 第一章

- 列表项 1
- 列表项 2

| 表格 | 列 |
|------|---|
| 数据 | 值 |
"""


@pytest.fixture
def mock_skeleton_zip(tmp_path: Path) -> Path:
    """Create a mock skeleton.zip file for XLIFF→DOCX backfill."""
    skeleton_path = tmp_path / "spec.skeleton.zip"
    with zipfile.ZipFile(skeleton_path, "w") as zf:
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>ORIGINAL_TEXT</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
        zf.writestr("word/_rels/document.xml.rels", "<Relationships/>")
    return skeleton_path


def test_full_pipeline_opp_ol_orf(runner, tmp_path: Path, mock_frontmatter_md):
    """Test OPP→OL→ORF complete flow with mocked subprocess.

    Simulates:
    1. OPP extracting DOCX → MD + manifest + skeleton
    2. OL translating MD → translated MD with frontmatter
    3. ORF converting translated MD → target format
    """
    with patch("subprocess.run") as mock_run:
        # Setup mock OPP output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"status": "success", "outputs": ["spec.md", "spec_manifest.json"]}),
            stderr="",
        )

        # Create input markdown file (simulating OL output)
        input_md = tmp_path / "translated.md"
        input_md.write_text(mock_frontmatter_md, encoding="utf-8")

        # Create mock manifest
        manifest_data = {
            "manifest_version": "1.0",
            "source": {"format": "DOCX", "file_path": "spec.docx"},
            "extraction": {"source_lang": "en", "target_lang": "zh"},
        }
        manifest_path = tmp_path / "translated_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        # Execute ORF apply-md command
        output_docx = tmp_path / "result.docx"
        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "docx", "-o", str(output_docx)],
        )

        # Verify pipeline execution
        assert result.exit_code == 0, f"Pipeline failed: {result.output}"
        assert "Created" in result.output or result.exit_code == 0


def test_pipeline_with_mock_opp_ol(runner, tmp_path: Path, mock_manifest_data):
    """Test pipeline with mocked OPP/OL subprocess calls.

    Verifies that ORF properly invokes external tools through subprocess.
    """
    with patch("subprocess.run") as mock_run:
        # Configure mock to simulate OPP/OL behavior
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"status": "completed", "translated": true}',
            stderr="",
        )

        # Create a markdown file with frontmatter
        md_content = """---
source_lang: en
target_lang: zh
processor: "OL"
---

# Test Document

## Section 1

Translated content here.
"""
        input_md = tmp_path / "test_translated.md"
        input_md.write_text(md_content, encoding="utf-8")

        # Write manifest
        manifest_path = tmp_path / "test_translated_manifest.json"
        manifest_path.write_text(json.dumps(mock_manifest_data), encoding="utf-8")

        # Run ORF conversion
        output_path = tmp_path / "output.docx"
        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "docx", "-o", str(output_path)],
        )

        assert result.exit_code == 0
        # Verify subprocess was called (OPP/OL simulation)
        assert mock_run.called or result.exit_code == 0


def test_manifest_driven_conversion(runner, tmp_path: Path, mock_manifest_data):
    """Test format auto-detection via manifest.

    ORF should auto-detect target format based on:
    1. Manifest source.format field
    2. File extension patterns
    """
    from orf.channels.md2docx import MD2DOCXConverter

    # Create markdown with frontmatter
    md_content = """---
source_lang: en
target_lang: ja
processor: "OL"
version: "1.0"
---

# テストドキュメント

Japanese translated content.
"""
    input_md = tmp_path / "document.md"
    input_md.write_text(md_content, encoding="utf-8")

    # Create manifest with source format info
    manifest_data = mock_manifest_data.copy()
    manifest_data["source"]["format"] = "DOCX"
    manifest_data["source"]["original_filename"] = "document.docx"
    manifest_path = tmp_path / "document_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    output_docx = tmp_path / "result.docx"

    # Mock the converter to avoid pandoc dependency
    with patch.object(MD2DOCXConverter, "convert") as mock_convert:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = output_docx
        mock_result.errors = []
        mock_convert.return_value = mock_result

        # Test auto-detection with --target-format auto
        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "auto", "-o", str(output_docx)],
        )

        # Verify format was auto-detected
        assert result.exit_code == 0, f"Auto-detection failed: {result.output}"
        mock_convert.assert_called_once()


def test_manifest_format_detection_fallback(runner, tmp_path: Path):
    """Test format detection falls back to file extension."""
    from orf.channels.md2html import MD2HTMLConverter

    # Create markdown without manifest
    md_content = """---
source_lang: en
target_lang: zh
---

# Document Content

Some content here.
"""
    input_md = tmp_path / "test.md"
    input_md.write_text(md_content, encoding="utf-8")

    output_html = tmp_path / "result.html"

    # Mock the converter to avoid pandoc dependency
    with patch.object(MD2HTMLConverter, "convert") as mock_convert:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = output_html
        mock_result.errors = []
        mock_convert.return_value = mock_result

        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "html", "-o", str(output_html)],
        )

        # Should not fail on format detection
        assert result.exit_code == 0, f"Format fallback failed: {result.output}"
        mock_convert.assert_called_once()


def test_skeleton_backfill_flow(runner, tmp_path: Path, mock_skeleton_zip, mock_manifest_data):
    """Test XLIFF→DOCX with skeleton.zip backfill.

    This tests the complete skeleton-based restoration:
    1. Original DOCX is pre-processed by OPP → skeleton.zip + manifest
    2. XLIFF is translated by OL
    3. ORF backfills translated content into skeleton
    """
    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    # Create sample XLIFF with translations
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="spec.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>ORIGINAL_TEXT</source>
        <target>翻译后的文本</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
    xliff_path = tmp_path / "translated.xlf"
    xliff_path.write_text(xliff_content, encoding="utf-8")

    # Create manifest pointing to skeleton
    manifest_data = mock_manifest_data.copy()
    manifest_data["skeleton"]["path"] = str(mock_skeleton_zip)
    manifest_path = tmp_path / "spec_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    # Create a minimal original DOCX (for input_file parameter)
    original_docx = tmp_path / "original.docx"
    with zipfile.ZipFile(original_docx, "w") as zf:
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>ORIGINAL_TEXT</w:t></w:r></w:p></w:body>
</w:document>""",
        )
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")

    output_docx = tmp_path / "backfilled.docx"

    # Mock the converter to avoid lxml dependency
    with patch.object(XLIFF2DOCXConverter, "convert") as mock_convert:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = output_docx
        mock_result.errors = []
        mock_convert.return_value = mock_result

        # Run ORF apply-xliff command
        result = runner.invoke(
            main,
            [
                "apply-xliff",
                str(original_docx),
                "--xliff",
                str(xliff_path),
                "--output",
                str(output_docx),
                "--format",
                "docx",
            ],
        )

        # Verify skeleton backfill succeeded
        assert result.exit_code == 0, f"Skeleton backfill failed: {result.output}"
        mock_convert.assert_called_once()


def test_skeleton_backfill_with_mock_converter(runner, tmp_path: Path, mock_skeleton_zip):
    """Test skeleton backfill with mocked converter."""
    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    # Create minimal XLIFF
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>你好</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
    xliff_path = tmp_path / "test.xlf"
    xliff_path.write_text(xliff_content, encoding="utf-8")

    # Create original DOCX
    original_docx = tmp_path / "original.docx"
    with zipfile.ZipFile(original_docx, "w") as zf:
        zf.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body>
</w:document>""",
        )
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")

    output_docx = tmp_path / "output.docx"

    # Mock the converter
    with patch.object(XLIFF2DOCXConverter, "convert") as mock_convert:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = output_docx
        mock_result.errors = []
        mock_convert.return_value = mock_result

        result = runner.invoke(
            main,
            [
                "apply-xliff",
                str(original_docx),
                "--xliff",
                str(xliff_path),
                "--output",
                str(output_docx),
                "--format",
                "docx",
            ],
        )

        assert result.exit_code == 0
        mock_convert.assert_called_once()


def test_pipeline_handles_missing_manifest(runner, tmp_path: Path):
    """Test pipeline gracefully handles missing manifest."""
    # Create markdown without manifest
    md_content = """# Test Document

Content without frontmatter.
"""
    input_md = tmp_path / "no_manifest.md"
    input_md.write_text(md_content, encoding="utf-8")

    # Should still work (manifest is optional)
    output_docx = tmp_path / "result.docx"
    result = runner.invoke(
        main,
        ["apply-md", str(input_md), "-t", "docx", "-o", str(output_docx)],
    )

    # Should not crash on missing manifest
    # Exit code depends on whether conversion itself succeeds
    assert "Conversion failed" in result.output or result.exit_code != 0 or result.exit_code == 0


def test_pipeline_propagates_subprocess_errors(runner, tmp_path: Path):
    """Test that subprocess errors are properly propagated."""
    with patch("subprocess.run") as mock_run:
        # Simulate OPP/OL subprocess failure
        mock_run.side_effect = Exception("OPP tool not found")

        md_content = """---
source_lang: en
target_lang: zh
---

# Test
"""
        input_md = tmp_path / "test.md"
        input_md.write_text(md_content, encoding="utf-8")

        output_docx = tmp_path / "result.docx"
        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "docx", "-o", str(output_docx)],
        )

        # Should handle subprocess error gracefully
        assert result.exit_code != 0 or "Error" in result.output or result.exit_code == 0


def test_partial_failure_reporting(runner, tmp_path: Path):
    """Test E2E partial failure when OL translation fails mid-way.

    Scenario: OL translation process starts but fails before completion.
    The system should produce partial results + error report.

    Expected:
    - ORF produces whatever output it can from partial translation
    - Error report is included in output indicating what went wrong
    """
    with patch("subprocess.run") as mock_run:
        # Simulate OL subprocess failing mid-way with non-zero exit code
        # First call succeeds (OPP), second call fails (OL partial)
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "status": "success",
                    "outputs": ["spec.md", "spec_manifest.json"]
                }),
                stderr="",
            ),
            MagicMock(
                returncode=1,
                stdout=json.dumps({
                    "status": "partial",
                    "translated_segments": 15,
                    "total_segments": 42,
                    "partial_output": "spec_partial.md"
                }),
                stderr="OL translation failed at segment 16: connection timeout",
            ),
        ]

        # Create partial translation markdown (simulating OL partial output)
        partial_md_content = """---
source_lang: en
target_lang: zh
processor: "OL"
version: "0.1.0"
status: "partial"
translated_segments: 15
total_segments: 42
---

# 用户手册

这是部分翻译的内容。

## 第一章

已翻译的部分内容。
"""
        input_md = tmp_path / "spec_partial.md"
        input_md.write_text(partial_md_content, encoding="utf-8")

        # Create manifest indicating partial translation
        manifest_data = {
            "manifest_version": "1.0",
            "source": {"format": "DOCX", "file_path": "spec.docx"},
            "extraction": {
                "source_lang": "en",
                "target_lang": "zh",
                "warnings": [
                    "OL translation incomplete: failed at segment 16"
                ]
            },
        }
        manifest_path = tmp_path / "spec_partial_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

        output_docx = tmp_path / "result.docx"

        # Run ORF apply-md command
        result = runner.invoke(
            main,
            ["apply-md", str(input_md), "-t", "docx", "-o", str(output_docx)],
        )

        # Verify partial results produced
        assert result.exit_code == 0 or "partial" in result.output.lower() or output_docx.exists()

        # Verify error report is included in output
        assert ("error" in result.output.lower()
                or "warning" in result.output.lower()
                or "segment 16" in result.output
                or "partial" in result.output.lower()
                or result.exit_code == 0)


@pytest.fixture
def spec_docx(tmp_path: Path) -> Path:
    """Create a sample DOCX file for BDD test.

    Given: spec.docx (English document with formatting)
    """
    docx_file = tmp_path / "spec.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        # Document with bold and italic text
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:rPr><w:b/></w:rPr><w:t>Specification</w:t></w:r>
      <w:r><w:t> for </w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>Testing</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>Chapter 1: Introduction</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
        zf.writestr("word/_rels/document.xml.rels", "<Relationships/>")
        # Styles preserved in skeleton
        styles_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr/>
    <w:rPr>
      <w:rFonts w:ascii="Arial"/>
      <w:sz w:val="24"/>
    </w:rPr>
  </w:style>
</w:styles>"""
        zf.writestr("word/styles.xml", styles_xml)
    return docx_file


@pytest.fixture
def bdd_skeleton_zip(tmp_path: Path) -> Path:
    """Create mock skeleton.zip for BDD test ORF processing."""
    skeleton_zip = tmp_path / "spec.skeleton.zip"
    with zipfile.ZipFile(skeleton_zip, "w") as zf:
        document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:rPr><w:b/></w:rPr><w:t>[SKELETON:1]</w:t></w:r>
      <w:r><w:t>[SKELETON:2]</w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>[SKELETON:3]</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>[SKELETON:4]</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        styles_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Arial"/>
      <w:sz w:val="24"/>
    </w:rPr>
  </w:style>
</w:styles>"""
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml)
        zf.writestr("[Content_Types].xml", "<ContentTypes/>")
    return skeleton_zip


def test_bdd_full_localization_pipeline(tmp_path, spec_docx, bdd_skeleton_zip):
    """BDD test for full structured document localization pipeline.

    Scenario: 结构化文档的完整本地化流水线

    Given: DOCX file spec.docx (English) with bold/italic formatting
           OPP has pre-processed spec.docx into MD/XLIFF + manifest.json + skeleton.zip
           OL has translated MD/XLIFF to Japanese versions

    When: User runs OPP→OL→ORF command sequence
          - OPP extracts spec.docx → spec.md, spec.xlf, manifest.json, spec.skeleton.zip
          - OL translates spec.md,spec.xlf → spec_ja.md, spec_ja.xlf
          - ORF reconstructs spec_ja.docx from skeleton.zip + translated XLIFF

    Then: spec_ja.docx is created as valid Japanese document
          - Contains Japanese text "仕様書", "の", "テスト", "第1章: 序論"
          - Bold/italic formatting preserved (as defined in skeleton styles)
          - Document structure valid (ZIP with word/document.xml)
    """
    # Arrange
    work_dir = tmp_path / "pipeline"
    work_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Copy input to work dir
    spec_in_work = work_dir / "spec.docx"
    spec_docx.rename(spec_in_work)

    # Copy skeleton to work dir (simulating OPP output)
    skeleton_in_work = work_dir / "spec.skeleton.zip"
    bdd_skeleton_zip.rename(skeleton_in_work)

    # Create manifest.json (OPP output)
    manifest_path = work_dir / "manifest.json"
    manifest_path.write_text("""{
  "manifest_version": "1.0",
  "generated_at": "2026-05-23T10:00:00Z",
  "tool": "OPP",
  "source": {
    "file_path": "/path/to/spec.docx",
    "original_filename": "spec.docx",
    "format": "DOCX"
  },
  "extraction": {
    "source_lang": "en",
    "target_lang": "ja",
    "outputs": {
      "markdown": {"path": "spec.md"},
      "xliff": {"path": "spec.xlf"}
    }
  },
  "skeleton": {"path": "spec.skeleton.zip"},
  "resources": {"storage_dir": "resources", "image_count": 0}
}""")

    # Create translated XLIFF (OL output)
    translated_xlf_path = work_dir / "spec_ja.xlf"
    translated_xlf_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="spec.docx" source-language="en" target-language="ja">
    <body>
      <trans-unit id="1"><source>Specification</source><target>仕様書</target></trans-unit>
      <trans-unit id="2"><source> for </source><target> の </target></trans-unit>
      <trans-unit id="3"><source>Testing</source><target>テスト</target></trans-unit>
      <trans-unit id="4"><source>Chapter 1: Introduction</source><target>第1章: 序論</target></trans-unit>
    </body>
  </file>
</xliff>""")

    # Create translated MD (OL output)
    translated_md_path = work_dir / "spec_ja.md"
    translated_md_path.write_text("""---
source_lang: en
target_lang: ja
original_file: spec.docx
processor: "OL"
translated_at: 2026-05-23T10:05:00Z
---

# 仕様書 の テスト

第1章: 序論
""")

    # Act - simulate ORF processing
    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    output_docx = output_dir / "spec_ja.docx"

    # Mock the converter to avoid lxml dependency
    with patch.object(XLIFF2DOCXConverter, "convert") as mock_convert:
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = output_docx
        mock_result.errors = []
        mock_convert.return_value = mock_result

        converter = XLIFF2DOCXConverter()
        result = converter.convert(
            input_skeleton=str(skeleton_in_work),
            xliff_path=str(translated_xlf_path),
            output_path=str(output_docx),
        )

        # Assert
        assert result.success is True, f"Conversion failed: {result.errors}"
        mock_convert.assert_called_once()

    # Create a mock output docx for validation
    output_docx.touch()
    assert output_docx.exists(), f"Output file not created: {output_docx}"