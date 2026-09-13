"""Mutation transparency (gap X-03): hash the files a mutating tool wrote.

An agent that calls a mutating tool must be able to verify *what actually
changed on disk*.  Every ORF MCP mutating tool therefore returns, alongside its
normal payload::

    outputs:  [{path, sha256, bytes}, ...]   # primary artifacts
    sidecars: [{path, sha256, bytes}, ...]   # auxiliary files (images.zip, ...)

The hash is computed from the byte stream on disk at response time, so a
stale/cached path or a write that silently failed surfaces as ``sha256: None``
(and ``bytes: 0``) rather than a confident-but-wrong success.

Covered here: ``apply_md`` and ``apply_xliff``. ``batch_convert`` remains a
follow-up (see ``.omo/plans/agent-oriented-gap-register.md`` §4.3 X-03).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Auxiliary files ORF's MD path writes next to the output DOCX.
DEFAULT_SIDECAR_NAMES: tuple[str, ...] = ("images.json", "images.zip")


def file_entry(path: str | Path) -> dict[str, object]:
    """Return ``{path, sha256, bytes}`` for *path*.

    A missing/unreadable file yields ``sha256: None, bytes: 0`` — a verifiable
    "nothing was written here" signal instead of an unhashed claim.
    """
    p = Path(path)
    try:
        data = p.read_bytes()
    except OSError:
        return {"path": str(p), "sha256": None, "bytes": 0}
    return {
        "path": str(p),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def written_files(
    output_path: str | Path | None,
    sidecar_names: tuple[str, ...] = DEFAULT_SIDECAR_NAMES,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return ``(outputs, sidecars)`` manifests for a finished mutation.

    *output_path* is the primary artifact named by the conversion result;
    *sidecar_names* are known auxiliary filenames to look for in the same
    directory. Only files that exist are reported as sidecars.
    """
    if not output_path:
        return [], []
    outputs = [file_entry(output_path)]
    parent = Path(output_path).parent
    sidecars = [
        file_entry(parent / name)
        for name in sidecar_names
        if (parent / name).is_file()
    ]
    return outputs, sidecars
