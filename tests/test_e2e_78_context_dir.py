"""Tests for context_dir mechanism (improvement #2).

When an agent passes a context_dir parameter, relative paths in the
tool call get resolved against it before path validation.
"""
from __future__ import annotations

import json
import os
import sys


# Ensure tests are run from the suite root (where ORF PathValidator allows writes)
EXPECTED_CWD = "/mnt/d/贯维/Omni_Suite"

# MUST run before any orf.mcp.* import: path_validator is a module-level
# singleton in orf.mcp.common that reads ORF_MCP_ALLOWED_DIRS at import.
if "ORF_MCP_ALLOWED_DIRS" not in os.environ:
    os.environ["ORF_MCP_ALLOWED_DIRS"] = EXPECTED_CWD


def test_context_dir_resolves_relative_reference_doc():
    """When context_dir is set, a relative reference_doc path is resolved
    against context_dir before the path validator runs."""
    from orf.mcp.tools.apply_md import apply_md
    from orf.mcp import server as srv

    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return {"success": True, "output_path": "ctx_out.docx"}

    orig = srv._run_cli_command
    srv._run_cli_command = fake_run
    try:
        # Create a context subdir + put a fake reference doc inside
        ctx_dir = "test_context_dir"
        os.makedirs(ctx_dir, exist_ok=True)
        ref_name = "fake_ref.docx"
        ref_path = os.path.join(ctx_dir, ref_name)
        with open(ref_path, "wb") as f:
            f.write(b"PK\x03\x04fake")  # fake docx bytes

        result = apply_md(
            content="# Hello",
            target_format="docx",
            reference_doc=ref_name,  # relative path
            context_dir=EXPECTED_CWD,
            output_path="ctx_out.docx",
        )
    finally:
        srv._run_cli_command = orig
        # Cleanup
        if os.path.exists(ref_path):
            os.unlink(ref_path)
        if os.path.exists(ctx_dir):
            os.rmdir(ctx_dir)

    data = json.loads(result)
    assert data["success"] is True, f"unexpected result: {data}"

    # The --reference-doc arg should be the absolute path, not the relative
    ref_idx = captured["args"].index("--reference-doc")
    ref_arg = captured["args"][ref_idx + 1]
    assert ref_arg == os.path.join(EXPECTED_CWD, ref_name), (
        f"context_dir did not resolve relative path. got: {ref_arg}"
    )


def test_context_dir_absolute_path_unchanged():
    """Absolute paths win over context_dir (don't get re-prepended)."""
    from orf.mcp.tools.apply_md import apply_md
    from orf.mcp import server as srv

    # Create a real ref file so the path validation passes
    ref_abs = os.path.join(EXPECTED_CWD, "_test_absolute_ref.docx")
    with open(ref_abs, "wb") as f:
        f.write(b"PK\x03\x04fake")

    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return {"success": True, "output_path": "ctx_out.docx"}

    orig = srv._run_cli_command
    srv._run_cli_command = fake_run
    try:
        # Absolute reference_doc + valid context_dir (in allowed dirs).
        # The absolute reference_doc should be preserved as-is — context_dir
        # only applies to relative paths.
        result = apply_md(
            content="# Hello",
            target_format="docx",
            reference_doc=ref_abs,
            context_dir=EXPECTED_CWD,  # valid (in allowed dirs)
            output_path="ctx_out.docx",
        )
    finally:
        srv._run_cli_command = orig
        if os.path.exists(ref_abs):
            os.unlink(ref_abs)

    data = json.loads(result)
    assert data["success"] is True, f"unexpected result: {data}"
    ref_idx = captured["args"].index("--reference-doc")
    ref_arg = captured["args"][ref_idx + 1]
    assert ref_arg == ref_abs, (
        f"absolute path was modified: {ref_arg}"
    )


def test_context_dir_none_uses_path_as_is():
    """When context_dir is None, the path is used as-is (backward compat)."""
    from orf.mcp.tools.apply_md import apply_md
    from orf.mcp import server as srv

    captured = {}
    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        return {"success": True, "output_path": "out.docx"}

    orig = srv._run_cli_command
    srv._run_cli_command = fake_run
    try:
        result = apply_md(
            content="# Hello",
            target_format="docx",
            reference_doc="just_relative.docx",  # no context_dir
            output_path="out.docx",
        )
    finally:
        srv._run_cli_command = orig

    data = json.loads(result)
    # Should fail (path not in allowed dirs) but the failure is
    # because the relative path is treated as cwd-relative, NOT
    # because context_dir was applied. Verify the path is the
    # unmodified relative one.
    ref_idx = captured["args"].index("--reference-doc")
    ref_arg = captured["args"][ref_idx + 1]
    assert ref_arg == "just_relative.docx", (
        f"no-context_dir path was modified: {ref_arg}"
    )


def test_context_dir_validated_against_allowed_dirs():
    """A context_dir outside the allowed dirs returns PATH_NOT_ALLOWED."""
    from orf.mcp.tools.apply_md import apply_md

    result = apply_md(
        content="# Hello",
        target_format="docx",
        context_dir="/some/path/that/is/not/allowed",
        output_path="out.docx",
    )
    data = json.loads(result)
    assert data["success"] is False
    assert any(
        err.get("code") == "PATH_NOT_ALLOWED" and "context_dir" in err.get("message", "")
        for err in data.get("errors", [])
    )
