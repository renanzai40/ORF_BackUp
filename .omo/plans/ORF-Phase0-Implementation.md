# ORF Phase 0 实现计划：项目骨架与 MD 回写基础

**版本**: v1.1 (审查修正版)
**Phase**: Phase 0
**目标**: 搭建 ORF 项目仓库结构，实现 MD→DOCX/ODT/EPUB 三种回写通道，构建 manifest/frontmatter 解析与资源路径映射胶水代码

---

## 1. 项目初始化

### 1.1 创建项目骨架

**注意**：测试目录使用扁平结构，匹配 OPP/OL 惯例（不使用嵌套子目录）。

**执行步骤**:

```bash
mkdir -p src/orf
mkdir -p src/orf/channels      # 格式转换通道（MD→DOCX/ODT/EPUB/PPTX）
mkdir -p src/orf/parsers        # manifest.json 和 YAML frontmatter 解析器
mkdir -p src/orf/converters      # 通用转换器基类
mkdir -p src/orf/logging         # 日志模块（标准 logging，匹配 OPP/OL）
mkdir -p tests
mkdir -p tests/fixtures         # 测试固件
mkdir -p logs
mkdir -p config

touch src/orf/__init__.py
touch src/orf/channels/__init__.py
touch src/orf/parsers/__init__.py
touch src/orf/converters/__init__.py
touch src/orf/logging/__init__.py
```

### 1.2 创建 pyproject.toml

**文件**: `pyproject.toml`

```toml
[project]
name = "omni-re-formatter"
version = "0.1.0"
description = "Omni-Re-Formatter: 将本地化后的 MD/XLIFF 还原为目标复杂格式"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [
    { name = "1StepMore" }
]
keywords = ["localization", "docx", "md", "xliff", "pandoc"]
classifiers = [
    "Development Status :: 1 - Planning",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "click>=8.1.0",
    "tqdm>=4.66.0",
    "pyyaml>=6.0",
    "python-magic>=0.4.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
]

[project.scripts]
orf = "orf.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/orf"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
```

### 1.3 创建 README.md

**文件**: `README.md`

```markdown
# Omni-Re-Formatter (ORF)

ORF 是 Omni 文档本地化生态的最后一环，负责将标准化中间件还原为目标复杂格式。

## 核心功能

- 读取 OL 翻译后的 MD/XLIFF 及 manifest.json/skeleton.zip
- 调用 Pandoc/md2pptx/translate-toolkit 等成熟轮子
- 配合自研胶水代码（manifest 解析、skeleton 回填、资源路径还原）
- 重组生成本地化的复杂格式文档

## 支持格式

- **MD 回写**: DOCX, ODT, EPUB, HTML, RTF, PDF
- **XLIFF 回写**: DOCX (基于 skeleton.zip), ODF

## 安装

```bash
pip install omni-re-formatter
```

## 快速开始

```bash
# MD 转 DOCX
orf apply-md translated.md --target-format docx --output result.docx

# XLIFF 回填（需要 skeleton.zip）
orf apply-xliff original.skeleton.zip --xliff translated.xlf --output result.docx
```

## 依赖关系

- OPP (Omni-Pre-Processor): 提取文档为 MD/XLIFF + manifest.json + skeleton.zip
- OL (Omni-Localizer): 翻译 MD/XLIFF，输出含 YAML frontmatter 的本地化文件
- ORF: 读取本地化文件，还原为目标格式

## 开发

```bash
pip install -e ".[dev]"
pytest tests/
```
```

### 1.4 配置文件

**文件**: `config/default.yaml`

```yaml
# ORF 默认配置

# 转换设置
conversion:
  # 性能限制
  max_file_size_mb: 500
  max_paragraphs: 10000
  max_slides: 500
  max_translation_units: 10000

  # 并发限制
  max_concurrent_tasks: 5

  # 图片处理
  image_max_dpi: 300
  image_compression: true

# Pandoc 设置
pandoc:
  version: "3.x"  # 需在 CI 中锁定版本
  reference_docx: "config/reference.docx"
  reference_odt: "config/reference.odt"

# 日志设置
logging:
  level: "INFO"
  format: "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
  log_dir: "logs"
  rotation:
    max_bytes: 10485760  # 10MB
    backup_count: 5

# 资源管理
resources:
  storage_dir: "resources"
  deduplicate: true
  hash_algorithm: "md5"
```

