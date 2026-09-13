"""R-04 regression: explicit partial-success contract for ``orf convert-batch``.

Plan gap R-04 (``.omo/plans/agent-oriented-gap-register.md`` §4.2,
"Partial-success semantics unused/dishonest"): ``convert_batch.py:198-254``
counted failures but its JSON summary carried no overall ``status``, so an
agent could not tell a fully-successful batch from a partially-failed one
except by counting keys itself, and there was no ``--allow-partial`` escape
hatch to accept a partially-succeeded batch as a non-error.

Contract locked here (per plan R-04 Decision + ``scenarios/STANDARDS.md``):

* The ``--json`` summary always carries an overall ``status``:
  ``empty`` (no files matched, exit 0) · ``complete`` (all succeeded) ·
  ``partial`` (some succeeded, some failed) · ``failed`` (all failed).
* ``succeeded`` / ``failed`` / ``retryable`` report the counts;
  ``retryable`` = number of failed items a retry could plausibly clear
  (every batch failure is an operational conversion failure, so today it
  equals ``failed``; a future permanent-failure classifier may split them).
* Exit code (``#exit-codes``): ``complete``/``empty`` → 0; ``partial`` →
  non-zero unless ``--allow-partial``; ``failed`` → ALWAYS non-zero —
  ``--allow-partial`` must NOT mask a total failure (no misleading success
  output: exit code and counts must never disagree).
* ``success_count`` / ``fail_count`` / ``total`` are kept for backward
  compatibility with the T-03 schema.

``test_*_status_and_exit`` are the failing-first assertions: RED on the
unfixed code (no ``status`` key, no ``--allow-partial`` flag), GREEN once
R-04 lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from orf.cli import main
from orf.commands import convert_batch as convert_batch_module


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _parse_single_json(stdout: str) -> dict[str, Any]:
    """``json.loads`` the WHOLE stdout — rejects any banner/trailer."""
    parsed = json.loads(stdout)
    assert isinstance(parsed, dict), f"stdout JSON is not an object: {type(parsed)}"
    return parsed


def _write_frontmatter_md(directory: Path, name: str) -> Path:
    """convert-batch only picks up MD files carrying YAML frontmatter."""
    md = directory / name
    md.write_text(
        "---\nsource_lang: en\ntarget_lang: zh\n---\n\n# Hello\n",
        encoding="utf-8",
    )
    return md


def _make_src(tmp_path: Path, count: int) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(count):
        _write_frontmatter_md(src, f"doc{i}.md")
    return src


def _batch(
    runner: CliRunner,
    src: Path,
    out: Path,
    *extra: str,
) -> Any:
    return runner.invoke(
        main,
        [
            "convert-batch",
            str(src),
            "--target-format",
            "html",
            "--output-dir",
            str(out),
            "--json",
            *extra,
        ],
    )


def _fake_convert_single(failing_names: set[str], raising_names: set[str] | None = None):
    """Deterministic per-file converter: succeed unless the name is failing."""

    def fake(
        md_file: Path,
        converter_class: type,
        output_path: Path,
        target_format: str,
    ) -> tuple[bool, str | None]:
        if raising_names and md_file.name in raising_names:
            raise ValueError(f"malformed input for {md_file.name}")
        if md_file.name in failing_names:
            return False, f"synthetic conversion failure for {md_file.name}"
        return True, None

    return fake


# ---------------------------------------------------------------------------
# 2-of-3 valid → partial
# ---------------------------------------------------------------------------


def test_convert_batch_partial_2_of_3_status_and_nonzero_exit(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2/3 succeed, 1 fails → ``status: partial`` + non-zero exit.

    RED on the unfixed code: no ``status`` key, and ``--allow-partial`` is
    not a valid flag.
    """
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names={"doc2.md"}),
    )

    result = _batch(runner, src, out)

    assert result.exit_code != 0, (
        "partial batch without --allow-partial must exit non-zero "
        f"(got {result.exit_code}); stdout={result.stdout!r}"
    )
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "partial"
    assert obj["succeeded"] == 2
    assert obj["failed"] == 1
    assert obj["retryable"] == 1
    assert obj["total"] == 3
    # T-03 backward-compat keys survive.
    assert obj["success_count"] == 2
    assert obj["fail_count"] == 1


