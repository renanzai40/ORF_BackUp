"""Tests for ORF MCP apply_md reference_doc_content inline content.

Closes the agent-pain-point of "I have a reference DOCX, I don't want
to write it to a file just to pass a path to the MCP tool."
"""
from __future__ import annotations

import base64
import json


# Minimal valid DOCX bytes (zip with a single empty document.xml).
# We build it at runtime so the test file doesn't need a binary blob.
# The exact byte content doesn't matter — pandoc will fail to render an
# empty docx but the apply_md TOOL's temp-file + args building should
# still work for the test.
import io
import zipfile


def _minimal_docx_b64() -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<?xml version='1.0'?><x/>")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_reference_doc_content_writes_tempfile():
    """Verify reference_doc_content is accepted, base64-decoded, and the
    resulting temp file is passed as the --reference-doc CLI arg."""
    import asyncio
    from orf.mcp.tools.apply_md import apply_md

    # Stub out _run_cli_command to capture the args + verify the temp
    # file BEFORE apply_md's finally block cleans it up.
    from orf.mcp import server as srv
    import os

    captured = {}
    def fake_run(args, **kwargs):
        # Snapshot of state at the moment CLI was invoked
        captured["args"] = list(args)
        # Verify the temp file is still on disk at this point
        ref_idx = args.index("--reference-doc")
        captured["ref_path"] = args[ref_idx + 1]
        captured["ref_path_exists_at_run"] = os.path.exists(captured["ref_path"])
        return {"success": True, "output_path": "test_output.docx"}

    orig = srv._run_cli_command
    srv._run_cli_command = fake_run
    try:
        result = apply_md(
            content="# Hello",
            target_format="docx",
            reference_doc_content=_minimal_docx_b64(),
            output_path="test_output.docx",
        )
    finally:
        srv._run_cli_command = orig

    data = json.loads(result)
    assert data["success"] is True, f"unexpected result: {data}"

    # Verify the temp file existed at the moment the CLI was invoked
    assert captured["ref_path"].endswith(".docx")
    assert captured["ref_path_exists_at_run"] is True, (
        f"reference_doc temp file did not exist at CLI run: {captured['ref_path']}"
    )


def test_reference_doc_and_content_mutually_exclusive():
    """If both reference_doc and reference_doc_content are provided,
    return MUTUALLY_EXCLUSIVE error."""
    from orf.mcp.tools.apply_md import apply_md

    result = apply_md(
        content="# Hello",
        target_format="docx",
        reference_doc="some_path.docx",
        reference_doc_content="some-base64-data",
        output_path="test_output.docx",
    )
    data = json.loads(result)
    assert data["success"] is False
    assert any(
        err.get("code") == "MUTUALLY_EXCLUSIVE"
        for err in data.get("errors", [])
    )


def test_reference_doc_content_falls_back_to_text_on_bad_base64():
    """If reference_doc_content is not valid base64, fall back to writing
    the raw UTF-8 bytes to the temp file (rather than failing the call)."""
    from orf.mcp.tools.apply_md import apply_md
    from orf.mcp import server as srv
    import os

    captured = {}
    fallback_path = {}
    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        ref_idx = args.index("--reference-doc")
        fallback_path["path"] = args[ref_idx + 1]
        fallback_path["exists"] = os.path.exists(fallback_path["path"])
        with open(fallback_path["path"], "rb") as f:
            fallback_path["content"] = f.read()
        return {"success": True, "output_path": "test_output.docx"}

    orig = srv._run_cli_command
    srv._run_cli_command = fake_run
    try:
        # This string is not valid base64 — should fall back to UTF-8
        result = apply_md(
            content="# Hello",
            target_format="docx",
            reference_doc_content="not-valid-base64-!@#$%^&*()",
            output_path="test_output.docx",
        )
    finally:
        srv._run_cli_command = orig

    data = json.loads(result)
    assert data["success"] is True, f"unexpected result: {data}"
    assert fallback_path["exists"] is True
    # Should contain the raw bytes (since base64 failed, fell back to UTF-8)
    assert b"not-valid-base64" in fallback_path["content"]
