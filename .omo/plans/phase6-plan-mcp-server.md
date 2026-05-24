# ORF Phase 6 Plan - MCP Server Implementation

**Version**: v1.0
**Author**: Sisyphus
**Date**: 2026-05-24
**Project**: Omni-Re-Formatter (ORF)
**Goal**: Transform ORF into an agent-facing tool with MCP server for AI agent integration

---

## Context

### Why MCP (Model Context Protocol)?

Based on research across OPP, OL, and the broader ecosystem:

| Criterion | ORF Reality | MCP Fit |
|-----------|-------------|---------|
| Document operations are stateful | Yes - multi-step conversion | ✅ MCP persistent connections |
| Structured formats (DOCX/PPTX) | Yes - complex binary formats | ✅ MCP typed schemas |
| Agents need tool discovery | Yes - dynamic operation finding | ✅ MCP `tools/list` |
| Human-oriented CLI | Yes - click.echo everywhere | ❌ CLI alone |
| Token efficiency critical? | No | Neutral |

**Decision**: MCP wins over SKILL because:
1. Document state spans multiple operations (read skeleton → apply XLIFF → inject formatting → repack)
2. Agents need typed schemas to avoid 38% failure rate from schema mismatches
3. MCP servers exist for document processing (docx-mcp, mcp-pandoc, docgem-mcp)

**Reference**: OPP has MCP server at `src/opp/mcp/server.py` - pattern to follow.

---

### Current State

| Component | Status | Key Files |
|-----------|--------|-----------|
| **CLI** | ✅ Done | `src/orf/cli.py` (4 commands) |
| **ConversionResult** | ⚠️ Needs Fix | `errors` is `list[str]`, needs `ErrorDetail` |
| **RecoveryStrategy** | ✅ Done | `conversion_error.py` (6 strategies) |
| **Logging** | ✅ Done | `logging/__init__.py` (needs audit enhancement) |
| **Phase Plans** | ✅ Done | phase1-5 exist, phase4 COMPLETED |

### Critical Issue Found

`ConversionResult.errors` is currently `list[str]` - this is wrong for MCP. Must be `list[ErrorDetail]` with `code`, `message`, `recovery_strategy` to prevent 38% schema mismatch failure.

---

## Phase 6 Scope

### Tasks

| Task | Description | Category | Dependency |
|------|-------------|----------|------------|
| **P6-0** | Add `--json` output mode + Fix ConversionResult types | `quick` | None | ✅ DONE |
| **P6-1** | Create ORF MCP Server scaffold | `deep` | P6-0 | ✅ DONE |
| **P6-2** | Add MCP tools with typed schemas | `unspecified-high` | P6-1 | ✅ DONE |
| **P6-5** | Add Foreman agent for job orchestration | `artistry` | P6-2 | ✅ DONE |
| **P6-6** | Add Specialist agents for format channels | `artistry` | P6-5 | ✅ DONE |
| **P6-7** | Add HITL (Human-in-the-Loop) approval | `unspecified-high` | P6-5 | ✅ DONE |
| **P6-8** | Add audit trail logging (enhance existing) | `quick` | None | ✅ DONE |
| **P6-9** | Integration tests for MCP server | `quick` | P6-2 | ✅ DONE |
| **P6-10** | E2E tests OPP→OL→ORF pipeline | `unspecified-high` | P6-9 | ✅ DONE |

---

## Task Decomposition

### P6-0: Add `--json` output mode + Fix ConversionResult types

**Depends**: None
**Category**: `quick`
**Blocks**: P6-1

**What**:
1. Add `--json` flag to all 4 CLI commands in `src/orf/cli.py`:
   - `apply-md --json`
   - `apply-xliff --json`
   - `convert-batch --json`
   - `info --json`

2. Fix `ConversionResult.errors` type in `src/orf/converters/base.py`:
   ```python
   @dataclass
   class ErrorDetail:
       code: str  # e.g., "SKELETON_NOT_FOUND"
       message: str
       recovery_strategy: Optional[RecoveryStrategy] = None
   
   @dataclass
   class WarningDetail:
       code: str
       message: str
   
   # ConversionResult:
   errors: list[ErrorDetail] = field(default_factory=list)
   warnings: list[WarningDetail] = field(default_factory=list)
   ```

