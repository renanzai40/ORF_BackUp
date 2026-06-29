"""ORF#13: Tests for xliff2json channel.

Verifies that XLIFF files can be converted to JSON output with
unit_id, source, and target fields preserved.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from pathlib import Path

# Import the function we're about to create (RED phase — will fail until GREEN)
from orf.channels.xliff2json import apply_xliff_to_json


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Create a sample XLIFF file for testing."""
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="1">
        <source>Hello World</source>
        <target>你好世界</target>
      </trans-unit>
      <trans-unit id="2">
        <source>Goodbye</source>
        <target>再见</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
    xliff_file = tmp_path / "test.xlf"
    xliff_file.write_text(xliff_content, encoding="utf-8")
    return xliff_file


@pytest.fixture
def empty_xliff(tmp_path: Path) -> Path:
    """Create an XLIFF file with no trans-units."""
    xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="en" target-language="zh-CN">
    <body></body>
  </file>
</xliff>"""
    xliff_file = tmp_path / "empty.xlf"
    xliff_file.write_text(xliff_content, encoding="utf-8")
    return xliff_file


class TestApplyXliffToJson:
    """Unit tests for apply_xliff_to_json."""

    def test_basic_conversion(self, sample_xliff: Path, tmp_path: Path):
        """Convert a 2-unit XLIFF to JSON and verify structure."""
        output = tmp_path / "output.json"
        result = apply_xliff_to_json(sample_xliff, output)

        assert result["success"] is True
        assert result["unit_count"] == 2
        assert output.exists()

        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["unit_count"] == 2
        assert len(data["xliff_units"]) == 2

    def test_unit_fields_preserved(self, sample_xliff: Path, tmp_path: Path):
        """Verify unit_id, source, target are correctly extracted."""
        output = tmp_path / "output.json"
        apply_xliff_to_json(sample_xliff, output)

        data = json.loads(output.read_text(encoding="utf-8"))
        unit1 = data["xliff_units"][0]
        assert unit1["unit_id"] == "1"
        assert unit1["source"] == "Hello World"
        assert unit1["target"] == "你好世界"

        unit2 = data["xliff_units"][1]
        assert unit2["unit_id"] == "2"
        assert unit2["source"] == "Goodbye"
        assert unit2["target"] == "再见"

    def test_empty_xliff(self, empty_xliff: Path, tmp_path: Path):
        """XLIFF with no trans-units produces empty list."""
        output = tmp_path / "output.json"
        result = apply_xliff_to_json(empty_xliff, output)

        assert result["success"] is True
        assert result["unit_count"] == 0

        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["unit_count"] == 0
        assert data["xliff_units"] == []

    def test_output_is_valid_json(self, sample_xliff: Path, tmp_path: Path):
        """Output file is valid JSON with proper encoding."""
        output = tmp_path / "output.json"
        apply_xliff_to_json(sample_xliff, output)

        raw = output.read_text(encoding="utf-8")
        data = json.loads(raw)  # Will raise if invalid
        assert "xliff_units" in data
        assert "unit_count" in data

    def test_unicode_preserved(self, tmp_path: Path):
        """CJK characters in source/target are preserved in JSON output."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.docx" source-language="zh" target-language="en">
    <body>
      <trans-unit id="42">
        <source>中文源文本</source>
        <target>Chinese source text</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "cjk.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")
        output = tmp_path / "output.json"

        apply_xliff_to_json(xliff_file, output)

        raw = output.read_text(encoding="utf-8")
        assert "中文源文本" in raw  # ensure_ascii=False
        data = json.loads(raw)
        assert data["xliff_units"][0]["source"] == "中文源文本"

    def test_returns_output_path_string(self, sample_xliff: Path, tmp_path: Path):
        """Return dict contains string path, not Path object."""
        output = tmp_path / "output.json"
        result = apply_xliff_to_json(sample_xliff, output)
        assert isinstance(result["output_path"], str)

    def test_json_indentation(self, sample_xliff: Path, tmp_path: Path):
        """Output JSON is pretty-printed with indent=2."""
        output = tmp_path / "output.json"
        apply_xliff_to_json(sample_xliff, output)

        raw = output.read_text(encoding="utf-8")
        # Pretty-printed: should contain newlines and spaces
        assert "\n" in raw
        assert "  " in raw

    def test_xliff_to_json_with_arrays(self, tmp_path: Path):
        """Handle OPP-style flat dot-notation keys (items.0, items.1) from JSON arrays."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="items.0">
        <source>first</source>
        <target>第一</target>
      </trans-unit>
      <trans-unit id="items.1">
        <source>second</source>
        <target>第二</target>
      </trans-unit>
      <trans-unit id="items.2">
        <source>third</source>
        <target>第三</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "array.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")
        output = tmp_path / "output.json"

        result = apply_xliff_to_json(xliff_file, output)
        assert result["success"] is True
        assert result["unit_count"] == 3

        data = json.loads(output.read_text(encoding="utf-8"))
        ids = {u["unit_id"] for u in data["xliff_units"]}
        assert "items.0" in ids
        assert "items.1" in ids
        assert "items.2" in ids

    def test_xliff_to_json_nested_keys(self, tmp_path: Path):
        """Handle OPP-style nested dot-notation keys (user.name, user.profile.bio)."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="user.name">
        <source>Alice</source>
        <target>爱丽丝</target>
      </trans-unit>
      <trans-unit id="user.profile.bio">
        <source>Developer</source>
        <target>开发者</target>
      </trans-unit>
      <trans-unit id="user.profile.location">
        <source>Beijing</source>
        <target>北京</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "nested.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")
        output = tmp_path / "output.json"

        result = apply_xliff_to_json(xliff_file, output)
        assert result["success"] is True
        assert result["unit_count"] == 3

        data = json.loads(output.read_text(encoding="utf-8"))
        ids = {u["unit_id"] for u in data["xliff_units"]}
        assert "user.name" in ids
        assert "user.profile.bio" in ids
        assert "user.profile.location" in ids

    # ── RED phase tests (will fail until original_json_path is implemented) ──

    def test_xliff_to_json_reconstructs_nested(self, tmp_path: Path):
        """Reconstruct nested JSON structure from dot-notation XLIFF trans-units."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="user.name">
        <source>Alice</source>
        <target>爱丽丝</target>
      </trans-unit>
      <trans-unit id="user.profile.bio">
        <source>Developer</source>
        <target>开发者</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "nested.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")

        original_json = {"user": {"name": "Alice", "profile": {"bio": "Developer"}}}
        json_path = tmp_path / "original.json"
        json_path.write_text(
            json.dumps(original_json, ensure_ascii=False), encoding="utf-8"
        )

        output = tmp_path / "output.json"
        result = apply_xliff_to_json(
            xliff_file, output, original_json_path=json_path
        )
        assert result["success"] is True

        data = json.loads(output.read_text(encoding="utf-8"))
        assert "reconstructed" in data
        assert data["reconstructed"]["user"]["name"] == "爱丽丝"
        assert data["reconstructed"]["user"]["profile"]["bio"] == "开发者"

    def test_xliff_to_json_reconstructs_arrays(self, tmp_path: Path):
        """Reconstruct JSON with array indexing from dot-notation XLIFF trans-units."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="items.0.title">
        <source>First Item</source>
        <target>第一项</target>
      </trans-unit>
      <trans-unit id="items.1.title">
        <source>Second Item</source>
        <target>第二项</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "array.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")

        original_json = {
            "items": [
                {"title": "First Item"},
                {"title": "Second Item"},
            ]
        }
        json_path = tmp_path / "original.json"
        json_path.write_text(
            json.dumps(original_json, ensure_ascii=False), encoding="utf-8"
        )

        output = tmp_path / "output.json"
        result = apply_xliff_to_json(
            xliff_file, output, original_json_path=json_path
        )
        assert result["success"] is True

        data = json.loads(output.read_text(encoding="utf-8"))
        assert "reconstructed" in data
        assert data["reconstructed"]["items"][0]["title"] == "第一项"
        assert data["reconstructed"]["items"][1]["title"] == "第二项"

    def test_xliff_to_json_reconstructs_deep_nesting(self, tmp_path: Path):
        """Reconstruct deeply nested JSON from dot-notation XLIFF trans-units."""
        xliff_content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="a.b.c.d.e">
        <source>deep_value</source>
        <target>深层值</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        xliff_file = tmp_path / "deep.xlf"
        xliff_file.write_text(xliff_content, encoding="utf-8")

        original_json = {"a": {"b": {"c": {"d": {"e": "deep_value"}}}}}
        json_path = tmp_path / "original.json"
        json_path.write_text(
            json.dumps(original_json, ensure_ascii=False), encoding="utf-8"
        )

        output = tmp_path / "output.json"
        result = apply_xliff_to_json(
            xliff_file, output, original_json_path=json_path
        )
        assert result["success"] is True

        data = json.loads(output.read_text(encoding="utf-8"))
        assert "reconstructed" in data
        assert data["reconstructed"]["a"]["b"]["c"]["d"]["e"] == "深层值"

    def test_xliff_to_json_without_original_returns_flat(self, sample_xliff: Path, tmp_path: Path):
        """Without original_json_path, output has no 'reconstructed' key (backward compat)."""
        output = tmp_path / "output.json"
        result = apply_xliff_to_json(sample_xliff, output)
        assert result["success"] is True

        data = json.loads(output.read_text(encoding="utf-8"))
        assert "reconstructed" not in data
        assert "xliff_units" in data
        assert "unit_count" in data


