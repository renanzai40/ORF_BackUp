"""ORF MCP Server with FastMCP."""

from typing import Optional
import json
from pathlib import Path
import subprocess
import sys

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None

from orf.mcp.schemas import (
    ApplyMdInput, ApplyMdResult, ApplyXLIFFInput, ApplyXLIFFResult,
    BatchConvertInput, BatchResult, DetectFormatInput, DetectFormatResult,
    InfoInput, InfoResult, ErrorDetail
)
from orf.mcp.security import PathValidator

# Global server instance
_mcp: Optional["FastMCP"] = None


def _run_cli_command(args: list[str]) -> dict:
    """Run ORF CLI command and return parsed JSON result."""
    result = subprocess.run(
        [sys.executable, "-m", "orf.cli"] + args + ["--json"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        # Try to parse error as JSON
        try:
            return json.loads(result.stdout)
        except:
            return {"success": False, "errors": [{"code": "CLI_ERROR", "message": result.stderr or "Unknown error", "recovery_strategy": None}]}


def get_server() -> "FastMCP":
    """Get or create the MCP server instance."""
    global _mcp
    if _mcp is None:
        if FastMCP is None:
            raise ImportError("fastmcp not installed. Run: pip install fastmcp")
        _mcp = FastMCP("ORF MCP Server")
        _register_tools()
    return _mcp


def _register_tools():
    """Register all MCP tools."""
    server = _mcp

    @server.tool()
    def apply_md(input_md: str, target_format: str, output_path: Optional[str] = None) -> str:
        """Convert MD to target format."""
        # Validate path
        valid, error = PathValidator.validate(input_md)
        if not valid:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": error, "recovery_strategy": None}],
                "warnings": [],
                "metadata": {}
            })

        args = ["apply-md", input_md, "--target-format", target_format]
        if output_path:
            args.extend(["--output", output_path])

        return json.dumps(_run_cli_command(args))

    @server.tool()
    def apply_xliff(input_file: str, xliff_path: str, output_path: str, format: str) -> str:
        """Apply XLIFF translation to original document."""
        # Validate paths
        for p in [input_file, xliff_path]:
            valid, error = PathValidator.validate(p)
            if not valid:
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": "PATH_NOT_ALLOWED", "message": error, "recovery_strategy": None}],
                    "warnings": [],
                    "metadata": {}
                })

        args = ["apply-xliff", input_file, "--xliff", xliff_path, "--output", output_path, "--format", format]
        return json.dumps(_run_cli_command(args))

    @server.tool()
    def batch_convert(input_dir: str, target_format: str, pattern: str = "*.md") -> str:
        """Batch convert MD files."""
        valid, error = PathValidator.validate(input_dir)
        if not valid:
            return json.dumps({
                "success_count": 0,
                "fail_count": 0,
                "total": 0,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": error, "recovery_strategy": None}]
            })

        args = ["convert-batch", input_dir, "--target-format", target_format, "--pattern", pattern]
        return json.dumps(_run_cli_command(args))

    @server.tool()
    def detect_format(file_path: str) -> str:
        """Detect document format."""
        valid, error = PathValidator.validate(file_path)
        if not valid:
            return json.dumps({"format": "UNKNOWN", "confidence": 0.0})

        args = ["info", file_path]
        result = _run_cli_command(args)
        return json.dumps({"format": result.get("format", "UNKNOWN"), "confidence": 1.0})

    @server.tool()
    def info(file_path: str) -> str:
        """Get document information."""
        valid, error = PathValidator.validate(file_path)
        if not valid:
            return json.dumps({
                "format": "UNKNOWN",
                "size_mb": 0.0,
                "resource_count": None,
                "manifest_status": "error"
            })

        return json.dumps(_run_cli_command(["info", file_path]))


def main():
    """Run the MCP server."""
    server = get_server()
    server.run()


if __name__ == "__main__":
    main()