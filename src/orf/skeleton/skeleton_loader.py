"""Skeleton loader for DOCX/OOXML documents."""

import zipfile
from typing import Any

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class SkeletonLoader:
    """Loader for DOCX skeleton documents.

    Loads a DOCX file (ZIP), extracts word/document.xml,
    and provides helpers for paragraph manipulation and repacking.
    """

    def __init__(self) -> None:
        self.xml: str | None = None
        self.files: dict[str, Any] = {}
        self.bytes: bytes = b""

    def load_skeleton(self, path: str) -> dict[str, Any]:
        """Load a DOCX file and extract its contents.

        Args:
            path: Path to the DOCX file.

        Returns:
            dict with keys: xml (str), files (dict), bytes (bytes)
        """
        self.files = {}
        self.xml = None
        self.bytes = b""

        with zipfile.ZipFile(path, "r") as zf:
            # Read entire ZIP into memory
            self.bytes = zf.read(zf.namelist()[0])  # Read first file as representative
            for name in zf.namelist():
                self.files[name] = zf.read(name)

        if "word/document.xml" in self.files:
            self.xml = self.files["word/document.xml"].decode("utf-8")

        return {"xml": self.xml, "files": self.files, "bytes": self.bytes}

    def extract_document_xml(self) -> str:
        """Extract word/document.xml as a string.

        Returns:
            The document.xml content as a string.
        """
        if self.xml is None:
            raise ValueError("No document.xml loaded. Call load_skeleton first.")
        return self.xml

    def find_paragraphs(self) -> list[Any]:
        """Find all <w:p> elements in document order.

        Returns:
            List of <w:p> element nodes.
        """
        if self.xml is None:
            raise ValueError("No XML loaded. Call load_skeleton first.")

        root = etree.fromstring(self.xml.encode("utf-8"))
        return root.xpath(
            "//w:p",
            namespaces={"w": W_NS},
        )

    def backfill_plain(self, paragraph_index: int, text: str) -> None:
        """Replace text content at the given paragraph index.

        Args:
            paragraph_index: Zero-based index of the paragraph.
            text: Replacement text string.
        """
        if self.xml is None:
            raise ValueError("No XML loaded. Call load_skeleton first.")

        root = etree.fromstring(self.xml.encode("utf-8"))
        paragraphs = root.xpath(
            "//w:p",
            namespaces={"w": W_NS},
        )

        if paragraph_index < 0 or paragraph_index >= len(paragraphs):
            raise IndexError(
                f"paragraph_index {paragraph_index} out of range "
                f"(found {len(paragraphs)} paragraphs)"
            )

        p = paragraphs[paragraph_index]

        for t in p.xpath(".//w:t", namespaces={"w": W_NS}):
            t.text = ""

        first_t = p.xpath(".//w:t", namespaces={"w": W_NS})
        if first_t:
            first_t[0].text = text
        else:
            r = etree.SubElement(p, f"{{{W_NS}}}r")
            t = etree.SubElement(r, f"{{{W_NS}}}t")
            t.text = text

        self.xml = etree.tostring(root, encoding="unicode", xml_declaration=True)

    def repack_docx(self, output_path: str, modified_xml: str | None = None) -> None:
        """Repack modified XML into a new DOCX file.

        Args:
            output_path: Path to write the new DOCX.
            modified_xml: XML string to write; if None, uses self.xml.
        """
        if modified_xml is not None:
            xml_bytes = modified_xml.encode("utf-8")
        elif self.xml is not None:
            xml_bytes = self.xml.encode("utf-8")
        else:
            raise ValueError("No XML to repack. Call load_skeleton first.")

        files_copy = dict(self.files)
        if "word/document.xml" in files_copy:
            files_copy["word/document.xml"] = xml_bytes

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files_copy.items():
                zf.writestr(name, data)