### 1.5 初始化日志模块

**文件**: `src/orf/logging/__init__.py`

**注意**：使用标准 `logging` 模块，匹配 OPP (`opp/logger.py`) 和 OL (`ol_logging/`) 的惯例。

```python
"""ORF 日志系统

基于标准 logging 模块，追踪转换全生命周期。
匹配 OPP/OL 的日志惯例。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

# 日志文件命名
LOG_FILE_PATTERN = "orf_{date}.log"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# 全局 logger 缓存
_loggers = {}


def setup_logger(name: str = "orf", level: str = "INFO") -> logging.Logger:
    """配置 ORF 日志器

    Args:
        name: 日志器名称，用于区分不同模块
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)

    Returns:
        配置好的 Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件 handler（DEBUG 级别，完整格式）
    log_file = LOG_DIR / LOG_FILE_PATTERN.format(date=datetime.now().strftime("%Y%m%d"))
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "orf") -> logging.Logger:
    """获取 logger 实例

    如果 logger 未配置，先进行默认配置。

    Args:
        name: 模块名称 (如 "cli", "channel.md2docx")

    Returns:
        Logger 实例
    """
    if name not in _loggers:
        return setup_logger(name)
    return _loggers[name]
```

---

## 2. Manifest 与 Frontmatter 解析器

### 2.1 Manifest 解析器

**文件**: `src/orf/parsers/manifest.py`

```python
"""OPP manifest.json 解析器

读取 OPP 输出的 manifest.json，提取源文件信息、输出路径、skeleton 路径等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orf.utils.logging import get_logger

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
    markdown: Optional[dict] = None  # {path, paragraph_count, table_count}
    xliff: Optional[dict] = None      # {path, trans_unit_count}


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
    """完整的 manifest 结构"""
    version: str
    generated_at: str
    tool: str
    tool_version: str
    source: ManifestSource
    extraction: dict
    outputs: ManifestOutputs
    skeleton: Optional[ManifestSkeleton] = None
    resources: ManifestResources
    images: list[dict] = None  # [{mime_type, width, height, data_size_bytes}]


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
```

### 2.2 Frontmatter 解析器

**文件**: `src/orf/parsers/frontmatter.py`

```python
"""OL YAML Frontmatter 解析器

读取 OL 翻译后 MD 文件开头的 YAML frontmatter，提取翻译元数据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from orf.utils.logging import get_logger

logger = get_logger("parser.frontmatter")


@dataclass
class FrontmatterMetadata:
    """YAML frontmatter 元数据"""
    source_lang: str
    target_lang: str
    original_file: str
    processor: str
    version: str
    translated_at: str


class FrontmatterParseError(Exception):
    """Frontmatter 解析错误"""
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
```

### 2.3 解析器测试

**注意**：测试使用扁平结构，匹配 OPP/OL 惯例。

**文件**: `tests/test_manifest_parser.py`

```python
"""Manifest 解析器测试"""

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
    """创建示例 manifest.json"""
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
    """测试成功解析 manifest"""
    manifest = parse_manifest(sample_manifest)

    assert isinstance(manifest, Manifest)
    assert manifest.version == "1.0"
    assert manifest.source.format == "DOCX"
    assert manifest.source.original_filename == "spec.docx"
    assert manifest.skeleton is not None
    assert manifest.skeleton.path == "spec.skeleton.zip"
    assert manifest.outputs.markdown["path"] == "spec.md"
    assert manifest.outputs.xliff["trans_unit_count"] == 42


def test_parse_manifest_missing_file():
    """测试解析不存在的文件"""
    with pytest.raises(ManifestParseError, match="Manifest file not found"):
        parse_manifest("/nonexistent/manifest.json")


def test_parse_manifest_invalid_json(tmp_path: Path):
    """测试解析无效 JSON"""
    invalid_manifest = tmp_path / "invalid.json"
    invalid_manifest.write_text("{ not json }")

    with pytest.raises(ManifestParseError, match="Invalid JSON"):
        parse_manifest(invalid_manifest)


def test_parse_manifest_missing_fields(tmp_path: Path):
    """测试解析缺少必要字段的 manifest"""
    incomplete_manifest = tmp_path / "incomplete.json"
    incomplete_manifest.write_text('{"manifest_version": "1.0"}')  # 缺少 source 和 extraction

    with pytest.raises(ManifestParseError, match="Missing required field"):
        parse_manifest(incomplete_manifest)


def test_find_manifest_by_md_path(tmp_path: Path):
    """测试根据 MD 路径查找 manifest"""
    md_file = tmp_path / "spec.md"
    md_file.touch()

    # 创建 manifest
    manifest_data = {"manifest_version": "1.0", "source": {}, "extraction": {}}
    manifest_file = tmp_path / "spec_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)

    found = find_manifest(md_file)
    assert found == manifest_file


def test_find_manifest_not_found(tmp_path: Path):
    """测试找不到 manifest"""
    md_file = tmp_path / "orphan.md"
    md_file.touch()

    found = find_manifest(md_file)
    assert found is None
```

