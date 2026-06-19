"""Skeleton loader for DOCX/OOXML documents."""

import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class SkeletonLoader:
    """Loader for DOCX skeleton documents.

    Loads a DOCX file (ZIP), extracts word/document.xml,
    and provides helpers for paragraph manipulation and repacking.
    """

    @staticmethod
    def _validate_zip_entry_name(name: str) -> None:
        """Reject ZIP entries that could escape the extraction directory (zip-slip).

        Raises ValueError if the entry name is an absolute path or contains
        parent-directory references (``..``).
        """
        # Reject absolute paths (POSIX /, Windows \\, or C:)
        if name.startswith(("/", "\\")) or (len(name) >= 2 and name[1] == ":"):
            raise ValueError(
                f"Skipped unsafe skeleton entry '{name}': absolute paths not allowed"
            )
        # Reject parent-directory references
        parts = name.replace("\\", "/").split("/")
        if any(part == ".." for part in parts):
            raise ValueError(
                f"Skipped unsafe skeleton entry '{name}': parent-directory reference (..) not allowed"
            )

    def __init__(self) -> None:
        self.xml: str | None = None
        self.files: dict[str, Any] = {}
        self.compress_types: dict[str, int] = {}
        self.bytes: bytes = b""

    def load_skeleton(self, path: str, max_file_size_mb: int | None = None) -> dict[str, Any]:
        """Load a DOCX file and extract its contents.

        Args:
            path: Path to the DOCX file.
            max_file_size_mb: Maximum allowed file size in MB. Raises ValueError if exceeded.

        Returns:
            dict with keys: xml (str), files (dict), bytes (bytes)
        """
        self.files = {}
        self.compress_types = {}
        self.xml = None
        self.bytes = b""

        if max_file_size_mb is not None:
            file_size_mb = Path(path).stat().st_size / (1024 * 1024)
            if file_size_mb > max_file_size_mb:
                raise ValueError(
                    f"File size ({file_size_mb:.1f} MB) exceeds limit of {max_file_size_mb} MB"
                )

        with zipfile.ZipFile(path, "r") as zf:
            # Validate every entry name BEFORE reading (zip-slip prevention)
            for name in zf.namelist():
                self._validate_zip_entry_name(name)
            # Read entire ZIP into memory
            self.bytes = zf.read(zf.namelist()[0])  # Read first file as representative
            for name in zf.namelist():
                self.files[name] = zf.read(name)
                self.compress_types[name] = zf.getinfo(name).compress_type

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
        return root.xpath(  # type: ignore[no-any-return]
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

        Preserves the original compression method for each file (e.g. media files
        are typically STORED, not DEFLATED). Some Windows preview handlers reject
        DEFLATE-compressed media inside OOXML containers.

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

        doc_compress_type = self.compress_types.get(
            "word/document.xml", zipfile.ZIP_STORED
        )

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in self.files:
                data = self.files[name] if name != "word/document.xml" else xml_bytes
                ct = self.compress_types.get(name, zipfile.ZIP_STORED)
                if ct == zipfile.ZIP_STORED:
                    zf.writestr(name, data, compress_type=zipfile.ZIP_STORED)
                else:
                    zf.writestr(name, data)