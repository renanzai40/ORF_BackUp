"""FIX-#9: Regression test for xliff2docx root replacement bug.

Before the fix: when _apply_source_formatting returns a brand-new
lxml tree (etree.fromstring path), the lookup references
(body_paragraphs, all_paragraphs, wt_text_map, body_paragraph_text_map,
all_paragraph_text_map) still pointed to elements in the discarded
old tree. Subsequent backfills modified stale elements that never
made it into the output document, so only the FIRST paragraph was
correctly translated.

This test:
1. Creates a synthetic DOCX with multiple paragraphs containing bold
2. Builds an XLIFF with corresponding trans-units
3. Runs convert()
4. Asserts ALL paragraphs were translated (not just the first)

If the fix is broken, only the first paragraph would be translated
and the test would fail.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import pytest

from lxml import etree


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _build_minimal_docx(paragraph_texts: list[str], bold_indices: set[int] | None = None) -> bytes:
    """Build a minimal DOCX in memory with the given paragraphs.

    bold_indices: set of paragraph indices (0-based) that should have bold formatting.
    """
    if bold_indices is None:
        bold_indices = set()

    paragraphs_xml = []
    for i, text in enumerate(paragraph_texts):
        bold_xml = ""
        if i in bold_indices:
            bold_xml = (
                '<w:rPr><w:b/></w:rPr>'
            )
        paragraphs_xml.append(
            f'<w:p>'
            f'<w:r>'
            f'{bold_xml}'
            f'<w:t xml:space="preserve">{text}</w:t>'
            f'</w:r>'
            f'</w:p>'
        )
    body = "".join(paragraphs_xml)

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{WORD_NS}">
  <w:body>{body}</w:body>
</w:document>"""

    buf = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<?xml version='1.0'?><x/>")
        z.writestr("word/document.xml", document_xml)
    with open(buf, "rb") as f:
        data = f.read()
    Path(buf).unlink()
    return data


def _build_xliff(translations: list[tuple[str, str]]) -> str:
    """Build a minimal XLIFF 1.2 with one trans-unit per (source, target)."""
    units = []
    for i, (source, target) in enumerate(translations):
        units.append(
            f'<trans-unit id="tu-{i+1}" resname="para_index_{i}">'
            f'<source>{source}</source>'
            f'<target>{target}</target>'
            f'</trans-unit>'
        )
    body = "".join(units)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test.docx" source-language="zh" target-language="en" datatype="plaintext">
    <body>{body}</body>
  </file>
