"""Image resource management with MD5-based deduplication for ORF Phase 2."""

import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from orf.error_handlers.conversion_error import ResourceManagementError
from orf.logging import get_logger

logger = get_logger("orf.resources.image_manager")


@dataclass
class ImageResource:
    """Represents an image resource with deduplication metadata.

    Attributes:
        original_path: Original path to the image file.
        md5: MD5 hash of the image content.
        dedup_name: Deduplication name using MD5 prefix (e.g., image_a1b2c3d4.png).
        formats: Set of formats this image is used in.
        path_mappings: Mapping from format to resolved output path.
    """

    original_path: str
    md5: str
    dedup_name: str
    formats: set[str] = field(default_factory=set)
    path_mappings: dict[str, str] = field(default_factory=dict)


class ImageManager:
    """Thread-safe image manager with MD5-based deduplication.

    Manages image resources across multiple formats, ensuring duplicate images
    are detected and unified based on content hash.
    """

    def __init__(self, output_dir: Optional[Path | str] = None) -> None:
        """Initialize the ImageManager.

        Args:
            output_dir: Base output directory for processed images.
        """
        self._images: dict[str, ImageResource] = {}
        self._lock = threading.Lock()
        self._output_dir = Path(output_dir) if output_dir else None
        logger.debug("ImageManager initialized with output_dir=%s", output_dir)

    def register_image(
        self,
        image_path: Path | str,
        format: str,
    ) -> ImageResource:
        """Register an image with MD5-based deduplication.

        Args:
            image_path: Path to the image file.
            format: Target format for the image.

        Returns:
            ImageResource for the registered image.

        Raises:
            ResourceManagementError: If image cannot be read or processed.
        """
        image_path = Path(image_path)

        try:
            content = image_path.read_bytes()
        except OSError as e:
            raise ResourceManagementError(
                resource_path=str(image_path),
                operation="register_image",
                reason=f"Cannot read image file: {e}",
            ) from e

        md5_hash = hashlib.md5(content).hexdigest()
        ext = image_path.suffix.lower()

        with self._lock:
            if md5_hash in self._images:
                resource = self._images[md5_hash]
                resource.formats.add(format)
                logger.debug(
                    "Image deduplicated: %s -> %s (format=%s)",
                    image_path.name,
                    resource.dedup_name,
                    format,
                )
                return resource

            dedup_name = f"image_{md5_hash[:8]}{ext}"
            resource = ImageResource(
                original_path=str(image_path),
                md5=md5_hash,
                dedup_name=dedup_name,
                formats={format},
                path_mappings={},
            )
            self._images[md5_hash] = resource
            logger.debug(
                "Image registered: %s -> %s (md5=%s, format=%s)",
                image_path.name,
                dedup_name,
                md5_hash[:8],
                format,
            )
            return resource

    def get_image(self, md5_hash: str) -> Optional[ImageResource]:
        """Retrieve an image resource by MD5 hash.

        Args:
            md5_hash: MD5 hash of the image.

        Returns:
            ImageResource if found, None otherwise.
        """
        with self._lock:
            return self._images.get(md5_hash)

    def get_dedup_name(self, md5_hash: str) -> Optional[str]:
        """Get the deduplication name for an image.

        Args:
            md5_hash: MD5 hash of the image.

        Returns:
            Deduplication name if found, None otherwise.
        """
        with self._lock:
            resource = self._images.get(md5_hash)
            return resource.dedup_name if resource else None

    def update_path_mapping(
        self, md5_hash: str, format: str, output_path: Path | str
    ) -> None:
        """Update the output path mapping for an image.

        Args:
            md5_hash: MD5 hash of the image.
            format: Target format.
            output_path: Resolved output path for this format.
        """
        with self._lock:
            resource = self._images.get(md5_hash)
            if resource:
                resource.path_mappings[format] = str(output_path)
                logger.debug(
                    "Path mapping updated: %s[%s] -> %s",
                    resource.dedup_name,
                    format,
                    output_path,
                )

    def list_images(self) -> list[ImageResource]:
        """List all registered image resources.

        Returns:
            List of all ImageResource objects.
        """
        with self._lock:
            return list(self._images.values())

    def clear(self) -> None:
        """Clear all registered images."""
        with self._lock:
            self._images.clear()
            logger.debug("ImageManager cleared")