3. Update CLI to use new typed errors:
   ```python
   if output_json:
       click.echo(json.dumps({
           'success': result.success,
           'output_path': str(result.output_path),
           'errors': [{'code': e.code, 'message': e.message, 'recovery_strategy': e.recovery_strategy.value if e.recovery_strategy else None} for e in result.errors],
           'warnings': [{'code': w.code, 'message': w.message} for w in result.warnings],
           'metadata': result.metadata
       }, indent=2))
   ```

**Verify**:
- `orf apply-md doc.md --format docx --json` returns valid JSON
- JSON contains typed `errors` array with `code` field
- Invalid input returns typed error (not human hint)

---

### P6-1: Create ORF MCP Server scaffold

**Depends**: P6-0
**Category**: `deep`
**Blocks**: P6-2

**What**:
1. Create `src/orf/mcp/` directory structure
2. Create `src/orf/mcp/__init__.py`
3. Create `src/orf/mcp/server.py` with FastMCP:
   ```python
   from fastmcp import FastMCP
   
   _mcp: Optional[FastMCP] = None
   
   def get_server() -> FastMCP:
       global _mcp
       if _mcp is None:
           _mcp = FastMCP("ORF MCP Server")
           # Register tools
       return _mcp
   
   def main():
       server = get_server()
       server.run()
   ```
4. Create `src/orf/mcp/config.py`:
   ```python
   from dataclasses import dataclass
   
   @dataclass
   class MCPConfig:
       host: str = "127.0.0.1"
       port: int = 8765
       max_file_size_mb: int = 100
       timeout_seconds: int = 30
   ```
5. Add entry point to `pyproject.toml`:
   ```toml
   [project.scripts]
   orf = "orf.cli:main"
   orf-mcp-server = "orf.mcp.server:main"
   ```

**Verify**:
- `python -m orf.mcp.server` starts without error
- `uvx orf-mcp-server` works
- Server responds to `tools/list` with empty list (no tools yet)

---

### P6-2: Add MCP tools with typed schemas

**Depends**: P6-1
**Category**: `unspecified-high`
**Blocks**: P6-9

**What**:
1. Create `src/orf/mcp/schemas.py` with Pydantic models:
   ```python
   from pydantic import BaseModel
   from typing import Optional
   
   class ApplyMdInput(BaseModel):
       input_md: str
       target_format: str
       output_path: Optional[str] = None
   
   class ApplyMdResult(BaseModel):
       success: bool
       output_path: Optional[str]
       errors: list[ErrorDetail]
       warnings: list[WarningDetail]
       metadata: dict
   
   class ApplyXLIFFInput(BaseModel):
       input_file: str
       xliff_path: str
       output_path: str
       format: str
   
   class ApplyXLIFFResult(BaseModel):
       success: bool
       output_path: Optional[str]
       errors: list[ErrorDetail]
       warnings: list[WarningDetail]
       metadata: dict
   
   class BatchConvertInput(BaseModel):
       input_dir: str
       target_format: str
       pattern: str = "*.md"
   
   class BatchResult(BaseModel):
       success_count: int
       fail_count: int
       errors: list[ErrorDetail]
   
   class DetectFormatInput(BaseModel):
       file_path: str
   
   class DetectFormatResult(BaseModel):
       format: str
       confidence: float
   
   class InfoInput(BaseModel):
       file_path: str
   
   class InfoResult(BaseModel):
       format: str
       size_mb: float
       manifest_status: str
       resource_count: Optional[int]
   ```

2. Implement 5 MCP tools in `server.py`:
   - `apply_md` - Convert MD to target format
   - `apply_xliff` - Apply XLIFF translation
   - `batch_convert` - Batch convert MD files
   - `detect_format` - Detect document format
   - `info` - Get document info

3. Create `src/orf/mcp/security.py`:
   ```python
   from pathlib import Path
   
   class PathValidator:
       """Validate paths to prevent directory traversal."""
       
       ALLOWED_EXTENSIONS = {'.md', '.docx', '.pptx', '.xliff', '.xml', '.html'}
       
       @staticmethod
       def validate(path: Path, base_dir: Path) -> bool:
           resolved = path.resolve()
           return resolved.is_relative_to(base_dir)
   ```

**Verify**:
- All tools return valid JSON against Pydantic schemas
- Path traversal returns error (not allowed)
- Invalid format returns typed error

---

### P6-5: Add Foreman agent for job orchestration

**Depends**: P6-2
**Category**: `artistry`
**Blocks**: P6-6, P6-7

