"""Markdown to PDF conversion channel with dual-engine support (Pandoc, WeasyPrint)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from orf.converters.base import BaseConverter, ConversionResult
from orf.logging import get_logger
from orf.converters.options import ConverterOptions

logger = get_logger("channel.md2pdf")


class MD2PDFConverter(BaseConverter):
    """Markdown to PDF converter with dual-engine support.

    Supports two conversion engines:
    - 'pandoc' (default): Uses Pandoc with pdflatex to convert MD → PDF
    - 'weasyprint': Converts MD → HTML via MD2HTMLConverter, then HTML → PDF via WeasyPrint
    """

    @property
    def supported_format(self) -> str:
        return "PDF"

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

        if not self.validate_input(input_path):
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Invalid input file: {input_path}"],
            )

        opts = options or ConverterOptions()
        engine = opts.engine.lower()
        if engine == "weasyprint":
            return self._convert_weasyprint(input_path, output_path, options)
        else:
            return self._convert_pandoc(input_path, output_path, options)

    def _convert_pandoc(
        self,
        input_path: Path,
        output_path: Path,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        """Convert MD → PDF using Pandoc with pdflatex."""
        opts = options or ConverterOptions()
        cmd = [
            "pandoc",
            str(input_path),
            "-o", str(output_path),
            "--to", "pdf",
        ]

        # Use xelatex engine for Chinese font support
        if opts.chinese_font:
            cmd.extend(["--pdf-engine=xelatex", "-V", "mainfont=SimSun"])
        else:
            cmd.extend(["--pdf-engine=pdflatex"])

        try:
            logger.info(f"Running: {' '.join(cmd)}")
            cmd[1] = str(input_path.resolve())
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(input_path.parent),
            )

            logger.debug(f"Pandoc output: {result.stdout}")
            if result.stderr:
                logger.warning(f"Pandoc stderr: {result.stderr}")

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "pandoc", "engine": "pdflatex", "cmd": " ".join(cmd)},
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

    def _convert_weasyprint(
        self,
        input_path: Path,
        output_path: Path,
        options: ConverterOptions | None = None,
    ) -> ConversionResult:
        """Convert MD → HTML → PDF using WeasyPrint."""
        # Check WeasyPrint availability using importlib (avoids ruff false positive)
        import importlib.util
        if importlib.util.find_spec("weasyprint") is None:
            logger.warning("WeasyPrint not installed, falling back to pandoc engine. Install with: pip install omni-re-formatter[weasyprint]")
            return self._convert_pandoc(input_path, output_path, options)

        # Import WeasyPrint for actual use
        from weasyprint import HTML  # noqa: F401

        # Import MD2HTMLConverter for the intermediate HTML step
        from orf.channels.md2html import MD2HTMLConverter

        # Intermediate HTML file path
        html_path = output_path.with_suffix(".html")

        # Step 1: MD → HTML via MD2HTMLConverter
        md2html = MD2HTMLConverter()
        html_result = md2html.convert(input_path, html_path, options)

        if not html_result.success:
            logger.error(f"MD → HTML conversion failed: {html_result.errors}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"MD → HTML failed: {html_result.errors}"],
            )

        # Step 2: HTML → PDF via WeasyPrint
        try:
            logger.info(f"WeasyPrint: Converting {html_path} → {output_path}")
            HTML(str(html_path)).write_pdf(str(output_path))

            logger.debug(f"PDF written to: {output_path}")

            # Clean up intermediate HTML on success
            try:
                html_path.unlink()
            except OSError as exc:
                logger.warning("Failed to remove intermediate HTML %s: %s", html_path, exc)

            return ConversionResult(
                output_path=output_path,
                success=True,
                metadata={"tool": "weasyprint", "engine": "html2pdf"},
            )

        except Exception as e:
            logger.error(f"WeasyPrint failed: {e}")
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"WeasyPrint error: {e}"],
            )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2PDF does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically. "
            "Use --embed-media with Pandoc for inline image embedding."
        )
        return ([], images)