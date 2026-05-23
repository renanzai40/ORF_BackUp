"""OL YAML frontmatter parser for localized markdown files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from orf.logging import get_logger

logger = get_logger("parser.frontmatter")


@dataclass
class FrontmatterMetadata:
    source_lang: str
    target_lang: str
    original_file: str
    processor: str
    version: str
    translated_at: str


class FrontmatterParseError(Exception):
    pass


# 注意：OL 实际输出的 frontmatter 不使用 `...`，格式为:
# ---
# source_lang: en
# target_lang: zh
# original_file: spec.md
# processor: "OL"
# version: "0.1.0"
# translated_at: 2026-05-22T15:00:00Z
# ---
# (仅使用 --- 闭合，无 ...)

FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n',
    re.DOTALL | re.MULTILINE
)


def parse_frontmatter(md_path: Path | str) -> FrontmatterMetadata:
    """解析 MD 文件开头的 YAML frontmatter

    Args:
        md_path: MD 文件路径

    Returns:
        FrontmatterMetadata 对象

    Raises:
        FrontmatterParseError: 解析失败
    """
    md_path = Path(md_path)

    if not md_path.exists():
        raise FrontmatterParseError(f"MD file not found: {md_path}")

    try:
        content = md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise FrontmatterParseError(f"Cannot read file as UTF-8: {e}")

    # 查找 frontmatter 块
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        raise FrontmatterParseError(f"No YAML frontmatter found in {md_path}")

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        raise FrontmatterParseError(f"Invalid YAML in frontmatter: {e}")

    # 提取必要字段
    required_fields = ["source_lang", "target_lang", "original_file"]
    for field in required_fields:
        if field not in data:
            raise FrontmatterParseError(f"Missing required field in frontmatter: {field}")

    return FrontmatterMetadata(
        source_lang=data["source_lang"],
        target_lang=data["target_lang"],
        original_file=data["original_file"],
        processor=data.get("processor", "OL"),
        version=data.get("version", "unknown"),
        translated_at=data.get("translated_at", ""),
    )


def strip_frontmatter(content: str) -> str:
    """移除 content 中的 YAML frontmatter

    Args:
        content: MD 文件内容

    Returns:
        去除 frontmatter 后的内容
    """
    return FRONTMATTER_PATTERN.sub("", content)


def has_frontmatter(content: str) -> bool:
    """检查 content 是否包含 YAML frontmatter

    Args:
        content: MD 文件内容

    Returns:
        True if content has frontmatter
    """
    return bool(FRONTMATTER_PATTERN.match(content))


def find_md_with_frontmatter(directory: Path | str) -> list[Path]:
    """在目录中查找所有含 frontmatter 的 MD 文件

    Args:
        directory: 搜索目录

    Returns:
        MD 文件路径列表
    """
    directory = Path(directory)
    results = []

    for md_file in directory.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if has_frontmatter(content):
                results.append(md_file)
        except Exception:
            continue

    return results
