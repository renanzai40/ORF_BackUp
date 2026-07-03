"""Tests for Phase 4 ORF reliability: subprocess timeouts and rId fix."""
import pytest


# --- P4-T1: subprocess timeouts ---

@pytest.mark.parametrize("module_name", [
    "md2pptx",
    "md2docx",
    "md2epub",
    "md2odt",
    "md2rtf",
    "md2icml",
    "xliff2odf",
])
def test_p4_t1_subprocess_has_timeout(module_name):
    """Each subprocess.run call in the 7 target channels must have a timeout= parameter."""
    import importlib
    mod = importlib.import_module(f"orf.channels.{module_name}")
    assert mod.__file__ is not None
    source = open(mod.__file__, "r").read()
    assert "_CONVERSION_TIMEOUT" in source, (
        f"{module_name} missing _CONVERSION_TIMEOUT constant"
    )
    assert "timeout=_CONVERSION_TIMEOUT" in source, (
        f"{module_name} does not use timeout=_CONVERSION_TIMEOUT in subprocess.run"
    )


@pytest.mark.parametrize("module_name", [
    "md2pptx",
    "md2docx",
    "md2epub",
    "md2odt",
    "md2rtf",
    "md2icml",
    "xliff2odf",
])
def test_p4_t1_timeout_expired_handled(module_name):
    """Each module must handle subprocess.TimeoutExpired (catch or have timeout constant)."""
    import importlib
    mod = importlib.import_module(f"orf.channels.{module_name}")
    assert mod.__file__ is not None
    source = open(mod.__file__, "r").read()
    has_handler = "TimeoutExpired" in source
    assert has_handler, (
        f"{module_name} does not handle subprocess.TimeoutExpired"
    )


# --- P4-T2: rId1 fallback ---

def test_p4_t2_no_bare_return_rid1():
    """xliff2docx/images.py must NOT have a bare 'return rId1' without creating rels."""
    from orf.channels.xliff2docx import images
    assert images.__file__ is not None
    source = open(images.__file__, "r").read()
    # The old pattern was: else: return "rId1" (without creating rels file).
    # The fix creates the rels file properly. Verify no bare return exists.
    import re
    # Match "return \"rId1\"" that is NOT preceded by creating a rels entry
    bare_returns = re.findall(r'return\s+["\']rId1["\']', source)
    # Each occurrence should be inside the rels-creation block, not bare
    for match in bare_returns:
        # Find the context — should be inside an else block that creates rels
        idx = source.find(match)
        context = source[max(0, idx-200):idx]
        assert "files[rels_name]" in context, (
            f"Bare 'return \"rId1\"' found without creating rels file at offset {idx}"
        )


def test_p4_t2_add_image_to_zip_creates_rels_when_missing():
    """When rels file is missing, add_image_to_zip should create it, not return rId1."""
    from orf.channels.xliff2docx.images import add_image_to_zip
    # Minimal 1x1 PNG
    img_bytes = (
        b"\x89PNG\r\n\x1a\n"  # PNG signature
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
        b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB"
        b"\x60\x82"
    )
    files = {}
    namelist = []
    rid = add_image_to_zip(img_bytes, "image/png", files, namelist)
    assert rid is not None, "add_image_to_zip returned None when rels file was missing"
    assert "word/_rels/document.xml.rels" in files, (
        "add_image_to_zip did not create the rels file when it was missing"
    )
