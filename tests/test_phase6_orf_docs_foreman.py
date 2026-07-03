"""Tests for Phase 6 ORF docs and Foreman (P6-T1, T2, T3)."""


def test_p6_t1_foreman_supports_all_16_formats():
    """P6-T1: Foreman should route all 16 output formats to specialists."""
    from orf.agents.specialists import format_specialist
    # All 16 formats that ORF supports
    all_formats = [
        "docx", "pptx", "epub", "html", "rtf", "pdf", "icml", "srt",
        "csv", "xlsx", "json", "ipynb", "eml", "msg", "odt", "xml",
    ]
    specialist = format_specialist.FormatSpecialist()
    supported = specialist.supported_formats
    for fmt in all_formats:
        assert fmt in supported, (
            f"Format {fmt!r} is not in FormatSpecialist.supported_formats. "
            f"Foreman cannot route {fmt} format."
        )


def test_p6_t1_foreman_routing_table_covers_all_16_formats():
    """P6-T1: Foreman.route_to_specialist should have explicit entries for all 16 formats."""
    from orf.agents.foreman import ForemanAgent, JobRequest
    foreman = ForemanAgent()
    all_formats = [
        "docx", "pptx", "epub", "html", "rtf", "pdf", "icml", "srt",
        "csv", "xlsx", "json", "ipynb", "eml", "msg", "odt", "xml",
    ]
    for fmt in all_formats:
        job = JobRequest(input_path="/tmp/test.md", target_format=fmt)
        specialist = foreman.route_to_specialist(job)
        assert specialist is not None, (
            f"Foreman.route_to_specialist returned None for format {fmt!r}."
        )


def test_p6_t2_get_capabilities_xliff_count_is_5():
    """P6-T2: get_capabilities should say 5 XLIFF backfill formats, not 7."""
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "src" / "orf" / "mcp" / "server.py"
    content = p.read_text(encoding="utf-8")
    # Check the count
    assert "XLIFF backfill formats (5)" in content, (
        f"server.py should say 'XLIFF backfill formats (5)' but says something else. "
        f"Only 5 formats are supported (DOCX, PPTX, EPUB, HTML, ODT)."
    )
    # The old "7" should not be present
    assert "XLIFF backfill formats (7)" not in content, (
        f"server.py still says 'XLIFF backfill formats (7)' but only 5 are supported."
    )


def test_p6_t3_agents_md_documents_get_capabilities():
    """P6-T3: AGENTS.md should document the get_capabilities MCP tool."""
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "AGENTS.md"
    content = p.read_text(encoding="utf-8")
    # The MCP tools table should mention get_capabilities
    import re
    has_get_capabilities = bool(re.search(r"\|\s*`?get_capabilities`?\s*\|", content))
    assert has_get_capabilities, (
        f"AGENTS.md does not document the get_capabilities MCP tool. "
        f"The MCP tools table needs a row for it."
    )
