"""ORF MCP Server with FastMCP."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None


from orf.mcp.security import PathValidator
from orf.logging import get_logger

logger = get_logger("mcp.server")

# Global server instance
_mcp: Optional["FastMCP"] = None


def _run_cli_command(args: list[str]) -> dict:
    """Run ORF CLI command and return parsed JSON result."""
    result = subprocess.run(
        [sys.executable, "-m", "orf.cli"] + args + ["--json"],
        capture_output=True,
        text=True
    )

    # Bug 4 Fix: Handle empty stdout
    if not result.stdout.strip():
        logger.error(f"CLI returned empty stdout. args={args}, stderr={result.stderr[:500]}")
        return {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": "EMPTY_OUTPUT",
                "message": f"CLI returned empty. stderr: {result.stderr[:500]}",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}. stdout: {result.stdout[:200]}")
        return {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": "JSON_PARSE_ERROR",
                "message": f"JSON decode failed: {e}. Output: {result.stdout[:500]}",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }

    if result.returncode == 0:
        return parsed
    else:
        # CLI failed but might have valid error JSON
        return parsed if "success" in parsed else {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": "CLI_ERROR",
                "message": result.stderr or "Unknown error",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }


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
    def apply_xliff(
        input_file: str,
        xliff_path: str,
        output_path: str,
        format: str,
        xliff_content: Optional[str] = None,
        images: Optional[list[dict]] = None,
    ) -> str:
        """Apply XLIFF translation to original document with optional image injection.

        Args:
            input_file: Original document file path (skeleton).
            xliff_path: Translated XLIFF file path (mutually exclusive with xliff_content).
            output_path: Output file path.
            format: Output format (docx, pptx, epub, html, odt).
            xliff_content: Inline XLIFF content (mutually exclusive with xliff_path).
            images: Optional list of image placement data from OPP for precise image restoration.

        Returns:
            JSON result string.
        """
        # C4 fix: reject image placements that carry `file_path` (arbitrary
        # file read). MCP clients must provide `data_base64` only.
        if images:
            for idx, img_dict in enumerate(images):
                if isinstance(img_dict, dict) and img_dict.get("file_path"):
                    return json.dumps({
                        "success": False,
                        "output_path": None,
                        "errors": [{
                            "code": "FILE_PATH_NOT_ALLOWED",
                            "message": (
                                f"image[{idx}].file_path is not allowed via MCP; "
                                "supply data_base64 instead."
                            ),
                        }],
                        "warnings": [],
                        "metadata": {},
                    })
        # C5 fix: validate output_path against allowlist before subprocess
        valid_out, out_err = PathValidator.validate(output_path)
        if not valid_out:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {out_err}"}],
                "warnings": [],
                "metadata": {},
            })
        if xliff_path and xliff_content:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "MUTUALLY_EXCLUSIVE", "message": "xliff_path and xliff_content are mutually exclusive"}],
                "warnings": [],
                "metadata": {}
            })

        xliff_temp_path = None
        xliff_to_use = xliff_path
        if xliff_content:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xliff', delete=False)
            tmp.write(xliff_content)
            tmp.close()
            xliff_temp_path = tmp.name
            xliff_to_use = xliff_temp_path

        for p in [input_file, xliff_to_use]:
            valid, error = PathValidator.validate(p)
            if not valid:
                if xliff_temp_path:
                    try:
                        os.unlink(xliff_temp_path)
                    except Exception as exc:
                        logger.warning(
                            "Failed to remove temp xliff file %s: %s",
                            xliff_temp_path,
                            exc,
                        )
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": "PATH_NOT_ALLOWED", "message": error}],
                    "warnings": [],
                    "metadata": {}
                })

        args = [
            "apply-xliff", input_file,
            "--xliff", xliff_to_use,
            "--output", output_path,
            "--format", format,
        ]

        temp_created = False
        if images:
            images_data = []
            for img_dict in images:
                try:
                    img_bytes = None
                    if "data_base64" in img_dict and img_dict["data_base64"]:
                        img_bytes = base64.b64decode(img_dict["data_base64"])
                    elif "file_path" in img_dict and img_dict["file_path"]:
                        img_bytes = Path(img_dict["file_path"]).read_bytes()

                    if img_bytes:
                        b64 = base64.b64encode(img_bytes).decode("utf-8")
                        img_record = {
                            "data_base64": b64,
                            "mime_type": img_dict.get("mime_type", "image/png"),
                            "width": img_dict.get("width"),
                            "height": img_dict.get("height"),
                            "paragraph_index": img_dict.get("paragraph_index"),
                            "slide_index": img_dict.get("slide_index"),
                            "page_number": img_dict.get("page_number"),
                            "element_index": img_dict.get("element_index"),
                            "spine_index": img_dict.get("spine_index"),
                        }
                        images_data.append(img_record)
                except Exception as e:
                    logger.warning("Failed to process image placement: %s", e)
                    continue

            if images_data:
                fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="orf_images_")
                try:
                    os.write(fd, json.dumps(images_data).encode("utf-8"))
                    os.close(fd)
                    args.extend(["--images-json", temp_path])
                    temp_created = True
                except Exception as e:
                    logger.error("Failed to create temp images file: %s", e)
                    os.close(fd)
                    temp_created = False
            else:
                temp_created = False

        result = _run_cli_command(args)

        if temp_created:
            try:
                os.unlink(temp_path)
            except Exception as exc:
                logger.warning(
                    "Failed to remove temp file %s: %s", temp_path, exc
                )

        if xliff_temp_path:
            try:
                os.unlink(xliff_temp_path)
            except Exception as exc:
                logger.warning(
                    "Failed to remove temp xliff file %s: %s",
                    xliff_temp_path,
                    exc,
                )

        return json.dumps(result)

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


# Module-level aliases for in-process use (tests, callers that import these
# directly rather than going through the FastMCP server). The bodies of
# these wrappers duplicate the tool logic above so they work whether or not
# _register_tools() has been called (i.e., before get_server() is invoked,
# or in environments where FastMCP is unavailable). The @server.tool()
# decorators in _register_tools() remain the canonical MCP surface; these
# aliases are a parallel call path that the existing tests and any direct
# importers rely on.


def apply_md(input_md: str, target_format: str, output_path: Optional[str] = None) -> str:
    """Convert MD to target format. In-process equivalent of the MCP tool."""
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


def apply_xliff(
    input_file: str,
    xliff_path: str,
    output_path: str,
    format: str,
    xliff_content: Optional[str] = None,
    images: Optional[list[dict]] = None,
) -> str:
    """Apply XLIFF translation. In-process equivalent of the MCP tool."""
    # C4 fix: reject image placements that carry `file_path` (arbitrary
    # file read). MCP clients must provide `data_base64` only.
    if images:
        for idx, img_dict in enumerate(images):
            if isinstance(img_dict, dict) and img_dict.get("file_path"):
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{
                        "code": "FILE_PATH_NOT_ALLOWED",
                        "message": (
                            f"image[{idx}].file_path is not allowed via MCP; "
                            "supply data_base64 instead."
                        ),
                    }],
                    "warnings": [],
                    "metadata": {},
                })
    # C5 fix: validate output_path against allowlist before subprocess
    valid_out, out_err = PathValidator.validate(output_path)
    if not valid_out:
        return json.dumps({
            "success": False,
            "output_path": None,
            "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {out_err}"}],
            "warnings": [],
            "metadata": {},
        })
    if xliff_path and xliff_content:
        return json.dumps({
            "success": False,
            "output_path": None,
            "errors": [{"code": "MUTUALLY_EXCLUSIVE", "message": "xliff_path and xliff_content are mutually exclusive"}],
            "warnings": [],
            "metadata": {}
        })

    xliff_to_use = xliff_path
    xliff_temp_path = None
    if xliff_content:
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xliff', delete=False)
        tmp.write(xliff_content)
        tmp.close()
        xliff_temp_path = tmp.name
        xliff_to_use = xliff_temp_path

    for p in [input_file, xliff_to_use]:
        valid, error = PathValidator.validate(p)
        if not valid:
            if xliff_temp_path:
                try:
                    os.unlink(xliff_temp_path)
                except Exception as exc:
                    logger.warning(
                        "Failed to remove temp xliff file %s: %s",
                        xliff_temp_path,
                        exc,
                    )
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": error}],
                "warnings": [],
                "metadata": {}
            })

    args = [
        "apply-xliff", input_file,
        "--xliff", xliff_to_use,
        "--output", output_path,
        "--format", format,
    ]

    temp_created = False
    temp_path = ""
    if images:
        images_data = []
        for img_dict in images:
            try:
                img_bytes = None
                if "data_base64" in img_dict and img_dict["data_base64"]:
                    img_bytes = base64.b64decode(img_dict["data_base64"])
                elif "file_path" in img_dict and img_dict["file_path"]:
                    img_bytes = Path(img_dict["file_path"]).read_bytes()

                if img_bytes:
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    img_record = {
                        "data_base64": b64,
                        "mime_type": img_dict.get("mime_type", "image/png"),
                        "width": img_dict.get("width"),
                        "height": img_dict.get("height"),
                        "paragraph_index": img_dict.get("paragraph_index"),
                        "slide_index": img_dict.get("slide_index"),
                        "page_number": img_dict.get("page_number"),
                        "element_index": img_dict.get("element_index"),
                        "spine_index": img_dict.get("spine_index"),
                    }
                    images_data.append(img_record)
            except Exception as e:
                logger.warning("Failed to process image placement: %s", e)
                continue

        if images_data:
            fd, temp_path = tempfile.mkstemp(suffix=".json", prefix="orf_images_")
            try:
                os.write(fd, json.dumps(images_data).encode("utf-8"))
                os.close(fd)
                args.extend(["--images-json", temp_path])
                temp_created = True
            except Exception as e:
                logger.error("Failed to create temp images file: %s", e)
                os.close(fd)
                temp_created = False

    result = _run_cli_command(args)

    if temp_created:
        try:
            os.unlink(temp_path)
        except Exception as exc:
            logger.warning(
                "Failed to remove temp file %s: %s", temp_path, exc
            )

    if xliff_temp_path:
        try:
            os.unlink(xliff_temp_path)
        except Exception as exc:
            logger.warning(
                "Failed to remove temp xliff file %s: %s",
                xliff_temp_path,
                exc,
            )

    return json.dumps(result)


def main():
    """Run the MCP server."""
    server = get_server()
    server.run()


if __name__ == "__main__":
    main()