</xliff>"""


def _extract_paragraph_texts(docx_path: Path) -> list[str]:
    """Extract plain paragraph text from a DOCX file."""
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as f:
            tree = etree.parse(f)
    body = tree.getroot().find(f"{{{WORD_NS}}}body")
    out: list[str] = []
    for p in body.findall(f"{{{WORD_NS}}}p"):
        texts = p.findall(f".//{{{WORD_NS}}}t")
        out.append("".join(t.text or "" for t in texts))
    return out


def test_fix9_root_replacement_invalidates_paragraph_refs(tmp_path: Path):
    """Reproduce FIX-#9: many paragraphs, only first is translated.

    If the fix is broken, only the first paragraph ends up translated.
    With the fix, all paragraphs are translated.
    """
    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    # 1. Build a DOCX with 5 Chinese paragraphs (paragraph 0 is bold)
    source_paragraphs = [
        "第一段",
        "第二段",
        "第三段",
        "第四段",
        "第五段",
    ]
    target_paragraphs = [
        "First paragraph",
        "Second paragraph",
        "Third paragraph",
        "Fourth paragraph",
        "Fifth paragraph",
    ]
    docx_bytes = _build_minimal_docx(
        source_paragraphs, bold_indices={0}
    )

    docx_path = tmp_path / "input.docx"
    with open(docx_path, "wb") as f:
        f.write(docx_bytes)

    # 2. Build a matching XLIFF with all 5 trans-units
    xliff_content = _build_xliff(
        list(zip(source_paragraphs, target_paragraphs))
    )
    xliff_path = tmp_path / "input.xlf"
    with open(xliff_path, "w", encoding="utf-8") as f:
        f.write(xliff_content)

    # 3. Construct skeleton from input.docx (required for convert)
    skeleton_path = tmp_path / "skeleton.zip"
    with zipfile.ZipFile(skeleton_path, "w") as z:
        with zipfile.ZipFile(docx_path, "r") as src:
            for name in src.namelist():
                z.writestr(name, src.read(name))

    # 4. Run the convert (FIX-#9: rebuild_indexes fires when
    # _apply_source_formatting replaces root)
    converter = XLIFF2DOCXConverter()
    output_path = tmp_path / "output.docx"
    from orf.converters.options import ConverterOptions
    options = ConverterOptions(skeleton_html=str(skeleton_path))
    result = converter.convert(
        input_path=str(docx_path),
        xliff_path=str(xliff_path),
        output_path=str(output_path),
        options=options,
    )
    assert result.success, f"convert failed: {result.errors}"

    # 5. Verify ALL paragraphs were translated (not just the first)
    output_paragraphs = _extract_paragraph_texts(output_path)
    assert len(output_paragraphs) == 5, (
        f"expected 5 paragraphs, got {len(output_paragraphs)}: {output_paragraphs}"
    )

    for i, (src_para, tgt_para) in enumerate(
        zip(source_paragraphs, target_paragraphs)
    ):
        assert tgt_para in output_paragraphs[i], (
            f"paragraph {i} not translated: got {output_paragraphs[i]!r}, "
            f"expected {tgt_para!r}. "
            f"This is FIX-#9: only the first paragraph was translated, "
            f"or the rebuild_indexes fix is not working."
        )
        assert src_para not in output_paragraphs[i], (
            f"paragraph {i} still has source text {src_para!r} — backfill "
            f"wrote to a stale tree reference."
        )


def test_fix9_bold_formatting_preserved(tmp_path: Path):
    """FIX-#9 sub-test: bold formatting on paragraph 0 must survive."""
    from orf.channels.xliff2docx import XLIFF2DOCXConverter

    docx_bytes = _build_minimal_docx(
        ["Bold paragraph", "Plain paragraph"],
        bold_indices={0},
    )
    docx_path = tmp_path / "input.docx"
    with open(docx_path, "wb") as f:
        f.write(docx_bytes)

    from lxml import etree as _etree
    xliff = """<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="test.docx" source-language="en" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="tu-1" resname="para_index_0">
        <source>Bold paragraph</source>
        <target>Bold paragraph</target>
      </trans-unit>
      <trans-unit id="tu-2" resname="para_index_1">
        <source>Plain paragraph</source>
        <target>Plain paragraph</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
    xliff_path = tmp_path / "input.xlf"
    with open(xliff_path, "w", encoding="utf-8") as f:
        f.write(xliff)

    skeleton_path = tmp_path / "skeleton.zip"
    with zipfile.ZipFile(skeleton_path, "w") as z:
        with zipfile.ZipFile(docx_path, "r") as src:
            for name in src.namelist():
                z.writestr(name, src.read(name))

    converter = XLIFF2DOCXConverter()
    output_path = tmp_path / "output.docx"
    from orf.converters.options import ConverterOptions
    options = ConverterOptions(skeleton_html=str(skeleton_path))
    result = converter.convert(
        input_path=str(docx_path),
        xliff_path=str(xliff_path),
        output_path=str(output_path),
        options=options,
    )
    assert result.success, f"convert failed: {result.errors}"

    with zipfile.ZipFile(output_path) as z:
        with z.open("word/document.xml") as f:
            tree = _etree.parse(f)
    body = tree.getroot().find(f"{{{WORD_NS}}}body")
    paragraphs = body.findall(f"{{{WORD_NS}}}p")
    para0 = paragraphs[0]
    bold_in_para0 = para0.findall(f".//{{{WORD_NS}}}b")
    assert len(bold_in_para0) > 0, (
        f"paragraph 0 lost its bold formatting — FIX-#9 inline formatting "
        f"may be writing to a stale tree reference. "
        f"Tree: {_etree.tostring(body, pretty_print=True).decode()}"
    )
