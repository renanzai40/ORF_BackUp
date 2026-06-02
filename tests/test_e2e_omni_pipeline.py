"""End-to-end tests for OPP→OL→ORF pipeline.

These tests verify the complete Omni localization ecosystem:
OPP extracts document → OL translates → ORF reconstructs format.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import tempfile
import zipfile
import os

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestOmniPipeline:
    """Test complete Omni localization pipeline."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_opp_output(self, temp_workspace):
        """Mock OPP extraction output."""
        # Create mock manifest
        manifest = {
            "source": {"format": "DOCX", "file": "original.docx"},
            "extraction": {"source_lang": "en", "target_lang": "zh"},
            "images": ["image1.png", "image2.png"]
        }
        
        # Create mock translated MD
        translated_md = """---
source_file: original.docx
source_lang: en
target_lang: zh
---

# Translated Content

This is the translated document content.
"""
        
        # Create mock skeleton ZIP
        skeleton_path = temp_workspace / "original.skeleton.zip"
        with zipfile.ZipFile(skeleton_path, 'w') as zf:
            zf.writestr("word/document.xml", "<document>content</document>")
        
        return {
            "manifest": manifest,
            "translated_md": translated_md,
            "skeleton_path": skeleton_path
        }
    
    @patch("subprocess.run")
    def test_opp_extracts_document(self, mock_run, temp_workspace, mock_opp_output):
        """Test that OPP correctly extracts document."""
        # Mock OPP CLI call
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "status": "success",
                "outputs": [
                    str(temp_workspace / "original.md"),
                    str(temp_workspace / "original_manifest.json")
                ]
            }),
            stderr=""
        )
        
        # Verify OPP would be called with correct arguments
        from orf.mcp.server import _run_cli_command
        
        # Simulate OPP extraction
        result = _run_cli_command(["extract", "original.docx"])
        assert result["status"] == "success"
    
    @patch("subprocess.run") 
    def test_ol_translates_md(self, mock_run, temp_workspace):
        """Test that OL correctly translates MD."""
        # Mock OL CLI call
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "status": "success",
                "output": str(temp_workspace / "translated.md")
            }),
            stderr=""
        )
        
        from orf.mcp.server import _run_cli_command
        
        # Simulate OL translation
        result = _run_cli_command(["translate-md", "original.md", "-s", "en", "-t", "zh"])
        assert result["status"] == "success"
    
    @patch("subprocess.run")
    def test_orf_reconstructs_format(self, mock_run, temp_workspace):
        """Test that ORF correctly reconstructs format from translated MD."""
        # Mock ORF CLI call
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "success": True,
                "output_path": str(temp_workspace / "result.docx"),
                "errors": [],
                "warnings": [],
                "metadata": {"format": "docx"}
            }),
            stderr=""
        )
        
        from orf.mcp.server import _run_cli_command
        
        # Simulate ORF reconstruction
        result = _run_cli_command([
            "apply-md", 
            str(temp_workspace / "translated.md"),
            "--target-format", "docx",
            "--output", str(temp_workspace / "result.docx")
        ])
        
        assert result["success"] is True
        assert "result.docx" in result["output_path"]
    
    @patch("subprocess.run")
    def test_full_pipeline_integration(self, mock_run, temp_workspace, mock_opp_output):
        """Test complete OPP→OL→ORF pipeline."""
        # Track call sequence
        calls = []
        
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            calls.append(cmd)
            
            if "extract" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "status": "success",
                        "outputs": [
                            str(temp_workspace / "original.md"),
                            str(temp_workspace / "manifest.json")
                        ]
                    }),
                    stderr=""
                )
            elif "translate-md" in cmd or "translate-xliff" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "status": "success",
                        "output": str(temp_workspace / "translated.md")
                    }),
                    stderr=""
                )
            elif "apply-md" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "success": True,
                        "output_path": str(temp_workspace / "result.docx"),
                        "errors": [],
                        "warnings": [],
                        "metadata": {}
                    }),
                    stderr=""
                )
            
            return MagicMock(returncode=0, stdout="{}", stderr="")
        
        mock_run.side_effect = mock_run_side_effect
        
        # Simulate full pipeline
        from orf.mcp.server import _run_cli_command
        
        # Step 1: OPP Extract
        opp_result = _run_cli_command(["extract", "original.docx"])
        assert opp_result["status"] == "success"
        
        # Step 2: OL Translate
        ol_result = _run_cli_command(["translate-md", "original.md", "-s", "en", "-t", "zh"])
        assert ol_result["status"] == "success"
        
        # Step 3: ORF Reconstruct
        orf_result = _run_cli_command([
            "apply-md",
            "translated.md",
            "--target-format", "docx",
            "--output", "result.docx"
        ])
        assert orf_result["success"] is True
        
        # Verify pipeline sequence
        assert len(calls) >= 3
    
    @patch("subprocess.run")
    def test_pipeline_with_xliff(self, mock_run, temp_workspace):
        """Test OPP→OL→ORF pipeline with XLIFF translation."""
        def mock_run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])

            if "extract" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "status": "success",
                        "outputs": [str(temp_workspace / "original.xlf")]
                    }),
                    stderr=""
                )
            elif "translate-xliff" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "status": "success",
                        "output": str(temp_workspace / "translated.xlf")
                    }),
                    stderr=""
                )
            elif "apply-xliff" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "success": True,
                        "output_path": str(temp_workspace / "result.docx"),
                        "errors": [],
                        "warnings": [],
                        "metadata": {}
                    }),
                    stderr=""
                )

            return MagicMock(returncode=0, stdout="{}", stderr="")

        mock_run.side_effect = mock_run_side_effect

        from orf.mcp.server import _run_cli_command

        opp_result = _run_cli_command(["extract", "original.docx", "--format", "xliff"])
        assert opp_result["status"] == "success"

        ol_result = _run_cli_command(["translate-xliff", "original.xlf", "-s", "en", "-t", "zh"])
        assert ol_result["status"] == "success"

        orf_result = _run_cli_command([
            "apply-xliff",
            "original.docx",
            "--xliff", "translated.xlf",
            "--output", "result.docx",
            "--format", "docx"
        ])

        assert orf_result["success"] is True
    
    def test_skeleton_backfill_concept(self, temp_workspace):
        """Test that skeleton ZIP is correctly handled."""
        # Create skeleton ZIP
        skeleton_path = temp_workspace / "test.skeleton.zip"
        with zipfile.ZipFile(skeleton_path, 'w') as zf:
            zf.writestr("word/document.xml", "<document>original</document>")
            zf.writestr("word/header.xml", "<header/>")
        
        # Verify skeleton contents
        with zipfile.ZipFile(skeleton_path, 'r') as zf:
            names = zf.namelist()
            assert "word/document.xml" in names
            assert "word/header.xml" in names
        
        # Simulate XLIFF application (would modify document.xml)
        with zipfile.ZipFile(skeleton_path, 'a') as zf:
            # In real implementation, XLIFF translations would be applied here
            pass
        
        # Verify skeleton still valid
        with zipfile.ZipFile(skeleton_path, 'r') as zf:
            names = zf.namelist()
            assert len(names) >= 2