**文件**: `tests/test_frontmatter_parser.py`

```python
"""Frontmatter 解析器测试"""

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
    """创建带 frontmatter 的 MD 文件

    注意：OL 输出的 frontmatter 不使用 ... 尾随符。
    """
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
    """创建不带 frontmatter 的 MD 文件"""
    content = """# 用户手册

这是普通内容，没有 frontmatter。
"""

    md_file = tmp_path / "plain.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


def test_parse_frontmatter_success(md_with_frontmatter: Path):
    """测试成功解析 frontmatter"""
    metadata = parse_frontmatter(md_with_frontmatter)

    assert isinstance(metadata, FrontmatterMetadata)
    assert metadata.source_lang == "en"
    assert metadata.target_lang == "zh"
    assert metadata.original_file == "spec.md"
    assert metadata.processor == "OL"
    assert metadata.version == "0.1.0"


def test_parse_frontmatter_missing_file():
    """测试解析不存在的文件"""
    with pytest.raises(FrontmatterParseError, match="MD file not found"):
        parse_frontmatter("/nonexistent/file.md")


def test_parse_frontmatter_no_frontmatter(md_without_frontmatter: Path):
    """测试解析没有 frontmatter 的文件"""
    with pytest.raises(FrontmatterParseError, match="No YAML frontmatter found"):
        parse_frontmatter(md_without_frontmatter)


def test_strip_frontmatter(md_with_frontmatter: Path):
    """测试移除 frontmatter"""
    content = md_with_frontmatter.read_text()
    stripped = strip_frontmatter(content)

    assert not stripped.startswith("---")
    assert stripped.startswith("# 用户手册")
    assert "translated_at" not in stripped


def test_has_frontmatter():
    """测试 frontmatter 检测"""
    # OL 实际输出的 frontmatter 不使用 ...
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
    """测试查找含 frontmatter 的 MD 文件"""
    # 创建多个 MD 文件（使用 OL 实际 frontmatter 格式）
    (tmp_path / "spec1_zh.md").write_text("---\nkey: value\nprocessor: \"OL\"\n---\n# Title\n", encoding="utf-8")
    (tmp_path / "spec2_zh.md").write_text("---\nkey: value\nprocessor: \"OL\"\n---\n# Title\n", encoding="utf-8")
    (tmp_path / "plain.md").write_text("# Plain\n", encoding="utf-8")

    found = find_md_with_frontmatter(tmp_path)
    assert len(found) == 2
    assert all(f.stem.endswith("_zh") for f in found)
```

---

## 3. 格式转换通道（MD→DOCX/ODT/EPUB）

### 3.1 通道基类

**文件**: `src/orf/converters/base.py`

