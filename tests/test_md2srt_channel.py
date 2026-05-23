"""MD to SRT extraction channel tests."""

from pathlib import Path

import pytest
from orf.channels.md2srt import MD2SRTConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_md_with_srt(tmp_path: Path) -> Path:
    content = """# 视频字幕

这是一些介绍文字。

1
00:00:01,000 --> 00:00:03,000
**第一行字幕**

2
00:00:04,000 --> 00:00:06,000
*第二行字幕*

3
00:00:07,000 --> 00:00:09,000
普通文本
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def sample_md_without_srt(tmp_path: Path) -> Path:
    content = """# 普通文档

这是普通内容，没有字幕。
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestMD2SRTConverter:
    def test_supported_format(self):
        converter = MD2SRTConverter()
        assert converter.supported_format == "SRT"

    def test_validate_input_valid(self, sample_md_with_srt: Path):
        converter = MD2SRTConverter()
        assert converter.validate_input(sample_md_with_srt) is True

    def test_validate_input_invalid(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2SRTConverter()
        assert converter.validate_input(txt_file) is False

    def test_convert_success(self, sample_md_with_srt: Path, tmp_path: Path):
        output = tmp_path / "output.srt"

        converter = MD2SRTConverter()
        result = converter.convert(sample_md_with_srt, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert result.metadata["blocks_extracted"] == 3

        content = output.read_text(encoding="utf-8")
        assert "00:00:01,000 --> 00:00:03,000" in content
        assert "**第一行字幕**" not in content
        assert "第一行字幕" in content
        assert "第二行字幕" in content

    def test_convert_no_srt_blocks(self, sample_md_without_srt: Path, tmp_path: Path):
        output = tmp_path / "output.md"

        converter = MD2SRTConverter()
        result = converter.convert(sample_md_without_srt, output)

        assert result.success is True
        assert result.metadata["blocks_extracted"] == 0
        content = output.read_text(encoding="utf-8")
        assert "这是普通内容，没有字幕。" in content

    def test_convert_invalid_input(self, tmp_path: Path):
        invalid_file = tmp_path / "nonexistent.md"
        output = tmp_path / "output.srt"

        converter = MD2SRTConverter()
        result = converter.convert(invalid_file, output)

        assert result.success is False
        assert "Invalid input file" in result.errors[0]

    def test_clean_subtitle_text(self):
        converter = MD2SRTConverter()
        text = "**bold** and *italic* and ~~strike~~ and `code`"
        cleaned = converter._clean_subtitle_text(text)
        assert cleaned == "bold and italic and strike and code"

    def test_clean_subtitle_text_underscore(self):
        converter = MD2SRTConverter()
        text = "__bold__ and _italic_"
        cleaned = converter._clean_subtitle_text(text)
        assert cleaned == "bold and italic"