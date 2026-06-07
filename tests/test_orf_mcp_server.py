"""Integration tests for ORF MCP Server."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orf.mcp.server import get_server, _run_cli_command
from orf.mcp.security import PathValidator


class TestPathValidator:
    """Tests for path security validation."""
    
    def test_valid_path(self):
        """Valid paths should pass."""
        valid, error = PathValidator.validate("test.md")
        assert valid is True
        assert error == ""
    
    def test_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        valid, error = PathValidator.validate("../../etc/passwd")
        assert valid is False
        assert "traversal" in error.lower()
    
    def test_absolute_path_valid(self):
        """Absolute paths should be validated."""
        valid, error = PathValidator.validate("/tmp/test.md")
        assert valid is True


class TestRunCLICommand:
    """Tests for CLI command runner."""
    
    @patch("subprocess.run")
    def test_successful_command(self, mock_run):
        """Successful CLI commands should return parsed JSON."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"success": True, "output_path": "/tmp/out.docx"})
        )
        
        result = _run_cli_command(["apply-md", "input.md", "--target-format", "docx"])
        
        assert result["success"] is True
        assert result["output_path"] == "/tmp/out.docx"
    
    @patch("subprocess.run")
    def test_failed_command(self, mock_run):
        """Failed CLI commands should return error JSON."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps({
                "success": False,
                "errors": [{"code": "ERROR", "message": "Test error", "recovery_strategy": None}]
            }),
            stderr="Error message"
        )

        result = _run_cli_command(["apply-md", "bad.md", "--target-format", "docx"])

        assert result["success"] is False
        assert len(result["errors"]) > 0

    @patch("subprocess.run")
    @patch.dict("os.environ", {"OMNI_TEST_FAKE_PANDOC": "1"}, clear=False)
    def test_fake_pandoc_env_not_leaked_to_subprocess(self, mock_run):
        """OMNI_TEST_FAKE_PANDOC must NOT be inherited by the CLI subprocess.

        ULTRAREADY-VERIFY (2026-06-07): the MCP server used to invoke the
        CLI without an ``env=`` argument, so a test harness that started
        the MCP server with ``OMNI_TEST_FAKE_PANDOC=1`` would silently
        route every MCP conversion to a stub-DOCX. This test pins the
        contract that the seam is scrubbed before subprocess invocation.
        """
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"success": True, "output_path": "/tmp/out.docx"})
        )

        result = _run_cli_command(["apply-md", "input.md", "--target-format", "docx"])

        assert mock_run.called, "subprocess.run was not invoked"
        # Inspect the env kwarg that was passed to subprocess.run.
        kwargs = mock_run.call_args.kwargs
        assert "env" in kwargs, (
            "subprocess.run was called without env=; "
            "the FAKE_PANDOC seam will leak across the MCP boundary."
        )
        assert "OMNI_TEST_FAKE_PANDOC" not in kwargs["env"], (
            f"OMNI_TEST_FAKE_PANDOC leaked into subprocess env: {kwargs['env']!r}"
        )
        # Sanity: real env vars (PATH) are still present.
        assert "PATH" in kwargs["env"]
        # And the call still produced a real result.
        assert result["success"] is True


class TestApplyMdTool:
    """Tests for apply_md MCP tool."""
    
    @patch("subprocess.run")
    def test_apply_md_success(self, mock_run):
        """apply_md should return success on valid input."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "success": True,
                "output_path": "/tmp/result.docx",
                "errors": [],
                "warnings": [],
                "metadata": {}
            })
        )
        
        from orf.mcp.server import _register_tools, _mcp
        import orf.mcp.server as server_module
        
        # Get the tool function
        server = get_server()
        
        # Test path validation blocks traversal
        result = asyncio.run(server.call_tool("apply_md", {
            "input_md": "../../etc/passwd",
            "target_format": "docx"
        }))
        result_data = json.loads(result.content[0].text)
        assert result_data["success"] is False
        assert "PATH_NOT_ALLOWED" in str(result_data["errors"])


class TestApplyXLIFFTool:
    """Tests for apply_xliff MCP tool."""
    
    def test_apply_xliff_path_validation(self):
        """apply_xliff should validate paths."""
        server = get_server()
        
        result = asyncio.run(server.call_tool("apply_xliff", {
            "input_file": "../../etc/passwd",
            "xliff_path": "test.xlf",
            "output_path": "out.docx",
            "format": "docx"
        }))
        result_data = json.loads(result.content[0].text)
        assert result_data["success"] is False


class TestBatchConvertTool:
    """Tests for batch_convert MCP tool."""
    
    def test_batch_convert_invalid_path(self):
        """batch_convert should handle invalid paths."""
        server = get_server()
        
        result = asyncio.run(server.call_tool("batch_convert", {
            "input_dir": "../../dangerous",
            "target_format": "docx",
            "pattern": "*.md"
        }))
        result_data = json.loads(result.content[0].text)
        assert result_data["success_count"] == 0
        assert len(result_data["errors"]) > 0


class TestDetectFormatTool:
    """Tests for detect_format MCP tool."""
    
    def test_detect_format_invalid_path(self):
        """detect_format should handle invalid paths."""
        server = get_server()
        
        result = asyncio.run(server.call_tool("detect_format", {
            "file_path": "../../etc/passwd"
        }))
        result_data = json.loads(result.content[0].text)
        assert result_data["format"] == "UNKNOWN"
        assert result_data["confidence"] == 0.0


class TestInfoTool:
    """Tests for info MCP tool."""
    
    def test_info_invalid_path(self):
        """info should handle invalid paths."""
        server = get_server()
        
        result = asyncio.run(server.call_tool("info", {
            "file_path": "../../etc/passwd"
        }))
        result_data = json.loads(result.content[0].text)
        assert result_data["manifest_status"] == "error"


class TestMCPIntegration:
    """Full integration tests."""
    
    def test_server_starts(self):
        """MCP server should start without error."""
        server = get_server()
        assert server is not None
    
    @patch("subprocess.run")
    def test_full_apply_md_flow(self, mock_run):
        """Test complete apply_md flow with mocked CLI."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "success": True,
                "output_path": "/tmp/result.docx",
                "errors": [],
                "warnings": [],
                "metadata": {"format": "docx"}
            })
        )
        
        server = get_server()
        result = asyncio.run(server.call_tool("apply_md", {
            "input_md": "translated.md",
            "target_format": "docx"
        }))
        result_data = json.loads(result.content[0].text)
        
        assert result_data["success"] is True
        assert result_data["output_path"] == "/tmp/result.docx"