# Omni-Re-Formatter (ORF) Phase 3 Plan - Agent-Oriented Implementation

**Version**: v1.0  
**Author**: Sisyphus (Lead Agent)  
**Date**: 2026-05-23  
**Project**: Omni-Re-Formatter (ORF)  
**Goal**: Phase 3 implementation - UX enhancement, E2E integration, and PyPI release

---

## Context

### Current State (Phases 0-2 Complete)

**What exists**:

| Component | Status | Key Files |
|-----------|--------|-----------|
| CLI Framework | ✅ Click-based, 333 lines | `src/orf/cli.py` |
| 14 Converter Channels | ✅ Complete | `src/orf/channels/` |
| Format Auto-Detection | ✅ Complete | `src/orf/detection/` |
| Image Manager | ✅ Complete | `src/orf/resources/` |
| Error Handling | ✅ 8 exception types | `src/orf/error_handlers/` |
| Manifest/Frontmatter Parsers | ✅ Complete | `src/orf/parsers/` |
| Logging System | ✅ Complete | `src/orf/logging/` |
| Tests | ✅ 21 test files | `tests/` |

**What exists in Phase 3 area**:

| File | Lines | Status |
|------|-------|--------|
| `tests/test_cli.py` | 340 | Covers apply-xliff with 5 formats + failure cases |
| `tests/test_integration.py` | 731 | Full OPP→OL→ORF pipeline tests + BDD scenario |
| `tests/test_packaging.py` | 90 | Wheel/sdist/entry_point tests |
| `pyproject.toml` | 65 | PEP 621 compliant, has `[project.scripts]` |
| `src/orf/cli.py` | 333 | Uses click.progressbar, has --verbose, info command |

### Known Gaps (from codebase audit)

1. **CLI**: `apply-md` lacks progress bar (only `convert-batch` has one)
2. **CLI**: Error messages lack fix suggestions for common errors
3. **Tests**: `test_cli.py` does not test `apply-md` command at all
4. **Tests**: `convert-batch` not tested
5. **Tests**: Missing tests for CLI `--verbose` behavior
6. **PyPI**: No release workflow docs

### Tool Matrix (from main plan)

| Category | Tool | Purpose |
|----------|------|---------|
| CLI框架 | click | 命令行界面构建 |
| 进度条 | tqdm | 转换进度显示 (spec says tqdm, current uses click.progressbar) |
| 打包 | setuptools/pyproject.toml | PyPI 包打包 |
| 发布 | twine | PyPI 包发布 |

---

## Phase 3 ATDD Acceptance Criteria

| ID | Criterion | Current Status | Verification |
|----|-----------|----------------|--------------|
| ATDD-1 | CLI provides clear help info and progress feedback | ❌ apply-md has no progress bar | Manual test + pytest |
| ATDD-2 | OPP→OL→ORF E2E test pass rate 100% | ✅ test_integration.py exists | `pytest tests/test_integration.py -v` |
| ATDD-3 | PyPI package installs via `pip install omni-re-formatter` | ✅ pyproject.toml has deps | `pip install -e .` test |
| ATDD-4 | CLI provides friendly error suggestions | ❌ No fix suggestions | Manual test |
| ATDD-5 | Partial failure produces partial results + error report | ⚠️ Partial test exists | Manual verification |

---

## Task Dependency Graph

| Task | Depends On | Reason |
|------|------------|--------|
| **P3-T1** (CLI: add tqdm progress to apply-md) | None | Standalone enhancement |
| **P3-T2** (CLI: add error fix suggestions) | None | Standalone enhancement |
| **P3-T3** (Tests: add apply-md CLI tests) | P3-T1 | Tests new progress bar feature |
| **P3-T4** (Tests: add convert-batch CLI tests) | P3-T1 | Tests new progress bar feature |
| **P3-T5** (Tests: add verbose flag tests) | None | Standalone test |
| **P3-T6** (PyPI: add release workflow docs) | None | Standalone documentation |
| **P3-T7** (Integration: verify E2E pipeline 100%) | P3-T3, P3-T4 | Integration verification |

---

## Parallel Execution Graph

```
Wave 1 (Start Immediately - No Dependencies):
├── P3-T1 (unspecified-high): Add tqdm progress to apply-md
├── P3-T2 (unspecified-high): Add error fix suggestions
├── P3-T5 (quick): Add verbose flag tests
└── P3-T6 (deep): Add PyPI release workflow docs

Wave 2 (After Wave 1 - Testing):
├── P3-T3 (quick): Add apply-md CLI tests
└── P3-T4 (quick): Add convert-batch CLI tests

Wave 3 (After Wave 2 - Integration):
└── P3-T7 (unspecified-high): Verify E2E pipeline 100% pass

Critical Path: Wave 1 → Wave 2 → Wave 3
Estimated Parallel Speedup: ~30% faster than sequential
```

---

## Tasks

### Task P3-T1: Add tqdm progress to apply-md command

**Delegation Recommendation**:
- Category: `unspecified-high` - CLI enhancement requiring careful integration
- Skills: None

