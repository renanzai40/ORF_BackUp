# Contributing to Omni-Re-Formatter

## Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
orf --help
```

## Testing

Tests are organized with markers: `unit`, `integration`, `e2e`.

```bash
# Run all tests
pytest

# Run by marker
pytest -m unit
pytest -m integration
pytest -m e2e

# With coverage (target: ≥90%)
pytest --cov=src/orf --cov-report=term-missing
```

## Documentation

All public functions and classes must include:
- **Docstrings**: Google-style, describing purpose, args, and return values
- **Type hints**: Full annotations for parameters and return types

Example:
```python
def process_file(path: Path, format: str) -> dict[str, Any]:
    """Process a file and return metadata.

    Args:
        path: Path to the input file.
        format: Target output format.

    Returns:
        Dictionary containing processing metadata.

    Raises:
        ValueError: If format is not supported.
    """
    ...
```

## Code Style

### Ruff (Linting)
```bash
# Check
ruff check src/

# Auto-fix
ruff check --fix src/
```

Configuration: `line-length = 100`, `target-version = "py313"`.

### MyPy (Type Checking)
```bash
mypy src/
```

Configuration: `python_version = "3.13"`, `strict = true`.

## Release Process

1. **Update version** in `pyproject.toml` (e.g., `0.1.0` → `0.2.0`)

2. **Update changelog** (if exists) or add git tag notes

3. **Commit changes**:
   ```bash
   git add pyproject.toml [changelog]
   git commit -m "Bump version to X.Y.Z"
   ```

4. **Create git tag**:
   ```bash
   git tag -a vX.Y.Z -m "Release X.Y.Z"
   git push origin main --tags
   ```

5. **Build and upload**:
   ```bash
   python -m build
   twine upload dist/*
   ```

6. **Publish to PyPI** (automatic after approval)