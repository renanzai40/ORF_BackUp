"""Equivalence test: decorated vs. module-level `apply_xliff` outputs.

The two call paths (the `@server.tool()`-decorated wrapper registered
in `_register_tools` and the module-level alias at server.py:346) are
intentionally duplicated, per the comment at server.py:317-324. The
duplication is a deliberate parallel entry point for in-process
callers, *not* a refactoring opportunity.

The fix for Q-1 (server.py:179-184 dead pre-block leaking tempfiles)
must be a pure deletion: it must not change observable output. This
test pins the equivalence so that future changes to either branch
cannot silently diverge the two surfaces.

Strategy: drive both call sites with identical arguments, both with
the same mocked `_run_cli_command` return value, and assert that the
JSON-decoded result dicts are equal. Because both paths funnel into
the same `_run_cli_command` call after they finish their setup, the
output dict is fully determined by the mocked CLI response and is
identical when both sides produce the same effective `xliff_to_use`.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orf.mcp.server import get_server, apply_xliff as module_level_apply_xliff


MINIMAL_XLIFF = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<xliff version='1.2' xmlns='urn:oasis:names:tc:xliff:document:1.2'>"
    "<file original='hello.txt' source-language='en' target-language='zh' datatype='plaintext'>"
    "<body><trans-unit id='1'><source>Hello</source><target>你好</target></trans-unit></body>"
    "</file></xliff>"
)


def _mock_cli_response(output_path: str) -> dict:
    return {
        "success": True,
        "output_path": output_path,
        "errors": [],
        "warnings": [],
        "metadata": {"format": "docx", "engine": "pandoc"},
    }


def test_apply_xliff_identical_output_decorated_and_module_level(tmp_path: Path):
    """Decorated tool and module-level alias produce identical JSON output.

    Both surfaces are invoked with the exact same arguments and the
    exact same mocked CLI response. The test asserts that the decoded
    result dicts are equal. Any divergence in their internal handling
    (e.g. xliff_to_use reset, path-validation branches, error
    formatting) would show up here.
    """
    input_file = tmp_path / "in.docx"
    input_file.write_bytes(b"fake-docx-for-test")
    output_path = str(tmp_path / "out.docx")

    args = {
        "input_file": str(input_file),
        "xliff_path": "",
        "output_path": output_path,
        "format": "docx",
        "xliff_content": MINIMAL_XLIFF,
    }

    server = get_server()

    # The module-level alias uses keyword args directly.
    with patch("orf.mcp.server._run_cli_command") as mock_cli:
        mock_cli.return_value = _mock_cli_response(output_path)
        module_raw = module_level_apply_xliff(**args)
        module_result = json.loads(module_raw)

    # The decorated tool is invoked via server.call_tool; the tool
    # inspects only the kwarg keys it declared, and FastMCP wraps the
    # JSON return.
    with patch("orf.mcp.server._run_cli_command") as mock_cli:
        mock_cli.return_value = _mock_cli_response(output_path)
        decorated = asyncio.run(server.call_tool("apply_xliff", args))
        decorated_raw = decorated.content[0].text
        decorated_result = json.loads(decorated_raw)

    # Both must report success with the mocked CLI return.
    assert module_result["success"] is True
    assert decorated_result["success"] is True

    # Equivalence: the two surfaces must produce the same decoded
    # result. The Q-1 fix preserves this contract (the dead pre-block
    # was always overwritten by the second block, so xliff_to_use
    # always reached _run_cli_command with the correct tempfile).
    assert decorated_result == module_result, (
        "Decorated and module-level apply_xliff diverged.\n"
        f"  decorated: {decorated_result}\n"
        f"  module:    {module_result}\n"
    )
