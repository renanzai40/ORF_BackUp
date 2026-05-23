"""Markdown to Outlook MSG conversion channel."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("channel.md2msg")

FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE
)


class MD2MSGConverter(BaseConverter):
    """Markdown to Outlook MSG converter using Aspose.Email."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "MSG"

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

    def _parse_mapi_properties(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse mapi_properties from frontmatter YAML.

        Args:
            content: Full MD file content

        Returns:
            mapi_properties dict or None if not found
        """
        match = FRONTMATTER_PATTERN.match(content)
        if not match:
            return None
        try:
            data = yaml.safe_load(match.group(1))
            return data.get("mapi_properties") if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None

    def _strip_frontmatter(self, content: str) -> str:
        """Remove frontmatter from content."""
        return FRONTMATTER_PATTERN.sub("", content)

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options: Any,
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

        # Parse email_headers and mapi_properties from frontmatter
        email_headers = self._parse_email_headers(content)
        mapi_properties = self._parse_mapi_properties(content)

        if not email_headers and not mapi_properties:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Email headers or MAPI properties required in frontmatter"],
            )

        # Extract MD body (content after frontmatter)
        md_body = self._strip_frontmatter(content)

        try:
            from aspose.email import (
                MailMessage,
                MailAddress,
                MailAddressCollection,
            )
            from aspose.email.mapi import MapiMessage
            from aspose.email.mapi.properties import (
                MapiProperty,
            )
            from aspose.email.mapi.properties.known_property_ids import (
                KnownPropertyIds,
            )
            from aspose.email.save_options import SaveOptions

            # Create MailMessage for body content
            msg = MailMessage()

            # Set email headers from frontmatter
            if email_headers:
                if email_headers.get("from"):
                    msg.from_address = MailAddress(str(email_headers["from"]))
                if email_headers.get("to"):
                    to_addresses = MailAddressCollection()
                    for to_addr in email_headers["to"].split(","):
                        to_addr = to_addr.strip()
                        if to_addr:
                            to_addresses.append(MailAddress(to_addr))
                    msg.to = to_addresses
                if email_headers.get("cc"):
                    cc_addresses = MailAddressCollection()
                    for cc_addr in email_headers["cc"].split(","):
                        cc_addr = cc_addr.strip()
                        if cc_addr:
                            cc_addresses.append(MailAddress(cc_addr))
                    msg.cc = cc_addresses
                if email_headers.get("subject"):
                    msg.subject = str(email_headers["subject"])

                # Set body from MD content (translated)
                msg.body = md_body

                # Set date if provided
                if email_headers.get("date"):
                    try:
                        date_str = str(email_headers["date"])
                        # Try parsing ISO format date
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        msg.date = dt
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse date: {email_headers.get('date')}")

            # Create MapiMessage from MailMessage to get MSG format with MAPI properties
            mapi_msg = MapiMessage.from_mail_message(msg)

            # Apply MAPI properties from frontmatter if provided
            if mapi_properties:
                self._set_mapi_properties(mapi_msg, mapi_properties)

            # Save as MSG
            save_options = SaveOptions.default_msg
            mapi_msg.save(str(output_path), save_options)

            logger.debug(f"MSG written: {output_path}")

            metadata = {
                "format": "MSG",
                "has_mapi_properties": mapi_properties is not None,
            }
            if email_headers:
                metadata["headers"] = list(email_headers.keys())

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata=metadata,
            )

        except ImportError as e:
            logger.error(f"Aspose.Email not available: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Aspose.Email library required for MSG conversion. Install with: pip install aspose.email"],
            )
        except Exception as e:
            logger.error(f"MSG conversion failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[str(e)],
            )

    def _set_mapi_properties(self, mapi_msg: Any, properties: Dict[str, Any]) -> None:
        """Set MAPI properties on the message.

        Args:
            mapi_msg: MapiMessage instance
            properties: Dict of MAPI property names to values
        """
        from aspose.email.mapi.properties.known_property_ids import (  # noqa: F401
            KnownPropertyIds,
        )

        # Map common MAPI property names to known property IDs
        property_id_map = {
            "conversation_id": KnownPropertyIds.PID_TAG_CONVERSATION_ID,
            "internet_message_id": KnownPropertyIds.PID_TAG_INTERNET_MESSAGE_ID,
            "in_reply_to_id": KnownPropertyIds.PID_TAG_IN_REPLY_TO_ID,
            "priority": KnownPropertyIds.PID_TAG_PRIORITY,
            "sensitivity": KnownPropertyIds.PID_TAG_SENSITIVITY,
            "client_submit_time": KnownPropertyIds.PID_TAG_CLIENT_SUBMIT_TIME,
            "sent_representing_name": KnownPropertyIds.PID_TAG_SENT_REPRESENTING_NAME,
            "sent_representing_email_address": KnownPropertyIds.PID_TAG_SENT_REPRESENTING_EMAIL_ADDRESS,
            "received_by_name": KnownPropertyIds.PID_TAG_RECEIVED_BY_NAME,
            "received_by_email_address": KnownPropertyIds.PID_TAG_RECEIVED_BY_EMAIL_ADDRESS,
        }

        for prop_name, prop_value in properties.items():
            if prop_value is None:
                continue

            prop_id = property_id_map.get(prop_name)
            if prop_id:
                try:
                    mapi_msg.set_property(prop_id, prop_value)
                except Exception as e:
                    logger.warning(f"Could not set MAPI property {prop_name}: {e}")
            else:
                # Try to set as custom property using property name
                try:
                    mapi_msg.set_property(prop_name, prop_value)
                except Exception as e:
                    logger.warning(f"Could not set custom property {prop_name}: {e}")