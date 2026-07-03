"""Path validation with directory allowlist and file size limits."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# System directories that should never be accessed
SYSTEM_DIRS: set = {
    '/etc',
    '/usr',
    '/var',
    '/System',
    '/Library',
    r'/C:/Windows',
    r'C:\Windows',
}

# Blocked file extensions (executables and scripts)
BLOCKED_EXTENSIONS: set = {
    '.exe',
    '.bat',
    '.cmd',
    '.sh',
    '.ps1',
    '.vbs',
    '.js',
}


@dataclass
class ValidationResult:
    """Result of path validation.

    Attributes:
        success: True if path passed all validation checks.
        error: Error message if validation failed, None otherwise.
        resolved_path: The resolved Path object if successful, None otherwise.
    """
    success: bool
    error: Optional[str] = None
    resolved_path: Optional[Path] = None


class PathValidator:
    """Validates file paths against security rules.

    Validates that:
    - Path doesn't contain traversal components (..)
    - Path resolves to an allowed directory
    - Path is not a symlink pointing outside allowed directories
    - Path doesn't target system directories
    - File has allowed extension (document whitelist)
    - File extension is not blocked (executable blacklist)
    - File size is within limit
    - File exists and is accessible

    Args:
        allowed_directories: List of root directories that are allowed to access.
        max_file_size_bytes: Maximum allowed file size in bytes (default: 100MB).
    """

    # E2E-80: extended with all the output formats ORF's apply-md
    # advertises support for. Previously the validator rejected output
    # paths like result.csv or result.xlsx even though ORF supports them.
    ALLOWED_EXTENSIONS = {
        '.md', '.docx', '.pptx', '.xliff', '.xlf', '.xml', '.html', '.odt', '.epub', '.zip',
        '.csv', '.tsv', '.xlsx', '.json', '.ipynb', '.eml', '.msg', '.srt', '.icml', '.rtf',
        '.pdf',
    }

    def __init__(
        self,
        allowed_directories: List[Path],
        max_file_size_bytes: int = 100_000_000,
    ):
        self.allowed_directories = [Path(d).resolve() for d in allowed_directories]
        self.max_file_size_bytes = max_file_size_bytes

        # P2-T4: MCP_ALLOWED_EXTENSIONS env var overrides the default set
        custom_exts = os.environ.get("MCP_ALLOWED_EXTENSIONS")
        if custom_exts:
            self.ALLOWED_EXTENSIONS = {
                ext.strip() if ext.strip().startswith(".") else f".{ext.strip()}"
                for ext in custom_exts.split(",")
                if ext.strip()
            }

    def validate_path(self, path: str, allow_missing: bool = False) -> ValidationResult:
        """Validate a file path against security rules.

        Args:
            path: The path string to validate.
            allow_missing: If True, skip the existence check (for output paths).
                          If False (default), file must exist and be readable.

        Returns:
            ValidationResult with success=True if valid, or success=False with error message.
        """
        try:
            input_path = Path(path)
        except (ValueError, OSError) as e:
            return ValidationResult(
                success=False,
                error=f"Invalid path format: {e}",
            )

        # Check for path traversal attempts
        if '..' in input_path.parts:
            return ValidationResult(
                success=False,
                error="Path traversal detected (.. components are not allowed)",
            )

        # Resolve the path (follows symlinks)
        try:
            resolved = input_path.resolve()
        except (ValueError, OSError) as e:
            return ValidationResult(
                success=False,
                error=f"Cannot resolve path: {e}",
            )

        # Check if path points to a system directory
        for sys_dir in SYSTEM_DIRS:
            sys_path = Path(sys_dir)
            try:
                resolved_parts = resolved.parts
                sys_parts = sys_path.parts
                if len(resolved_parts) >= len(sys_parts):
                    if all(
                        a == b for a, b in zip(resolved_parts[:len(sys_parts)], sys_parts)
                    ):
                        return ValidationResult(
                            success=False,
                            error=f"Access to system directory not allowed: {sys_dir}",
                        )
            except ValueError:
                pass

        # Check if resolved path is within allowed directories
        is_in_allowed = False
        for allowed_dir in self.allowed_directories:
            try:
                resolved.relative_to(allowed_dir)
                is_in_allowed = True
                break
            except ValueError:
                pass

        if not is_in_allowed:
            return ValidationResult(
                success=False,
                error=f"Path is not within allowed directories: {', '.join(str(d) for d in self.allowed_directories)}",
            )

        # Check if path is a symlink pointing outside allowed directories
        if input_path.is_symlink():
            try:
                link_target = input_path.resolve()
                link_in_allowed = False
                for allowed_dir in self.allowed_directories:
                    try:
                        link_target.relative_to(allowed_dir)
                        link_in_allowed = True
                        break
                    except ValueError:
                        pass
                if not link_in_allowed:
                    return ValidationResult(
                        success=False,
                        error="Symlink points outside allowed directories",
                    )
            except (ValueError, OSError):
                return ValidationResult(
                    success=False,
                    error="Symlink target is not accessible",
                )

        # Check blocked extensions
        if input_path.suffix.lower() in BLOCKED_EXTENSIONS:
            return ValidationResult(
                success=False,
                error=f"File extension '{input_path.suffix}' is blocked",
            )

        # Check allowed extensions (document whitelist)
        if input_path.suffix.lower() not in self.ALLOWED_EXTENSIONS:
            # Directories have no extension; skip extension check for directories
            if resolved.is_dir():
                return ValidationResult(success=True, resolved_path=resolved)
            return ValidationResult(
                success=False,
                error=f"Extension '{input_path.suffix}' not in allowed set",
            )

        if not resolved.exists():
            if allow_missing:
                return ValidationResult(success=True, resolved_path=resolved)
            return ValidationResult(
                success=False,
                error="File does not exist",
            )

        # Check if it's a file (not a directory)
        if not resolved.is_file():
            return ValidationResult(
                success=False,
                error="Path must be a file, not a directory",
            )

        # Check file size
        try:
            file_size = resolved.stat().st_size
            if file_size > self.max_file_size_bytes:
                return ValidationResult(
                    success=False,
                    error=f"File size ({file_size} bytes) exceeds limit of {self.max_file_size_bytes} bytes",
                )
        except OSError as e:
            return ValidationResult(
                success=False,
                error=f"Cannot access file to check size: {e}",
            )

        return ValidationResult(
            success=True,
            resolved_path=resolved,
        )

    @staticmethod
    def validate(input_path: str, base_dir: Optional[Path] = None) -> Tuple[bool, str]:
        """[Legacy] Static path validation for backward compatibility.

        This is a simplified wrapper that checks path traversal and allowed
        extensions only. For full validation (directory containment, system
        dir blocking, symlink checks, file size limits), use the instance
        method ``validate_path()`` via ``PathValidator(allowed_directories=...).validate_path(path)``.

        Returns:
            (is_valid, error_message) tuple matching the original API.
        """
        path = Path(input_path)

        # Check for directory traversal
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False, "Invalid path"

        if '..' in path.parts:
            return False, "Path traversal not allowed"

        if path.suffix.lower() not in PathValidator.ALLOWED_EXTENSIONS:
            return False, f"Extension '{path.suffix}' not in allowed set"

        if base_dir:
            try:
                resolved.relative_to(base_dir.resolve())
            except ValueError:
                return False, "Path outside allowed directory"

        return True, ""
