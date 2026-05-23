# ORF Phase 1 Plan - WITH Inline Formatting Preservation

**Version**: v1.2  
**Author**: Sisyphus  
**Date**: 2026-05-22  
**Project**: Omni-Re-Formatter (ORF)  
**Goal**: Phase 1 implementation + **Inline Formatting Preservation** for DOCX/PPTX/EPUB/HTML

---

## Context

### What's Changed

**Previous scope**: DOCX only with inline formatting preservation.

**Now**: OPP supports inline formatting tracking for **DOCX, PPTX, EPUB, and HTML**. ORF Phase 1 must preserve formatting across ALL these formats.

### Updated Pipeline Flow

```
OPP (with inline tracking)              OL                    ORF Phase 1
─────────────────────                ─────                 ──────────────

DOCX + XLIFF (with <bx>/<ex>) ──────────────────────→ XLIFF→DOCX (preserve formatting)
PPTX + XLIFF (with <bx>/<ex>) ──────────────────────→ XLIFF→PPTX (preserve formatting)
EPUB + XLIFF (with <bx>/<ex>) ──────────────────────→ XLIFF→EPUB (preserve formatting)
HTML + XLIFF (with <bx>/<ex>) ──────────────────────→ XLIFF→HTML (preserve formatting)
```

**XLIFF inline elements (`<bx>`, `<ex>`) are universal** - the same markup works for all formats. ORF just needs to convert them to the target format's native representation.

---

## Format Coverage Matrix

| Input Format | OPP Tracks Inline | ORF Output | Inline Preservation |
|--------------|-------------------|------------|-------------------|
| **DOCX** + XLIFF | ✅ Bold/Italic/Underline/Strike | DOCX | ✅ `<w:rPr>` |
| **PPTX** + XLIFF | ✅ Bold/Italic/Underline/Strike | PPTX | ✅ `<a:rPr>` |
| **EPUB** + XLIFF | ✅ Bold/Italic/Underline | EPUB | ✅ `<strong>`, `<em>` |
| **HTML** + XLIFF | ✅ Bold/Italic/Underline/Strike | HTML | ✅ `<strong>`, `<em>`, `<u>`, `<s>` |

### Target Format Representations

| Target | Format Element | Example |
|--------|---------------|---------|
| **DOCX** | `<w:rPr><w:b/></w:rPr>` | `<w:r><w:rPr><w:b/></w:rPr><w:t>text</w:t></w:r>` |
| **PPTX** | `<a:rPr b="1"/>` | `<a:r><a:rPr lang="en" b="1"/><a:t>text</a:t></a:r>` |
| **EPUB/HTML** | `<strong>`, `<em>` | `<strong>text</strong>`, `<em>text</em>` |

---

## Task Decomposition

### Wave 1: Foundation

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **1** | `error_handlers/conversion_error.py` | Error classes + recovery strategies | `unspecified-high` | None | ✅ DONE |
| **2** | `skeleton/skeleton_loader.py` | Load skeleton, extract XML, basic backfill | `unspecified-high` | None | ✅ DONE |
| **2b** | `skeleton/inline_formatting.py` | Parse XLIFF inline elements (`<bx>`, `<ex>`) | `unspecified-high` | Task 2 | ✅ DONE |

### Wave 2: XLIFF→DOCX Backfill

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **3** | `channels/xliff2docx.py` | XLIFF→DOCX with inline formatting | `unspecified-high` | Task 2b | ✅ DONE |
| **3t** | `tests/test_xliff2docx_channel.py` | TDD for DOCX backfill | `quick` | Task 3 | ✅ DONE |

### Wave 3: XLIFF→PPTX Backfill (NEW)

| Task | Module | Description | Category | Dependency | Status |
|------|--------|-------------|----------|------------|--------|
| **4** | `channels/xliff2pptx.py` | XLIFF→PPTX with inline formatting | `unspecified-high` | Task 2b | ✅ DONE |
| **4t** | `tests/test_xliff2pptx_channel.py` | TDD for PPTX backfill | `quick` | Task 4 | ✅ DONE |

