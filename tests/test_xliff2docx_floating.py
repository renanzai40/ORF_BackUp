"""Tests for ORF floating image injection (wp:anchor).

Phase 3 of the real-llm-integration-tests plan: verify that when OPP supplies
an ImagePlacement with is_floating=True and wp_anchor_h/v set, ORF writes a
<w:drawing><wp:anchor> element preserving the page-relative H/V position.

Contract with OPP (Phase 2 emits these fields, Phase 3 consumes them):
  is_floating=True   -> use wp:anchor path
  paragraph_index    -> None (floating images are page-positioned, not paragraph-bound)
  wp_anchor_h        -> wp:posOffset for <wp:positionH> (EMU)
  wp_anchor_v        -> wp:posOffset for <wp:positionV> (EMU)
  wp_anchor_relative_h / _v -> wp:position{*}@relativeFrom
"""

import zipfile
from pathlib import Path

from lxml import etree

from orf.channels.xliff2docx import (
    A_NS,
    PIC_NS,
    W_NS,
    WP_NS,
    XLIFF2DOCXConverter,
)
from orf.mcp.schemas import ImagePlacement


# 1x1 transparent PNG.
TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwGhQGI/UOEQAAAASUVORK5CYII="
)

DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Para 0</w:t></w:r></w:p>
    <w:p><w:r><w:t>Para 1</w:t></w:r></w:p>
    <w:p><w:r><w:t>Para 2</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

WORD_NS_MAP = {"w": W_NS}
WP_NS_MAP = {"wp": WP_NS}
ALL_NS_MAP = {"w": W_NS, "wp": WP_NS, "a": A_NS, "pic": PIC_NS}


def _create_skeleton_docx(tmp_path: Path) -> Path:
    """Create a minimal DOCX skeleton in tmp_path/skeleton.docx."""
    docx_path = tmp_path / "skeleton.docx"
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", DOC_XML)
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "word/_rels/document.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>""",
        )
    return docx_path


def _read_output_document_xml(docx_path: Path) -> etree._Element:
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    return etree.fromstring(xml_bytes)


