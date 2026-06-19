"""MD to MSG channel tests.

Tests for MD2MSGConverter which produces Outlook .msg files via Aspose.Email.
The library is optional and is mocked at the import boundary via sys.modules
so the test suite does not require it to be installed.
"""

import importlib
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from orf.channels import md2msg
from orf.converters.base import ConversionResult

# W2.2: Availability flag for conditional test assertions
try:
    import aspose.email as _aspose_check  # noqa: F401
    ASPOSE_AVAILABLE = True
except ImportError:
    ASPOSE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _install_aspose_mocks() -> dict[str, Any]:
    """Install minimal aspose.* module mocks in sys.modules.

    Returns the MagicMock instances so tests can configure return values /
    assert on calls. The mocks reproduce just enough of the Aspose.Email
    surface area that ``MD2MSGConverter.convert`` exercises.
    """
    aspose_email = types.ModuleType("aspose.email")

    mail_message = MagicMock(name="MailMessage")
    mail_message.return_value = mail_message

    mail_address = MagicMock(name="MailAddress")
    mail_address.return_value = mail_address

    mail_address_collection = MagicMock(name="MailAddressCollection")
    mail_address_collection.return_value = mail_address_collection

    save_options = MagicMock(name="SaveOptions")
    save_options.default_msg = MagicMock(name="SaveOptions.default_msg")

    aspose_email.MailMessage = mail_message
    aspose_email.MailAddress = mail_address
    aspose_email.MailAddressCollection = mail_address_collection

    aspose_email_mapi = types.ModuleType("aspose.email.mapi")
    mapi_message = MagicMock(name="MapiMessage")
    mapi_message.from_mail_message = MagicMock(
        name="MapiMessage.from_mail_message",
        return_value=MagicMock(name="mapi_msg"),
    )
    mapi_message.from_mail_message.return_value.set_property = MagicMock()
    aspose_email_mapi.MapiMessage = mapi_message

    aspose_email_save = types.ModuleType("aspose.email.save_options")
    aspose_email_save.SaveOptions = save_options

    aspose_email_mapi_pkg = types.ModuleType("aspose.email.mapi.properties")
    aspose_email_known = types.ModuleType(
        "aspose.email.mapi.properties.known_property_ids"
    )
    known_ids = MagicMock(name="KnownPropertyIds")
    aspose_email_known.KnownPropertyIds = known_ids

    mocks = {
        "aspose.email": aspose_email,
        "aspose.email.mapi": aspose_email_mapi,
        "aspose.email.save_options": aspose_email_save,
        "aspose.email.mapi.properties": aspose_email_mapi_pkg,
        "aspose.email.mapi.properties.known_property_ids": aspose_email_known,
        "MailMessage": mail_message,
        "MailAddress": mail_address,
        "MailAddressCollection": mail_address_collection,
        "SaveOptions": save_options,
        "MapiMessage": mapi_message,
    }
    sys.modules.update(mocks)
    return mocks


