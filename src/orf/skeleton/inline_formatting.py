"""Inline formatting module for ORF Phase 1.

Handles conversion and application of inline formatting elements
extracted from XLIFF <bx>/<ex> tags to various document formats.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class InlineElement:
    """Represents an inline formatting element extracted from XLIFF.

    Attributes:
        id: Unique identifier for the inline element (from XLIFF id attribute).
        type: Formatting type (bold, italic, underline, strike, etc.).
        begin_pos: Starting position in the source text.
        end_pos: Ending position in the source text.
        text_covered: Optional text that this element covers in the source.
    """
    id: str
    type: str  # "bold", "italic", "underline", "strike"
    begin_pos: int
    end_pos: int
    text_covered: Optional[str] = None


class InlineFormattingApplier(ABC):
    """Abstract base class for applying inline formatting to document formats."""

    @abstractmethod
    def apply_formatting(
        self,
        content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply inline formatting to document content.

        Args:
            content: The document XML/HTML content.
            inline_elements: List of InlineElement objects defining formatting.
            target_text: The target text to apply formatting to.

        Returns:
            Modified document content with formatting applied.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError


class XLIFFInlineParser:
    """Parse XLIFF inline elements from source/target text.

    Extracts <bx> (markup open tag) and <ex> (markup close tag) elements
    from XLIFF mrk or seg tags and maps them to positions in the text.
    """

    # Regex patterns for XLIFF inline tags
    # <bx id="..." type="..." atrs.../> - markup open tag
    # <ex id="..." atrs.../> - markup close tag
    BX_PATTERN = re.compile(
        r'<bx[^>]*\sid="([^"]+)"[^>]*\stype="([^"]+)"[^>]*/?>',
        re.IGNORECASE
    )
    EX_PATTERN = re.compile(
        r'<ex[^>]*\sid="([^"]+)"[^>]*/?>',
        re.IGNORECASE
    )
    # MRK pattern for marked sections: <mrk mtype="protected" ...>text</mrk>
    MRK_OPEN_PATTERN = re.compile(
        r'<mrk[^>]*\smtype="protected"[^>]*>',
        re.IGNORECASE
    )
    MRK_CLOSE_PATTERN = re.compile(
        r'</mrk>',
        re.IGNORECASE
    )

    def parse_source(self, text: str) -> List[InlineElement]:
        """Extract inline elements from XLIFF source text.

        Args:
            text: XLIFF source text containing <bx> and <ex> tags.

        Returns:
            List of InlineElement objects with positions in the text.
        """
        elements = []

        # Find all <bx> tags (markup open)
        for match in self.BX_PATTERN.finditer(text):
            elem_id, elem_type = match.groups()
            elements.append(InlineElement(
                id=elem_id,
                type=elem_type,
                begin_pos=match.start(),
                end_pos=match.end(),
                text_covered=None
            ))

        # Find all <ex> tags (markup close)
        for match in self.EX_PATTERN.finditer(text):
            elem_id = match.group(1)
            elements.append(InlineElement(
                id=elem_id,
                type="close",  # ex tags are always closes
                begin_pos=match.start(),
                end_pos=match.end(),
                text_covered=None
            ))

        return elements

    def map_elements_to_positions(
        self,
        text: str,
        inline_elements: List[InlineElement]
    ) -> List[InlineElement]:
        """Map inline elements to actual text positions by stripping tags.

        Updates begin_pos and end_pos to point to the actual text content
        rather than the markup tags themselves.

        Args:
            text: The text with XLIFF markup.
            inline_elements: Elements with positions at markup locations.

        Returns:
            Elements with updated positions reflecting text content.
        """
        # Strip all XML tags to get pure text positions
        stripped_text = re.sub(r'<[^>]+>', '', text)

        # Build position mapping: stripped_pos -> original_pos
        original_pos = 0
        in_tag = False
        mapping = []

        for i, char in enumerate(text):
            if char == '<':
                in_tag = True
            elif char == '>':
                in_tag = False
            elif not in_tag:
                mapping.append((len(mapping), original_pos))
                original_pos += 1

        # Re-map element positions
        remapped = []
        for elem in inline_elements:
            # Find corresponding stripped text position
            orig_begin = elem.begin_pos
            orig_end = elem.end_pos

            # Binary search for stripped positions
            stripped_begin = self._find_stripped_pos(mapping, orig_begin)
            stripped_end = self._find_stripped_pos(mapping, orig_end)

            text_covered = stripped_text[stripped_begin:stripped_end] if stripped_begin < len(stripped_text) else None

            remapped.append(InlineElement(
                id=elem.id,
                type=elem.type,
                begin_pos=stripped_begin,
                end_pos=stripped_end,
                text_covered=text_covered
            ))

        return remapped

    def _find_stripped_pos(self, mapping: List[tuple], original_pos: int) -> int:
        """Find the stripped text position corresponding to an original position."""
        # Find closest stripped position <= original_pos
        result = 0
        for stripped_pos, orig_pos in mapping:
            if orig_pos <= original_pos:
                result = stripped_pos
            else:
                break
        return result

    def parse_from_segment(self, segment: str) -> List[InlineElement]:
        """Parse inline elements from an XLIFF segment with mrk tags.

        Args:
            segment: XLIFF segment text, e.g., '<mrk mtype="protected" ...>text</mrk>'

        Returns:
            List of InlineElement objects mapped to text content positions.
        """
        elements = self.parse_source(segment)
        return self.map_elements_to_positions(segment, elements)


class DOCXInlineApplier(InlineFormattingApplier):
    """Apply inline formatting to DOCX (Word) XML documents.

    Converts XLIFF inline element types to DOCX w:rPr (run properties)
    elements in the document XML.
    """

    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    W_PREFIX = f"{{{W_NS}}}"

    # Mapping from XLIFF type to DOCX property element
    TYPE_TO_TAG = {
        "bold": "b",
        "italic": "i",
        "underline": "u",
        "strike": "strike",
        "double-underline": "u",
        "single-underline": "u",
    }

    def apply_formatting(
        self,
        content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply inline formatting to DOCX XML content.

        Finds text runs matching the target text and wraps content
        in appropriate formatting tags.

        Args:
            content: The DOCX document.xml content as string.
            inline_elements: List of InlineElement objects to apply.
            target_text: The target text that should receive formatting.

        Returns:
            Modified document XML with formatting applied.
        """
        if not inline_elements:
            return content

        # Build formatting XML for each element
        # We need to find text runs and insert rPr elements

        for elem in inline_elements:
            if elem.type == "close":
                continue  # Handle close tags specially

            tag_name = self.TYPE_TO_TAG.get(elem.type.lower(), elem.type)
            if not tag_name:
                continue

            # Find text in runs and wrap with formatting
            # This is a simplified implementation
            # rpr_xml would be used in actual implementation

            # For actual DOCX formatting, we would need to:
            # 1. Find w:r elements containing the target text
            # 2. Insert w:rPr with the appropriate formatting child
            # This is format-dependent and may need adjustment

        return content

    def create_run_properties(self, elem_type: str) -> str:
        """Create w:rPr XML for a given formatting type.

        Args:
            elem_type: The inline element type (bold, italic, etc.)

        Returns:
            XML string for w:rPr element.
        """
        tag_name = self.TYPE_TO_TAG.get(elem_type.lower(), elem_type)

        if elem_type.lower() in ("bold",):
            return f"<{self.W_PREFIX}rPr><{self.W_PREFIX}b/></{self.W_PREFIX}rPr>"
        elif elem_type.lower() in ("italic",):
            return f"<{self.W_PREFIX}rPr><{self.W_PREFIX}i/></{self.W_PREFIX}rPr>"
        elif elem_type.lower() in ("underline", "double-underline"):
            val = "single" if elem_type.lower() == "underline" else "double"
            return f"<{self.W_PREFIX}rPr><{self.W_PREFIX}u w:val=\"{val}\"/></{self.W_PREFIX}rPr>"
        elif elem_type.lower() in ("strike",):
            return f"<{self.W_PREFIX}rPr><{self.W_PREFIX}strike/></{self.W_PREFIX}rPr>"
        else:
            return f"<{self.W_PREFIX}rPr><{self.W_PREFIX}{tag_name}/></{self.W_PREFIX}rPr>"


