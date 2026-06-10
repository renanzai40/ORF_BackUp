"""Security utilities for MCP server."""

from pathlib import Path


class PathValidator:
    """Validate paths to prevent directory traversal."""

    ALLOWED_EXTENSIONS = {'.md', '.docx', '.pptx', '.xliff', '.xlf', '.xml', '.html', '.odt', '.epub'}

    @staticmethod
    def validate(input_path: str, base_dir: Path | None = None) -> tuple[bool, str]:
        """Validate a file path.

        Returns:
            (is_valid, error_message)
        """
        path = Path(input_path)

        # Check for directory traversal
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False, "Invalid path"

        # Check if path contains suspicious patterns
        if '..' in path.parts:
            return False, "Path traversal not allowed"

        if path.suffix.lower() not in PathValidator.ALLOWED_EXTENSIONS:
            return False, f"Extension '{path.suffix}' not in allowed set"

        # If base_dir provided, ensure path is within base_dir
        if base_dir:
            try:
                resolved.relative_to(base_dir.resolve())
            except ValueError:
                return False, "Path outside allowed directory"

        return True, ""