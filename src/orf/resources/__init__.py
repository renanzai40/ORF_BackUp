"""Resource management module for ORF Phase 2.

Provides image management with MD5-based deduplication and path resolution
for multi-format document processing.
"""

from orf.resources.image_manager import ImageManager, ImageResource
from orf.resources.path_resolver import PathResolver

__all__ = [
    "ImageManager",
    "ImageResource",
    "PathResolver",
]