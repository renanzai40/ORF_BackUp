"""MCP Server configuration."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class MCPConfig:
    """Configuration for ORF MCP Server."""

    host: str = "127.0.0.1"
    port: int = 8765
    max_file_size_mb: int = 100
    timeout_seconds: int = 30
    allowed_formats: Optional[list[str]] = None

    def __post_init__(self) -> None:
        if self.allowed_formats is None:
            self.allowed_formats = [
                "docx",
                "odt",
                "epub",
                "html",
                "rtf",
                "pdf",
                "csv",
                "json",
                "xlsx",
                "xml",
                "ipynb",
                "eml",
                "msg",
                "pptx",
            ]