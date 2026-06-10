"""Test MD2DOCXConverter 'separate_images' option.

When separate_images=True, the converter:
- Extracts all images (data URIs and file paths) from MD to images_dir
- Writes an image_manifest.json describing the mapping
- Strips image references from MD (so pandoc produces a DOCX with no images)
- Returns stripped MD in a sibling location

The default behavior (without separate_images) keeps the existing
base64 preprocessing that lets Pandoc embed images.
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orf.channels.md2docx import MD2DOCXConverter
from orf.converters.options import ConverterOptions


PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


def _write_md_with_two_data_uris(tmp_path: Path) -> Path:
    """Write a markdown file with two base64 data URI images."""
    md_content = f"""# Test Document

Some text here.

![Test Image 1](data:image/png;base64,{PNG_B64})

More text after first image.

![Test Image 2](data:image/png;base64,{PNG_B64})

End of document.
"""
    md_path = tmp_path / "input.md"
    md_path.write_text(md_content, encoding="utf-8")
    return md_path


def _fake_pandoc_success(output_path: Path, cmd, **kwargs):
    """Create a minimal DOCX at output_path to simulate pandoc success."""
    with zipfile.ZipFile(output_path, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Test content</w:t></w:r></w:p></w:body>'
            '</w:document>',
        )
    result = MagicMock()
    result.returncode = 0
    result.stdout = ""
    result.stderr = ""
    return result


class TestMDSeparateImages:
    def test_separate_images_extracts_data_uris_to_dir(self, tmp_path: Path):
        """With separate_images=True, base64 data URI images are extracted to images_dir."""
        md_path = _write_md_with_two_data_uris(tmp_path)
        images_dir = tmp_path / "images"
        output_docx = tmp_path / "output.docx"

        with patch("subprocess.run", side_effect=lambda *a, **kw: _fake_pandoc_success(output_docx, *a, **kw)):
            converter = MD2DOCXConverter()
            result = converter.convert(
                input_path=md_path,
                output_path=output_docx,
                options=ConverterOptions(separate_images=True, images_dir=images_dir),
            )

        assert result.success
        assert output_docx.exists()
        assert images_dir.exists()
        assert (images_dir / "image_manifest.json").exists()

        image_files = sorted(images_dir.glob("image_*.png"))
        assert len(image_files) == 2, f"Expected 2 images, got {len(image_files)}"

        manifest = json.loads((images_dir / "image_manifest.json").read_text())
        assert manifest["total"] == 2
        assert len(manifest["images"]) == 2
        for entry in manifest["images"]:
            assert entry["alt"] in ("Test Image 1", "Test Image 2")
            assert entry["size_bytes"] > 0
            assert entry["original_ref"].startswith("data:image/png;base64,")

    def test_separate_images_strips_image_refs_from_md(self, tmp_path: Path):
        """The MD passed to pandoc has no image references (they're stripped)."""
        md_path = _write_md_with_two_data_uris(tmp_path)
        images_dir = tmp_path / "images"
        output_docx = tmp_path / "output.docx"

        captured_md = None
        def capture_pandoc(cmd, **kwargs):
            nonlocal captured_md
            captured_md = Path(cmd[1]).read_text(encoding="utf-8")
            return _fake_pandoc_success(output_docx, cmd, **kwargs)

        with patch("subprocess.run", side_effect=capture_pandoc):
            converter = MD2DOCXConverter()
            converter.convert(
                input_path=md_path,
                output_path=output_docx,
                options=ConverterOptions(separate_images=True, images_dir=images_dir),
            )

        assert captured_md is not None
        assert "data:image" not in captured_md
        assert "![Test Image" not in captured_md
        assert "Test Document" in captured_md
        assert "Some text here" in captured_md
        assert "More text after first image" in captured_md

    def test_separate_images_default_off_keeps_existing_behavior(self, tmp_path: Path):
        """Without separate_images, the existing base64-preprocessing path is taken."""
        md_path = _write_md_with_two_data_uris(tmp_path)
        output_docx = tmp_path / "output.docx"

        captured_md = None
        def capture_pandoc(cmd, **kwargs):
            nonlocal captured_md
            captured_md = Path(cmd[1]).read_text(encoding="utf-8")
            return _fake_pandoc_success(output_docx, cmd, **kwargs)

        with patch("subprocess.run", side_effect=capture_pandoc):
            converter = MD2DOCXConverter()
            converter.convert(
                input_path=md_path,
                output_path=output_docx,
            )

        assert captured_md is not None
        assert "data:image" not in captured_md
        assert (tmp_path / "images").exists() is False

    def test_separate_images_handles_missing_file_ref_gracefully(self, tmp_path: Path):
        """A non-existent file-path image ref is skipped with a warning (no crash)."""
        md_path = tmp_path / "input.md"
        md_path.write_text(f"""# Test

![Missing](nonexistent.png)

End.
""", encoding="utf-8")
        images_dir = tmp_path / "images"
        output_docx = tmp_path / "output.docx"

        with patch("subprocess.run", side_effect=lambda *a, **kw: _fake_pandoc_success(output_docx, *a, **kw)):
            converter = MD2DOCXConverter()
            result = converter.convert(
                input_path=md_path,
                output_path=output_docx,
                options=ConverterOptions(separate_images=True, images_dir=images_dir),
            )

        assert result.success
        assert images_dir.exists()
        assert not list(images_dir.glob("image_*.png"))
        manifest = json.loads((images_dir / "image_manifest.json").read_text())
        assert manifest["total"] == 0
