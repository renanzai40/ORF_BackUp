"""MD to EML channel tests.

Tests for MD2EMLConverter which produces RFC 5322 email messages from
Markdown input with YAML frontmatter containing email_headers.
"""

from email import message_from_bytes
from pathlib import Path

import pytest

from orf.channels.md2eml import MD2EMLConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def eml_md(tmp_path: Path) -> Path:
    """Minimal MD with valid email_headers frontmatter."""
    content = """---\nemail_headers:\n  From: sender@example.com\n  To: receiver@example.com\n  Subject: Hello World\n---\n\nBody line one.\n\nBody line two.\n"""
    md_file = tmp_path / "email.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def eml_md_with_date(tmp_path: Path) -> Path:
    """MD with explicit Date header in frontmatter."""
    content = """---\nemail_headers:\n  From: a@example.com\n  To: b@example.com\n  Subject: With Date\n  Date: Mon, 04 Jun 2026 12:00:00 +0000\n---\n\nBody.\n"""
    md_file = tmp_path / "with_date.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2EMLConverter:
    def test_supported_format(self):
        converter = MD2EMLConverter()
        assert converter.supported_format == "EML"

    def test_validate_input_valid(self, eml_md: Path):
        converter = MD2EMLConverter()
        assert converter.validate_input(eml_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2EMLConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = MD2EMLConverter()
        assert converter.validate_input("/nonexistent/path/file.md") is False

    def test_convert_success(self, eml_md: Path, tmp_path: Path):
        output = tmp_path / "out.eml"

        converter = MD2EMLConverter()
        result = converter.convert(eml_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.errors == []
        assert output.exists()
        raw = output.read_bytes()
        assert b"From: sender@example.com" in raw
        assert result.metadata.get("format") == "EML"

    def test_convert_writes_rfc5322_message(self, eml_md: Path, tmp_path: Path):
        output = tmp_path / "rfc.eml"

        converter = MD2EMLConverter()
        converter.convert(eml_md, output)

        raw = output.read_bytes()
        msg = message_from_bytes(raw)

        # Required / set headers from frontmatter should be present.
        assert msg["From"] == "sender@example.com"
        assert msg["To"] == "receiver@example.com"
        assert msg["Subject"] == "Hello World"
        # Body content (after stripping frontmatter) should appear in payload.
        payload = msg.get_payload()
        assert "Body line one." in payload
        assert "Body line two." in payload

    def test_convert_adds_date_header_if_missing(
        self, eml_md: Path, tmp_path: Path
    ):
        """Frontmatter has no Date → output must still carry a Date header."""
        output = tmp_path / "no_date.eml"

        converter = MD2EMLConverter()
        result = converter.convert(eml_md, output)

        assert result.success is True
        msg = message_from_bytes(output.read_bytes())
        assert msg["Date"] is not None
        # Should look like an RFC 5322 date — contains a comma and a 4-digit year.
        assert "," in msg["Date"]
        assert "202" in msg["Date"] or "203" in msg["Date"]

    def test_convert_errors_when_no_email_headers(self, tmp_path: Path):
        md = tmp_path / "no_headers.md"
        md.write_text(
            "---\n"
            "title: No headers here\n"
            "---\n"
            "\n"
            "Body.\n",
            encoding="utf-8",
        )
        output = tmp_path / "out.eml"

        converter = MD2EMLConverter()
        result = converter.convert(md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is False
        assert any("Email headers required" in e.message for e in result.errors)

    def test_convert_handles_yaml_parse_error(self, tmp_path: Path):
        """Invalid YAML in frontmatter → treated as 'no headers'."""
        md = tmp_path / "bad_yaml.md"
        # Malformed YAML (unclosed quote) inside the frontmatter block.
        md.write_text(
            "---\n"
            "email_headers:\n"
            "  From: \"unterminated\n"
            "---\n"
            "\n"
            "Body.\n",
            encoding="utf-8",
        )
        output = tmp_path / "out.eml"

        converter = MD2EMLConverter()
        result = converter.convert(md, output)

        # YAML parse error collapses to "no email_headers" → same error path.
        assert result.success is False
        assert any("Email headers required" in e.message for e in result.errors)

    def test_inject_images_noop(self):
        converter = MD2EMLConverter()
        images = [{"id": "img1"}, {"id": "img2"}]
        applied, remaining = converter.inject_images(
            skeleton_path="ignored",
            images=images,
            output_path="ignored",
        )
        assert applied == []
        assert remaining is images
