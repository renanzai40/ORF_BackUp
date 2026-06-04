"""Tests for the Human-in-the-Loop approval workflow.

Covers:
- RiskLevel enum (4 values)
- Operation / ApprovalRequest / ApprovalResult dataclasses
- HITLApproval.needs_approval — file_size thresholds, cloud target, manual_intervention
- HITLApproval._assess_risk — every branch
- HITLApproval.create_approval_request — populates _pending_approvals
- HITLApproval.request_approval (async) — auto-approve LOW, pending for HIGH
- HITLApproval.resolve_approval — happy path, unknown request_id
- HITLApproval.get_pending_approvals — returns list copy
- Threshold constants
"""

from __future__ import annotations

import asyncio

import pytest

from orf.workflow.hitl_approval import (
    ApprovalRequest,
    ApprovalResult,
    HITLApproval,
    Operation,
    RiskLevel,
)


# The source uses the deprecated ``asyncio.get_event_loop().time()`` pattern in
# ``ApprovalRequest.requested_at``'s default factory. On Python 3.13 that raises
# RuntimeError when no current event loop exists. Some of these tests also call
# ``asyncio.run`` which closes its loop on completion, so we must re-establish
# a default loop on every test, not once per session.
@pytest.fixture(autouse=True)
def _ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


# =============================================================================
# RiskLevel enum
# =============================================================================


class TestRiskLevelEnum:
    def test_has_four_values(self):
        assert len(list(RiskLevel)) == 4

    def test_low_value(self):
        assert RiskLevel.LOW.value == 1

    def test_limited_value(self):
        assert RiskLevel.LIMITED.value == 2

    def test_high_value(self):
        assert RiskLevel.HIGH.value == 3

    def test_unacceptable_value(self):
        assert RiskLevel.UNACCEPTABLE.value == 4

    def test_names(self):
        names = {r.name for r in RiskLevel}
        assert names == {"LOW", "LIMITED", "HIGH", "UNACCEPTABLE"}


# =============================================================================
# Dataclasses
# =============================================================================


class TestOperationDataclass:
    def test_minimal_creation(self):
        op = Operation(
            operation_type="convert",
            file_path="/tmp/a.md",
            file_size_mb=10.0,
        )
        assert op.operation_type == "convert"
        assert op.file_path == "/tmp/a.md"
        assert op.file_size_mb == 10.0
        assert op.target is None
        assert op.recovery_strategy is None
        assert op.metadata == {}

    def test_full_creation(self):
        op = Operation(
            operation_type="upload",
            file_path="/tmp/a.md",
            file_size_mb=200.0,
            target="s3",
            recovery_strategy="manual_intervention",
            metadata={"k": "v"},
        )
        assert op.target == "s3"
        assert op.recovery_strategy == "manual_intervention"
        assert op.metadata == {"k": "v"}

    def test_metadata_default_is_independent_per_instance(self):
        op_a = Operation(operation_type="x", file_path="a", file_size_mb=1.0)
        op_b = Operation(operation_type="y", file_path="b", file_size_mb=1.0)
        op_a.metadata["k"] = "v"
        assert op_b.metadata == {}