```python
"""格式转换器基类

定义通用接口，所有格式通道都应继承此基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata


@dataclass
class ConversionResult:
    """转换结果"""
    output_path: Path
    success: bool
    warnings: list[str] = None
    errors: list[str] = None
    metadata: dict = None  # 转换相关元数据

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


class BaseConverter(ABC):
    """格式转换器基类"""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        """初始化转换器

        Args:
            manifest: OPP manifest.json 元数据
            frontmatter: OL YAML frontmatter 元数据
        """
        self.manifest = manifest
        self.frontmatter = frontmatter

    @abstractmethod
    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        """执行格式转换

        Args:
            input_path: 输入文件路径（MD 文件）
            output_path: 输出文件路径
            **options: 格式特定选项

        Returns:
            ConversionResult
        """
        pass

    @abstractmethod
    def validate_input(self, input_path: Path | str) -> bool:
        """验证输入文件

        Args:
            input_path: 输入文件路径

        Returns:
            True if valid
        """
        pass

    @property
    @abstractmethod
    def supported_format(self) -> str:
        """支持的输出格式名称（如 'DOCX', 'ODT', 'EPUB'）"""
        pass

    def get_log_context(self) -> dict:
        """获取日志上下文信息"""
        context = {"converter": self.supported_format}

        if self.manifest:
            context["source_format"] = self.manifest.source.format
            context["source_lang"] = self.manifest.extraction.get("source_lang")
            context["target_lang"] = self.manifest.extraction.get("target_lang")

        if self.frontmatter:
            context["original_file"] = self.frontmatter.original_file
            context["translated_at"] = self.frontmatter.translated_at

        return context
```

### 3.2 MD→DOCX 通道

**文件**: `src/orf/channels/md2docx.py`

```python
"""Markdown 转 DOCX 通道

基于 Pandoc 实现，支持 reference-doc 模板。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.utils.logging import get_logger

logger = get_logger("channel.md2docx")


class MD2DOCXConverter(BaseConverter):
    """Markdown → DOCX 转换器"""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        reference_docx: Optional[Path | str] = None,
    ):
        super().__init__(manifest, frontmatter)
        self.reference_docx = Path(reference_docx) if reference_docx else None

    @property
    def supported_format(self) -> str:
        return "DOCX"

    def validate_input(self, input_path: Path | str) -> bool:
        """验证输入是否为有效 MD 文件"""
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        """执行 MD→DOCX 转换

        Args:
            input_path: MD 文件路径
            output_path: 输出 DOCX 路径
            **options: 可选参数
                - template: 使用 reference-doc 模板路径

        Returns:
            ConversionResult
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        # 构建 Pandoc 命令
        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "docx",
        ]

        # 添加 reference-doc 模板
        template = options.get("template") or self.reference_docx
        if template:
            cmd.extend(["--reference-doc", str(template)])

        # 添加选项
        if options.get("extract_media"):
            cmd.append("--extract-media=.")

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.debug(f"Pandoc output: {result.stdout}")
            if result.stderr:
                logger.warning(f"Pandoc stderr: {result.stderr}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
```

### 3.3 MD→ODT 通道

**文件**: `src/orf/channels/md2odt.py`

```python
"""Markdown 转 ODT 通道

基于 Pandoc 实现，支持 reference-odt 模板。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.utils.logging import get_logger

logger = get_logger("channel.md2odt")


class MD2ODTConverter(BaseConverter):
    """Markdown → ODT 转换器"""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        reference_odt: Optional[Path | str] = None,
    ):
        super().__init__(manifest, frontmatter)
        self.reference_odt = Path(reference_odt) if reference_odt else None

    @property
    def supported_format(self) -> str:
        return "ODT"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "odt",
        ]

        template = options.get("template") or self.reference_odt
        if template:
            cmd.extend(["--reference-doc", str(template)])

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
```

### 3.4 MD→EPUB 通道

**文件**: `src/orf/channels/md2epub.py`

```python
"""Markdown 转 EPUB 通道

基于 Pandoc 实现，处理元数据与目录。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.utils.logging import get_logger

logger = get_logger("channel.md2epub")


class MD2EPUBConverter(BaseConverter):
    """Markdown → EPUB 转换器"""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "EPUB"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "epub",
        ]

        # EPUB 元数据选项
        if options.get("title"):
            cmd.extend(["--metadata", f"title={options['title']}"])
        if options.get("author"):
            cmd.extend(["--metadata", f"author={options['author']}"])
        if options.get("lang"):
            cmd.extend(["--metadata", f"lang={options['lang']}"])

        # 目录
        if options.get("toc"):
            cmd.append("--toc")

        # 嵌入图片
        if options.get("embed_images"):
            cmd.append("--self-contained")

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
```

### 3.5 通道测试

**注意**：测试使用扁平结构，匹配 OPP/OL 惯例。

**文件**: `tests/test_md2docx_channel.py`

