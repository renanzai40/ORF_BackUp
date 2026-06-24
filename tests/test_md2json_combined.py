"""Combined mode tests: fenced ```json block + json_field: kv translations."""
import json
from pathlib import Path

import pytest

from orf.channels.md2json import MD2JSONConverter


def _make_md(fenced: str, kv_lines: list[str]) -> str:
    """Build MD content with a fenced block and json_field: kv lines."""
    parts = [fenced]
    for line in kv_lines:
        parts.append(f"json_field:{line}")
    return "\n\n".join(parts)


def _run_convert(md_text: str, tmp_path: Path):
    """Run converter on inline MD text, return parsed JSON result."""
    src = tmp_path / "input.md"
    dst = tmp_path / "output.json"
    src.write_text(md_text, encoding="utf-8")
    conv = MD2JSONConverter()
    result = conv.convert(src, dst)
    assert result.success, f"Conversion failed: {result.errors}"
    return json.loads(dst.read_text(encoding="utf-8"))


class TestMD2JSONCombined:
    def test_combined_simple_translation(self, tmp_path: Path):
        md = _make_md('```json\n{"name": "Alice"}\n```', ["name = Alice [TR]"])
        data = _run_convert(md, tmp_path)
        assert data["name"] == "Alice [TR]"

    def test_combined_preserves_numbers(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"count": 42, "price": 9.99}\n```',
            ["count = forty-two"],
        )
        data = _run_convert(md, tmp_path)
        assert data["count"] == 42
        assert data["price"] == 9.99

    def test_combined_preserves_booleans(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"active": true, "deleted": false}\n```',
            [],
        )
        data = _run_convert(md, tmp_path)
        assert data["active"] is True
        assert data["deleted"] is False

    def test_combined_preserves_nulls(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"name": "Alice", "spouse": null}\n```',
            ["name = Alice_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data["spouse"] is None
        assert data["name"] == "Alice_TR"

    def test_combined_nested_translation(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"user": {"profile": {"name": "Bob", "bio": "dev"}}}\n```',
            ["user.profile.name = Bob_TR", "user.profile.bio = dev_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data["user"]["profile"]["name"] == "Bob_TR"
        assert data["user"]["profile"]["bio"] == "dev_TR"

    def test_combined_array_translation(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"items": ["a", "b", "c"]}\n```',
            ["items.0 = a_TR", "items.1 = b_TR", "items.2 = c_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data["items"] == ["a_TR", "b_TR", "c_TR"]

    def test_combined_partial_translation(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"name": "Alice", "city": "Belgrade", "country": "SRB"}\n```',
            ["name = Alice_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data["name"] == "Alice_TR"
        assert data["city"] == "Belgrade"
        assert data["country"] == "SRB"

    def test_combined_unicode(self, tmp_path: Path):
        md = _make_md(
            '```json\n{"title": "中文标题", "desc": "日本語"}\n```',
            ["title = 中文_TR", "desc = 日本語_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data["title"] == "中文_TR"
        assert data["desc"] == "日本語_TR"

    def test_combined_no_kv_passes_through(self, tmp_path: Path):
        md = _make_md('```json\n{"name": "Alice", "score": 100}\n```', [])
        data = _run_convert(md, tmp_path)
        assert data["name"] == "Alice"
        assert data["score"] == 100

    def test_combined_requires_json_field_prefix(self, tmp_path: Path):
        old_style = '```json\n{"a": "old_val"}\n```\n\na = new_val'
        src = tmp_path / "input.md"
        dst = tmp_path / "output.json"
        src.write_text(old_style, encoding="utf-8")
        conv = MD2JSONConverter()
        result = conv.convert(src, dst)
        assert result.success
        data = json.loads(dst.read_text(encoding="utf-8"))
        assert data["a"] == "old_val"

    def test_combined_root_array(self, tmp_path: Path):
        md = _make_md(
            '```json\n["hello", "world"]\n```',
            ["0 = hello_TR", "1 = world_TR"],
        )
        data = _run_convert(md, tmp_path)
        assert data == ["hello_TR", "world_TR"]

    def test_combined_only_fence_no_kv(self, tmp_path: Path):
        src = tmp_path / "input.md"
        dst = tmp_path / "output.json"
        src.write_text("```json\n{\"key\": \"value\"}\n```", encoding="utf-8")
        conv = MD2JSONConverter()
        result = conv.convert(src, dst)
        assert result.success
        data = json.loads(dst.read_text(encoding="utf-8"))
        assert data["key"] == "value"

    def test_combined_neither_fence_nor_kv_errors(self, tmp_path: Path):
        src = tmp_path / "input.md"
        dst = tmp_path / "output.json"
        src.write_text("# Just a header\n\nNo JSON here.", encoding="utf-8")
        conv = MD2JSONConverter()
        result = conv.convert(src, dst)
        assert not result.success
        assert len(result.errors) > 0