class TestApprovalRequestDataclass:
    def test_creation(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        req = ApprovalRequest(
            operation=op,
            risk_level=RiskLevel.LOW,
            reason="Standard operation",
        )
        assert req.operation is op
        assert req.risk_level == RiskLevel.LOW
        assert req.reason == "Standard operation"
        # requested_at default is a float
        assert isinstance(req.requested_at, float)
        # default timeout
        assert req.timeout_seconds == 300


class TestApprovalResultDataclass:
    def test_approved_creation(self):
        res = ApprovalResult(approved=True, approver="alice", reason="ok")
        assert res.approved is True
        assert res.approver == "alice"
        assert res.reason == "ok"
        assert res.decided_at is None

    def test_denied_creation(self):
        res = ApprovalResult(approved=False, reason="nope")
        assert res.approved is False
        assert res.reason == "nope"
        assert res.approver is None
        assert res.decided_at is None


# =============================================================================
# Threshold constants
# =============================================================================


class TestThresholdConstants:
    def test_large_file_threshold_is_100mb(self):
        assert HITLApproval.LARGE_FILE_THRESHOLD_MB == 100

    def test_cloud_operation_risk_is_high(self):
        assert HITLApproval.CLOUD_OPERATION_RISK == RiskLevel.HIGH


# =============================================================================
# _assess_risk — every branch
# =============================================================================


class TestAssessRisk:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_unacceptable_above_500mb(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=600.0,
        )
        assert self.hitl._assess_risk(op) == RiskLevel.UNACCEPTABLE

    def test_unacceptable_at_500mb(self):
        # Strict > 500, not >=
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=501.0,
        )
        assert self.hitl._assess_risk(op) == RiskLevel.UNACCEPTABLE

    def test_high_above_100mb(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=150.0,
        )
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_high_cloud_target_s3(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0, target="s3",
        )
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_high_cloud_target_azure(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0, target="azure",
        )
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_high_cloud_target_cloud(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0, target="cloud",
        )
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_limited_manual_intervention(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0,
            recovery_strategy="manual_intervention",
        )
        assert self.hitl._assess_risk(op) == RiskLevel.LIMITED

    def test_low_default(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0,
        )
        assert self.hitl._assess_risk(op) == RiskLevel.LOW


# =============================================================================
# needs_approval — every branch
# =============================================================================


class TestNeedsApproval:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_small_local_operation_no_approval(self):
        op = Operation(operation_type="x", file_path="a", file_size_mb=10.0)
        assert self.hitl.needs_approval(op) is False

    def test_large_file_over_100mb_needs_approval(self):
        op = Operation(operation_type="x", file_path="a", file_size_mb=200.0)
        assert self.hitl.needs_approval(op) is True

    def test_at_100mb_does_not_need_approval(self):
        # Strictly > 100, not >=
        op = Operation(operation_type="x", file_path="a", file_size_mb=100.0)
        assert self.hitl.needs_approval(op) is False

    def test_at_101mb_needs_approval(self):
        op = Operation(operation_type="x", file_path="a", file_size_mb=101.0)
        assert self.hitl.needs_approval(op) is True

    def test_over_500mb_needs_approval(self):
        op = Operation(operation_type="x", file_path="a", file_size_mb=600.0)
        assert self.hitl.needs_approval(op) is True

    def test_cloud_target_s3_needs_approval(self):
        op = Operation(
            operation_type="upload", file_path="a",
            file_size_mb=10.0, target="s3",
        )
        assert self.hitl.needs_approval(op) is True

    def test_cloud_target_azure_needs_approval(self):
        op = Operation(
            operation_type="upload", file_path="a",
            file_size_mb=10.0, target="azure",
        )
        assert self.hitl.needs_approval(op) is True

    def test_cloud_target_cloud_needs_approval(self):
        op = Operation(
            operation_type="upload", file_path="a",
            file_size_mb=10.0, target="cloud",
        )
        assert self.hitl.needs_approval(op) is True

    def test_local_target_does_not_need_approval(self):
        op = Operation(
            operation_type="convert", file_path="a",
            file_size_mb=10.0, target="local",
        )
        assert self.hitl.needs_approval(op) is False

    def test_manual_intervention_needs_approval(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0,
            recovery_strategy="manual_intervention",
        )
        assert self.hitl.needs_approval(op) is True

    def test_other_recovery_strategy_does_not_need_approval(self):
        op = Operation(
            operation_type="x", file_path="a", file_size_mb=10.0,
            recovery_strategy="retry",
        )
        assert self.hitl.needs_approval(op) is False


# =============================================================================
# create_approval_request
# =============================================================================


