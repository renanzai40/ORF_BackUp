"""格式转换器基类

定义通用接口，所有格式通道都应继承此基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata


@dataclass
class ConversionResult:
    """转换结果"""
    output_path: Path
    success: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        pass


class BaseConverter(ABC):
    """格式转换器基类"""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ) -> None:
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
        **options: Any,
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

    def get_log_context(self) -> dict[str, Any]:
        """获取日志上下文信息"""
        context: dict[str, Any] = {"converter": self.supported_format}

        if self.manifest:
            context["source_format"] = self.manifest.source.format
            context["source_lang"] = self.manifest.extraction.get("source_lang")
            context["target_lang"] = self.manifest.extraction.get("target_lang")

        if self.frontmatter:
            context["original_file"] = self.frontmatter.original_file
            context["translated_at"] = self.frontmatter.translated_at

        return context