**Depends On**: None

**Description**: 
Add tqdm-based progress bar to `apply-md` single-file conversion for consistency with spec.

**Implementation**:
```python
# In src/orf/cli.py - apply_md function
from tqdm import tqdm

# Add progress indication for single file operations
click.echo(f"Converting {input_path.name} to {target_format}...")
```

**File Changes**:
- `src/orf/cli.py`: Add tqdm import, add progress indication in apply_md

**Acceptance Criteria**:
- `orf apply-md input.md -t docx -o output.docx --verbose` shows progress
- `orf apply-md --help` mentions progress indicator

---

### Task P3-T2: Add error fix suggestions to CLI

**Delegation Recommendation**:
- Category: `unspecified-high` - User experience improvement
- Skills: None

**Depends On**: None

**Description**:
Enhance error messages with fix suggestions for common errors.

**Implementation**:
```python
# In src/orf/cli.py - error handling enhancement

ERROR_SUGGESTIONS = {
    "FileNotFoundError": "Check file path. Ensure file exists.",
    "InvalidFormat": "Use --target-format: docx, odt, epub, html, rtf, pdf",
    "MissingXLIFF": "Use --xliff option to specify translation file."
}

def _get_fix_suggestion(error: Exception) -> str:
    """Get actionable fix suggestion."""
    return ERROR_SUGGESTIONS.get(type(error).__name__, "Run 'orf --help' for usage")
```

**File Changes**:
- `src/orf/cli.py`: Add error suggestion helper and use in handlers

**Acceptance Criteria**:
- `orf apply-md nonexistent.md` shows "Check file path..."
- `orf apply-xliff doc.docx --xliff missing.xlf` shows "Use --xliff..."

---

### Task P3-T3: Add apply-md CLI tests

**Delegation Recommendation**:
- Category: `quick` - Test file modification
- Skills: None

**Depends On**: P3-T1

**Description**:
Add tests for `apply-md` command to `tests/test_cli.py`

**Test Cases**:
```python
class TestApplyMd:
    """Test apply-md command."""

    def test_apply_md_docx_success(self, runner, sample_md, tmp_path):
        """Test apply-md with DOCX format."""
        # Test docx, odt, epub, html, rtf, pdf formats
        pass

    def test_apply_md_missing_input(self, runner, tmp_path):
        """Test apply-md with missing input."""
        pass
```

**File Changes**:
- `tests/test_cli.py`: Add `TestApplyMd` class with 6+ test methods

**Acceptance Criteria**:
- `pytest tests/test_cli.py::TestApplyMd -v` passes

---

### Task P3-T4: Add convert-batch CLI tests

**Delegation Recommendation**:
- Category: `quick` - Test file modification
- Skills: None

**Depends On**: P3-T1

**Description**:
Add tests for `convert-batch` command (not currently tested)

**Test Cases**:
```python
class TestConvertBatch:
    """Test convert-batch command."""

    def test_convert_batch_single_file(self, runner, tmp_path):
        pass

    def test_convert_batch_no_files(self, runner, tmp_path):
        assert "No files found" in result.output
```

**File Changes**:
- `tests/test_cli.py`: Add `TestConvertBatch` class

**Acceptance Criteria**:
- `pytest tests/test_cli.py::TestConvertBatch -v` passes

---

### Task P3-T5: Add verbose flag tests

**Delegation Recommendation**:
- Category: `quick` - Simple test addition
- Skills: None

**Depends On**: None

**Description**:
Test `--verbose` flag behavior across CLI commands

**Test Cases**:
```python
def test_verbose_flag_enables_debug_logging(runner):
    """Test --verbose flag."""
    result = runner.invoke(main, ["--verbose", "--help"])
    assert result.exit_code == 0
```

**File Changes**:
- `tests/test_cli.py`: Add verbose tests

**Acceptance Criteria**:
- `pytest tests/test_cli.py -k "verbose" -v` passes

---

### Task P3-T6: Add PyPI release workflow documentation

**Delegation Recommendation**:
- Category: `deep` - Documentation
- Skills: None

**Depends On**: None

**Description**:
Create `RELEASE.md` with step-by-step PyPI publishing process

**Content**:
```markdown
# ORF Release Process

## Version Bump
1. Update version in pyproject.toml
2. git tag v0.2.0

## Build
1. rm -rf dist/ build/
2. python -m build

## Publish
1. twine upload dist/*  (Test PyPI first)
2. pip install omni-re-formatter
```

**File Changes**:
- Create `RELEASE.md` at project root

**Acceptance Criteria**:
- `RELEASE.md` exists with all sections

---

### Task P3-T7: Verify E2E pipeline 100% pass rate

**Delegation Recommendation**:
- Category: `unspecified-high` - Integration verification
- Skills: None

**Depends On**: P3-T3, P3-T4

**Description**:
Run full integration test suite and verify 100% pass

**Verification**:
```bash
pytest tests/test_cli.py tests/test_integration.py tests/test_packaging.py -v
pytest tests/ --cov=src/orf --cov-report=term-missing
```