class TestCreateApprovalRequest:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_creates_low_risk_request(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        req = self.hitl.create_approval_request(op)

        assert req.risk_level == RiskLevel.LOW
        assert req.operation is op
        assert req.reason == "Standard operation"

    def test_creates_high_risk_request(self):
        op = Operation(
            operation_type="upload", file_path="a.md",
            file_size_mb=150.0, target="s3",
        )
        req = self.hitl.create_approval_request(op)

        assert req.risk_level == RiskLevel.HIGH
        assert "Large file" in req.reason or "cloud" in req.reason.lower()

    def test_creates_unacceptable_request(self):
        op = Operation(
            operation_type="x", file_path="a.md", file_size_mb=600.0,
        )
        req = self.hitl.create_approval_request(op)

        assert req.risk_level == RiskLevel.UNACCEPTABLE
        assert "too large" in req.reason.lower()

    def test_creates_limited_request(self):
        op = Operation(
            operation_type="x", file_path="a.md", file_size_mb=10.0,
            recovery_strategy="manual_intervention",
        )
        req = self.hitl.create_approval_request(op)

        assert req.risk_level == RiskLevel.LIMITED
        assert "manual_intervention" in req.reason

    def test_pending_approvals_populated(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op)

        assert "convert:a.md" in self.hitl._pending_approvals
        assert isinstance(
            self.hitl._pending_approvals["convert:a.md"], ApprovalRequest
        )

    def test_multiple_requests_tracked(self):
        for i in range(3):
            op = Operation(
                operation_type="convert", file_path=f"file_{i}.md",
                file_size_mb=10.0,
            )
            self.hitl.create_approval_request(op)

        assert len(self.hitl._pending_approvals) == 3


# =============================================================================
# request_approval (async)
# =============================================================================


class TestRequestApproval:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_request_approval_auto_approves_low_risk(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        req = self.hitl.create_approval_request(op)
        assert req.risk_level == RiskLevel.LOW

        result = asyncio.run(self.hitl.request_approval(req))

        assert isinstance(result, ApprovalResult)
        assert result.approved is True
        assert "low risk" in (result.reason or "").lower()

    def test_request_approval_returns_pending_for_high_risk(self):
        op = Operation(
            operation_type="upload", file_path="big.md",
            file_size_mb=200.0, target="s3",
        )
        req = self.hitl.create_approval_request(op)
        assert req.risk_level == RiskLevel.HIGH

        result = asyncio.run(self.hitl.request_approval(req))

        assert result.approved is False
        assert "pending" in (result.reason or "").lower()

    def test_request_approval_returns_pending_for_unacceptable(self):
        op = Operation(
            operation_type="x", file_path="huge.md", file_size_mb=600.0,
        )
        req = self.hitl.create_approval_request(op)
        result = asyncio.run(self.hitl.request_approval(req))

        assert result.approved is False


# =============================================================================
# resolve_approval
# =============================================================================


class TestResolveApproval:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_resolve_known_request(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op)

        result = self.hitl.resolve_approval("convert:a.md", approved=True, approver="bob")
        assert result.approved is True
        assert result.approver == "bob"
        # Removed from pending
        assert "convert:a.md" not in self.hitl._pending_approvals

    def test_resolve_known_request_denied(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op)

        result = self.hitl.resolve_approval("convert:a.md", approved=False)
        assert result.approved is False
        assert "convert:a.md" not in self.hitl._pending_approvals

    def test_resolve_unknown_request_id(self):
        result = self.hitl.resolve_approval("nonexistent:id", approved=True)
        assert result.approved is False
        assert result.reason == "Request not found"

    def test_resolve_stores_in_approval_results(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op)
        self.hitl.resolve_approval("convert:a.md", approved=True)

        assert "convert:a.md" in self.hitl._approval_results


# =============================================================================
# get_pending_approvals
# =============================================================================


class TestGetPendingApprovals:
    def setup_method(self):
        self.hitl = HITLApproval()

    def test_empty_initially(self):
        assert self.hitl.get_pending_approvals() == []

    def test_returns_list_copy(self):
        op1 = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        op2 = Operation(operation_type="convert", file_path="b.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op1)
        self.hitl.create_approval_request(op2)

        pending = self.hitl.get_pending_approvals()
        assert len(pending) == 2

        # Mutating the returned list must not affect internal state
        pending.clear()
        assert len(self.hitl.get_pending_approvals()) == 2

    def test_resolved_requests_not_in_pending(self):
        op = Operation(operation_type="convert", file_path="a.md", file_size_mb=10.0)
        self.hitl.create_approval_request(op)
        self.hitl.resolve_approval("convert:a.md", approved=True)

        assert self.hitl.get_pending_approvals() == []