```python
"""MD→DOCX 通道测试"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.md2docx import MD2DOCXConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    """创建示例 MD 文件"""
    content = """# 用户手册

这是中文内容。

## 第一章

- 列表项 1
- 列表项 2

| 表格 | 列 |
|------|---|
| 数据 | 值 |
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def mock_pandoc_success(sample_md: Path, tmp_path: Path):
    """模拟成功的 Pandoc 执行"""
    output = tmp_path / "test.docx"

    def mock_run(cmd, *args, **kwargs):
        output.touch()  # 创建输出文件
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_run):
        yield output


class TestMD2DOCXConverter:
    """MD2DOCXConverter 测试"""

    def test_supported_format(self):
        """测试支持的格式名称"""
        converter = MD2DOCXConverter()
        assert converter.supported_format == "DOCX"

    def test_validate_input_valid(self, sample_md: Path):
        """测试有效输入验证"""
        converter = MD2DOCXConverter()
        assert converter.validate_input(sample_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        """测试无效扩展名"""
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2DOCXConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        """测试不存在的文件"""
        converter = MD2DOCXConverter()
        assert converter.validate_input("/nonexistent/file.md") is False

    @patch("subprocess.run")
    def test_convert_success(self, mock_run, sample_md: Path, tmp_path: Path):
        """测试成功转换"""
        output = tmp_path / "output.docx"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )

        converter = MD2DOCXConverter()
        result = converter.convert(sample_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert "pandoc" in result.metadata["tool"]

        # 验证命令包含正确的参数
        call_args = mock_run.call_args[0][0]
        assert "pandoc" in call_args
        assert str(sample_md) in call_args
        assert str(output) in call_args
        assert "--to" in call_args
        assert "docx" in call_args

    @patch("subprocess.run")
    def test_convert_with_template(self, mock_run, sample_md: Path, tmp_path: Path):
        """测试带模板转换"""
        output = tmp_path / "output.docx"
        template = tmp_path / "template.docx"
        template.touch()
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        converter = MD2DOCXConverter(reference_docx=template)
        result = converter.convert(sample_md, output)

        assert result.success is True
        call_args = mock_run.call_args[0][0]
        assert "--reference-doc" in call_args
        assert str(template) in call_args

    @patch("subprocess.run")
    def test_convert_pandoc_error(self, mock_run, sample_md: Path, tmp_path: Path):
        """测试 Pandoc 执行错误"""
        output = tmp_path / "output.docx"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "pandoc", stderr="Unknown extension"
        )

        converter = MD2DOCXConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert len(result.errors) > 0
        assert "Pandoc error" in result.errors[0]

    @patch("subprocess.run")
    def test_convert_pandoc_not_found(self, mock_run, sample_md: Path, tmp_path: Path):
        """测试 Pandoc 未找到"""
        output = tmp_path / "output.docx"
        mock_run.side_effect = FileNotFoundError()

        converter = MD2DOCXConverter()
        result = converter.convert(sample_md, output)

        assert result.success is False
        assert "not in PATH" in result.errors[0]

    def test_convert_invalid_input(self, tmp_path: Path):
        """测试无效输入"""
        invalid_file = tmp_path / "nonexistent.md"
        output = tmp_path / "output.docx"

        converter = MD2DOCXConverter()
        result = converter.convert(invalid_file, output)

        assert result.success is False
        assert "Invalid input file" in result.errors[0]

    def test_get_log_context(self, sample_md: Path):
        """测试日志上下文"""
        from orf.parsers.manifest import Manifest, ManifestSource, ManifestOutputs
        from orf.parsers.frontmatter import FrontmatterMetadata

        mock_manifest = MagicMock(spec=Manifest)
        mock_manifest.source.format = "DOCX"
        mock_manifest.extraction = {"source_lang": "en", "target_lang": "zh"}

        mock_frontmatter = MagicMock(spec=FrontmatterMetadata)
        mock_frontmatter.original_file = "spec.md"
        mock_frontmatter.translated_at = "2026-05-22T15:00:00Z"

        converter = MD2DOCXConverter(manifest=mock_manifest, frontmatter=mock_frontmatter)
        context = converter.get_log_context()

        assert context["converter"] == "DOCX"
        assert context["source_format"] == "DOCX"
        assert context["source_lang"] == "en"
        assert context["target_lang"] == "zh"
        assert context["original_file"] == "spec.md"
```