def test_convert_batch_partial_2_of_3_allow_partial_exit_zero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same 2/3 partial batch with ``--allow-partial`` → exit 0.

    The escape hatch accepts partial success as a non-error while the JSON
    still reports ``status: partial`` with honest counts.
    """
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names={"doc2.md"}),
    )

    result = _batch(runner, src, out, "--allow-partial")

    assert result.exit_code == 0, f"stderr: {result.stderr[-800:]}"
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "partial"
    assert obj["succeeded"] == 2
    assert obj["failed"] == 1


# ---------------------------------------------------------------------------
# 0-of-3 valid → failed (--allow-partial must NOT mask it)
# ---------------------------------------------------------------------------


def test_convert_batch_failed_0_of_3_status_and_nonzero_exit(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """0/3 succeed → ``status: failed`` + non-zero exit."""
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names={"doc0.md", "doc1.md", "doc2.md"}),
    )

    result = _batch(runner, src, out)

    assert result.exit_code != 0, (
        "a fully-failed batch must exit non-zero "
        f"(got {result.exit_code}); stdout={result.stdout!r}"
    )
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "failed"
    assert obj["succeeded"] == 0
    assert obj["failed"] == 3
    assert obj["retryable"] == 3


def test_convert_batch_failed_0_of_3_allow_partial_still_nonzero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADVERSARIAL: ``--allow-partial`` on a 0/3 batch must STILL exit non-zero.

    ``--allow-partial`` only downgrades a *partial* batch (some succeeded).
    A total failure is not partial — masking it with exit 0 would be
    misleading success output (exit code says OK, counts say everything
    failed).
    """
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names={"doc0.md", "doc1.md", "doc2.md"}),
    )

    result = _batch(runner, src, out, "--allow-partial")

    assert result.exit_code != 0, (
        "--allow-partial must not mask a total failure "
        f"(got {result.exit_code}); stdout={result.stdout!r}"
    )
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "failed"
    assert obj["succeeded"] == 0
    assert obj["failed"] == 3


# ---------------------------------------------------------------------------
# All-valid → complete; empty dir → empty
# ---------------------------------------------------------------------------


def test_convert_batch_complete_all_succeed_exit_zero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3/3 succeed → ``status: complete`` + exit 0."""
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names=set()),
    )

    result = _batch(runner, src, out)

    assert result.exit_code == 0, f"stderr: {result.stderr[-800:]}"
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "complete"
    assert obj["succeeded"] == 3
    assert obj["failed"] == 0
    assert obj["retryable"] == 0


def test_convert_batch_empty_dir_status_empty_exit_zero(
    runner: CliRunner, tmp_path: Path
) -> None:
    """No frontmatter files matched → ``status: empty`` + exit 0."""
    src = tmp_path / "empty_src"
    src.mkdir()
    out = tmp_path / "out"
    out.mkdir()

    result = _batch(runner, src, out)

    assert result.exit_code == 0, f"stderr: {result.stderr[-800:]}"
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "empty"
    assert obj["succeeded"] == 0
    assert obj["failed"] == 0
    assert obj["retryable"] == 0
    assert obj["total"] == 0


# ---------------------------------------------------------------------------
# Malformed input — a converter exception is a counted failure, not a crash
# ---------------------------------------------------------------------------


def test_convert_batch_malformed_input_counts_as_failed(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADVERSARIAL: a file that makes the converter raise is counted as
    ``failed`` (not a crash), producing ``status: partial`` with honest
    counts and a non-zero exit.
    """
    src = _make_src(tmp_path, 3)
    out = tmp_path / "out"
    out.mkdir()

    monkeypatch.setattr(
        convert_batch_module, "_convert_single",
        _fake_convert_single(failing_names=set(), raising_names={"doc1.md"}),
    )

    result = _batch(runner, src, out)

    assert result.exit_code != 0, (
        "a batch with a raised conversion failure must exit non-zero "
        f"(got {result.exit_code}); stdout={result.stdout!r}"
    )
    obj = _parse_single_json(result.stdout)
    assert obj["status"] == "partial"
    assert obj["succeeded"] == 2
    assert obj["failed"] == 1
    assert obj["retryable"] == 1
