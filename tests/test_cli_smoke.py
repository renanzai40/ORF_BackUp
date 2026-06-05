"""ORF CLI smoke: invoke `apply-md` and `apply-xliff` end-to-end.

Spawns the ORF CLI as a real subprocess (not in-process CliRunner) so we
exercise the same code path users hit from the shell. The LLM and pandoc
seams are bypassed via env vars:

  - OMNI_TEST_FAKE_LLM=1     (in case any converter reaches an LLM adapter)
  - OMNI_TEST_FAKE_PANDOC=1  (mandatory — pandoc binary is not installed;
                              ORF's apply-md routes DOCX/EPUB/HTML/PDF
                              conversions through pandoc, and the fake
                              runner writes a minimal valid DOCX at the
                              output path so downstream checks pass)

Inputs are produced by running the OPP CLI first on a real DOCX fixture
(the same path users take):

  OPP --target-format=both <docx> -o <intermediate_dir>/
      -> <intermediate_dir>/<docx>.md
      -> <intermediate_dir>/<docx>.xlf
      -> <intermediate_dir>/<docx>_manifest.json
      -> <intermediate_dir>/<docx>.skeleton.zip

  orf apply-md    <intermediate_dir>/<docx>.md   --target-format docx  -o <out>.docx
  orf apply-xliff <docx> --xliff <intermediate_dir>/<docx>.xlf  -o <out>.docx

Run with:
    cd /mnt/d/贯维/Omni_Suite/Omni_Re_Formatter
    OMNI_TEST_FAKE_PANDOC=1 OMNI_TEST_FAKE_LLM=1 \
        pytest tests/test_cli_smoke.py -v --tb=short
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


VENV_PY = "/mnt/d/贯维/Omni_Suite/.venv_ol/bin/python"
ORF_DIR = Path("/mnt/d/贯维/Omni_Suite/Omni_Re_Formatter")
OPP_DIR = Path("/mnt/d/贯维/Omni_Suite/Omni_Pre_Processor")
REPO_ROOT = Path("/mnt/d/贯维/Omni_Suite")

HAIER_DOCX = REPO_ROOT / "爱上海尔_第二章_全球创牌 - E2E测试专用.docx"
MERIDIAN_DOCX = REPO_ROOT / "Meridian_Robotics_Product_Overview_E2E.docx"

_BASE_ENV = {
    **os.environ,
    "OMNI_TEST_FAKE_LLM": "1",
    "OMNI_TEST_FAKE_PANDOC": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONIOENCODING": "utf-8",
}


def run_orf(*args: str, timeout: int = 240) -> subprocess.CompletedProcess:
    """Invoke `python -m orf.cli ...` in ORF_DIR with the venv interpreter."""
    cmd = [VENV_PY, "-m", "orf.cli", *args]
    return subprocess.run(
        cmd,
        cwd=str(ORF_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_BASE_ENV,
    )


def run_opp_extract(docx: Path, out_dir: Path, target_format: str = "both") -> None:
    """Run OPP CLI to produce MD/XLIFF intermediates for `docx` in `out_dir`."""
    cmd = [
        VENV_PY, "-m", "opp.cli",
        str(docx),
        "--target-format", target_format,
        "--source-lang", "en", "--target-lang", "zh",
        "--output-dir", str(out_dir),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(OPP_DIR),
        capture_output=True,
        text=True,
        timeout=240,
        env=_BASE_ENV,
    )
    assert proc.returncode == 0, (
        f"OPP pre-extract failed: exit={proc.returncode}\n"
        f"stderr(last 1500)={proc.stderr[-1500:]}"
    )


@pytest.fixture(scope="module", autouse=True)
def _check_real_fixtures():
    for p in (HAIER_DOCX, MERIDIAN_DOCX):
        if not p.exists():
            pytest.skip(f"Real fixture missing: {p}")


@pytest.fixture(scope="module")
def opp_intermediates(tmp_path_factory) -> dict[str, Path]:
    """Run OPP once on a real DOCX; reuse the MD/XLIFF/skeleton/manifest."""
    out = tmp_path_factory.mktemp("orf_opp_intermediates")
    run_opp_extract(MERIDIAN_DOCX, out, target_format="both")
    stem = MERIDIAN_DOCX.stem
    md = out / f"{stem}.md"
    xlf = out / f"{stem}.xlf"
    skeleton = out / f"{stem}.skeleton.zip"
    manifest = out / f"{stem}_manifest.json"
    assert md.exists() and md.stat().st_size > 0
    assert xlf.exists() and xlf.stat().st_size > 0
    assert skeleton.exists() and skeleton.stat().st_size > 0
    assert manifest.exists() and manifest.stat().st_size > 0
    return {
        "md": md,
        "xlf": xlf,
        "skeleton": skeleton,
        "manifest": manifest,
        "dir": out,
        "stem": stem,
    }


# --- Tests ------------------------------------------------------------------


class TestCLIBasics:
    def test_help(self):
        proc = run_orf("--help")
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1000]}"
        assert "apply-md" in proc.stdout
        assert "apply-xliff" in proc.stdout
        assert "convert-batch" in proc.stdout
        assert "info" in proc.stdout

    def test_apply_md_help(self):
        proc = run_orf("apply-md", "--help")
        assert proc.returncode == 0
        assert "--target-format" in proc.stdout
        assert "--output" in proc.stdout

    def test_apply_xliff_help(self):
        proc = run_orf("apply-xliff", "--help")
        assert proc.returncode == 0
        assert "--xliff" in proc.stdout
        assert "--output" in proc.stdout
        assert "--format" in proc.stdout

    def test_info_on_real_docx(self):
        proc = run_orf("info", str(MERIDIAN_DOCX))
        assert proc.returncode == 0, f"stderr: {proc.stderr[:1000]}"
        # Format detection should report DOCX.
        assert "DOCX" in proc.stdout, f"stdout: {proc.stdout}"


class TestApplyMD:
    """`orf apply-md <input.md> --target-format <fmt> -o <out>` end-to-end.

    The fake-pandoc runner writes a minimal valid DOCX at the output
    path so all conversion-target formats succeed in this hermetic
    environment. The output is therefore always a real DOCX zip, even
    when the target format is epub/html (pandoc would normally do the
    actual transformation; the fake runner short-circuits to a DOCX).
    """

    def test_apply_md_to_docx(self, opp_intermediates, tmp_path):
        out = tmp_path / "result.docx"
        proc = run_orf(
            "apply-md", str(opp_intermediates["md"]),
            "--target-format", "docx",
            "-o", str(out),
        )
        assert proc.returncode == 0, (
            f"exit={proc.returncode}\nstdout={proc.stdout[-1000:]}\n"
            f"stderr={proc.stderr[-1500:]}"
        )
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0, "output is empty"
        # Fake pandoc always writes a real DOCX; validate ZIP magic.
        with open(out, "rb") as f:
            magic = f.read(4)
        assert magic[:2] == b"PK", f"not a ZIP/DOCX: magic={magic!r}"

    def test_apply_md_to_html(self, opp_intermediates, tmp_path):
        out = tmp_path / "result.html"
        proc = run_orf(
            "apply-md", str(opp_intermediates["md"]),
            "--target-format", "html",
            "-o", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0

    def test_apply_md_to_epub(self, opp_intermediates, tmp_path):
        out = tmp_path / "result.epub"
        proc = run_orf(
            "apply-md", str(opp_intermediates["md"]),
            "--target-format", "epub",
            "-o", str(out),
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0

    def test_apply_md_json_output(self, opp_intermediates, tmp_path):
        out = tmp_path / "result_json.docx"
        proc = run_orf(
            "apply-md", str(opp_intermediates["md"]),
            "--target-format", "docx",
            "-o", str(out),
            "--json",
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        # ORF emits pretty-printed JSON on a single block; recover the
        # outermost `{ ... }` substring and parse it.
        import json as _json
        start = proc.stdout.find("{")
        end = proc.stdout.rfind("}")
        assert start != -1 and end != -1 and end > start, (
            f"no JSON braces in stdout:\n{proc.stdout[:1000]}"
        )
        obj = _json.loads(proc.stdout[start:end + 1])
        assert obj.get("success") is True, f"json: {obj}"
        assert obj.get("output_path"), f"missing output_path: {obj}"


class TestApplyXLIFF:
    """`orf apply-xliff <original.docx> --xliff <trans.xlf> -o <out>`.

    ORF's XLIFF backfill is native (not pandoc), so it actually replaces
    text inside the original DOCX skeleton and re-zips it. Even with the
    fake-pandoc seam, the XLIFF→DOCX converter exercises real ORF code.
    """

    def test_apply_xliff_to_docx(self, opp_intermediates, tmp_path):
        out = tmp_path / "backfilled.docx"
        proc = run_orf(
            "apply-xliff", str(MERIDIAN_DOCX),
            "--xliff", str(opp_intermediates["xlf"]),
            "-o", str(out),
            "--format", "docx",
        )
        assert proc.returncode == 0, (
            f"exit={proc.returncode}\nstdout={proc.stdout[-1000:]}\n"
            f"stderr={proc.stderr[-1500:]}"
        )
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0, "output is empty"
        # DOCX output is a real ZIP — verify magic.
        with open(out, "rb") as f:
            magic = f.read(4)
        assert magic[:2] == b"PK", f"not a ZIP/DOCX: magic={magic!r}"
        # Should still contain a word/document.xml inside the ZIP.
        import zipfile
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        assert "word/document.xml" in names, f"missing document.xml in {names}"

    def test_apply_xliff_to_html(self, opp_intermediates, tmp_path):
        """XLIFF→HTML backfill needs an HTML source file (not DOCX).

        ORF's XLIFF→HTML converter reads `input_file` as an HTML template
        and substitutes translations from the XLIFF. Passing a DOCX fails
        with a UTF-8 decode error. So we build a minimal HTML input
        alongside a minimal XLIFF (with matching trans-units) and run the
        real backfill against that.
        """
        # Minimal HTML input the converter can read as a template.
        html_in = tmp_path / "input.html"
        html_in.write_text(
            "<!DOCTYPE html>\n<html><head><title>T</title></head>\n"
            "<body><h1>Hello World</h1>\n"
            "<p>First paragraph about Omni Suite.</p>\n"
            "<p>Second paragraph with details.</p>\n"
            "</body></html>\n",
            encoding="utf-8",
        )
        # Minimal XLIFF whose <source> fragments align with the HTML body.
        xlf_in = tmp_path / "input.xlf"
        xlf_in.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
            '  <file source-language="en" target-language="zh" original="input" datatype="plaintext">\n'
            '    <body>\n'
            '      <trans-unit id="tu1"><source>Hello World</source><target>[ZH]</target></trans-unit>\n'
            '      <trans-unit id="tu2"><source>First paragraph about Omni Suite.</source><target>[ZH]</target></trans-unit>\n'
            '      <trans-unit id="tu3"><source>Second paragraph with details.</source><target>[ZH]</target></trans-unit>\n'
            '    </body>\n'
            '  </file>\n'
            '</xliff>\n',
            encoding="utf-8",
        )
        out = tmp_path / "backfilled.html"
        proc = run_orf(
            "apply-xliff", str(html_in),
            "--xliff", str(xlf_in),
            "-o", str(out),
            "--format", "html",
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0
        body = out.read_text(encoding="utf-8")
        # Translation target token [ZH] should appear in the backfilled HTML.
        assert "[ZH]" in body, f"translation not applied:\n{body[:500]}"

    def test_apply_xliff_to_epub(self, opp_intermediates, tmp_path):
        out = tmp_path / "backfilled.epub"
        proc = run_orf(
            "apply-xliff", str(MERIDIAN_DOCX),
            "--xliff", str(opp_intermediates["xlf"]),
            "-o", str(out),
            "--format", "epub",
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        assert out.exists(), f"output {out} not created"
        assert out.stat().st_size > 0

    def test_apply_xliff_missing_xliff(self, tmp_path):
        """`--xliff` is required; CLI must reject when absent."""
        out = tmp_path / "should_not_exist.docx"
        proc = run_orf(
            "apply-xliff", str(MERIDIAN_DOCX),
            "-o", str(out),
            "--format", "docx",
            # --xliff deliberately omitted
        )
        assert proc.returncode != 0, "ORF should refuse apply-xliff without --xliff"
        assert "xliff" in proc.stderr.lower() or "missing" in proc.stderr.lower()


class TestConvertBatch:
    """`orf convert-batch <dir> --target-format <fmt>` batch path.

    ORF's convert-batch only picks up MD files that carry YAML
    frontmatter (`has_frontmatter()` is the gate). OPP's raw MD output
    has no frontmatter, so we wrap the OPP-extracted MD with a synthetic
    OL-style frontmatter block before handing it to the batch command.
    """

    def test_convert_batch_dir(self, opp_intermediates, tmp_path):
        # Prepare a batch input dir with a frontmatter-bearing MD.
        batch_in = tmp_path / "batch_in"
        batch_in.mkdir()
        md_body = opp_intermediates["md"].read_text(encoding="utf-8")
        wrapped = (
            "---\n"
            "source_lang: en\n"
            "target_lang: zh\n"
            "original_file: Meridian_Robotics_Product_Overview_E2E.md\n"
            "processor: \"OL\"\n"
            "version: \"0.2.6\"\n"
            "translated_at: 2026-06-04T20:00:00Z\n"
            "---\n\n"
            f"{md_body}"
        )
        (batch_in / "Meridian_Robotics_Product_Overview_E2E.md").write_text(
            wrapped, encoding="utf-8",
        )

        batch_out = tmp_path / "batch_out"
        proc = run_orf(
            "convert-batch", str(batch_in),
            "--target-format", "docx",
            "-o", str(batch_out),
            "-p", "*.md",
        )
        assert proc.returncode == 0, f"stderr: {proc.stderr[-1500:]}"
        # At least one .docx produced.
        produced = list(batch_out.rglob("*.docx"))
        assert produced, (
            f"no .docx in {batch_out} (found: {list(batch_out.rglob('*'))})"
        )