**What**:
1. Create `src/orf/agents/__init__.py`
2. Create `src/orf/agents/foreman.py`:
   ```python
   """Foreman Agent - Job orchestration supervisor."""
   
   from typing import Optional
   from enum import Enum
   
   class JobComplexity(Enum):
       SIMPLE = 1      # Single file, known format
       MODERATE = 2    # Batch, or unknown format
       COMPLEX = 3     # Multi-format, large files
   
   class ForemanAgent:
       """Orchestrates conversion jobs, delegates to Specialists."""
       
       def __init__(self):
           self.specialists = self._init_specialists()
       
       def decompose_job(self, job_request: dict) -> list[dict]:
           """Analyze job, decompose into subtasks."""
           complexity = self._assess_complexity(job_request)
           if complexity == JobComplexity.SIMPLE:
               return [job_request]
           # Route to appropriate specialists
           ...
       
       def handle_error(self, error: ErrorDetail) -> RecoveryStrategy:
           """Decide recovery strategy for error."""
           ...
   ```

**Reference**: Phase2 plan has detailed Foreman patterns - reference that, don't reinvent.

**Verify**:
- Foreman correctly routes simple jobs to single specialist
- Foreman correctly decomposes complex jobs
- Recovery strategy applied per error type

---

### P6-6: Add Specialist agents for format channels

**Depends**: P6-5
**Category**: `artistry`
**Blocks**: None

**What**:
Create `src/orf/agents/specialists/` directory with:

| Specialist | Formats | Responsibility |
|-----------|---------|----------------|
| `format_specialist.py` | DOCX, PPTX, ODT, EPUB | Office format with skeleton backfill |
| `data_specialist.py` | XLSX, CSV, JSON | Data format conversion |
| `markup_specialist.py` | XML, HTML | Markup format conversion |
| `email_specialist.py` | EML, MSG | Email format reconstruction |

Each specialist:
```python
class FormatSpecialist:
    """Handles DOCX/PPTX/ODT/EPUB conversions."""
    
    def can_handle(self, format: str) -> bool:
        return format in ['docx', 'pptx', 'odt', 'epub']
    
    def convert(self, input_path: Path, output_path: Path, **options) -> ConversionResult:
        """Delegate to appropriate channel."""
        ...
    
    def get_capabilities(self) -> dict:
        return {
            'formats': ['docx', 'pptx', 'odt', 'epub'],
            'supports_skeleton': True,
            'supports_inline_formatting': True
        }
```

**Reference**: Phase2 plan patterns - reference, don't reinvent.

**Verify**:
- Each specialist handles format-specific edge cases
- Specialists report back to Foreman with result + metrics
- Error handling uses appropriate RecoveryStrategy

---

### P6-7: Add HITL (Human-in-the-Loop) approval

**Depends**: P6-5
**Category**: `unspecified-high`
**Blocks**: None

**What**:
1. Create `src/orf/workflow/__init__.py`
2. Create `src/orf/workflow/hitl_approval.py`:
   ```python
   """Human-in-the-Loop approval for sensitive operations."""
   
   from enum import Enum
   
   class RiskLevel(Enum):
       LOW = 1
       LIMITED = 2
       HIGH = 3
       UNACCEPTABLE = 4
   
   class HITLApproval:
       """Request human approval for high-risk operations."""
       
       def needs_approval(self, operation: dict) -> bool:
           """Check if operation requires human approval."""
           return (
               operation.get('file_size_mb', 0) > 100 or
               operation.get('target') == 'cloud' or
               operation.get('recovery_strategy') == RecoveryStrategy.MANUAL_INTERVENTION
           )
       
       async def request_approval(self, operation: dict) -> bool:
           """Request human approval. Returns True if approved."""
           # MCP notification to human reviewer
           # Wait for approval response
           pass
   ```

**Verify**:
- Files >100MB trigger approval request
- Cloud operations trigger approval request
- Manual intervention errors trigger approval request

---

### P6-8: Add audit trail logging (enhance existing)

**Depends**: None (can parallelize with P6-0)
**Category**: `quick`
**Blocks**: None

**What**:
Enhance `src/orf/logging/__init__.py` to add audit fields:

```python
def get_audit_logger(name: str = "orf.audit") -> logging.Logger:
    """Get audit logger with correlation_id, agent_id fields."""
    logger = get_logger(name)
    
    # Add correlation_id to all log entries
    class AuditFormatter(logging.Formatter):
        def format(self, record):
            record.correlation_id = getattr(record, 'correlation_id', 'N/A')
            record.agent_id = getattr(record, 'agent_id', 'N/A')
            return super().format(record)
    
    # Apply to file handler
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.setFormatter(AuditFormatter(...))
    
    return logger
```

