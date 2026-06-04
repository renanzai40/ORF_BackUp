"""MD to XML channel tests.

Tests for MD2XMLConverter which produces an XML document from Markdown
content using stdlib ``xml.etree.ElementTree``.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from orf.channels.md2xml import MD2XMLConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def xml_md(tmp_path: Path) -> Path:
    content = (
        "# Title\n"
        "\n"
        "Some paragraph.\n"
        "\n"
        "## Subhead\n"
        "\n"
        "- item 1\n"
        "- item 2\n"
    )
    md = tmp_path / "doc.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xml_headings_md(tmp_path: Path) -> Path:
    content = (
        "# h1\n"
        "## h2\n"
        "### h3\n"
    )
    md = tmp_path / "headings.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xml_code_md(tmp_path: Path) -> Path:
    content = (
        "```python\n"
        "x = 1\n"
        "```\n"
    )
    md = tmp_path / "code.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xml_list_md(tmp_path: Path) -> Path:
    content = (
        "- alpha\n"
        "- beta\n"
        "- gamma\n"
    )
    md = tmp_path / "list.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xml_table_md(tmp_path: Path) -> Path:
    content = (
        "| c1 | c2 |\n"
        "|----|----|\n"
        "| a  | b  |\n"
    )
    md = tmp_path / "tbl.md"
    md.write_text(content, encoding="utf-8")
    return md


@pytest.fixture
def xml_inline_md(tmp_path: Path) -> Path:
    content = "This has **bold** and *italic* and `code` inline.\n"
    md = tmp_path / "inline.md"
    md.write_text(content, encoding="utf-8")
    return md


class TestMD2XMLConverter:
    def test_supported_format(self):
        converter = MD2XMLConverter()
        assert converter.supported_format == "XML"

    def test_validate_input_valid(self, xml_md: Path):
        converter = MD2XMLConverter()
        assert converter.validate_input(xml_md) is True

    def test_validate_input_invalid_extension(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        converter = MD2XMLConverter()
        assert converter.validate_input(txt_file) is False

    def test_validate_input_not_exists(self):
        converter = MD2XMLConverter()
        assert converter.validate_input("/nonexistent/file.md") is False

    def test_convert_creates_document_root(
        self, xml_md: Path, tmp_path: Path
    ):
        output = tmp_path / "out.xml"

        converter = MD2XMLConverter()
        result = converter.convert(xml_md, output)

        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert output.exists()
        # Round-trip through ElementTree to confirm structural validity.
        tree = ET.parse(output)
        root = tree.getroot()
        assert root.tag == "document"
        # The fixture has at least one heading and one paragraph/listh
        # child element.
        assert len(list(root)) > 0

    def test_convert_parses_headings(
        self, xml_headings_md: Path, tmp_path: Path
    ):
        output = tmp_path / "headings.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_headings_md, output)

        tree = ET.parse(output)
        root = tree.getroot()
        tags = [child.tag for child in root]
        assert "h1" in tags
        assert "h2" in tags
        assert "h3" in tags

    def test_convert_parses_code_blocks(
        self, xml_code_md: Path, tmp_path: Path
    ):
        output = tmp_path / "code.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_code_md, output)

        tree = ET.parse(output)
        root = tree.getroot()
        pre_elems = root.findall("pre")
        assert len(pre_elems) == 1
        code_elem = pre_elems[0].find("code")
        assert code_elem is not None
        assert code_elem.text is not None
        assert "x = 1" in code_elem.text

    def test_convert_parses_unordered_lists(
        self, xml_list_md: Path, tmp_path: Path
    ):
        output = tmp_path / "list.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_list_md, output)

        tree = ET.parse(output)
        root = tree.getroot()
        ul_elems = root.findall("ul")
        assert len(ul_elems) == 1
        items = ul_elems[0].findall("li")
        assert [li.text for li in items] == ["alpha", "beta", "gamma"]

    def test_convert_parses_tables(
        self, xml_table_md: Path, tmp_path: Path
    ):
        output = tmp_path / "table.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_table_md, output)

        tree = ET.parse(output)
        root = tree.getroot()
        table_elems = root.findall("table")
        assert len(table_elems) == 1
        rows = table_elems[0].findall("tr")
        # 1 header + 1 data row (separator dropped)
        assert len(rows) == 2
        assert [td.text for td in rows[0].findall("td")] == ["c1", "c2"]
        assert [td.text for td in rows[1].findall("td")] == ["a", "b"]

    def test_convert_strips_inline_markdown(
        self, xml_inline_md: Path, tmp_path: Path
    ):
        output = tmp_path / "inline.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_inline_md, output)

        tree = ET.parse(output)
        root = tree.getroot()
        p = root.find("p")
        assert p is not None
        assert p.text is not None
        # The ** and * markers should be stripped, but the words remain.
        assert "**" not in p.text
        assert "*" not in p.text
        assert "bold" in p.text
        assert "italic" in p.text
        # Inline code backticks should also be removed.
        assert "`" not in p.text
        assert "code" in p.text

    def test_convert_writes_xml_declaration(
        self, xml_md: Path, tmp_path: Path
    ):
        output = tmp_path / "decl.xml"

        converter = MD2XMLConverter()
        converter.convert(xml_md, output)

        first_line = output.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == '<?xml version="1.0" encoding="UTF-8"?>'

    def test_inject_images_noop(self):
        converter = MD2XMLConverter()
        images = [{"id": "img1"}]
        applied, remaining = converter.inject_images(
            skeleton_path="ignored",
            images=images,
            output_path="ignored",
        )
        assert applied == []
        assert remaining is images