class TestXLIFF2DOCXFloatingImage:
    """Verify inject_images writes wp:anchor for floating images."""

    def test_floating_image_writes_wp_anchor(self, tmp_path: Path):
        """A floating image should produce a wp:anchor in output document.xml."""
        skeleton = _create_skeleton_docx(tmp_path)
        converter = XLIFF2DOCXConverter()
        output = tmp_path / "out.docx"

        images = [
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=None,  # floating images are not paragraph-bound
                is_floating=True,
                wp_anchor_h=2_286_000,  # 2.5 inches in EMU
                wp_anchor_v=914_400,    # 1.0 inch in EMU
            )
        ]

        injected, orphaned = converter.inject_images(skeleton, images, output)

        assert output.exists(), "output DOCX should be created"
        assert len(injected) == 1, f"expected 1 injected, got {len(injected)}"
        assert len(orphaned) == 0, f"expected 0 orphaned, got {len(orphaned)}"

        root = _read_output_document_xml(output)
        anchors = root.xpath("//wp:anchor", namespaces=ALL_NS_MAP)
        assert len(anchors) == 1, (
            f"expected 1 wp:anchor for floating image, found {len(anchors)}"
        )

        anchor = anchors[0]
        pos_h = anchor.find(f"{{{WP_NS}}}positionH")
        pos_v = anchor.find(f"{{{WP_NS}}}positionV")
        assert pos_h is not None and pos_v is not None, (
            "wp:anchor must contain positionH and positionV children"
        )

        h_offset = pos_h.find(f"{{{WP_NS}}}posOffset")
        v_offset = pos_v.find(f"{{{WP_NS}}}posOffset")
        assert h_offset is not None and h_offset.text == "2286000", (
            f"positionH posOffset mismatch: {h_offset.text if h_offset is not None else None}"
        )
        assert v_offset is not None and v_offset.text == "914400", (
            f"positionV posOffset mismatch: {v_offset.text if v_offset is not None else None}"
        )

        assert pos_h.get(f"relativeFrom") == "page", (
            f"positionH@relativeFrom should default to 'page', got {pos_h.get('relativeFrom')}"
        )
        assert pos_v.get(f"relativeFrom") == "page", (
            f"positionV@relativeFrom should default to 'page', got {pos_v.get('relativeFrom')}"
        )

        assert anchor.find(f"{{{WP_NS}}}extent") is not None
        assert anchor.find(f"{{{WP_NS}}}simplePos") is not None

        blip = anchor.find(f".//{{{A_NS}}}blip")
        assert blip is not None, "wp:anchor must contain a:blip referencing the image rId"
        embed_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        assert blip.get(embed_attr), "a:blip must have r:embed set"

    def test_floating_image_respects_custom_relative_from(self, tmp_path: Path):
        """relativeFrom attributes should be honored (e.g. 'column' / 'margin')."""
        skeleton = _create_skeleton_docx(tmp_path)
        converter = XLIFF2DOCXConverter()
        output = tmp_path / "out_relative.docx"

        images = [
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=None,
                is_floating=True,
                wp_anchor_h=1_000_000,
                wp_anchor_v=2_000_000,
                wp_anchor_relative_h="column",
                wp_anchor_relative_v="margin",
            )
        ]

        converter.inject_images(skeleton, images, output)
        root = _read_output_document_xml(output)

        anchors = root.xpath("//wp:anchor", namespaces=ALL_NS_MAP)
        assert len(anchors) == 1
        anchor = anchors[0]
        pos_h = anchor.find(f"{{{WP_NS}}}positionH")
        pos_v = anchor.find(f"{{{WP_NS}}}positionV")
        assert pos_h.get(f"relativeFrom") == "column"
        assert pos_v.get(f"relativeFrom") == "margin"

    def test_mixed_floating_and_inline_images(self, tmp_path: Path):
        """A mix of floating + inline images should produce both wp:anchor and wp:inline."""
        skeleton = _create_skeleton_docx(tmp_path)
        converter = XLIFF2DOCXConverter()
        output = tmp_path / "out_mixed.docx"

        images = [
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=1,  # inline, paragraph 1
                is_floating=False,
            ),
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=None,  # floating
                is_floating=True,
                wp_anchor_h=3_000_000,
                wp_anchor_v=4_000_000,
            ),
        ]

        injected, orphaned = converter.inject_images(skeleton, images, output)
        assert len(injected) == 2, f"expected 2 injected, got {len(injected)}"
        assert len(orphaned) == 0

        root = _read_output_document_xml(output)
        anchors = root.xpath("//wp:anchor", namespaces=ALL_NS_MAP)
        inlines = root.xpath("//wp:inline", namespaces=ALL_NS_MAP)

        assert len(anchors) == 1, f"expected 1 wp:anchor (floating), got {len(anchors)}"
        assert len(inlines) == 1, f"expected 1 wp:inline (inline), got {len(inlines)}"

        pos_h = anchors[0].find(f"{{{WP_NS}}}positionH/{{{WP_NS}}}posOffset")
        assert pos_h is not None and pos_h.text == "3000000"

    def test_multiple_floating_images_all_anchored(self, tmp_path: Path):
        """Multiple floating images should all produce distinct wp:anchor elements."""
        skeleton = _create_skeleton_docx(tmp_path)
        converter = XLIFF2DOCXConverter()
        output = tmp_path / "out_multi.docx"

        images = [
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=None,
                is_floating=True,
                wp_anchor_h=1_000_000 * (i + 1),
                wp_anchor_v=2_000_000 * (i + 1),
            )
            for i in range(3)
        ]

        injected, orphaned = converter.inject_images(skeleton, images, output)
        assert len(injected) == 3
        assert len(orphaned) == 0

        root = _read_output_document_xml(output)
        anchors = root.xpath("//wp:anchor", namespaces=ALL_NS_MAP)
        assert len(anchors) == 3, f"expected 3 wp:anchor, got {len(anchors)}"

        offsets_h = sorted(
            int(a.find(f"{{{WP_NS}}}positionH/{{{WP_NS}}}posOffset").text)
            for a in anchors
        )
        assert offsets_h == [1_000_000, 2_000_000, 3_000_000], (
            f"positionH offsets mismatch: {offsets_h}"
        )

    def test_floating_only_no_orphans(self, tmp_path: Path):
        """All-floating input should leave orphan list empty (no spurious drops)."""
        skeleton = _create_skeleton_docx(tmp_path)
        converter = XLIFF2DOCXConverter()
        output = tmp_path / "out_floating_only.docx"

        images = [
            ImagePlacement(
                data_base64=TINY_PNG_BASE64,
                mime_type="image/png",
                paragraph_index=None,
                is_floating=True,
                wp_anchor_h=500_000,
                wp_anchor_v=600_000,
            )
        ]
        injected, orphaned = converter.inject_images(skeleton, images, output)
        assert len(orphaned) == 0, (
            f"floating images must not be orphaned; got orphaned={len(orphaned)}"
        )
        assert len(injected) == 1
