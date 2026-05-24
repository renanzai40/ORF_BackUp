# Omni-Re-Formatter (ORF) Phase 4 Implementation Plan

> Agent-Oriented Implementation Plan
> Based on: Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md
> Phase: 4 of 4 (Final Phase)
> Last Updated: 2026-05-23

---

## Phase 4 Overview

### Goals

1. **Streaming/Chunked Conversion** - For超大文件，避免 Pandoc OOM
2. **Format Extensions** - InDesign ICML, SRT subtitles support
3. **Cloud Integration** - AWS S3, Azure Blob direct resource I/O
4. **AI-Assisted Layout** - Vision model for automatic overflow correction

### Current State (Phases 0-4 Complete)

| Component | Status | Key Files |
|-----------|--------|-----------|
| **MD Channels** | ✅ Done | `md2docx.py`, `md2odt.py`, `md2epub.py`, `md2html.py`, `md2rtf.py`, `md2pdf.py`, `md2icml.py`, `md2srt.py` |
| **XLIFF Channels** | ✅ Done | `xliff2docx.py`, `xliff2pptx.py`, `xliff2epub.py`, `xliff2html.py`, `xliff2odf.py` |
| **Format Detection** | ✅ Done | `format_detector.py`, `magic_bytes.py` |
| **Resource Management** | ✅ Done | `image_manager.py`, `path_resolver.py` |
| **Skeleton Loader** | ✅ Done | `skeleton_loader.py`, `inline_formatting.py` |
| **Streaming Conversion** | ✅ Done | `stream_converter.py`, `chunked_md_converter.py` |
| **Cloud Integration** | ✅ Done | `s3_client.py`, `azure_blob_client.py`, `cloud_resource_manager.py` |
| **AI Layout** | ✅ Done | `layout_analyzer.py`, `overflow_corrector.py` |
| **CLI** | ✅ Done | `cli.py` (4 commands: apply-md, apply-xliff, convert-batch, info) |
| **Tests** | ✅ Done | 25 test files, 199+ passing, 7 pre-existing failures |
| **Packaging** | ✅ Done | `pyproject.toml` with `[project.scripts]` entry point |

### Key Changes from Original Plan (Technical Debt Section)

Per lines 631-636 of the development plan:

1. **Streaming/Chunked Conversion** - Add streaming base class for large files
2. **Format Extensions** - Add ICML (InDesign) and SRT (subtitles) channels
3. **Cloud Integration** - Add S3/Azure Blob clients
4. **AI-Assisted Layout** - Add vision-based overflow detection

---

## Wave 1: Streaming Conversion (Parallel)

### P4.1.1: Add StreamingConverter Base Class

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/converters/stream_converter.py` with chunked processing base class
- **Verify**:
  - `StreamChunk` dataclass with index, content, size properties
  - `StreamingConverter` abstract base class with `convert_stream()` method
  - Progress callback support for chunk processing
  - Memory-efficient chunk iteration
- **Success Criteria**: `convert_stream()` processes file in chunks without loading entire file into memory
- **Status**: ✅ DONE

### P4.1.2: Add ChunkedMDConverter

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/converters/chunked_md_converter.py` for 1000+ page documents
- **Verify**:
  - Splits MD by H2 headers to preserve section structure
  - Configurable chunk size (default 64KB)
  - Merges chunks preserving header boundaries
- **Success Criteria**: Documents >10MB process without OOM; output identical to non-streaming for small files
- **Status**: ✅ DONE

### P4.1.3: Write test_stream_converter.py

- **Agent**: `quick`
- **Task**: Create TDD tests for streaming conversion
- **Test Cases**:
  - `test_stream_chunk_properties` - index, content, size
  - `test_split_chunks_by_header` - H2 boundary splitting
  - `test_merge_chunks_preserves_structure` - output equals input
  - `test_progress_callback_called` - callback receives (current, total)
- **Success Criteria**: All tests pass; 100% coverage on stream_converter.py
- **Status**: ✅ DONE

---

## Wave 2: Format Extensions (Parallel)

