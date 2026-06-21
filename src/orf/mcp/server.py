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
# 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
from orf.mcp.auth import check_auth, auth_failure_response
# H5: token bucket DoS rate limiter (2026-06-20)
from orf.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response

# ULTRAREADY-VERIFY (2026-06-07): env vars that must NEVER be inherited
# by the CLI subprocess. These are test-only seams — if a test harness
# started the MCP server with one of them set, every MCP conversion
# would silently produce fake output. The list is centralized here so
# adding a new seam in the future means updating one constant + one test.
_MCP_SCRUB_ENV_KEYS = frozenset({
    "OMNI_TEST_FAKE_PANDOC",
    "OMNI_TEST_FAKE_LLM",
    "OMNI_TEST_FAKE",
    "OMNI_TEST_MOCK",
    "OMNI_TEST_STUB",
})

from orf.mcp.security import PathValidator
from orf.mcp.config import MCPConfig, load_config
from orf.logging import get_logger
logger = get_logger("mcp.server")

# Global server instance
_mcp: Optional["FastMCP"] = None

# Config & validator
_orf_config: MCPConfig = load_config()
_path_validator = PathValidator(
    allowed_directories=_orf_config.allowed_directories or [Path.cwd()],
    max_file_size_bytes=_orf_config.max_file_size_mb * 1024 * 1024,
)