### Wave 4: XLIFF→EPUB Backfill (NEW)

| Task | Module | Description | Category | Dependency | Status |
|------|--------|-------------|----------|------------|--------|
| **5** | `channels/xliff2epub.py` | XLIFF→EPUB with inline formatting | `unspecified-high` | Task 2b | ✅ DONE |
| **5t** | `tests/test_xliff2epub_channel.py` | TDD for EPUB backfill | `quick` | Task 5 | ✅ DONE |

### Wave 5: XLIFF→HTML Backfill (NEW)

| Task | Module | Description | Category | Dependency | Status |
|------|--------|-------------|----------|------------|--------|
| **6** | `channels/xliff2html.py` | XLIFF→HTML with inline formatting | `unspecified-high` | Task 2b | ✅ DONE |
| **6t** | `tests/test_xliff2html_channel.py` | TDD for HTML backfill | `quick` | Task 6 | ✅ DONE |

### Wave 6: MD Output Channels

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **7** | `channels/md2pptx.py` | MD→PPTX (md2pptx CLI wrapper) | `unspecified-high` | None | ✅ DONE |
| **8** | `channels/xliff2odf.py` | XLIFF→ODF (translate-toolkit) | `unspecified-high` | None | ✅ DONE |
| **7t** | `tests/test_md2pptx_channel.py` | TDD for MD→PPTX | `quick` | Task 7 | ✅ DONE |
| **8t** | `tests/test_xliff2odf_channel.py` | TDD for ODF backfill | `quick` | Task 8 | ✅ DONE |

### Wave 7: CLI & Integration

| Task | Module | Description | Category | Dependency |
|------|--------|-------------|----------|------------|
| **9** | `cli.py` | Add `apply-xliff` command for all formats | `quick` | Tasks 3-6 | ✅ DONE |
| **10** | `tests/test_cli.py` | TDD for CLI | `quick` | Task 9 | ✅ DONE |

---

## Key Implementation Details

### Task 2b: Inline Formatting Infrastructure

**File**: `src/orf/skeleton/inline_formatting.py`

This is the **core shared infrastructure** for all format backfills.

```python
@dataclass
class InlineElement:
    """XLIFF inline element parsed from source text."""
    id: str
    type: str                    # "bold", "italic", "underline", "strike", "bold,italic"
    begin_pos: int               # Character position of <bx>
    end_pos: int                 # Character position of <ex>
    text_covered: Optional[str] = None


class XLIFFInlineParser:
    """Parse XLIFF inline elements from source/target text."""
    
    INLINE_PATTERNS = [
        re.compile(r'<bx[^>]*id="([^"]+)"[^>]*type="([^"]+)"[^>]*/>'),
        re.compile(r'<ex[^>]*id="([^"]+)"[^>]*/>'),
    ]
    
    def parse_source(self, text: str) -> List[InlineElement]:
        """Extract inline elements with begin/end positions."""
        # Returns list of InlineElement with position info
        ...


class InlineFormattingApplier:
    """Base class for applying formatting to different formats."""
    
    def apply_formatting(
        self,
        original_content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply inline formatting to content based on XLIFF elements."""
        raise NotImplementedError


class DOCXInlineApplier(InlineFormattingApplier):
    """Apply formatting to DOCX XML."""
    
    W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    def apply_formatting(
        self,
        document_xml: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply bold/italic/underline to <w:rPr>."""
        # Add <w:b/>, <w:i/>, <w:u/>, <w:strike/> to runs
        ...


class PPTXInlineApplier(InlineFormattingApplier):
    """Apply formatting to PPTX XML."""
    
    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    
    def apply_formatting(
        self,
        slide_xml: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply bold/italic/underline to <a:rPr>."""
        # Add b="1", i="1", u="sng" attributes to run properties
        ...


class EPUBHTMLInlineApplier(InlineFormattingApplier):
    """Apply formatting to EPUB/HTML."""
    
    def apply_formatting(
        self,
        content: str,
        inline_elements: List[InlineElement],
        target_text: str
    ) -> str:
        """Apply <strong>, <em>, <u>, <s> tags."""
        # Convert inline elements to HTML tags
        ...
```

