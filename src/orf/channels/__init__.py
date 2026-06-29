"""ORF format conversion channels."""

from typing import Callable

from orf.channels.xliff2json import apply_xliff_to_json

# Dispatch table: channel name → callable
CHANNELS: dict[str, Callable] = {
    "xliff2json": apply_xliff_to_json,
}

__all__ = [
    "apply_xliff_to_json",
    "CHANNELS",
]
