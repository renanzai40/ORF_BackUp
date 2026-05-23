"""ORF CLI entry point for format conversion."""

from __future__ import annotations

from pathlib import Path

import click

from orf.channels.md2docx import MD2DOCXConverter
from orf.channels.md2odt import MD2ODTConverter
from orf.channels.md2epub import MD2EPUBConverter
from orf.parsers.manifest import parse_manifest, find_manifest, ManifestParseError
from orf.parsers.frontmatter import (
    parse_frontmatter,
    FrontmatterParseError,
    has_frontmatter,
)
from orf.error_handlers.conversion_error import FormatDetectionError
from orf.logging import setup_logger, get_logger

logger = get_logger("cli")


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="启用详细日志")
def main(verbose: bool):
    """ORF - Omni-Re-Formatter: 将本地化后的 MD/XLIFF 还原为目标复杂格式。"""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(level=log_level)


@main.command("apply-md")
@click.argument("input_md", type=click.Path(exists=True))
@click.option(
    "--target-format",
    "-t",
    type=click.Choice(["docx", "odt", "epub", "html", "rtf", "pdf", "auto"]),
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
):
    """将 MD 文件转换为目标格式

    INPUT_MD: 输入的 MD 文件路径（通常由 OL 翻译后的文件）
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

    logger.info(f"Converting {input_path} -> {output_path} ({target_format})")

    manifest = None
    try:
        manifest_path = find_manifest(input_path)
        if manifest_path:
            logger.info(f"Found manifest: {manifest_path}")
            manifest = parse_manifest(manifest_path)
    except ManifestParseError as e:
        logger.warning(f"Failed to parse manifest: {e}")

    frontmatter = None
    try:
        frontmatter = parse_frontmatter(input_path)
        logger.info(
            f"Frontmatter: {frontmatter.source_lang} -> {frontmatter.target_lang}"
        )
    except FrontmatterParseError as e:
        logger.warning(f"Failed to parse frontmatter: {e}")

    if target_format == "docx":
        converter = MD2DOCXConverter(manifest=manifest, frontmatter=frontmatter)
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
    else:
        raise click.ClickException(
            f"Unsupported format '{target_format}'\n"
            f"Hint: Valid formats are: docx, odt, epub, html, rtf, pdf\n"
            f"       Use --target-format <format> to specify"
        )

    options = {}
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
    ) as bar:
        result = converter.convert(input_path, output_path, **options)
        bar.update(1)

    if result.success:
        logger.info(f"Conversion successful: {result.output_path}")
        click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        errors_str = ", ".join(result.errors) if result.errors else "Unknown error"
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
def convert_batch(
    input_dir: str,
    target_format: str,
    output_dir: str | None,
    pattern: str,
):
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
        converter_class = MD2DOCXConverter
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
                except Exception:
                    pass

                frontmatter = None
                try:
                    frontmatter = parse_frontmatter(md_file)
                except Exception:
                    pass

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


@main.command("apply-xliff")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--xliff", "-x", required=True, help="Translated XLIFF file")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["docx", "pptx", "epub", "html", "odt"]),
    default="docx",
    help="Output format",
)
def apply_xliff(input_file: str, xliff: str, output: str, format: str):
    """Apply XLIFF translation to original document.

    INPUT_FILE: Original document (DOCX/PPTX/EPUB/HTML)
    """
    input_path = Path(input_file)
    output_path = Path(output)
    xliff_path = Path(xliff)

    logger.info(f"Applying XLIFF {xliff_path} to {input_path} -> {output_path} ({format})")

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

    if result.success:
        logger.info(f"Conversion successful: {result.output_path}")
        click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        raise click.ClickException(
            f"Conversion failed: {result.errors}\n"
            f"Hint: 1) Check XLIFF file is valid\n"
            f"       2) Verify original document exists\n"
            f"       3) Try --verbose for detailed logs"
        )


@main.command("info")
@click.argument("input_file", type=click.Path(exists=True))
def info(input_file: str):
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
    click.echo(f"Format: {detected_format}")
    click.echo(f"Size: {size_mb:.2f} MB")
    if resource_count is not None:
        click.echo(f"Resources: {resource_count} images")
    click.echo(f"Manifest: {manifest_status}")


if __name__ == "__main__":
    main()
