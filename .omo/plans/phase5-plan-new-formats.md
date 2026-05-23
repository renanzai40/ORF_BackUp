# ORF Phase 5: New Format Channels Implementation Plan

> DD Vibe Standards: UTDD → ATDD → TDD → BDD
> Based on: Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md
> Phase: 5 (New Formats)
> Last Updated: 2026-05-23

---

## Phase 5 Overview

### Goals

Add support for new output formats to align with OPP input formats:

| Format | Wheel | Output Type | Complexity |
|--------|-------|-------------|------------|
| **XLSX** | `openpyxl` | Spreadsheet | Medium |
| **CSV** | stdlib `csv` | Data file | Low |
| **JSON** | stdlib `json` | Structured data | Low |
| **XML** | stdlib `xml` + `lxml` | Structured markup | Medium |
| **IPYNB** | `nbformat` | Jupyter notebook | Medium |
| **EML** | stdlib `email` | Email message | Medium |
| **MSG** | `aspose-email-foss` | Outlook message | Medium |

### Alignment with DD Vibe Standards

| DD Vibe Principle | Application in Phase 5 |
|-------------------|------------------------|
| **UTDD** | Write ALL unit tests BEFORE writing any converter code |
| **ATDD** | Define acceptance criteria for each format channel |
| **TDD** | Red → Green → Refactor cycle; tests must pass before commit |
| **BDD** | Given-When-Then scenarios for each conversion workflow |

---

## Wave 1: Data Formats (XLSX, CSV, JSON)

### Format Rationale

- **XLSX**: OPP extracts XLSX content as tabular data; ORF reconstructs from MD with markdown tables or JSON blocks
- **CSV**: Direct data exchange format; OPP extracts tabular data; ORF reconstructs from MD table syntax
- **JSON**: OPP extracts structured JSON; ORF reconstructs from JSON blocks in MD or structured data

### BDD Scenarios

#### Scenario: XLSX Channel - Basic Tabular Data

```
Given: OL translated MD file with tabular data extracted by OPP
When: User executes orf apply-md data_zh.md --target-format xlsx --output data_zh.xlsx
Then:
  - XLSX file contains translated content in cells
  - Multiple sheets supported if MD contains sheet separators
  - Cell formatting (bold headers) preserved from source
```

#### Scenario: CSV Channel - Flat Data Export

```
Given: OL translated MD file with CSV content
When: User executes orf apply-md table_zh.md --target-format csv --output table_zh.csv
Then:
  - CSV file contains translated text in UTF-8 encoding
  - Header row preserved if present
  - Comma/semicolon delimiter detected from source
```

#### Scenario: JSON Channel - Structured Data Preservation

```
Given: OL translated JSON extracted from structured document
When: User executes orf apply-md structured_zh.md --target-format json --output structured_zh.json
Then:
  - JSON structure preserved (nested objects/arrays)
  - Translated values replace source values
  - Non-translatable keys (IDs, timestamps) unchanged
```

---

## Wave 2: Markup Formats (XML, IPYNB)

### BDD Scenarios

#### Scenario: XML Channel - MD to XML Conversion

> **NOTE**: This converts MD content to XML representation (not OPP data reconstruction).
> For OPP's XML extraction → use `xliff2xml` or similar pipeline.

```
Given: OL translated MD content
When: User executes orf apply-md doc_zh.md --target-format xml --output doc_zh.xml
Then:
  - MD content converted to basic XML structure
  - Headings become <h1>, <h2>, etc.
  - Paragraphs become <p> elements
  - Lists become <ul>/<ol> with <li> items
  - Tables become <table>/<tr>/<td> elements
  - Original XML structure is NOT preserved (this is MD→XML, not data2xml)
```

**For OPP XML extraction → XML reconstruction**, use a different approach:
```
Given: OPP extracted XML with translated content
When: User applies translations to XML
Then: XML structure preserved with translated values
```

#### Scenario: IPYNB Channel - Jupyter Notebook Reconstruction

```
Given: OPP extracted IPYNB content with OL translated cells
When: User executes orf apply-md notebook_zh.md --target-format ipynb --output notebook_zh.ipynb
Then:
  - Notebook contains markdown and code cells
  - Markdown cells use translated content
  - Code cells preserved as-is
  - Kernel metadata preserved
  - Cell outputs unchanged
```

---

## Wave 3: Email Formats (EML, MSG)

