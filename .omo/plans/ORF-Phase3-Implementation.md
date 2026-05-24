# Omni-Re-Formatter (ORF) Phase 3 Implementation Plan

> Agent-Oriented Implementation Plan
> Based on: Omni-Re-Formatter (ORF) 开发计划 - DD Vibe Phase版.md
> Phase: 3 of 3 (Final Phase)
> Last Updated: 2026-05-23

---

## Phase 3 Overview

### Goals
1. **完善 CLI 用户体验** - intuitive CLI with help info and progress feedback
2. **OPP → OL → ORF 完整流水线集成测试** - E2E pipeline testing
3. **PyPI 发布** - packaging and distribution via `pip install omni-re-formatter`

### Current State (Phases 0-2 Complete)

| Component | Status | Location |
|-----------|--------|----------|
| CLI Framework | ✅ Click-based | `src/orf/cli.py` (299 lines) |
| Existing CLI Tests | ✅ `test_cli.py`, `test_cli_phase2.py` | `tests/` (539 lines combined) |
| 14 Converter Channels | ✅ Complete | `src/orf/channels/` |
| Format Auto-Detection | ✅ Complete | `src/orf/detection/` |
| Image Manager | ✅ Complete | `src/orf/resources/` |
| Error Handling | ✅ 8 exception types | `src/orf/error_handlers/` |

### Key Changes from Original Plan (Review Corrections)

1. **Replace `tqdm` with `click.progressbar()`** - Click's native progress bar is preferred for CLI integration
2. **Do NOT recreate `test_cli.py`** - Already exists at 340 lines, extend coverage instead
3. **Use `[project.scripts]` in pyproject.toml** for entry point, not a `scripts/` directory

---

## Test Deliverables (Per Development Plan)

| File | Status | Action |
|------|--------|--------|
| `tests/test_cli.py` | ✅ Exists | Extend coverage for new commands |
| `tests/test_integration.py` | ❌ Missing | **CREATE** - E2E pipeline tests |
| `tests/test_packaging.py` | ❌ Missing | **CREATE** - Build/install/entry point verification |

---

## Wave 1: Foundation (Parallel)

### P3.1.1: CLI Audit
- **Agent**: `quick`
- **Task**: Audit `src/orf/cli.py` against Click best practices
- **Verify**:
  - Uses `@click.group()`, `@click.command()` correctly
  - Commands use `@click.argument()` and `@click.option()` properly
  - Error handling uses `click.ClickException` or `click.BadParameter`
  - `--verbose` flag properly controls logging level
- **Success Criteria**: CLI uses idiomatic Click patterns
- **Status**: ✅ DONE - Audit complete. Issues found: error handling uses `sys.exit(1)` instead of Click exceptions. Decorators and --verbose are correct.

### P3.3.1: pyproject.toml Audit
- **Agent**: `quick`
- **Task**: Verify `pyproject.toml` structure per PEP 621
- **Verify**:
  - `[build-system]` with `requires` and `build-backend`
  - `[project]` table with name, version, description, requires-python
  - `[project.optional-dependencies]` for dev/test deps
  - No legacy setup.py metadata
- **Success Criteria**: pyproject.toml is PyPI-ready
- **Status**: ✅ DONE - PEP 621 compliant. [project.scripts] orf already exists (P3.3.2 already done). [project.optional-dependencies] missing `test = ["coverage"]` group (to be fixed in P3.3.3).

### P3.3.2: Add CLI Entry Point
- **Agent**: `deep`
- **Task**: Add `[project.scripts]` entry point to pyproject.toml
- **Change**:
  ```toml
  [project.scripts]
  orf = "orf.cli:main"
  ```
- **Success Criteria**: `pip install -e . && orf --help` works
- **Status**: ✅ DONE - Already present in pyproject.toml at line 39-40. Confirmed working.

---

## Wave 2: CLI Enhancement (Parallel)