def _run_cli_command(args: list[str]) -> dict:
    """Run ORF CLI command and return parsed JSON result."""
    # ULTRAREADY-VERIFY (2026-06-07): scrub test-only env vars before
    # invoking the CLI subprocess. Without this, a test harness that
    # started the MCP server with OMNI_TEST_FAKE_PANDOC=1 would silently
    # route every MCP conversion to a stub-DOCX (the FAKE_PANDOC seam
    # in orf/cli.py:191-212 monkey-patches subprocess.run for the
    # lifetime of the CLI process).
    scrubbed_env = {
        k: v for k, v in os.environ.items()
        if k not in _MCP_SCRUB_ENV_KEYS
    }
    result = subprocess.run(
        [sys.executable, "-m", "orf.cli"] + args + ["--json"],
        capture_output=True,
        text=True,
        env=scrubbed_env,
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


def _safe_unlink(path: str) -> bool:
    """Resolve+revalidate path before unlink; refuse to follow symlinks."""
    try:
        resolved = Path(path).resolve()
    except (ValueError, OSError):
        return False
    if Path(path).is_symlink():
        return False
    result = _path_validator.validate_path(str(resolved), allow_missing=True)
    if not result.success:
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False


def _safe_temp_output(suffix: str, parent: Optional[Path] = None) -> str:
    """Create a tempfile inside parent dir (must be in an allowed dir)."""
    if parent is None:
        parent = Path.cwd()
    parent_resolved = parent.resolve()
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="orf_mcp_", dir=str(parent_resolved))
    os.close(fd)
    return name


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
    def apply_md(
        input_md: str,
        target_format: str,
        output_path: Optional[str] = None,
        images: Optional[list[dict]] = None,
        separate_images: bool = True,
        reference_doc: Optional[str] = None,
        template: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        lang: Optional[str] = None,
        embed_images: bool = False,
        text_only: bool = False,
        max_file_size_mb: Optional[float] = None,
    ) -> str:
        """Convert MD to target format.
        Images (from OPP ``images.json``) are extracted during conversion into
        ``images.zip + images.json`` alongside the output DOCX when
        ``separate_images=True`` (default). When ``separate_images=False``,
        images embedded as base64 data URIs in the markdown are decoded and
        placed inline in the output document by Pandoc.
        """
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
        # Validate input path
        result = _path_validator.validate_path(input_md)
        if not result.success:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": result.error, "recovery_strategy": None}],
                "warnings": [],
                "metadata": {}
            })

        # Validate output path if provided
        if output_path:
            result_out = _path_validator.validate_path(output_path, allow_missing=True)
            if not result_out.success:
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {result_out.error}", "recovery_strategy": None}],
                    "warnings": [],
                    "metadata": {}
                })

        for path_param, path_value in (("reference_doc", reference_doc), ("template", template)):
            if path_value:
                pv = _path_validator.validate_path(path_value, allow_missing=True)
                if not pv.success:
                    return json.dumps({
                        "success": False,
                        "output_path": None,
                        "errors": [{"code": "PATH_NOT_ALLOWED",
                                    "message": f"{path_param}: {pv.error}",
                                    "recovery_strategy": None}],
                        "warnings": [],
                        "metadata": {}
                    })

        args = ["apply-md", input_md, "--target-format", target_format]
        if output_path:
            args.extend(["--output", output_path])
        if not separate_images:
            args.append("--no-separate-images")
        if reference_doc:
            args.extend(["--reference-doc", reference_doc])
        if template:
            args.extend(["--template", template])
        if title:
            args.extend(["--title", title])
        if author:
            args.extend(["--author", author])
        if lang:
            args.extend(["--lang", lang])
        if embed_images:
            args.append("--embed-images")
        if text_only:
            args.append("--text-only")
        if max_file_size_mb is not None:
            args.extend(["--max-file-size-mb", str(max_file_size_mb)])

        # Write images data to a temp JSON file and pass via --images-json.
        images_json_path: str | None = None
        if images:
            try:
                fd, images_json_path = tempfile.mkstemp(suffix=".json", prefix="orf_mcp_images_")
                os.close(fd)
                with open(images_json_path, "w") as f:
                    json.dump({"images": images}, f)
                args.extend(["--images-json", images_json_path])
            except Exception as e:
                logger.warning("Failed to write images temp file: %s", e)

        try:
            return json.dumps(_run_cli_command(args))
        finally:
            if images_json_path:
                _safe_unlink(images_json_path)

    @server.tool()
    def apply_xliff(
        input_file: str,
        xliff_path: str,
        output_path: str,
        format: str,
        xliff_content: Optional[str] = None,
        images: Optional[list[dict]] = None,
        force: bool = False,
        no_cache: bool = False,
        max_file_size_mb: Optional[float] = None,
    ) -> str:
        """Apply XLIFF translation to original document with optional image injection.

        Args:
            force: Bypass skeleton-vs-format validation for cross-format
                conversions (e.g. DOCX XLIFF → PPTX). CLI: --force.
            no_cache: Skip ORF's content-addressed cache. CLI: --no-cache.
            max_file_size_mb: Reject inputs above this size. CLI: --max-file-size-mb.
        """
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
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
        result_out = _path_validator.validate_path(output_path, allow_missing=True)
        if not result_out.success:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {result_out.error}"}],
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
            result_p = _path_validator.validate_path(p)
            if not result_p.success:
                if xliff_temp_path:
                    _safe_unlink(xliff_temp_path)
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": "PATH_NOT_ALLOWED", "message": result_p.error}],
                    "warnings": [],
                    "metadata": {}
                })

        args = [
            "apply-xliff", input_file,
            "--xliff", xliff_to_use,
            "--output", output_path,
            "--format", format,
        ]
        if force:
            args.append("--force")
        if no_cache:
            args.append("--no-cache")
        if max_file_size_mb is not None:
            args.extend(["--max-file-size-mb", str(max_file_size_mb)])

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
            _safe_unlink(temp_path)

        if xliff_temp_path:
            _safe_unlink(xliff_temp_path)

        return json.dumps(result)

    @server.tool()
    def batch_convert(input_dir: str, target_format: str, pattern: str = "*.md", auth_token: Optional[str] = None) -> str:
        """Batch convert MD files."""
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
        # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
        auth_ok, _ = check_auth(auth_token)
        if not auth_ok:
            return json.dumps(auth_failure_response(), ensure_ascii=False)
        result_dir = _path_validator.validate_path(input_dir, allow_missing=True)
        if not result_dir.success:
            return json.dumps({
                "success_count": 0,
                "fail_count": 0,
                "total": 0,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": result_dir.error, "recovery_strategy": None}]
            })

        args = ["convert-batch", input_dir, "--target-format", target_format, "--pattern", pattern]
        return json.dumps(_run_cli_command(args))

    @server.tool()
    def detect_format(file_path: str, auth_token: Optional[str] = None) -> str:
        """Detect document format."""
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
        # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
        auth_ok, _ = check_auth(auth_token)
        if not auth_ok:
            return json.dumps(auth_failure_response(), ensure_ascii=False)
        result_df = _path_validator.validate_path(file_path)
        if not result_df.success:
            return json.dumps({"format": "UNKNOWN", "confidence": 0.0})

        args = ["info", file_path]
        result = _run_cli_command(args)
        return json.dumps({"format": result.get("format", "UNKNOWN"), "confidence": 1.0})

    @server.tool()
    def info(file_path: str, auth_token: Optional[str] = None) -> str:
        """Get document information."""
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
        # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
        auth_ok, _ = check_auth(auth_token)
        if not auth_ok:
            return json.dumps(auth_failure_response(), ensure_ascii=False)
        result_info = _path_validator.validate_path(file_path)
        if not result_info.success:
            return json.dumps({
                "format": "UNKNOWN",
                "size_mb": 0.0,
                "resource_count": None,
                "manifest_status": "error"
            })

        return json.dumps(_run_cli_command(["info", file_path]))

    @server.tool()
    def ping(auth_token: Optional[str] = None) -> str:
        """Health check endpoint. Returns module name and version."""
        # H5: token bucket rate limiter
        rate_ok, rate_err = check_rate_limit()
        if not rate_ok:
            return json.dumps({**rate_limit_failure_response(), "error": rate_err})
        # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
        auth_ok, _ = check_auth(auth_token)
        if not auth_ok:
            return json.dumps(auth_failure_response(), ensure_ascii=False)
        from orf import __version__ as _orf_version
        return json.dumps(
            {"success": True, "module": "orf", "version": _orf_version},
            ensure_ascii=False,
        )


