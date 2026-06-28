"""Image injection functions for the XLIFF2DOCX converter.

Handles inline and floating image injection, deduplication via
extent (cx/cy) matching, and ZIP manipulation for DOCX media.
"""

from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from orf.logging import get_logger
from orf.mcp.schemas import ImagePlacement

from ._ns import (
    A_NS,
    ALLOWED_RELATIVE_FROM,
    PIC_NS,
    W_NS,
    WORD_NS_MAP,
    WP_NS,
)

logger = get_logger("channel.xliff2docx.images")


def inject_images_into_docx(
    skeleton_path: Path | str,
    images: list[ImagePlacement],
    output_path: Path | str,
    skeleton_loader: Any,
    get_image_bytes_fn: Any = None,
    get_image_dimensions_fn: Any = None,
) -> tuple[list[ImagePlacement], list[ImagePlacement]]:
    """Inject images into DOCX skeleton.

    Routes each image by position type:
      - ``is_floating=True, paragraph_index=None`` → ``wp:anchor`` (page-positioned)
      - ``paragraph_index=int``                    → ``wp:inline`` (paragraph-anchored)
      - otherwise                                  → orphaned (logged)

    Args:
        skeleton_path: Path to skeleton DOCX file.
        images: List of ``ImagePlacement`` objects from OPP.
        output_path: Path to write the output DOCX.
        skeleton_loader: A ``SkeletonLoader`` instance.
        get_image_bytes_fn: Callable to get image bytes.
        get_image_dimensions_fn: Callable to get image dimensions.

    Returns:
        Tuple of (injected_images, orphaned_images).
    """
    if get_image_bytes_fn is None:
        get_image_bytes_fn = get_image_bytes
    if get_image_dimensions_fn is None:
        get_image_dimensions_fn = get_image_dimensions

    skeleton_path = Path(skeleton_path)
    output_path = Path(output_path)

    orphaned: list[ImagePlacement] = []
    injected: list[ImagePlacement] = []

    floating = [
        img for img in images
        if getattr(img, "is_floating", False) and img.paragraph_index is None
    ]
    positioned = [
        img for img in images
        if img.paragraph_index is not None and not getattr(img, "is_floating", False)
    ]
    unpositioned = [
        img for img in images
        if img.paragraph_index is None and not getattr(img, "is_floating", False)
    ]

    if unpositioned:
        for img in unpositioned:
            logger.warning(
                "Image has no paragraph_index, appending to end: mime_type=%s",
                img.mime_type,
            )
        orphaned.extend(unpositioned)

    if not positioned and not floating:
        if images:
            skeleton_loader.load_skeleton(str(skeleton_path))
            skeleton_loader.repack_docx(str(output_path))
        return (injected, orphaned)

    try:
        skeleton_data = skeleton_loader.load_skeleton(str(skeleton_path))
    except Exception as e:
        logger.error("Failed to load skeleton for image injection: %s", e)
        orphaned.extend(images)
        return (injected, orphaned)

    document_xml = skeleton_data.get("xml")
    if document_xml is None:
        logger.warning(
            "Skeleton has no 'xml' key (cross-format?). Skipping image injection."
        )
        orphaned.extend(images)
        return (injected, orphaned)
    files = skeleton_data["files"]
    namelist = list(files.keys())

    root = etree.fromstring(document_xml.encode("utf-8"))
    paragraphs = root.xpath("//w:p", namespaces=WORD_NS_MAP)

    img_by_para: dict[int, list[ImagePlacement]] = {}
    for img in positioned:
        idx = img.paragraph_index
        assert idx is not None, "positioned images must have paragraph_index"
        if idx not in img_by_para:
            img_by_para[idx] = []
        img_by_para[idx].append(img)

    for para_idx, imgs in img_by_para.items():
        if para_idx < 0 or para_idx >= len(paragraphs):
            logger.warning(
                "paragraph_index %d out of range, %d paragraphs available",
                para_idx,
                len(paragraphs),
            )
            orphaned.extend(imgs)
            continue

        para = paragraphs[para_idx]
        next_r = None
        for child in para:
            if child.tag == f"{{{W_NS}}}r":
                next_r = child
                break

        for img in imgs:
            try:
                img_bytes = get_image_bytes_fn(img)
                width, height = get_image_dimensions_fn(img, img_bytes)

                # Dedup (TURNKEY-IMG-01): skip inline drawings already in the skeleton
                if paragraph_already_has_drawing(root, width, height):
                    logger.debug(
                        "Skipping duplicate inline image at paragraph %d "
                        "with cx=%d, cy=%d (already present in skeleton)",
                        para_idx, width, height,
                    )
                    injected.append(img)
                    continue

                rId = add_image_to_zip(img_bytes, img.mime_type, files, namelist)
                drawing_xml = create_drawing_xml(rId, width, height)
                drawing_elem = etree.fromstring(drawing_xml)

                if next_r is not None:
                    insert_pos = list(para).index(next_r)
                    para.insert(insert_pos, drawing_elem)
                else:
                    para.append(drawing_elem)

                injected.append(img)
                logger.debug(
                    "Injected image at paragraph %d: rId=%s, mime=%s",
                    para_idx,
                    rId,
                    img.mime_type,
                )
            except Exception as e:
                logger.error("Failed to inject image: %s", e)
                orphaned.append(img)

    for img in floating:
        try:
            if inject_floating_image(root, img, files, namelist, get_image_bytes_fn, get_image_dimensions_fn):
                injected.append(img)
                logger.debug(
                    "Injected floating image: rId=embedded, H=%d EMU, V=%d EMU",
                    img.wp_anchor_h,
                    img.wp_anchor_v,
                )
            else:
                orphaned.append(img)
        except Exception as e:
            logger.error("Failed to inject floating image: %s", e)
            orphaned.append(img)

    new_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + etree.tostring(root, encoding="unicode")
    )

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                ct = skeleton_loader.compress_types.get(name, zipfile.ZIP_STORED)
                data_to_write = data if name != "word/document.xml" else new_xml.encode("utf-8")
                if ct == zipfile.ZIP_STORED:
                    zf.writestr(name, data_to_write, compress_type=zipfile.ZIP_STORED)
                else:
                    zf.writestr(name, data_to_write)
    except Exception as e:
        logger.error("Failed to repack DOCX with images: %s", e)
        return (injected, orphaned + [img for img in positioned if img not in injected])

    if orphaned:
        logger.warning(
            "%d images could not be positioned and were not injected",
            len(orphaned),
        )

    return (injected, orphaned)