### P3.1.2: Add Progress Bars
- **Agent**: `deep`
- **Task**: Add `click.progressbar()` for batch operations
- **Change** (replace tqdm in `convert-batch`):
  ```python
  with click.progressbar(md_files, label=f"Converting to {target_format}",
                         show_pos=True, show_percent=True) as bar:
      for md_file in bar:
          # conversion logic
  ```
- **Note**: For `apply-md` single-file operations, progress bar not needed
- **Success Criteria**: `orf convert-batch dir/ -t docx` shows progress bar
- **Status**: ✅ DONE - tqdm replaced with click.progressbar(), verified working

### P3.1.3: Improve Error Messages
- **Agent**: `deep`
- **Task**: Enhance CLI error handling with Click patterns
- **Add**:
  - Use `click.BadParameter` for argument validation errors
  - Use `click.ClickException` for command-level errors
  - Add `--fix-suggestion` hints for common errors
- **Success Criteria**: `orf apply-md nonexistent.md` shows helpful error with suggestion
- **Status**: ✅ DONE - All 6 sys.exit(1) replaced with raise click.ClickException(...), helpful suggestions added

### P3.3.3: Organize Dependencies
- **Agent**: `deep`
- **Task**: Ensure proper dependency grouping
- **Verify**:
  ```toml
  [project.optional-dependencies]
  dev = ["pytest>=7.4.0", "pytest-cov>=4.1.0", "ruff"]
  test = ["coverage"]
  ```
- **Success Criteria**: `pip install -e ".[dev]"` installs all dev dependencies
- **Status**: ✅ DONE - test = ["coverage"] added to pyproject.toml

### P3.3.4: Write test_packaging.py
- **Agent**: `quick`
- **Task**: Create packaging tests
- **Test Cases**:
  1. `test_wheel_builds` - `python -m build` produces valid wheel
  2. `test_sdist_builds` - sdist tarball is valid
  3. `test_entry_point_resolves` - `orf --help` works after install
  4. `test_import_after_install` - `import orf` succeeds
- **Success Criteria**: All tests pass, `twine check dist/*` passes
- **Status**: ✅ DONE - tests/test_packaging.py created with all 4 test functions

---

## Wave 3: New Commands + Integration (Parallel)

### P3.1.4: Add `orf info` Command
- **Agent**: `quick`
- **Task**: Add `orf info <file>` command
- **Functionality**:
  ```bash
  orf info document.docx
  # Output:
  # Format: DOCX
  # Size: 1.2 MB
  # Resources: 15 images
  # Manifest: present
  ```
- **Implementation**: Use `FormatDetector` from `src/orf/detection/format_detector.py`
- **Success Criteria**: `orf info <file>` returns format, size, resource count
- **Status**: ✅ DONE - info command added to cli.py (lines 289-325), shows format/size/manifest presence

### P3.2.1: Write test_integration.py
- **Agent**: `deep`
- **Task**: Create E2E integration tests
- **New File**: `tests/test_integration.py`
- **Test Cases**:
  1. `test_full_pipeline_opp_ol_orf` - OPP→OL→ORF complete flow
  2. `test_pipeline_with_mock_opp_ol` - Mock OPP/OL subprocess calls
  3. `test_manifest_driven_conversion` - Format auto-detection via manifest
  4. `test_skeleton_backfill_flow` - XLIFF→DOCX with skeleton.zip
- **Success Criteria**: `pytest tests/test_integration.py` passes
- **Status**: ✅ DONE - tests/test_integration.py created with 10+ test functions (all passing)

### P3.2.2: Write BDD Scenario Test
- **Agent**: `deep`
- **Task**: Implement BDD scenario from development plan
- **Scenario**: "结构化文档的完整本地化流水线" (Structured Document Full Localization Pipeline)
- **Given**: DOCX file spec.docx (English)
- **When**: User runs OPP→OL→ORF command sequence
- **Then**: spec_ja.docx is valid Japanese document with preserved formatting
- **Implementation**: Use pytest-bdd or pure pytest with clear Given/When/Then comments
- **Success Criteria**: Test verifies complete pipeline
- **Status**: ✅ DONE - test_bdd_full_localization_pipeline added to test_integration.py (lines 459-546)

