"""Markdown to DOCX conversion channel using Pandoc."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.parsers.manifest import Manifest
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2docx")

IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\((data:image/([^;]+);base64,([^)]+))\)')
IMAGE_REF_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
OLIMG_PATTERN = re.compile(r'OLIMG\d+')


class MD2DOCXConverter(BaseConverter):
    """Markdown to DOCX converter using Pandoc."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
        reference_docx: Optional[Path | str] = None,
    ) -> None:
        super().__init__(manifest, frontmatter)
        self.reference_docx = Path(reference_docx) if reference_docx else None

    @property
    def supported_format(self) -> str:
        return "DOCX"

    def validate_input(self, input_path: Path | str) -> bool:
        input_path = Path(input_path)
        return input_path.exists() and input_path.suffix.lower() == ".md"

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        input_path = Path(input_path)
        output_path = Path(output_path)
        opts = options or ConverterOptions()

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        temp_dir = None
        md_path = input_path

        if opts.separate_images and opts.images_dir:
            images_dir = Path(opts.images_dir)
            md_path, _ = self._extract_images_separately(
                input_path, output_path, images_dir
            )
            logger.info(f"Separated images to {images_dir}, stripped MD at {md_path}")
        else:
            base64_images = self._find_base64_images(input_path)
            if base64_images:
                md_path, temp_dir = self._preprocess_md_images(input_path)
                logger.info(f"Extracted {len(base64_images)} base64 images to temp directory")

        # text-only mode: strip all image references and OLIMG placeholders
        # so pandoc produces a clean text-only DOCX.
        if opts.text_only:
            raw = md_path.read_text(encoding="utf-8")
            stripped = OLIMG_PATTERN.sub("", raw)
            stripped = IMAGE_REF_PATTERN.sub("", stripped)
            if stripped != raw:
                text_only_path = md_path.parent / f"{md_path.stem}_textonly{md_path.suffix}"
                text_only_path.write_text(stripped.strip(), encoding="utf-8")
                md_path = text_only_path
                logger.info(
                    "Text-only mode: stripped %d chars of image references",
                    len(raw) - len(stripped),
                )

        cmd = [
            "pandoc",
            str(md_path),
            "-o", str(output_path),
            "--to", "docx",
            "--from", "markdown-smart",
        ]

        template = opts.template or self.reference_docx
        if template:
            cmd.extend(["--reference-doc", str(template)])

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(md_path.parent),
            )

            logger.debug(f"Pandoc output: {result.stdout}")
            if result.stderr:
                if opts.text_only:
                    logger.debug(f"Pandoc stderr: {result.stderr}")
                else:
                    logger.warning(f"Pandoc stderr: {result.stderr}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "cmd": " ".join(cmd)},
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc failed: {e.stderr}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Pandoc error: {e.stderr}"],
            )
        except FileNotFoundError:
            logger.error("Pandoc not found in PATH")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["Pandoc not installed or not in PATH"],
            )
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _find_base64_images(self, md_path: Path) -> list[dict[str, Any]]:
        """Find all base64 data URI images in MD file."""
        images = []
        content = md_path.read_text(encoding="utf-8", errors="ignore")
        for match in IMAGE_PATTERN.finditer(content):
            images.append({
                "alt": match.group(1),
                "full_uri": match.group(2),
                "mime_type": f"image/{match.group(3)}",
                "base64_data": match.group(4),
            })
        return images

    def _preprocess_md_images(self, md_path: Path) -> tuple[Path, Path]:
        """Extract base64 images to files and rewrite MD references.

        Returns:
            Tuple of (modified_md_path, temp_dir_path)
        """
        content = md_path.read_text(encoding="utf-8", errors="ignore")
        temp_dir = Path(tempfile.mkdtemp(prefix="orf_md_images_"))
        images_dir = temp_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        def replace_base64(match: re.Match) -> str:
            alt = match.group(1)
            mime_ext = match.group(3)
            base64_data = match.group(4)
            try:
                img_bytes = base64.b64decode(base64_data)
            except (ValueError, TypeError):
                logger.exception("Failed to decode base64 image data, returning raw match")
                return match.group(0)
            img_hash = hashlib.md5(img_bytes).hexdigest()[:12]
            ext = "png" if mime_ext == "png" else mime_ext
            filename = f"image_{img_hash}.{ext}"
            filepath = images_dir / filename
            filepath.write_bytes(img_bytes)
            return f"![{alt}]({filepath.as_posix()})"

        new_content = IMAGE_PATTERN.sub(replace_base64, content)
        new_md_path = temp_dir / md_path.name
        new_md_path.write_text(new_content, encoding="utf-8")

        return new_md_path, temp_dir

    def _extract_images_separately(
        self,
        input_path: Path,
        output_path: Path,
        images_dir: Path,
    ) -> tuple[Path, None]:
        """Extract all images to images_dir, write manifest, return stripped MD.

        Unlike _preprocess_md_images which rewrites image refs to point at the
        extracted files (and relies on Pandoc to embed them), this version
        REMOVES the image references entirely. The output is a DOCX with no
        embedded images, plus a directory of extracted images plus a manifest
        describing the original → extracted mapping.

        Returns:
            Tuple of (stripped_md_path, None — no temp_dir to clean up;
            images_dir is owned by the caller)
        """
        images_dir.mkdir(parents=True, exist_ok=True)
        content = input_path.read_text(encoding="utf-8", errors="ignore")

        manifest_entries: list[dict] = []
        stripped_content = content
        image_counter = 0

        for match in IMAGE_REF_PATTERN.finditer(content):
            alt = match.group(1)
            ref = match.group(2)

            try:
                if ref.startswith("data:image/"):
                    mime_match = re.match(r"data:image/([^;]+);base64,(.+)", ref)
                    if not mime_match:
                        continue
                    mime_ext = mime_match.group(1)
                    data = base64.b64decode(mime_match.group(2))
                    ext = "png" if mime_ext == "png" else mime_ext
                else:
                    img_path = (input_path.parent / ref).resolve()
                    if not img_path.exists():
                        logger.warning(f"Image ref not found, skipping: {ref}")
                        continue
                    data = img_path.read_bytes()
                    ext = img_path.suffix.lstrip(".") or "png"

                image_counter += 1
                img_hash = hashlib.md5(data).hexdigest()[:12]
                filename = f"image_{image_counter:03d}_{img_hash}.{ext}"
                out_path = images_dir / filename
                out_path.write_bytes(data)

                manifest_entries.append({
                    "original_ref": ref,
                    "extracted_path": str(out_path.relative_to(images_dir.parent)),
                    "alt": alt,
                    "size_bytes": len(data),
                })

                stripped_content = stripped_content.replace(match.group(0), "")
            except Exception as e:
                logger.warning(f"Failed to extract image {ref}: {e}")

        manifest_path = images_dir / "image_manifest.json"
        manifest_path.write_text(
            json.dumps({"images": manifest_entries, "total": len(manifest_entries)}, indent=2),
            encoding="utf-8",
        )

        stripped_path = output_path.parent / f"{input_path.stem}.stripped.md"
        stripped_path.write_text(stripped_content, encoding="utf-8")

        return stripped_path, None

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        """MD2DOCX uses pre-processing approach for images.

        Images embedded in MD as base64 data URIs are extracted to temp files
        during convert() and rewritten as local file references before Pandoc.
        No post-conversion injection needed.

        The `images` parameter (from images_json) is NOT used in MD pipeline.
        MD2DOCX extracts images directly from base64 in the markdown content.

        For precise paragraph-level image placement, use the XLIFF pipeline instead.
        This method returns ([], images) meaning all images are treated as orphaned.

        Returns:
            tuple[list, list]: First list is empty (no injected images), second list
                              contains all images as orphaned.
        """
        logger.debug(
            "MD2DOCX handles images via pre-processing. "
            "Base64 images are extracted and rewritten as local file references before Pandoc."
        )
        return ([], images)
