"""T6/T7 regression tests: ORF MCP apply_md / apply_xliff CLI parity params.

Locks in the audit T6/T7 (2026-06-21) additions:
- apply_md: reference_doc, template, title, author, lang, embed_images, text_only, max_file_size_mb
- apply_xliff: force, no_cache, max_file_size_mb
"""
from __future__ import annotations

import inspect

from orf.mcp import server


class TestApplyMdParityParams:
    def test_apply_md_accepts_all_new_params(self):
        sig = inspect.signature(server.apply_md)
        new_params = [
            "reference_doc",
            "template",
            "title",
            "author",
            "lang",
            "embed_images",
            "text_only",
            "max_file_size_mb",
        ]
        for p in new_params:
            assert p in sig.parameters, f"apply_md missing param: {p}"

    def test_apply_md_defaults(self):
        sig = inspect.signature(server.apply_md)
        assert sig.parameters["separate_images"].default is True
        assert sig.parameters["embed_images"].default is False
        assert sig.parameters["text_only"].default is False


class TestApplyXliffParityParams:
    def test_apply_xliff_accepts_all_new_params(self):
        sig = inspect.signature(server.apply_xliff)
        new_params = ["force", "no_cache", "max_file_size_mb"]
        for p in new_params:
            assert p in sig.parameters, f"apply_xliff missing param: {p}"

    def test_apply_xliff_force_default_false(self):
        sig = inspect.signature(server.apply_xliff)
        assert sig.parameters["force"].default is False

    def test_apply_xliff_no_cache_default_false(self):
        sig = inspect.signature(server.apply_xliff)
        assert sig.parameters["no_cache"].default is False
