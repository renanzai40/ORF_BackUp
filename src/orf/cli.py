"""ORF CLI entry point for format conversion."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import json
from pathlib import Path
from typing import Any, Optional

import click

from orf.channels.md2docx import MD2DOCXConverter
from orf.channels.md2odt import MD2ODTConverter
from orf.channels.md2epub import MD2EPUBConverter
from orf.converters.base import BaseConverter
from orf.converters.options import ConverterOptions
from orf.parsers.manifest import parse_manifest, find_manifest, ManifestParseError
from orf.parsers.frontmatter import (
    parse_frontmatter,
    FrontmatterParseError,
    has_frontmatter,
)
from orf.error_handlers.conversion_error import FormatDetectionError
from orf.logging import setup_logger, get_logger

logger = get_logger("cli")


# ========== A6: Content-addressed cache (~/.omni_cache/orf/) ==========
# Re-runs of the same input+config skip the expensive conversion (pandoc,
# openpyxl, etc.) and just copy the cached <sha256>.<ext> to the output
# path. The cache root can be overridden with the OMNI_CACHE_DIR env var
# (used by tests). Mode 0o700 protects any sensitive content.
# CACHE_DIR_NAME is the per-module subdirectory under OMNI_CACHE_DIR.
CACHE_DIR_NAME = "orf"
_cache_logger = get_logger("cli.cache")


def _cache_root() -> Path:
    """Return the ORF cache root, creating it (mode 0o700) on first access.

    The env var is read at call-time (not at import-time) so tests can
    override it via monkeypatch.setenv() before any call.
    """
    root = Path(
        os.environ.get("OMNI_CACHE_DIR", str(Path.home() / ".omni_cache"))
    ) / CACHE_DIR_NAME
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _cache_key_apply_md(
    input_path: Path,
    target_format: str,
    manifest_path: Optional[Path],
    template: Optional[str],
    images_json: Optional[str],
) -> str:
    """sha256(input_bytes + target_format + manifest_bytes + template_bytes + images_json_bytes).

    Each "config" element that can change the conversion output is hashed
    in. Any change to input, target_format, manifest content, template
    content, or images.json content yields a different cache key and
    forces a fresh conversion.
    """
    h = hashlib.sha256()
    h.update(input_path.read_bytes())
    h.update(target_format.encode("utf-8"))
    if manifest_path is not None and manifest_path.exists():
        h.update(manifest_path.read_bytes())
    if template:
        tp = Path(template)
        if tp.exists():
            h.update(tp.read_bytes())
    if images_json:
        ip = Path(images_json)
        if ip.exists():
            h.update(ip.read_bytes())
    return h.hexdigest()


def _cache_key_apply_xliff(
    input_path: Path,
    xliff_path: Path,
    fmt: str,
    images_json: Optional[str],
) -> str:
    """sha256(input_bytes + xliff_bytes + format + images_json_bytes)."""
    h = hashlib.sha256()
    h.update(input_path.read_bytes())
    h.update(xliff_path.read_bytes())
    h.update(fmt.encode("utf-8"))
    if images_json:
        ip = Path(images_json)
        if ip.exists():
            h.update(ip.read_bytes())
    return h.hexdigest()


def _check_cache(cache_key: str, output_path: Path, ext: str, no_cache: bool = False) -> bool:
    """If cached, copy to ``output_path`` and return True. Honors ``--no-cache``."""
    if no_cache:
        return False
    cache_file = _cache_root() / f"{cache_key}{ext}"
    if cache_file.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(cache_file, output_path)
        _cache_logger.info(f"Cache hit: {cache_file} -> {output_path}")
        return True
    return False


def _write_cache(cache_key: str, output_path: Path, ext: str, no_cache: bool = False) -> None:
    """Copy ``output_path`` into the cache for next run. Honors ``--no-cache``."""
    if no_cache:
        return
    if not output_path.exists():
        return
    cache_file = _cache_root() / f"{cache_key}{ext}"
    cache_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy(output_path, cache_file)
    _cache_logger.debug(f"Cache miss: wrote {cache_file}")


def _clear_orf_cache() -> int:
    """Remove all cached ORF files. Returns the number of files removed."""
    root = _cache_root()
    if not root.exists():
        return 0
    count = sum(1 for _ in root.iterdir())
    shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return count


def _error_item_to_dict(e: Any) -> dict[str, Any]:
    """Normalize error items (ErrorDetail or str) to dict for JSON output."""
    if hasattr(e, 'code'):
        return {
            'code': e.code,
            'message': e.message,
            'recovery_strategy': e.recovery_strategy.value if e.recovery_strategy else None,
        }
    return {'code': 'UNKNOWN', 'message': str(e), 'recovery_strategy': None}


def _error_item_to_str(e: Any) -> str:
    """Normalize error items (ErrorDetail or str) to string."""
    return e.message if hasattr(e, 'message') else str(e)


def _warning_item_to_dict(w: Any) -> dict[str, str]:
    """Normalize warning items (WarningDetail or str) to dict for JSON output."""
    if hasattr(w, 'code'):
        return {'code': w.code, 'message': w.message}
    return {'code': 'UNKNOWN', 'message': str(w)}


def _safe_json_dumps(data: dict) -> str:
    """Serialize data to JSON, filtering non-serializable metadata values."""
    import json
    cleaned = dict(data)
    if 'metadata' in cleaned:
        cleaned['metadata'] = _sanitize_for_json(cleaned['metadata'])
    return json.dumps(cleaned, indent=2, default=str)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize objects for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(type(obj).__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="启用详细日志")
def main(verbose: bool) -> None:
    """ORF - Omni-Re-Formatter: 将本地化后的 MD/XLIFF 还原为目标复杂格式。"""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(level=log_level)
    _maybe_install_fake_pandoc()


def _maybe_install_fake_pandoc() -> None:
    import os
    if os.environ.get("OMNI_TEST_FAKE_PANDOC") != "1":
        return
    import subprocess as _subprocess
    import sys
    from pathlib import Path as _SeamPath
    _suite_root = _SeamPath(__file__).resolve().parents[3]
    if str(_suite_root) not in sys.path:
        sys.path.insert(0, str(_suite_root))
    from tests.test_e2e_pipeline_fixtures import _FakePandocRunner
    _fake_runner = _FakePandocRunner()
    _original_run = _subprocess.run
    def _patched_run(*args, **kwargs):
        try:
            cmd = args[0] if args else kwargs.get("args") or kwargs.get("cmd")
        except (IndexError, KeyError, TypeError):
            logger.exception("Failed to extract command from patched subprocess call")
            cmd = None
        if cmd and isinstance(cmd, (list, tuple)) and len(cmd) > 0 and "pandoc" in str(cmd[0]):
            return _fake_runner(*args, **kwargs)
        return _original_run(*args, **kwargs)
    _subprocess.run = _patched_run


@main.command("apply-md")
@click.argument("input_md", type=click.Path(exists=True))
@click.option(
    "--target-format",
    "-t",
    type=click.Choice(["auto", "docx", "odt", "epub", "html", "rtf", "pdf", "csv", "json", "xlsx", "xml", "ipynb", "eml", "msg"]),
    default="docx",
    help="目标格式",
)
@click.option("--auto-detect", is_flag=True, help="自动检测输入文件格式")
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--template", type=click.Path(), help="Pandoc reference 模板路径")
@click.option("--title", type=str, help="EPUB 标题")
@click.option("--author", type=str, help="EPUB 作者")
@click.option("--lang", type=str, default="zh", help="EPUB 语言")
@click.option("--embed-images", is_flag=True, help="EPUB 嵌入图片")
@click.option("--json", "output_json", is_flag=True, help="JSON 格式输出")
@click.option("--images-json", "images_json", type=click.Path(exists=True), help="JSON file with image placement data from OPP (NOTE: image injection not supported for MD pipeline; use XLIFF pipeline for precise image placement)")
@click.option("--no-cache", "no_cache", is_flag=True, help="Skip the .omni_cache/ cache check (force a fresh conversion)")
@click.option("--clear-cache", "clear_cache", is_flag=True, help="Remove all cached ORF outputs and exit")
def apply_md(
    input_md: str,
    target_format: str,
    auto_detect: bool,
    output: str | None,
    template: str | None,
    title: str | None,
    author: str | None,
    lang: str,
    embed_images: bool,
    output_json: bool,
    images_json: str | None,
    no_cache: bool,
    clear_cache: bool,
) -> None:
    """将 MD 文件转换为目标格式

    INPUT_MD: 输入的 MD 文件路径（通常由 OL 翻译后的文件）

    注意：MD 格式是行级别的，而非段落级别。Pandoc 将 ![Image](url) 作为行内元素处理，
    原始 DOCX 的段落边界在 MD 输出中不会保留。对于需要精确结构的文档（如图片+标题段落），
    请使用 XLIFF 管道。
    """
    input_path = Path(input_md)

    if target_format == "auto" or auto_detect:
        from orf.detection import FormatDetector

        detector = FormatDetector()
        try:
            detected = detector.detect(input_path)
            format_map = {
                "DOCX": "docx",
                "ODT": "odt",
                "EPUB": "epub",
                "HTML": "html",
                "RTF": "rtf",
                "PDF": "pdf",
            }
            target_format = format_map.get(detected, detected.lower())
            logger.info(f"Auto-detected format: {detected} -> {target_format}")
        except FormatDetectionError as e:
            logger.error(f"Format detection failed: {e}")
            raise click.ClickException(
                f"Format detection failed: {e}\n"
                f"Hint: 1) Ensure manifest.json exists with source.format field\n"
                f"       2) Check the input file is a valid document\n"
                f"       3) Use --target-format <format> to specify manually"
            )

    if output is None:
        output_path = input_path.with_suffix(f".{target_format}")
    else:
        output_path = Path(output)

    if clear_cache:
        n = _clear_orf_cache()
        logger.info(f"Cleared {n} cached file(s) from {_cache_root()}")
        click.echo(f"Cleared {n} cached file(s) from {_cache_root()}")
        return

    logger.info(f"Converting {input_path} -> {output_path} ({target_format})")

    manifest = None
    manifest_path: Optional[Path] = None
    try:
        manifest_path = find_manifest(input_path)
        if manifest_path:
            logger.info(f"Found manifest: {manifest_path}")
            manifest = parse_manifest(manifest_path)
    except ManifestParseError as e:
        logger.warning(f"Failed to parse manifest: {e}")

    cache_key = _cache_key_apply_md(input_path, target_format, manifest_path, template, images_json)
    if _check_cache(cache_key, output_path, f".{target_format}", no_cache=no_cache):
        logger.info(f"Cache hit for {input_path.name} -> {output_path}")
        if output_json:
            click.echo(_safe_json_dumps({
                'success': True,
                'output_path': str(output_path),
                'errors': [],
                'warnings': [],
                'metadata': {'cache_hit': True},
            }))
        else:
            click.echo(f"Created {output_path} (cached)")
        return

    frontmatter = None
    try:
        frontmatter = parse_frontmatter(input_path)
        logger.info(
            f"Frontmatter: {frontmatter.source_lang} -> {frontmatter.target_lang}"
        )
    except FrontmatterParseError as e:
        logger.warning(f"Failed to parse frontmatter: {e}")

    if target_format == "docx":
        converter: BaseConverter = MD2DOCXConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "odt":
        converter = MD2ODTConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "epub":
        converter = MD2EPUBConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "html":
        from orf.channels.md2html import MD2HTMLConverter
        converter = MD2HTMLConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "rtf":
        from orf.channels.md2rtf import MD2RTFConverter
        converter = MD2RTFConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "pdf":
        from orf.channels.md2pdf import MD2PDFConverter
        converter = MD2PDFConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "csv":
        from orf.channels.md2csv import MD2CSVConverter
        converter = MD2CSVConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "json":
        from orf.channels.md2json import MD2JSONConverter
        converter = MD2JSONConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "xml":
        from orf.channels.md2xml import MD2XMLConverter
        converter = MD2XMLConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "eml":
        from orf.channels.md2eml import MD2EMLConverter
        converter = MD2EMLConverter(manifest=manifest, frontmatter=frontmatter)
    elif target_format == "xlsx":
        try:
            from orf.channels.md2xlsx import MD2XLSXConverter
            converter = MD2XLSXConverter(manifest=manifest, frontmatter=frontmatter)
        except ImportError as e:
            raise click.ClickException(
                f"XLSX conversion requires openpyxl.\n"
                f"Install with: pip install omni-re-formatter[office]\n"
                f"Error: {e}"
            )
    elif target_format == "ipynb":
        try:
            from orf.channels.md2ipynb import MD2IPYNBConverter
            converter = MD2IPYNBConverter(manifest=manifest, frontmatter=frontmatter)
        except ImportError as e:
            raise click.ClickException(
                f"IPYNB conversion requires nbformat.\n"
                f"Install with: pip install omni-re-formatter[notebook]\n"
                f"Error: {e}"
            )
    elif target_format == "msg":
        try:
            from orf.channels.md2msg import MD2MSGConverter
            converter = MD2MSGConverter(manifest=manifest, frontmatter=frontmatter)
        except ImportError as e:
            raise click.ClickException(
                f"MSG conversion requires aspose-email-foss.\n"
                f"Install with: pip install omni-re-formatter[email-output]\n"
                f"Error: {e}"
            )
    else:
        raise click.ClickException(
            f"Unsupported format '{target_format}'\n"
            f"Hint: Valid formats are: docx, odt, epub, html, rtf, pdf, csv, json, xlsx, xml, ipynb, eml, msg\n"
            f"       Use --target-format <format> to specify"
        )

    options: dict[str, Any] = {}
    if template:
        options["template"] = Path(template)
    if title:
        options["title"] = title
    if author:
        options["author"] = author
    if lang:
        options["lang"] = lang
    if embed_images:
        options["embed_images"] = True

    with click.progressbar(
        length=1,
        label=f"Converting to {target_format}",
        show_pos=True,
        show_percent=True,
        file=sys.stderr if output_json else None,
    ) as bar:
        bar.update(1)
        result = converter.convert(input_path, output_path, ConverterOptions(**options))

    images = None
    if images_json:
        try:
            import json
            with open(images_json) as f:
                images_data = json.load(f)
            from orf.mcp.schemas import ImagePlacement
            if isinstance(images_data, dict) and "images" in images_data:
                images_data = images_data["images"]
            images = [ImagePlacement(**img) for img in images_data]
            logger.info(f"Loaded {len(images)} images from {images_json}")
        except Exception as e:
            logger.warning(f"Failed to load images from {images_json}: {e}")

    if result.success and images:
        import tempfile
        import shutil
        try:
            # Bug #6 fix: inject_images overwrites output_path (uses as skeleton)
            # Copy translated output to temp skeleton file, inject into temp, then repack to final output
            tmp_skeleton = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)
            tmp_skeleton.close()
            shutil.copy2(result.output_path, tmp_skeleton.name)

            injected, orphaned = converter.inject_images(
                tmp_skeleton.name, images, result.output_path
            )
            # Clean up temp skeleton
            Path(tmp_skeleton.name).unlink(missing_ok=True)
            logger.info(
                f"Injected {len(injected)} images, {len(orphaned)} orphaned"
            )
            if orphaned:
                for img in orphaned:
                    logger.warning(
                        f"Orphaned image (no position): mime_type={img.mime_type}"
                    )
        except AttributeError:
            logger.warning(
                "Converter does not support image injection"
            )
        except Exception as e:
            logger.error(f"Image injection failed: {e}")

    if result.success:
        _write_cache(cache_key, output_path, f".{target_format}", no_cache=no_cache)
        logger.info(f"Conversion successful: {result.output_path}")
        if output_json:
            click.echo(_safe_json_dumps({
                'success': True,
                'output_path': str(result.output_path),
                'errors': [_error_item_to_dict(e) for e in result.errors],
                'warnings': [_warning_item_to_dict(w) for w in result.warnings],
                'metadata': result.metadata
            }))
        else:
            click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        errors_str = ", ".join(_error_item_to_str(e) for e in result.errors) if result.errors else "Unknown error"
        if output_json:
            click.echo(_safe_json_dumps({
                'success': False,
                'output_path': str(result.output_path) if result.output_path else None,
                'errors': [_error_item_to_dict(e) for e in result.errors],
                'warnings': [_warning_item_to_dict(w) for w in result.warnings],
                'metadata': result.metadata
            }))
        else:
            raise click.ClickException(
                f"Conversion failed: {errors_str}\n"
                f"Hint: 1) Check Pandoc is installed (pip install pandoc)\n"
                f"       2) Verify input file is valid\n"
                f"       3) Try --verbose for detailed logs"
            )


@main.command("convert-batch")
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--target-format", "-t", type=click.Choice(["docx", "odt", "epub"]))
@click.option("--output-dir", "-o", type=click.Path(), help="输出目录")
@click.option("--pattern", "-p", default="*.md", help="文件匹配模式")
@click.option("--json", "output_json", is_flag=True, help="JSON 格式输出")
def convert_batch(
    input_dir: str,
    target_format: str,
    output_dir: str | None,
    pattern: str,
    output_json: bool,
) -> None:
    """批量转换 MD 文件"""
    input_path = Path(input_dir)
    output_path = Path(output_dir) if output_dir else input_path

    md_files = []
    for md_file in input_path.rglob(pattern):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if has_frontmatter(content):
                md_files.append(md_file)
        except Exception as e:
            logger.warning(f"Skipping {md_file}: {e}")

    logger.info(f"Found {len(md_files)} MD files to convert")

    if not md_files:
        click.echo("No files found to convert")
        return

    if target_format == "docx":
        converter_class: type = MD2DOCXConverter
    elif target_format == "odt":
        converter_class = MD2ODTConverter
    elif target_format == "epub":
        converter_class = MD2EPUBConverter
    else:
        raise click.ClickException(
            f"Unsupported format '{target_format}'\n"
            f"Hint: Valid formats are: docx, odt, epub\n"
            f"       Use --target-format <format> to specify"
        )

    success_count = 0
    fail_count = 0

    with click.progressbar(md_files, label=f"Converting to {target_format}", show_pos=True, show_percent=True) as bar:
        for md_file in bar:
            try:
                manifest = None
                try:
                    manifest_path = find_manifest(md_file)
                    if manifest_path:
                        manifest = parse_manifest(manifest_path)
                except Exception as exc:
                    logger.warning("Failed to parse manifest for %s: %s", md_file, exc)

                frontmatter = None
                try:
                    frontmatter = parse_frontmatter(md_file)
                except Exception as exc:
                    logger.warning("Failed to parse frontmatter for %s: %s", md_file, exc)

                converter = converter_class(manifest=manifest, frontmatter=frontmatter)
                output_file = output_path / f"{md_file.stem}.{target_format}"

                result = converter.convert(md_file, output_file)

                if result.success:
                    success_count += 1
                else:
                    fail_count += 1
                    logger.error(f"Failed: {md_file}: {result.errors}")

            except Exception as e:
                fail_count += 1
                logger.error(f"Error processing {md_file}: {e}")

    click.echo(f"\nCompleted: {success_count} succeeded, {fail_count} failed")

    if output_json:
        click.echo(json.dumps({
            'success_count': success_count,
            'fail_count': fail_count,
            'total': len(md_files)
        }, indent=2))


@main.command("apply-xliff")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--xliff", "-x", required=True, help="Translated XLIFF file")
@click.option("--xliff-content", "xliff_content", type=str, help="Inline XLIFF content (alternative to --xliff)")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["docx", "pptx", "epub", "html", "odt"]),
    default="docx",
    help="Output format",
)
@click.option("--json", "output_json", is_flag=True, help="JSON 格式输出")
@click.option("--images-json", "images_json", type=click.Path(exists=True), help="JSON file with image placement data from OPP")
@click.option("--no-cache", "no_cache", is_flag=True, help="Skip the .omni_cache/ cache check (force a fresh conversion)")
@click.option("--clear-cache", "clear_cache", is_flag=True, help="Remove all cached ORF outputs and exit")
def apply_xliff(input_file: str, xliff: str, xliff_content: Optional[str], output: str, format: str, output_json: bool, images_json: str, no_cache: bool, clear_cache: bool) -> None:
    """Apply XLIFF translation to original document.

    INPUT_FILE: Original document (DOCX/PPTX/EPUB/HTML)
    """
    input_path = Path(input_file)
    output_path = Path(output)

    # Mutually exclusive check
    if xliff and xliff_content:
        raise click.BadParameter("--xliff and --xliff-content are mutually exclusive")

    # Handle inline XLIFF content
    xliff_path = Path(xliff)
    if xliff_content:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xliff', delete=False) as tmp:
            tmp.write(xliff_content)
            xliff_path = Path(tmp.name)

    if clear_cache:
        n = _clear_orf_cache()
        logger.info(f"Cleared {n} cached file(s) from {_cache_root()}")
        click.echo(f"Cleared {n} cached file(s) from {_cache_root()}")
        return

    cache_key = _cache_key_apply_xliff(input_path, xliff_path, format, images_json)
    if _check_cache(cache_key, output_path, f".{format}", no_cache=no_cache):
        logger.info(f"Cache hit for {input_path.name} -> {output_path}")
        if output_json:
            click.echo(_safe_json_dumps({
                'success': True,
                'output_path': str(output_path),
                'errors': [],
                'warnings': [],
                'metadata': {'cache_hit': True},
            }))
        else:
            click.echo(f"Created {output_path} (cached)")
        return

    images = None
    if images_json:
        import json
        try:
            with open(images_json) as f:
                images_data = json.load(f)
            from orf.mcp.schemas import ImagePlacement
            if isinstance(images_data, dict) and "images" in images_data:
                images_data = images_data["images"]
            images = [ImagePlacement(**img) for img in images_data]
            logger.info(f"Loaded {len(images)} images from {images_json}")
        except Exception as e:
            logger.warning(f"Failed to load images from {images_json}: {e}")

    logger.info(f"Applying XLIFF {xliff_path} to {input_path} -> {output_path} ({format})")

    converter: Any
    if format == "docx":
        from orf.channels.xliff2docx import XLIFF2DOCXConverter

        converter = XLIFF2DOCXConverter()
    elif format == "pptx":
        from orf.channels.xliff2pptx import XLIFF2PPTXConverter

        converter = XLIFF2PPTXConverter()
    elif format == "epub":
        from orf.channels.xliff2epub import XLIFF2EPUBConverter

        converter = XLIFF2EPUBConverter()
    elif format == "html":
        from orf.channels.xliff2html import XLIFF2HTMLConverter

        converter = XLIFF2HTMLConverter()
    elif format == "odt":
        from orf.channels.xliff2odf import XLIFF2ODFConverter

        converter = XLIFF2ODFConverter()
    else:
        raise click.ClickException(
            f"Unsupported format '{format}'\n"
            f"Hint: Valid formats are: docx, pptx, epub, html, odt\n"
            f"       Use --format <format> to specify"
        )

    result = converter.convert(input_path, xliff_path, output_path)

    if result.success and images:
        import tempfile
        import shutil
        try:
            tmp_skeleton = tempfile.NamedTemporaryFile(suffix='.docx', delete=False)
            tmp_skeleton.close()
            shutil.copy2(result.output_path, tmp_skeleton.name)

            injected, orphaned = converter.inject_images(
                tmp_skeleton.name, images, result.output_path
            )
            Path(tmp_skeleton.name).unlink(missing_ok=True)
            logger.info(
                f"Injected {len(injected)} images, {len(orphaned)} orphaned"
            )
            if orphaned:
                for img in orphaned:
                    logger.warning(
                        f"Orphaned image (no position): mime_type={img.mime_type}"
                    )
        except AttributeError:
            logger.warning(
                "Converter does not support image injection, continuing without images"
            )
        except Exception as e:
            logger.error(f"Image injection failed: {e}")

    if result.success:
        _write_cache(cache_key, output_path, f".{format}", no_cache=no_cache)
        logger.info(f"Conversion successful: {result.output_path}")
        if output_json:
            click.echo(_safe_json_dumps({
                'success': True,
                'output_path': str(result.output_path),
                'errors': [_error_item_to_dict(e) for e in result.errors],
                'warnings': [_warning_item_to_dict(w) for w in result.warnings],
                'metadata': result.metadata
            }))
        else:
            click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        errors_str = ", ".join(_error_item_to_str(e) for e in result.errors) if result.errors else "Unknown error"
        if output_json:
            click.echo(_safe_json_dumps({
                'success': False,
                'output_path': str(result.output_path) if result.output_path else None,
                'errors': [_error_item_to_dict(e) for e in result.errors],
                'warnings': [_warning_item_to_dict(w) for w in result.warnings],
                'metadata': result.metadata
            }))
        else:
            raise click.ClickException(
                f"Conversion failed: {errors_str}\n"
                f"Hint: 1) Check XLIFF file is valid\n"
                f"       2) Verify original document exists\n"
                f"       3) Try --verbose for detailed logs"
            )


@main.command("info")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, help="JSON 格式输出")
def info(input_file: str, output_json: bool) -> None:
    """Show information about a document file.

    INPUT_FILE: Document file to inspect (DOCX, ODT, EPUB, etc.)
    """
    from orf.detection import FormatDetector

    input_path = Path(input_file)

    # Detect format
    detector = FormatDetector()
    try:
        detected_format = detector.detect(input_path)
    except FormatDetectionError as e:
        raise click.ClickException(f"Format detection failed: {e}")

    # Get file size
    file_size = input_path.stat().st_size
    size_mb = file_size / (1024 * 1024)

    # Check manifest presence and get resource count
    manifest_path = find_manifest(input_path)
    manifest_status = "present" if manifest_path else "not found"

    resource_count = None
    if manifest_path:
        try:
            manifest = parse_manifest(manifest_path)
            if manifest.images:
                resource_count = len(manifest.images)
        except Exception as e:
            logger.warning(f"Failed to parse manifest for resource count: {e}")

    # Output
    if output_json:
        click.echo(json.dumps({
            'format': detected_format,
            'size_mb': round(size_mb, 2),
            'resource_count': resource_count,
            'manifest_status': manifest_status
        }, indent=2))
    else:
        click.echo(f"Format: {detected_format}")
        click.echo(f"Size: {size_mb:.2f} MB")
        if resource_count is not None:
            click.echo(f"Resources: {resource_count} images")
        click.echo(f"Manifest: {manifest_status}")


if __name__ == "__main__":
    main()
