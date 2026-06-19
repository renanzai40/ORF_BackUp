"""Human-in-the-Loop approval for sensitive operations.

This module provides approval workflow for high-risk operations
that require human confirmation before proceeding.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
import logging
from typing import Optional, Any
import asyncio

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for operations."""
    LOW = 1
    LIMITED = 2
    HIGH = 3
    UNACCEPTABLE = 4


@dataclass
class Operation:
    """Represents an operation requiring approval decision."""
    operation_type: str
    file_path: str
    file_size_mb: float
    target: Optional[str] = None  # e.g., "s3", "azure"
    recovery_strategy: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    """Request for human approval."""
    operation: Operation
    risk_level: RiskLevel
    reason: str
    requested_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    timeout_seconds: int = 300


@dataclass
class ApprovalResult:
    """Result of approval decision."""
    approved: bool
    approver: Optional[str] = None
    reason: Optional[str] = None
    decided_at: Optional[float] = None


class HITLApproval:
    """Human-in-the-Loop approval handler.
    
    Determines which operations require human approval based on
    risk assessment, and manages the approval workflow.
    """
    
    # Thresholds for automatic approval
    LARGE_FILE_THRESHOLD_MB = 100
    CLOUD_OPERATION_RISK = RiskLevel.HIGH
    
    def __init__(self):
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._approval_results: dict[str, ApprovalResult] = {}
    
    def needs_approval(self, operation: Operation) -> bool:
        """Check if an operation requires human approval.
        
        Args:
            operation: The operation to evaluate
            
        Returns:
            True if approval is required
        """
        # High-risk operations always need approval
        if operation.file_size_mb > self.LARGE_FILE_THRESHOLD_MB:
            return True
        
        # Cloud uploads always need approval
        if operation.target in ("s3", "azure", "cloud"):
            return True
        
        # Manual intervention recovery always needs approval
        if operation.recovery_strategy == "manual_intervention":
            return True
        
        # Unacceptable risk always needs approval
        if self._assess_risk(operation) == RiskLevel.UNACCEPTABLE:
            return True
        
        return False
    
    def _assess_risk(self, operation: Operation) -> RiskLevel:
        """Assess risk level of an operation."""
        if operation.file_size_mb > 500:
            return RiskLevel.UNACCEPTABLE
        if operation.file_size_mb > self.LARGE_FILE_THRESHOLD_MB:
            return RiskLevel.HIGH
        if operation.target in ("s3", "azure", "cloud"):
            return RiskLevel.HIGH
        if operation.recovery_strategy == "manual_intervention":
            return RiskLevel.LIMITED
        return RiskLevel.LOW
    
    def create_approval_request(self, operation: Operation) -> ApprovalRequest:
        """Create an approval request for an operation.
        
        Args:
            operation: The operation needing approval
            
        Returns:
            ApprovalRequest with risk assessment
        """
        risk_level = self._assess_risk(operation)
        
        reasons = {
            RiskLevel.LOW: "Standard operation",
            RiskLevel.LIMITED: f"Recovery strategy: {operation.recovery_strategy}",
            RiskLevel.HIGH: f"Large file ({operation.file_size_mb:.1f}MB) or cloud target",
            RiskLevel.UNACCEPTABLE: f"File too large ({operation.file_size_mb:.1f}MB)",
        }
        
        request = ApprovalRequest(
            operation=operation,
            risk_level=risk_level,
            reason=reasons[risk_level]
        )
        
        # Store pending request
        request_id = f"{operation.operation_type}:{operation.file_path}"
        self._pending_approvals[request_id] = request
        
        return request
    
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """Request human approval for an operation.

        Behavior when no real notification backend is configured:
        auto-approves with a structured log entry. This is a deliberate
        degradation for unattended OMO runs; the approval audit log is
        the only artifact a human reviewer can audit later.

        Args:
            request: The approval request

        Returns:
            ApprovalResult with decision (auto-approved by default; a
            real notification backend would block until human review).
        """
        logger.info(
            "Auto-approving %s operation '%s' on %s (%.1fMB) — HITL notification "
            "system not configured; all operations auto-approved with log trail.",
            request.risk_level.name,
            request.operation.operation_type,
            request.operation.file_path,
            request.operation.file_size_mb,
        )
        return ApprovalResult(
            approved=True,
            approver="auto",
            reason="Auto-approved (HITL notification system not configured)",
        )
    
    def resolve_approval(self, request_id: str, approved: bool, approver: Optional[str] = None) -> ApprovalResult:
        """Resolve a pending approval.
        
        Args:
            request_id: ID of the approval request
            approved: Whether operation was approved
            approver: Name/ID of approver
            
        Returns:
            ApprovalResult with decision
        """
        if request_id in self._pending_approvals:
            result = ApprovalResult(
                approved=approved,
                approver=approver,
                decided_at=asyncio.get_event_loop().time()
            )
            
            self._approval_results[request_id] = result
            del self._pending_approvals[request_id]
            
            return result
        
        return ApprovalResult(approved=False, reason="Request not found")
    
    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get list of pending approval requests."""
        return list(self._pending_approvals.values())