**Audit Events to Log**:
- Job started/completed/failed (correlation_id)
- Format detection results
- Conversion success/failure
- Agent decisions (delegation, recovery)
- Resource usage (CPU, memory, time)

**Verify**:
- Log entries include `correlation_id` and `agent_id` fields
- Audit logs parseable for compliance review

---

### P6-9: Integration tests for MCP server

**Depends**: P6-2
**Category**: `quick`
**Blocks**: P6-10

**What**:
Create `tests/test_orf_mcp_server.py`:

```python
import pytest
from mcp.client import MCPClient

class TestORFMCPApplyMd:
    def test_apply_md_docx_success(self, mcp_client):
        result = mcp_client.call_tool("apply_md", {
            "input_md": "test.md",
            "target_format": "docx"
        })
        assert result.success is True
    
    def test_apply_md_invalid_format(self, mcp_client):
        result = mcp_client.call_tool("apply_md", {
            "input_md": "test.md",
            "target_format": "invalid"
        })
        assert result.success is False
        assert result.errors[0].code == "UNSUPPORTED_FORMAT"

class TestORFMCPApplyXLIFF:
    def test_apply_xliff_docx_success(self, mcp_client):
        ...

class TestORFMCPBatchConvert:
    def test_batch_convert_success(self, mcp_client):
        ...

class TestORFMCPSecurity:
    def test_path_traversal_blocked(self, mcp_client):
        result = mcp_client.call_tool("apply_md", {
            "input_md": "../../etc/passwd",
            "target_format": "docx"
        })
        assert result.errors[0].code == "PATH_NOT_ALLOWED"
```

**Verify**:
- `pytest tests/test_orf_mcp_server.py -v` passes
- All tool endpoints tested
- Error cases covered
- Security validation tested

---

### P6-10: E2E tests OPP→OL→ORF pipeline

**Depends**: P6-9
**Category**: `unspecified-high`
**Blocks**: None

**What**:
Create `tests/test_e2e_omni_pipeline.py`:

```python
@pytest.mark.e2e
def test_full_pipeline_opp_ol_orf():
    """Test full Omni ecosystem: OPP → OL → ORF"""
    
    # OPP: Extract DOCX to MD+XLIFF (mocked)
    with patch("subprocess.run") as mock_opp:
        mock_opp.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "status": "success",
                "outputs": ["spec.md", "spec_manifest.json"]
            }),
            stderr=""
        )
        
        # OL: Translate MD (mocked)
        with patch("subprocess.run") as mock_ol:
            mock_ol.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"status": "success"}),
                stderr=""
            )
            
            # ORF: Reconstruct via MCP
            result = mcp_client.call_tool("apply_md", {
                "input_md": "translated.md",
                "target_format": "docx"
            })
            
            assert result.success is True
            # Verify skeleton backfill worked
            assert Path("result.docx").exists()
```

**Verify**:
- `pytest tests/test_e2e_omni_pipeline.py -v` passes
- Full pipeline with mocked OPP/OL
- Skeleton backfill verified

---

## Parallel Execution Graph

```
Wave 1 (Start Immediately - No Dependencies):
├── P6-0 (quick): Add --json output mode + Fix ConversionResult types
└── P6-8 (quick): Add audit trail logging (enhance existing)

Wave 2 (After P6-0 - JSON Mode Ready):
├── P6-1 (deep): Create ORF MCP Server scaffold
└── P6-9 (quick): Integration tests for MCP server

Wave 3 (After P6-1 - MCP Foundation):
└── P6-2 (unspecified-high): Add MCP tools with typed schemas

Wave 4 (After P6-2 - Agent Integration):
├── P6-5 (artistry): Add Foreman agent for job orchestration
├── P6-6 (artistry): Add Specialist agents for format channels
└── P6-7 (unspecified-high): Add HITL approval workflow

Wave 5 (After Wave 4 - E2E Verification):
└── P6-10 (unspecified-high): E2E tests OPP→OL→ORF pipeline

Critical Path: P6-0 → P6-1 → P6-2 → Wave 4 → Wave 5
Estimated Parallel Speedup: ~45% faster than sequential
```

---

## File Structure

