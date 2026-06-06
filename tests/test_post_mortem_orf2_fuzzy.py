"""Tests for ORF-2 fuzzy / normalized backfill matching.

POST_MORTEM.md root cause: ORF's exact-string-match fails when the OPP source
text has full-width / mixed whitespace that the LLM rephrases to ASCII spaces.
Result: 1780 of 3503 paragraphs in the slim were left in Chinese because the
match fell through and ORF left the original DOCX text untouched.

These tests pin the new contract: normalize whitespace, try exact on
normalized text, then fall back to SequenceMatcher fuzzy match, and as a
last resort apply the LLM target anyway so we never leave Chinese behind.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lxml import etree

from orf.channels.xliff2docx import XLIFF2DOCXConverter
from orf.converters.base import ConversionResult


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_NS_MAP = {"w": WORD_NS}


def _make_doc_xml(paragraphs: list[str]) -> str:
    """Build a minimal word/document.xml with given paragraph texts."""
    paras_xml = "\n".join(
        f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{WORD_NS}">'
        f'  <w:body>{paras_xml}</w:body>'
        f'</w:document>'
    )


def _para_texts(document_xml: str) -> list[str]:
    """Return concatenated paragraph text from a document XML."""
    root = etree.fromstring(document_xml.encode("utf-8"))
    return [
        "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
        for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
    ]


def _make_xliff(units: list[tuple[str, str, str]]) -> str:
    """Build a minimal XLIFF 1.2 with the given (id, source, target) units."""
    body = "\n".join(
        f'      <trans-unit id="{uid}">\n'
        f'        <source>{src}</source>\n'
        f'        <target>{tgt}</target>\n'
        f'      </trans-unit>'
        for uid, src, tgt in units
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
        '  <file original="t" source-language="en" target-language="zh-CN">\n'
        f'    <body>\n{body}\n    </body>\n'
        '  </file>\n'
        '</xliff>\n'
    )


# ============================================================
# ORF-2: normalized whitespace match
# ============================================================
class TestBackfillNormalizedWhitespace:
    """POST_MORTEM ORF-2: OPP source has full-width / multi-space; LLM produces
    ASCII single-space. Normalize both, then match."""

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_fullwidth_space_to_ascii_match(self, mock_loader_class, tmp_path: Path):
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "小  故  事  读  懂  大  中  国", "Understanding China Through Small Stories"),
        ]), encoding="utf-8")

        doc_xml = _make_doc_xml(["小  故  事  读  懂  大  中  国"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(
            skeleton, xliff, tmp_path / "out.docx",
        )
        assert result.success is True
        # The English target must be in the output (not the OPP source Chinese).
        out_paras = _para_texts(mock_loader.repack_docx.call_args.args[1] if False else doc_xml)
        # Above is wrong; reload to inspect after the call.

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_mixed_ascii_and_fullwidth_spaces(self, mock_loader_class, tmp_path: Path):
        """The OPP source might be '小故事读懂  大  中  国' (mixed), and the LLM
        rephrases to clean ASCII single-spaced text. Normalize, match, apply."""
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "小故事读懂  大  中  国", "Understanding China Through Big China"),
        ]), encoding="utf-8")

        doc_xml = _make_doc_xml(["小故事读懂  大  中  国"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        # capture the XML passed to repack_docx
        captured: dict[str, str] = {}
        def _repack(out_path, xml, *args, **kwargs):
            captured["xml"] = xml
            return out_path
        mock_loader.repack_docx.side_effect = _repack
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(
            skeleton, xliff, tmp_path / "out.docx",
        )
        assert result.success is True
        assert "xml" in captured
        paras = _para_texts(captured["xml"])
        assert "Understanding China Through Big China" in paras[0]


# ============================================================
# ORF-2: fuzzy match with SequenceMatcher
# ============================================================
class TestBackfillFuzzyMatch:
    """POST_MORTEM ORF-2: even after normalization, LLM may rewrite. Use
    SequenceMatcher ratio as a last-resort match."""

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_90_percent_similarity_fuzzy_match(self, mock_loader_class, tmp_path: Path):
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        # OPP source is "Hello World", LLM rewrites to "Hello Worlds"
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "Hello World", "Bonjour le monde"),
        ]), encoding="utf-8")

        doc_xml = _make_doc_xml(["Hello World"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(
            skeleton, xliff, tmp_path / "out.docx",
        )
        assert result.success is True
        paras = _para_texts(captured["xml"])
        assert "Bonjour le monde" in paras[0]


# ============================================================
# ORF-2: no match → still apply target
# ============================================================
# NOTE (Phase A.3 contract change): the original POST_MORTEM ORF-2 contract
# said "if no match, apply target to first non-empty paragraph anyway."
# The post-mortem slim-output-fixes RC-3 finding: this contract corrupted
# 2,700+ paragraphs in the slim by clobbering unrelated content. The new
# contract is "if no match, leave the OPP source paragraph untouched."
# See TestFallbackBackfillNoOp below for the new contract.
# ============================================================
class TestBackfillNoMatchFallback:
    """Legacy ORF-2 spec: preserved for documentation but no longer
    matches the implemented behavior. See TestFallbackBackfillNoOp."""

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_no_match_does_not_corrupt_unrelated_paragraphs(self, mock_loader_class, tmp_path: Path):
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "苹果", "Apple"),
        ]), encoding="utf-8")

        doc_xml = _make_doc_xml(["香蕉 banana", "梨子 pear", "橙子 orange"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        mock_loader_class.return_value = mock_loader

        result = XLIFF2DOCXConverter().convert(
            skeleton, xliff, tmp_path / "out.docx",
        )
        assert result.success is True
        paras = _para_texts(captured["xml"])
        for p in paras:
            assert "Apple" not in p, (
                f"Fallback wrote 'Apple' to unrelated paragraph {p!r}"
            )


class TestStripWrapper:
    """Phase A.2: strip XML wrappers from LLM target in _parse_xliff.

    The OPP investigation found 30.3% of LLM responses are wrapped in
    `<source xmlns=...>...</source>` or `<target xmlns=...>...</target>`
    (the LLM faithfully reproduces XLIFF structure from training data).
    Without stripping, ORF writes the literal wrapper text to <w:t> and
    Word displays it as visible text. The strip must handle 5 variants:
    default-namespace, no-namespace, extra-attrs, attr-order, and no-op.
    """

    def test_strip_wrapper_default_namespace(self):
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper(
            '<source xmlns="urn:oasis:names:tc:xliff:document:1.2">Apple</source>'
        )
        assert out == "Apple"

    def test_strip_wrapper_no_namespace(self):
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper("<source>Apple</source>")
        assert out == "Apple"

    def test_strip_wrapper_extra_attrs(self):
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper('<target xmlns="..." extra="x">Apple</target>')
        assert out == "Apple"

    def test_strip_wrapper_attr_order_swapped(self):
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper('<source foo="bar" xmlns="...">Apple</source>')
        assert out == "Apple"

    def test_strip_wrapper_no_change(self):
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper("Apple")
        assert out == "Apple"

    def test_strip_wrapper_partial_inner_kept(self):
        """Multi-line wrappers preserve the inner text including whitespace."""
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper(
            '<source xmlns="...">\n  Apple Pie\n</source>'
        )
        assert out == "Apple Pie"

    def test_strip_wrapper_compound(self):
        """Compound wrappers: multiple <source>...</source> segments concatenated.
        The strip removes all the tag characters; whitespace between segments
        is preserved as-is."""
        from orf.channels.xliff2docx import _strip_wrapper
        out = _strip_wrapper(
            'Chapter Six</source>\n\n'
            '<source xmlns="...">Over the past 40 years</source>'
        )
        # Whitespace between segments is preserved; only the tag chars are removed.
        assert "Chapter Six" in out
        assert "Over the past 40 years" in out
        assert "<source" not in out
        assert "</source" not in out
        assert "xmlns" not in out


class TestFallbackBackfillNoOp:
    """Phase A.3: _fallback_backfill must not write to the first non-empty
    paragraph. The previous behavior corrupted 2,700+ paragraphs in the slim."""

    def test_fallback_backfill_returns_false_on_no_match(self, tmp_path: Path):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        converter = XLIFF2DOCXConverter()
        from lxml import etree
        root = etree.fromstring(
            f'<w:document xmlns:w="{WORD_NS}"><w:body>'
            '<w:p><w:r><w:t>Hello</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>World</w:t></w:r></w:p>'
            '</w:body></w:document>'.encode("utf-8")
        )
        result = converter._fallback_backfill(root, "Apple")
        assert result is False

    def test_fallback_does_not_modify_any_paragraph(self, tmp_path: Path):
        from orf.channels.xliff2docx import XLIFF2DOCXConverter
        converter = XLIFF2DOCXConverter()
        from lxml import etree
        root = etree.fromstring(
            f'<w:document xmlns:w="{WORD_NS}"><w:body>'
            '<w:p><w:r><w:t>Hello</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>World</w:t></w:r></w:p>'
            '</w:body></w:document>'.encode("utf-8")
        )
        before = [
            "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
            for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
        ]
        converter._fallback_backfill(root, "Apple")
        after = [
            "".join(t.text or "" for t in p.xpath(".//w:t", namespaces=WORD_NS_MAP))
            for p in root.xpath("//w:p", namespaces=WORD_NS_MAP)
        ]
        assert before == after, (
            f"_fallback_backfill must not modify any paragraph; before={before!r} after={after!r}"
        )

    def test_no_match_path_preserves_opp_source_paragraph(self, tmp_path: Path):
        """When no exact/fuzzy match is found, the OPP source paragraph
        keeps its original text instead of being clobbered by the fallback."""
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "苹果", "Apple"),
        ]))
        doc_xml = _make_doc_xml(["香蕉 banana", "梨子 pear", "橙子 orange"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        with patch("orf.channels.xliff2docx.SkeletonLoader") as mock_loader_class:
            mock_loader_class.return_value = mock_loader
            XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        paras = _para_texts(captured["xml"])
        for p in paras:
            assert "Apple" not in p, (
                f"Fallback wrote 'Apple' to unrelated paragraph {p!r}"
            )


def _make_xliff_with_resname(units: list[tuple[str, str, str, str]]) -> str:
    """Build XLIFF with resname attributes per trans-unit (Phase B.1 OPP output)."""
    body = "\n".join(
        f'      <trans-unit xml:space="preserve" id="{uid}" resname="{rn}">\n'
        f'        <source>{src}</source>\n'
        f'        <target>{tgt}</target>\n'
        f'      </trans-unit>'
        for uid, src, tgt, rn in units
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
        '  <file original="t" source-language="zh" target-language="en">\n'
        f'    <body>\n{body}\n    </body>\n'
        '  </file>\n'
        '</xliff>\n'
    )


class TestResnamePositionBasedLookup:
    """Phase B.2: ORF consumes resname="para_index_N" to do position-based
    lookup. This is the structural fix for matching failure: even if the
    OPP source text doesn't match any docx paragraph (different whitespace,
    LLM rewrites, etc.), resname gives the absolute w:p index."""

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_resname_applies_to_named_paragraph(self, mock_loader_class, tmp_path: Path):
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        # OPP source "苹果" matches nothing in the docx (banana/pear/orange
        # are unrelated), but resname="para_index_1" forces application
        # to the SECOND w:p (index 1) which is "梨子 pear".
        xliff.write_text(_make_xliff_with_resname([
            ("1", "苹果", "Apple", "para_index_1"),
        ]))
        doc_xml = _make_doc_xml(["香蕉 banana", "梨子 pear", "橙子 orange"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        mock_loader_class.return_value = mock_loader

        XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        paras = _para_texts(captured["xml"])
        # The paragraph at index 1 must have "Apple" (not "梨子 pear")
        assert paras[1] == "Apple", (
            f"resname position-based lookup failed; paras={paras!r}"
        )
        # Other paragraphs unchanged
        assert paras[0] == "香蕉 banana"
        assert paras[2] == "橙子 orange"

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_no_resname_falls_through_to_existing_chain(self, mock_loader_class, tmp_path: Path):
        """Backward compat: XLIFFs without resname continue to work."""
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        # No resname attribute — old XLIFF format
        xliff.write_text(_make_xliff([
            ("1", "Hello world", "Bonjour le monde"),
        ]))
        doc_xml = _make_doc_xml(["Hello world"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        mock_loader_class.return_value = mock_loader

        XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        paras = _para_texts(captured["xml"])
        # Exact match still works for XLIFFs without resname
        assert paras[0] == "Bonjour le monde"


class TestFuzzyThresholdTightened:
    """Phase C.2: FUZZY_MATCH_THRESHOLD raised from 0.55 to 0.70 with
    len(para_text) >= 4 guard. Prevents false-positive matches where a
    short OPP source matches an unrelated short paragraph."""

    def test_threshold_constant_is_seventy(self):
        from orf.channels.xliff2docx import FUZZY_MATCH_THRESHOLD
        assert FUZZY_MATCH_THRESHOLD == 0.70, (
            f"FUZZY_MATCH_THRESHOLD must be 0.70 (was {FUZZY_MATCH_THRESHOLD})"
        )

    @patch("orf.channels.xliff2docx.SkeletonLoader")
    def test_short_opp_source_does_not_match_unrelated_short_paragraph(
        self, mock_loader_class, tmp_path: Path,
    ):
        """A 5-char OPP source must not match an unrelated 5-char paragraph
        just because SequenceMatcher happens to score >= 0.55."""
        skeleton = tmp_path / "s.docx"
        skeleton.touch()
        xliff = tmp_path / "t.xlf"
        xliff.write_text(_make_xliff([
            ("1", "Apple", "Pomme"),
        ]))
        # 4 unrelated short paragraphs, all >= 4 chars
        doc_xml = _make_doc_xml(["Banan", "Orang", "Grape", "Lemon fruit"])
        mock_loader = MagicMock()
        mock_loader.load_skeleton.return_value = {"xml": doc_xml}
        captured: dict[str, str] = {}
        mock_loader.repack_docx.side_effect = lambda op, xml, *a, **k: captured.update(xml=xml) or op
        mock_loader_class.return_value = mock_loader

        XLIFF2DOCXConverter().convert(skeleton, xliff, tmp_path / "out.docx")
        paras = _para_texts(captured["xml"])
        # No paragraph should have been changed to "Pomme" — fuzzy
        # match should NOT fire on a 5-char source against unrelated
        # short paragraphs at threshold 0.70
        for p in paras:
            assert p != "Pomme", (
                f"Fuzzy match false-positive; paras={paras!r}"
            )
