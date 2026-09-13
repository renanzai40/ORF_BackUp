"""apply_md tool — Convert MD to target format for ORF MCP Server."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from orf.mcp._errors import (
    INLINE_CONTENT_WRITE_FAILED,
    INLINE_REFERENCE_DOC_WRITE_FAILED,
    MISSING_INPUT,
    MUTUALLY_EXCLUSIVE,
    PATH_NOT_ALLOWED,
)
from orf.mcp.auth import auth_failure_response, check_auth
from orf.mcp.common import (
    augment_error,
    get_path_validator,
    logger,
    resolve_context_path,
    safe_unlink,
    success_response,
)
from orf.mcp.manifest import written_files
from orf.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response


def apply_md(
    input_md: Optional[str] = None,
    target_format: str = "",
    output_path: Optional[str] = None,
    images: Optional[list[dict]] = None,
    separate_images: bool = True,
    reference_doc: Optional[str] = None,
    reference_doc_content: Optional[str] = None,
    template: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    lang: Optional[str] = None,
    embed_images: bool = False,
    text_only: bool = False,
    max_file_size_mb: Optional[float] = None,
    auth_token: Optional[str] = None,
    traceparent: Optional[str] = None,
    content: Optional[str] = None,
    context_dir: Optional[str] = None,
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
    # E2E-76: accept inline markdown via ``content`` alongside the
    # path-based ``input_md`` so text-in/text-out agent flows work.
    if not input_md and not content:
        return json.dumps(augment_error({
            "success": False,
            "output_path": None,
            "errors": [{
                "code": MISSING_INPUT,
                "message": "Either input_md (path) or content (inline markdown) is required.",
                "recovery_strategy": None,
            }],
            "warnings": [],
            "metadata": {},
        }))
    if input_md and content:
        return json.dumps(augment_error({
            "success": False,
            "output_path": None,
            "errors": [{
                "code": MUTUALLY_EXCLUSIVE,
                "message": "input_md and content are mutually exclusive — supply one, not both.",
                "recovery_strategy": None,
            }],
            "warnings": [],
            "metadata": {},
        }))

    if reference_doc and reference_doc_content:
        return json.dumps(augment_error({
            "success": False,
            "output_path": None,
            "errors": [{
                "code": MUTUALLY_EXCLUSIVE,
                "message": "reference_doc and reference_doc_content are mutually exclusive — supply one, not both.",
                "recovery_strategy": None,
            }],
            "warnings": [],
            "metadata": {},
        }))

    content_temp_path: str | None = None
    if content is not None:
        # PathValidator requires the path to live under an allowed dir;
        # mkstemp with an explicit parent keeps it inside cwd.
        parent = Path.cwd()
        try:
            parent_resolved = parent.resolve()
            fd, content_temp_path = tempfile.mkstemp(
                suffix=".md", prefix="orf_mcp_inline_", dir=str(parent_resolved),
            )
            os.close(fd)
            with open(content_temp_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error("Failed to write inline content to tempfile: %s", e)
            return json.dumps(augment_error({
                "success": False,
                "output_path": None,
                "errors": [{
                    "code": INLINE_CONTENT_WRITE_FAILED,
                    "message": f"Failed to materialize inline content: {e}",
                    "recovery_strategy": None,
                }],
                "warnings": [],
                "metadata": {},
            }))
        input_md = content_temp_path

    reference_doc_temp_path: str | None = None
    if reference_doc_content is not None:
        # Write inline DOCX content to a temp file in cwd (allowed by
        # PathValidator). Accept either base64-encoded bytes or raw text
        # (pandoc reference docs are binary .docx — use base64).
        parent = Path.cwd()
        try:
            parent_resolved = parent.resolve()
            fd, reference_doc_temp_path = tempfile.mkstemp(
                suffix=".docx", prefix="orf_mcp_refdoc_", dir=str(parent_resolved),
            )
            os.close(fd)
            # Try base64 first; fall back to UTF-8 text bytes if that fails.
            import base64
            try:
                docx_bytes = base64.b64decode(reference_doc_content, validate=True)
            except Exception:  # expected
                docx_bytes = reference_doc_content.encode("utf-8")
            with open(reference_doc_temp_path, "wb") as f:
                f.write(docx_bytes)
        except Exception as e:
            logger.error("Failed to write reference_doc_content to tempfile: %s", e)
            if reference_doc_temp_path:
                safe_unlink(reference_doc_temp_path)
            return json.dumps(augment_error({
                "success": False,
                "output_path": None,
                "errors": [{
                    "code": INLINE_REFERENCE_DOC_WRITE_FAILED,
                    "message": f"Failed to materialize inline reference_doc: {e}",
                    "recovery_strategy": None,
                }],
                "warnings": [],
                "metadata": {},
            }))
        reference_doc = reference_doc_temp_path

    try:
        result = get_path_validator().validate_path(input_md)
        if not result.success:
            return json.dumps(augment_error({
                "success": False,
                "output_path": None,
                "errors": [{"code": PATH_NOT_ALLOWED, "message": result.error, "recovery_strategy": None}],
                "warnings": [],
                "metadata": {}
            }))

        # Resolve relative paths against context_dir (agent convenience)
        if context_dir:
            cv = get_path_validator().validate_path(context_dir)
            if not cv.success:
                return json.dumps(augment_error({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": PATH_NOT_ALLOWED, "message": f"context_dir: {cv.error}", "recovery_strategy": None}],
                    "warnings": [],
                    "metadata": {}
                }))
        output_path = resolve_context_path(output_path, context_dir)
        reference_doc = resolve_context_path(reference_doc, context_dir)
        template = resolve_context_path(template, context_dir)

        if output_path:
            result_out = get_path_validator().validate_path(output_path, allow_missing=True)
            if not result_out.success:
                return json.dumps(augment_error({
                    "success": False,
                    "output_path": None,
                    "errors": [{"code": PATH_NOT_ALLOWED, "message": f"output_path: {result_out.error}", "recovery_strategy": None}],
                    "warnings": [],
                    "metadata": {}
                }))

        for path_param, path_value in (("reference_doc", reference_doc), ("template", template)):
            if path_value:
                pv = get_path_validator().validate_path(path_value, allow_missing=True)
                if not pv.success:
                    return json.dumps(augment_error({
                        "success": False,
                        "output_path": None,
                        "errors": [{"code": PATH_NOT_ALLOWED,
                                    "message": f"{path_param}: {pv.error}",
                                    "recovery_strategy": None}],
                        "warnings": [],
                        "metadata": {}
                    }))

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
            from orf.mcp.server import _run_cli_command
            cli_result = _run_cli_command(args)
            if cli_result.get("success"):
                response = success_response(cli_result)
                response["outputs"], response["sidecars"] = written_files(
                    cli_result.get("output_path")
                )
                return json.dumps(response)
            return json.dumps(augment_error(cli_result))
        finally:
            if images_json_path:
                safe_unlink(images_json_path)
    finally:
        if content_temp_path:
            safe_unlink(content_temp_path)
        if reference_doc_temp_path:
            safe_unlink(reference_doc_temp_path)