# Module-level aliases for in-process use (tests, callers that import these
# directly rather than going through the FastMCP server). The bodies of
# these wrappers duplicate the tool logic above so they work whether or not
# _register_tools() has been called (i.e., before get_server() is invoked,
# or in environments where FastMCP is unavailable). The @server.tool()
# decorators in _register_tools() remain the canonical MCP surface; these
# aliases are a parallel call path that the existing tests and any direct
# importers rely on.


def apply_md(
    input_md: str,
    target_format: str,
    output_path: Optional[str] = None,
    images: Optional[list[dict]] = None,
    separate_images: bool = True,
    reference_doc: Optional[str] = None,
    template: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    lang: Optional[str] = None,
    embed_images: bool = False,
    text_only: bool = False,
    max_file_size_mb: Optional[float] = None,
    auth_token: Optional[str] = None,
) -> str:
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    """Convert MD to target format. In-process equivalent of the MCP tool."""
    result = _path_validator.validate_path(input_md)
    if not result.success:
        return json.dumps({
            "success": False,
            "output_path": None,
            "errors": [{"code": "PATH_NOT_ALLOWED", "message": result.error, "recovery_strategy": None}],
            "warnings": [],
            "metadata": {}
        })

    if output_path:
        result_out = _path_validator.validate_path(output_path, allow_missing=True)
        if not result_out.success:
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {result_out.error}", "recovery_strategy": None}],
                "warnings": [],
                "metadata": {}
            })

    for path_param, path_value in (("reference_doc", reference_doc), ("template", template)):
        if path_value:
            pv = _path_validator.validate_path(path_value, allow_missing=True)
            if not pv.success:
                return json.dumps({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": "PATH_NOT_ALLOWED",
                                "message": f"{path_param}: {pv.error}",
                                "recovery_strategy": None}],
                    "warnings": [],
                    "metadata": {}
                })

    args = ["apply-md", input_md, "--target-format", target_format]
    if output_path:
        args.extend(["--output", output_path])
    if not separate_images:
        args.append("--no-separate-images")
    if reference_doc:
        args.extend(["--reference-doc", reference_doc])
    if template:
        args.extend(["--template", template])
    if title:
        args.extend(["--title", title])
    if author:
        args.extend(["--author", author])
    if lang:
        args.extend(["--lang", lang])
    if embed_images:
        args.append("--embed-images")
    if text_only:
        args.append("--text-only")
    if max_file_size_mb is not None:
        args.extend(["--max-file-size-mb", str(max_file_size_mb)])

    images_json_path: str | None = None
    if images:
        try:
            fd, images_json_path = tempfile.mkstemp(suffix=".json", prefix="orf_mcp_images_")
            os.close(fd)
            with open(images_json_path, "w") as f:
                json.dump({"images": images}, f)
            args.extend(["--images-json", images_json_path])
        except Exception as e:
            logger.warning("Failed to write images temp file: %s", e)

    try:
        return json.dumps(_run_cli_command(args))
    finally:
        if images_json_path:
            _safe_unlink(images_json_path)


