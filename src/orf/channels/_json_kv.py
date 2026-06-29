"""Shared OPP key-value utility: unflatten dot-notation paths and apply translations.

OPP's JSONExtractor flattens nested JSON into ``json_field:key.path = value``
lines. This module provides the reverse: reconstructing nested dicts/lists from
those paths, and applying translated values back into a base structure.
"""
from __future__ import annotations

import re
from typing import Any


def unflatten_opp_kv(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Unflatten OPP-style `key.path = value` pairs back to nested JSON.

    OPP's JSONExtractor flattens with ``_flatten()`` which produces dot-paths
    for dict keys and ``.0``, ``.1``, ... for list indices. Example::

        "root.0.Model" = "BCD-500WD"

    becomes::

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

    first_parts = re.split(r"[.\u3002]", pairs[0][0]) if pairs else []
    if first_parts and first_parts[0].isdigit():
        root: Any = []
    else:
        root = {}

    for path, raw in pairs:
        parts = re.split(r"[.\u3002]", path)
        _set_path(root, parts, _coerce(raw))

    return root


def apply_opp_kv_translations(base: Any, translations: dict[str, str]) -> Any:
    """Walk *base* structure, substitute string leaves with *translations*.

    Non-string values (numbers, bools, nulls) are preserved from *base* — only
    string leaves are looked up in the *translations* dict. If a path is not
    found, the original base value is kept (partial translation support).
    """
    def _walk(node: Any, path: str) -> Any:
        if isinstance(node, dict):
            return {
                k: _walk(v, f"{path}.{k}" if path else k)
                for k, v in node.items()
            }
        elif isinstance(node, list):
            return [
                _walk(v, f"{path}.{i}" if path else str(i))
                for i, v in enumerate(node)
            ]
        elif isinstance(node, str):
            return translations.get(path, node)
        return node
    return _walk(base, "")
