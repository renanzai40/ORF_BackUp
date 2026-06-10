"""MD to IPYNB channel tests.

Tests for MD2IPYNBConverter which produces Jupyter notebooks from Markdown.
The `nbformat` library is optional and is mocked at the import boundary via
``sys.modules`` so the test suite does not require it to be installed.
"""

import sys
import types
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Install nbformat / nbformat.v4 mocks BEFORE importing the channel module
# (the channel does `import nbformat` at module level).
# ---------------------------------------------------------------------------


class _FakeCell:
    """Minimal cell object exposing the attributes the converter reads back."""

    def __init__(self, cell_type: str, source: str, language: str | None = None):
        self.cell_type = cell_type
        self.source = source
        self.metadata: dict[str, Any] = {}
        if language is not None:
            self.metadata["language"] = language.capitalize()


class _FakeNotebook:
    def __init__(self):
        self.cells: list[_FakeCell] = []
        self.metadata: dict[str, Any] = {}


_nbformat_writes: list[tuple[Any, Any]] = []


def _new_notebook(cells=None):
    nb = _FakeNotebook()
    nb.cells = list(cells or [])
    return nb


def _new_code_cell(source):
    return _FakeCell("code", source, language="python")


def _new_markdown_cell(source):
    return _FakeCell("markdown", source)


def _fake_write(nb, output_path):
    _nbformat_writes.append((nb, output_path))


def _install_nbformat_mocks() -> None:
    if "nbformat" in sys.modules:
        return
    nbformat_mod = types.ModuleType("nbformat")
    nbformat_v4 = types.ModuleType("nbformat.v4")

    nbformat_v4.new_notebook = _new_notebook
    nbformat_v4.new_code_cell = _new_code_cell
    nbformat_v4.new_markdown_cell = _new_markdown_cell
    nbformat_mod.write = _fake_write
    nbformat_mod.v4 = nbformat_v4

    sys.modules["nbformat"] = nbformat_mod
    sys.modules["nbformat.v4"] = nbformat_v4


_install_nbformat_mocks()


# Now safe to import the channel.
import pytest

from orf.channels import md2ipynb
from orf.converters.base import ConversionResult


@pytest.fixture
def nb_md(tmp_path: Path) -> Path:
    content = (
        "# Heading\n"
        "\n"
        "Some intro text.\n"
        "\n"
        "```python\n"
        "print('hi')\n"
        "```\n"
        "\n"
        "Trailing prose.\n"
    )
    md = tmp_path / "notebook.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def nb_empty_md(tmp_path: Path) -> Path:
    md = tmp_path / "empty.md"
    md.write_text("", encoding="utf-8")
    return md


@pytest.fixture
def nb_python2_md(tmp_path: Path) -> Path:
    content = (
        "```python\n"
        "print('hi')\n"
        "```\n"
    )
    md = tmp_path / "py2.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def nb_multi_lang_md(tmp_path: Path) -> Path:
    content = (
        "```python\n"
        "x = 1\n"
        "```\n"
        "\n"
        "```javascript\n"
        "let y = 2;\n"
        "```\n"
    )
    md = tmp_path / "multi.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def nb_no_lang_md(tmp_path: Path) -> Path:
    content = (
        "```\n"
        "plain code\n"
        "```\n"
    )
    md = tmp_path / "nolang.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture(autouse=True)
def _clear_writes():
    _nbformat_writes.clear()
    yield
    _nbformat_writes.clear()


class TestMD2IPYNBConverter:
    def test_supported_format(self):
        converter = md2ipynb.MD2IPYNBConverter()
        assert converter.supported_format == "IPYNB"

    def test_validate_input_valid(self, nb_md: Path):
        converter = md2ipynb.MD2IPYNBConverter()
        assert converter.validate_input(nb_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = md2ipynb.MD2IPYNBConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = md2ipynb.MD2IPYNBConverter()
        assert converter.validate_input("/nonexistent/file.md") is False

    def test_convert_creates_notebook_with_code_and_markdown_cells(
        self, nb_md: Path, tmp_path: Path
    ):
        output = tmp_path / "out.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        result = converter.convert(nb_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.output_path == output
        assert len(_nbformat_writes) == 1

        nb = _nbformat_writes[0][0]
        cell_types = [c.cell_type for c in nb.cells]
        assert "markdown" in cell_types
        assert "code" in cell_types
        md_cell = next(c for c in nb.cells if c.cell_type == "markdown")
        assert "Some intro text." in md_cell.source
        code_cell = next(c for c in nb.cells if c.cell_type == "code")
        assert "print('hi')" in code_cell.source

    def test_convert_empty_md_creates_empty_notebook(
        self, nb_empty_md: Path, tmp_path: Path
    ):
        output = tmp_path / "empty.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        result = converter.convert(nb_empty_md, output)

        assert result.success is True
        assert len(_nbformat_writes) == 1
        nb = _nbformat_writes[0][0]
        assert nb.cells == []

    def test_convert_uses_python3_kernel_default(
        self, nb_md: Path, tmp_path: Path
    ):
        output = tmp_path / "kernel_default.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        converter.convert(nb_md, output)

        nb = _nbformat_writes[0][0]
        assert nb.metadata["kernelspec"]["name"] == "python3"

    def test_convert_respects_kernel_option(
        self, nb_python2_md: Path, tmp_path: Path
    ):
        output = tmp_path / "kernel_py2.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        from orf.converters.options import ConverterOptions
        converter.convert(nb_python2_md, output, ConverterOptions(kernel="python2"))

        nb = _nbformat_writes[0][0]
        assert nb.metadata["kernelspec"]["name"] == "python2"

    def test_convert_detects_code_block_language(
        self, nb_multi_lang_md: Path, tmp_path: Path
    ):
        output = tmp_path / "multi.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        converter.convert(nb_multi_lang_md, output)

        nb = _nbformat_writes[0][0]
        code_cells = [c for c in nb.cells if c.cell_type == "code"]
        languages = sorted(c.metadata["language"] for c in code_cells)
        assert languages == ["Javascript", "Python"]

    def test_convert_no_language_defaults_to_python(
        self, nb_no_lang_md: Path, tmp_path: Path
    ):
        output = tmp_path / "nolang.ipynb"

        converter = md2ipynb.MD2IPYNBConverter()
        converter.convert(nb_no_lang_md, output)

        nb = _nbformat_writes[0][0]
        code_cells = [c for c in nb.cells if c.cell_type == "code"]
        assert len(code_cells) == 1
        assert code_cells[0].metadata["language"] == "Python"

    def test_inject_images_noop(self):
        converter = md2ipynb.MD2IPYNBConverter()
        images = [{"id": "img1"}]
        applied, remaining = converter.inject_images(
            skeleton_path="ignored",
            images=images,
            output_path="ignored",
        )
        assert applied == []
        assert remaining is images