### Task 3: XLIFF→DOCX Converter

**File**: `src/orf/channels/xliff2docx.py`

```python
class XLIFF2DOCXConverter(BaseConverter):
    """XLIFF→DOCX backfill with inline formatting preservation."""
    
    def __init__(self, manifest=None, frontmatter=None):
        super().__init__(manifest, frontmatter)
        self.skeleton_loader = SkeletonLoader()
        self.inline_parser = XLIFFInlineParser()
        self.docx_applier = DOCXInlineApplier()
    
    def convert(
        self,
        input_skeleton: Path | str,
        xliff_path: Path | str,
        output_path: Path | str,
        **options
    ) -> ConversionResult:
        # 1. Load skeleton (original DOCX ZIP)
        skeleton_data = self.skeleton_loader.load_skeleton(Path(input_skeleton))
        document_xml = skeleton_data['xml']
        
        # 2. Parse XLIFF
        xliff_units = self._parse_xliff(Path(xliff_path))
        
        # 3. Backfill each trans-unit
        modified_xml = document_xml
        inline_count = 0
        
        for idx, unit in enumerate(xliff_units):
            target_text = unit.target or unit.source
            
            # Parse inline elements
            inline_elements = self.inline_parser.parse_source(unit.source)
            
            if inline_elements:
                modified_xml = self.docx_applier.apply_formatting(
                    modified_xml, inline_elements, target_text
                )
                inline_count += 1
            else:
                # Plain text replacement
                modified_xml = self.skeleton_loader.backfill_plain(
                    modified_xml, idx, target_text
                )
        
        # 4. Repack as DOCX
        output_path = Path(output_path)
        self.skeleton_loader.repack_docx(modified_xml, output_path)
        
        return ConversionResult(
            output_path=output_path,
            success=True,
            metadata={'inline_elements_applied': inline_count}
        )
```

### Task 4: XLIFF→PPTX Converter

**File**: `src/orf/channels/xliff2pptx.py`

```python
class XLIFF2PPTXConverter(BaseConverter):
    """XLIFF→PPTX backfill with inline formatting preservation."""
    
    # Uses same XLIFF→skeleton approach but for PPTX ZIP
    # Applies formatting via PPTXInlineApplier
    
    P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    
    def convert(self, pptx_skeleton: Path, xliff_path: Path, output_path: Path) -> ConversionResult:
        # Similar flow to DOCX but:
        # - Skeleton is PPTX ZIP
        # - Target XML is ppt/slides/slideN.xml
        # - Formatting via <a:rPr b="1" i="1" u="sng"/>
        ...
```

### Task 5: XLIFF→EPUB Converter

**File**: `src/orf/channels/xliff2epub.py`

```python
class XLIFF2EPUBConverter(BaseConverter):
    """XLIFF→EPUB backfill with inline formatting preservation."""
    
    # EPUB is HTML inside ZIP
    # Formatting via HTML tags: <strong>, <em>
    
    def convert(self, epub_skeleton: Path, xliff_path: Path, output_path: Path) -> ConversionResult:
        # 1. Load EPUB skeleton
        # 2. Parse XLIFF
        # 3. Apply formatting via EPUBHTMLInlineApplier
        # 4. Repack as EPUB
        ...
```

### Task 6: XLIFF→HTML Converter

**File**: `src/orf/channels/xliff2html.py`

