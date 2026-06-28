"""Image injection functions for the XLIFF2HTML converter."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from orf.mcp.schemas import ImagePlacement
from orf.logging import get_logger

logger = get_logger("channel.xliff2html.images")


def inject_images_into_html(
    html_path: Path | str,
    images: list[ImagePlacement],
    output_path: Path | str,
    get_image_bytes_fn: Any = None,
) -> tuple[list[ImagePlacement], list[ImagePlacement]]:
    """Inject images into HTML at specified DOM element positions.

    Args:
        html_path: Path to HTML file.
        images: List of ImagePlacement objects from OPP.
        output_path: Path to write the output HTML.
        get_image_bytes_fn: Callable to get image bytes from ImagePlacement.
                           Defaults to get_image_bytes if None.

    Returns:
        Tuple of (injected_images, orphaned_images).
    """
    html_path = Path(html_path)
    output_path = Path(output_path)

    if get_image_bytes_fn is None:
        get_image_bytes_fn = get_image_bytes

    orphaned: list[ImagePlacement] = []
    injected: list[ImagePlacement] = []

    positioned = [img for img in images if img.element_index is not None]
    unpositioned = [img for img in images if img.element_index is None]

    if unpositioned:
        for img in unpositioned:
            logger.warning(
                "Image has no element_index, appending to end: mime_type=%s",
                img.mime_type,
            )
        orphaned.extend(unpositioned)

    if not positioned:
        if images and html_path.exists():
            html_path.read_text(encoding="utf-8")
        return (injected, orphaned)

    try:
        html_content = html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read HTML for image injection: %s", e)
        orphaned.extend(images)
        return (injected, orphaned)

    soup = BeautifulSoup(html_content, "html.parser")
    img_tags = soup.find_all("img")

    img_by_idx: dict[int, list[ImagePlacement]] = {}
    for img in positioned:
        idx = img.element_index
        assert idx is not None, "positioned images must have element_index"
        if idx not in img_by_idx:
            img_by_idx[idx] = []
        img_by_idx[idx].append(img)

    for elem_idx, imgs in img_by_idx.items():
        if elem_idx < 0 or elem_idx >= len(img_tags):
            logger.warning(
                "element_index %d out of range, %d img tags available",
                elem_idx,
                len(img_tags),
            )
            orphaned.extend(imgs)
            continue

        target_tag = img_tags[elem_idx]
        for img in imgs:
            try:
                img_bytes = get_image_bytes_fn(img)
                src = create_data_uri(img_bytes, img.mime_type)
                new_tag = soup.new_tag("img", src=src)
                if img.width:
                    new_tag["width"] = img.width
                if img.height:
                    new_tag["height"] = img.height
                target_tag.insert_after(new_tag)
                target_tag = new_tag
                injected.append(img)
                logger.debug(
                    "Injected image at element %d: mime=%s",
                    elem_idx,
                    img.mime_type,
                )
            except Exception as e:
                logger.error("Failed to inject image: %s", e)
                orphaned.append(img)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(str(soup), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write HTML with images: %s", e)
        return (injected, orphaned + [img for img in positioned if img not in injected])

    if orphaned:
        logger.warning(
            "%d images could not be positioned and were not injected",
            len(orphaned),
        )

    return (injected, orphaned)


def get_image_bytes(img: ImagePlacement) -> bytes:
    """Extract image bytes from an ImagePlacement.

    Args:
        img: ImagePlacement object with data_base64 or file_path

    Returns:
        Raw image bytes

    Raises:
        ValueError: If no image data is available
    """
    if img.data_base64:
        return base64.b64decode(img.data_base64)
    if img.file_path:
        # C4 fix (defense in depth): validate file_path before reading.
        from orf.mcp.security import PathValidator

        valid, err = PathValidator.validate(img.file_path)
        if not valid:
            raise ValueError(f"file_path rejected: {err}")
        return Path(img.file_path).read_bytes()
    raise ValueError("ImagePlacement must have data_base64 or file_path")


def create_data_uri(img_bytes: bytes, mime_type: str) -> str:
    """Create a data URI from image bytes and MIME type.

    Args:
        img_bytes: Raw image bytes
        mime_type: MIME type of the image

    Returns:
        Data URI string
    """
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"
