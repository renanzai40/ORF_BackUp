"""Tests for DOCXInlineApplier and PPTXInlineApplier ``apply_formatting``.

TDD red-phase: these tests assert the *new* behavior planned for T6, where
``apply_formatting`` must inject ``<w:rPr>`` / ``<a:rPr>`` children into the
matched run. Against the current no-op implementation, tests #1-#9 are
expected to FAIL (the applier returns ``content`` unchanged, so the
rPr children are missing). Test #10 is a regression check on the
``create_run_properties`` helpers and must PASS today.

See:
    - ``orf.skeleton.inline_formatting.DOCXInlineApplier.apply_formatting``
      (currently a no-op at lines 221-263)
    - ``orf.skeleton.inline_formatting.PPTXInlineApplier.apply_formatting``
      (currently a no-op at lines 307-337)
"""

import lxml.etree

from orf.skeleton.inline_formatting import (
    DOCXInlineApplier,
    InlineElement,
    PPTXInlineApplier,
)


# Namespace constants — keep in sync with xliff2docx.py / xliff2pptx.py.
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


# ---------------------------------------------------------------------------
# Minimal valid XML fixtures.
# A bare ``<w:r>``/``<a:r>`` element cannot be parsed by lxml without a
# namespace declaration, so each fixture is wrapped in a parent that
# declares the namespace.  The applier is given the inner run content via
# ``apply_formatting`` so the assertions remain focused on the run level.
# ---------------------------------------------------------------------------

# A valid w:document with a single run containing the target text "Hello".
MINIMAL_DOCX = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:body>'
    '<w:p><w:r><w:t>Hello</w:t></w:r></w:p>'
    '</w:body>'
    '</w:document>'
)

# A valid a:graphicFrame with a single a:r containing the target text "Hello".
MINIMAL_PPTX = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<a:graphicFrame xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<a:graphic><a:graphicData>'
    '<p:txBody xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
    '<a:p><a:r><a:t>Hello</a:t></a:r></a:p>'
    '</p:txBody>'
    '</a:graphicData></a:graphic>'
    '</a:graphicFrame>'
)


def _find_run_with_text(root: lxml.etree._Element, text: str, r_tag: str, t_tag: str):
    """Return the first ``<r>`` element whose ``<t>`` child text equals ``text``.

    Returns ``None`` if no such run exists.
    """
    for run in root.findall(f".//{r_tag}"):
        t = run.find(f"{t_tag}")
        if t is not None and t.text == text:
            return run
    return None


# ---------------------------------------------------------------------------
# DOCXInlineApplier
# ---------------------------------------------------------------------------