class TestApplyXliffJsonRouting:
    """Tests that apply-xliff CLI correctly routes to xliff2json."""

    def _run_cli(self, *args: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
        """Run ORF apply-xliff as a subprocess."""
        src_dir = Path(__file__).resolve().parents[1] / "src"
        cmd = [sys.executable, "-m", "orf", "apply-xliff", *args]
        env = {"PYTHONPATH": str(src_dir), "OMNI_TEST_FAKE_LLM": "1"}
        import os
        merged = {**os.environ, **env}
        return subprocess.run(
            cmd, capture_output=True, text=True, env=merged, timeout=30,
        )

    def test_json_format_routing_produces_output(self, tmp_path: Path):
        """--format json routes to xliff2json and produces valid JSON output."""
        xliff_file = tmp_path / "test.xlf"
        xliff_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="greeting">
        <source>Hello</source>
        <target>你好</target>
      </trans-unit>
      <trans-unit id="farewell">
        <source>Goodbye</source>
        <target>再见</target>
      </trans-unit>
    </body>
  </file>
</xliff>""")
        output = tmp_path / "result.json"

        # Input is the XLIFF itself (no skeleton needed for JSON format)
        result = self._run_cli(
            str(xliff_file), "--xliff", str(xliff_file),
            "--output", str(output), "--format", "json",
            tmp_path=tmp_path,
        )

        assert result.returncode == 0, (
            f"CLI failed: stdout={result.stdout}\nstderr={result.stderr}"
        )
        assert output.exists(), f"Output {output} not created"
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["unit_count"] == 2
        assert len(data["xliff_units"]) == 2

    def test_json_format_routing_preserves_units(self, tmp_path: Path):
        """Translated values are preserved through JSON format routing."""
        xliff_file = tmp_path / "test.xlf"
        xliff_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">
  <file original="test.json" source-language="en" target-language="zh-CN">
    <body>
      <trans-unit id="key1">
        <source>Hello World</source>
        <target>你好世界</target>
      </trans-unit>
      <trans-unit id="key2">
        <source>Translate me</source>
        <target>翻译我</target>
      </trans-unit>
    </body>
  </file>
</xliff>""")
        output = tmp_path / "result.json"

        result = self._run_cli(
            str(xliff_file), "--xliff", str(xliff_file),
            "--output", str(output), "--format", "json",
            tmp_path=tmp_path,
        )

        assert result.returncode == 0
        data = json.loads(output.read_text(encoding="utf-8"))
        units = {u["unit_id"]: u for u in data["xliff_units"]}
        assert units["key1"]["source"] == "Hello World"
        assert units["key1"]["target"] == "你好世界"
        assert units["key2"]["source"] == "Translate me"
        assert units["key2"]["target"] == "翻译我"

    def test_json_format_rejects_invalid_xliff(self, tmp_path: Path):
        """Invalid XLIFF produces error, not crash."""
        bad_xliff = tmp_path / "bad.xlf"
        bad_xliff.write_text("not xml", encoding="utf-8")
        output = tmp_path / "result.json"

        result = self._run_cli(
            str(bad_xliff), "--xliff", str(bad_xliff),
            "--output", str(output), "--format", "json",
            tmp_path=tmp_path,
        )

        assert result.returncode != 0, (
            f"Expected failure for invalid XLIFF; got stdout={result.stdout}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert any(w in combined for w in ("error", "fail", "invalid")), (
            f"Expected error message; got: {combined}"
        )