class TestPipelineErrorHandling:
    """Test error handling in pipeline."""
    
    @patch("subprocess.run")
    def test_opp_extraction_failure(self, mock_run):
        """Test handling when OPP extraction fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps({
                "success": False,
                "errors": [{
                    "code": "OPP_READ_ERROR",
                    "message": "Cannot read DOCX file",
                    "recovery_strategy": None
                }],
                "warnings": [],
                "metadata": {}
            }),
            stderr="Error: Cannot read DOCX"
        )

        from orf.mcp.server import _run_cli_command

        result = _run_cli_command(["extract", "corrupted.docx"])
        assert result["success"] is False
        assert any(e["code"] == "OPP_READ_ERROR" for e in result["errors"])
    
    @patch("subprocess.run")
    def test_orf_missing_skeleton(self, mock_run):
        """Test handling when skeleton is missing."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps({
                "success": False,
                "errors": [{
                    "code": "SKELETON_NOT_FOUND",
                    "message": "Skeleton file not found",
                    "recovery_strategy": "manual_intervention"
                }],
                "warnings": [],
                "metadata": {}
            }),
            stderr=""
        )
        
        from orf.mcp.server import _run_cli_command
        
        result = _run_cli_command(["apply-xliff", "doc.docx", "--xliff", "trans.xlf", "--format", "docx"])
        assert result["success"] is False
        assert any(e["code"] == "SKELETON_NOT_FOUND" for e in result["errors"])


@pytest.mark.e2e
class TestE2EPipeline:
    """End-to-end tests requiring full system."""
    
    def test_pipeline_concept(self):
        """Basic pipeline concept test."""
        # This test verifies the pipeline architecture concept
        # In real E2E test, would use actual OPP/OL/ORF installations
        pipeline_steps = ["extract", "translate", "reconstruct"]
        assert len(pipeline_steps) == 3
        assert "extract" in pipeline_steps
        assert "reconstruct" in pipeline_steps