### Email Header Source Clarification

> **CRITICAL**: Email headers (To, From, Subject, Date, CC) are NOT in the MD body.
> They MUST come from manifest or frontmatter. OPP extracts email as EML/MSG with headers stored in manifest.

**Required frontmatter structure for email formats**:
```yaml
email_headers:
  to: "recipient@example.com"
  from: "sender@example.com"
  subject: "Original Subject"
  date: "2026-05-22T10:00:00Z"
  cc: "cc@example.com"
  message_id: "<original-message-id>"
  in_reply_to: "<parent-message-id>"
```

ORF will:
1. Read headers from manifest (if available) or frontmatter
2. Read body from translated MD
3. Reconstruct EML/MSG with original headers + translated body

### BDD Scenarios

#### Scenario: EML Channel - RFC 5322 Email Reconstruction

```
Given: OPP extracted email with manifest containing headers + OL translated MD body
When: User executes orf apply-md email_zh.md --target-format eml --output email_zh.eml
Then:
  - EML file follows RFC 5322 format
  - Headers from manifest/frontmatter (To, From, Subject, Date, CC)
  - Body content from translated MD
  - MIME multipart structure maintained
  - Attachments reference preserved (not extracted)
```

#### Scenario: MSG Channel - Outlook Message Reconstruction

```
Given: OPP extracted email with manifest containing MAPI properties + OL translated MD body
When: User executes orf apply-md outlook_zh.md --target-format msg --output outlook_zh.msg
Then:
  - MSG file is Outlook-compatible
  - MAPI properties from manifest (PR_SENDER_*, PR_RECIPIENT_*)
  - Body content from translated MD
  - Attachments reference preserved
  - Can be converted to EML for portability
```

---

## UTDD - Unit Test Templates (Write BEFORE Implementation)

### Test: md2xlsx_channel.py

```python
class TestMD2XLSXConverter:
    """UTDD for MD to XLSX conversion"""

    def test_supported_format(self):
        """XLSX channel returns 'XLSX' as supported format"""

    def test_validate_input_valid_md(self):
        """Valid .md files pass validation"""

    def test_validate_input_invalid_extension(self):
        """Non-.md files fail validation"""

    def test_convert_success_with_tabular_data(self):
        """MD with table syntax converts to XLSX with cells"""

    def test_convert_preserves_header_formatting(self):
        """First row rendered as bold headers"""

    def test_convert_multiple_sheets(self):
        """MD with sheet separators creates multiple worksheets"""

    def test_convert_empty_md(self):
        """Empty MD produces empty XLSX with single sheet"""

    def test_convert_pandoc_error(self):
        """Pandoc failure produces error result"""

    def test_metadata_includes_sheet_count(self):
        """ConversionResult metadata has sheet_count"""
```

### Test: md2csv_channel.py

```python
class TestMD2CSVConverter:
    """UTDD for MD to CSV conversion"""

    def test_supported_format(self):
        """CSV channel returns 'CSV' as supported format"""

    def test_convert_simple_table(self):
        """MD table converts to single CSV file"""

    def test_convert_preserves_header_row(self):
        """First row treated as header"""

    def test_convert_delimiter_detection(self):
        """Detects comma vs semicolon from source"""

    def test_convert_empty_table(self):
        """Empty table produces empty CSV"""

    def test_convert_non_table_md(self):
        """MD without tables produces minimal CSV"""
```

### Test: md2json_channel.py

```python
class TestMD2JSONConverter:
    """UTDD for MD to JSON conversion"""

    def test_supported_format(self):
        """JSON channel returns 'JSON' as supported format"""

    def test_convert_preserves_structure(self):
        """Nested objects/arrays preserved"""

    def test_convert_translates_values_only(self):
        """Keys unchanged, only values translated"""

    def test_convert_array_handling(self):
        """Arrays preserved with correct ordering"""

    def test_convert_invalid_json_md(self):
        """MD not parseable as JSON produces error"""
```

### Test: md2xml_channel.py

```python
class TestMD2XMLConverter:
    """UTDD for MD to XML conversion"""

    def test_supported_format(self):
        """XML channel returns 'XML' as supported format"""

    def test_convert_preserves_namespaces(self):
        """XML namespaces preserved from source"""

    def test_convert_preserves_attributes(self):
        """Element attributes maintained"""

    def test_convert_cdata_sections(self):
        """CDATA sections preserved"""

    def test_convert_invalid_xml_structure(self):
        """Non-XML MD produces error result"""
```