### P4.2.1: Add MD2ICMLConverter

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/channels/md2icml.py` for InDesign ICML output
- **Verify**:
  - Uses `pandoc --to icml`
  - Inherits `BaseConverter` correctly
  - Returns `ConversionResult` with metadata
- **Success Criteria**: `pandoc input.md -o output.icml` produces valid ICML file
- **Status**: ✅ DONE

### P4.2.2: Add MD2SRTConverter

- **Agent**: `quick`
- **Task**: Create `src/orf/channels/md2srt.py` for subtitle extraction
- **Verify**:
  - Parses MD with SRT blocks (timestamp lines)
  - Cleans MD formatting from subtitle text
  - Outputs valid SRT format
- **Success Criteria**: MD with `00:00:01 --> 00:00:03` blocks converts to valid SRT
- **Status**: ✅ DONE

### P4.2.3: Write test_md2icml_channel.py

- **Agent**: `quick`
- **Task**: Create TDD tests for ICML channel
- **Test Cases**:
  - `test_supported_format` - returns "ICML"
  - `test_validate_input_valid` - .md files accepted
  - `test_convert_success` - pandoc icml call
  - `test_convert_pandoc_error` - error handling
- **Success Criteria**: All tests pass
- **Status**: ✅ DONE

### P4.2.4: Write test_md2srt_channel.py

- **Agent**: `quick`
- **Task**: Create TDD tests for SRT channel
- **Test Cases**:
  - `test_supported_format` - returns "SRT"
  - `test_extract_srt_blocks` - parses timed blocks
  - `test_clean_subtitle_text` - removes MD formatting
  - `test_no_srt_blocks_returns_original` - passthrough for non-timed MD
- **Success Criteria**: All tests pass
- **Status**: ✅ DONE

---

## Wave 3: Cloud Integration (Parallel)

### P4.3.1: Add S3ResourceClient

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/cloud/s3_client.py` for AWS S3 operations
- **Verify**:
  - `download(key, dest)` - downloads to local path
  - `upload(source, key)` - uploads to S3
  - `exists(key)` - checks if blob exists
  - `list_resources(prefix)` - lists under prefix
- **Success Criteria**: `S3ResourceClient(bucket="x").download("key", Path("dest"))` works
- **Status**: ✅ DONE

### P4.3.2: Add AzureBlobResourceClient

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/cloud/azure_blob_client.py` for Azure Blob operations
- **Verify**:
  - Same interface as S3ResourceClient
  - Uses `azure.storage.blob.BlobServiceClient`
- **Success Criteria**: `AzureBlobResourceClient(connection_string="x", container="y").download("key", Path("dest"))` works
- **Status**: ✅ DONE

### P4.3.3: Add CloudResourceManager

- **Agent**: `unspecified-high`
- **Task**: Create `src/orf/cloud/cloud_resource_manager.py` unified interface
- **Verify**:
  - Constructor takes `provider="s3"|"azure"` + config dict
  - `download_resource(remote, local)` delegates to provider
  - `upload_resource(local, remote)` delegates to provider
  - `resource_exists(remote)` checks existence
  - `list_resources(prefix)` lists resources
- **Success Criteria**: Same code works with both S3 and Azure by changing provider
- **Status**: ✅ DONE

### P4.3.4: Write test_cloud_clients.py

- **Agent**: `quick`
- **Task**: Create TDD tests for cloud integration
- **Test Cases**:
  - `test_s3_client_download` - mocked boto3
  - `test_s3_client_upload` - mocked boto3
  - `test_azure_client_download` - mocked BlobServiceClient
  - `test_cloud_manager_s3` - unified interface with S3
  - `test_cloud_manager_azure` - unified interface with Azure
- **Success Criteria**: All tests pass with mocked clients
- **Status**: ✅ DONE

---

## Wave 4: AI-Assisted Layout (Parallel)

### P4.4.1: Add LayoutAnalyzer

- **Agent**: `artistry`
- **Task**: Create `src/orf/ai/layout_analyzer.py` for overflow detection
- **Verify**:
  - `analyze(document_path)` returns list of `OverflowIssue`
  - `OverflowIssue` dataclass with file_path, element_id, overflow_percentage, severity
  - Renders document to images for vision analysis
  - Calls vision API to detect overflow
- **Success Criteria**: `LayoutAnalyzer().analyze(docx_path)` returns issues with overflow_percentage > 0
- **Status**: ✅ DONE

### P4.4.2: Add OverflowCorrector

- **Agent**: `artistry`
- **Task**: Create `src/orf/ai/overflow_corrector.py` for text adjustment
- **Verify**:
  - `correct_document(path, max_overflow)` fixes overflow issues
  - `estimate_expansion_ratio(text, source_lang, target_lang)` returns ratio
  - Uses LLM to suggest shorter translation
- **Success Criteria**: Corrected text fits within container (overflow_percentage < max_overflow)
- **Status**: ✅ DONE

### P4.4.3: Write test_layout_analyzer.py

- **Agent**: `unspecified-high`
- **Task**: Create TDD tests for AI layout correction
- **Test Cases**:
  - `test_overflow_issue_dataclass` - fields populated correctly
  - `test_estimate_expansion_ratio_en_zh` - returns ~1.8
  - `test_estimate_expansion_ratio_en_de` - returns ~1.25
  - `test_analyze_returns_issues` - mocked vision API
  - `test_correct_document_fixes_overflow` - mocked LLM
- **Success Criteria**: All tests pass with mocked AI providers
- **Status**: ✅ DONE

---

## Agent Assignment Summary

| Agent | Tasks |
|-------|-------|
| `artistry` | P4.4.1, P4.4.2 |
| `unspecified-high` | P4.1.1, P4.1.2, P4.2.1, P4.3.1, P4.3.2, P4.3.3, P4.4.3 |
| `quick` | P4.1.3, P4.2.2, P4.2.3, P4.2.4, P4.3.4 |

---

## Parallel Execution Graph

```
Wave 1 (Streaming):
├── P4.1.1 (unspecified-high): StreamingConverter base class
├── P4.1.2 (unspecified-high): ChunkedMDConverter
└── P4.1.3 (quick): test_stream_converter.py

