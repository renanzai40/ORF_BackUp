"""Manifest parser tests."""

import json
import pytest
from pathlib import Path
from orf.parsers.manifest import (
    parse_manifest,
    ManifestParseError,
    find_manifest,
    Manifest,
)


@pytest.fixture
def sample_manifest(tmp_path: Path) -> Path:
    manifest_data = {
        "manifest_version": "1.0",
        "generated_at": "2026-05-22T14:30:00Z",
        "tool": "OPP",
        "tool_version": "0.2.0",
        "source": {
            "file_path": "/path/to/spec.docx",
            "original_filename": "spec.docx",
            "format": "DOCX",
            "file_size_bytes": 45824,
            "file_hash_md5": "a1b2c3d4e5f6",
        },
        "extraction": {
            "source_lang": "en",
            "target_lang": "zh",
            "outputs": {
                "markdown": {
                    "path": "spec.md",
                    "paragraph_count": 150,
                    "table_count": 3,
                },
                "xliff": {
                    "path": "spec.xlf",
                    "trans_unit_count": 42,
                },
            },
            "images": [
                {"mime_type": "image/png", "width": 800, "height": 600, "data_size_bytes": 24580}
            ],
            "warnings": [],
        },
        "skeleton": {
            "path": "spec.skeleton.zip",
            "format": "ZIP",
            "key_files": ["word/document.xml", "word/styles.xml"],
        },
        "resources": {
            "storage_dir": "resources",
            "image_count": 5,
        },
    }

    manifest_path = tmp_path / "spec_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    return manifest_path


def test_parse_manifest_success(sample_manifest: Path):
    manifest = parse_manifest(sample_manifest)

    assert isinstance(manifest, Manifest)
    assert manifest.version == "1.0"
    assert manifest.source.format == "DOCX"
    assert manifest.source.original_filename == "spec.docx"
    assert manifest.skeleton is not None
    assert manifest.skeleton.path == "spec.skeleton.zip"
    assert manifest.outputs.markdown is not None
    assert manifest.outputs.markdown["path"] == "spec.md"
    assert manifest.outputs.xliff is not None
    assert manifest.outputs.xliff["trans_unit_count"] == 42


def test_parse_manifest_missing_file():
    with pytest.raises(ManifestParseError, match="Manifest file not found"):
        parse_manifest("/nonexistent/manifest.json")


def test_parse_manifest_invalid_json(tmp_path: Path):
    invalid_manifest = tmp_path / "invalid.json"
    invalid_manifest.write_text("{ not json }")

    with pytest.raises(ManifestParseError, match="Invalid JSON"):
        parse_manifest(invalid_manifest)


def test_parse_manifest_missing_fields(tmp_path: Path):
    incomplete_manifest = tmp_path / "incomplete.json"
    incomplete_manifest.write_text('{"manifest_version": "1.0"}')

    with pytest.raises(ManifestParseError, match="Missing required field"):
        parse_manifest(incomplete_manifest)


def test_find_manifest_by_md_path(tmp_path: Path):
    md_file = tmp_path / "spec.md"
    md_file.touch()

    manifest_data = {"manifest_version": "1.0", "source": {}, "extraction": {}}
    manifest_file = tmp_path / "spec_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)

    found = find_manifest(md_file)
    assert found == manifest_file


def test_find_manifest_not_found(tmp_path: Path):
    md_file = tmp_path / "orphan.md"
    md_file.touch()

    found = find_manifest(md_file)
    assert found is None