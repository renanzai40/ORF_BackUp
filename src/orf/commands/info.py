"""info command: Show information about a document file."""

from __future__ import annotations

import json
from pathlib import Path

import click

from orf.parsers.manifest import parse_manifest, find_manifest
from orf.error_handlers.conversion_error import FormatDetectionError
from orf.logging import get_logger

logger = get_logger("cli")


@click.command("info")
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
        click.echo(
            json.dumps(
                {
                    "format": detected_format,
                    "size_mb": round(size_mb, 2),
                    "resource_count": resource_count,
                    "manifest_status": manifest_status,
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Format: {detected_format}")
        click.echo(f"Size: {size_mb:.2f} MB")
        if resource_count is not None:
            click.echo(f"Resources: {resource_count} images")
        click.echo(f"Manifest: {manifest_status}")