Wave 2 (Format Extensions):
├── P4.2.1 (unspecified-high): MD2ICMLConverter
├── P4.2.2 (quick): MD2SRTConverter
├── P4.2.3 (quick): test_md2icml_channel.py
└── P4.2.4 (quick): test_md2srt_channel.py

Wave 3 (Cloud Integration):
├── P4.3.1 (unspecified-high): S3ResourceClient
├── P4.3.2 (unspecified-high): AzureBlobResourceClient
├── P4.3.3 (unspecified-high): CloudResourceManager
└── P4.3.4 (quick): test_cloud_clients.py

Wave 4 (AI Layout):
├── P4.4.1 (artistry): LayoutAnalyzer
├── P4.4.2 (artistry): OverflowCorrector
└── P4.4.3 (unspecified-high): test_layout_analyzer.py
```

---

## File Structure (Phase 4 Additions)

```
src/orf/
├── converters/
│   ├── stream_converter.py        # P4.1.1
│   ├── chunked_md_converter.py    # P4.1.2
│   └── base.py                    # Existing
├── channels/
│   ├── md2icml.py                 # P4.2.1
│   ├── md2srt.py                  # P4.2.2
│   └── ... (existing)
├── cloud/                         # NEW
│   ├── __init__.py                # P4.3.3
│   ├── s3_client.py              # P4.3.1
│   ├── azure_blob_client.py       # P4.3.2
│   └── cloud_resource_manager.py # P4.3.3
├── ai/                            # NEW
│   ├── __init__.py               # P4.4.1
│   ├── layout_analyzer.py         # P4.4.1
│   └── overflow_corrector.py     # P4.4.2
└── ... (existing)
```

**Test additions**:
```
tests/
├── test_stream_converter.py       # P4.1.3
├── test_md2icml_channel.py       # P4.2.3
├── test_md2srt_channel.py        # P4.2.4
├── test_cloud_clients.py         # P4.3.4
└── test_layout_analyzer.py        # P4.4.3
```

---

## Dependencies to Add

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
aws = ["boto3>=1.34.0"]
azure = ["azure-storage-blob>=12.19.0"]
ai = ["openai>=1.12.0"]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "ruff>=0.1.0",
    "mypy>=1.5.0",
    "weasyprint>=60.0",
    "boto3>=1.34.0",
    "azure-storage-blob>=12.19.0",
    "openai>=1.12.0",
]
```

---

## Success Criteria Summary

| Wave | Criteria |
|------|----------|
| **Wave 1 (Streaming)** | Documents >10MB process without OOM; Progress callback reports chunk processing; Output identical to non-streaming for small files |
| **Wave 2 (Format)** | MD→ICML produces valid InCopy markup; MD→SRT extracts timed subtitles correctly |
| **Wave 3 (Cloud)** | S3/Azure download/upload works; CloudResourceManager unifies both providers |
| **Wave 4 (AI)** | Overflow detection identifies text exceeding containers; Correction suggestions fit within layout |

---

## Non-Functional Requirements

- Streaming chunk processing ≤ 64KB per chunk
- Cloud client operations timeout after 30s
- AI layout analysis requires API key configuration
- All new converters inherit BaseConverter properly

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Pandoc ICML output not compatible with all InDesign versions | Provide fallback to PDF; add validation step |
| Cloud credentials not available in CI | Mock S3/Azure clients in tests |
| AI API costs for layout analysis | Add `dry_run` mode; require explicit opt-in |
| Streaming breaks markdown structure | Split on H2 headers only; merge preserves boundaries |

---

## Related Documents

- Main plan: `Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md` (Technical Debt section: lines 631-636)
- Phase 3 plan: `.omo/plans/ORF-Phase3-Implementation.md`
- Phase 2 plan: `.omo/plans/phase2-plan-agent-oriented.md`

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-05-23 | Initial Phase 4 plan with hierarchical task IDs, inline success criteria, AI/Cloud/Streaming/Format scopes |
| v0.1 | 2026-05-23 | Draft with flat task IDs (P4-1 format) |