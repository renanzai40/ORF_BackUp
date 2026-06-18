"""Markdown to JSON conversion channel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from orf.converters.base import BaseConverter, ConversionResult
from orf.converters.options import ConverterOptions
from orf.logging import get_logger
from orf.parsers.frontmatter import FrontmatterMetadata
from orf.parsers.manifest import Manifest

logger = get_logger("channel.md2json")

JSON_BLOCK_PATTERN = re.compile(r"```json\s*(.*?)\s*(?:```|$)", re.DOTALL)
# 2026-06-18 round 14 #3: OPP's JSONExtractor flattens nested JSON to
# `key.path = value` lines (one per leaf). The reverse — unflattening these
# back to nested JSON — was missing, so any OPP→OL→ORF round-trip of a
# JSON file failed with "No JSON code block found in Markdown".
# Both `.` and full-width `。` are accepted as path delimiters because
# OL may translate the period when target_lang is zh.
OPP_KV_PATTERN = re.compile(
    r"^([A-Za-z_\u4e00-\u9fff][\w.\u3002\[\]0-9]*)\s*=\s*(.*)$"
)


def _unflatten_opp_kv(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Unflatten OPP-style `key.path = value` pairs back to nested JSON.

    OPP's JSONExtractor flattens with `_flatten()` which produces dot-paths
    for dict keys and `.0`, `.1`, ... for list indices. Example:
        "root.0.Model" = "BCD-500WD"
    becomes
        {"root": [{"Model": "BCD-500WD"}]}

    Values that look like numbers (int/float) or booleans are coerced to
    their JSON-native types. Everything else stays a string.
    """
    def _coerce(value: str) -> Any:
        s = value.strip()
        if s.lower() in ("true", "false"):
            return s.lower() == "true"
        if s.lower() in ("null", "none"):
            return None
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    def _set_path(root: Any, path: list[str], value: Any) -> None:
        cur = root
        for i, key in enumerate(path):
            is_last = i == len(path) - 1
            next_key = path[i + 1] if not is_last else None
            if isinstance(cur, list):
                idx = int(key)
                # Grow list with None placeholders if needed.
                # OPP's flatten skips None/empty values, so list indices
                # can have gaps (e.g. root.0, root.2 with root.1 missing).
                while len(cur) <= idx:
                    cur.append(None)
                if is_last:
                    cur[idx] = value
                    return
                if cur[idx] is None or not isinstance(cur[idx], (dict, list)):
                    cur[idx] = [] if (next_key or "").isdigit() else {}
                cur = cur[idx]
            else:
                if is_last:
                    cur[key] = value
                    return
                if next_key and next_key.isdigit():
                    if key not in cur or not isinstance(cur[key], list):
                        cur[key] = []
                else:
                    if key not in cur or not isinstance(cur[key], dict):
                        cur[key] = {}
                cur = cur[key]

    # Detect the container type from the first key path.
    first_parts = re.split(r"[.\u3002]", pairs[0][0]) if pairs else []
    if first_parts and first_parts[0].isdigit():
        root: Any = []
    else:
        root = {}

    for path, raw in pairs:
        parts = re.split(r"[.\u3002]", path)
        _set_path(root, parts, _coerce(raw))

    return root


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
            return ConversionResult(
                output_path=output_path,
                success=False,
                errors=[f"Failed to read input file: {e}"],
            )

        # 2026-06-18 round 14 #3: try OPP-style `key.path = value` lines
        # FIRST (this is what OPP's JSONExtractor actually produces).
        # Fall back to a JSON code block for hand-authored MD.
        data: Any = None
        pairs: list[tuple[str, str]] = []
        for line in content.splitlines():
            m = OPP_KV_PATTERN.match(line)
            if m:
                pairs.append((m.group(1), m.group(2)))

        if pairs:
            try:
                data = _unflatten_opp_kv(pairs)
            except Exception as e:
                logger.warning(f"OPP-KV unflatten failed ({e}); falling back to JSON block")
                data = None

        if data is None:
            match = JSON_BLOCK_PATTERN.search(content)
            if not match:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=["No JSON code block or OPP key=value pairs found in Markdown"],
                )
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                return ConversionResult(
                    output_path=output_path,
                    success=False,
                    errors=[f"Invalid JSON syntax: {e}"],
                )

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
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