class TestDOCXInlineApplier:
    """Tests for ``DOCXInlineApplier.apply_formatting``."""

    def test_apply_formatting_injects_bold_rpr(self):
        """type="bold" must inject <w:rPr><w:b/></w:rPr> into the matched run."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_DOCX,
            [InlineElement(id="1", type="bold", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{W}r", f"{W}t")
        assert run is not None, "expected to find a <w:r> containing target text 'Hello'"

        rpr = run.find(f"{W}rPr")
        assert rpr is not None, (
            "<w:rPr> should be injected as a child of the matched run for bold formatting, "
            "but no <w:rPr> was found"
        )
        assert rpr.find(f"{W}b") is not None, "<w:b/> should be present in the rPr for bold"

    def test_apply_formatting_injects_italic_rpr(self):
        """type="italic" must inject <w:rPr><w:i/></w:rPr> into the matched run."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_DOCX,
            [InlineElement(id="1", type="italic", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{W}r", f"{W}t")
        assert run is not None

        rpr = run.find(f"{W}rPr")
        assert rpr is not None, (
            "<w:rPr> should be injected as a child of the matched run for italic formatting"
        )
        assert rpr.find(f"{W}i") is not None, "<w:i/> should be present in the rPr for italic"

    def test_apply_formatting_injects_underline_rpr(self):
        """type="underline" must inject <w:rPr><w:u/></w:rPr> into the matched run."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_DOCX,
            [InlineElement(id="1", type="underline", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{W}r", f"{W}t")
        assert run is not None

        rpr = run.find(f"{W}rPr")
        assert rpr is not None, (
            "<w:rPr> should be injected as a child of the matched run for underline formatting"
        )
        assert rpr.find(f"{W}u") is not None, "<w:u/> should be present in the rPr for underline"

    def test_apply_formatting_injects_strike_rpr(self):
        """type="strike" must inject <w:rPr><w:strike/></w:rPr> into the matched run."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_DOCX,
            [InlineElement(id="1", type="strike", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{W}r", f"{W}t")
        assert run is not None

        rpr = run.find(f"{W}rPr")
        assert rpr is not None, (
            "<w:rPr> should be injected as a child of the matched run for strike formatting"
        )
        assert rpr.find(f"{W}strike") is not None, (
            "<w:strike/> should be present in the rPr for strike"
        )

    def test_apply_formatting_multi_format(self):
        """type="bold,italic" must inject BOTH <w:b/> and <w:i/> in one rPr."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_DOCX,
            [
                InlineElement(
                    id="1",
                    type="bold,italic",
                    begin_pos=0,
                    end_pos=0,
                    text_covered="Hello",
                )
            ],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{W}r", f"{W}t")
        assert run is not None

        rpr = run.find(f"{W}rPr")
        assert rpr is not None, (
            "<w:rPr> should be injected for multi-format type 'bold,italic'"
        )
        assert rpr.find(f"{W}b") is not None, "<w:b/> should be present for 'bold' half of type"
        assert rpr.find(f"{W}i") is not None, "<w:i/> should be present for 'italic' half of type"

    def test_apply_formatting_noop_when_no_inline_elements(self):
        """Empty ``inline_elements`` must leave the document XML unchanged."""
        applier = DOCXInlineApplier()
        result = applier.apply_formatting(MINIMAL_DOCX, [], target_text="Hello")

        assert result == MINIMAL_DOCX, (
            "apply_formatting must return the original content unchanged "
            "when no inline elements are provided"
        )


# ---------------------------------------------------------------------------
# PPTXInlineApplier
# ---------------------------------------------------------------------------


class TestPPTXInlineApplier:
    """Tests for ``PPTXInlineApplier.apply_formatting``."""

    def test_apply_formatting_injects_bold_rpr(self):
        """type="bold" must inject <a:rPr b="1"/> into the matched run."""
        applier = PPTXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_PPTX,
            [InlineElement(id="1", type="bold", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{A}r", f"{A}t")
        assert run is not None, "expected to find an <a:r> containing target text 'Hello'"

        rpr = run.find(f"{A}rPr")
        assert rpr is not None, (
            "<a:rPr> should be injected as a child of the matched run for bold formatting, "
            "but no <a:rPr> was found"
        )
        assert rpr.get(f"{A}b") == "1", "<a:rPr> b attribute should be '1' for bold"

    def test_apply_formatting_injects_italic_rpr(self):
        """type="italic" must inject <a:rPr i="1"/> into the matched run."""
        applier = PPTXInlineApplier()
        result = applier.apply_formatting(
            MINIMAL_PPTX,
            [InlineElement(id="1", type="italic", begin_pos=0, end_pos=0, text_covered="Hello")],
            target_text="Hello",
        )

        root = lxml.etree.fromstring(result.encode("utf-8"))
        run = _find_run_with_text(root, "Hello", f"{A}r", f"{A}t")
        assert run is not None

        rpr = run.find(f"{A}rPr")
        assert rpr is not None, (
            "<a:rPr> should be injected as a child of the matched run for italic formatting"
        )
        assert rpr.get(f"{A}i") == "1", "<a:rPr> i attribute should be '1' for italic"

    def test_apply_formatting_noop_when_no_inline_elements(self):
        """Empty ``inline_elements`` must leave the slide XML unchanged."""
        applier = PPTXInlineApplier()
        result = applier.apply_formatting(MINIMAL_PPTX, [], target_text="Hello")

        assert result == MINIMAL_PPTX, (
            "apply_formatting must return the original content unchanged "
            "when no inline elements are provided"
        )


# ---------------------------------------------------------------------------
# Regression: the existing ``create_run_properties`` helpers must still
# return well-formed XML.  This test is expected to PASS today, and must
# continue to PASS after the T6 fix lands.
# ---------------------------------------------------------------------------


def _wrap_clark_xml_for_parsing(xml_str: str, ns_uri: str) -> str:
    """Make a Clark-notation XML fragment parseable by lxml.

    The current ``create_run_properties`` helpers emit Clark-notation
    strings like ``<{ns}rPr><{ns}b/></{ns}rPr>`` — valid as Python data
    but not as raw XML, because ``{`` is illegal at the start of a tag
    name.  To assert on it with lxml, strip the ``{ns}`` prefixes and
    wrap the result in a root whose *default* namespace is the same
    one, so lxml resolves the unprefixed elements into the expected
    Clark tag.
    """
    stripped = xml_str.replace("{" + ns_uri + "}", "")
    return f'<root xmlns="{ns_uri}">{stripped}</root>'


def test_create_run_properties_helpers_still_work():
    """``create_run_properties`` / ``create_run_properties_a`` stay well-formed."""
    docx_applier = DOCXInlineApplier()
    pptx_applier = PPTXInlineApplier()

    w_ns_uri = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    a_ns_uri = "http://schemas.openxmlformats.org/drawingml/2006/main"

    # --- DOCX: bold -> <w:rPr><w:b/></w:rPr> ---
    docx_bold_xml = docx_applier.create_run_properties("bold")
    parsed = lxml.etree.fromstring(
        _wrap_clark_xml_for_parsing(docx_bold_xml, w_ns_uri).encode("utf-8")
    )
    rpr = parsed.find(f"{W}rPr")
    assert rpr is not None, f"DOCX bold rPr should be present in {docx_bold_xml!r}"
    assert rpr.find(f"{W}b") is not None, "DOCX bold rPr should contain <w:b/>"

    # --- PPTX: bold -> <a:rPr b="1"/> ---
    # The current helper emits the ``b`` attribute *unprefixed* in the
    # returned string.  Assert on both the namespaced and unprefixed
    # forms so the test stays green if T6 switches to the canonical
    # ``a:b="1"`` form.
    pptx_bold_xml = pptx_applier.create_run_properties("bold")
    parsed = lxml.etree.fromstring(
        _wrap_clark_xml_for_parsing(pptx_bold_xml, a_ns_uri).encode("utf-8")
    )
    rpr = parsed.find(f"{A}rPr")
    assert rpr is not None, f"PPTX bold rPr should be present in {pptx_bold_xml!r}"
    b_value = rpr.get(f"{A}b") or rpr.get("b")
    assert b_value == "1", f"PPTX bold rPr should have b == '1', got {b_value!r}"
