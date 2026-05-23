"""ORF CLI entry point for format conversion."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from tqdm import tqdm

from orf.channels.md2docx import MD2DOCXConverter
from orf.channels.md2odt import MD2ODTConverter
from orf.channels.md2epub import MD2EPUBConverter
from orf.parsers.manifest import parse_manifest, find_manifest, ManifestParseError
from orf.parsers.frontmatter import (
    parse_frontmatter,
    FrontmatterParseError,
    has_frontmatter,
)
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
    type=click.Choice(["docx", "odt", "epub", "html", "rtf", "pdf"]),
    default="docx",
    help="目标格式",
)
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--template", type=click.Path(), help="Pandoc reference 模板路径")
@click.option("--title", type=str, help="EPUB 标题")
@click.option("--author", type=str, help="EPUB 作者")
@click.option("--lang", type=str, default="zh", help="EPUB 语言")
@click.option("--embed-images", is_flag=True, help="EPUB 嵌入图片")
def apply_md(
    input_md: str,
    target_format: str,
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
    else:
        logger.error(f"Unsupported format: {target_format}")
        click.echo(f"Error: Unsupported format '{target_format}'", err=True)
        sys.exit(1)

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

    result = converter.convert(input_path, output_path, **options)

    if result.success:
        logger.info(f"Conversion successful: {result.output_path}")
        click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        click.echo("Conversion failed:", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)


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
        click.echo(f"Unsupported format: {target_format}", err=True)
        sys.exit(1)

    success_count = 0
    fail_count = 0

    with tqdm(total=len(md_files), desc=f"Converting to {target_format}") as pbar:
        for md_file in md_files:
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

            pbar.update(1)

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
        logger.error(f"Unsupported format: {format}")
        click.echo(f"Error: Unsupported format '{format}'", err=True)
        sys.exit(1)

    result = converter.convert(input_path, xliff_path, output_path)

    if result.success:
        logger.info(f"Conversion successful: {result.output_path}")
        click.echo(f"Created {result.output_path}")
    else:
        logger.error(f"Conversion failed: {result.errors}")
        click.echo("Conversion failed:", err=True)
        for error in result.errors:
            click.echo(f"  - {error}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