```python
class XLIFF2HTMLConverter(BaseConverter):
    """XLIFF→HTML backfill with inline formatting preservation."""
    
    # Pure HTML (no ZIP)
    # Formatting via HTML tags: <strong>, <em>, <u>, <s>
    
    def convert(self, html_template: Path, xliff_path: Path, output_path: Path) -> ConversionResult:
        # 1. Load HTML template
        # 2. Parse XLIFF
        # 3. Apply formatting via EPUBHTMLInlineApplier
        # 4. Save as HTML
        ...
```

---

## CLI Commands (Updated)

### New Commands

```python
@main.command("apply-xliff")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--xliff", "-x", required=True, help="Translated XLIFF file")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--format", "-f", type=click.Choice(["docx", "pptx", "epub", "html", "odt"]), 
              default="docx", help="Output format")
def apply_xliff(input_file: str, xliff: str, output: str, format: str):
    """Apply XLIFF translation to original document.
    
    INPUT_FILE: Original document (DOCX/PPTX/EPUB/HTML)
    """
    if format == "docx":
        converter = XLIFF2DOCXConverter()
    elif format == "pptx":
        converter = XLIFF2PPTXConverter()
    elif format == "epub":
        converter = XLIFF2EPUBConverter()
    elif format == "html":
        converter = XLIFF2HTMLConverter()
    elif format == "odt":
        converter = XLIFF2ODFConverter()
    
    result = converter.convert(input_file, xliff, output)
```

---

## Inline Formatting Mapping

| XLIFF Type | DOCX | PPTX | EPUB/HTML |
|-------------|------|------|------------|
| `bold` | `<w:b/>` | `b="1"` | `<strong>` |
| `italic` | `<w:i/>` | `i="1"` | `<em>` |
| `underline` | `<w:u val="single"/>` | `u="sng"` | `<u>` |
| `strike` | `<w:strike/>` | `strike="1"` | `<s>` |
| `bold,italic` | `<w:b/><w:i/>` | `b="1" i="1"` | `<strong><em>` |

---

## Backward Compatibility

### No Inline Elements

If XLIFF has no `<bx>`/`<ex>` elements, ORF falls back to plain text replacement:
```python
if inline_elements:
    modified_xml = applier.apply_formatting(...)
else:
    modified_xml = skeleton_loader.backfill_plain(...)
```

### OPP Without Inline Tracking

If OPP didn't track formatting (old version), `inline_elements` will be empty:
- Same fallback behavior
- Works without OPP upgrade

---

## Success Criteria

### All Formats
- [x] XLIFF→DOCX works with inline formatting
- [x] XLIFF→PPTX works with inline formatting
- [x] XLIFF→EPUB works with inline formatting
- [x] XLIFF→HTML works with inline formatting
- [x] CLI commands work for all formats
- [x] Error handling system in place

### Inline Formatting
- [x] `XLIFFInlineParser` parses `<bx>` and `<ex>` correctly
- [x] Bold formatting preserved across all formats
- [x] Italic formatting preserved across all formats
- [x] Underline formatting preserved (DOCX/PPTX/HTML)
- [x] Strikethrough formatting preserved (DOCX/HTML)
- [x] Combined formatting (bold+italic) handled

### Performance
- [x] XLIFF→DOCX ≥ 5MB/s
- [x] XLIFF→PPTX ≥ 5MB/s
- [x] XLIFF→EPUB ≥ 5MB/s
- [x] XLIFF→HTML ≥ 10MB/s
- [x] Inline parsing ≤ 1ms per trans-unit

---

## File Changes Summary

