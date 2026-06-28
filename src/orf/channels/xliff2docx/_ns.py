"""Shared namespace constants and configuration for the xliff2docx package."""

from __future__ import annotations

import re

# XLIFF namespaces
XLIFF_NS_1_2 = "urn:oasis:names:tc:xliff:document:1.2"
XLIFF_NS_1_1 = "urn:oasis:names:tc:xliff:document:1.1"
XLIFF_NS_2_0 = "urn:oasis:names:tc:xliff:document:2.0"
XLIFF_NS_MAP_1_2 = {"xliff": XLIFF_NS_1_2}
XLIFF_NS_MAP_1_1 = {"xliff": XLIFF_NS_1_1}
XLIFF_NS_MAP_2_0 = {"xliff": XLIFF_NS_2_0}
XLIFF_NS = XLIFF_NS_1_2
XLIFF_NS_MAP = XLIFF_NS_MAP_1_2

# Drawing namespaces
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_NS_MAP = {"w": W_NS}

# C13 fix: OOXML DrawingML allows these values for relativeFrom attributes.
ALLOWED_RELATIVE_FROM: frozenset[str] = frozenset({
    "page",
    "column",
    "margin",
    "paragraph",
    "line",
    "character",
})

# ORF-2: minimum SequenceMatcher ratio for fuzzy paragraph match
FUZZY_MATCH_THRESHOLD = 0.70

# Phase A.2: permissive wrapper-strip regex
_INNER_STRIP_RE = re.compile(
    r'<\s*/?\s*(?:source|target)\b[^>]*>',
    re.DOTALL,
)

# Phase A.2.a: regex to strip <bx>/<ex> inline formatting tags
_INLINE_TAGS_RE = re.compile(r'</?(?:bx|ex)\b[^>]*/?>', re.DOTALL)