def paragraph_already_has_drawing(
    root: etree._Element,
    cx: int,
    cy: int,
) -> bool:
    """True iff ``root`` already contains a ``<w:drawing>`` with matching extent.

    Document-wide (not paragraph-local) extent match because OPP's
    ``paragraph_index`` doesn't reliably match ORF's ``//w:p`` enumeration
    (off-by-one observed in practice).

    Mirrors the floating-image dedup at inject_floating_image: that one
    iterates ``wp:anchor`` positionH/V; this one iterates ``wp:extent`` cx/cy.
    """
    for extent in root.iter(f"{{{WP_NS}}}extent"):
        try:
            existing_cx = int(extent.get("cx", "-1"))
            existing_cy = int(extent.get("cy", "-1"))
        except (ValueError, TypeError):
            continue
        if existing_cx == cx and existing_cy == cy:
            return True
    return False


def inject_floating_image(
    root: etree._Element,
    img: ImagePlacement,
    files: dict[str, bytes],
    namelist: list[str],
    get_image_bytes_fn: Any,
    get_image_dimensions_fn: Any,
) -> bool:
    """Inject a single floating image as a ``w:drawing > wp:anchor``.

    Floating images are page-positioned via ``wp:posOffset``, attached to
    the first ``w:p`` in the body (Word treats anchors attached at the body
    level as page-relative). H/V coordinates are read from the image record.
    """
    img_bytes = get_image_bytes_fn(img)
    rId = add_image_to_zip(img_bytes, img.mime_type, files, namelist)
    width, height = get_image_dimensions_fn(img, img_bytes)

    anchor_xml = create_floating_anchor_xml(
        rId=rId,
        cx=width,
        cy=height,
        pos_h=img.wp_anchor_h,
        pos_v=img.wp_anchor_v,
        relative_h=getattr(img, "wp_anchor_relative_h", "page") or "page",
        relative_v=getattr(img, "wp_anchor_relative_v", "page") or "page",
    )
    anchor_elem = etree.fromstring(anchor_xml)

    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        return False

    first_para = body.find(f"{{{W_NS}}}p")
    if first_para is None:
        return False

    first_para.insert(0, anchor_elem)
    return True


