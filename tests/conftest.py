"""Pytest configuration and shared fixtures for ORF tests."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_md_content() -> str:
    """Sample markdown content for testing."""
    return """# 用户手册

这是中文内容。

## 第一章

- 列表项 1
- 列表项 2

| 表格 | 列 |
|------|---|
| 数据 | 值 |
"""


@pytest.fixture
def sample_frontmatter_md_content() -> str:
    """Sample markdown with frontmatter for testing."""
    return """---
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


@pytest.fixture
def sample_manifest_data() -> dict:
    """Sample manifest.json data for testing."""
    return {
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
