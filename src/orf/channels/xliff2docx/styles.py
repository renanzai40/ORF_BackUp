"""Style handling and formatting preservation for the XLIFF2DOCX converter.

Contains functions for applying inline formatting (bold, italic, underline,
strike) to DOCX ``<w:t>`` elements, and utilities for style preservation
during XLIFF backfill.
"""

from __future__ import annotations

from typing import Any

from lxml import etree



def apply_inline_formatting_to_run(
    t_elem: etree._Element,
    inline_elements: list[Any],
    target_text: str,
    docx_applier: Any,
) -> None:
    """Apply inline formatting to a text run element.

    Uses the ``DOCXInlineApplier.TYPE_TO_TAG`` mapping to convert
    XLIFF inline element types (bold, italic, etc.) to DOCX ``<w:rPr>``
    child elements.

    Args:
        t_elem: The ``w:t`` element to apply formatting to.
        inline_elements: List of inline elements to apply.
        target_text: The target text for formatting.
        docx_applier: A ``DOCXInlineApplier`` instance.
    """
    parent = t_elem.getparent()
    if parent is None:
        return

    r_parent = parent.getparent()
    if r_parent is None:
        r_parent = parent

    # Insert rPr (run properties) before the w:t element
    rpr = etree.SubElement(r_parent, f"{{{docx_applier.W_NS}}}rPr")

    for elem in inline_elements:
        if elem.type == "close":
            continue

        tag_name = docx_applier.TYPE_TO_TAG.get(elem.type.lower(), elem.type)
        if tag_name:
            prop_elem = etree.SubElement(rpr, f"{{{docx_applier.W_NS}}}{tag_name}")

            # Handle special properties like underline with val attribute
            if elem.type.lower() in ("underline", "double-underline", "single-underline"):
                val = "single" if elem.type.lower() == "underline" else "double"
                prop_elem.set(f"{{{docx_applier.W_NS}}}val", val)


def build_inline_format_map(
    inline_elements: list[Any],
) -> dict[int, dict[str, str]]:
    """Build a mapping from character positions to inline format types.

    Useful for checking which format types are active at each position
    in a text run.  Position indices are string-level (not element-level).

    Args:
        inline_elements: List of inline elements (with ``begin_pos``, ``end_pos``, ``type``).

    Returns:
        Dict mapping position index to dict of active format types.
    """
    fmt_map: dict[int, dict[str, str]] = {}
    for elem in inline_elements:
        if hasattr(elem, 'begin_pos') and hasattr(elem, 'end_pos'):
            pos = elem.begin_pos
            if pos not in fmt_map:
                fmt_map[pos] = {}
            if hasattr(elem, 'type'):
                fmt_map[pos][elem.type] = elem.type
    return fmt_map