def create_floating_anchor_xml(
    rId: str,
    cx: int,
    cy: int,
    pos_h: int,
    pos_v: int,
    relative_h: str = "page",
    relative_v: str = "page",
) -> str:
    """Build a ``w:drawing > wp:anchor`` element string for a floating image.

    C13 fix: ``relative_h``/``relative_v`` are validated against the OOXML
    allowlist and serialized via ``etree.SubElement`` + ``.set()`` (which
    XML-escapes attribute values) instead of f-string interpolation.
    """
    # Validate against allowlist BEFORE serializing
    if relative_h not in ALLOWED_RELATIVE_FROM:
        raise ValueError(
            f"relative_h {relative_h!r} is not in the OOXML allowlist "
            f"{sorted(ALLOWED_RELATIVE_FROM)}"
        )
    if relative_v not in ALLOWED_RELATIVE_FROM:
        raise ValueError(
            f"relative_v {relative_v!r} is not in the OOXML allowlist "
            f"{sorted(ALLOWED_RELATIVE_FROM)}"
        )

    # Numeric coercion for pos_h/pos_v
    pos_h_int = int(pos_h)
    pos_v_int = int(pos_v)

    NSMAP = {
        "w": W_NS,
        "wp": WP_NS,
        "a": A_NS,
        "pic": PIC_NS,
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    drawing = etree.Element(f"{{{W_NS}}}drawing", nsmap=NSMAP)
    anchor = etree.SubElement(
        drawing,
        f"{{{WP_NS}}}anchor",
        attrib={
            "distT": "0",
            "distB": "0",
            "distL": "114300",
            "distR": "114300",
            "simplePos": "0",
            "relativeHeight": "251659264",
            "behindDoc": "0",
            "locked": "0",
            "layoutInCell": "1",
            "allowOverlap": "1",
        },
    )
    etree.SubElement(anchor, f"{{{WP_NS}}}simplePos", x="0", y="0")
    pos_h_elem = etree.SubElement(
        anchor, f"{{{WP_NS}}}positionH", relativeFrom=relative_h,
    )
    etree.SubElement(pos_h_elem, f"{{{WP_NS}}}posOffset").text = str(pos_h_int)
    pos_v_elem = etree.SubElement(
        anchor, f"{{{WP_NS}}}positionV", relativeFrom=relative_v,
    )
    etree.SubElement(pos_v_elem, f"{{{WP_NS}}}posOffset").text = str(pos_v_int)
    etree.SubElement(anchor, f"{{{WP_NS}}}extent", cx=str(cx), cy=str(cy))
    etree.SubElement(anchor, f"{{{WP_NS}}}effectExtent", l="0", t="0", r="0", b="0")
    etree.SubElement(anchor, f"{{{WP_NS}}}wrapNone")
    etree.SubElement(anchor, f"{{{WP_NS}}}docPr", id="1", name="Picture")
    cNvGraphicFramePr = etree.SubElement(anchor, f"{{{WP_NS}}}cNvGraphicFramePr")
    etree.SubElement(
        cNvGraphicFramePr, f"{{{A_NS}}}graphicFrameLocks", noChangeAspect="1"
    )
    graphic = etree.SubElement(anchor, f"{{{A_NS}}}graphic")
    graphicData = etree.SubElement(
        graphic, f"{{{A_NS}}}graphicData",
        uri="http://schemas.openxmlformats.org/drawingml/2006/picture",
    )
    pic_pic = etree.SubElement(graphicData, f"{{{PIC_NS}}}pic")
    nvPicPr = etree.SubElement(pic_pic, f"{{{PIC_NS}}}nvPicPr")
    etree.SubElement(nvPicPr, f"{{{PIC_NS}}}cNvPr", id="1", name="image")
    etree.SubElement(nvPicPr, f"{{{PIC_NS}}}cNvPicPr")
    blipFill = etree.SubElement(pic_pic, f"{{{PIC_NS}}}blipFill")
    etree.SubElement(
        blipFill, f"{{{A_NS}}}blip",
        attrib={"{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed": rId},
    )
    stretch = etree.SubElement(blipFill, f"{{{A_NS}}}stretch")
    etree.SubElement(stretch, f"{{{A_NS}}}fillRect")
    spPr = etree.SubElement(pic_pic, f"{{{PIC_NS}}}spPr")
    xfrm = etree.SubElement(spPr, f"{{{A_NS}}}xfrm")
    etree.SubElement(xfrm, f"{{{A_NS}}}off", x="0", y="0")
    etree.SubElement(xfrm, f"{{{A_NS}}}ext", cx=str(cx), cy=str(cy))
    prstGeom = etree.SubElement(spPr, f"{{{A_NS}}}prstGeom", prst="rect")
    etree.SubElement(prstGeom, f"{{{A_NS}}}avLst")

    return etree.tostring(drawing, encoding="unicode")


def get_image_bytes(img: ImagePlacement) -> bytes:
    """Extract image bytes from an ImagePlacement.

    Args:
        img: ImagePlacement with ``data_base64`` or ``file_path``.

    Returns:
        Raw image bytes.

    Raises:
        ValueError: If neither ``data_base64`` nor ``file_path`` is set.
    """
    if img.data_base64:
        return base64.b64decode(img.data_base64)
    if img.file_path:
        # C4 fix (defense in depth): validate file_path before reading
        from orf.mcp.security import PathValidator
        valid, err = PathValidator.validate(img.file_path)
        if not valid:
            raise ValueError(f"file_path rejected: {err}")
        return Path(img.file_path).read_bytes()
    raise ValueError("ImagePlacement must have data_base64 or file_path")


def get_image_dimensions(
    img: ImagePlacement,
    img_bytes: bytes,
) -> tuple[int, int]:
    """Get image dimensions from ImagePlacement metadata or via PIL.

    Args:
        img: ImagePlacement (may have ``width``/``height`` set).
        img_bytes: Raw image bytes for PIL fallback.

    Returns:
        Tuple of (width, height) in EMU or pixels.
    """
    if img.width is not None and img.height is not None:
        return (img.width, img.height)

    try:
        from PIL import Image
        from io import BytesIO

        img_obj = Image.open(BytesIO(img_bytes))
        w, h = img_obj.size
        return (w, h)
    except (OSError, ValueError):
        logger.exception("Failed to get image dimensions, using default 200000x150000")
        return (200000, 150000)


def add_image_to_zip(
    img_bytes: bytes,
    mime_type: str,
    files: dict[str, bytes],
    namelist: list[str],
) -> str:
    """Add an image to the DOCX ZIP's ``word/media/`` and update relationships.

    Deduplicates: if the same bytes already exist in ``word/media/``, reuses
    the existing relationship ID.

    Args:
        img_bytes: Raw image data.
        mime_type: MIME type (e.g. ``image/png``).
        files: Mutable dict of ZIP member name → bytes.
        namelist: Mutable list of ZIP member names.

    Returns:
        Relationship ID (e.g. ``rId5``) for the image.
    """
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/webp": ".webp",
    }
    ext = ext_map.get(mime_type, ".png")
    md5_hash = hashlib.md5(img_bytes).hexdigest()
    dedup_name = f"image_{md5_hash[:8]}{ext}"

    existing_rid = None
    for name, data in files.items():
        if name.startswith("word/media/") and data == img_bytes:
            existing_rid = name
            break

    if existing_rid:
        rels_file = files.get("word/_rels/document.xml.rels")
        if rels_file:
            try:
                rels_root = etree.fromstring(rels_file)
                media_filename = existing_rid.replace("word/media/", "")
                for rel in rels_root:
                    target = rel.get("Target", "")
                    if target.replace("\\", "/").endswith(media_filename):
                        return rel.get("Id")
            except Exception:
                logger.debug("Failed to extract media filename from existing rels", exc_info=True)
        return existing_rid.replace("word/media/", "rId")

    media_name = f"word/media/{dedup_name}"
    files[media_name] = img_bytes
    namelist.append(media_name)

    rels_name = "word/_rels/document.xml.rels"
    if rels_name in files:
        rels_xml = files[rels_name].decode("utf-8")
        root = etree.fromstring(rels_xml.encode("utf-8"))

        max_rid = 0
        for rel in root.xpath("//*"):
            rid = rel.get("Id", "")
            if rid.startswith("rId"):
                try:
                    num = int(rid[3:])
                    if num > max_rid:
                        max_rid = num
                except ValueError:
                    pass

        new_rid = f"rId{max_rid + 1}"
        rels_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        new_rel = etree.SubElement(root, f"{{{rels_ns}}}Relationship")
        new_rel.set("Id", new_rid)
        new_rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        new_rel.set("Target", f"media/{dedup_name}")

        files[rels_name] = etree.tostring(root, encoding="unicode").encode("utf-8")

        return new_rid
    else:
        return "rId1"