| File | Change Type | Lines |
|------|------------|-------|
| `src/orf/skeleton/skeleton_loader.py` | Modify | +100 |
| `src/orf/skeleton/inline_formatting.py` | **NEW** | +250 |
| `src/orf/channels/xliff2docx.py` | **NEW** | +100 |
| `src/orf/channels/xliff2pptx.py` | **NEW** | +100 |
| `src/orf/channels/xliff2epub.py` | **NEW** | +100 |
| `src/orf/channels/xliff2html.py` | **NEW** | +80 |
| `src/orf/channels/xliff2odf.py` | **NEW** | +80 |
| `src/orf/channels/md2pptx.py` | **NEW** | +60 |
| `src/orf/cli.py` | Modify | +50 |
| `tests/test_xliff2docx_channel.py` | **NEW** | +80 |
| `tests/test_xliff2pptx_channel.py` | **NEW** | +80 |
| `tests/test_xliff2epub_channel.py` | **NEW** | +80 |
| `tests/test_xliff2html_channel.py` | **NEW** | +80 |
| `tests/test_xliff2odf_channel.py` | **NEW** | +60 |
| `tests/test_md2pptx_channel.py` | **NEW** | +60 |
| `tests/test_cli.py` | Modify | +60 |
| `tests/test_inline_formatting.py` | **NEW** | +150 |

---

## Timeline

| Wave | Tasks | Description |
|------|-------|-------------|
| Wave 1 | 1-2, 2b | Foundation + inline parser |
| Wave 2 | 3, 3t | XLIFF→DOCX |
| Wave 3 | 4, 4t | XLIFF→PPTX |
| Wave 4 | 5, 5t | XLIFF→EPUB |
| Wave 5 | 6, 6t | XLIFF→HTML |
| Wave 6 | 7-8, 7t-8t | MD→PPTX + ODF |
| Wave 7 | 9-10, 10t | CLI + Integration |

**Estimated Total**: 1.5 days

---

## Commit Strategy

```bash
# Wave 1: Foundation
git commit -m "feat(error_handlers): add ConversionError classes"
git commit -m "feat(skeleton): add SkeletonLoader"
git commit -m "feat(skeleton): add XLIFFInlineParser and format-specific appliers"

# Wave 2: DOCX
git commit -m "feat(channels): add XLIFF2DOCXConverter with inline formatting"

# Wave 3: PPTX
git commit -m "feat(channels): add XLIFF2PPTXConverter with inline formatting"

# Wave 4: EPUB
git commit -m "feat(channels): add XLIFF2EPUBConverter with inline formatting"

# Wave 5: HTML
git commit -m "feat(channels): add XLIFF2HTMLConverter with inline formatting"

# Wave 6: MD + ODF
git commit -m "feat(channels): add MD2PPTXConverter and XLIFF2ODFConverter"

# Wave 7: CLI
git commit -m "feat(cli): add apply-xliff command for all formats"
git commit -m "test: add inline formatting preservation tests"
```

---

## Dependencies

| OPP Task | ORF Task | Connection |
|----------|----------|------------|
| OPP Task 1-2 | ORF Task 2b | `InlineElement` dataclass must match |
| OPP Task 3-4 (DOCX) | ORF Task 3 | XLIFF→DOCX pipeline |
| OPP Task 5a-5b (PPTX) | ORF Task 4 | XLIFF→PPTX pipeline |
| OPP Task 6a-6b (EPUB) | ORF Task 5 | XLIFF→EPUB pipeline |
| OPP Task 7a-7b (HTML) | ORF Task 6 | XLIFF→HTML pipeline |

---

## Related Plans

- **OPP Inline Formatting Tracking**: `/mnt/d/贯维/Omni_Pre_Processor/.omo/plans/inline-formatting-tracking.md`

---

## Implementation Complete ✅

**All 17 implementation tasks completed:**
- Wave 1: Foundation (Tasks 1, 2, 2b) ✅
- Wave 2: XLIFF→DOCX (Tasks 3, 3t) ✅
- Wave 3: XLIFF→PPTX (Tasks 4, 4t) ✅
- Wave 4: XLIFF→EPUB (Tasks 5, 5t) ✅
- Wave 5: XLIFF→HTML (Tasks 6, 6t) ✅
- Wave 6: MD→PPTX + ODF (Tasks 7, 8, 7t, 8t) ✅
- Wave 7: CLI + Tests (Tasks 9, 10) ✅

**All success criteria met:** ✅
- **ORF Phase 0**: `.omo/plans/ORF-Phase0-Implementation.md`