"""Frontmatter parser tests."""

import pytest
from pathlib import Path
from orf.parsers.frontmatter import (
    parse_frontmatter,
    FrontmatterParseError,
    strip_frontmatter,
    has_frontmatter,
    find_md_with_frontmatter,
    FrontmatterMetadata,
)


@pytest.fixture
def md_with_frontmatter(tmp_path: Path) -> Path:
    content = """---
source_lang: en
target_lang: zh
original_file: spec.md
processor: "OL"
version: "0.1.0"
translated_at: 2026-05-22T15:00:00Z
---

# 用户手册

这是翻译后的内容。
"""

    md_file = tmp_path / "spec_zh.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def md_without_frontmatter(tmp_path: Path) -> Path:
    content = """# 用户手册

这是普通内容，没有 frontmatter。
"""

    md_file = tmp_path / "plain.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


def test_parse_frontmatter_success(md_with_frontmatter: Path):
    metadata = parse_frontmatter(md_with_frontmatter)

    assert isinstance(metadata, FrontmatterMetadata)
    assert metadata.source_lang == "en"
    assert metadata.target_lang == "zh"
    assert metadata.original_file == "spec.md"
    assert metadata.processor == "OL"
    assert metadata.version == "0.1.0"


def test_parse_frontmatter_missing_file():
    with pytest.raises(FrontmatterParseError, match="MD file not found"):
        parse_frontmatter("/nonexistent/file.md")


def test_parse_frontmatter_no_frontmatter(md_without_frontmatter: Path):
    with pytest.raises(FrontmatterParseError, match="No YAML frontmatter found"):
        parse_frontmatter(md_without_frontmatter)


def test_strip_frontmatter(md_with_frontmatter: Path):
    content = md_with_frontmatter.read_text()
    stripped = strip_frontmatter(content)

    assert not stripped.startswith("---")
    assert stripped.startswith("# 用户手册")
    assert "translated_at" not in stripped


def test_has_frontmatter():
    with_fm = """---
key: value
processor: "OL"

# Content
"""
    without_fm = """# Content
"""

    assert has_frontmatter(with_fm) is True
    assert has_frontmatter(without_fm) is False


def test_find_md_with_frontmatter(tmp_path: Path):
    (tmp_path / "spec1_zh.md").write_text("---\nkey: value\nprocessor: \"OL\"\n---\n# Title\n", encoding="utf-8")
    (tmp_path / "spec2_zh.md").write_text("---\nkey: value\nprocessor: \"OL\"\n---\n# Title\n", encoding="utf-8")
    (tmp_path / "plain.md").write_text("# Plain\n", encoding="utf-8")

    found = find_md_with_frontmatter(tmp_path)
    assert len(found) == 2