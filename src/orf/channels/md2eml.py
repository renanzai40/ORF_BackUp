"""Markdown to RFC 5322 Email conversion channel."""

from __future__ import annotations

import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2eml")

FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE
)


class MD2EMLConverter(BaseConverter):
    """Markdown to RFC 5322 Email converter using stdlib email module."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "EML"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _parse_email_headers(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse email_headers from frontmatter YAML.

        Args:
            content: Full MD file content

        Returns:
            email_headers dict or None if not found
        """
        match = FRONTMATTER_PATTERN.match(content)
        if not match:
            return None
        try:
            data = yaml.safe_load(match.group(1))
            return data.get("email_headers") if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None

    def _strip_frontmatter(self, content: str) -> str:
        """Remove frontmatter from content."""
        return FRONTMATTER_PATTERN.sub("", content)

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        try:
            content = input_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read input file: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

        # Parse email_headers from frontmatter
        email_headers = self._parse_email_headers(content)
        if not email_headers:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Email headers required in frontmatter"],
            )

        # Extract MD body (content after frontmatter)
        md_body = self._strip_frontmatter(content)

        # Create RFC 5322 email message
        msg = EmailMessage()
        msg.set_content(md_body)

        # Set headers from frontmatter.email_headers
        for header_name, header_value in email_headers.items():
            if header_value is not None:
                msg[header_name] = str(header_value)

        # Ensure Date header is set (RFC 5322 requires it)
        if "Date" not in msg:
            from datetime import datetime, timezone

            msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

        # Serialize as bytes with UTF-8 encoding
        try:
            eml_bytes = msg.as_bytes(policy=self._eml_policy())
        except Exception as e:
            logger.error(f"Failed to serialize email: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

        try:
            output_path.write_bytes(eml_bytes)
        except Exception as e:
            logger.error(f"Failed to write EML file: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

        logger.debug(f"EML written: {output_path}")
        return ConversionResult(
            output_path=output_path,
            success=True,
            metadata={"format": "EML", "headers": list(email_headers.keys())},
        )

    @staticmethod
    def _eml_policy() -> Any:
        """Get email policy for RFC 5322 compliance."""
        from email.policy import EmailPolicy

        return EmailPolicy(
            max_line_length=0,  # No line length limit for EML
            linesep="\r\n",
        )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2EML does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically."
        )
        return ([], images)