### P3.2.3: Mock OPP/OL in Integration Tests
- **Agent**: `quick`
- **Task**: Add subprocess mocks for OPP and OL
- **Pattern**:
  ```python
  @patch("subprocess.run")
  def test_with_mock_opp_ol(mock_run):
      # Mock OPP output: skeleton.zip + manifest.json
      # Mock OL output: translated XLIFF
      # Test ORF processing
  ```
- **Success Criteria**: Tests run without real OPP/OL installation
- **Status**: ✅ DONE - mock_opp_output() and mock_ol_output() fixtures created, test_with_mock_opp_ol test exists

---

## Wave 4: Finalization (Parallel)

### P3.2.4: Partial-Failure Test
- **Agent**: `deep`
- **Task**: Test E2E partial failure handling
- **Scenario**: OL translation fails mid-way
- **Expected**: ORF produces partial results + error report
- **Success Criteria**: `orf apply-xliff` reports partial success with error details
- **Status**: ✅ DONE - test_partial_failure_reporting added to test_integration.py (lines 459-546)

### P3.3.5: Add Release Instructions
- **Agent**: `deep`
- **Task**: Create CONTRIBUTING.md with release instructions
- **Content**:
  ```markdown
  ## Release Process

  1. Update version in pyproject.toml
  2. Update CHANGELOG.md
  3. Create git tag: `git tag v1.0.0`
  4. Build: `python -m build`
  5. Check: `twine check dist/*`
  6. Test PyPI: `twine upload --repository testpypi dist/*`
  7. Production: `twine upload dist/*`
  ```
- **Success Criteria**: Maintainer can release with documented workflow
- **Status**: ✅ DONE - CONTRIBUTING.md created at project root with all sections (Setup, Testing, Docs, Code Style, Release)

---

## Agent Assignment Summary

| Agent | Tasks |
|-------|-------|
| `quick` | P3.1.1, P3.3.1, P3.3.4, P3.1.4, P3.2.3 |
| `deep` | P3.3.2, P3.1.2, P3.1.3, P3.3.3, P3.2.1, P3.2.2, P3.2.4, P3.3.5 |

---

## Parallel Execution Graph

```
Wave 1 (Foundation):
├── P3.1.1 (quick): Audit CLI
├── P3.3.1 (quick): Audit pyproject.toml
└── P3.3.2 (deep): Add entry point

Wave 2 (CLI Enhancement):
├── P3.1.2 (deep): Add progress bars (click.progressbar)
├── P3.1.3 (deep): Improve error messages
├── P3.3.3 (deep): Organize dependencies
└── P3.3.4 (quick): Write test_packaging.py

Wave 3 (New Commands + Integration):
├── P3.1.4 (quick): Add orf info command
├── P3.2.1 (deep): Write test_integration.py
├── P3.2.2 (deep): Write BDD scenario test
└── P3.2.3 (quick): Mock OPP/OL in tests

Wave 4 (Finalization):
├── P3.2.4 (deep): Partial-failure test
└── P3.3.5 (deep): Add release instructions
```

---

## Success Criteria Summary

| Phase | Criteria |
|-------|----------|
| **CLI UX** | `orf --help` shows all options; invalid args show fix suggestions; progress bar for batch ops |
| **E2E Integration** | OPP→OL→ORF test pass rate 100%; partial failure produces partial results + error report |
| **PyPI Release** | `pip install omni-re-formatter` works; `twine check dist/*` passes; entry point resolves |

---

## Non-Functional Requirements

- Format detection response time ≤ 50ms
- All format conversion performance ≥ 10MB/s
- Test coverage target: ≥ 90%
- CLI provides friendly error messages with fix suggestions

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| CLI design not matching user habits | User testing + iterate on feedback |
| PyPI dependency conflicts | Use `[project.optional-dependencies]` strictly; test in clean venv |
| E2E tests need OPP/OL installed | Use subprocess mocks for CI/CD |