"""AI-powered text overflow correction for translated documents."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from orf.logging import get_logger
from orf.ai.layout_analyzer import LayoutAnalyzer, OverflowIssue

logger = get_logger("ai.overflow_corrector")

# Language expansion ratios when translating from English
# These ratios help estimate how much text expands when translated
EXPANSION_RATIOS: Dict[Tuple[str, str], float] = {
    ("en", "zh"): 1.8,
    ("en", "de"): 1.25,
    ("en", "ja"): 1.1,
    ("en", "ko"): 1.3,
    ("en", "fr"): 1.15,
    ("en", "es"): 1.1,
}

# Fallback ratios for non-english source languages
FALLBACK_RATIOS: Dict[Tuple[str, str], float] = {
    ("zh", "en"): 0.6,
    ("de", "en"): 0.8,
    ("ja", "en"): 0.9,
    ("ko", "en"): 0.75,
    ("fr", "en"): 0.85,
    ("es", "en"): 0.9,
}


@dataclass
class OverflowIssueFixed:
    """Record of an overflow issue that was corrected."""
    file_path: str
    element_id: str
    original_text: str
    suggested_text: str
    overflow_percentage: float
    max_overflow: float
    method: str  # e.g., "llm_shorten", "expansion_ratio_hint"


class OverflowCorrector:
    """AI-powered text overflow correction for translated documents.
    
    Uses LayoutAnalyzer to detect overflow issues and LLM to generate
    shorter alternative translations when text exceeds layout constraints.
    
    Usage:
        corrector = OverflowCorrector(layout_analyzer=analyzer)
        fixed = corrector.correct_document("document.pdf", max_overflow=10.0)
    """

    def __init__(self, layout_analyzer: Optional["LayoutAnalyzer"] = None):
        """Initialize the overflow corrector.
        
        Args:
            layout_analyzer: Optional LayoutAnalyzer instance. If not provided,
                            it will be created on first use.
        """
        self._layout_analyzer = layout_analyzer

    @property
    def layout_analyzer(self) -> "LayoutAnalyzer":
        """Lazy initialization of LayoutAnalyzer."""
        if self._layout_analyzer is None:
            from orf.ai.layout_analyzer import LayoutAnalyzer
            self._layout_analyzer = LayoutAnalyzer()
        return self._layout_analyzer

    def estimate_expansion_ratio(
        self, 
        text: str, 
        source_lang: str, 
        target_lang: str
    ) -> float:
        """Estimate text expansion ratio for a language pair.
        
        Args:
            text: The text to estimate expansion for.
            source_lang: Source language code (e.g., "en", "zh").
            target_lang: Target language code (e.g., "zh", "de").
            
        Returns:
            Float ratio indicating expected text length change.
            Values > 1.0 mean expansion, < 1.0 mean contraction.
        """
        source_lang = source_lang.lower()
        target_lang = target_lang.lower()
        
        # Check exact pair match
        pair = (source_lang, target_lang)
        if pair in EXPANSION_RATIOS:
            ratio = EXPANSION_RATIOS[pair]
            logger.debug(
                f"Expansion ratio for {source_lang}->{target_lang}: {ratio}"
            )
            return ratio
        
        # Check reverse pair (translation direction)
        reverse_pair = (target_lang, source_lang)
        if reverse_pair in EXPANSION_RATIOS:
            ratio = 1.0 / EXPANSION_RATIOS[reverse_pair]
            logger.debug(
                f"Reverse expansion ratio for {source_lang}->{target_lang}: {ratio}"
            )
            return ratio
        
        # Check fallback ratios
        if pair in FALLBACK_RATIOS:
            ratio = FALLBACK_RATIOS[pair]
            logger.debug(
                f"Fallback ratio for {source_lang}->{target_lang}: {ratio}"
            )
            return ratio
        
        # Default to no expansion
        logger.debug(
            f"No specific ratio for {source_lang}->{target_lang}, using 1.0"
        )
        return 1.0

    def correct_document(
        self, 
        path: Path | str, 
        max_overflow: float = 10.0
    ) -> List[OverflowIssueFixed]:
        """Correct overflow issues in a document.
        
        Analyzes the document using LayoutAnalyzer, identifies elements
        where overflow_percentage exceeds max_overflow, and generates
        shorter text alternatives using LLM.
        
        Args:
            path: Path to the document file.
            max_overflow: Maximum allowed overflow percentage. Elements
                         exceeding this will be corrected.
            
        Returns:
            List of OverflowIssueFixed objects for each correction made.
        """
        path = Path(path)
        logger.info(f"Correcting overflow in document: {path}")
        
        # Analyze document for overflow issues
        issues = self.layout_analyzer.analyze(path)
        
        if not issues:
            logger.info("No overflow issues found in document")
            return []
        
        # Filter issues that exceed max_overflow
        exceeding_issues = [
            issue for issue in issues 
            if issue.overflow_percentage > max_overflow
        ]
        
        if not exceeding_issues:
            logger.info(
                f"All {len(issues)} issues are within max_overflow ({max_overflow}%)"
            )
            return []
        
        logger.info(
            f"Found {len(exceeding_issues)} issues exceeding {max_overflow}% overflow"
        )
        
        fixed_issues = []
        for issue in exceeding_issues:
            fix = self._generate_shorter_text(issue)
            if fix:
                logger.info(
                    f"Fixed overflow in {issue.element_id}: "
                    f"{issue.overflow_percentage:.1f}% -> {fix.suggested_text[:30]}..."
                )
                fixed_issues.append(fix)
        
        logger.info(f"Corrected {len(fixed_issues)} overflow issues")
        return fixed_issues

    def _generate_shorter_text(
        self, 
        issue: "OverflowIssue"
    ) -> Optional[OverflowIssueFixed]:
        """Generate a shorter version of text to fix overflow.
        
        This is a placeholder that would call LLM in production.
        
        Args:
            issue: The overflow issue to fix.
            
        Returns:
            OverflowIssueFixed with suggested shorter text, or None if failed.
        """
        logger.debug(f"Generating shorter text for {issue.element_id}")
        
        # Placeholder implementation - in production this would call LLM
        # to suggest a shorter translation that preserves meaning
        original_text = issue.original_text
        overflow_pct = issue.overflow_percentage
        
        # Simple heuristic shortening (placeholder for LLM)
        words = original_text.split()
        if len(words) <= 2:
            # Cannot shorten further
            return None
        
        # Estimate how much to reduce based on overflow percentage
        # If overflow is 30%, we need to reduce text by roughly 30%
        reduction_factor = overflow_pct / 100.0
        target_words = max(1, int(len(words) * (1 - reduction_factor * 0.5)))
        target_words = min(target_words, len(words))
        
        # Take first portion and add ellipsis
        if target_words >= len(words):
            return None
            
        suggested = " ".join(words[:target_words]) + "..."
        
        return OverflowIssueFixed(
            file_path=issue.file_path,
            element_id=issue.element_id,
            original_text=original_text,
            suggested_text=suggested,
            overflow_percentage=issue.overflow_percentage,
            max_overflow=issue.overflow_percentage,  # Already exceeded
            method="llm_shorten_placeholder"
        )

    def suggest_shorter_translation(
        self, 
        text: str, 
        target_lang: str,
        max_length_ratio: float = 0.8
    ) -> str:
        """Suggest a shorter version of translation for overflow prevention.
        
        This is a placeholder method that would use LLM to generate
        a more concise translation that fits layout constraints.
        
        Args:
            text: Original text to shorten.
            target_lang: Target language code.
            max_length_ratio: Maximum length as ratio of original (0.0-1.0).
            
        Returns:
            Shorter version of the text that preserves meaning.
        """
        logger.debug(f"Suggesting shorter translation for {target_lang}")
        
        # Placeholder: simple truncation with ellipsis
        # In production, this would use LLM to rewrite concisely
        words = text.split()
        target_count = max(1, int(len(words) * max_length_ratio))
        
        if target_count >= len(words):
            return text
            
        return " ".join(words[:target_count]) + "..."


__all__ = [
    "OverflowCorrector", 
    "OverflowIssueFixed",
    "EXPANSION_RATIOS",
]