"""XLIFF to HTML conversion channel with inline formatting preservation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Any

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.skeleton.inline_formatting import XLIFFInlineParser, EPUBHTMLInlineApplier
from orf.error_handlers.conversion_error import XLIFFParseError, InlineFormattingError
from orf.logging import get_logger

logger = get_logger("channel.xliff2html")


class XLIFF2HTMLConverter(BaseConverter):
    """XLIFF to HTML backfill converter with inline formatting preservation.

    Converts XLIFF translation files back to HTML by:
    1. Loading the original HTML template
    2. Parsing the XLIFF file for translations
    3. Applying inline formatting (bold, italic, underline, strike)
    4. Saving the result as HTML

    Inline formatting mapping:
        - bold -> <strong>
        - italic -> <em>
        - underline -> <u>
        - strike -> <s>
    """

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        """Initialize the XLIFF to HTML converter.

        Args:
            manifest: OPP manifest.json metadata
            frontmatter: OL YAML frontmatter metadata
        """
        super().__init__(manifest, frontmatter)
        self.inline_parser = XLIFFInlineParser()
        self.html_applier = EPUBHTMLInlineApplier()

    @property
    def supported_format(self) -> str:
        """Supported output format."""
        return "HTML"

    def validate_input(self, input_path: Path | str) -> bool:
        """Validate that the HTML template file exists and is readable.

        Args:
            input_path: Path to the HTML template file

        Returns:
            True if the input file exists and has .html/.htm extension
        """
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() in (".html", ".htm")

    def convert(  # type: ignore[override]
        self,
        html_template: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options: Any,
    ) -> ConversionResult:
        """Convert XLIFF translation to HTML with inline formatting preserved.

        Args:
            html_template: Path to the original HTML template file
            xliff_path: Path to the XLIFF translation file
            output_path: Path for the output HTML file
            **options: Additional options (preserve_inline, encoding)

        Returns:
            ConversionResult with success status and any warnings/errors
        """
        html_template = Path(html_template)
        xliff_path = Path(xliff_path)
        output_path = Path(output_path)

        # 1. Validate and load HTML template
        if not html_template.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"HTML template not found: {html_template}"],
            )

        try:
            html_content = html_template.read_text(
                encoding=options.get("encoding", "utf-8")
            )
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to read HTML template: {e}"],
            )

        # 2. Validate and parse XLIFF
        if not xliff_path.exists():
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"XLIFF file not found: {xliff_path}"],
            )

        try:
            xliff_content = xliff_path.read_text(
                encoding=options.get("encoding", "utf-8")
            )
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to read XLIFF file: {e}"],
            )

        # 3. Parse XLIFF and extract translations
        try:
            translations = self._parse_xliff(xliff_content)
        except XLIFFParseError as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

        # 4. Apply translations and formatting to HTML
        result_content = html_content  # Default to original if processing fails
        warnings_list: list[str] = []
        try:
            result_content = self._apply_translations_and_formatting(
                html_content, translations, xliff_content, **options
            )
        except InlineFormattingError as e:
            warnings_list.append(str(e))
            # Continue with original content if formatting fails

        # 5. Save output HTML
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result_content, encoding="utf-8")
        except Exception as e:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to write output HTML: {e}"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            warnings=warnings_list,
            metadata={
                "source_format": "XLIFF",
                "target_format": "HTML",
                "template": str(html_template),
                "xliff": str(xliff_path),
            },
        )

    def _parse_xliff(self, xliff_content: str) -> dict[str, str]:
        """Parse XLIFF content and extract translation units.

        Args:
            xliff_content: The XLIFF file content as string

        Returns:
            Dictionary mapping segment IDs to translated text

        Raises:
            XLIFFParseError: If XLIFF content is malformed
        """
        translations = {}

        # XLIFF trans-unit pattern: <trans-unit id="...">
        # with <source>...</source> and <target>...</target>
        trans_unit_pattern = re.compile(
            r'<trans-unit[^>]+id="([^"]+)"[^>]*>(.*?)</trans-unit>',
            re.DOTALL | re.IGNORECASE
        )

        source_pattern = re.compile(r'<source[^>]*>(.*?)</source>', re.DOTALL | re.IGNORECASE)
        target_pattern = re.compile(r'<target[^>]*>(.*?)</target>', re.DOTALL | re.IGNORECASE)

        for match in trans_unit_pattern.finditer(xliff_content):
            unit_id = match.group(1)
            unit_content = match.group(2)

            # Extract target (translated) text
            target_match = target_pattern.search(unit_content)
            if target_match:
                # Strip XLIFF inline tags for the translation
                target_text = self._strip_xliff_inline_tags(target_match.group(1))
                translations[unit_id] = target_text
            else:
                # Fall back to source if no target
                source_match = source_pattern.search(unit_content)
                if source_match:
                    source_text = self._strip_xliff_inline_tags(source_match.group(1))
                    translations[unit_id] = source_text

        return translations

    def _strip_xliff_inline_tags(self, text: str) -> str:
        """Remove XLIFF inline formatting tags from text.

        Args:
            text: Text containing <bx/> and <ex/> tags

        Returns:
            Plain text with inline tags removed
        """
        # Remove <bx .../> tags
        text = re.sub(r'<bx[^>]*/>', '', text, flags=re.IGNORECASE)
        # Remove <ex .../> tags
        text = re.sub(r'<ex[^>]*/>', '', text, flags=re.IGNORECASE)
        return text

    def _apply_translations_and_formatting(
        self,
        html_content: str,
        translations: dict[str, str],
        xliff_content: str,
        **options,
    ) -> str:
        """Apply translations and inline formatting to HTML content.

        Args:
            html_content: The original HTML template content
            translations: Dictionary of translation units
            xliff_content: The full XLIFF content for inline tag processing
            **options: Additional options like preserve_inline

        Returns:
            HTML content with translations and formatting applied

        Raises:
            InlineFormattingError: If inline formatting cannot be applied
        """
        preserve_inline = options.get("preserve_inline", True)

        if not preserve_inline:
            # Simply replace placeholder markers with translations
            result = html_content
            for unit_id, translated_text in translations.items():
                # Replace markers like [trans-unit-id] or data-id attributes
                result = result.replace(f"[{unit_id}]", translated_text)
                result = re.sub(
                    rf'data-trans-unit-id="{re.escape(unit_id)}"[^>]*>',
                    f'>{translated_text}',
                    result
                )
            return result

        # Apply inline formatting conversion using EPUBHTMLInlineApplier
        # This converts <bx type="bold"/> to <strong> and <ex id="..."/> to </strong>
        formatted_content = self.html_applier.convert_xliff_to_html(xliff_content)

        # Replace placeholders with translated text
        result = formatted_content
        for unit_id, translated_text in translations.items():
            result = result.replace(f"[{unit_id}]", translated_text)

        return result