"""orf detect-format — Detect the file format of a document.

Companion CLI to the ORF MCP detect_format_tool. Reads a file and
prints the detected format and confidence score.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from orf.detection import FormatDetector
from orf.error_handlers.conversion_error import FormatDetectionError


@click.command("detect-format")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON")
def detect_format(input_file: str, output_json: bool) -> None:
    """Detect the file format of a document.

    INPUT_FILE: Path to the document file to inspect.
    """
    detector = FormatDetector()
    try:
        fmt, confidence = detector.detect(Path(input_file))
    except FormatDetectionError as e:
        raise click.ClickException(f"Format detection failed: {e}")

    if output_json:
        click.echo(json.dumps(
            {"file": str(input_file), "format": str(fmt), "confidence": round(confidence, 4)},
            indent=2,
        ))
    else:
        click.echo(f"Format: {fmt}  (confidence: {confidence:.2%})")