---

## 4. CLI 入口

### 4.1 CLI 实现

**文件**: `src/orf/cli.py`

```python
"""ORF 命令行接口

支持 MD 文件的格式转换，读取 manifest.json 和 YAML frontmatter。
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from tqdm import tqdm

from orf.channels.md2docx import MD2DOCXConverter
from orf.channels.md2odt import MD2ODTConverter
from orf.channels.md2epub import MD2EPUBConverter
from orf.parsers.manifest import parse_manifest, find_manifest, ManifestParseError
from orf.parsers.frontmatter import (
    parse_frontmatter,
    FrontmatterParseError,
    has_frontmatter,
    strip_frontmatter,
)
from orf.utils.logging import setup_logger, get_logger

logger = get_logger("cli")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="启用详细日志")
def main(verbose: bool):
    """ORF - Omni-Re-Formatter

    将本地化后的 MD/XLIFF 还原为目标复杂格式。
    """
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(level=log_level)


@main.command("apply-md")
@click.argument("input_md", type=click.Path(exists=True))
@click.option(
    "--target-format",
    "-t",
    type=click.Choice(["docx", "odt", "epub", "html", "rtf", "pdf"]),
    default="docx",
    help="目标格式",
)
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--template", type=click.Path(), help="Pandoc reference 模板路径")
@click.option("--title", type=str, help="EPUB 标题")
@click.option("--author", type=str, help="EPUB 作者")
@click.option("--lang", type=str, default="zh", help="EPUB 语言")
@click.option("--embed-images", is_flag=True, help="EPUB 嵌入图片")
def apply_md(
    input_md: str,
    target_format: str,
    output: str | None,
    template: str | None,
    title: str | None,
    author: str | None,
    lang: str,
    embed_images: bool,
):
    """将 MD 文件转换为目标格式

    INPUT_MD: 输入的 MD 文件路径（通常由 OL 翻译后的文件）
    """
    input_path = Path(input_md)

    # 如果未指定输出，自动生成
    if output is None:
        output_path = input_path.with_suffix(f".{target_format}")
    else:
        output_path = Path(output)

    logger.info(f"Converting {input_path} -> {output_path} ({target_format})")

    # 尝试解析 manifest.json
    manifest = None
    try:
        manifest_path = find_manifest(input_path)
        if manifest_path:
            logger.info(f"Found manifest: {manifest_path}")
            manifest = parse_manifest(manifest_path)
    except ManifestParseError as e:
        logger.warning(f"Failed to parse manifest: {e}")

    # 尝试解析 YAML frontmatter
    frontmatter = None
    try:
        frontmatter = parse_frontmatter(input_path)
        logger.info(
            f"Frontmatter: {frontmatter.source_lang} -> {frontmatter.target_lang}"
        )
    except FrontmatterParseError as e:
        logger.warning(f"Failed to parse frontmatter: {e}")

    # 根据目标格式选择转换器
    if target_format == "docx":
        converter = MD2DOCXConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "odt":
        converter = MD2ODTConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "epub":
        converter = MD2EPUBConverter(manifest=manifest, frontmatter=frontmatter)
    else:
        logger.error(f"Unsupported format: {target_format}")
        click.echo(f"Error: Unsupported format '{target_format}'", err=True)
        sys.exit(1)

    # 执行转换
    options = {}
    if template:
        options["template"] = Path(template)
    if title:
        options["title"] = title
    if author:
        options["author"] = author
    if lang:
        options["lang"] = lang
    if embed_images:
        options["embed_images"] = True

    result = converter.convert(input_path, output_path, **options)

    if result.success:
        logger.info(f"Conversion successful: {result.output_path}")
        click.echo(f"✓ Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        click.echo(f"✗ Conversion failed:", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)


@main.command("convert-batch")
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--target-format", "-t", type=click.Choice(["docx", "odt", "epub"]))
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--pattern", "-p", default="*.md", help="文件匹配模式")
def convert_batch(
    input_dir: str,
    target_format: str,
    output_dir: str | None,
    pattern: str,
):
    """批量转换 MD 文件"""
    input_path = Path(input_dir)
    output_path = Path(output_dir) if output_dir else input_path

    # 查找所有 MD 文件（含 frontmatter）
    md_files = []
    for md_file in input_path.rglob(pattern):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if has_frontmatter(content):
                md_files.append(md_file)
        except Exception as e:
            logger.warning(f"Skipping {md_file}: {e}")

    logger.info(f"Found {len(md_files)} MD files to convert")

    if not md_files:
        click.echo("No files found to convert")
        return

    # 选择转换器
    if target_format == "docx":
        converter_class = MD2DOCXConverter
    elif target_format == "odt":
        converter_class = MD2ODTConverter
    elif target_format == "epub":
        converter_class = MD2EPUBConverter
    else:
        click.echo(f"Unsupported format: {target_format}", err=True)
        sys.exit(1)

    # 批量转换
    success_count = 0
    fail_count = 0

    with tqdm(total=len(md_files), desc=f"Converting to {target_format}") as pbar:
        for md_file in md_files:
            try:
                manifest = None
                try:
                    manifest_path = find_manifest(md_file)
                    if manifest_path:
                        manifest = parse_manifest(manifest_path)
                except Exception:
                    pass

                frontmatter = None
                try:
                    frontmatter = parse_frontmatter(md_file)
                except Exception:
                    pass

                converter = converter_class(manifest=manifest, frontmatter=frontmatter)
                output_file = output_path / f"{md_file.stem}.{target_format}"

                result = converter.convert(md_file, output_file)

                if result.success:
                    success_count += 1
                else:
                    fail_count += 1
                    logger.error(f"Failed: {md_file}: {result.errors}")

            except Exception as e:
                fail_count += 1
                logger.error(f"Error processing {md_file}: {e}")

            pbar.update(1)

    click.echo(f"\nCompleted: {success_count} succeeded, {fail_count} failed")


if __name__ == "__main__":
    main()
```

