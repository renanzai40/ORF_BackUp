"""ULTRAREADY-FIX (2026-06-08): regression test for ORF fuzzy backfill
with nested text-box content inside body paragraphs.

Bug surfaced during real E2E run on `爱上海尔_第二章_全球创牌 - E2E测试专用.docx`:
the source DOCX has body paragraph #8 (a 周云杰 quote paragraph) which
CONTAINS a `<w:drawing>` element whose text box holds the stats labels
("亚洲 ×5", "×116 ×54", etc.). ORF's `_fuzzy_backfill` was using
`.//w:t` (descendant XPath) for both matching AND writing — so when a
non-body unit like `×116 ×54` came through, the fuzzy match found
body[8] (because its nested text box contained "×116 ×54") and then
DESTRUCTIVELY overwrote body[8]'s entire `<w:t>` runs with "×116 ×54",
destroying the English 周云杰 translation.

Fix: `_fuzzy_backfill` must use `./w:t` (direct children) for both
matching and writing. This prevents nested drawings/text-boxes from
contaminating the match and from being destroyed by the write.
"""
import os
import zipfile

from orf.channels.xliff2docx import XLIFF2DOCXConverter


def _build_docx_with_nested_textbox(tmp_path):
    """Build a minimal DOCX where the body paragraph contains a nested
    text box with different text from the paragraph itself.
    """
    docx_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:v="urn:schemas-microsoft-com:vml"
            xmlns:o="urn:schemas-microsoft-com:office:office">
  <w:body>
    <w:p>
      <w:r>
        <w:t>BODY_PARAGRAPH_TEXT</w:t>
      </w:r>
      <w:r>
        <w:pict>
          <v:group style="width:100pt;height:50pt">
            <w:p>
              <w:r>
                <w:t>TEXTBOX_INNER_TEXT</w:t>
              </w:r>
            </w:p>
          </v:group>
        </w:pict>
      </w:r>
    </w:p>
    <w:sectPr/>
  </w:body>
</w:document>'''
    docx_dir = tmp_path / "docx_pkg"
    docx_dir.mkdir()
    (docx_dir / "word").mkdir()
    (docx_dir / "word" / "document.xml").write_text(docx_xml, encoding="utf-8")
    (docx_dir / "_rels").mkdir()
    (docx_dir / "_rels" / ".rels").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        encoding="utf-8",
    )
    (docx_dir / "[Content_Types].xml").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>',
        encoding="utf-8",
    )
    docx_path = tmp_path / "input.docx"
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(docx_dir):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, docx_dir)
                z.write(fp, arcname)
    return docx_path


def _build_xliff(tmp_path, source_text, target_text):
    xliff_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="input.docx" source-language="zh" target-language="en" datatype="plaintext">
    <body>
      <trans-unit id="1" resname="non_body_test">
        <source>{source_text}</source>
        <target>{target_text}</target>
      </trans-unit>
    </body>
  </file>
</xliff>'''
    p = tmp_path / "test.xlf"
    p.write_text(xliff_xml, encoding="utf-8")
    return p


def test_bugB_body_paragraph_preserved_when_fuzzy_match_via_nested_textbox(tmp_path):
    """End-to-end: the body paragraph's direct text must be PRESERVED
    even when a non-body unit's source matches text inside a nested
    drawing/text-box within that body paragraph.
    """
    docx_path = _build_docx_with_nested_textbox(tmp_path)
    xliff_path = _build_xliff(tmp_path, "TEXTBOX_INNER_TEXT", "TRANSLATED_TEXTBOX")
    output_path = tmp_path / "output.docx"

    converter = XLIFF2DOCXConverter()
    result = converter.convert(docx_path, xliff_path, output_path)
    assert result.success, f"convert failed: {result.errors}"

    with zipfile.ZipFile(output_path) as z:
        out_xml = z.read("word/document.xml").decode("utf-8")

    assert "BODY_PARAGRAPH_TEXT" in out_xml, (
        f"BUG: body paragraph text was destroyed by nested-textbox match. "
        f"Output XML:\n{out_xml}"
    )
    assert "TRANSLATED_TEXTBOX" in out_xml, (
        f"text-box target not applied. Output XML:\n{out_xml}"
    )
    assert "TEXTBOX_INNER_TEXT" not in out_xml, (
        f"text-box source text not replaced. Output XML:\n{out_xml}"
    )
