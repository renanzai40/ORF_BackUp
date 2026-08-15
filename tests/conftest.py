"""Pytest configuration and shared fixtures for ORF tests."""

import os

import pytest
from pathlib import Path


# MUST run before any orf.mcp.* import: path_validator is a module-level
# singleton in orf.mcp.common that reads ORF_MCP_ALLOWED_DIRS at import.
# Allow the CWD (the repo the tests run from) so tests that write to
# Path.cwd() pass on any checkout, not just the author's machine.
SUITE_ROOT = str(Path.cwd())
if "ORF_MCP_ALLOWED_DIRS" not in os.environ:
    os.environ["ORF_MCP_ALLOWED_DIRS"] = SUITE_ROOT

# Disable MCP rate limiting for the test suite. Default burst is 10
# requests; tests calling apply_md/apply_xliff in sequence exhaust it
# and subsequent calls return RATE_LIMITED (no `errors` key) instead
# of PATH_NOT_ALLOWED, breaking C5 + context_dir assertions.
os.environ.setdefault("OMNI_RATE_LIMIT_RPM", "0")

MINIMAL_DOCX_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Hello world</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:r>
        <w:t>Second paragraph</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""


def create_minimal_docx(output_path: Path, document_xml: str):
    """Create a minimal DOCX file with the given document.xml content."""
    import zipfile

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
        zf.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""")


@pytest.fixture
def sample_md_content() -> str:
    """Sample markdown content for testing."""
    return """# 用户手册

这是中文内容。

## 第一章

- 列表项 1
- 列表项 2

| 表格 | 列 |
|------|---|
| 数据 | 值 |
"""


@pytest.fixture
def sample_frontmatter_md_content() -> str:
    """Sample markdown with frontmatter for testing."""
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
"""


@pytest.fixture
def sample_manifest_data() -> dict:
    """Sample manifest.json data for testing."""
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
                "markdown": {
                    "path": "spec.md",
                    "paragraph_count": 150,
                    "table_count": 3,
                },
                "xliff": {
                    "path": "spec.xlf",
                    "trans_unit_count": 42,
                },
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
        "resources": {
            "storage_dir": "resources",
            "image_count": 5,
        },
    }


# Phase 2 fixtures

@pytest.fixture
def sample_image_paths(tmp_path: Path) -> list[Path]:
    """Create sample image files for resource manager tests."""
    from PIL import Image  # Use Pillow for image creation

    images = []
    for i in range(3):
        img_path = tmp_path / f"test_image_{i}.png"
        # Create a simple 10x10 PNG
        img = Image.new("RGB", (10, 10), color="red")
        img.save(img_path)
        images.append(img_path)
    return images


@pytest.fixture
def sample_detectable_content(tmp_path: Path) -> dict[str, Path]:
    """Create sample files for format detection tests."""
    import json

    files = {}

    # MD file with frontmatter
    md_path = tmp_path / "test.md"
    md_path.write_text("---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Test")
    files["md"] = md_path

    # Manifest JSON
    manifest_path = tmp_path / "test_manifest.json"
    manifest_data = {
        "manifest_version": "1.0",
        "source": {"format": "DOCX", "file_path": "test.docx"},
        "extraction": {}
    }
    manifest_path.write_text(json.dumps(manifest_data))
    files["manifest"] = manifest_path

    # PDF file
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test content")
    files["pdf"] = pdf_path

    return files


@pytest.fixture
def css_template_file(tmp_path: Path) -> Path:
    """Create a sample CSS file for HTML conversion."""
    css_path = tmp_path / "style.css"
    css_path.write_text("body { font-family: Arial; }")
    return css_path


@pytest.fixture
def minimal_docx(tmp_path: Path) -> Path:
    """Create a minimal DOCX file in a tmp dir for use across test classes.

    Promoted from TestXLIFF2DOCXBackfill in test_e2e_behavioral.py so
    all test classes (including TestORFXLIFFContract, which uses the
    same fixture) can share it without per-class duplication.
    """
    path = tmp_path / "test.docx"
    create_minimal_docx(path, MINIMAL_DOCX_DOCUMENT)
    return path


# =============================================================================
# Golden file options (Task 3.3a)
# =============================================================================


def pytest_addoption(parser):
    """Register pytest CLI options for golden file capture/verification."""
    parser.addoption(
        "--golden-capture",
        action="store_true",
        default=False,
        help="Capture golden files (copy actual output to golden dir)",
    )
    parser.addoption(
        "--golden-verify",
        action="store_true",
        default=True,
        help="Verify output against golden files (default: on)",
    )
    parser.addoption(
        "--no-golden-verify",
        action="store_false",
        dest="golden_verify",
        help="Skip golden file verification",
    )
    parser.addoption(
        "--golden-dir",
        default="tests/golden/xliff2docx",
        help="Golden file directory (default: tests/golden/xliff2docx)",
    )