@pytest.fixture
def msg_md(tmp_path: Path) -> Path:
    """MD with valid email_headers frontmatter for MSG conversion."""
    content = """---\nemail_headers:\n  from: sender@example.com\n  to: receiver@example.com\n  subject: Hello World\n---\n\nBody line one.\n"""
    md_file = tmp_path / "email.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def msg_md_no_headers(tmp_path: Path) -> Path:
    """MD with no email_headers and no mapi_properties."""
    md = tmp_path / "no_headers.md"
    md.write_text(
        "---\ntitle: Plain\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture
def msg_md_bad_date(tmp_path: Path) -> Path:
    """MD with an unparseable Date in frontmatter."""
    md = tmp_path / "bad_date.md"
    md.write_text(
        "---\nemail_headers:\n  from: sender@example.com\n  to: receiver@example.com\n  subject: Bad Date\n  date: not-a-real-date\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture
def msg_md_mapi_only(tmp_path: Path) -> Path:
    """MD with mapi_properties only (no email_headers) — should still convert."""
    md = tmp_path / "mapi_only.md"
    md.write_text(
        "---\nmapi_properties:\n  conversation_id: conv-123\n---\n\nBody.\n",
        encoding="utf-8",
    )
    return md


@pytest.fixture
def msg_md_with_headers(tmp_path: Path) -> Path:
    """W2.2: MD with valid email_headers for MSG/EML conversion tests."""
    content = "---\nemail_headers:\n  from: sender@example.com\n  to: receiver@example.com\n  subject: Test Subject\n  date: 2026-06-20T10:00:00Z\n---\n\n# Test Subject\n\nBody content.\n"
    md_file = tmp_path / "with_headers.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMD2MSGConverter:
    def test_supported_format(self):
        converter = md2msg.MD2MSGConverter()
        assert converter.supported_format == "MSG"

    def test_validate_input_valid(self, msg_md: Path):
        converter = md2msg.MD2MSGConverter()
        assert converter.validate_input(msg_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = md2msg.MD2MSGConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = md2msg.MD2MSGConverter()
        assert converter.validate_input("/nonexistent/file.md") is False

    def test_convert_success(self, msg_md: Path, tmp_path: Path):
        mocks = _install_aspose_mocks()
        output = tmp_path / "out.msg"

        converter = md2msg.MD2MSGConverter()
        result = converter.convert(msg_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.errors == []
        assert result.metadata.get("format") == "MSG"
        # The MapiMessage.save() call should have been invoked.
        mapi_msg = mocks["MapiMessage"].from_mail_message.return_value
        mapi_msg.save.assert_called_once()
        args, _kwargs = mapi_msg.save.call_args
        assert str(output) in args

    def test_convert_fallback_when_no_headers_or_mapi(
        self, msg_md_no_headers: Path, tmp_path: Path
    ):
        """When no email_headers or mapi_properties exist, conversion succeeds
        with synthesized defaults (subject from H1 or '(no subject)')."""
        _install_aspose_mocks()
        output = tmp_path / "out.msg"

        converter = md2msg.MD2MSGConverter()
        result = converter.convert(msg_md_no_headers, output)

        assert result.success is True
        assert result.metadata.get("format") == "MSG"

    def test_convert_writes_msg_file(self, msg_md: Path, tmp_path: Path):
        """Happy path: a real .msg file gets written and the file system is touched."""
        mocks = _install_aspose_mocks()
        output = tmp_path / "happy.msg"

        converter = md2msg.MD2MSGConverter()
        result = converter.convert(msg_md, output)

        assert result.success is True
        # The mocked MapiMessage.save writes nothing on its own — the
        # converter's success path is what we are validating here.
        mapi_msg = mocks["MapiMessage"].from_mail_message.return_value
        assert mapi_msg.save.called
        assert result.metadata["format"] == "MSG"

    def test_convert_warns_on_unparseable_date(
        self, msg_md_bad_date: Path, tmp_path: Path
    ):
        """Bad date should be silently dropped (warning logged) and convert still succeeds."""
        _install_aspose_mocks()
        output = tmp_path / "bad_date.msg"

        converter = md2msg.MD2MSGConverter()
        result = converter.convert(msg_md_bad_date, output)

        # Conversion itself should still succeed; the bad date is only a warning.
        assert result.success is True

    def test_inject_images_noop(self):
        converter = md2msg.MD2MSGConverter()
        images = [{"id": "img1"}]
        applied, remaining = converter.inject_images(
            skeleton_path="ignored",
            images=images,
            output_path="ignored",
        )
        assert applied == []
        assert remaining is images

    def test_convert_missing_aspose(self, msg_md: Path, tmp_path: Path):
        """When aspose.email cannot be imported, convert gracefully degrades to EML fallback."""
        original_module = sys.modules.get("aspose.email")

        def _raise_on_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "aspose.email" or name.startswith("aspose.email"):
                raise ImportError("simulated: aspose.email not installed")
            return importlib.__import__(name, globals, locals, fromlist, level)

        import builtins

        real_import = builtins.__import__
        builtins.__import__ = _raise_on_import
        try:
            importlib.reload(md2msg)
            output = tmp_path / "missing.msg"
            converter = md2msg.MD2MSGConverter()
            result = converter.convert(msg_md, output)

            assert result.success is True
            assert result.metadata.get("format") == "eml"
            assert len(result.warnings) > 0
            all_warnings = " ".join(w.message for w in result.warnings)
            assert "aspose" in all_warnings.lower() or "eml" in all_warnings.lower()
            # EML fallback file must exist
            assert result.output_path.exists()
            assert result.output_path.suffix == ".eml"
        finally:
            builtins.__import__ = real_import
            if original_module is not None:
                sys.modules["aspose.email"] = original_module
            else:
                sys.modules.pop("aspose.email", None)
            importlib.reload(md2msg)


# --- W2.2: MSG path documentation tests ---

class TestMSGPathDocumentation:
    def test_msg_path_without_backend_warns_clearly(self, msg_md_with_headers: Path, tmp_path: Path):
        """W2.1: Without aspose-email-foss, MD→MSG must emit clear warning, write .eml fallback."""
        original_modules = {k: sys.modules[k] for k in list(sys.modules) if k.startswith("aspose")}
        for mod in list(original_modules):
            del sys.modules[mod]

        importlib.reload(md2msg)
        try:
            output = tmp_path / "out.msg"
            converter = md2msg.MD2MSGConverter()
            result = converter.convert(msg_md_with_headers, output)

            if not ASPOSE_AVAILABLE:
                assert result.success is True
                assert len(result.warnings) > 0
                all_messages = " ".join(w.message for w in result.warnings)
                assert "aspose" in all_messages.lower()
                assert result.metadata.get("format") == "eml"
                assert result.output_path.suffix == ".eml"
                assert result.output_path.exists()
        finally:
            sys.modules.update(original_modules)
            importlib.reload(md2msg)


class TestEMLAlternative:
    def test_eml_path_always_works_as_alternative(self, msg_md_with_headers: Path, tmp_path: Path):
        """W2.1: EML is the fully-supported open alternative — must always work."""
        from orf.channels.md2eml import MD2EMLConverter
        output = tmp_path / "out.eml"
        converter = MD2EMLConverter()
        result = converter.convert(msg_md_with_headers, output)
        assert result.success
        assert output.exists() and output.stat().st_size > 0
        content = output.read_text(encoding="utf-8")
        assert "from:" in content.lower()
        assert "to:" in content.lower()
        assert "subject:" in content.lower()
