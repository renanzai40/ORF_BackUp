"""Atomic filesystem writes: stage to a temp sibling, then rename into place.

A crash between ``open()`` and ``close()`` on the final path leaves a
truncated or half-written artifact. Writing to a temp sibling first and
``os.replace``-ing on success means a reader sees either the previous
complete artifact or the new complete artifact — never a partial one.

The staging path lives in the same directory as the destination so the
rename stays on one filesystem (POSIX ``rename`` is only atomic there) and
keeps the destination's suffix, so converters that branch on the output
extension behave unchanged. The staging path is *not* created by
:func:`temp_sibling_path`; an external tool (e.g. pandoc) or
:func:`atomic_write_bytes` fills it, then :func:`publish` commits it.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def temp_sibling_path(dst: Path | str) -> Path:
    """Return a hidden, same-directory, same-suffix staging path for ``dst``.

    The path is not created — the caller writes it, then calls :func:`publish`
    (or :func:`discard` on failure).
    """
    dst = Path(dst)
    token = secrets.token_hex(8)
    return dst.with_name(f".{dst.stem}.{token}{dst.suffix}")


def publish(staged: Path | str, dst: Path | str) -> None:
    """Atomically move a fully-written ``staged`` file onto ``dst``."""
    os.replace(str(staged), str(dst))


def discard(staged: Path | str) -> None:
    """Remove a staging file, ignoring the case where it was never created."""
    Path(staged).unlink(missing_ok=True)


def atomic_write_bytes(dst: Path | str, data: bytes) -> None:
    """Write ``data`` to ``dst`` atomically (temp sibling + fsync + rename)."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    staged = temp_sibling_path(dst)
    try:
        with open(staged, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(staged, dst)
    finally:
        staged.unlink(missing_ok=True)


def atomic_write_text(dst: Path | str, text: str, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``dst`` atomically."""
    atomic_write_bytes(dst, text.encode(encoding))
