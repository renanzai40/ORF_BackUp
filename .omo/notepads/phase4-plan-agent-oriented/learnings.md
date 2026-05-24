# Phase 4 Learnings

## Test Fixes Applied

### test_md2pdf_channel.py - test_convert_weasyprint_import_error
- **Problem**: Test patched `orf.channels.md2pdf._weasyprint_error` which didn't exist
- **Fix**: Patch `importlib.util.find_spec` to return `None` (simulates weasyprint not installed)
- **Pattern**: When testing missing module imports, patch `importlib.util.find_spec` not module-level variables

### test_cli_phase2.py - test_auto_detect_success & test_auto_detect_flag
- **Problem**: Tests patched `orf.channels.md2docx.MD2DOCXConverter` but CLI imports converters at module level and creates them at use site
- **Fix**: Patch `orf.cli.MD2DOCXConverter` and `orf.cli.MD2EPUBConverter` instead
- **Pattern**: When testing CLI commands that import converters at module level, patch where the converter is used (in cli.py), not where it's defined

## Dependencies Status
- azure-storage-blob, boto3, openai: Installation timed out (network)
- tests/test_cloud_clients.py, test_layout_analyzer.py, test_overflow_corrector.py: Cannot run until packages installed
- These are optional dependencies - core ORF functionality unaffected

## Verification Results
- 202 passed, 1 skipped (weasyprint), 4 warnings
- All core functionality tests passing
- Cloud/AI tests require external packages

## Cloud/AI Test Fixes (2026-05-23)

### Problem
Cloud and AI tests couldn't run without azure/boto3/openai packages installed because:
1. Module-level imports failed when packages missing
2. Test patch targets couldn't resolve when packages missing
3. Exception classes couldn't be imported inside methods

### Fixes Applied
1. **Lazy imports in cloud modules**:
   - `cloud/__init__.py`: Uses `__getattr__` for lazy loading of S3ResourceClient/AzureBlobResourceClient
   - `cloud_resource_manager.py`: Uses `_ensure_initialized()` for lazy provider registration
   - `s3_client.py`: Uses `__getattr__` + imports inside methods
   - `azure_blob_client.py`: Uses `__getattr__` + imports inside methods

2. **Test module-faking approach**:
   - Tests inject fake modules into `sys.modules` before client creation
   - S3 tests: `sys.modules["boto3"]`, `sys.modules["botocore"]`, `sys.modules["botocore.exceptions"]`
   - Azure tests: `sys.modules["azure"]`, `sys.modules["azure.storage.blob"]`, `sys.modules["azure.core.exceptions"]`

3. **Exception class synchronization**:
   - Tests that define local MockClientError/MockResourceNotFoundError update `sys.modules` references
   - Ensures the exception class caught by client code is the same instance raised in tests

4. **Method-level imports**:
   - `s3_client.py`: `from botocore.exceptions import ClientError` inside methods
   - `azure_blob_client.py`: `from azure.core.exceptions import ResourceNotFoundError` inside methods

### Result
All 272 tests pass including cloud and AI tests, without azure/boto3/openai installed.

## Test Fixes Summary
- `test_md2pdf_channel.py`: Patched `importlib.util.find_spec` not `_weasyprint_error`
- `test_cli_phase2.py`: Patched `orf.cli.MD2DOCXConverter` not `orf.channels.md2docx.MD2DOCXConverter`
