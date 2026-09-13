"""R-06 regression: ``orf apply-md`` writes must be atomic and idempotent.

Plan gap R-06 (``.omo/plans/agent-oriented-gap-register.md`` §4.2,
"Idempotency/retry-safety unvalidated"): a retried conversion rewrote its
output and sidecars in place with content that changed run to run. Two
concrete non-determinism sources were present in the shipped code:

* ``docProps/core.xml`` carried a ``dcterms:created``/``dcterms:modified``
  wall-clock timestamp injected by pandoc, so the DOCX bytes differed on
  every run.
* ``images.zip`` stored each member with the on-disk mtime as its ZIP
  timestamp, so the archive bytes differed on every run.

Neither write was atomic: pandoc wrote straight to the final path, so an
interrupted run could leave a truncated DOCX, and the sidecars were
written in place.

Contract locked here (per ``scenarios/STANDARDS.md`` framing — retrying a
successful conversion must converge, not drift):

* two runs of the same conversion produce a byte-identical output DOCX;
* the ``images.json`` + ``images.zip`` sidecars are byte-identical and
  are not duplicated;
* a failed conversion never replaces a previously-good output (atomic
  stage-then-rename);
* re-running with a different image set leaves no stale image files
  behind (idempotent sidecar handling).

The ``test_*`` assertions below are RED on the unfixed code and GREEN
once ``apply-md`` stages its writes through a temp sibling + ``os.replace``
and pandoc/sidecar writes are made deterministic.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from orf.cli import main
from orf.converters.base import ConversionResult, ErrorDetail

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="apply-md DOCX conversion requires the pandoc binary",
)

# Two distinct valid 1x1 PNGs (base64) used to exercise the image sidecar path.
_PNG_A = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_PNG_B = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9Q"
    "DwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_VALID_MD = (
    "---\nsource_lang: en\ntarget_lang: zh\n---\n\n"
    "# User Manual\n\nWelcome to the guide.\n\n## Section\n\nSome body text.\n"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_images_json(path: Path, images: list[dict[str, Any]]) -> Path:
    path.write_text(json.dumps({"images": images}), encoding="utf-8")
    return path


def _image_entry(b64: str, paragraph_index: int) -> dict[str, Any]:
    return {
        "data_base64": b64,
        "mime_type": "image/png",
        "paragraph_index": paragraph_index,
    }


def _invoke_apply_md(
    runner: CliRunner,
    md: Path,
    output: Path,
    images_json: Path | None = None,
) -> Any:
    args = [
        "apply-md",
        str(md),
        "--target-format",
        "docx",
        "-o",
        str(output),
        "--no-cache",
    ]
    if images_json is not None:
        args += ["--images-json", str(images_json)]
    return runner.invoke(main, args)


def _sidecars(output_dir: Path) -> dict[str, Path]:
    return {
        "images.json": output_dir / "images.json",
        "images.zip": output_dir / "images.zip",
    }


def _temp_leftovers(output_dir: Path) -> list[str]:
    """Hidden stage files a temp+rename write may leave behind on failure."""
    return [p.name for p in output_dir.iterdir() if p.name.startswith(".")]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_two_runs_produce_byte_identical_output_and_sidecars(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same conversion twice -> identical DOCX/work/zip hashes, no duplicates.

    RED before R-06: the DOCX and images.zip hashes differ between runs.
    """
    monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
    md = tmp_path / "doc.md"
    md.write_text(_VALID_MD, encoding="utf-8")
    images_json = _write_images_json(
        tmp_path / "opp_images.json",
        [_image_entry(_PNG_A, 0), _image_entry(_PNG_B, 1)],
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    output = out_dir / "result.docx"

    first = _invoke_apply_md(runner, md, output, images_json)
    assert first.exit_code == 0, first.output
    hashes_first = {"out.docx": _sha256(output)}
    hashes_first.update({n: _sha256(p) for n, p in _sidecars(out_dir).items()})

    # Re-run the identical conversion into the same output directory.
    second = _invoke_apply_md(runner, md, output, images_json)
    assert second.exit_code == 0, second.output
    hashes_second = {"out.docx": _sha256(output)}
    hashes_second.update({n: _sha256(p) for n, p in _sidecars(out_dir).items()})

    assert hashes_second == hashes_first, (
        "retrying apply-md must be idempotent; hashes drifted: "
        f"{hashes_first} != {hashes_second}"
    )


def test_no_duplicate_sidecars_after_retry(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exactly one images.json and one images.zip remain after two runs."""
    monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
    md = tmp_path / "doc.md"
    md.write_text(_VALID_MD, encoding="utf-8")
    images_json = _write_images_json(
        tmp_path / "opp_images.json", [_image_entry(_PNG_A, 0)]
    )
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    output = out_dir / "result.docx"

    for _ in range(2):
        result = _invoke_apply_md(runner, md, output, images_json)
        assert result.exit_code == 0, result.output

    assert sorted(p.name for p in out_dir.glob("images.json*")) == ["images.json"]
    assert sorted(p.name for p in out_dir.glob("images.zip*")) == ["images.zip"]
    assert _temp_leftovers(out_dir) == [], (
        f"atomic writes leaked stage files: {_temp_leftovers(out_dir)}"
    )


def test_failed_conversion_does_not_replace_existing_output(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing conversion must leave a previously-good output untouched.

    RED before R-06: the converter was handed the final output path and
    wrote a partial file there before failing.
    """
    monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
    md = tmp_path / "doc.md"
    md.write_text(_VALID_MD, encoding="utf-8")
    output = tmp_path / "result.docx"
    sentinel = b"SENTINEL-EXISTING-ARTIFACT"
    output.write_bytes(sentinel)

    def _partial_then_fail(
        self: Any, input_path: Any, output_path: Any, options: Any = None
    ) -> ConversionResult:
        # Simulate a converter that opens the output path and dies mid-write.
        Path(output_path).write_bytes(b"PARTIAL-WRITE")
        return ConversionResult(
            output_path=Path(output_path),
            success=False,
            errors=[ErrorDetail(code="CONVERSION_ERROR", message="synthetic failure")],
        )

    monkeypatch.setattr(
        "orf.channels.md2docx.MD2DOCXConverter.convert", _partial_then_fail
    )

    result = _invoke_apply_md(runner, md, output)
    assert result.exit_code != 0

    assert output.read_bytes() == sentinel, (
        "a failed conversion must not clobber the existing output"
    )
    assert _temp_leftovers(tmp_path) == [], (
        f"atomic staging leaked temp files: {_temp_leftovers(tmp_path)}"
    )


def test_rerun_with_different_images_leaves_no_stale_files(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry with a different image set must not leave stale image files."""
    monkeypatch.setenv("OMNI_CACHE_DIR", str(tmp_path / "cache"))
    md = tmp_path / "doc.md"
    md.write_text(_VALID_MD, encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    output = out_dir / "result.docx"
    images_dir = out_dir / "images"

    first_json = _write_images_json(
        tmp_path / "opp_images_a.json", [_image_entry(_PNG_A, 0)]
    )
    assert _invoke_apply_md(runner, md, output, first_json).exit_code == 0
    first_files = {p.name for p in images_dir.glob("OLIMG_*")}
    assert len(first_files) == 1

    second_json = _write_images_json(
        tmp_path / "opp_images_b.json", [_image_entry(_PNG_B, 0)]
    )
    assert _invoke_apply_md(runner, md, output, second_json).exit_code == 0
    second_files = {p.name for p in images_dir.glob("OLIMG_*")}

    assert first_files.isdisjoint(second_files), "different image bytes/hashes expected"
    assert len(second_files) == 1, (
        f"stale image files left after retry: {sorted(second_files)}"
    )