---

## 5. 实施检查清单

### 5.1 项目骨架（预计 0.5 天）

- [x] 创建项目目录结构 (`src/orf/`, `tests/`, `config/`, `logs/`)
- [x] 创建 `pyproject.toml` 并配置依赖（不含 loguru，使用标准 logging）
- [x] 创建 `README.md`
- [x] 创建 `config/default.yaml`
- [x] 初始化 `src/orf/logging/__init__.py` 日志模块（标准 logging）
- [x] 运行 `pip install -e ".[dev]"` 验证依赖
- [x] 运行 `pytest --collect-only` 验证测试可被发现

### 5.2 Manifest/Frontmatter 解析器（预计 0.5 天）

- [x] 实现 `src/orf/parsers/manifest.py` 的 `parse_manifest()` 和 `find_manifest()`
- [x] 实现 `src/orf/parsers/frontmatter.py` 的 `parse_frontmatter()`, `strip_frontmatter()`, `has_frontmatter()`, `find_md_with_frontmatter()`
- [x] 编写 `tests/test_manifest_parser.py`（6 个测试用例）
- [x] 编写 `tests/test_frontmatter_parser.py`（6 个测试用例）
- [x] 运行所有解析器测试，确保通过

### 5.3 格式转换通道（预计 0.5 天）

- [x] 实现 `src/orf/converters/base.py` 基类
- [x] 实现 `src/orf/channels/md2docx.py` 的 `MD2DOCXConverter`
- [x] 实现 `src/orf/channels/md2odt.py` 的 `MD2ODTConverter`
- [x] 实现 `src/orf/channels/md2epub.py` 的 `MD2EPUBConverter`
- [x] 编写 `tests/test_md2docx_channel.py`（8 个测试用例）
- [x] 编写 `tests/test_md2odt_channel.py`
- [x] 编写 `tests/test_md2epub_channel.py`
- [x] 运行所有通道测试，确保通过

### 5.4 CLI 入口（预计 0.5 天）

- [x] 实现 `src/orf/cli.py` 的 `apply-md` 和 `convert-batch` 命令
- [x] 配置 click 命令组
- [x] 集成 manifest/frontmatter 解析
- [x] 测试 CLI `--help` 输出
- [x] 测试 `orf apply-md input.md --target-format docx`
- [x] 测试 `orf convert-batch input_dir --target-format docx`

### 5.5 CI/CD 配置（预计 0.5 天）

