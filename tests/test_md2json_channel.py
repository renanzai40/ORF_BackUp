"""MD to JSON channel tests."""

from pathlib import Path

import pytest
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md_with_json(tmp_path: Path) -> Path:
    """MD file containing a JSON code block."""
    content = """# Sample Document

This is some text before the JSON block.

```json
{
  "name": "Test",
  "value": 42,
  "nested": {
    "key": "value"
  }
}
```

Some text after.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def sample_md_with_array(tmp_path: Path) -> Path:
    """MD file containing JSON with array."""
    content = """# Array Sample

```json
["item1", "item2", "item3"]
"""
    md_file = tmp_path / "array.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def sample_md_no_json(tmp_path: Path) -> Path:
    """MD file without JSON code block."""
    content = """# No JSON

This document has no JSON code block at all.
"""
    md_file = tmp_path / "nojson.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def sample_md_invalid_json(tmp_path: Path) -> Path:
    """MD file with invalid JSON in code block."""
    content = """# Invalid JSON

```json
{
  "broken": json is missing quotes
}
```
"""
    md_file = tmp_path / "invalid.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2JSONConverter:
    def test_supported_format(self):
        from orf.channels.md2json import MD2JSONConverter

        converter = MD2JSONConverter()
        assert converter.supported_format == "JSON"

    def test_validate_input_valid_md(self, sample_md_with_json: Path):
        from orf.channels.md2json import MD2JSONConverter

        converter = MD2JSONConverter()
        assert converter.validate_input(sample_md_with_json) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        from orf.channels.md2json import MD2JSONConverter

        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2JSONConverter()
        assert converter.validate_input(txt_file) is False

    def test_convert_preserves_structure(self, sample_md_with_json: Path, tmp_path: Path):
        """Nested objects and arrays are preserved in output."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_with_json, output)

        assert result.success is True
        assert result.output_path == output

        import json

        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        assert "nested" in data
        assert isinstance(data["nested"], dict)
        assert "key" in data["nested"]

    def test_convert_translates_values_only(self, sample_md_with_json: Path, tmp_path: Path):
        """Keys remain unchanged, only values are preserved."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_with_json, output)

        assert result.success is True

        import json

        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        # Keys should be preserved
        assert "name" in data
        assert "value" in data
        assert "nested" in data
        # Values should be present
        assert data["value"] == 42

    def test_convert_array_handling(self, sample_md_with_array: Path, tmp_path: Path):
        """Arrays are preserved with correct ordering."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_with_array, output)

        assert result.success is True

        import json

        with open(output, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == 3
        assert data[0] == "item1"
        assert data[1] == "item2"
        assert data[2] == "item3"

    def test_convert_invalid_json_md(self, sample_md_no_json: Path, tmp_path: Path):
        """Non-JSON MD produces an error."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_no_json, output)

        assert result.success is False
        assert len(result.errors) > 0

    def test_convert_invalid_json_syntax(self, sample_md_invalid_json: Path, tmp_path: Path):
        """MD with invalid JSON syntax produces an error."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_invalid_json, output)

        assert result.success is False
        assert len(result.errors) > 0

    def test_convert_success_result(self, sample_md_with_json: Path, tmp_path: Path):
        """Returns ConversionResult with success=True for valid input."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_with_json, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output

    def test_metadata_has_format_info(self, sample_md_with_json: Path, tmp_path: Path):
        """Metadata contains source format information."""
        from orf.channels.md2json import MD2JSONConverter

        output = tmp_path / "output.json"
        converter = MD2JSONConverter()
        result = converter.convert(sample_md_with_json, output)

        assert result.success is True
        assert result.metadata is not None
        assert "source_format" in result.metadata
        assert result.metadata["source_format"] == "MD"