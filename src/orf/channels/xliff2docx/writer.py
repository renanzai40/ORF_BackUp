"""DOCX writing and run-formatting functions for the XLIFF2DOCX converter.

Contains functions for building formatted DOCX ``<w:r>`` elements from
XLIFF inline tags.
"""

from __future__ import annotations

import re

from lxml import etree

from ._ns import W_NS

W = f"{{{W_NS}}}"


def build_formatted_runs(target_text: str) -> list[etree._Element]:
    """Parse target_text with XLIFF bx/ex tags and build DOCX ``w:r`` elements.

    Args:
        target_text: Target text potentially containing ``<bx.../>`` and ``<ex.../>`` tags.

    Returns:
        List of ``w:r`` elements with appropriate ``rPr`` formatting, or empty list
        if no formatting tags found.
    """
    bx_re = re.compile(r'<bx[^>]*\sid="([^"]*)"[^>]*\stype="([^"]*)"[^>]*/>', re.IGNORECASE)
    ex_re = re.compile(r'<ex[^>]*\sid="([^"]*)"[^>]*/>', re.IGNORECASE)

    segments: list[tuple[str, dict[str, str]]] = []
    open_formats: dict[str, str] = {}
    remaining = target_text

    while remaining:
        bx_match = bx_re.search(remaining)
        ex_match = ex_re.search(remaining)

        if not bx_match and not ex_match:
            if remaining:
                segments.append((remaining, dict(open_formats)))
            break

        earliest = None
        if bx_match:
            earliest = (bx_match.start(), bx_match, "bx")
        if ex_match:
            ex_start = ex_match.start()
            if earliest is None or ex_start < earliest[0]:
                earliest = (ex_start, ex_match, "ex")

        if earliest is None:
            segments.append((remaining, dict(open_formats)))
            break

        tag_pos, match_obj, tag_type = earliest

        if tag_pos > 0:
            segments.append((remaining[:tag_pos], dict(open_formats)))

        if tag_type == "bx":
            elem_id, elem_type = match_obj.group(1), match_obj.group(2).lower()
            for fmt in (s.strip() for s in elem_type.split(',')):
                if fmt:
                    open_formats[f"{elem_id}::{fmt}"] = fmt
        else:
            elem_id = match_obj.group(1)
            keys_to_remove = [k for k in open_formats if k.startswith(f"{elem_id}::")]
            for k in keys_to_remove:
                del open_formats[k]

        remaining = remaining[match_obj.end():]

    # Fast path: no bx/ex in target_text → plain text
    if not ('<bx' in target_text.lower() or '<ex' in target_text.lower()):
        return []

    if not segments:
        clean = re.sub(r'<bx[^>]*/>|<ex[^>]*/>', '', target_text)
        if clean == target_text:
            return []
        segments = [(clean, {})]

    runs = []
    for text, active_formats in segments:
        if not text:
            continue
        r = etree.Element(f"{W}r")

        has_formatting = any(
            fmt in ("bold", "italic", "underline", "double-underline", "single-underline", "strike")
            for fmt in active_formats.values()
        )
        if has_formatting:
            rpr = etree.SubElement(r, f"{W}rPr")
            if "bold" in active_formats.values():
                etree.SubElement(rpr, f"{W}b")
            if "italic" in active_formats.values():
                etree.SubElement(rpr, f"{W}i")
            for fmt_type, fmt_val in active_formats.items():
                if fmt_val == "double-underline":
                    u_elem = etree.SubElement(rpr, f"{W}u")
                    u_elem.set(f"{W}val", "double")
                elif fmt_val == "single-underline":
                    u_elem = etree.SubElement(rpr, f"{W}u")
                    u_elem.set(f"{W}val", "single")
                elif fmt_val == "underline":
                    u_elem = etree.SubElement(rpr, f"{W}u")
                    u_elem.set(f"{W}val", "single")
                if fmt_val == "strike":
                    etree.SubElement(rpr, f"{W}strike")

        t = etree.SubElement(r, f"{W}t")
        t.text = text

        runs.append(r)

    return runs