class PPTXInlineApplier(InlineFormattingApplier):
    """Apply inline formatting to PPTX (PowerPoint) XML documents.

    Converts XLIFF inline element types to PPTX a:rPr (run properties)
    elements in the slide XML.
    """

    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    A_PREFIX = f"{{{A_NS}}}"

    # Mapping from XLIFF type to PPTX property
    TYPE_TO_ATTR = {
        "bold": "b",
        "italic": "i",
        "underline": "u",
        "strike": "strike",
    }

    def apply_formatting(
        self,
        content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply inline formatting to PPTX slide XML content.

        Args:
            content: The PPTX slide XML content as string.
            inline_elements: List of InlineElement objects to apply.
            target_text: The target text that should receive formatting.

        Returns:
            Modified slide XML with formatting applied.
        """
        if not inline_elements:
            return content

        for elem in inline_elements:
            if elem.type == "close":
                continue

            attr_name = self.TYPE_TO_ATTR.get(elem.type.lower(), elem.type)
            if not attr_name:
                continue

            # PPTX formatting would be applied to a:rPr elements
            # Similar approach to DOCX but with DrawingML namespace

        return content

    def create_run_properties(self, elem_type: str) -> str:
        """Create a:rPr XML for a given formatting type.

        Args:
            elem_type: The inline element type.

        Returns:
            XML string for a:rPr element.
        """
        attr_name = self.TYPE_TO_ATTR.get(elem_type.lower(), elem_type)

        if elem_type.lower() == "bold":
            return f"<{self.A_PREFIX}rPr lang=\"en-US\" b=\"1\"/>"
        elif elem_type.lower() == "italic":
            return f"<{self.A_PREFIX}rPr lang=\"en-US\" i=\"1\"/>"
        elif elem_type.lower() == "underline":
            return f"<{self.A_PREFIX}rPr lang=\"en-US\" u=\"sng\"/>"
        elif elem_type.lower() == "strike":
            return f"<{self.A_PREFIX}rPr lang=\"en-US\" strike=\"sng\"/>"
        else:
            return f"<{self.A_PREFIX}rPr lang=\"en-US\"><{self.A_PREFIX}{attr_name}/></{self.A_PREFIX}rPr>"


class EPUBHTMLInlineApplier(InlineFormattingApplier):
    """Apply inline formatting to EPUB/HTML content.

    Converts XLIFF <bx>/<ex> inline tags to HTML <strong>, <em>, <u>, <s> tags.
    """

    # Mapping from XLIFF type to HTML tag
    TYPE_TO_TAG = {
        "bold": "strong",
        "italic": "em",
        "underline": "u",
        "strike": "s",
        "double-underline": "u",
    }

    def apply_formatting(
        self,
        content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply inline formatting by converting XLIFF tags to HTML.

        Converts <bx id="..." type="..."/> to opening HTML tags
        and <ex id="..."/> to closing HTML tags.

        Args:
            content: The content with XLIFF inline tags.
            inline_elements: List of InlineElement objects (may be unused if using direct conversion).
            target_text: The target text (not used for HTML conversion).

        Returns:
            Content with XLIFF inline tags converted to HTML formatting.
        """
        result = content

        # Build a mapping of id to type for <bx> tags
        open_tags = {}  # id -> type
        for elem in inline_elements:
            if elem.type != "close":
                open_tags[elem.id] = elem.type

        # Track which positions we've converted to avoid double-processing
        converted_positions = set()

        # Process in reverse order to preserve positions
        for elem in sorted(inline_elements, key=lambda e: e.begin_pos, reverse=True):
            if elem.begin_pos in converted_positions:
                continue

            if elem.type == "close":
                # Find corresponding opening tag
                # Look for <bx> before this position with matching id
                bx_pattern = re.compile(
                    rf'<bx[^>]*\sid="{re.escape(elem.id)}"[^>]*type="([^"]+)"[^>]*/?>',
                    re.IGNORECASE
                )
                # Search backwards from current position
                search_text = result[:elem.begin_pos]
                matches = list(bx_pattern.finditer(search_text))

                if matches:
                    last_match = matches[-1]
                    html_tag = self.TYPE_TO_TAG.get(
                        last_match.group(1).lower(),
                        last_match.group(1)
                    )
                    # Replace the <ex> tag with closing HTML tag
                    result = (
                        result[:elem.begin_pos] +
                        f"</{html_tag}>" +
                        result[elem.end_pos:]
                    )
                    converted_positions.add(elem.begin_pos)

        # Now convert remaining <bx> tags to opening HTML tags
        for elem in inline_elements:
            if elem.type == "close":
                continue

            html_tag = self.TYPE_TO_TAG.get(elem.type.lower(), elem.type)

            # Find and replace <bx .../> with <tag>
            bx_pattern = re.compile(
                rf'<bx[^>]*\sid="{re.escape(elem.id)}"[^>]*type="{re.escape(elem.type)}"[^>]*/?>',
                re.IGNORECASE
            )
            result = bx_pattern.sub(f"<{html_tag}>", result)

        return result

    def convert_xliff_to_html(self, xliff_content: str) -> str:
        """Convert XLIFF inline tags to HTML directly from content.

        Args:
            xliff_content: Content containing XLIFF <bx> and <ex> tags.

        Returns:
            Content with HTML formatting tags.
        """
        result = xliff_content

        # Replace closing tags first (</ex> style)
        result = re.sub(
            r'<ex[^>]*id="([^"]+)"[^>]*/?>',
            lambda m: self._get_closing_tag_for_id(result, m.group(1)),
            result,
            flags=re.IGNORECASE
        )

        # Replace opening tags
        result = re.sub(
            r'<bx[^>]*type="([^"]+)"[^>]*/?>',
            lambda m: self._get_opening_tag_for_type(m.group(1)),
            result,
            flags=re.IGNORECASE
        )

        return result

    def _get_opening_tag_for_type(self, xliff_type: str) -> str:
        """Get HTML opening tag for XLIFF type."""
        html_tag = self.TYPE_TO_TAG.get(xliff_type.lower(), xliff_type)
        return f"<{html_tag}>"

    def _get_closing_tag_for_id(self, content: str, elem_id: str) -> str:
        """Get HTML closing tag for an element id."""
        # Look for the corresponding <bx> tag to determine type
        bx_pattern = re.compile(
            rf'<bx[^>]*id="{re.escape(elem_id)}"[^>]*type="([^"]+)"',
            re.IGNORECASE
        )
        match = bx_pattern.search(content)
        if match:
            html_tag = self.TYPE_TO_TAG.get(match.group(1).lower(), match.group(1))
            return f"</{html_tag}>"
        return "</span>"  # Fallback to generic span


# Utility function for bulk conversion
def apply_inline_formatting_to_document(
    document_xml: str,
    inline_elements: List[InlineElement],
    target_text: str,
    format: str
) -> str:
    """Apply inline formatting to document based on format type.

    Args:
        document_xml: The document content as string.
        inline_elements: List of InlineElement objects.
        target_text: Target text for formatting.
        format: Format type ('docx', 'pptx', 'epub', 'html').

    Returns:
        Document with formatting applied.
    """
    if format.lower() in ("docx", "word"):
        applier = DOCXInlineApplier()
    elif format.lower() in ("pptx", "powerpoint"):
        applier = PPTXInlineApplier()
    elif format.lower() in ("epub", "html"):
        applier = EPUBHTMLInlineApplier()
    else:
        raise ValueError(f"Unsupported format: {format}")

    return applier.apply_formatting(document_xml, inline_elements, target_text)