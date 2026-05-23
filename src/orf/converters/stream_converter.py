"""流式转换器基类

提供内存高效的分块处理大文档的能力，避免 OOM。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.logging import get_logger


@dataclass
class StreamChunk:
    """流式块数据"""

    index: int
    content: str
    size: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "size", len(self.content.encode("utf-8")))

    @property
    def size_mb(self) -> float:
        """块大小（MB）"""
        return self.size / (1024 * 1024)


class StreamingConverter(BaseConverter, ABC):
    """流式转换器基类

    提供内存高效的分块处理能力，适用于大文档转换。
    """

    def __init__(
        self,
        chunk_size: int = 64 * 1024,  # 默认 64KB 块大小
        **kwargs: Any,
    ) -> None:
        """初始化流式转换器

        Args:
            chunk_size: 块大小（字节），默认 64KB
            **kwargs: 父类参数
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self._logger = get_logger()

    @abstractmethod
    def _split_chunks(
        self,
        input_path: Path | str,
    ) -> list[StreamChunk]:
        """将输入文件分割为块

        Args:
            input_path: 输入文件路径

        Returns:
            块列表
        """
        pass

    @abstractmethod
    def _process_chunk(
        self,
        chunk: StreamChunk,
        **options: Any,
    ) -> str:
        """处理单个块

        Args:
            chunk: 待处理块
            **options: 处理选项

        Returns:
            处理后的内容
        """
        pass

    @abstractmethod
    def _merge_chunks(
        self,
        chunks: list[str],
        output_path: Path | str,
    ) -> ConversionResult:
        """合并块并写入输出

        Args:
            chunks: 处理后的块列表
            output_path: 输出文件路径

        Returns:
            转换结果
        """
        pass

    def convert_stream(
        self,
        input_path: Path | str,
        output_path: Path | str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **options: Any,
    ) -> ConversionResult:
        """流式转换（带进度回调）

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            progress_callback: 进度回调函数，签名 (current, total)
            **options: 格式特定选项

        Returns:
            ConversionResult
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        self._logger.info(
            f"Starting stream conversion: {input_path} -> {output_path}",
            extra=self.get_log_context(),
        )

        # 分割块
        chunks = self._split_chunks(input_path)
        total = len(chunks)

        if total == 0:
            self._logger.warning("No chunks generated", extra=self.get_log_context())
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Input file produced no chunks"],
            )

        self._logger.info(
            f"Split into {total} chunks",
            extra={**self.get_log_context(), "chunk_count": total},
        )

        # 处理每个块
        processed: list[str] = []
        for i, chunk in enumerate(chunks):
            try:
                result = self._process_chunk(chunk, **options)
                processed.append(result)

                if progress_callback:
                    progress_callback(i + 1, total)

            except Exception as e:
                self._logger.error(
                    f"Chunk {i} processing failed: {e}",
                    extra=self.get_log_context(),
                )
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[f"Chunk {i} failed: {str(e)}"],
                )

        # 合并块
        merge_result: ConversionResult = self._merge_chunks(processed, output_path)

        self._logger.info(
            f"Stream conversion complete: {merge_result.success}",
            extra=self.get_log_context(),
        )

        return merge_result

    def iter_chunks(
        self,
        input_path: Path | str,
    ) -> Generator[StreamChunk, None, None]:
        """内存高效地迭代块（生成器）

        Args:
            input_path: 输入文件路径

        Yields:
            StreamChunk
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            index = 0
            while True:
                chunk_content = f.read(self.chunk_size)
                if not chunk_content:
                    break
                yield StreamChunk(index=index, content=chunk_content)
                index += 1