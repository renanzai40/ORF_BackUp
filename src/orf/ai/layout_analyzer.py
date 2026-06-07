"""AI-powered document overflow detection using vision analysis."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
import tempfile
import subprocess

from orf.logging import get_logger

logger = get_logger("ai.layout_analyzer")


class Severity(Enum):
    """Severity levels for overflow issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class OverflowIssue:
    """Represents a text overflow issue in a document element."""
    file_path: str
    element_id: str
    original_text: str
    overflow_percentage: float
    severity: Severity

    def __post_init__(self) -> None:
        if self.overflow_percentage < 0:
            self.overflow_percentage = 0
        if self.overflow_percentage > 100:
            self.overflow_percentage = 100
        
        if self.severity == Severity.LOW and self.overflow_percentage > 10:
            self.severity = Severity.MEDIUM
        if self.severity == Severity.MEDIUM and self.overflow_percentage > 25:
            self.severity = Severity.HIGH


@dataclass
class OverflowFix:
    """Correction suggestion for an overflow issue."""
    issue: OverflowIssue
    suggested_text: str
    reduction_percentage: float


class LayoutAnalyzer:
    """AI-powered document overflow detection.
    
    Analyzes document layouts by rendering to images and using vision API
    to detect text overflow issues.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the layout analyzer.
        
        Args:
            api_key: Optional API key for vision service. Can be set later.
        """
        self._api_key = api_key
        self._vision_client: Optional[Any] = None

    def set_api_key(self, api_key: str) -> None:
        """Set the API key for vision service.
        
        Args:
            api_key: API key for the vision service.
        """
        self._api_key = api_key
        if api_key:
            try:
                from openai import OpenAI
                self._vision_client = OpenAI(api_key=api_key)
            except ImportError:
                logger.warning("openai package not installed")
                self._vision_client = None

    def _get_vision_client(self) -> Optional[Any]:
        """Get or create the vision client lazily.
        
        Returns:
            OpenAI client instance or None if not available.
        """
        if self._vision_client is None and self._api_key:
            try:
                from openai import OpenAI
                self._vision_client = OpenAI(api_key=self._api_key)
            except ImportError:
                logger.warning("openai package not installed")
                return None
        return self._vision_client

    def _render_to_images(self, document_path: Path) -> List[Path]:
        """Render document to images for vision analysis.
        
        Args:
            document_path: Path to the document file.
            
        Returns:
            List of paths to rendered images.
        """
        logger.info(f"Rendering document to images: {document_path}")
        
        images = []
        suffix = document_path.suffix.lower()
        
        if suffix == ".pdf":
            images = self._render_pdf(document_path)
        elif suffix in [".docx", ".doc"]:
            images = self._render_docx(document_path)
        elif suffix in [".md", ".html", ".htm"]:
            images = self._render_markup(document_path)
        else:
            logger.warning(f"Unsupported document format: {suffix}")
            
        return images

    def _render_pdf(self, pdf_path: Path) -> List[Path]:
        """Render PDF to images using ImageMagick or similar.
        
        Args:
            pdf_path: Path to PDF file.
            
        Returns:
            List of paths to rendered images.
        """
        images = []
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                _ = subprocess.run(
                    ["pdftoppm", "-png", "-r", "150", str(pdf_path),
                     str(Path(tmpdir) / "page")],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                images = list(Path(tmpdir).glob("page-*.png"))
                logger.info(f"Rendered {len(images)} pages from PDF")
            except subprocess.CalledProcessError as e:
                logger.warning(f"pdftoppm failed: {e.stderr}")
            except FileNotFoundError:
                logger.warning("pdftoppm not found, cannot render PDF")

        return images

    def _render_docx(self, docx_path: Path) -> List[Path]:
        """Render DOCX to images using LibreOffice.
        
        Args:
            docx_path: Path to DOCX file.
            
        Returns:
            List of paths to rendered images.
        """
        images = []
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                _ = subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "png",
                     "--outdir", tmpdir, str(docx_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                images = list(Path(tmpdir).glob("*.png"))
                logger.info(f"Rendered {len(images)} images from DOCX")
            except subprocess.CalledProcessError as e:
                logger.warning(f"LibreOffice failed: {e.stderr}")
            except FileNotFoundError:
                logger.warning("LibreOffice not found, cannot render DOCX")

        return images

    def _render_markup(self, markup_path: Path) -> List[Path]:
        """Render markup (MD/HTML) to images using pandoc.
        
        Args:
            markup_path: Path to markup file.
            
        Returns:
            List of paths to rendered images.
        """
        images = []
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                pdf_path = Path(tmpdir) / "output.pdf"
                _ = subprocess.run(
                    ["pandoc", str(markup_path), "-o", str(pdf_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                if pdf_path.exists():
                    images = self._render_pdf(pdf_path)
            except subprocess.CalledProcessError as e:
                logger.warning(f"pandoc failed: {e.stderr}")
            except FileNotFoundError:
                logger.warning("pandoc not found, cannot render markup")

        return images

    def _call_vision_api(self, images: List[Path]) -> List[Dict[str, Any]]:
        """Call vision API to detect overflow in rendered images.

        ULTRAREADY-VERIFY (2026-06-07): the previous behavior returned
        fabricated mock data when no API key was configured or the
        client init failed. That silently poisoned any future integration.
        This method now raises RuntimeError instead — production code
        must fail loud.

        Args:
            images: List of image paths to analyze.

        Returns:
            List of detection results with overflow information.

        Raises:
            RuntimeError: if no API key is configured, the vision
                client cannot be initialized, or the API call fails.
        """
        if not self._api_key:
            raise RuntimeError(
                "vision API key required (ULTRAREADY-VERIFY: no mock "
                "fallback in production)"
            )

        logger.info(f"Calling vision API for {len(images)} images")

        import base64
        client = self._get_vision_client()
        if client is None:
            raise RuntimeError(
                "vision client init failed (ULTRAREADY-VERIFY: no mock "
                "fallback in production)"
            )

        results = []
        for img_path in images:
            with open(img_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}},
                        {"type": "text", "text": "Analyze this document page for text overflow issues. "
                         "Look for text that extends beyond containers, cut-off content, "
                         "or layout problems. Return JSON with elements that have overflow: "
                         "[{\"element_id\": \"...\", \"overflow_percentage\": ..., \"text\": \"...\"}]"}
                    ]
                }],
                max_tokens=2048
            )

            import json
            content = response.choices[0].message.content
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            results.extend(json.loads(content))

        return results

    def _mock_vision_results(self, images: List[Path]) -> List[Dict[str, Any]]:
        """Return mock vision results when API is not available.
        
        Args:
            images: List of image paths (used for count only).
            
        Returns:
            Mock overflow detection results.
        """
        logger.info("Using mock vision results")
        
        mock_elements = [
            {"element_id": "p_001", "overflow_percentage": 15.5, "text": "Sample text that might overflow"},
            {"element_id": "h_002", "overflow_percentage": 8.2, "text": "Heading text"},
        ]
        
        return mock_elements[:len(images)]

    def analyze(self, document_path: Path) -> List[OverflowIssue]:
        """Analyze a document for overflow issues.
        
        Args:
            document_path: Path to the document to analyze.
            
        Returns:
            List of OverflowIssue objects detected in the document.
        """
        logger.info(f"Analyzing document: {document_path}")
        
        if not document_path.exists():
            logger.error(f"Document not found: {document_path}")
            return []
            
        images = self._render_to_images(document_path)
        
        if not images:
            logger.warning("No images generated, cannot analyze")
            return []
            
        vision_results = self._call_vision_api(images)
        
        issues = []
        for result in vision_results:
            severity = Severity.LOW
            if result.get("overflow_percentage", 0) > 25:
                severity = Severity.HIGH
            elif result.get("overflow_percentage", 0) > 10:
                severity = Severity.MEDIUM
                
            issue = OverflowIssue(
                file_path=str(document_path),
                element_id=result.get("element_id", "unknown"),
                original_text=result.get("text", ""),
                overflow_percentage=result.get("overflow_percentage", 0),
                severity=severity
            )
            issues.append(issue)
            
        logger.info(f"Found {len(issues)} overflow issues")
        return issues

    def fix_overflow(self, issue: OverflowIssue) -> Optional[OverflowFix]:
        """Generate correction suggestions for an overflow issue using LLM.

        ULTRAREADY-VERIFY (2026-06-07): the previous behavior returned a
        fabricated mock fix when no API key was configured or the
        client init failed. Production code must fail loud.

        Args:
            issue: The overflow issue to fix.

        Returns:
            OverflowFix with suggested shorter text, or None if cannot fix.

        Raises:
            RuntimeError: if no API key is configured, the vision
                client cannot be initialized, or the LLM call fails.
        """
        logger.info(f"Generating fix for issue: {issue.element_id}")

        if not self._api_key:
            raise RuntimeError(
                "vision API key required (ULTRAREADY-VERIFY: no mock "
                "fallback in production)"
            )

        client = self._get_vision_client()
        if client is None:
            raise RuntimeError(
                "vision client init failed (ULTRAREADY-VERIFY: no mock "
                "fallback in production)"
            )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": f"""Suggest a shorter version of this text that conveys
                the same meaning but fits better in a document layout.
                Original text: {issue.original_text}
                Current overflow: {issue.overflow_percentage}%

                Return JSON: {{"suggested_text": "...", "reduction_percentage": ...}}
                """
            }],
            max_tokens=1024
        )

        import json
        content = response.choices[0].message.content
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        result = json.loads(content)

        return OverflowFix(
            issue=issue,
            suggested_text=result.get("suggested_text", issue.original_text),
            reduction_percentage=result.get("reduction_percentage", 0)
        )

    def _mock_fix_suggestion(self, issue: OverflowIssue) -> Optional[OverflowFix]:
        """Generate mock fix suggestion when API is not available.
        
        Args:
            issue: The overflow issue to fix.
            
        Returns:
            Mock OverflowFix with shortened text suggestion.
        """
        words = issue.original_text.split()
        if len(words) <= 3:
            suggested = issue.original_text
        else:
            suggested = " ".join(words[:max(1, len(words) - 2)]) + "..."
            
        reduction = min(30.0, issue.overflow_percentage * 0.8)
        
        return OverflowFix(
            issue=issue,
            suggested_text=suggested,
            reduction_percentage=reduction
        )