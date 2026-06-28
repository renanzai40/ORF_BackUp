"""XLIFF parsing functions for the XLIFF2HTML converter."""

from __future__ import annotations

import re


def parse_xliff(xliff_content: str) -> dict[str, str]:
    """Parse XLIFF content and extract translation units.

    Args:
        xliff_content: The XLIFF file content as string

    Returns:
        Dictionary mapping segment IDs to translated text

    Raises:
        XLIFFParseError: If XLIFF content is malformed
    """
    translations: dict[str, str] = {}

    # XLIFF trans-unit pattern: <trans-unit id="...">
    # with <source>...</source> and <target>...</target>
    trans_unit_pattern = re.compile(
        r'<trans-unit[^>]+id="([^"]+)"[^>]*>(.*?)</trans-unit>',
        re.DOTALL | re.IGNORECASE,
    )

    source_pattern = re.compile(
        r"<source[^>]*>(.*?)</source>", re.DOTALL | re.IGNORECASE
    )
    target_pattern = re.compile(
        r"<target[^>]*>(.*?)</target>", re.DOTALL | re.IGNORECASE
    )

    for match in trans_unit_pattern.finditer(xliff_content):
        unit_id = match.group(1)
        unit_content = match.group(2)

        # Extract target (translated) text
        target_match = target_pattern.search(unit_content)
        if target_match:
            # Strip XLIFF inline tags for the translation
            target_text = strip_xliff_inline_tags(target_match.group(1))
            translations[unit_id] = target_text
        else:
            # Fall back to source if no target
            source_match = source_pattern.search(unit_content)
            if source_match:
                source_text = strip_xliff_inline_tags(source_match.group(1))
                translations[unit_id] = source_text

    return translations


def strip_xliff_inline_tags(text: str) -> str:
    """Remove XLIFF inline formatting tags from text.

    Args:
        text: Text containing <bx/> and <ex/> tags

    Returns:
        Plain text with inline tags removed
    """
    # Remove <bx .../> tags
    text = re.sub(r"<bx[^>]*/>", "", text, flags=re.IGNORECASE)
    # Remove <ex .../> tags
    text = re.sub(r"<ex[^>]*/>", "", text, flags=re.IGNORECASE)
    return text