- [x] 创建 `.github/workflows/test.yml`
- [x] 配置 Python 3.10/3.11/3.12 测试矩阵
- [x] 配置 Pandoc 安装（Linux/macOS/Windows）
- [x] 配置 pytest + coverage
- [x] 配置 ruff lint 检查
- [x] 推送首次 commit，验证 CI 通过

---

## 6. 验收标准

### 6.1 功能验收

- [ ] `orf apply-md spec_zh.md --target-format docx` 成功生成 `spec_zh.docx`
- [ ] `orf apply-md spec_zh.md --target-format odt` 成功生成 `spec_zh.odt`
- [ ] `orf apply-md spec_zh.md --target-format epub --title "用户手册"` 成功生成 `spec_zh.epub`
- [ ] `orf convert-batch output_dir --target-format docx` 批量转换成功

### 6.2 元数据验收

- [ ] manifest.json 解析成功率 100%
- [ ] YAML frontmatter 解析成功率 100%
- [ ] manifest + frontmatter 都缺失时，转换仍可进行（使用默认值）

### 6.3 异常处理验收

- [ ] 无效 MD 文件 → 报错，进程不崩溃
- [ ] Pandoc 未安装 → 友好提示
- [ ] 输出路径不可写 → 报错

### 6.4 性能验收

- [ ] Manifest + Frontmatter 解析 ≤ 10ms
- [ ] MD→DOCX 转换 ≥ 15MB/s

---

## 7. 文件结构（Phase 0 完成后）

**注意**：测试目录为扁平结构，匹配 OPP/OL 惯例。日志使用 `logging/` 模块（标准 logging），匹配 OPP/OL。

```
omni-re-formatter/
├── .github/
│   └── workflows/
│       └── test.yml          # CI/CD 配置
├── config/
│   └── default.yaml          # 默认配置
├── logs/                     # 日志目录
├── src/
│   └── orf/
│       ├── __init__.py
│       ├── cli.py             # CLI 入口
│       ├── channels/          # 格式转换通道
│       │   ├── __init__.py
│       │   ├── md2docx.py
│       │   ├── md2odt.py
│       │   └── md2epub.py
│       ├── converters/       # 转换器基类
│       │   ├── __init__.py
│       │   └── base.py
│       ├── parsers/          # 元数据解析器
│       │   ├── __init__.py
│       │   ├── manifest.py
│       │   └── frontmatter.py
│       └── logging/          # 日志模块（标准 logging）
│           └── __init__.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/             # 测试固件
│   ├── test_md2docx_channel.py
│   ├── test_md2odt_channel.py
│   ├── test_md2epub_channel.py
│   ├── test_manifest_parser.py
│   ├── test_frontmatter_parser.py
│   ├── test_resource_manager.py
│   └── test_logging_system.py
├── pyproject.toml
└── README.md
```

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| Pandoc 版本差异 | 输出不一致 | CI 中锁定 Pandoc 版本 |
| manifest/frontmatter 格式不兼容 | 解析失败 | 宽松解析 + 降级策略 + 警告 |
| 图片路径断链 | 文档图片丢失 | 解析资源目录 + 路径映射 |
| Windows/macOS/Linux 路径差异 | 文件找不到 | 使用 `pathlib.Path` 统一处理 |

---

## 9. 审查修正记录

### v1.0 → v1.1 修正内容

| 项目 | 修正前 | 修正后 | 原因 |
|------|--------|--------|------|
| 测试目录结构 | `tests/test_channels/` + `tests/test_parsers/` (嵌套) | 扁平 `tests/` 结构 | 匹配 OPP/OL 惯例 |
| 日志库 | loguru | 标准 `logging` 模块 | 匹配 OPP (`opp/logger.py`) 和 OL (`ol_logging/`) |
| 日志模块路径 | `src/orf/utils/logging.py` | `src/orf/logging/__init__.py` | 标准 logging 模块位置 |
| Frontmatter 正则 | `r'^---\s*\n(.*?)\n\.\.\.\s*\n'` | `r'^---\s*\n(.*?)\n---\s*\n'` | OL 实际输出不使用 `...` |
| 测试固件 frontmatter | 包含 `...` 尾随符 | 移除 `...` | 匹配 OL 实际输出格式 |
| pyproject.toml 依赖 | 包含 `loguru>=0.7.0` | 移除 loguru | 使用标准 logging 模块 |