### Test: md2ipynb_channel.py

```python
class TestMD2IPYNBConverter:
    """UTDD for MD to IPYNB conversion"""

    def test_supported_format(self):
        """IPYNB channel returns 'IPYNB' as supported format"""

    def test_convert_markdown_cells(self):
        """MD content becomes markdown cells"""

    def test_convert_code_cells_preserved(self):
        """Code blocks become code cells unchanged"""

    def test_convert_preserves_kernel_metadata(self):
        """kernel spec and language info preserved"""

    def test_convert_empty_notebook(self):
        """Empty MD produces minimal notebook"""

    def test_convert_nbformat_version(self):
        """Output uses nbformat v4"""
```

### Test: md2eml_channel.py

```python
class TestMD2EMLConverter:
    """UTDD for MD to EML conversion"""

    def test_supported_format(self):
        """EML channel returns 'EML' as supported format"""

    def test_convert_preserves_headers(self):
        """To, From, Subject, Date headers preserved"""

    def test_convert_body_translated(self):
        """Email body content translated"""

    def test_convert_multipart_structure(self):
        """Multipart MIME structure maintained"""

    def test_convert_missing_headers(self):
        """Missing headers handled gracefully"""
```

### Test: md2msg_channel.py

```python
class TestMD2MSGConverter:
    """UTDD for MD to MSG conversion"""

    def test_supported_format(self):
        """MSG channel returns 'MSG' as supported format"""

    def test_convert_mapi_properties(self):
        """MAPI properties preserved"""

    def test_convert_body_translated(self):
        """MSG body content translated"""

    def test_convert_can_convert_to_eml(self):
        """MSG convertible to EML format"""
```

---

## ATDD - Acceptance Criteria by Format

### Input Detection Logic

For XLSX, CSV, JSON - the MD input may contain different structures:

