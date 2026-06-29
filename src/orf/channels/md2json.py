"""Markdown to JSON conversion channel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from orf.channels._json_kv import apply_opp_kv_translations, unflatten_opp_kv
from orf.converters.base import BaseConverter, ConversionResult
from orf.converters.options import ConverterOptions
from orf.logging import get_logger
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.parsers.manifest import Manifest

logger = get_logger("channel.md2json")

JSON_BLOCK_PATTERN = re.compile(r"```json\s*(.*?)\s*(?:```|$)", re.DOTALL)
# OPP 0.7.0+: JSONExtractor emits json_field:path = value lines (one per string
# leaf) alongside a ```json fenced block. The json_field: prefix acts as a
# structural anchor — OL preserves it while translating the value. Both `.`
# and full-width `。` are accepted as path delimiters because OL may translate
# the period when target_lang is zh.
OPP_KV_PATTERN = re.compile(
    r"^json_field:([A-Za-z_\u4e00-\u9fff0-9][\w.\u3002\[\]0-9]*)\s*=\s*(.*)$"
)


class MD2JSONConverter(BaseConverter):
    """Markdown to JSON converter."""

    def __init__(
        self,
        manifest: Optional[Manifest] = None,
        frontmatter: Optional[FrontmatterMetadata] = None,
    ):
        super().__init__(manifest, frontmatter)

    @property
    def supported_format(self) -> str:
        return "JSON"

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

        try:
            content = input_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read input file: %s", e, exc_info=True)
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to read input file: {e}"],
            )

        data: Any = None
        base_data: Any = None
        translations: dict[str, str] = {}

        # Strategy 1: combined mode — fenced block as base + json_field: kv as translations
        fence_match = JSON_BLOCK_PATTERN.search(content)
        if fence_match:
            try:
                base_data = json.loads(fence_match.group(1))
            except json.JSONDecodeError as e:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[f"Invalid JSON syntax in fenced block: {e}"],
                )

        # Collect json_field: kv translations
        for line in content.splitlines():
            m = OPP_KV_PATTERN.match(line)
            if m:
                translations[m.group(1)] = m.group(2)

        if base_data is not None:
            if translations:
                try:
                    data = apply_opp_kv_translations(base_data, translations)
                except Exception as e:
                    logger.error("Failed to apply json_field translations: %s", e, exc_info=True)
                    return ConversionResult(
                        output_path=output_path,
                        success=False,
                        errors=[f"Failed to apply json_field translations: {e}"],
                    )
            else:
                data = base_data
        elif translations:
            # Fallback: kv lines only, no fence — use legacy unflatten (loses non-strings)
            pairs = [(k, v) for k, v in translations.items()]
            try:
                data = unflatten_opp_kv(pairs)
            except Exception as e:
                logger.warning(f"OPP-KV unflatten failed ({e})")
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[f"OPP-KV unflatten failed: {e}"],
                )
        else:
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=["No JSON code block or OPP json_field: kv pairs found in Markdown"],
            )

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to write output file: %s", e, exc_info=True)
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to write output file: {e}"],
            )

        return ConversionResult(
            output_path=output_path,
            success=True,
            metadata={"source_format": "MD"},
        )

    def inject_images(
        self,
        skeleton_path: Path | str,
        images: list,
        output_path: Path | str,
    ) -> tuple[list, list]:
        logger.warning(
            "MD2JSON does not support inject_images via paragraph_index. "
            "Images in MD are handled by Pandoc automatically."
        )
        return ([], images)