```
src/orf/
├── mcp/                              # NEW: MCP Server
│   ├── __init__.py
│   ├── server.py                    # P6-1, P6-2
│   ├── config.py                    # P6-1
│   ├── schemas.py                   # P6-2 (Pydantic models)
│   └── security.py                  # P6-2 (PathValidator)
├── agents/                           # NEW: Agent System
│   ├── __init__.py
│   ├── foreman.py                   # P6-5
│   └── specialists/                 # P6-6
│       ├── __init__.py
│       ├── format_specialist.py
│       ├── data_specialist.py
│       ├── markup_specialist.py
│       └── email_specialist.py
├── workflow/                         # NEW: Workflow Layer
│   ├── __init__.py
│   └── hitl_approval.py             # P6-7
├── logging/
│   └── __init__.py                  # P6-8 (enhance, not create)
└── converters/
    └── base.py                      # P6-0 (fix ErrorDetail types)

tests/
├── test_orf_mcp_server.py           # P6-9
└── test_e2e_omni_pipeline.py        # P6-10
```

---

## Atomic Commit Strategy

```bash
# Commit 1: P6-0 - CLI --json mode + ConversionResult fix
git commit -m "feat(cli): add --json output mode and fix ConversionResult types

- Add --json flag to apply-md, apply-xliff, convert-batch, info
- Fix ConversionResult.errors to list[ErrorDetail] with code/message/recovery_strategy
- Closes P6-0"

# Commit 2: P6-1 - MCP Server scaffold
git commit -m "feat(mcp): add ORF MCP server with FastMCP

- Add src/orf/mcp/server.py with FastMCP setup
- Add src/orf/mcp/config.py with MCPConfig
- Add entry point orf-mcp-server in pyproject.toml
- Closes P6-1"

# Commit 3: P6-2 - MCP tools with typed schemas
git commit -m "feat(mcp): add 5 MCP tools with Pydantic schemas

- apply_md, apply_xliff, batch_convert, detect_format, info
- Add src/orf/mcp/schemas.py with typed models
- Add src/orf/mcp/security.py with PathValidator
- Closes P6-2"

# Commit 4: P6-8 - Audit trail logging
git commit -m "feat(logging): add audit trail with correlation_id and agent_id

- Enhance logging/__init__.py with audit fields
- Add get_audit_logger() function
- Closes P6-8"

# Commit 5: P6-5, P6-6, P6-7 - Agent system + HITL
git commit -m "feat(agents): add Foreman + Specialist agent system with HITL

- Add src/orf/agents/foreman.py for job orchestration
- Add format/data/markup/email specialists
- Add src/orf/workflow/hitl_approval.py for large file approval
- Closes P6-5, P6-6, P6-7"

# Commit 6: P6-9 - MCP integration tests
git commit -m "test(mcp): add MCP server integration tests

- Test all 5 tools with success and error cases
- Test security validation (path traversal blocked)
- Closes P6-9"

# Commit 7: P6-10 - E2E pipeline tests
git commit -m "test(e2e): add OPP→OL→ORF pipeline integration tests

- Full Omni ecosystem pipeline test
- Closes P6-10"
```

---

## Success Criteria

| Task | Verification |
|------|--------------|
| P6-0 | `orf apply-md --json` returns valid JSON with typed errors |
| P6-1 | `python -m orf.mcp.server` starts without error |
| P6-2 | All 5 tools return valid JSON against Pydantic schemas |
| P6-5 | Foreman correctly routes jobs to Specialists |
| P6-6 | Specialists handle format-specific cases |
| P6-7 | Large file (>100MB) triggers approval |
| P6-8 | Log entries include correlation_id and agent_id |
| P6-9 | `pytest tests/test_orf_mcp_server.py -v` passes |
| P6-10 | `pytest tests/test_e2e_omni_pipeline.py -v` passes |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| FastMCP version conflicts | Server won't start | Pin `fastmcp>=0.1.0` in pyproject.toml |
| ConversionResult break existing code | User-facing regression | Add `--json` flag, don't change default output |
| Schema mismatch (38% failure) | Tool returns wrong data | Use Pydantic on both input and output |
| Path validation security | Directory traversal | Use PathValidator with allowlist |
| Timeout handling | Orphaned operations | 30s default, configurable per tool |

---

## Reference: Existing Plans to Reference

- **phase2-plan-agent-oriented.md** (1251 lines) - Has detailed Foreman/Specialist patterns
- **phase4-plan-agent-oriented.md** (369 lines) - COMPLETED, covers streaming/cloud/AI

Do not reinvent patterns already defined in these plans. Reference and extend.