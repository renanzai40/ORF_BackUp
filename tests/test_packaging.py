"""Packaging and release tests for ORF."""

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from orf.cli import main


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def clean_dist():
    """Clean dist directory before and after tests."""
    dist = Path("dist")
    if dist.exists():
        for f in dist.iterdir():
            f.unlink()
    yield
    if dist.exists():
        for f in dist.iterdir():
            f.unlink()


class TestPackaging:
    """Test package build and distribution."""

    def test_wheel_builds(self, clean_dist):
        """Test that wheel package builds successfully."""
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", "dist"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        wheels = list(Path("dist").glob("*.whl"))
        assert len(wheels) == 1, f"Expected 1 wheel, found {len(wheels)}"
        assert wheels[0].name.startswith("orf-")

    def test_sdist_builds(self, clean_dist):
        """Test that source distribution builds successfully."""
        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", "--outdir", "dist"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        tarballs = list(Path("dist").glob("*.tar.gz"))
        assert len(tarballs) == 1, f"Expected 1 tarball, found {len(tarballs)}"
        assert tarballs[0].name.startswith("orf-")

    def test_entry_point_resolves(self, runner):
        """Test that the orf entry point resolves correctly after install."""
        # Install package in editable mode
        install_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True,
        )
        assert install_result.returncode == 0, f"Install failed: {install_result.stderr}"

        # Verify entry point resolves
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, f"Entry point failed: {result.output}"
        assert "ORF" in result.output or "orf" in result.output.lower()

    def test_import_after_install(self):
        """Test that the orf module can be imported after installation."""
        # Install package
        install_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True,
        )
        assert install_result.returncode == 0, f"Install failed: {install_result.stderr}"

        # Verify import works
        import_result = subprocess.run(
            [sys.executable, "-c", "import orf"],
            capture_output=True,
            text=True,
        )
        assert import_result.returncode == 0, f"Import failed: {import_result.stderr}"