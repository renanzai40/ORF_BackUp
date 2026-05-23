"""H2 header-based chunked MD converter for streaming large documents."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

from orf.converters.base import ConversionResult
from orf.converters.stream_converter import StreamingConverter, StreamChunk
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger

logger = get_logger("converter.chunked_md")


class ChunkedMDConverter(StreamingConverter):
    """Streaming converter that splits MD by H2 headers to preserve section structure.

    Splits on ## header lines and merges chunks with double newlines.
    """

    def __init__(
        self,
        chunk_size: int = 64 * 1024,  # 64KB default
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        """Initialize chunked MD converter.

        Args:
            chunk_size: Maximum chunk size in bytes (default 64KB)
            manifest: OPP manifest metadata
            frontmatter: OL YAML frontmatter metadata
        """
        super().__init__(
            chunk_size=chunk_size,
            manifest=manifest,
            frontmatter=frontmatter,
        )

    @property
    def supported_format(self) -> str:
        return "MD_CHUNKED"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def _split_chunks(self, input_path: Path | str) -> list[StreamChunk]:
        """Split MD file by H2 (##) headers to preserve section structure.

        Args:
            input_path: Input MD file path

        Returns:
            List of StreamChunk objects, each containing a section
        """
        input_path = Path(input_path)
        chunks: list[StreamChunk] = []

        content = input_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        if not lines:
            return [StreamChunk(index=0, content="")]

        current_section: list[str] = []
        chunk_index = 0

        for line in lines:
            # Detect H2 header
            if line.startswith("## "):
                # Save current section if non-empty
                if current_section:
                    chunk_content = "\n".join(current_section) + "\n"
                    chunks.append(StreamChunk(index=chunk_index, content=chunk_content))
                    chunk_index += 1
                    current_section = []

            current_section.append(line)

        # Don't forget the last section
        if current_section:
            chunk_content = "\n".join(current_section) + "\n"
            chunks.append(StreamChunk(index=chunk_index, content=chunk_content))

        return chunks

    def _process_chunk(self, chunk: StreamChunk, **options: Any) -> str:
        """Pass through chunk content (actual conversion happens at channel level).

        Args:
            chunk: Input chunk to process
            **options: Processing options (unused)

        Returns:
            The chunk content unchanged
        """
        return chunk.content

    def _merge_chunks(
        self,
        chunks: list[str],
        output_path: Path | str,
    ) -> ConversionResult:
        """Merge chunks with double newlines to preserve header spacing.

        Args:
            chunks: List of processed chunk strings
            output_path: Output file path

        Returns:
            ConversionResult with success status
        """
        output_path = Path(output_path)

        if not chunks:
            output_path.write_text("", encoding="utf-8")
            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"chunk_count": 0},
            )

        # Join with double newlines to preserve section spacing
        merged_content = "\n\n".join(chunks)

        output_path.write_text(merged_content, encoding="utf-8")

        logger.debug(
            f"Merged {len(chunks)} chunks into {output_path}",
            extra=self.get_log_context(),
        )

        return ConversionResult(
            output_path=output_path,
            success=True,
            metadata={"chunk_count": len(chunks)},
        )