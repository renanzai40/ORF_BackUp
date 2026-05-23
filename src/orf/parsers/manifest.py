"""OPP manifest.json 解析器

读取 OPP 输出的 manifest.json，提取源文件信息、输出路径、skeleton 路径等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from orf.logging import get_logger

logger = get_logger("parser.manifest")


@dataclass
class ManifestSource:
    """源文件信息"""
    file_path: str
    original_filename: str
    format: str  # DOCX, PPTX, PDF, etc.
    file_size_bytes: int
    file_hash_md5: str


@dataclass
class ManifestOutputs:
    """输出文件信息"""
    markdown: Optional[dict[str, Any]] = None  # {path, paragraph_count, table_count}
    xliff: Optional[dict[str, Any]] = None      # {path, trans_unit_count}


@dataclass
class ManifestSkeleton:
    """Skeleton 信息（用于 XLIFF→DOCX 回填）"""
    path: str
    format: str  # ZIP
    key_files: list[str]


@dataclass
class ManifestResources:
    """资源信息"""
    storage_dir: str
    image_count: int


@dataclass
class Manifest:
    version: str
    generated_at: str
    tool: str
    tool_version: str
    source: ManifestSource
    extraction: dict[str, Any]
    outputs: ManifestOutputs
    skeleton: Optional[ManifestSkeleton] = None
    images: Optional[list[dict[str, Any]]] = None
    resources: Optional[ManifestResources] = None


class ManifestParseError(Exception):
    """Manifest 解析错误"""
    pass


def parse_manifest(manifest_path: Path | str) -> Manifest:
    """解析 OPP manifest.json

    Args:
        manifest_path: manifest.json 文件路径

    Returns:
        Manifest 对象

    Raises:
        ManifestParseError: 解析失败
    """
    manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise ManifestParseError(f"Manifest file not found: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ManifestParseError(f"Invalid JSON in manifest: {e}")

    # 验证必要字段
    required_fields = ["manifest_version", "source", "extraction"]
    for field in required_fields:
        if field not in data:
            raise ManifestParseError(f"Missing required field: {field}")

    try:
        source = ManifestSource(
            file_path=data["source"]["file_path"],
            original_filename=data["source"]["original_filename"],
            format=data["source"]["format"],
            file_size_bytes=data["source"].get("file_size_bytes", 0),
            file_hash_md5=data["source"].get("file_hash_md5", ""),
        )

        outputs = ManifestOutputs(
            markdown=data["extraction"].get("outputs", {}).get("markdown"),
            xliff=data["extraction"].get("outputs", {}).get("xliff"),
        )

        skeleton = None
        if "skeleton" in data and data["skeleton"]:
            skeleton = ManifestSkeleton(
                path=data["skeleton"]["path"],
                format=data["skeleton"].get("format", "ZIP"),
                key_files=data["skeleton"].get("key_files", []),
            )

        resources = ManifestResources(
            storage_dir=data.get("resources", {}).get("storage_dir", "resources"),
            image_count=data.get("resources", {}).get("image_count", 0),
        )

        return Manifest(
            version=data.get("manifest_version", "unknown"),
            generated_at=data.get("generated_at", ""),
            tool=data.get("tool", ""),
            tool_version=data.get("tool_version", ""),
            source=source,
            extraction=data.get("extraction", {}),
            outputs=outputs,
            skeleton=skeleton,
            resources=resources,
            images=data.get("extraction", {}).get("images", []),
        )
    except KeyError as e:
        raise ManifestParseError(f"Missing field in manifest: {e}")


def find_manifest(md_path: Path | str) -> Optional[Path]:
    """根据 MD 文件路径查找对应的 manifest.json

    Args:
        md_path: MD 文件路径

    Returns:
        manifest.json 路径，如果不存在返回 None
    """
    md_path = Path(md_path)
    manifest_path = md_path.parent / f"{md_path.stem}_manifest.json"

    if manifest_path.exists():
        return manifest_path

    # fallback: 搜索同级目录
    for sibling in md_path.parent.glob("*_manifest.json"):
        return sibling

    return None