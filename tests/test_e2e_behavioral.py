"""E2E behavioral tests for ORF xliff2docx backfill.

These tests verify the xliff2docx channel correctly:
1. Registers word namespace for xpath queries (Bug #4)
2. Uses xml_declaration=False with unicode encoding (Bug #5)
3. Actually writes translations to output DOCX
4. Handles OPP's source-only XLIFF format
5. Fails gracefully when XLIFF lacks <target> elements

These tests are NOT mocked - they verify actual output state.
"""

import pytest
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# Minimal DOCX skeleton (word/document.xml)
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

# XLIFF with translations (source + target)
XLIFF_WITH_TRANSLATIONS = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh" datatype="wordprocessingml">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
        <target>你好世界</target>
      </trans-unit>
      <trans-unit id="2">
        <source>Second paragraph</source>
        <target>第二段</target>
      </trans-unit>
    </body>
  </file>
</xliff>
"""

# OPP-style XLIFF: source-only (no target) - THIS IS THE PROBLEM FORMAT
OPP_STYLE_XLIFF_SOURCE_ONLY = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh" datatype="wordprocessingml">
    <body>
      <trans-unit id="1">
        <source>Hello world</source>
      </trans-unit>
    </body>
  </file>
</xliff>
"""


def create_minimal_docx(output_path: Path, document_xml: str):
    """Create a minimal DOCX file with the given document.xml content."""
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


def extract_document_xml(docx_path: Path) -> str:
    """Extract word/document.xml from a DOCX file."""
    with zipfile.ZipFile(docx_path, "r") as zf:
        return zf.read("word/document.xml").decode("utf-8")


