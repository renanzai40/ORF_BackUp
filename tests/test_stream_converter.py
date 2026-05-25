"""流式转换器测试"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orf.converters.stream_converter import StreamChunk, StreamingConverter
from orf.converters.base import ConversionResult


class TestStreamChunk:
    """StreamChunk 数据类测试"""

    def test_stream_chunk_creation(self):
        """测试块创建和属性"""
        chunk = StreamChunk(index=0, content="Hello, World!")
        assert chunk.index == 0
        assert chunk.content == "Hello, World!"
        assert chunk.size == len("Hello, World!".encode("utf-8"))
        assert chunk.size_mb == chunk.size / (1024 * 1024)

    def test_stream_chunk_size_calculation(self):
        """测试块大小计算（UTF-8 编码）"""
        chunk = StreamChunk(index=1, content="中文测试")
        # "中文测试" 的 UTF-8 编码长度
        expected_size = len("中文测试".encode("utf-8"))
        assert chunk.size == expected_size


class ConcreteStreamingConverter(StreamingConverter):
    """具体实现用于测试"""

    def _split_chunks(self, input_path: Path | str) -> list[StreamChunk]:
        return list(self.iter_chunks(input_path))

    def _process_chunk(self, chunk: StreamChunk, **options) -> str:
        return chunk.content.upper()

    def _merge_chunks(
        self, chunks: list[str], output_path: Path | str
    ) -> ConversionResult:
        output_path = Path(output_path)
        output_path.write_text("\n".join(chunks), encoding="utf-8")
        return ConversionResult(output_path=output_path, success=True)

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        **options,
    ) -> ConversionResult:
        return self.convert_stream(input_path, output_path, **options)

    def validate_input(self, input_path: Path | str) -> bool:
        return Path(input_path).exists()

    @property
    def supported_format(self) -> str:
        return "STREAM"


class TestStreamingConverter:
    """StreamingConverter 抽象基类测试"""

    def test_abstract_methods_required(self):
        """测试抽象方法必须被实现"""
        with pytest.raises(TypeError):
            StreamingConverter()

    def test_concrete_implementation(self):
        """测试具体实现可以实例化"""
        converter = ConcreteStreamingConverter()
        assert converter.chunk_size == 64 * 1024  # 默认值

    def test_custom_chunk_size(self):
        """测试自定义块大小"""
        converter = ConcreteStreamingConverter(chunk_size=1024)
        assert converter.chunk_size == 1024

    def test_convert_stream_success(self, tmp_path):
        """测试流式转换成功"""
        # 创建测试输入文件（大于默认 chunk_size，确保多个块）
        input_file = tmp_path / "input.txt"
        # 200KB content to ensure multiple chunks with 64KB chunk_size
        input_file.write_text("x" * 200 * 1024, encoding="utf-8")

        output_file = tmp_path / "output.txt"

        converter = ConcreteStreamingConverter()
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        result = converter.convert_stream(
            input_file,
            output_file,
            progress_callback=progress_callback,
        )

        assert result.success is True
        # 每个块处理后调用回调
        assert len(progress_calls) > 1
        # 最后一次回调 current == total
        assert progress_calls[-1] == (progress_calls[-1][0], progress_calls[-1][0])

    def test_convert_stream_no_chunks(self, tmp_path):
        """测试空文件处理"""
        input_file = tmp_path / "empty.txt"
        input_file.write_text("", encoding="utf-8")

        output_file = tmp_path / "output.txt"

        converter = ConcreteStreamingConverter()
        result = converter.convert_stream(input_file, output_file)

        assert result.success is False
        assert "produced no chunks" in result.errors[0].message

    def test_iter_chunks(self, tmp_path):
        """测试生成器迭代块"""
        input_file = tmp_path / "input.txt"
        content = "1234567890"  # 10 chars
        input_file.write_text(content, encoding="utf-8")

        converter = ConcreteStreamingConverter(chunk_size=3)
        chunks = list(converter.iter_chunks(input_file))

        assert len(chunks) == 4  # "123", "456", "789", "0"
        assert chunks[0].content == "123"
        assert chunks[0].index == 0
        assert chunks[1].content == "456"
        assert chunks[1].index == 1
        assert chunks[3].content == "0"
        assert chunks[3].index == 3

    def test_iter_chunks_file_not_found(self):
        """测试文件不存在时抛出异常"""
        converter = ConcreteStreamingConverter()
        with pytest.raises(FileNotFoundError):
            list(converter.iter_chunks("/nonexistent/file.txt"))

    def test_convert_stream_chunk_error(self, tmp_path):
        """测试块处理错误时返回失败"""
        # 创建大于 chunk_size 的输入文件以确保多个块
        input_file = tmp_path / "input.txt"
        # 150KB to ensure at least 2 chunks with 64KB chunk_size
        input_file.write_text("x" * 150 * 1024, encoding="utf-8")

        output_file = tmp_path / "output.txt"

        class ErrorConverter(ConcreteStreamingConverter):
            def _process_chunk(self, chunk: StreamChunk, **options) -> str:
                if chunk.index == 1:
                    raise ValueError("Simulated error")
                return chunk.content.upper()

        converter = ErrorConverter()
        result = converter.convert_stream(input_file, output_file)

        assert result.success is False
        assert "Chunk 1 failed" in result.errors[0].message