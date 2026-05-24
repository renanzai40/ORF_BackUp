"""Pydantic models for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class ErrorDetail(BaseModel):
    """Error information matching orf.converters.base.ErrorDetail."""
    code: str
    message: str
    recovery_strategy: Optional[str] = None


class WarningDetail(BaseModel):
    """Warning information matching orf.converters.base.WarningDetail."""
    code: str
    message: str


class ApplyMdInput(BaseModel):
    """Input for apply_md tool."""
    input_md: str = Field(..., description="Input MD file path")
    target_format: str = Field(..., description="Target format (docx, odt, epub, etc.)")
    output_path: Optional[str] = Field(None, description="Optional output path")


class ApplyMdResult(BaseModel):
    """Result from apply_md tool."""
    success: bool
    output_path: Optional[str]
    errors: list[ErrorDetail] = Field(default_factory=list)
    warnings: list[WarningDetail] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplyXLIFFInput(BaseModel):
    """Input for apply_xliff tool."""
    input_file: str = Field(..., description="Original document file path")
    xliff_path: str = Field(..., description="Translated XLIFF file path")
    output_path: str = Field(..., description="Output file path")
    format: str = Field(..., description="Output format (docx, pptx, epub, html, odt)")


class ApplyXLIFFResult(BaseModel):
    """Result from apply_xliff tool."""
    success: bool
    output_path: Optional[str]
    errors: list[ErrorDetail] = Field(default_factory=list)
    warnings: list[WarningDetail] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchConvertInput(BaseModel):
    """Input for batch_convert tool."""
    input_dir: str = Field(..., description="Input directory containing MD files")
    target_format: str = Field(..., description="Target format")
    pattern: str = Field(default="*.md", description="File pattern to match")


class BatchResult(BaseModel):
    """Result from batch_convert tool."""
    success_count: int
    fail_count: int
    total: int
    errors: list[ErrorDetail] = Field(default_factory=list)


class DetectFormatInput(BaseModel):
    """Input for detect_format tool."""
    file_path: str = Field(..., description="File to detect format for")


class DetectFormatResult(BaseModel):
    """Result from detect_format tool."""
    format: str
    confidence: float = 1.0


class InfoInput(BaseModel):
    """Input for info tool."""
    file_path: str = Field(..., description="File to get info for")


class InfoResult(BaseModel):
    """Result from info tool."""
    format: str
    size_mb: float
    resource_count: Optional[int] = None
    manifest_status: str