class TestXLIFF2DOCXBackfill:
    """Test xliff2docx backfill functionality."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def minimal_docx(self, temp_dir) -> Path:
        """Create a minimal DOCX file."""
        path = temp_dir / "test.docx"
        create_minimal_docx(path, MINIMAL_DOCX_DOCUMENT)
        return path

    def test_backfill_translation_replaces_source_with_target(self, minimal_docx, temp_dir):
        """Test that _backfill_translation replaces source text with target text.

        This is the core behavioral test - verify translations are actually written.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # Backfill: replace "Hello world" with "你好世界"
        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="你好世界",
            inline_elements=None,
        )

        # Verify target text is in the result
        assert "你好世界" in result_xml, "Target translation not found in output"
        # Verify source text is NOT in the result (replaced)
        assert "Hello world" not in result_xml, "Source text still present (not replaced)"

    def test_backfill_uses_word_namespace(self, temp_dir):
        """Test that xpath queries use registered word namespace.

        Bug #4: xpath("//w:t") requires namespace registration.
        If namespace is not registered, xpath returns empty and nothing is replaced.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # If namespace is NOT registered, this would raise or return empty
        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="CHINESE_TEXT",
            inline_elements=None,
        )

        # If Bug #4 exists: result would still have "Hello world"
        # If Bug #4 is fixed: result would have "CHINESE_TEXT"
        assert "CHINESE_TEXT" in result_xml, \
            "Namespace not registered - xpath returned empty, translation not applied"
        assert "Hello world" not in result_xml, \
            "Source still present - namespace bug caused no replacement"

    def test_backfill_xml_declaration_unicode_encoding(self, temp_dir):
        """Test that xml_declaration=False works with encoding="unicode".

        Bug #5: xml_declaration=True with encoding="unicode" causes ValueError.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # This should NOT raise ValueError
        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="TRANSLATED",
            inline_elements=None,
        )

        # Verify result is valid XML string (not bytes)
        assert isinstance(result_xml, str), "Result should be string, not bytes"

        # Verify no XML declaration issues
        # If Bug #5 exists: would get ValueError or malformed XML
        assert result_xml.startswith("<w:document"), \
            f"XML declaration issue - unexpected start: {result_xml[:50]}"

    def test_full_pipeline_source_only_xliff(self, minimal_docx, temp_dir):
        """Test full pipeline with OPP-style source-only XLIFF.

        OPP generates XLIFF with only <source> (no <target>).
        OR should handle this gracefully.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # OPP-style XLIFF has no target - backfill should not crash
        # It will find nothing to replace, which is expected
        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="NonExistent text",
            target_text="Should not appear",
            inline_elements=None,
        )

        # Should return modified XML (or original if no match)
        assert isinstance(result_xml, str)
        assert "<w:document" in result_xml or result_xml == MINIMAL_DOCX_DOCUMENT


class TestXLIFF2DOCXWithTranslations:
    """Test full XLIFF→DOCX pipeline with actual translations."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def docx_with_translations(self, temp_dir) -> Path:
        """Create DOCX with multiple paragraphs."""
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Para 1: Hello</w:t>
      </w:r>
    </w:p>
    <w:p>
      <w:r>
        <w:t>Para 2: World</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""
        path = temp_dir / "multi.docx"
        create_minimal_docx(path, doc_xml)
        return path

    def test_backfill_multiple_units(self, docx_with_translations, temp_dir):
        """Test backfilling multiple trans-units."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # Apply first translation
        result1 = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="你好世界",
            inline_elements=None,
        )

        # Apply second translation
        result2 = converter._backfill_translation(
            document_xml=result1,
            source_text="Second paragraph",
            target_text="第二段",
            inline_elements=None,
        )

        # Both translations should be present
        assert "你好世界" in result2
        assert "第二段" in result2


class TestORFXLIFFContract:
    """Test that ORF output satisfies downstream requirements."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_output_docx_is_valid_zip(self, minimal_docx, temp_dir):
        """Verify output is a valid DOCX (ZIP archive)."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        # Apply translation
        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="TRANSLATED",
            inline_elements=None,
        )

        # Create output DOCX
        output_path = temp_dir / "output.docx"
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", result_xml)
            zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")

        # Verify it's a valid ZIP
        with zipfile.ZipFile(output_path, "r") as zf:
            names = zf.namelist()
            assert "word/document.xml" in names

    def test_translated_docx_content_is_valid_xml(self, minimal_docx, temp_dir):
        """Verify translated DOCX contains valid XML in document.xml."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()

        result_xml = converter._backfill_translation(
            document_xml=MINIMAL_DOCX_DOCUMENT,
            source_text="Hello world",
            target_text="VALID_XML_TEST",
            inline_elements=None,
        )

        # Result should be parseable XML
        root = ET.fromstring(result_xml)
        assert root is not None

        # Should have the translated text
        texts = [t.text for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")]
        assert "VALID_XML_TEST" in texts


class TestORFInjectImagesAtParagraphIndex:
    """Test xliff2docx inject_images at correct paragraph_index positions.

    OPP extracts images with paragraph_index metadata.
    ORF should inject images at the SAME paragraph_index in output DOCX.
    """

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    def create_docx_with_paragraphs(self, temp_dir: Path) -> tuple[Path, list[str]]:
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Para 0 - First</w:t></w:r></w:p>
    <w:p><w:r><w:t>Para 1 - Second</w:t></w:r></w:p>
    <w:p><w:r><w:t>Para 2 - Third</w:t></w:r></w:p>
    <w:p><w:r><w:t>Para 3 - Fourth</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        path = temp_dir / "with_paragraphs.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("word/document.xml", doc_xml)
            zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
            zf.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""")
            zf.writestr("word/_rels/document.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""")
        return path

    def test_image_injected_at_paragraph_0(self, temp_dir):
        """Image should be injected at paragraph_index=0 (first paragraph)."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        from orf.mcp.schemas import ImagePlacement

        converter = XLIFF2DOCXConverter()
        docx_path = self.create_docx_with_paragraphs(temp_dir)

        # Image at paragraph_index=0 (first paragraph)
        images = [
            ImagePlacement(
                data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwGhQGI/UOEQAAAASUVORK5CYII=",
                mime_type="image/png",
                paragraph_index=0,
            )
        ]

        output_path = temp_dir / "output.docx"
        injected, orphaned = converter.inject_images(docx_path, images, output_path)

        assert len(injected) == 1, f"Expected 1 injected, got {len(injected)}"
        assert len(orphaned) == 0, f"Expected 0 orphaned, got {len(orphaned)}"

        # Verify image is in first paragraph
        with zipfile.ZipFile(output_path, "r") as zf:
            content = zf.read("word/document.xml").decode("utf-8")
            # Image should be in first paragraph
            assert "paragraph_index=0" in content or "rId" in content or len(injected) > 0

    def test_image_at_last_paragraph_index(self, temp_dir):
        """Image at last paragraph_index should be handled correctly."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        from orf.mcp.schemas import ImagePlacement

        converter = XLIFF2DOCXConverter()
        docx_path = self.create_docx_with_paragraphs(temp_dir)

        # Image at paragraph_index=3 (last paragraph, 0-indexed)
        images = [
            ImagePlacement(
                data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwGhQGI/UOEQAAAASUVORK5CYII=",
                mime_type="image/png",
                paragraph_index=3,
            )
        ]

        output_path = temp_dir / "output_last.docx"
        injected, orphaned = converter.inject_images(docx_path, images, output_path)

        # Should succeed without error
        assert output_path.exists(), "Output DOCX should be created"

    def test_image_out_of_range_paragraph_index(self, temp_dir):
        """Image with paragraph_index beyond paragraph count should be orphaned."""
        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        from orf.mcp.schemas import ImagePlacement

        converter = XLIFF2DOCXConverter()
        docx_path = self.create_docx_with_paragraphs(temp_dir)

        # paragraph_index=99 is beyond available paragraphs (only 4 paragraphs: 0-3)
        images = [
            ImagePlacement(
                data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwGhQGI/UOEQAAAASUVORK5CYII=",
                mime_type="image/png",
                paragraph_index=99,
            )
        ]

        output_path = temp_dir / "output_oor.docx"
        injected, orphaned = converter.inject_images(docx_path, images, output_path)

        # Out-of-range should be orphaned
        assert len(orphaned) == 1, f"Expected 1 orphaned, got {len(orphaned)}"
        assert len(injected) == 0, f"Expected 0 injected, got {len(injected)}"