def apply_xliff(
    input_file: str,
    xliff_path: str,
    output_path: str,
    format: str,
    xliff_content: Optional[str] = None,
    images: Optional[list[dict]] = None,
    force: bool = False,
    no_cache: bool = False,
    max_file_size_mb: Optional[float] = None,
    auth_token: Optional[str] = None,
) -> str:
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
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
    result_out = _path_validator.validate_path(output_path, allow_missing=True)
    if not result_out.success:
        return json.dumps({
            "success": False,
            "output_path": None,
            "errors": [{"code": "PATH_NOT_ALLOWED", "message": f"output_path: {result_out.error}"}],
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
        result_p = _path_validator.validate_path(p)
        if not result_p.success:
            if xliff_temp_path:
                _safe_unlink(xliff_temp_path)
            return json.dumps({
                "success": False,
                "output_path": None,
                "errors": [{"code": "PATH_NOT_ALLOWED", "message": result_p.error}],
                "warnings": [],
                "metadata": {}
            })

    args = [
        "apply-xliff", input_file,
        "--xliff", xliff_to_use,
        "--output", output_path,
        "--format", format,
    ]
    if force:
        args.append("--force")
    if no_cache:
        args.append("--no-cache")
    if max_file_size_mb is not None:
        args.extend(["--max-file-size-mb", str(max_file_size_mb)])

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
        _safe_unlink(temp_path)

    if xliff_temp_path:
        _safe_unlink(xliff_temp_path)

    return json.dumps(result)


def batch_convert(input_dir: str, target_format: str, pattern: str = "*.md", auth_token: Optional[str] = None) -> str:
    """Batch convert MD files. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    result_dir = _path_validator.validate_path(input_dir, allow_missing=True)
    if not result_dir.success:
        return json.dumps({
            "success_count": 0,
            "fail_count": 0,
            "total": 0,
            "errors": [{"code": "PATH_NOT_ALLOWED", "message": result_dir.error, "recovery_strategy": None}]
        })

    args = ["convert-batch", input_dir, "--target-format", target_format, "--pattern", pattern]
    return json.dumps(_run_cli_command(args))


def detect_format(file_path: str, auth_token: Optional[str] = None) -> str:
    """Detect document format. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    result_df = _path_validator.validate_path(file_path)
    if not result_df.success:
        return json.dumps({"format": "UNKNOWN", "confidence": 0.0})

    args = ["info", file_path]
    result = _run_cli_command(args)
    return json.dumps({"format": result.get("format", "UNKNOWN"), "confidence": 1.0})


def info(file_path: str, auth_token: Optional[str] = None) -> str:
    """Get document information. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    result_info = _path_validator.validate_path(file_path)
    if not result_info.success:
        return json.dumps({
            "format": "UNKNOWN",
            "size_mb": 0.0,
            "resource_count": None,
            "manifest_status": "error"
        })

    return json.dumps(_run_cli_command(["info", file_path]))


def ping(auth_token: Optional[str] = None) -> str:
    """Health check endpoint. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    from orf import __version__ as _orf_version
    return json.dumps(
        {"success": True, "module": "orf", "version": _orf_version},
        ensure_ascii=False,
    )


def main():
    """Run the MCP server."""
    server = get_server()
    server.run()


if __name__ == "__main__":
    main()