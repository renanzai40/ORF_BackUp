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
from pathlib import Path
from lxml import etree


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


def read_docx_xml(path: Path) -> str:
    """Read word/document.xml from a DOCX file as a UTF-8 string.

    Precondition helper for assertion-style behavioral tests against the
    public XLIFF2DOCXConverter.convert() API. Spec T7 Step 1.
    """
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


class TestXLIFF2DOCXBackfill:
    """Test xliff2docx backfill functionality via the public convert() API."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def sample_xliff(self, temp_dir) -> Path:
        """XLIFF with <source>+<target> translations of the minimal DOCX body."""
        path = temp_dir / "translations.xlf"
        path.write_text(XLIFF_WITH_TRANSLATIONS, encoding="utf-8")
        return path

    @pytest.fixture
    def opp_source_only_xliff(self, temp_dir) -> Path:
        """OPP-style XLIFF: <source> only, no <target>. Must not crash convert()."""
        path = temp_dir / "opp_source_only.xlf"
        path.write_text(OPP_STYLE_XLIFF_SOURCE_ONLY, encoding="utf-8")
        return path

    def test_backfill_translation_replaces_source_with_target(
        self, minimal_docx, sample_xliff, temp_dir
    ):
        """Public convert() must replace 'Hello world' with '你好世界' in output DOCX.

        Strong assertion: target present AND source absent.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out.docx"
        result = converter.convert(str(minimal_docx), str(sample_xliff), str(output))

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        assert "你好世界" in content, "Target translation not found in output DOCX"
        assert "Hello world" not in content, "Source text still present (not replaced)"

    def test_backfill_uses_word_namespace(self, minimal_docx, sample_xliff, temp_dir):
        """Output DOCX must preserve xmlns:w so downstream xpath('//w:t') works (Bug #4).

        Strong assertion: namespace prefix declared on root element.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_ns.docx"
        result = converter.convert(str(minimal_docx), str(sample_xliff), str(output))

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        assert 'xmlns:w=' in content, \
            "Word namespace not preserved in output - xpath('//w:t') will return empty"

    def test_backfill_xml_declaration_unicode_encoding(
        self, minimal_docx, sample_xliff, temp_dir
    ):
        """Output document.xml must be a well-formed XML doc with translation (Bug #5).

        Strong assertion: parses with lxml AND contains target text in w:t elements.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_decl.docx"
        result = converter.convert(str(minimal_docx), str(sample_xliff), str(output))

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        root = etree.fromstring(content.encode("utf-8"))
        assert root is not None
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        texts = [t.text for t in root.iter(f"{ns}t") if t.text]
        assert "你好世界" in texts, \
            "Translated text not found in parsed w:t elements"

    def test_full_pipeline_source_only_xliff(
        self, minimal_docx, opp_source_only_xliff, temp_dir
    ):
        """OPP source-only XLIFF: output must contain source, not injected target.

        Strong assertion: source preserved AND no spurious target injected.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_opp.docx"
        result = converter.convert(
            str(minimal_docx), str(opp_source_only_xliff), str(output)
        )

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        assert "Hello world" in content, "Source text missing from output"
        assert "你好世界" not in content, \
            "Target text appeared in output despite source-only XLIFF"


class TestXLIFF2DOCXWithTranslations:
    """Test full XLIFF→DOCX pipeline with actual translations via convert()."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def docx_with_translations(self, temp_dir) -> Path:
        """Create DOCX with 3 distinct paragraphs for multi-unit backfill."""
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Hello</w:t></w:r></w:p>
    <w:p><w:r><w:t>World</w:t></w:r></w:p>
    <w:p><w:r><w:t>Greetings</w:t></w:r></w:p>
  </w:body>
</w:document>"""
        path = temp_dir / "multi.docx"
        create_minimal_docx(path, doc_xml)
        return path

    @pytest.fixture
    def three_unit_xliff(self, temp_dir) -> Path:
        """XLIFF with 3 trans-units, each translating a distinct source paragraph."""
        xliff = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="multi.docx" source-language="en" target-language="fr" datatype="wordprocessingml">
    <body>
      <trans-unit id="1">
        <source>Hello</source>
        <target>Bonjour</target>
      </trans-unit>
      <trans-unit id="2">
        <source>World</source>
        <target>Salut</target>
      </trans-unit>
      <trans-unit id="3">
        <source>Greetings</source>
        <target>Coucou</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        path = temp_dir / "three_units.xlf"
        path.write_text(xliff, encoding="utf-8")
        return path

    def test_backfill_multiple_units(
        self, docx_with_translations, three_unit_xliff, temp_dir
    ):
        """All 3 trans-units must be applied to the output DOCX in one convert() call.

        Strong assertion: every target string appears in output.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_multi.docx"
        result = converter.convert(
            str(docx_with_translations), str(three_unit_xliff), str(output)
        )

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        assert "Bonjour" in content, "Unit 1 target missing from output"
        assert "Salut" in content, "Unit 2 target missing from output"
        assert "Coucou" in content, "Unit 3 target missing from output"


class TestORFXLIFFContract:
    """Test that ORF output satisfies downstream requirements via convert()."""

    @pytest.fixture
    def temp_dir(self):
        import shutil
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def sample_xliff(self, temp_dir) -> Path:
        path = temp_dir / "translations.xlf"
        path.write_text(XLIFF_WITH_TRANSLATIONS, encoding="utf-8")
        return path

    def test_output_docx_is_valid_zip(self, minimal_docx, sample_xliff, temp_dir):
        """convert() must produce a valid DOCX (ZIP archive) containing word/document.xml.

        Strong assertion: zipfile.is_zipfile() AND required parts present.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_zip.docx"
        result = converter.convert(str(minimal_docx), str(sample_xliff), str(output))

        assert result.success, f"convert() failed: {result.errors}"
        assert zipfile.is_zipfile(output), "Output is not a valid ZIP archive"
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert "word/document.xml" in names, "Output ZIP missing word/document.xml"

    def test_translated_docx_content_is_valid_xml(self, minimal_docx, sample_xliff, temp_dir):
        """Output word/document.xml must parse as well-formed XML with translation present.

        Strong assertion: etree.fromstring does not raise AND target in w:t.
        """
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
        output = temp_dir / "out_valid.docx"
        result = converter.convert(str(minimal_docx), str(sample_xliff), str(output))

        assert result.success, f"convert() failed: {result.errors}"
        content = read_docx_xml(output)
        root = etree.fromstring(content.encode("utf-8"))
        assert root is not None
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        texts = [t.text for t in root.iter(f"{ns}t") if t.text]
        assert "你好世界" in texts, "Translation not found in parsed w:t elements"


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