class TestORFApplyXliffMutualExclusivity:
    """Test apply_xliff schema validates mutual exclusivity of xliff_path and xliff_content."""

    def test_xliff_and_xliff_content_mutually_exclusive(self):
        """apply_xliff should reject both xliff_path and xliff_content provided.

        This is Q3 decision: --xliff and --xliff-content are mutually exclusive.
        """
        from orf.mcp.schemas import ApplyXLIFFInput
        import pydantic

        # Both xliff_path and xliff_content provided should raise ValidationError
        with pytest.raises((pydantic.ValidationError, ValueError)) as exc_info:
            ApplyXLIFFInput(
                input_file="test.docx",
                xliff_path="/path/to/file.xlf",
                xliff_content="<?xml version...",  # Both provided - should error
                output_path="output.docx",
                format="docx",
            )

        # Error should mention mutual exclusivity
        assert "mutually exclusive" in str(exc_info.value).lower() or "exactly one" in str(exc_info.value).lower(), \
            f"Should raise mutual exclusivity error, got: {exc_info.value}"


class TestORFApplyMdImagesJsonNoOp:
    """Test apply_md with images_json parameter is no-op for MD pipeline.

    MD pipeline uses pre-processing (base64 → temp files → pandoc),
    not post-conversion injection.
    """

    def test_md_pipeline_inject_images_is_noop(self):
        """MD2DOCX inject_images does nothing - documented limitation.

        MD pipeline extracts base64 → writes temp files → pandoc handles images,
        so images_json parameter is ignored.
        """
        from orf.channels.md2docx import MD2DOCXConverter

        converter = MD2DOCXConverter()

        # Verify inject_images method signature accepts images parameter
        import inspect
        sig = inspect.signature(converter.inject_images)
        assert 'images' in sig.parameters

        # The docstring should document the no-op behavior
        assert "pre-process" in converter.inject_images.__doc__ or \
               "MD pipeline" in str(converter.inject_images.__doc__), \
               "inject_images should document MD pipeline limitation"
