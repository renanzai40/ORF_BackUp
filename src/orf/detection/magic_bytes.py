"""Magic bytes signatures for binary format detection.

Maps format names to their binary file signatures (magic bytes).
Also provides MIME type mapping and ZIP format disambiguation.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

# Magic bytes signatures: format name -> magic bytes prefix
MAGIC_SIGNATURES: dict[str, bytes] = {
    "PDF": b"%PDF",
    "DOCX": b"PK\x03\x04",
    "PPTX": b"PK\x03\x04",
    "ODT": b"PK\x03\x04",
    "EPUB": b"PK\x03\x04",
    "RTF": b"{\\rtf",
    "HTML": b"<!DOCTYPE",
}

_ZIP_MAGIC = b"PK\x03\x04"


def _disambiguate_zip_format(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if "word/document.xml" in names:
                return "docx"
            if "ppt/presentation.xml" in names:
                return "pptx"
            if "xl/workbook.xml" in names:
                return "xlsx"
            if "META-INF/container.xml" in names:
                if any(n.startswith("OEBPS/") for n in names):
                    return "epub"
                return "odt"
            if "content.xml" in names:
                return "odt"
    except (zipfile.BadZipFile, FileNotFoundError, PermissionError):
        pass
    return "zip/unknown"


# MIME type mapping: format name -> MIME type string
MIME_TYPES: dict[str, str] = {
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "PPTX": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ODT": "application/vnd.oasis.opendocument.text",
    "EPUB": "application/epub+zip",
    "RTF": "application/rtf",
    "HTML": "text/html",
    "MD": "text/markdown",
}