def create_drawing_xml(
    rId: str,
    cx: int,
    cy: int,
) -> str:
    """Create a ``<w:drawing>`` XML string with ``<wp:inline>`` for an image.

    Args:
        rId: Relationship ID for the image.
        cx: Width in EMU.
        cy: Height in EMU.

    Returns:
        XML string for the drawing element.
    """
    drawing = f'''
<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
           xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
           xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
             distT="0" distB="0" distL="0" distR="0">
    <wp:extent cx="{cx}" cy="{cy}"/>
    <wp:docPr id="1" name="Picture"/>
    <wp:cNvGraphicFramePr>
      <a:graphicFrameLocks noChangeAspect="1"/>
    </wp:cNvGraphicFramePr>
    <a:graphic>
      <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <pic:pic>
          <pic:nvPicPr>
            <pic:cNvPr id="1" name="image"/>
            <pic:cNvPicPr/>
          </pic:nvPicPr>
          <pic:blipFill>
            <a:blip r:embed="{rId}"/>
            <a:stretch>
              <a:fillRect/>
            </a:stretch>
          </pic:blipFill>
          <pic:spPr>
            <a:xfrm>
              <a:off x="0" y="0"/>
              <a:ext cx="{cx}" cy="{cy}"/>
            </a:xfrm>
            <a:prstGeom prst="rect">
              <a:avLst/>
            </a:prstGeom>
          </pic:spPr>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>'''
    return drawing