**Acceptance Criteria**:
- All tests pass
- Coverage ≥ 90%

---

## File Structure (Changes)

```
Omni_Re_Formatter/
├── RELEASE.md                    # NEW: PyPI release workflow
├── src/orf/
│   └── cli.py                   # MODIFIED: tqdm + fix suggestions
└── tests/
    └── test_cli.py              # MODIFIED: add apply-md + convert-batch tests
```

---

## Atomic Commit Strategy

### Commit 1: CLI enhancements
```
feat(cli): add tqdm progress and error fix suggestions

- Add tqdm import and progress indicator to apply-md
- Add _get_fix_suggestion() helper
- Closes #P3-T1, #P3-T2
```

### Commit 2: apply-md tests
```
test(cli): add TestApplyMd class with 6 test methods

- Covers docx, odt, epub, html, rtf, pdf formats
- Closes #P3-T3
```

### Commit 3: convert-batch and verbose tests
```
test(cli): add TestConvertBatch class and verbose tests

- Closes #P3-T4, #P3-T5
```

### Commit 4: Documentation
```
docs: add RELEASE.md with PyPI publishing workflow

- Closes #P3-T6
```

### Commit 5: Integration verification
```
test(integration): verify E2E pipeline 100% pass

- Closes #P3-T7
```

---

## TODO List (ADD THESE)

### Wave 1 (Start Immediately)

- [ ] **P3-T1: Add tqdm progress to apply-md**
  - What: Modify apply_md to add tqdm progress
  - Depends: None
  - Blocks: P3-T3
  - Category: `unspecified-high`
  - QA: `orf apply-md test.md -t docx -o out.docx --verbose`

- [ ] **P3-T2: Add error fix suggestions**
  - What: Add error suggestion helper
  - Depends: None
  - Blocks: None
  - Category: `unspecified-high`
  - QA: `orf apply-md missing.md` shows hint

- [ ] **P3-T5: Add verbose flag tests**
  - What: Add verbose tests
  - Depends: None
  - Blocks: None
  - Category: `quick`
  - QA: `pytest tests/test_cli.py -k "verbose" -v`

- [ ] **P3-T6: Add PyPI release workflow docs**
  - What: Create RELEASE.md
  - Depends: None
  - Blocks: None
  - Category: `deep`
  - QA: RELEASE.md exists with all sections

### Wave 2 (After Wave 1)

- [ ] **P3-T3: Add apply-md CLI tests**
  - What: Add TestApplyMd class
  - Depends: P3-T1
  - Blocks: P3-T7
  - Category: `quick`
  - QA: `pytest tests/test_cli.py::TestApplyMd -v`

- [ ] **P3-T4: Add convert-batch CLI tests**
  - What: Add TestConvertBatch class
  - Depends: P3-T1
  - Blocks: P3-T7
  - Category: `quick`
  - QA: `pytest tests/test_cli.py::TestConvertBatch -v`

### Wave 3 (After Wave 2)

- [ ] **P3-T7: Verify E2E pipeline 100% pass**
  - What: Run full test suite
  - Depends: P3-T3, P3-T4
  - Blocks: None
  - Category: `unspecified-high`
  - QA: `pytest tests/test_cli.py tests/test_integration.py tests/test_packaging.py -v`

---

## Execution Instructions

1. **Wave 1**: Fire IN PARALLEL
   ```
   task(category="unspecified-high", prompt="P3-T1: Add tqdm progress...")
   task(category="unspecified-high", prompt="P3-T2: Add error fix suggestions...")
   task(category="quick", prompt="P3-T5: Add verbose flag tests...")
   task(category="deep", prompt="P3-T6: Add PyPI release workflow docs...")
   ```

2. **Wave 2**: After Wave 1
   ```
   task(category="quick", prompt="P3-T3: Add apply-md CLI tests...")
   task(category="quick", prompt="P3-T4: Add convert-batch CLI tests...")
   ```

3. **Wave 3**: After Wave 2
   ```
   task(category="unspecified-high", prompt="P3-T7: Verify E2E pipeline...")
   ```

---

## Success Criteria

| Criterion | Verification | Status |
|-----------|--------------|--------|
| CLI help shows all commands | `orf --help` | Manual |
| Progress bar visible | `orf convert-batch dir/ -t docx` | Manual |
| Error messages include fix suggestions | `orf apply-md missing.md` | Manual |
| All tests pass | `pytest tests/ -v` | Automated |
| E2E pipeline 100% pass | `pytest tests/test_integration.py -v` | Automated |
| PyPI package builds | `python -m build && twine check dist/*` | Manual |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| tqdm vs click.progressbar | Spec says tqdm | Use tqdm as spec requires |
| OPP/OL not available | E2E needs mocks | test_integration.py uses mocks |

---

## Non-Functional Requirements

- CLI response time ≤ 100ms for help commands
- Progress bar updates every 100ms for large batch ops
- Error messages include specific fix suggestions
- Test coverage target: ≥ 90% for CLI module
- PyPI package size: < 10MB
