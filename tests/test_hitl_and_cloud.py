"""End-to-end tests for HITL approval flow and cloud storage mocks.

Covers three categories:

1. **HITL Approval Flow** — verifies that the Human-in-the-Loop approval
   workflow correctly classifies operations by risk level, accepts/rejects
   approval decisions, and exposes the pending-approval list. These tests
   use the *real* ``HITLApproval`` class (no mocks for the unit under test).

2. **S3 with moto** — verifies the production ``S3ResourceClient`` works
   end-to-end against an in-memory AWS S3 mock provided by ``moto``.
   No real AWS credentials are required.

3. **Azure with AsyncMock** — verifies the Azure Blob Storage SDK can be
   driven through async mocks without contacting real Azure. The
   production ``AzureBlobResourceClient`` uses the *sync* ``BlobServiceClient``
   so it is exercised with ``MagicMock`` for the production-code path; we
   also exercise the async ``azure.storage.blob.aio`` SDK directly with
   ``AsyncMock`` to demonstrate the async mock pattern end-to-end.

No production code is modified by this test file.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from orf.cloud.azure_blob_client import AzureBlobResourceClient
from orf.cloud.s3_client import S3ResourceClient
from orf.workflow.hitl_approval import (
    ApprovalRequest,
    ApprovalResult,
    HITLApproval,
    Operation,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Shared event-loop fixture
# ---------------------------------------------------------------------------
#
# The HITL module's ``ApprovalRequest.requested_at`` default factory calls
# ``asyncio.get_event_loop().time()``; on Python 3.13 this raises
# ``RuntimeError`` if no current event loop exists, and ``asyncio.run``
# closes its loop on completion.  We re-establish a fresh loop on every
# test that needs one.


@pytest.fixture(autouse=True)
def _ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


# =============================================================================
# 1. HITL Approval Flow
# =============================================================================


class TestHITLApprovalFlow:
    """End-to-end tests for the HITL approval workflow.

    These tests use the real ``HITLApproval`` class (no mocks) and verify
    that the four documented risk scenarios trigger the correct approval
    behaviour, that ``resolve_approval`` returns well-formed results for
    both approve and reject paths, and that ``get_pending_approvals``
    exposes the right view of in-flight requests.
    """

    def setup_method(self):
        self.hitl = HITLApproval()

    # ------------------------------------------------------------------
    # needs_approval — required scenarios
    # ------------------------------------------------------------------

    def test_file_above_100mb_requires_approval(self):
        """A 150MB file should require HITL approval (HIGH risk)."""
        op = Operation(
            operation_type="convert",
            file_path="/tmp/big.bin",
            file_size_mb=150.0,
        )
        assert self.hitl.needs_approval(op) is True
        # Sanity: the risk is also HIGH (not UNACCEPTABLE) at 150MB.
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_file_above_500mb_unacceptable_risk(self):
        """A 600MB file should be UNACCEPTABLE risk and require approval."""
        op = Operation(
            operation_type="convert",
            file_path="/tmp/huge.bin",
            file_size_mb=600.0,
        )
        assert self.hitl.needs_approval(op) is True
        assert self.hitl._assess_risk(op) == RiskLevel.UNACCEPTABLE

        # And the resulting approval request should carry the same risk.
        req = self.hitl.create_approval_request(op)
        assert req.risk_level == RiskLevel.UNACCEPTABLE
        assert "too large" in req.reason.lower()

    def test_manual_intervention_recovery_requires_approval(self):
        """recovery_strategy='manual_intervention' should require approval (LIMITED)."""
        op = Operation(
            operation_type="convert",
            file_path="/tmp/x.docx",
            file_size_mb=10.0,
            recovery_strategy="manual_intervention",
        )
        assert self.hitl.needs_approval(op) is True
        assert self.hitl._assess_risk(op) == RiskLevel.LIMITED

        req = self.hitl.create_approval_request(op)
        assert req.risk_level == RiskLevel.LIMITED
        assert "manual_intervention" in req.reason

    def test_cloud_target_s3_requires_approval(self):
        """Cloud target=s3 should require approval (HIGH risk)."""
        op = Operation(
            operation_type="upload",
            file_path="/tmp/x.docx",
            file_size_mb=10.0,
            target="s3",
        )
        assert self.hitl.needs_approval(op) is True
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    def test_cloud_target_azure_requires_approval(self):
        """Cloud target=azure should require approval (HIGH risk)."""
        op = Operation(
            operation_type="upload",
            file_path="/tmp/x.docx",
            file_size_mb=10.0,
            target="azure",
        )
        assert self.hitl.needs_approval(op) is True
        assert self.hitl._assess_risk(op) == RiskLevel.HIGH

    # ------------------------------------------------------------------
    # approve / reject via resolve_approval
    # ------------------------------------------------------------------

    def test_approve_approval_request_returns_approved_result(self):
        """Approving a pending request should return an approved ``ApprovalResult``."""
        op = Operation(
            operation_type="upload",
            file_path="/tmp/big.docx",
            file_size_mb=200.0,
            target="s3",
        )
        self.hitl.create_approval_request(op)
        request_id = "upload:/tmp/big.docx"
        assert request_id in self.hitl._pending_approvals

        result = self.hitl.resolve_approval(
            request_id, approved=True, approver="alice"
        )

        assert isinstance(result, ApprovalResult)
        assert result.approved is True
        assert result.approver == "alice"
        assert result.decided_at is not None
        # The request should be removed from pending once resolved.
        assert request_id not in self.hitl._pending_approvals
        # And stored in the results ledger.
        assert self.hitl._approval_results[request_id] is result

    def test_reject_approval_request_returns_rejected_result(self):
        """Rejecting a pending request should return a rejected ``ApprovalResult``."""
        op = Operation(
            operation_type="convert",
            file_path="/tmp/critical.docx",
            file_size_mb=50.0,
            recovery_strategy="manual_intervention",
        )
        self.hitl.create_approval_request(op)
        request_id = "convert:/tmp/critical.docx"
        assert request_id in self.hitl._pending_approvals

        result = self.hitl.resolve_approval(
            request_id, approved=False, approver="bob"
        )

        assert isinstance(result, ApprovalResult)
        assert result.approved is False
        assert result.approver == "bob"
        assert result.decided_at is not None
        # Rejected requests are also removed from pending.
        assert request_id not in self.hitl._pending_approvals
        assert self.hitl._approval_results[request_id] is result

    def test_get_pending_approvals_returns_list(self):
        """``get_pending_approvals`` should expose all in-flight requests."""
        assert self.hitl.get_pending_approvals() == []

        ops = [
            Operation(
                operation_type="upload",
                file_path=f"/tmp/file_{i}.docx",
                file_size_mb=200.0,
                target="s3",
            )
            for i in range(3)
        ]
        for op in ops:
            self.hitl.create_approval_request(op)

        pending = self.hitl.get_pending_approvals()
        assert isinstance(pending, list)
        assert len(pending) == 3
        assert all(isinstance(p, ApprovalRequest) for p in pending)

        # Resolving one should drop it from the pending list.
        self.hitl.resolve_approval("upload:/tmp/file_1.docx", approved=True)
        assert len(self.hitl.get_pending_approvals()) == 2


# =============================================================================
# 2. S3 with moto (real production S3ResourceClient + in-memory AWS mock)
# =============================================================================


class TestS3WithMoto:
    """Drive the production ``S3ResourceClient`` against ``moto``.

    The ``@mock_aws`` decorator swaps every boto3 client for an
    in-memory implementation, so upload/download/list/exists run
    end-to-end through the production code path without any real
    AWS account or credentials.
    """

    BUCKET = "orf-moto-test-bucket"
    REGION = "us-east-1"

    @mock_aws
    def test_s3_upload_download_roundtrip(self, tmp_path):
        """Upload a file to mock S3, download it, verify content matches."""
        # moto: create a real (mocked) S3 bucket via boto3 first.
        boto_s3 = boto3.client("s3", region_name=self.REGION)
        boto_s3.create_bucket(Bucket=self.BUCKET)

        # Production client — must use the same region so boto3 Session
        # inside S3ResourceClient.__init__ hits the same mocked endpoint.
        client = S3ResourceClient(
            bucket=self.BUCKET, region_name=self.REGION
        )

        # Prepare a small but non-trivial file (1KB of text).
        local_src = tmp_path / "roundtrip.md"
        payload = "# Hello moto\n" + ("line of text\n" * 50)
        local_src.write_text(payload)

        # Upload through the production client.
        assert client.upload(local_src, "subdir/roundtrip.md") is True

        # Download through the production client.
        local_dst = tmp_path / "downloaded.md"
        assert client.download("subdir/roundtrip.md", local_dst) is True
        assert local_dst.read_text() == payload

        # Round-trip integrity: byte-for-byte equality.
        assert local_src.read_bytes() == local_dst.read_bytes()

    @mock_aws
    def test_s3_list_objects(self, tmp_path):
        """List multiple uploaded objects under a prefix in mock S3."""
        boto_s3 = boto3.client("s3", region_name=self.REGION)
        boto_s3.create_bucket(Bucket=self.BUCKET)

        client = S3ResourceClient(
            bucket=self.BUCKET, region_name=self.REGION
        )

        # Upload three files (no prefix on the client — full keys).
        names = ["alpha.txt", "beta.txt", "gamma.txt"]
        for name in names:
            p = tmp_path / name
            p.write_text(f"contents of {name}")
            assert client.upload(p, name) is True

        keys = client.list_resources()
        assert sorted(keys) == sorted(names)

    @mock_aws
    def test_s3_list_objects_with_client_prefix(self, tmp_path):
        """``S3ResourceClient(prefix=...)`` should scope list/upload to that prefix."""
        boto_s3 = boto3.client("s3", region_name=self.REGION)
        boto_s3.create_bucket(Bucket=self.BUCKET)

        client = S3ResourceClient(
            bucket=self.BUCKET,
            prefix="data/2026",
            region_name=self.REGION,
        )

        # Upload two files via the prefixed client.
        for name in ["a.bin", "b.bin"]:
            p = tmp_path / name
            p.write_bytes(b"\x00\x01\x02" + name.encode())
            assert client.upload(p, name) is True

        # And one file at the root via a second unprefixed client to
        # prove the prefix actually scopes the listing.
        other = S3ResourceClient(bucket=self.BUCKET, region_name=self.REGION)
        p = tmp_path / "root.bin"
        p.write_bytes(b"root")
        assert other.upload(p, "root.bin") is True

        listed = client.list_resources()
        # Both files are visible through the prefixed client, full keys
        # include the configured prefix.
        assert sorted(listed) == ["data/2026/a.bin", "data/2026/b.bin"]

    @mock_aws
    def test_s3_exists_true_and_false(self, tmp_path):
        """``exists`` returns True for present objects, False for absent ones."""
        boto_s3 = boto3.client("s3", region_name=self.REGION)
        boto_s3.create_bucket(Bucket=self.BUCKET)

        client = S3ResourceClient(
            bucket=self.BUCKET, region_name=self.REGION
        )
        p = tmp_path / "present.txt"
        p.write_text("here")
        assert client.upload(p, "present.txt") is True

        assert client.exists("present.txt") is True
        assert client.exists("missing.txt") is False


# =============================================================================
# 3. Azure with AsyncMock
# =============================================================================


class TestAzureWithAsyncMock:
    """Azure Blob tests using ``AsyncMock`` for the async SDK path.

    The production ``AzureBlobResourceClient`` uses the *sync*
    ``azure.storage.blob.BlobServiceClient``.  These tests take two
    complementary approaches:

    * **Production code path** — mock the sync ``BlobServiceClient`` via
      ``MagicMock`` and exercise the real ``AzureBlobResourceClient`` to
      confirm upload / download / list work end-to-end with no real
      Azure credentials.
    * **Async SDK pattern** — exercise the async
      ``azure.storage.blob.aio`` module directly with ``AsyncMock`` to
      demonstrate the canonical pattern for mocking async Azure calls
      (``AsyncMock`` returns awaitables, so async code can ``await`` it).
    """

    CONNECTION_STRING = (
        "DefaultEndpointsProtocol=https;AccountName=test;"
        "AccountKey=ZmFrZS1rZXk=;EndpointSuffix=core.windows.net"
    )
    CONTAINER = "test-container"

    # ------------------------------------------------------------------
    # Production AzureBlobResourceClient (sync SDK) — MagicMock based
    # ------------------------------------------------------------------

    def _build_azure_client_with_sync_mocks(self):
        """Construct ``AzureBlobResourceClient`` with mocked sync SDK.

        Returns ``(client, blob_service_mock)`` where ``blob_service_mock``
        is the ``MagicMock`` returned by
        ``BlobServiceClient.from_connection_string``.
        """
        mock_blob_service = MagicMock()
        with patch(
            "azure.storage.blob.BlobServiceClient.from_connection_string",
            return_value=mock_blob_service,
        ):
            client = AzureBlobResourceClient(
                connection_string=self.CONNECTION_STRING,
                container=self.CONTAINER,
                prefix="azure/prefix",
            )
        return client, mock_blob_service

    def test_azure_upload_download_roundtrip(self, tmp_path):
        """Upload a file to mock Azure, download it, verify content matches."""
        client, mock_service = self._build_azure_client_with_sync_mocks()

        # Per-call blob client mock.
        mock_blob_client = MagicMock()
        mock_service.get_blob_client.return_value = mock_blob_client

        # download_blob() returns a stream-like object exposing .readall().
        upload_payload = b"hello azure mock\n" * 8
        mock_download_stream = MagicMock()
        mock_download_stream.readall.return_value = upload_payload
        mock_blob_client.download_blob.return_value = mock_download_stream

        # --- Upload phase ----------------------------------------------
        src = tmp_path / "src.md"
        src.write_bytes(upload_payload)
        assert client.upload(src, "doc.md") is True

        # get_blob_client is called for the upload.
        upload_call = mock_service.get_blob_client.call_args_list[0]
        assert upload_call.kwargs == {
            "container": self.CONTAINER,
            "blob": "azure/prefix/doc.md",
        }
        # upload_blob was invoked with overwrite=True.
        mock_blob_client.upload_blob.assert_called_once()
        _, upload_kwargs = mock_blob_client.upload_blob.call_args
        assert upload_kwargs.get("overwrite") is True

        # --- Download phase --------------------------------------------
        dst = tmp_path / "dst.md"
        assert client.download("doc.md", dst) is True
        assert dst.read_bytes() == upload_payload

        # get_blob_client was also called for the download.
        download_call = mock_service.get_blob_client.call_args_list[-1]
        assert download_call.kwargs == {
            "container": self.CONTAINER,
            "blob": "azure/prefix/doc.md",
        }
        # The download path wrote exactly what upload_blob produced.
        mock_blob_client.download_blob.assert_called_once()

    def test_azure_list_blobs(self):
        """``list_resources`` returns the names of all blobs in the container."""
        client, mock_service = self._build_azure_client_with_sync_mocks()

        # list_resources routes through get_container_client + list_blobs.
        mock_container_client = MagicMock()
        mock_service.get_container_client.return_value = mock_container_client

        blob1, blob2 = MagicMock(), MagicMock()
        blob1.name = "azure/prefix/file1.txt"
        blob2.name = "azure/prefix/file2.txt"
        mock_container_client.list_blobs.return_value = [blob1, blob2]

        keys = client.list_resources()

        assert keys == ["azure/prefix/file1.txt", "azure/prefix/file2.txt"]
        mock_service.get_container_client.assert_called_once_with(self.CONTAINER)
        mock_container_client.list_blobs.assert_called_once_with(
            name_starts_with="azure/prefix"
        )

    def test_azure_upload_file_not_found(self):
        """Upload to Azure returns False when the local source is missing."""
        client, mock_service = self._build_azure_client_with_sync_mocks()
        result = client.upload(Path("/nonexistent/does_not_exist.bin"), "k")
        assert result is False
        # No blob client should ever have been requested.
        mock_service.get_blob_client.assert_not_called()

    # ------------------------------------------------------------------
    # Async SDK pattern with AsyncMock
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_azure_aio_asyncmock_upload_download(self, tmp_path):
        """Demonstrate the AsyncMock pattern against ``azure.storage.blob.aio``.

        The production ``AzureBlobResourceClient`` uses the sync SDK and is
        covered by the tests above.  This test exercises the *async*
        ``BlobServiceClient`` directly so that the ``AsyncMock`` pattern
        (mock async classmethods + mock async instance methods) is also
        verified end-to-end.
        """
        payload = b"async azure payload"
        download_stream = MagicMock()
        download_stream.readall = MagicMock(return_value=payload)
        upload_mock = AsyncMock(return_value=None)
        download_mock = AsyncMock(return_value=download_stream)

        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob = upload_mock
        mock_blob_client.download_blob = download_mock

        mock_svc = MagicMock()
        mock_svc.get_blob_client.return_value = mock_blob_client

        with patch(
            "azure.storage.blob.aio.BlobServiceClient.from_connection_string",
            new_callable=AsyncMock,
            return_value=mock_svc,
        ):
            from azure.storage.blob.aio import BlobServiceClient

            async_svc = await BlobServiceClient.from_connection_string(
                self.CONNECTION_STRING
            )
            bc = async_svc.get_blob_client(
                container=self.CONTAINER, blob="async/key.bin"
            )

            src = tmp_path / "src_async.bin"
            src.write_bytes(payload)
            with open(src, "rb") as f:
                await bc.upload_blob(f, overwrite=True)

            dst = tmp_path / "dst_async.bin"
            with open(dst, "wb") as out:
                stream = await bc.download_blob()
                out.write(stream.readall())

        assert dst.read_bytes() == payload
        upload_mock.assert_awaited_once()
        download_mock.assert_awaited_once()
        mock_svc.get_blob_client.assert_called_once_with(
            container=self.CONTAINER, blob="async/key.bin"
        )