| MD Contains | Detection | Action |
|-------------|-----------|--------|
| Markdown table syntax (\| -- \| -- \|) | Regex | Parse markdown table → cells |
| JSON code block (\`\`\`json ... \`\`\`) | Regex | Extract JSON → write directly |
| CSV code block (\`\`\`csv ... \`\`\`) | Regex | Extract CSV → write directly |
| Raw tabular data | First line check | Write as single sheet |

Converter should detect input type and process accordingly.

### XLSX Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Conversion success rate | ≥ 95% for valid MD input |
| Sheet count accuracy | 100% match for multi-sheet MD |
| Header formatting | Bold font preserved |
| Cell encoding | UTF-8 for international characters |
| Performance | ≤ 5MB/s for files < 50MB |

### CSV Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Delimiter detection accuracy | ≥ 99% |
| Header row preserved | 100% |
| Encoding | UTF-8 with BOM option |
| Row count | Matches table row count |
| Performance | ≤ 10MB/s |

### JSON Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Structure preservation | 100% match |
| Value translation | All translatable values replaced |
| Key preservation | All keys unchanged |
| Valid JSON output | 100% (parseable) |
| Performance | ≤ 20MB/s |

### XML Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Namespace preservation | 100% |
| Attribute preservation | 100% |
| CDATA preservation | 100% |
| Valid XML output | 100% |
| Performance | ≤ 10MB/s |

### IPYNB Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Cell count match | 100% |
| Markdown cell translation | 100% |
| Code cell preservation | 100% (no modification) |
| Kernel metadata | Preserved |
| Valid notebook | Opens in Jupyter |
| Performance | ≤ 5MB/s |

### EML Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| RFC 5322 compliance | 100% |
| Header from manifest/frontmatter | 100% |
| Header preservation | 100% (must come from metadata, not MD) |
| Body translation | 100% |
| MIME structure | Valid |
| Attachment reference | Preserved |
| Performance | ≤ 2MB/s |

### MSG Acceptance Criteria

| Criteria | Metric |
|----------|--------|
| Outlook compatibility | Opens in Outlook |
| MAPI properties | Preserved |
| Body translation | 100% |
| EML conversion | Valid |
| Performance | ≤ 2MB/s |

---

## TDD Implementation Cycle

### Cycle for Each Format

```
🔴 RED (Week 1-2):
  1. Write ALL unit tests for format channel (UTDD)
  2. Write ATDD acceptance tests
  3. Verify all tests FAIL (proves tests are valid)

🟢 GREEN (Week 3-4):
  1. Implement format converter
  2. Run tests
  3. Fix failures
  4. Repeat until all pass

🔄 REFACTOR (Week 5):
  1. Code review for quality
  2. Extract common base class if applicable
  3. Verify tests still pass
```

### Agent Assignment

| Agent | Formats |
|-------|---------|
| `quick` | CSV, JSON (stdlib-based, simplest first) |
| `unspecified-high` | XLSX, XML, IPYNB |
| `unspecified-high` | EML, MSG |

---

## File Structure Additions

```
src/orf/channels/
├── md2xlsx.py          # Wave 1
├── md2csv.py           # Wave 1
├── md2json.py          # Wave 1
├── md2xml.py           # Wave 2
├── md2ipynb.py         # Wave 2
├── md2eml.py           # Wave 3
└── md2msg.py           # Wave 3

tests/
├── test_md2xlsx_channel.py      # Wave 1
├── test_md2csv_channel.py       # Wave 1
├── test_md2json_channel.py      # Wave 1
├── test_md2xml_channel.py       # Wave 2
├── test_md2ipynb_channel.py     # Wave 2
├── test_md2eml_channel.py       # Wave 3
└── test_md2msg_channel.py      # Wave 3
```

---

## Dependencies to Add

```toml
[project.optional-dependencies]
office = [
    "openpyxl>=3.0.0",   # XLSX output
]
notebook = [
    "nbformat>=5.0.0",  # IPYNB output
]
email-output = [
    "aspose-email-foss>=24.0.0",  # MSG output (MIT licensed)
]
# Note: CSV, JSON, XML, EML use stdlib only
```

---

## Parallel Execution Graph

```
Wave 1 (Data Formats):
├── P5.1.1 (quick): test_md2csv_channel.py
├── P5.1.2 (quick): md2csv.py implementation
├── P5.1.3 (quick): test_md2json_channel.py
├── P5.1.4 (quick): md2json.py implementation
├── P5.1.5 (unspecified-high): test_md2xlsx_channel.py
├── P5.1.6 (unspecified-high): md2xlsx.py implementation

Wave 2 (Markup Formats):
├── P5.2.1 (unspecified-high): test_md2xml_channel.py
├── P5.2.2 (unspecified-high): md2xml.py implementation
├── P5.2.3 (unspecified-high): test_md2ipynb_channel.py
├── P5.2.4 (unspecified-high): md2ipynb.py implementation

Wave 3 (Email Formats):
├── P5.3.1 (unspecified-high): test_md2eml_channel.py
├── P5.3.2 (unspecified-high): md2eml.py implementation
├── P5.3.3 (unspecified-high): test_md2msg_channel.py
├── P5.3.4 (unspecified-high): md2msg.py implementation
```

---

## Success Criteria Summary

| Wave | Format | Criteria |
|------|--------|----------|
| Wave 1 | CSV | All UTDD tests pass; ATDD acceptance met |
| Wave 1 | JSON | All UTDD tests pass; ATDD acceptance met |
| Wave 1 | XLSX | All UTDD tests pass; ATDD acceptance met |
| Wave 2 | XML | All UTDD tests pass; ATDD acceptance met |
| Wave 2 | IPYNB | All UTDD tests pass; ATDD acceptance met |
| Wave 3 | EML | All UTDD tests pass; ATDD acceptance met |
| Wave 3 | MSG | All UTDD tests pass; ATDD acceptance met |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| openpyxl memory issues with large XLSX | Use write_only mode; warn on >100MB |
| XML preservation edge cases | Validate output; fallback to plain text |
| IPYNB kernel metadata loss | Require explicit kernel specification in manifest |
| EML header source unclear | Must come from manifest/frontmatter (not MD) |
| MSG MAPI properties complex | Use aspose-email-foss; fallback to EML |
| Email formats need manifest changes | Coordinate with OPP to store headers in manifest |

---

## Related Documents

- Main plan: `Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md`
- DD Vibe standards: `DD Vibe.txt`
- Phase 4 plan: `.omo/plans/phase4-plan-agent-oriented.md`

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| v1.1 | 2026-05-24 | Clarify EML/MSG headers from manifest, not MD; XML is MD→XML not data2xml; XLSX/CSV/JSON input detection |
| v1.0 | 2026-05-23 | Initial Phase 5 plan with DD Vibe standards (UTDD→ATDD→TDD→BDD) |