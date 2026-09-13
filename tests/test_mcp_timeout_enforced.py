"""R-02 regression: configured MCP timeouts must actually be enforced.

Gap register R-02 (``.omo/plans/agent-oriented-gap-register.md``): the ORF MCP
CLI dispatcher ``orf.mcp.common.run_cli_command`` called ``subprocess.run``
with **no** ``timeout=``, so a hung/slow CLI subprocess blocked forever even
though ``ORF_MCP_TIMEOUT`` / ``MCP_TOOL_TIMEOUT`` were already loaded into
``MCPConfig.timeout_seconds``.

These tests are written red-first:

* ``test_hung_subprocess_yields_typed_timeout_within_bound`` — spawns a real
  ``python -c "time.sleep(...)"`` child through the dispatcher and asserts it
  returns a typed ``*_TIMEOUT`` error *within the configured bound* instead of
  hanging.
* ``test_partial_success_output_is_never_reported_as_success`` — adversarial
  "misleading success output": the child prints a valid success JSON line then
  hangs. The caller must still see the timeout, never the stale success.
* ``test_timeout_bound_is_read_fresh_from_config`` — adversarial "stale state":
  the bound must follow the *current* config on every call, not a value frozen
  at import.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure the sub-repo src is importable when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _allow_config(timeout_seconds: int):
    """Build a minimal MCPConfig for the dispatcher (allowlist is unrelated here)."""
    from orf.mcp.config import MCPConfig

    return MCPConfig(
        allowed_directories=[Path("/tmp")],
        timeout_seconds=timeout_seconds,
    )


def _patch_hanging_run(monkeypatch, child_code: str):
    """Replace ``subprocess.run`` with one that runs ``child_code`` instead of orf.cli.

    Returns a dict that records the ``timeout`` kwarg the dispatcher passed, so
    the test can prove the configured bound reached ``subprocess.run``.
    """
    import subprocess as _subprocess

    from orf.mcp import common

    real_run = _subprocess.run
    captured: dict[str, object] = {}

    def hanging_run(cmd, **kwargs):  # noqa: ANN001 - mirrors subprocess.run
        captured["timeout"] = kwargs.get("timeout")
        captured["cmd"] = cmd
        child = [sys.executable, "-c", child_code]
        return real_run(child, **kwargs)

    monkeypatch.setattr(common.subprocess, "run", hanging_run)
    return captured


def test_hung_subprocess_yields_typed_timeout_within_bound(monkeypatch):
    """Given a 1s configured bound, When the CLI hangs, Then a typed timeout fires fast."""
    from orf.mcp import common
    from orf.mcp._errors import CLI_TIMEOUT

    monkeypatch.setattr(common, "get_config", lambda: _allow_config(1))
    captured = _patch_hanging_run(monkeypatch, "import time; time.sleep(6)")

    start = time.monotonic()
    result = common.run_cli_command(["apply-md", "x.md", "--target-format", "docx"])
    elapsed = time.monotonic() - start

    # The bound reached the subprocess call, and the call actually returned.
    assert captured["timeout"] == 1, (
        "configured ORF_MCP_TIMEOUT was not passed to subprocess.run"
    )
    assert elapsed < 5, f"dispatcher hung past its 1s bound (took {elapsed:.1f}s)"

    # Typed *_TIMEOUT error with a retry hint, not a hang and not a crash.
    assert result["success"] is False
    assert result["errors"][0]["code"] == CLI_TIMEOUT
    assert result["errors"][0]["code"].endswith("_TIMEOUT")
    assert result["errors"][0]["recovery_strategy"] == "retry"


def test_partial_success_output_is_never_reported_as_success(monkeypatch):
    """A child that prints success JSON then hangs must still be reported as timeout.

    Adversarial: ``subprocess.run`` buffers output and raises ``TimeoutExpired``
    before returning, so the dispatcher must not parse that partial stdout.
    """
    from orf.mcp import common
    from orf.mcp._errors import CLI_TIMEOUT

    monkeypatch.setattr(common, "get_config", lambda: _allow_config(1))
    child = (
        "import json, sys, time;"
        "print(json.dumps({'success': True, 'output_path': '/tmp/fake.docx'}));"
        "sys.stdout.flush();"
        "time.sleep(6)"
    )
    _patch_hanging_run(monkeypatch, child)

    result = common.run_cli_command(["apply-md", "x.md", "--target-format", "docx"])

    assert result["success"] is False, "partial success output leaked as a real success"
    assert result["errors"][0]["code"] == CLI_TIMEOUT


def test_timeout_bound_is_read_fresh_from_config(monkeypatch):
    """The bound follows the current config on every call (no stale caching)."""
    from orf.mcp import common

    import subprocess as _subprocess

    real_run = _subprocess.run  # capture before patching the shared module attr
    seen: list[object] = []

    def spy_run(cmd, **kwargs):  # noqa: ANN001 - mirrors subprocess.run
        seen.append(kwargs.get("timeout"))
        return real_run(
            [sys.executable, "-c", "print('{}')"],
            **{k: v for k, v in kwargs.items() if k != "timeout"},
        )

    monkeypatch.setattr(common.subprocess, "run", spy_run)

    monkeypatch.setattr(common, "get_config", lambda: _allow_config(2))
    common.run_cli_command(["info", "x.md"])
    monkeypatch.setattr(common, "get_config", lambda: _allow_config(7))
    common.run_cli_command(["info", "x.md"])

    assert seen == [2, 7], f"timeout bound did not track config: {seen!r}"


def test_timeout_error_code_is_registered_with_a_safe_message():
    """The typed code is a real constant in the error map with a user-safe message."""
    from orf.mcp import _errors

    assert _errors.CLI_TIMEOUT == "CLI_TIMEOUT"
    assert _errors.SAFE_USER_MESSAGES[_errors.CLI_TIMEOUT].strip()
    assert _errors.get_safe_message(_errors.CLI_TIMEOUT) != _errors.get_safe_message(
        "NOT_A_REAL_CODE"
    )
