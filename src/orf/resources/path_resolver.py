"""Path resolution and validation for ORF Phase 2 resource management."""

from pathlib import Path
from typing import Optional

from orf.error_handlers.conversion_error import ResourceManagementError
from orf.logging import get_logger

logger = get_logger("orf.resources.path_resolver")


class PathResolver:
    """Resolves and validates resource paths for multi-format output.

    Handles relative path resolution, format-specific path adjustment,
    and path validation for resource management.
    """

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        """Initialize the PathResolver.

        Args:
            base_dir: Base directory for resolving relative paths.
        """
        self._base_dir = Path(base_dir) if base_dir else None
        logger.debug("PathResolver initialized with base_dir=%s", base_dir)

    def resolve_relative(
        self, resource_path: Path | str, base_dir: Optional[Path | str] = None
    ) -> Path:
        """Resolve a potentially relative resource path to an absolute path.

        Args:
            resource_path: The resource path to resolve.
            base_dir: Optional base directory override.

        Returns:
            Resolved absolute Path object.

        Raises:
            ResourceManagementError: If path resolution fails.
        """
        resource_path = Path(resource_path)

        if resource_path.is_absolute():
            logger.debug("Path is absolute: %s", resource_path)
            return resource_path

        resolved_base = Path(base_dir) if base_dir else self._base_dir

        if not resolved_base:
            raise ResourceManagementError(
                resource_path=str(resource_path),
                operation="resolve_relative",
                reason="No base directory available to resolve relative path",
            )

        resolved = (resolved_base / resource_path).resolve()
        logger.debug(
            "Relative path resolved: %s -> %s (base=%s)",
            resource_path,
            resolved,
            resolved_base,
        )
        return resolved

    def adjust_for_format(
        self,
        resource_path: Path | str,
        format: str,
        output_dir: Optional[Path | str] = None,
    ) -> Path:
        """Adjust resource path for target format-specific output location.

        Args:
            resource_path: The resource path to adjust.
            format: Target format for output.
            output_dir: Optional format-specific output directory.

        Returns:
            Adjusted Path for the format-specific output location.

        Raises:
            ResourceManagementError: If path adjustment fails.
        """
        resource_path = Path(resource_path)
        output_base = Path(output_dir) if output_dir else self._base_dir

        if not output_base:
            raise ResourceManagementError(
                resource_path=str(resource_path),
                operation="adjust_for_format",
                reason="No output directory available for format adjustment",
            )

        format_dir = output_base / format
        adjusted = format_dir / resource_path.name
        logger.debug(
            "Path adjusted for format: %s -> %s (format=%s, output=%s)",
            resource_path,
            adjusted,
            format,
            output_base,
        )
        return adjusted

    def validate_path(
        self,
        resource_path: Path | str,
        must_exist: bool = True,
        allowed_extensions: Optional[list[str]] = None,
    ) -> bool:
        """Validate a resource path for accessibility and type.

        Args:
            resource_path: The resource path to validate.
            must_exist: Whether the path must exist on the filesystem.
            allowed_extensions: Optional list of allowed file extensions.

        Returns:
            True if path is valid, False otherwise.

        Raises:
            ResourceManagementError: If validation encounters an error.
        """
        resource_path = Path(resource_path)

        if must_exist and not resource_path.exists():
            logger.warning("Path does not exist: %s", resource_path)
            return False

        if allowed_extensions:
            ext = resource_path.suffix.lower()
            if ext not in allowed_extensions:
                logger.warning(
                    "Path extension %s not in allowed list: %s",
                    ext,
                    allowed_extensions,
                )
                return False

        logger.debug(
            "Path validated: %s (exists=%s, ext=%s)",
            resource_path,
            resource_path.exists(),
            resource_path.suffix,
        )
        return True